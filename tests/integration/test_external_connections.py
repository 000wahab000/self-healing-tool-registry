from __future__ import annotations

import asyncio
import base64
import copy
from contextlib import AsyncExitStack, asynccontextmanager, suppress

import httpx
import pytest
from mcp import ClientSession
from mcp.shared.memory import create_client_server_memory_streams

from healer import gateway
from healer.models import (
    AuditEvent,
    DecisionPath,
    ErrorClass,
    HealOutcome,
    Reason,
    Tier,
)
from healer.store import REDACTED, Store, redact_value, sanitize
from mock_api.mcp_drift_server import create_drift_server


def test_ac_110_audit_store_redacts_raw_and_auth_header_echoes(tmp_path) -> None:
    token = "integration-token-value"
    basic = base64.b64encode(b"integration-user:integration-password").decode()
    store = Store(str(tmp_path / "audit.db"))
    try:
        store.audit(
            AuditEvent(
                ts_ms=1,
                tool="external__read",
                fingerprint="abc",
                cls=ErrorClass.E2,
                raw_code="401",
                tier=Tier.T1,
                path=DecisionPath.clue,
                fix_id=None,
                outcome=HealOutcome.ABORTED,
                reason=Reason.NO_CANDIDATE,
                mttr_ms=0,
                heal_ms=0,
                jev_tokens=0,
                llm_tokens=0,
                raw_error=sanitize(
                    f'{token} Authorization: Bearer {token} '
                    f'"authorization": "Basic {basic}"',
                    [token, f"Basic {basic}"],
                ),
                layers=[],
            )
        )
        stored = store.audit_events()[0].raw_error
        assert token not in stored
        assert basic not in stored
        assert REDACTED in stored
    finally:
        store.close()


def test_ac_110_redacted_spec_snapshot_preserves_large_schema(tmp_path) -> None:
    token = 'quoted"\\password\n雪'
    original = {"paths": {"/records": {"description": "x" * 6000, "token": token}}}
    store = Store(str(tmp_path / "spec.db"))
    try:
        store.save_spec("spec", redact_value(original, [token]))
        stored = store.get_spec("spec")
        assert stored["paths"]["/records"]["description"] == "x" * 6000
        assert stored["paths"]["/records"]["token"] == REDACTED
    finally:
        store.close()


