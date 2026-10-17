from __future__ import annotations

import httpx

from dashboard.app import create_app
from dashboard.metrics_view import call_latency
from healer.models import ErrorClass


def _call(agent, tool, ms, cls="OK"):
    return {"agent": agent, "tool": tool, "latency_ms": ms, "class": cls}


def test_ac_113_groups_by_agent_and_tool_with_percentiles():
    calls = [_call("healing", "get_user", ms) for ms in (10, 20, 30, 40)] + [
        _call("baseline", "get_user", 5, "E2"), _call("baseline", "get_user", 7)]
    out = call_latency(calls)
    rows = {(r["agent"], r["tool"]): r for r in out["rows"]}
    assert rows[("healing", "get_user")] == {"agent": "healing", "tool": "get_user", "n": 4,
                                             "errors": 0, "p50_ms": 25, "p95_ms": 40}
    assert rows[("baseline", "get_user")]["errors"] == 1
    assert out["total"] == 6


def test_ac_113_empty_log():
    assert call_latency([]) == {"rows": [], "total": 0, "p50_ms": 0.0, "p95_ms": 0.0}


async def test_ac_113_route_reads_the_call_log_since_reset(tmp_path):
    app = create_app(str(tmp_path / "dash.db"))
    dash = app.state.dash
    dash.store.log_call("healing", "r1", "get_user", ErrorClass.OK, 12)
    dash.store.log_call("mcp", "r2", "update_email", ErrorClass.E2, 30)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://dash") as c:
        data = (await c.get("/api/metrics/latency")).json()
    await dash.aclose()
    assert data["total"] == 2
    assert {(r["agent"], r["tool"], r["errors"]) for r in data["rows"]} == {
        ("healing", "get_user", 0), ("mcp", "update_email", 1)}
