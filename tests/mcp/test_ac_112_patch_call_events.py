from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from pathlib import Path

import httpx
import pytest

pytest.importorskip("mcp")
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from healer import gateway, mcp_server
from healer.models import HealOutcome
from healer.store import Store

PRISM = Path(__file__).parents[2] / "demo" / "prism"


def _published(major: int) -> dict:
    spec = json.loads((PRISM / f"openapi-v{major}.json").read_text())
    del spec["paths"]["/openapi.json"]["get"]["responses"]["200"]["content"]["application/json"]["example"]
    return spec


@pytest.mark.asyncio
async def test_ac_112_external_mcp_warm_fix_reuse_is_persisted_without_extra_heals(
    tmp_path: Path,
) -> None:
    active = 1
    queries: list[dict[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json=_published(active))
        query = dict(request.url.params)
        queries.append(query)
        expected = "order_id" if active == 1 else "order_reference"
        if expected not in query:
            return httpx.Response(
                422,
                headers={"content-type": "application/problem+json"},
                json={"detail": [{"loc": ["query", expected], "type": "missing"}]},
            )
        return httpx.Response(
            200,
            json={"order_id": "ORD-1001", "status": "shipped", "total": 49.95},
        )

    store = Store(str(tmp_path / "patch-calls.db"))
    api = {
        "name": "orders",
        "kind": "openapi",
        "base_url": "http://orders.example.test",
        "spec_url": "http://orders.example.test/openapi.json",
        "selected_operations": ["get_order"],
        "auth": {"type": "none"},
    }
    try:
        async with gateway.api_registry(
            api, store, {}, {}, transport=httpx.MockTransport(handle)
        ) as registry:
            server = mcp_server.create_server(registry, store=store)
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
                        before = (await session.list_tools()).model_dump(by_alias=True)["tools"]
                        invalid = await session.call_tool("orders__get_order", {"order_id": 12})
                        unknown = await session.call_tool("no_such_tool", {})
                        assert invalid.model_dump(by_alias=True)["isError"]
                        assert unknown.model_dump(by_alias=True)["isError"]
                        first = await session.call_tool("orders__get_order", {"order_id": "ORD-1001"})
                        assert first.structured_content == {
                            "order_id": "ORD-1001", "status": "shipped", "total": 49.95
                        }

                        active = 2
                        calls = [
                            await session.call_tool(
                                "orders__get_order", {"order_id": "ORD-1001"}
                            )
                            for _ in range(3)
                        ]
                        assert all(
                            call.structured_content
                            == {"order_id": "ORD-1001", "status": "shipped", "total": 49.95}
                            for call in calls
                        )
                        after = (await session.list_tools()).model_dump(by_alias=True)["tools"]
                        assert after == before
                finally:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

        events = store.call_events()
        patch_events = [event for event in events if event.get("patches")]
        assert len(events) == 6 and len(patch_events) == 3
        assert all("patches" not in event for event in events[:3])
        assert [event["class"] for event in patch_events] == ["OK"] * 3
        first_patch = patch_events[0]["patches"]
        warm_patches = [event["patches"] for event in patch_events[1:]]
        assert len(first_patch) == len(warm_patches[0]) == len(warm_patches[1]) == 1
        assert first_patch[0]["reused"] is False
        assert all(patches[0]["reused"] is True for patches in warm_patches)
        move = {"op": "move", "from": ["query", "order_id"], "to": ["query", "order_reference"]}
        assert all(patches[0]["request_ops"] == [move] for patches in [first_patch, *warm_patches])
        assert all(patches[0]["response_ops"] == [] for patches in [first_patch, *warm_patches])
        assert sum("order_reference" in query for query in queries) == 3
        assert len(store.audit_events()) == 1
        assert store.audit_events()[0].outcome is HealOutcome.RECOVERED
        assert all("patches" not in event for event in events if event["tool"] != "orders__get_order" or event["class"] != "OK")
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ac_112_response_only_fix_reuse_is_traced(mcp_registry, api) -> None:
    api.set_mutation("M3")
    server = mcp_server.create_server(mcp_registry, store=mcp_registry.store)
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
                first = await session.call_tool("get_user", {"user_id": "123"})
                second = await session.call_tool("get_user", {"user_id": "123"})
                assert first.structured_content["id"] == second.structured_content["id"] == "123"
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    events = mcp_registry.store.call_events()
    assert len(events) == 2
    assert [event["patches"][0]["reused"] for event in events] == [False, True]
    assert all(event["patches"][0]["request_ops"] == [] for event in events)
    assert all(event["patches"][0]["response_ops"] for event in events)
    audits = mcp_registry.store.audit_events()
    assert len(audits) == 1 and audits[0].outcome is HealOutcome.RECOVERED
