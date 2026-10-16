from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager, suppress

import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from healer.gateway import Gateway, upstream_registry
from healer.store import Store
from mock_api.mcp_drift_server import create_drift_server


@asynccontextmanager
async def _session(drift):
    server = drift.server
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        task = asyncio.create_task(
            server.run(server_streams[0], server_streams[1], server.create_initialization_options())
        )
        try:
            async with ClientSession(client_streams[0], client_streams[1]) as session:
                await session.initialize()
                yield session
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


@pytest.fixture
def gateway_factory(tmp_path):
    """A Gateway over in-memory upstream drift servers: {"users": drift, "tickets": drift}."""

    @asynccontextmanager
    async def build(*profiles: str):
        store = Store(str(tmp_path / "gw.db"))
        drifts = {p: create_drift_server(profile=p) for p in profiles}
        try:
            async with AsyncExitStack() as stack:
                regs = []
                for p in profiles:
                    session = await stack.enter_async_context(_session(drifts[p]))
                    regs.append(await upstream_registry(p, session, store, {}))
                yield Gateway(regs), drifts, store
        finally:
            store.close()

    return build
