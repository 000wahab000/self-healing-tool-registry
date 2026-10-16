from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import dashboard.app as dashboard_app
from dashboard import unified


class Gateway:
    def tools(self) -> list[dict]:
        return [
            {
                "name": "users__get_user",
                "description": "Get a user",
                "parameters": {
                    "type": "object",
                    "properties": {"user_id": {"type": "string"}},
                    "required": ["user_id"],
                },
            }
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, str]:
        return {"name": name, "user_id": arguments["user_id"]}


def arguments(tmp_path: Path, **kwargs: Any) -> SimpleNamespace:
    values = {
        "db": str(tmp_path / "shared.db"),
        "port": 18700,
        "host": "127.0.0.1",
        "base_url": "http://127.0.0.1:8000",
        "tools": "tools.json",
        "mcp_servers": "servers.json",
        "spec_path": "/openapi.json",
        "repair": False,
        "token_env": None,
        "allowed_host": None,
        "allowed_origin": None,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_ac_82_unified_deployment_environment_and_cli_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DB_PATH", "/var/lib/healer/registry.db")
    monkeypatch.setenv("PORT", "")
    monkeypatch.setenv("MCP_TOKEN_ENV", "DEPLOY_TOKEN")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "gateway.example, localhost")
    monkeypatch.setenv("MCP_ALLOWED_ORIGINS", "https://gateway.example")
    args = unified._arguments([])
    assert args.db == "/var/lib/healer/registry.db"
    assert args.port == 8080
    assert args.token_env == "DEPLOY_TOKEN"
    assert args.allowed_host == ["gateway.example", "localhost"]
    assert args.allowed_origin == ["https://gateway.example"]
    overridden = unified._arguments(
        ["--db", "cli.db", "--port", "18701", "--token-env", "CLI_TOKEN", "--allowed-host", "cli.example", "--allowed-origin", "https://cli.example"]
    )
    assert overridden.db == "cli.db"
    assert overridden.port == 18701
    assert overridden.token_env == "CLI_TOKEN"
    assert overridden.allowed_host == ["cli.example"]
    assert overridden.allowed_origin == ["https://cli.example"]


@pytest.mark.asyncio
async def test_ac_82_dashboard_and_mcp_share_port_and_gateway_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entered: list[str] = []

    @asynccontextmanager
    async def registry_context(args: SimpleNamespace) -> AsyncIterator[Gateway]:
        entered.append(args.base_url)
        yield Gateway()

    monkeypatch.setattr(unified.mcp_server, "registry_context", registry_context)
    dashboard_apps = []
    dashboard_factory = unified.create_dashboard_app

    def create_dashboard(*args: Any, **kwargs: Any) -> Any:
        app = dashboard_factory(*args, **kwargs)
        dashboard_apps.append(app)
        return app

    monkeypatch.setattr(unified, "create_dashboard_app", create_dashboard)
    app = unified.create_app(arguments(tmp_path))
    assert app is dashboard_apps[0]
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:18700"
        ) as client,
    ):
        assert (await client.get("/")).status_code == 200
        assert (await client.get("/live")).status_code == 200
        assert (await client.get("/api/state")).status_code == 200
        assert (await client.get("/connections")).status_code == 200
        metadata = (await client.get("/api/mcp")).json()
        front_door = metadata["front_door"]
        assert front_door["transports"]["http"]["default_port"] == 18700
        assert front_door["tools"][0]["name"] == "users__get_user"
        assert front_door["tools"][0]["parameters"]["required"] == ["user_id"]
        assert (await client.get("/users")).status_code == 404

        initialized = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
            headers={"accept": "application/json, text/event-stream"},
        )
        assert initialized.status_code == 200
        assert initialized.json()["result"]["protocolVersion"] == "2024-11-05"
        headers = {
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": "2024-11-05",
            "mcp-session-id": initialized.headers["mcp-session-id"],
        }
        listed = await client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            headers=headers,
        )
        assert listed.status_code == 200
        assert listed.json()["result"]["tools"][0]["name"] == "users__get_user"
        called = await client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "users__get_user",
                    "arguments": {"user_id": "u-1"},
                },
            },
            headers=headers,
        )
        assert called.status_code == 200
        assert called.json()["result"]["structuredContent"] == {
            "name": "users__get_user",
            "user_id": "u-1",
        }
    assert entered == ["http://127.0.0.1:8000"]


