from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app

ROOT = Path(__file__).parents[2]
CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}


@pytest.fixture
def api():
    return create_app()


@pytest.fixture
def tools_config() -> dict:
    return json.loads((ROOT / "config" / "tools.json").read_text())


@pytest_asyncio.fixture
async def mcp_registry(api, tools_config, tmp_path):
    store = Store(str(tmp_path / "mcp.db"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://mock"
    ) as client:
        registry = Registry(client, tools_config, CFG, store=store)
        await registry.load()
        try:
            yield registry
        finally:
            store.close()


@pytest.fixture
def mcp_client(mcp_registry):
    from mcp import ClientSession
    from mcp.server.lowlevel import Server
    from mcp.shared.memory import create_client_server_memory_streams

    from healer.mcp_server import create_server

    @asynccontextmanager
    async def connect():
        server: Server = create_server(mcp_registry)
        notifications = []

        async def handle_message(message):
            notifications.append(message)

        async with create_client_server_memory_streams() as (client_streams, server_streams):
            task = asyncio.create_task(
                server.run(
                    server_streams[0],
                    server_streams[1],
                    server.create_initialization_options(),
                )
            )
            try:
                async with ClientSession(
                    client_streams[0], client_streams[1], message_handler=handle_message
                ) as session:
                    await session.initialize()
                    yield session, notifications, server
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return connect
