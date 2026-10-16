"""Step 0 contracts between the two tracks (AGENTS.md): OperationSpec, SpecSource, FixStore."""

from __future__ import annotations

import typing

from healer.models import LoadedSpec, OperationSpec, ParamSpec
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
    """Contract 4: Registry provides tool definitions accessor to Healer for sibling/precompute inspect."""
    reg = await make_registry()
    assert reg.healer is not None
    assert reg.healer._tools is not None
    tool_defs = list(reg.healer._tools())
    assert "get_user" in {t.name for t in tool_defs}
