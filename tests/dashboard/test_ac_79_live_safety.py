"""AC-79: Live safety and timing panel (session heals)."""

from __future__ import annotations

import httpx
import pytest

from dashboard.app import create_app
from dashboard.metrics_view import live_safety
from healer.models import AuditEvent, ErrorClass, HealOutcome, Reason, Tier


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ("JEV_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY", "DB_PATH"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "dash.db"))


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dash") as c:
        yield c
    await app.state.dash.aclose()


def test_ac_79_live_safety_empty_audit():
    res = live_safety([])
    assert res["by_tier"]["0"]["n"] == 0
    assert res["by_tier"]["0"]["mttr_ms"]["p50"] == 0.0
    assert res["by_tier"]["1"]["n"] == 0
    assert res["by_tier"]["1"]["mttr_ms"]["p50"] == 0.0
    assert res["outcomes"]["RECOVERED"] == 0
    assert res["outcomes"]["REFUSED"] == 0
    assert res["refusals"] == []
    assert res["tokens"] == {"jev": 0, "llm": 0}


def test_ac_79_live_safety_hand_built_audit():
    events = [
        AuditEvent(
            ts_ms=1000,
            tool="get_user",
            fingerprint="fp1",
            cls=ErrorClass.E1,
            raw_code="500",
            tier=Tier.T0,
            path=None,
            fix_id=1,
            outcome=HealOutcome.RECOVERED,
            reason=None,
            mttr_ms=10,
            heal_ms=10,
        ),
        AuditEvent(
            ts_ms=2000,
            tool="get_user",
            fingerprint="fp1",
            cls=ErrorClass.E1,
            raw_code="500",
            tier=Tier.T0,
            path=None,
            fix_id=1,
            outcome=HealOutcome.RECOVERED,
            reason=None,
            mttr_ms=20,
            heal_ms=20,
        ),
        AuditEvent(
            ts_ms=3000,
            tool="update_email",
            fingerprint="fp2",
            cls=ErrorClass.E2,
            raw_code="422",
            tier=Tier.T1,
            path=None,
            fix_id=2,
            outcome=HealOutcome.RECOVERED,
            reason=None,
            mttr_ms=50,
            heal_ms=50,
        ),
        AuditEvent(
            ts_ms=4000,
            tool="create_ticket",
            fingerprint="fp3",
            cls=ErrorClass.E2,
            raw_code="422",
            tier=Tier.T1,
            path=None,
            fix_id=None,
            outcome=HealOutcome.ABORTED,
            reason=Reason.NO_SAFE_VALUE,
            mttr_ms=0,
            heal_ms=0,
        ),
    ]

    res = live_safety(events)
    assert res["by_tier"]["0"]["n"] == 2
    assert res["by_tier"]["0"]["mttr_ms"]["p50"] == 15.0
    assert res["by_tier"]["1"]["n"] == 1
    assert res["by_tier"]["1"]["mttr_ms"]["p50"] == 50.0

    assert res["outcomes"]["RECOVERED"] == 3
    assert res["outcomes"]["REFUSED"] == 1

    assert len(res["refusals"]) == 1
    assert res["refusals"][0]["tool"] == "create_ticket"
    assert res["refusals"][0]["reason"] == "NO_SAFE_VALUE"
    assert res["refusals"][0]["ts_ms"] == 4000


async def test_ac_79_live_safety_route_after_scripted_run(client):
    mut_res = await client.post("/api/mutation", json={"id": "M1"})
    assert mut_res.status_code == 200

    res = await client.get("/api/metrics/live")
    assert res.status_code == 200
    data = res.json()
    assert "by_tier" in data
    assert "0" in data["by_tier"]
    assert "1" in data["by_tier"]
    assert "outcomes" in data
    assert "refusals" in data
    assert "tokens" in data


async def test_ac_79_live_safety_panel_script_served(client):
    res = await client.get("/panels/live_safety.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"].lower()
    assert "HealerPanels.register" in res.text
    assert '"live_safety"' in res.text
