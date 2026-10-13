"""Offline agent tests: scripted fake chat model, in-process mock API, no network."""

from __future__ import annotations

import itertools
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

from agents import baseline_agent, common, healing_agent
from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app

CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}
TOOLS_JSON = Path(__file__).parents[2] / "config" / "tools.json"
TOKENS = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
_ids = itertools.count()


class FakeLLM(GenericFakeChatModel):
    """Replays a script of AIMessages; records the tools bound and the messages of every call."""

    bound: list = Field(default_factory=list)
    seen: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.bound = [convert_to_openai_tool(t) for t in tools]
        return self

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(list(messages))
        return super()._generate(messages, *args, **kwargs)


def call(name: str, **args) -> AIMessage:
    tool_call = {"name": name, "args": args, "id": f"call-{next(_ids)}"}
    return AIMessage(content="", tool_calls=[tool_call], usage_metadata=TOKENS)


def say(text: str) -> AIMessage:
    return AIMessage(content=text, usage_metadata=TOKENS)


def llm(*script: AIMessage) -> FakeLLM:
    return FakeLLM(messages=iter(script))


def last_tool_result(fake: FakeLLM) -> str:
    return fake.seen[-1][-1].content


FULL_TASK = [
    call("get_user", user_id="123"),
    call("update_email", user_id="123", email="ada.new@example.com"),
    call("set_manager", user_id="123", manager_id="456"),
    call("create_ticket", user_id="123", title="Email changed"),
    say("done"),
]


@pytest.fixture
def api():
    return create_app()


@pytest.fixture
async def client(api):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://mock"
    ) as c:
        yield c


@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "heal.db")


@pytest.fixture
def store(db_path):
    s = Store(db_path)
    yield s
    s.close()


@pytest.fixture
async def registry(client, store):
    reg = Registry(client, json.loads(TOOLS_JSON.read_text()), CFG, store=store)
    await reg.load()
    return reg


def build(kind: str, registry, client, fake, store=None, run_id="r1"):
    if kind == "healing":
        return healing_agent.build(registry, fake, store, run_id)
    return baseline_agent.build(client, registry, fake, store, run_id)


def call_rows(db_path: str) -> list[tuple]:
    db = sqlite3.connect(db_path)
    sql = "SELECT agent, run_id, tool, class FROM call_events ORDER BY event_id"
    rows = db.execute(sql).fetchall()
    db.close()
    return rows


async def test_both_agents_expose_identical_tools(registry, client):
    healing, baseline = llm(say("ok")), llm(say("ok"))
    await common.run(build("healing", registry, client, healing), common.TASK)
    await common.run(build("baseline", registry, client, baseline), common.TASK)
    assert healing.bound == baseline.bound
    functions = [t["function"] for t in healing.bound]
    assert [f["name"] for f in functions] == [t["name"] for t in registry.tools()]
    for f, spec in zip(functions, registry.tools(), strict=True):
        # the OpenAI conversion drops `title` noise, so compare what the LLM can act on
        assert f["parameters"]["required"] == spec["parameters"]["required"]
        assert {k: v["type"] for k, v in f["parameters"]["properties"].items()} == {
            k: v["type"] for k, v in spec["parameters"]["properties"].items()
        }


@pytest.mark.parametrize("kind", ["healing", "baseline"])
async def test_full_task_on_clean_api(kind, registry, client, api):
    fake = llm(*FULL_TASK)
    res = await common.run(build(kind, registry, client, fake), common.TASK)
    state = api.state()
    assert state["users"]["123"]["email"] == "ada.new@example.com"
    assert state["users"]["123"]["manager_id"] == "456"
    assert len(state["tickets"]) == 1
    assert (res.tool_calls, res.llm_tokens, res.hit_limit, res.error) == (
        4,
        5 * 15,
        False,
        None,
    )
    assert res.final_text == "done"


async def test_healing_agent_gets_user_back_under_m1(registry, client, api):
    api.set_mutation("M1")
    fake = llm(call("get_user", user_id="123"), say("done"))
    res = await common.run(build("healing", registry, client, fake), common.TASK)
    assert res.tool_calls == 1
    assert json.loads(last_tool_result(fake))["id"] == "123"


async def test_baseline_agent_gets_raw_422_under_m1(registry, client, api):
    api.set_mutation("M1")
    fake = llm(call("get_user", user_id="123"), say("done"))
    res = await common.run(build("baseline", registry, client, fake), common.TASK)
    assert res.tool_calls == 1
    assert last_tool_result(fake).startswith("HTTP 422:")


@pytest.mark.parametrize("kind", ["healing", "baseline"])
async def test_endless_tool_calls_trip_the_iteration_cap(kind, registry, client, api):
    api.set_mutation("M1")
    script = (call("get_user", user_id="123") for _ in itertools.count())
    fake = FakeLLM(messages=script)
    res = await common.run(build(kind, registry, client, fake), common.TASK)
    assert res.hit_limit is True
    assert res.error is None
    assert res.tool_calls == common.MAX_ITERATIONS
    assert res.llm_tokens > 0


async def test_llm_failure_is_reported_not_raised(registry, client):
    res = await common.run(build("healing", registry, client, llm()), common.TASK)
    assert res.error is not None
    assert res.hit_limit is False


async def test_call_events_are_logged(registry, client, api, store, db_path):
    api.set_mutation("M1")
    for kind in ("healing", "baseline"):
        fake = llm(call("get_user", user_id="123"), say("done"))
        await common.run(build(kind, registry, client, fake, store, f"{kind}-1"), "t")
    assert call_rows(db_path) == [
        ("healing", "healing-1", "get_user", "OK"),
        ("baseline", "baseline-1", "get_user", "E2"),
    ]


async def test_healing_agent_logs_class_of_structured_error(
    registry, client, store, db_path
):
    # missing required argument: the registry answers AGENT_ARG_ERROR, which carries no class
    fake = llm(call("get_user"), say("done"))
    await common.run(build("healing", registry, client, fake, store), "t")
    assert call_rows(db_path) == [("healing", "r1", "get_user", "BUSINESS")]


def test_make_llm_uses_openrouter_defaults(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    model = common.make_llm()
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.model_name == "anthropic/claude-haiku-5.5"
    assert model.temperature == 0
