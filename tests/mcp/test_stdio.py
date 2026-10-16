from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

pytest.importorskip("mcp")
from mcp import types

ROOT = Path(__file__).parents[2]
USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}


async def test_ac_34_cli_uses_real_custom_spec_and_closes_resources(monkeypatch, tmp_path):
    from healer import mcp_server
    from healer.store import Store
    from mock_api.app import create_app

    api = create_app()
    set_mutation = api.set_mutation

    def set_mutation_with_custom_spec(mid, custom=None):
        set_mutation(mid, custom)
        api.inner.add_api_route(
            "/custom/openapi.json", api.inner.openapi, methods=["GET"]
        )

    api.set_mutation = set_mutation_with_custom_spec
    api.set_mutation(None)
    paths = []
    inner = httpx.ASGITransport(app=api)

    class CustomSpecOnly(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if request.url.path == "/openapi.json":
                raise AssertionError("default OpenAPI endpoint must not be used")
            if request.url.path == "/custom/openapi.json":
                paths.append(request.url.path)
            return await inner.handle_async_request(request)

    clients = []
    real_async_client = httpx.AsyncClient

    def tracked_client(**kwargs):
        client = real_async_client(
            transport=CustomSpecOnly(), base_url=kwargs["base_url"], timeout=kwargs["timeout"]
        )
        client.was_closed = False
        original_close = client.aclose

        async def close():
            client.was_closed = True
            await original_close()

        client.aclose = close
        clients.append(client)
        return client

    stores = []
    real_store = Store

    class TrackedStore(real_store):
        def __init__(self, db):
            super().__init__(db)
            self.was_closed = False
            stores.append(self)

        def close(self):
            self.was_closed = True
            super().close()

    monkeypatch.setattr(mcp_server.httpx, "AsyncClient", tracked_client)
    monkeypatch.setattr(mcp_server, "Store", TrackedStore)

    calls = []
    registry_holder = {}

    class FakeServer:
        def create_initialization_options(self):
            return None

        async def run(self, *_args):
            api.set_mutation("M1")
            calls.append(
                await registry_holder["registry"].call(
                    "get_user", {"user_id": "123"}
                )
            )

    def create_test_server(reg):
        registry_holder["registry"] = reg
        return FakeServer()

    monkeypatch.setattr(mcp_server, "create_server", create_test_server)

    @asynccontextmanager
    async def stdio_server():
        yield object(), object()

    monkeypatch.setattr(mcp_server.stdio, "stdio_server", stdio_server)
    await mcp_server._serve(
        argparse.Namespace(
            base_url="http://mock",
            spec_path="/custom/openapi.json",
            tools=str(ROOT / "config" / "tools.json"),
            db=str(tmp_path / "mcp.db"),
        )
    )

    assert calls == [USER]
    assert paths == ["/custom/openapi.json", "/custom/openapi.json"]
    assert clients[0].was_closed is True
    assert stores[0].was_closed is True
    assert api.state()["users"]["123"]["name"] == "Ada"


def _schema_listing(result) -> list[dict]:
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "inputSchema": tool["inputSchema"],
        }
        for tool in result.model_dump(by_alias=True, exclude_none=True)["tools"]
    ]


async def test_ac_30_list_maps_frozen_registry_tools_and_disables_list_changed(
    mcp_registry, mcp_client
):
    async with mcp_client() as (session, _, server):
        result = await session.list_tools()

        expected = [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["parameters"],
            }
            for tool in mcp_registry.tools()
        ]
        assert _schema_listing(result) == expected
        serialized = result.model_dump(by_alias=True, exclude_none=True)
        assert all("inputSchema" in tool for tool in serialized["tools"])
        list_changed = server.get_capabilities().tools.list_changed
        assert list_changed is not True


async def test_ac_31_get_user_returns_healthy_data(mcp_client):
    async with mcp_client() as (session, _, _):
        result = await session.call_tool("get_user", {"user_id": "123"})

        response = result.model_dump(by_alias=True)
        assert response["isError"] is False
        assert response["structuredContent"] == USER


async def test_ac_32_heal_keeps_client_schema_stable_without_notification(
    api, mcp_registry, mcp_client
):
    async with mcp_client() as (session, notifications, _):
        before = await session.list_tools()
        frozen = _schema_listing(before)
        api.set_mutation("M1")

        result = await session.call_tool("get_user", {"user_id": "123"})

        response = result.model_dump(by_alias=True)
        assert response["isError"] is False
        assert response["structuredContent"] == USER
        after = await session.list_tools()
        assert _schema_listing(after) == frozen
        assert not any(isinstance(msg, types.ToolListChangedNotification) for msg in notifications)
        (event,) = mcp_registry.store.audit_events()
        assert len(mcp_registry.store.audit_events()) == 1
        assert event.outcome.value == "RECOVERED"


