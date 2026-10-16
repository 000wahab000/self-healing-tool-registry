from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from healer.gateway import upstream_registry
from healer.repair import RepairAgent
from healer.store import Store
from mock_api.mcp_drift_server import create_drift_server


@pytest.fixture
def repair_registry(tmp_path):
    """One upstream "users" registry; get_user is configured read-only so a pick needs no dry run."""

    @asynccontextmanager
    async def build(llm, jev=None):
        drift = create_drift_server(profile="users")
        server = drift.server
        store = Store(str(tmp_path / "repair.db"))
        async with create_client_server_memory_streams() as (cs, ss):
            task = asyncio.create_task(
                server.run(ss[0], ss[1], server.create_initialization_options())
            )
            try:
                async with ClientSession(cs[0], cs[1]) as session:
                    await session.initialize()
                    registry = await upstream_registry(
                        "users",
                        session,
                        store,
                        {},
                        jev,
                        overrides={
                            "users__get_user": {"write": False, "idempotent": True}
                        },
                        repair=RepairAgent(llm) if llm else None,
                    )
                    yield registry, drift, store
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
                store.close()

    return build
