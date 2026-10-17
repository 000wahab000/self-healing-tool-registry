from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from dashboard import unified
from dashboard.app import create_app


class _Gateway:
    def tools(self) -> list[dict]:
        return []

    async def call(self, name: str, arguments: dict) -> dict:
        return {}


def test_standalone_status_is_unknown_and_uses_dashboard_config_path(tmp_path: Path) -> None:
    config = tmp_path / "custom.json"
    api = {"name": "orders", "kind": "openapi", "base_url": "https://orders.example"}
    config.write_text(json.dumps({"servers": [], "apis": [api]}))
    client = TestClient(
        create_app(":memory:", upstream_config_path=config),
        client=("127.0.0.1", 50000),
    )

    response = client.get("/api/connections")
    assert response.json()["apis"][0]["runtime_status"] == "unknown"
    assert client.put("/api/connections/orders", json={"selected_operations": ["lookup"]}).status_code == 200
    assert json.loads(config.read_text())["apis"][0]["selected_operations"] == ["lookup"]


@pytest.mark.asyncio
async def test_unified_runtime_status_tracks_exact_startup_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "custom.json"
    original = {"name": "orders", "kind": "openapi", "base_url": "https://orders.example"}
    config.write_text(json.dumps({"servers": [], "apis": [original]}))
    args = SimpleNamespace(
        db=str(tmp_path / "dash.db"),
        port=18720,
        host="127.0.0.1",
        base_url="http://127.0.0.1:8000",
        tools="tools.json",
        mcp_servers=str(config),
        spec_path="/openapi.json",
        repair=False,
        token_env=None,
        allowed_host=None,
        allowed_origin=None,
    )

    @asynccontextmanager
    async def registry_context(_: SimpleNamespace) -> AsyncIterator[_Gateway]:
        yield _Gateway()

    monkeypatch.setattr(unified.mcp_server, "registry_context", registry_context)
    app = unified.create_app(args)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:18720"
        ) as client,
    ):
        current = (await client.get("/api/connections")).json()
        assert current["apis"][0]["runtime_status"] == "active"

        updated = await client.put(
            "/api/connections/orders", json={"selected_operations": ["lookup"]}
        )
        assert updated.status_code == 200
        added = await client.post(
            "/api/connections",
            json={"name": "billing", "kind": "openapi", "base_url": "https://billing.example"},
        )
        assert added.status_code == 200
        current = (await client.get("/api/connections")).json()
        assert {a["name"]: a["runtime_status"] for a in current["apis"]} == {
            "orders": "pending",
            "billing": "pending",
        }

    html = (Path(__file__).parents[2] / "dashboard" / "connections.html").read_text(encoding="utf-8")
    assert '"Active"' in html and '"Saved · restart required"' in html
    assert '"Saved · status unknown"' in html
    assert 'a.spec_url || (a.base_url +' in html
