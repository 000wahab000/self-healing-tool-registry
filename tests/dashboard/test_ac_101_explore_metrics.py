"""AC-101: scenario and prompt runs (POST /api/explore) feed the Metrics impact cards."""

from __future__ import annotations

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from dashboard.app import create_app


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ("JEV_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY", "DB_PATH"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
async def client(tmp_path):
    app = create_app(str(tmp_path / "ac101.db"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dash") as c:
        yield c
    await app.state.dash.aclose()


async def impact(client) -> dict:
    return (await client.get("/api/state")).json()["metrics"]["impact"]


async def explore(client, agent: str = "scripted", mutation: str = "M1") -> dict:
    r = await client.post(
        "/api/explore", json={"query": "q", "mutation": mutation, "agent": agent}
    )
    assert r.status_code == 200, r.text
    return r.json()


async def test_ac_101_scripted_explore_feeds_impact_cards(client):
    before = await impact(client)
    assert before["baseline_calls"] == before["healing_calls"] == 0

    result = await explore(client)
    imp = await impact(client)
    assert imp["healing_calls"] == len(result["healing"]["traces"]) > 0
    assert imp["baseline_calls"] == len(result["baseline"]["traces"]) > 0
    assert imp["turns_saved"] == max(0, imp["baseline_calls"] - imp["healing_calls"])
    assert imp["turns_saved"] > 0
    assert imp["tokens_measured"] is False  # scripted: estimate stays labelled


async def test_ac_101_explore_accumulates_and_reset_zeroes(client):
    await explore(client)
    first = await impact(client)
    await explore(client)
    second = await impact(client)
    assert second["healing_calls"] == 2 * first["healing_calls"]
    assert second["baseline_calls"] == 2 * first["baseline_calls"]

    assert (await client.post("/api/reset")).status_code == 200
    after = await impact(client)
    assert after["healing_calls"] == after["baseline_calls"] == after["turns_saved"] == 0

    await explore(client)
    assert (await impact(client))["baseline_calls"] == first["baseline_calls"]


class UsageLLM(GenericFakeChatModel):
    """Offline model that reports 10 tokens per reply, so the run measures tokens."""

    bound: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound = [convert_to_openai_tool(tool) for tool in tools]
        return self

    def _generate(self, messages, *args, **kwargs):
        if any(isinstance(m, ToolMessage) for m in messages):
            reply = AIMessage(content="done")
        else:
            reply = AIMessage(
                content="",
                tool_calls=[{"name": "get_user", "args": {"user_id": "123"}, "id": "t"}],
            )
        reply.usage_metadata = {"input_tokens": 6, "output_tokens": 4, "total_tokens": 10}
        return ChatResult(generations=[ChatGeneration(message=reply)])


async def test_ac_101_llm_explore_records_measured_tokens_without_double_logging(
    client, monkeypatch
):
    monkeypatch.setenv("NVIDIA_API_KEY", "dummy-key")
    monkeypatch.setattr("agents.common.make_llm", lambda: UsageLLM(messages=iter(())))
    result = await explore(client, agent="llm", mutation="M5")

    imp = await impact(client)
    assert imp["tokens_measured"] is True
    assert imp["baseline_tokens"] == result["baseline"]["llm_tokens"] > 0
    assert imp["healing_tokens"] == result["healing"]["llm_tokens"] > 0
    # make_tools logs each call once; the tracing executor must not log it again.
    assert imp["healing_calls"] == len(result["healing"]["traces"])
    assert imp["baseline_calls"] == len(result["baseline"]["traces"])

    assert (await client.post("/api/reset")).status_code == 200
    assert (await impact(client))["tokens_measured"] is False
