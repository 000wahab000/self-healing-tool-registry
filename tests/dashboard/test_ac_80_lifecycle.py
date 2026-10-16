"""AC-80: Fix lifecycle panel (candidates, promoted rules, replays)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import httpx
import pytest

from dashboard.app import create_app
from dashboard.metrics_view import fix_lifecycle
from healer.store import Store


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


async def wait_until_finished(client: httpx.AsyncClient, timeout: float = 5.0) -> dict:
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        res = await client.get("/api/state")
        s = res.json()
        runs = s.get("runs", {})
        if all(r.get("status") not in ("idle", "running") for r in runs.values()):
            return s
        await asyncio.sleep(0.02)
    raise TimeoutError("Dashboard runs did not complete within timeout")


async def test_ac_80_empty_store_returns_200_and_empty_lists(client):
    res = await client.get("/api/metrics/lifecycle")
    assert res.status_code == 200
    data = res.json()
    assert data["rules"] == []
    assert data["fixes"] == []
    assert data["snapshots"]["count"] == 0
    assert data["snapshots"]["latest_ms"] is None
    assert "snapshots" in data["unavailable"]


async def test_ac_80_after_scripted_m1_run_twice(client):
    # First run triggers M1 mutation -> tier 1 heal
    await client.post("/api/start", json={"agent": "scripted", "step_delay": 0})
    await client.post("/api/mutation", json={"id": "M1"})
    await wait_until_finished(client)

    # Second run against same active mutation -> tier 0 replay
    await client.post("/api/start", json={"agent": "scripted", "step_delay": 0})
    await wait_until_finished(client)

    res = await client.get("/api/metrics/lifecycle")
    assert res.status_code == 200
    data = res.json()

    assert len(data["fixes"]) >= 1
    m1_fix = next(f for f in data["fixes"] if f["tool"] == "get_user")
    assert m1_fix["first_heal_tier"] == 1
    assert m1_fix["tier1_heals"] >= 1
    assert m1_fix["tier0_replays"] >= 1
    assert len(m1_fix["ops"]) >= 1
    # Check that ops reflect the user_id -> customer_id move
    assert any(
        op.get("op") == "move" and "customer_id" in str(op.get("to"))
        for op in m1_fix["ops"]
    )


def test_ac_80_fix_lifecycle_performs_no_writes(tmp_path):
    real_store = Store(str(tmp_path / "test.db"))
    spy = MagicMock(wraps=real_store)

    data = fix_lifecycle(spy)
    assert isinstance(data, dict)

    write_methods = [
        "save_fix",
        "save_fix_and_audit",
        "record_result",
        "audit",
        "add_negative",
        "save_spec",
        "log_call",
        "promote",
        "record_rule_win",
    ]
    for method_name in write_methods:
        method = getattr(spy, method_name, None)
        if method:
            assert not method.called, f"Write method {method_name} was called during fix_lifecycle"

    real_store.close()


async def test_ac_80_lifecycle_panel_script_served(client):
    res = await client.get("/panels/lifecycle.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"].lower()
    assert "HealerPanels.register" in res.text
    assert '"lifecycle"' in res.text
