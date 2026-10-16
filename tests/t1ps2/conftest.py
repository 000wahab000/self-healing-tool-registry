from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Any

import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from mock_api.mcp_drift_server import McpDriftServer, create_drift_server


@pytest.fixture
def drift_users_server() -> McpDriftServer:
    return create_drift_server(profile="users")


@pytest.fixture
def drift_tickets_server() -> McpDriftServer:
    return create_drift_server(profile="tickets")


@pytest.fixture
def mcp_session_factory():
    @asynccontextmanager
    async def connect(drift_or_server: Any):
        server = (
            drift_or_server.server
            if hasattr(drift_or_server, "server")
            else drift_or_server
        )
        async with create_client_server_memory_streams() as (client_streams, server_streams):
            task = asyncio.create_task(
                server.run(
                    server_streams[0],
                    server_streams[1],
                    server.create_initialization_options(),
                )
            )
            try:
                async with ClientSession(client_streams[0], client_streams[1]) as session:
                    await session.initialize()
                    yield session
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    return connect
