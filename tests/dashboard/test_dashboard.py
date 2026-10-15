"""Dashboard API tests: the app runs in-process, both mocks and the agents are real."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

import httpx
import pytest

from dashboard import demo
from dashboard.app import create_app
from healer.models import ErrorClass, HealOutcome, Reason
from mock_api.app import MUTATIONS

M5_OPS = [
    {"op": "move", "from": ["body", "user_id"], "to": ["body", "target", "id"]},
    {"op": "cast", "path": ["body", "target", "id"], "to": "int"},
    {
        "op": "header",
        "name": "X-Tenant-Id",
        "src": {"ref": "config", "key": "TENANT_ID"},
    },
]
TOOLS = ["get_user", "update_email", "set_manager", "create_ticket"]
FAST = {"agent": "scripted", "step_delay": 0}
# Agents wait 3 x step_delay before their first call: room to trigger a mutation.
PACED = {"agent": "scripted", "step_delay": 0.1}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ("JEV_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY", "DB_PATH"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
async def client(tmp_path):
    app = create_app(str(tmp_path / "dash.db"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dash") as c:
        yield c
    await app.state.dash.aclose()


async def state(client, after: int = 0) -> dict:
    return (await client.get("/api/state", params={"after": after})).json()


async def finished(client, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        s = await state(client)
        if all(r["status"] not in ("idle", "running") for r in s["runs"].values()):
            return s
        await asyncio.sleep(0.02)
    raise AssertionError("runs did not finish")


async def run_with(client, mutation: str | None) -> dict:
    """Start the paced scripted agents, trigger `mutation` before their first call."""
    assert (await client.post("/api/start", json=PACED)).status_code == 200
    if mutation:
        r = await client.post("/api/mutation", json={"id": mutation})
        assert r.status_code == 200
    return await finished(client)


def calls(s: dict, agent: str) -> list[tuple[str, str]]:
    return [(e["tool"], e["class"]) for e in s["events"] if e["agent"] == agent]


async def test_index_serves_the_page(client):
    r = await client.get("/live")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "/api/state" in r.text


async def test_landing_links_to_the_live_page(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert 'href="/live"' in r.text


def test_mutation_buttons_cover_every_scenario_including_m6_m9_and_c3():
    """Phase 12D: one button per mutation (M6-D, M6-N, M9 and C3 included)."""
    page = (Path(__file__).parents[2] / "dashboard" / "index.html").read_text(
        encoding="utf-8"
    )
    groups = page.split("const GROUPS = [", 1)[1].split("];", 1)[0]
    buttons = set(re.findall(r'\["((?:M|C)\d+(?:-[A-Z])?)"', groups))
    assert buttons == set(MUTATIONS)


async def test_idle_state_before_any_run(client):
    s = await state(client)
    assert {a: r["status"] for a, r in s["runs"].items()} == {
        "healing": "idle",
        "baseline": "idle",
    }
    assert (s["events"], s["heals"], s["active_mutation"]) == ([], [], None)


async def test_clean_scripted_run_streams_events_from_both_agents(client):
    assert (await client.post("/api/start", json=FAST)).status_code == 200
    s = await finished(client)

    for agent in ("healing", "baseline"):
        run = s["runs"][agent]
        assert (run["status"], run["tool_calls"], run["hit_limit"]) == (
            "done",
            4,
            False,
        )
        assert calls(s, agent) == [(tool, "OK") for tool in TOOLS]
    assert s["heals"] == []
    for mock in s["mocks"].values():
        assert mock["data"]["users"]["123"]["email"] == "ada.new@example.com"
        assert [t["title"] for t in mock["data"]["tickets"]] == ["Email changed"]


async def test_events_cursor_returns_only_newer_rows(client):
    await client.post("/api/start", json=FAST)
    s = await finished(client)
    ids = [e["event_id"] for e in s["events"]]
    assert len(ids) == 8 and ids == sorted(ids)

    newer = await state(client, after=ids[4])
    assert [e["event_id"] for e in newer["events"]] == ids[5:]
    assert (await state(client, after=ids[-1]))["events"] == []


async def test_mutation_applies_to_both_mocks_and_can_be_cleared(client):
    r = await client.post("/api/mutation", json={"id": "M5"})
    assert r.status_code == 200
    s = await state(client)
    assert s["active_mutation"] == "M5"
    assert {a: m["mutation"] for a, m in s["mocks"].items()} == {
        "healing": "M5",
        "baseline": "M5",
    }

    await client.post("/api/mutation", json={"id": None})
    s = await state(client)
    assert s["active_mutation"] is None
    assert {m["mutation"] for m in s["mocks"].values()} == {None}


async def test_unknown_mutation_is_rejected_and_changes_nothing(client):
    await client.post("/api/mutation", json={"id": "M3"})
    r = await client.post("/api/mutation", json={"id": "M99"})
    assert r.status_code == 400
    s = await state(client)
    assert s["active_mutation"] == "M3"
    assert {m["mutation"] for m in s["mocks"].values()} == {"M3"}


async def test_llm_start_without_a_key_is_rejected(client):
    r = await client.post("/api/start", json={"agent": "llm"})
    assert r.status_code == 400
    s = await state(client)
    assert {r["status"] for r in s["runs"].values()} == {"idle"}


async def test_m5_heal_shows_its_fix_ops_and_the_baseline_hits_the_cap(client):
    s = await run_with(client, "M5")

    assert (s["runs"]["healing"]["status"], s["runs"]["healing"]["tool_calls"]) == (
        "done",
        4,
    )
    assert calls(s, "healing") == [(tool, "OK") for tool in TOOLS]
    assert s["runs"]["baseline"]["hit_limit"] is True
    assert calls(s, "baseline") == [("get_user", ErrorClass.E2)] * 10

    (heal,) = s["heals"]
    assert (heal["tool"], heal["class"], heal["tier"]) == ("get_user", "E2", 1)
    assert (heal["outcome"], heal["reason"]) == (HealOutcome.RECOVERED, None)
    assert heal["fix"] == {"request_ops": M5_OPS, "response_ops": []}
    assert s["metrics"]["outcomes"]["by_outcome"] == {"RECOVERED": 1}
    assert s["metrics"]["mttr"]["1"]["n"] == 1
    assert heal["mttr_ms"] < 4000


async def test_m8_is_refused_without_inventing_a_value(client):
    s = await run_with(client, "M8")

    (heal,) = s["heals"]
    assert (heal["tool"], heal["outcome"], heal["reason"]) == (
        "create_ticket",
        HealOutcome.ABORTED,
        Reason.NO_SAFE_VALUE,
    )
    assert heal["fix"] is None
    assert s["runs"]["healing"]["hit_limit"] is False
    assert s["mocks"]["healing"]["data"]["tickets"] == []
    assert s["metrics"]["mttr"] == {}


async def test_reset_clears_the_view_and_the_mocks(client):
    await run_with(client, "M5")
    before = (await state(client))["epoch"]

    r = await client.post("/api/reset")
    assert r.status_code == 200
    s = await state(client)
    assert s["epoch"] != before
    assert (s["events"], s["heals"], s["active_mutation"]) == ([], [], None)
    assert {r["status"] for r in s["runs"].values()} == {"idle"}
    for mock in s["mocks"].values():
        assert (mock["mutation"], mock["data"]["tickets"]) == (None, [])
        assert mock["data"]["users"]["123"]["email"] == "ada@example.com"


async def test_mutation_picked_before_start_survives_start(client):
    assert (await client.post("/api/mutation", json={"id": "M5"})).status_code == 200
    assert (await client.post("/api/start", json=PACED)).status_code == 200
    s = await finished(client)
    assert s["active_mutation"] == "M5"
    assert s["runs"]["baseline"]["hit_limit"] is True
    assert {t["error_class"] for t in s["traces"]["baseline"]} == {"E2"}
    assert s["traces"]["healing"][0]["heal_event"] is not None


async def test_start_again_runs_on_clean_mocks(client):
    await run_with(client, "M5")
    assert (await client.post("/api/mutation", json={"id": None})).status_code == 200
    s = await run_with(client, None)
    assert s["active_mutation"] is None
    assert s["runs"]["baseline"]["hit_limit"] is False
    assert len(s["events"]) == 8  # only this run's calls, not the earlier ones


async def test_report_endpoint_returns_text_or_null(client):
    body = (await client.get("/api/report")).json()
    assert set(body) == {"report"}
    assert body["report"] is None or isinstance(body["report"], str)


async def test_demo_runs_the_pitch_flow():
    events = await demo.main(step=0.02)
    assert [(e.tool, e.cls, e.outcome, e.reason) for e in events] == [
        ("get_user", ErrorClass.E2, HealOutcome.RECOVERED, None),
        ("get_user", ErrorClass.E5, HealOutcome.RECOVERED, None),
        ("create_ticket", ErrorClass.E2, HealOutcome.ABORTED, Reason.NO_SAFE_VALUE),
    ]
