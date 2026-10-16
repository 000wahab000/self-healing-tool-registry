from __future__ import annotations

import copy
import json
from pathlib import Path

import httpx
import pytest

from healer.graphql_loader import graphql_source
from healer.registry import Registry
from healer.store import Store
from mock_api.graphql_app import create_app

CFG = {}
TOOLS_PATH = Path(__file__).parents[2] / "config" / "tools.json"


def _protocol_config(tool: str) -> dict:
    source = json.loads(TOOLS_PATH.read_text())
    return {"header_sources": {}, "tools": {tool: source["tools"][tool]}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "tool", "args", "expected", "fix_count"),
    [
        (None, "get_user", {"user_id": "123"}, {"id": "123", "name": "Ada", "email": "ada@example.com"}, 0),
        ("M1", "get_user", {"user_id": "123"}, {"id": "123", "name": "Ada", "email": "ada@example.com"}, 1),
        ("M2", "update_email", {"user_id": "123", "email": "new@example.com"}, {"id": "123", "name": "Ada", "email": "new@example.com"}, 1),
        pytest.param(
            "M3", "get_user", {"user_id": "123"}, {"id": "123", "name": "Ada", "email": "ada@example.com"}, 1,
            # Fails with VERIFY_FAILED on the P1 branch itself; GraphQL is deferred to T2-6, fix there.
            marks=pytest.mark.xfail(strict=True, reason="GraphQL M3 envelope heal: VERIFY_FAILED (T2-6)"),
        ),
    ],
)
async def test_ac_38_registry_graphql_heals_and_keeps_schema_frozen(
    tmp_path, mutation, tool, args, expected, fix_count
):
    api = create_app()
    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as client:
        spec_source = graphql_source(client)
        config = _protocol_config(tool)
        store = Store(str(tmp_path / f"{mutation or 'healthy'}.db"))
        try:
            registry = Registry(client, config, CFG, store=store, spec_source=spec_source)
            await registry.load()
            frozen_schema = copy.deepcopy(registry.tools())
            if mutation:
                api.set_mutation(mutation)
            result = await registry.call(tool, args)
            assert result == expected
            assert api.state()["123"] == {
                key: value for key, value in expected.items() if key != "id"
            }
            assert registry.tools() == frozen_schema
            events = store.audit_events()
            assert len(events) == fix_count
            if fix_count:
                assert events[0].outcome.value == "RECOVERED"
                assert registry.defs[tool].active_fix is not None
                assert registry.defs[tool].active_fix.request_ops or registry.defs[tool].active_fix.response_ops
        finally:
            store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", [None, "M1", "M2"])
async def test_ac_38_registry_grpc_heals_and_keeps_schema_frozen(tmp_path, mutation):
    grpc = pytest.importorskip("grpc")
    pytest.importorskip("grpc_reflection")
    from mock_api.grpc_server import SERVICE, create_server

    original, _ = await create_server()
    active_server = original
    port = original.add_insecure_port("127.0.0.1:0")
    await original.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    store = Store(str(tmp_path / f"grpc-{mutation or 'healthy'}.db"))
    try:
        name = f"{SERVICE}.Lookup"
        config = _protocol_config("get_user")
        config["tools"] = {
            name: {"idempotent": True, "postchecks": [], "write": False}
        }
        client = httpx.AsyncClient()
        registry = Registry(client, config, CFG, store=store, grpc_channel=channel)
        await registry.load()
        frozen_schema = copy.deepcopy(registry.tools())
        if mutation:
            await original.stop(None)
            changed, _ = await create_server(mutation)
            changed.add_insecure_port(f"127.0.0.1:{port}")
            await changed.start()
            active_server = changed
        result = await registry.call(name, {"user_id": "123"})
        assert result == {"user_id": "123", "name": "Ada"}
        assert registry.tools() == frozen_schema
        events = store.audit_events()
        assert len(events) == int(mutation is not None)
        if mutation:
            assert events[0].outcome.value == "RECOVERED"
            assert registry.defs[name].active_fix is not None
            assert registry.defs[name].active_fix.request_ops
    finally:
        await channel.close()
        await active_server.stop(None)
        await client.aclose()
        store.close()
