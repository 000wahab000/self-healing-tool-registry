from __future__ import annotations

import httpx
import pytest

from dashboard.app import create_app
from healer.models import ErrorClass


@pytest.mark.asyncio
async def test_ac_112_state_exposes_patched_mcp_calls_after_reset_baseline(tmp_path) -> None:
    app = create_app(str(tmp_path / "patch-dashboard.db"))
    dash = app.state.dash
    move = {"op": "move", "from": ["query", "order_id"], "to": ["query", "order_reference"]}
    patches = [{"fix_id": 4, "reused": True, "request_ops": [move], "response_ops": []}]
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://dashboard"
        ) as client:
            dash.store.log_call("mcp", "run", "orders__get_order", ErrorClass.OK, 12, patches=patches)
            dash.store.log_call("mcp", "run", "orders__get_order", ErrorClass.OK, 8)
            state = (await client.get("/api/state")).json()
            patch_call = state["patch_calls"][0]
            assert patch_call == {
                "event_id": 1,
                "ts_ms": patch_call["ts_ms"],
                "agent": "mcp",
                "tool": "orders__get_order",
                "class": "OK",
                "latency_ms": 12,
                "patches": patches,
            }
            assert state["metrics"]["outcomes"] == {"by_outcome": {}, "by_reason": {}}

            last_event_id = state["events"][-1]["event_id"]
            poll = (await client.get(f"/api/state?after={last_event_id}")).json()
            assert poll["events"] == []
            assert [event["event_id"] for event in poll["patch_calls"]] == [1]

            dash.store.log_call("mcp", "run", "orders__get_order", ErrorClass.OK, 10, patches=patches)
            poll = (await client.get(f"/api/state?after={last_event_id}")).json()
            assert [event["event_id"] for event in poll["events"]] == [3]
            assert [event["event_id"] for event in poll["patch_calls"]] == [1, 3]

            assert (await client.post("/api/reset")).status_code == 200
            assert (await client.get("/api/state")).json()["patch_calls"] == []

            dash.store.log_call("mcp", "run-2", "orders__get_order", ErrorClass.OK, 10, patches=patches)
            later = (await client.get("/api/state")).json()["patch_calls"]
            assert len(later) == 1 and later[0]["event_id"] == 4
    finally:
        await dash.aclose()
