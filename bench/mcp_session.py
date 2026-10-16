"""An in-memory MCP client session over a mock drift server (shared by the MCP bench modules)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from mock_api.mcp_drift_server import McpDriftServer


@asynccontextmanager
async def session(drift: McpDriftServer) -> AsyncIterator[ClientSession]:
    server = drift.server
    async with create_client_server_memory_streams() as (client, srv):
        task = asyncio.create_task(
            server.run(srv[0], srv[1], server.create_initialization_options())
        )
        try:
            async with ClientSession(client[0], client[1]) as sess:
                await sess.initialize()
                yield sess
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