@pytest.mark.asyncio
async def test_ac_82_remote_mcp_requires_bearer_and_allowed_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def registry_context(args: SimpleNamespace) -> AsyncIterator[Gateway]:
        yield Gateway()

    monkeypatch.setattr(unified.mcp_server, "registry_context", registry_context)
    monkeypatch.setenv("MCP_TOKEN", "test-secret")
    args = arguments(
        tmp_path,
        host="0.0.0.0",
        token_env="MCP_TOKEN",
        allowed_host=["example.test"],
    )
    app = unified.create_app(args)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://example.test"
        ) as client,
    ):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        }
        assert (await client.post("/mcp", json=body)).status_code == 401
        headers = {
            "authorization": "Bearer test-secret",
            "accept": "application/json, text/event-stream",
        }
        assert (
            await client.post("/mcp", json=body, headers=headers)
        ).status_code == 200
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://evil.test"
        ) as hostile:
            assert (
                await hostile.post("/mcp", json=body, headers=headers)
            ).status_code != 200
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://example.test"
        ) as foreign_origin:
            assert (
                await foreign_origin.post(
                    "/mcp", json=body, headers={**headers, "origin": "https://evil.test"}
                )
            ).status_code != 200


@pytest.mark.asyncio
async def test_ac_82_remote_mcp_rejects_missing_token_and_wildcard_origin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    @asynccontextmanager
    async def registry_context(args: SimpleNamespace) -> AsyncIterator[Gateway]:
        yield Gateway()

    monkeypatch.setattr(unified.mcp_server, "registry_context", registry_context)
    missing_token = unified.create_app(
        arguments(tmp_path, host="0.0.0.0", allowed_host=["example.test"])
    )
    with pytest.raises(ValueError, match="remote HTTP binding"):
        async with missing_token.router.lifespan_context(missing_token):
            pytest.fail("remote binding must require a token")

    monkeypatch.setenv("MCP_TOKEN", "test-secret")
    wildcard_origin = unified.create_app(
        arguments(
            tmp_path,
            host="0.0.0.0",
            token_env="MCP_TOKEN",
            allowed_host=["example.test"],
            allowed_origin=["https://*"],
        )
    )
    with pytest.raises(ValueError, match="wildcard origins"):
        async with wildcard_origin.router.lifespan_context(wildcard_origin):
            pytest.fail("wildcard origins must be rejected")


@pytest.mark.asyncio
async def test_ac_82_dashboard_lifespan_closes_when_gateway_startup_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    closed: list[bool] = []
    registry_closed: list[bool] = []

    async def aclose(self: dashboard_app.Dashboard) -> None:
        closed.append(True)

    @asynccontextmanager
    async def registry_context(args: SimpleNamespace) -> AsyncIterator[Gateway]:
        try:
            yield Gateway()
        finally:
            registry_closed.append(True)

    monkeypatch.setattr(dashboard_app.Dashboard, "aclose", aclose)
    monkeypatch.setattr(unified.mcp_server, "registry_context", registry_context)
    app = unified.create_app(arguments(tmp_path, host="0.0.0.0"))
    with pytest.raises(ValueError, match="remote HTTP binding"):
        async with app.router.lifespan_context(app):
            pytest.fail("unreachable")
    assert closed == [True]
    assert registry_closed == [True]


@pytest.mark.asyncio
async def test_ac_82_dashboard_lifespan_closes_after_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    closed: list[bool] = []

    async def aclose(self: dashboard_app.Dashboard) -> None:
        closed.append(True)

    @asynccontextmanager
    async def registry_context(args: SimpleNamespace) -> AsyncIterator[Gateway]:
        yield Gateway()

    monkeypatch.setattr(dashboard_app.Dashboard, "aclose", aclose)
    monkeypatch.setattr(unified.mcp_server, "registry_context", registry_context)
    app = unified.create_app(arguments(tmp_path))
    async with app.router.lifespan_context(app):
        assert app.state.dash.gateway is not None
    assert closed == [True]
