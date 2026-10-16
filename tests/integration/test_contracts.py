"""Step 0 contracts between the two tracks (AGENTS.md): OperationSpec, SpecSource, FixStore."""

from __future__ import annotations

import typing

from healer.models import FixStatus, LoadedSpec, OperationSpec, ParamSpec
from healer.openapi_loader import openapi_source
from healer.store import FixStore, Store

USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}


def _keys(td: type) -> set[str]:
    return set(typing.get_type_hints(td))


async def test_openapi_operations_match_operation_spec(client):
    spec = await openapi_source(client)()

    assert spec.ops and spec.spec_hash
    for op in spec.ops.values():
        assert set(op) == _keys(OperationSpec)
        for param in op["params"]:
            assert set(param) == _keys(ParamSpec)


def test_sqlite_store_implements_fix_store(store):
    assert isinstance(store, FixStore)
    missing = {
        name
        for name in dir(FixStore)
        if not name.startswith("_") and not callable(getattr(Store, name, None))
    }
    assert not missing


async def test_injected_spec_source_serves_load_and_heal(api, client, make_registry):
    seen: list[str] = []
    default = openapi_source(client)

    async def source() -> LoadedSpec:
        spec = await default()
        seen.append(spec.spec_hash)
        return spec

    reg = await make_registry(spec_source=source)
    assert len(seen) == 1  # load

    api.set_mutation("M1")
    assert await reg.call("get_user", {"user_id": "123"}) == USER
    assert len(seen) == 2 and seen[0] != seen[1]  # the heal diagnosed the mutated spec


async def test_contract_4_registry_exposes_tools_accessor(make_registry):
    """Contract 4: Registry exposes tools() and passes tools accessor to Healer."""
    reg = await make_registry()
    assert reg.healer._tools is not None
    tools = list(reg.healer._tools())
    assert len(tools) == len(reg.tools())
    assert {t.name for t in tools} == {t["name"] for t in reg.tools()}


async def test_contract_5_spec_change_precompute(api, client, make_registry, store):
    """Contract 5: P4's watcher calls Healer.precompute(old: LoadedSpec, new: LoadedSpec).
    Must store fixes with status candidate and send 0 live requests."""
    old_spec = await openapi_source(client)()
    reg = await make_registry()

    api.set_mutation("M1")
    new_spec = await openapi_source(client)()

    calls_before = api.get_user_calls
    count = await reg.healer.precompute(old_spec, new_spec)
    assert count >= 1
    assert api.get_user_calls == calls_before  # 0 live requests

    cand = store._candidates
    assert any(f.status is FixStatus.candidate and f.tool == "get_user" for f in cand.values())