async def test_ac_33_m8_refusal_is_structured_and_does_not_invent_or_write(
    api, mcp_registry, mcp_client
):
    async with mcp_client() as (session, _, _):
        api.set_mutation("M8")

        result = await session.call_tool(
            "create_ticket", {"user_id": "123", "title": "t"}
        )

        response = result.model_dump(by_alias=True)
        assert response["isError"] is True
        refusal = response["structuredContent"]
        assert refusal["error"] == "SCHEMA_DRIFT_UNRECOVERABLE"
        assert refusal["reason"] == "NO_SAFE_VALUE"
        assert refusal["retry"] is False
        assert "priority" not in json.dumps(refusal)
        assert mcp_registry.store.audit_events()[0].reason.value == "NO_SAFE_VALUE"
        assert mcp_registry.store.audit_events()[0].outcome.value == "ABORTED"
        assert api.state()["tickets"] == []
        writes = [r for r in api.requests if r["path"] == "/tickets"]
        assert len(writes) == 1


async def test_ac_34_unknown_tool_and_invalid_arguments(mcp_client):
    async with mcp_client() as (session, _, _):
        unknown = await session.call_tool("not_a_tool", {})
        invalid = await session.call_tool("get_user", {"extra": True})

        unknown_response = unknown.model_dump(by_alias=True)
        invalid_response = invalid.model_dump(by_alias=True)
        assert unknown_response["isError"] is True
        assert unknown_response["structuredContent"]["error"] == "UNKNOWN_TOOL"
        assert invalid_response["isError"] is True
        assert invalid_response["structuredContent"]["error"] == "AGENT_ARG_ERROR"


@pytest.mark.parametrize("handler", ["list", "call"])
async def test_callback_exception_is_sanitized_and_keeps_secret_out_of_logs(
    handler, mcp_registry, monkeypatch, caplog, capsys
):
    from mcp import ClientSession, MCPError
    from mcp.shared.memory import create_client_server_memory_streams

    from healer.mcp_server import create_server

    sentinel = "SYNTHETIC_SECRET_SENTINEL"

    def fail_list():
        raise RuntimeError(sentinel)

    async def fail_call(_name, _arguments):
        raise RuntimeError(sentinel)

    monkeypatch.setattr(
        mcp_registry,
        "tools" if handler == "list" else "call",
        fail_list if handler == "list" else fail_call,
    )

    server = create_server(mcp_registry)
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        task = asyncio.create_task(
            server.run(
                *server_streams, server.create_initialization_options()
            )
        )
        try:
            async with ClientSession(*client_streams) as session:
                await session.initialize()
                if handler == "list":
                    with pytest.raises(MCPError) as error:
                        await session.list_tools()
                else:
                    result = await session.call_tool("get_user", {"user_id": "123"})
                    wire_result = result.model_dump(by_alias=True)
                    assert wire_result["isError"] is True
                    assert wire_result["structuredContent"] == {
                        "error": "MCP_TOOL_ERROR",
                        "retry": False,
                    }
                    assert sentinel not in json.dumps(wire_result)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    if handler == "list":
        assert error.value.code == -32603
        assert error.value.message == "MCP_LIST_ERROR"
        assert sentinel not in str(error.value)
    assert sentinel not in caplog.text
    captured = capsys.readouterr()
    assert sentinel not in captured.out + captured.err


async def test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(
    monkeypatch, tmp_path
):
    from healer import mcp_server
    from healer.store import Store

    class DownSpec(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(503, request=request)

    clients = []
    real_async_client = httpx.AsyncClient

    def tracked_client(**kwargs):
        client = real_async_client(transport=DownSpec(), **kwargs)
        client.was_closed = False
        original_close = client.aclose

        async def close():
            client.was_closed = True
            await original_close()

        client.aclose = close
        clients.append(client)
        return client

    stores = []
    real_store = Store

    class TrackedStore(real_store):
        def __init__(self, db):
            super().__init__(db)
            self.was_closed = False
            stores.append(self)

        def close(self):
            self.was_closed = True
            super().close()

    monkeypatch.setattr(mcp_server.httpx, "AsyncClient", tracked_client)
    monkeypatch.setattr(mcp_server, "Store", TrackedStore)
    with pytest.raises(httpx.HTTPStatusError):
        await mcp_server._serve(
            argparse.Namespace(
                base_url="http://mock",
                spec_path="/custom/openapi.json",
                tools=str(ROOT / "config" / "tools.json"),
                db=str(tmp_path / "startup-failure.db"),
            )
        )

    assert clients[0].was_closed is True
    assert stores[0].was_closed is True


def test_ac_34_module_help_writes_only_to_stdout():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    result = subprocess.run(
        [sys.executable, "-m", "healer.mcp_server", "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--base-url" in result.stdout
    assert "--spec-path" in result.stdout
    assert "--tools" in result.stdout
    assert "--db" in result.stdout
    assert result.stderr == ""


async def test_ac_34_stdio_subprocess_sdk_smoke():
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "tests" / "mcp" / "stdio_harness.py")],
        env=env,
        cwd=ROOT,
    )
    with tempfile.TemporaryFile(mode="w+t") as error_log:
        async with (
            asyncio.timeout(20),
            stdio_client(server, errlog=error_log) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert "get_user" in {tool.name for tool in tools.tools}
            result = await session.call_tool("get_user", {"user_id": "123"})
            response = result.model_dump(by_alias=True)
            assert response["isError"] is False
            assert response["structuredContent"] == USER
        error_log.seek(0)
        assert error_log.read() == ""
