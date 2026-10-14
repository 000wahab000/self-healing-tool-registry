"""Tests for the Explorer endpoints (/api/explorer/info and /api/explore)."""

from __future__ import annotations

import httpx
import pytest

from agents import common
from dashboard import explorer
from dashboard.app import create_app


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ("JEV_API_KEY", "OPENROUTER_API_KEY", "DB_PATH"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
async def client(tmp_path):
    app = create_app(str(tmp_path / "explorer.db"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dash") as c:
        yield c
    await app.state.dash.aclose()


async def test_explorer_info_endpoint(client):
    r = await client.get("/api/explorer/info")
    assert r.status_code == 200
    data = r.json()
    assert "mock_info" in data
    assert "predefined_queries" in data
    assert "error_classes" in data
    assert "mutations" in data
    assert len(data["mock_info"]["tools"]) == 4
    assert len(data["predefined_queries"]) >= 10
    assert len(data["error_classes"]) == 8


async def test_explore_clean_run(client):
    r = await client.post("/api/explore", json={"query": "Test clean", "mutation": None})
    assert r.status_code == 200
    res = r.json()
    assert res["mutation"] is None
    assert res["healing"]["data_correct"] is True
    assert res["baseline"]["data_correct"] is True
    assert res["healing"]["tool_calls"] == 4
    assert res["baseline"]["tool_calls"] == 4
    assert len(res["tool_schemas"]) == 4
    # No drift in clean run
    for s in res["tool_schemas"].values():
        assert s["input_drift"] is False
        assert s["output_drift"] is False


async def test_explore_m1_rename_heals(client):
    r = await client.post("/api/explore", json={"query": "Test M1", "mutation": "M1"})
    assert r.status_code == 200
    res = r.json()
    assert res["tool_schemas"]["get_user"]["input_drift"] is True
    assert res["healing"]["data_correct"] is True
    assert res["baseline"]["data_correct"] is False
    assert res["baseline"]["hit_limit"] is True
    assert len(res["healing"]["heals"]) == 1
    h = res["healing"]["heals"][0]
    assert h["tool"] == "get_user"
    assert h["outcome"] == "RECOVERED"
    assert h["class"] == "E2"


async def test_explore_m7_silent_drift_demonstrates_false_data(client):
    r = await client.post("/api/explore", json={"query": "Test M7", "mutation": "M7"})
    assert r.status_code == 200
    res = r.json()
    assert res["tool_schemas"]["update_email"]["input_drift"] is True
    # Healing agent recovered via postcheck
    assert res["healing"]["data_correct"] is True
    assert len(res["healing"]["heals"]) == 1
    assert res["healing"]["heals"][0]["class"] == "E6"
    assert res["healing"]["heals"][0]["outcome"] == "RECOVERED"
    # Baseline agent receives 200 OK without hitting limit, BUT final data state is FALSE/WRONG
    assert res["baseline"]["hit_limit"] is False
    assert res["baseline"]["data_correct"] is False
    assert res["baseline"]["data_state"]["users"]["123"]["email"] == "ada@example.com"


async def test_explore_llm_surfaces_llm_failure_instead_of_scripted_fallback(
    client, monkeypatch
):
    """The LLM path must never quietly return a canned scripted result."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    def boom():
        raise RuntimeError("provider exploded: free-models-per-day cap reached")

    monkeypatch.setattr(common, "make_llm", boom)
    r = await client.post(
        "/api/explore", json={"query": "Test llm", "mutation": "M4", "agent": "llm"}
    )
    assert r.status_code == 200
    res = r.json()
    assert res["agent"] == "llm"
    assert res["healing"]["status"] == "error"
    assert "free-models-per-day" in res["healing"]["error"]
    assert res["healing"]["traces"] == []


async def test_explore_m8_safe_refusal(client):
    r = await client.post("/api/explore", json={"query": "Test M8", "mutation": "M8"})
    assert r.status_code == 200
    res = r.json()
    assert len(res["healing"]["heals"]) == 1
    assert res["healing"]["heals"][0]["outcome"] == "ABORTED"
    assert res["healing"]["heals"][0]["reason"] == "NO_SAFE_VALUE"
    assert res["healing"]["data_state"]["tickets"] == []


async def test_explore_reports_which_agent_ran(client):
    r = await client.post("/api/explore", json={"query": "Clean", "mutation": None})
    assert r.json()["agent"] == "scripted"
    r = await client.post(
        "/api/explore", json={"query": "Clean", "mutation": None, "agent": "scripted"}
    )
    assert r.status_code == 200
    assert r.json()["healing"]["tool_calls"] == 4


async def test_explore_rejects_unknown_agent(client):
    r = await client.post("/api/explore", json={"query": "x", "mutation": None, "agent": "gpt"})
    assert r.status_code == 422  # rejected by the Literal before it reaches the handler


async def test_explore_llm_without_key_is_a_clear_400(client):
    r = await client.post("/api/explore", json={"query": "x", "mutation": None, "agent": "llm"})
    assert r.status_code == 400
    assert "OPENROUTER_API_KEY" in r.json()["detail"]


async def test_explorer_info_advertises_llm_state(client, monkeypatch):
    r = await client.get("/api/explorer/info")
    data = r.json()
    assert data["llm_available"] is False
    assert data["llm_model"]

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "openai/some-model")
    data = (await client.get("/api/explorer/info")).json()
    assert data["llm_available"] is True
    assert data["llm_model"] == "openai/some-model"


# --- helpers used only by the live-LLM path ---------------------------------


def test_coerce_args_casts_to_frozen_v1_types():
    schemas = {
        "create_ticket": {
            "agent_input": {
                "type": "object",
                "properties": {"user_id": {"type": "string"}, "title": {"type": "string"}},
            }
        }
    }
    args, coerced = explorer._coerce_args(
        "create_ticket", {"user_id": 123, "title": "Email changed"}, schemas
    )
    assert args == {"user_id": "123", "title": "Email changed"}
    assert coerced == [{"field": "user_id", "from": 123, "to": "123"}]


def test_coerce_args_leaves_halting_values_alone():
    schemas = {"t": {"agent_input": {"properties": {"user_id": {"type": "string"}}}}}
    args, coerced = explorer._coerce_args("t", {"user_id": "abc"}, schemas)
    assert args == {"user_id": "abc"}
    assert coerced == []
    assert explorer._coerce_args("unknown", {"a": 1}, schemas) == ({"a": 1}, [])


def test_short_error_truncates_provider_noise():
    assert explorer._short_error(None) is None
    long = "x " * 500
    out = explorer._short_error(long)
    assert len(out) < len(long) and out.endswith("…")
    assert explorer._short_error("Rate limit exceeded") == "Rate limit exceeded"


def test_parse_tool_result_handles_both_agents():
    assert explorer._parse_tool_result('{"id": "123"}') == {"id": "123"}
    assert explorer._parse_tool_result('HTTP 422: {"detail": "bad"}') == {
        "status_code": 422,
        "body": {"detail": "bad"},
    }
    assert explorer._parse_tool_result("plain text") == "plain text"


def test_correctness_is_scoped_to_the_tools_actually_called():
    data = {
        "users": {"123": {"email": "ada@example.com", "manager_id": None}},
        "tickets": [],
    }
    # create_ticket refused nothing and nothing was written -> a ticket run failed.
    ok, details = explorer.check_data_correctness(data, None, {"create_ticket"})
    assert ok is False and details["tickets"]["checked"] is True
    assert details["email"]["checked"] is False
    # M8 refuses the ticket, so an empty ticket list is the correct outcome.
    ok, _ = explorer.check_data_correctness(data, "M8", {"create_ticket"})
    assert ok is True
    # No touched set keeps the original four-step semantics.
    assert explorer.check_data_correctness(data, None)[0] is False
