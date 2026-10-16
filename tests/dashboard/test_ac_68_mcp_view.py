"""AC-68: the dashboard MCP view reports the front door's tools (T2-9, no T1-6)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from dashboard.app import create_app
from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app as create_mock

ROOT = Path(__file__).parents[2]
CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}


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


async def _front_door_tools() -> list[dict]:
    """Build a clean registry the way the MCP server does, and read its tools."""
    tools_config = json.loads(
        (ROOT / "config" / "tools.json").read_text(encoding="utf-8")
    )
    store = Store(":memory:")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=create_mock("test-token")),
            base_url="http://mock",
        ) as http:
            registry = Registry(http, tools_config, CFG, store)
            await registry.load()
            return registry.tools()
    finally:
        store.close()


async def test_ac_68_endpoint_lists_exactly_the_front_door_tools(client):
    info = (await client.get("/api/mcp")).json()
    served = info["front_door"]["tools"]
    expected = await _front_door_tools()

    assert [t["name"] for t in served] == [t["name"] for t in expected]
    assert [t["description"] for t in served] == [t["description"] for t in expected]
    for tool, want in zip(served, expected):
        assert tool["parameters"] == want["parameters"]
        assert tool["parameters"]["type"] == "object"


async def test_ac_68_reports_stdio_and_http_transports(client):
    info = (await client.get("/api/mcp")).json()
    transports = info["front_door"]["transports"]
    assert transports["stdio"] is True
    assert transports["http"]["path"] == "/mcp"
    assert transports["http"]["default_host"] == "127.0.0.1"
    assert transports["http"]["default_port"] == 8001


async def test_ac_68_invents_no_upstreams_while_the_config_is_absent(client):
    info = (await client.get("/api/mcp")).json()
    assert isinstance(info["upstream_config_present"], bool)
    assert isinstance(info["upstream_servers"], list)
    if not info["upstream_config_present"]:
        assert info["upstream_servers"] == []
    else:  # the shipped config lists the two mock drift servers
        assert {"users", "tickets"} <= {s["name"] for s in info["upstream_servers"]}


async def test_ac_68_view_uses_the_clean_spec_not_an_active_mutation(app, client):
    # A live mutation must not leak into the front door's frozen schemas.
    await app.state.dash.mutate("M5")
    tools = (await client.get("/api/mcp")).json()["front_door"]["tools"]
    by_name = {t["name"]: t for t in tools}
    # M5 moves user_id into target.id: the clean get_user schema keeps user_id.
    assert "user_id" in by_name["get_user"]["parameters"]["properties"]


def test_ac_68_page_has_the_mcp_tab_and_panel():
    page = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert 'data-tab="mcp"' in page
    assert 'id="view-mcp"' in page
    assert 'id="mcp-tools"' in page
    assert 'id="mcp-upstreams"' in page
    assert "/api/mcp" in page
    # The offline demo answers /api/mcp too.
    assert "DEMO_MCP" in page
