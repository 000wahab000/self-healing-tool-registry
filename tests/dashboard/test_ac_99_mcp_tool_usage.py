"""AC-99: the MCP tab counts tool calls made through the MCP protocol."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from types import SimpleNamespace

import httpx
import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from dashboard.app import create_app
from dashboard.metrics_view import mcp_tool_usage
from healer.mcp_server import create_server
from healer.models import ErrorClass
from healer.store import Store

TOOLS = [{"name": "get_user"}, {"name": "idle_tool"}]


def _call(agent, tool, cls, ms, ts):
    return {"agent": agent, "tool": tool, "class": cls, "latency_ms": ms, "ts_ms": ts}


def test_ac_99_usage_counts_sorting_and_zero_rows():
    calls = [
        _call("mcp", "get_user", "OK", 10, 100),
        _call("mcp", "get_user", "OK", 30, 300),
        _call("mcp", "get_user", "E5", 20, 200),
        _call("mcp", "extra", "OK", 5, 50),
        _call("healing", "get_user", "OK", 1, 999),
    ]
    audit = [SimpleNamespace(tool="get_user"), SimpleNamespace(tool="other")]
    out = mcp_tool_usage(TOOLS, calls, audit)
    assert out["total_calls"] == 4
    assert [r["name"] for r in out["tools"]] == ["get_user", "extra", "idle_tool"]
    first, extra, idle = out["tools"]
    assert (first["calls"], first["ok"], first["errors"], first["heals"]) == (3, 2, 1, 1)
    assert first["p50_ms"] == 20 and first["last_ms"] == 300
    assert extra["calls"] == 1 and extra["heals"] == 0
    assert idle["calls"] == 0 and idle["p50_ms"] is None and idle["last_ms"] is None




class _Registry:
    def __init__(self, result):
        self.result = result

    def tools(self):
        return []

    async def call(self, name, args):
        return self.result


async def _drive(server, name="get_user"):
    """One tools/call over in-memory MCP streams; returns the client's result."""
    async with create_client_server_memory_streams() as (client, srv):
        task = asyncio.create_task(
            server.run(srv[0], srv[1], server.create_initialization_options())
        )
        try:
            async with ClientSession(client[0], client[1]) as session:
                await session.initialize()
                return await session.call_tool(name, {})
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@pytest.mark.parametrize(
    ("result", "cls"),
    [
        ({"id": "1"}, ErrorClass.OK),
        ({"error": "API_ERROR", "class": "E5"}, ErrorClass.E5),
        ({"error": "UNKNOWN_TOOL", "retry": False}, ErrorClass.BUSINESS),
    ],
)
async def test_ac_99_tools_call_writes_one_call_event(result, cls):
    store = Store(":memory:")
    await _drive(create_server(_Registry(result), store=store))
    rows = store.call_events()
    assert len(rows) == 1
    assert (rows[0]["agent"], rows[0]["tool"], rows[0]["class"]) == ("mcp", "get_user", cls.value)
    store.close()


async def test_ac_99_logging_failure_never_breaks_the_call():
    class Broken:
        def log_call(self, *a, **k):
            raise RuntimeError("db gone")

    res = await _drive(create_server(_Registry({"id": "1"}), store=Broken()))
    assert not res.is_error


async def test_ac_99_route_returns_rows(tmp_path):
    app = create_app(str(tmp_path / "dash.db"))
    dash = app.state.dash
    dash.store.log_call("mcp", "r1", "get_user", ErrorClass.OK, 12)
    dash.store.log_call("healing", "r2", "get_user", ErrorClass.OK, 99)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://dash"
    ) as c:
        data = (await c.get("/api/mcp/calls")).json()
    await dash.aclose()
    assert data["total_calls"] == 1
    row = next(r for r in data["tools"] if r["name"] == "get_user")
    assert row["calls"] == 1 and row["p50_ms"] == 12