@asynccontextmanager
async def _mcp_session():
    server = create_drift_server(profile="users").server
    async with create_client_server_memory_streams() as (client, backend):
        task = asyncio.create_task(
            server.run(backend[0], backend[1], server.create_initialization_options())
        )
        try:
            async with ClientSession(client[0], client[1]) as session:
                await session.initialize()
                yield session
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def _connection_spec(field: str) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "isolated test", "version": "1"},
        "paths": {
            "/records": {
                "get": {
                    "operationId": "lookup",
                    "parameters": [
                        {
                            "name": field,
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                }
            }
        },
    }


def _empty_spec() -> dict:
    spec = _connection_spec("unused")
    spec["paths"]["/records"]["get"]["parameters"] = []
    return spec


def _parameter_spec(path: str, name: str, location: str) -> dict:
    spec = _connection_spec(name)
    path_item = spec["paths"].pop("/records")
    path_item["get"]["parameters"][0]["in"] = location
    spec["paths"][path] = path_item
    return spec


@pytest.mark.asyncio
async def test_ac_104_two_api_accounts_and_mcp_stay_isolated_through_replay(tmp_path) -> None:
    tokens = {"ACCOUNT_A_TOKEN": "account-a-secret", "ACCOUNT_B_TOKEN": "account-b-secret"}
    labels = {"Bearer account-a-secret": "account-a", "Bearer account-b-secret": "account-b"}
    spec_reads = {"account-a": 0, "account-b": 0}
    wire: list[tuple[str, str]] = []
    queries: list[tuple[str, dict[str, str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        authorization = request.headers["authorization"]
        account = labels[authorization]
        wire.append((account, request.url.path))
        queries.append((account, dict(request.url.params)))
        if request.url.path == "/openapi.json":
            spec_reads[account] += 1
            field = "old" if spec_reads[account] <= 2 else "new"
            return httpx.Response(200, json=_connection_spec(field))
        if request.url.path == "/records" and "old" in request.url.params:
            return httpx.Response(
                422,
                json={"detail": [{"loc": ["query", "new"], "type": "missing"}]},
            )
        return httpx.Response(200, json={"account": account})

    store = Store(str(tmp_path / "mixed.db"))
    try:
        async with AsyncExitStack() as stack:
            transport = httpx.MockTransport(handler)
            registries = []
            for account, token_env in (("alpha", "ACCOUNT_A_TOKEN"), ("beta", "ACCOUNT_B_TOKEN")):
                api = {
                    "name": account,
                    "kind": "openapi",
                    "base_url": "https://provider.example.test",
                    "auth": {"type": "bearer", "token_env": token_env},
                }
                registries.append(
                    await stack.enter_async_context(
                        gateway.api_registry(api, store, {}, tokens, transport=transport)
                    )
                )
            async with _mcp_session() as session:
                mcp = await gateway.upstream_registry("users", session, store, {})
                before = copy.deepcopy([tool["parameters"] for tool in registries[0].tools()])
                for account, registry in zip(("account-a", "account-b"), registries):
                    result = await registry.call(f"{('alpha' if account == 'account-a' else 'beta')}__lookup", {"old": "same-value"})
                    assert result == {"account": account}
                mcp_result = await mcp.call("users__get_user", {"user_id": "123"})
                assert "error" not in mcp_result
                assert [tool["parameters"] for tool in registries[0].tools()] == before
        assert {account for account, path in wire if path == "/records"} == {"account-a", "account-b"}
        assert spec_reads == {"account-a": 3, "account-b": 3}
        for account in ("account-a", "account-b"):
            account_queries = [q for owner, q in queries if owner == account and q]
            assert account_queries == [
                {"old": "same-value"},
                {"new": "same-value"},
            ]
        assert "old" in registries[0].defs["alpha__lookup"].agent_schema["properties"]
        events = store.audit_events()
        assert len(events) == 2
        assert all(event.outcome is HealOutcome.RECOVERED for event in events)
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ac_111_api_client_closes_when_connection_context_fails(tmp_path) -> None:
    spec = _connection_spec("lookup")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=spec))
    store = Store(str(tmp_path / "cleanup.db"))
    client = None
    try:
        with pytest.raises(RuntimeError, match="test failure"):
            async with gateway.api_registry(
                {
                    "name": "cleanup",
                    "kind": "openapi",
                    "base_url": "https://cleanup.example.test",
                },
                store,
                {},
                {},
                transport=transport,
            ) as registry:
                client = registry.client
                raise RuntimeError("test failure")
        assert client is not None and client.is_closed
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ac_107_added_required_secret_header_replays_only_with_approved_value(tmp_path) -> None:
    headers: list[str | None] = []
    specs = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal specs
        if request.url.path == "/openapi.json":
            specs += 1
            return httpx.Response(
                200,
                json=_empty_spec()
                if specs <= 2
                else _parameter_spec("/records", "X-Private", "header"),
            )
        headers.append(request.headers.get("x-private"))
        if len(headers) == 1:
            return httpx.Response(
                422,
                json={"detail": [{"loc": ["header", "X-Private"], "type": "missing"}]},
            )
        return httpx.Response(200, json={"ok": True})

    store = Store(str(tmp_path / "header-replay.db"))
    try:
        api = {
            "name": "header",
            "kind": "openapi",
            "base_url": "https://header.example.test",
            "secret_headers": {"X-Private": "PRIVATE_HEADER"},
        }
        async with gateway.api_registry(
            api, store, {}, {"PRIVATE_HEADER": "offline-secret"},
            transport=httpx.MockTransport(handler),
        ) as registry:
            result = await registry.call("header__lookup", {})
        assert result == {"ok": True}
        assert headers == ["offline-secret", "offline-secret"]
        assert len(store.audit_events()) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ac_107_required_header_without_reference_refuses_before_replay(tmp_path) -> None:
    headers = 0
    specs = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal headers, specs
        if request.url.path == "/openapi.json":
            specs += 1
            return httpx.Response(
                200,
                json=_empty_spec()
                if specs <= 2
                else _parameter_spec("/records", "X-Private", "header"),
            )
        headers += 1
        return httpx.Response(
            422,
            json={"detail": [{"loc": ["header", "X-Private"], "type": "missing"}]},
        )

    store = Store(str(tmp_path / "header-refusal.db"))
    try:
        api = {"name": "missing", "kind": "openapi", "base_url": "https://missing.example.test"}
        async with gateway.api_registry(
            api, store, {}, {}, transport=httpx.MockTransport(handler)
        ) as registry:
            result = await registry.call("missing__lookup", {})
        assert result["error"] == "SCHEMA_DRIFT_UNRECOVERABLE"
        assert headers == 1
        assert len(store.audit_events()) == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_ac_107_renamed_path_parameter_replays_without_changing_agent_schema(tmp_path) -> None:
    specs = 0
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal specs
        if request.url.path == "/openapi.json":
            specs += 1
            name = "old_id" if specs <= 2 else "record_id"
            return httpx.Response(
                200, json=_parameter_spec(f"/records/{{{name}}}", name, "path")
            )
        paths.append(request.url.path)
        if len(paths) == 1:
            return httpx.Response(404, json={"detail": "route changed"})
        return httpx.Response(200, json={"ok": True})

    store = Store(str(tmp_path / "path-replay.db"))
    try:
        api = {"name": "path", "kind": "openapi", "base_url": "https://path.example.test"}
        async with gateway.api_registry(
            api, store, {}, {}, transport=httpx.MockTransport(handler)
        ) as registry:
            before = copy.deepcopy(registry.tools()[0]["parameters"])
            result = await registry.call("path__lookup", {"old_id": "known-value"})
            after = registry.tools()[0]["parameters"]
        assert result == {"ok": True}
        assert paths == ["/records/known-value", "/records/known-value"]
        assert before == after and "old_id" in after["properties"]
        assert len(store.audit_events()) == 1
    finally:
        store.close()
