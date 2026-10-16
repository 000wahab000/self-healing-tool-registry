from __future__ import annotations

import httpx
import pytest

from healer.connection_security import resolve_headers, validate_entry_auth
from healer.gateway import validate_entry


def test_ac_102_legacy_token_is_runtime_bearer_without_mutation() -> None:
    entry = {
        "name": "legacy",
        "kind": "openapi",
        "base_url": "https://example.com",
        "token_env": "TOKEN",
    }
    original = entry.copy()
    validate_entry(entry)
    assert resolve_headers(entry, {"TOKEN": "secret"}) == {
        "Authorization": "Bearer secret"
    }
    assert entry == original


def test_ac_103_auth_profiles_and_conflicts() -> None:
    assert resolve_headers(
        {"auth": {"type": "api_key", "header": "X-Key", "value_env": "KEY"}},
        {"KEY": "secret"},
    ) == {"X-Key": "secret"}
    with pytest.raises(ValueError):
        resolve_headers({"auth": {"type": "bearer", "token_env": "MISSING"}}, {})
    with pytest.raises(ValueError):
        resolve_headers(
            {
                "headers": {"authorization": "literal"},
                "auth": {"type": "bearer", "token_env": "TOKEN"},
            },
            {"TOKEN": "secret"},
        )


def test_ac_103_reject_ambiguous_and_unsafe_config() -> None:
    cases = [
        {"auth": {"type": "bearer", "token_env": "TOKEN", "extra": "x"}},
        {"auth": {"type": "none"}, "token_env": "TOKEN"},
        {"headers": {"Authorization": "literal"}},
        {"secret_headers": {"X-Token": "TOKEN"}, "headers": {"x-token": "literal"}},
        {"headers": {"X-Test": "bad\r\nvalue"}},
    ]
    for entry in cases:
        with pytest.raises(ValueError):
            validate_entry_auth(entry)


def test_ac_103_entry_selection_and_spec_flags_validate() -> None:
    base = {"name": "api", "kind": "openapi", "base_url": "https://api.example"}
    for extra in (
        {"selected_operations": ["x", "x"]},
        {"spec_reuse_api_auth": "yes"},
        {"spec_url": "https://docs.example/spec", "spec_path": "/openapi.json"},
        {"spec_url": "//docs.example/openapi.json"},
    ):
        with pytest.raises(ValueError):
            validate_entry({**base, **extra})


def test_ac_104_auth_resolution_is_per_connection() -> None:
    a = resolve_headers(
        {"auth": {"type": "bearer", "token_env": "A"}}, {"A": "alpha", "B": "beta"}
    )
    b = resolve_headers(
        {"auth": {"type": "bearer", "token_env": "B"}}, {"A": "alpha", "B": "beta"}
    )
    assert a != b
    assert a["Authorization"] == "Bearer alpha"
    assert b["Authorization"] == "Bearer beta"


def test_ac_110_gateway_exports_raw_and_derived_secret_keys_only() -> None:
    from healer.gateway import _connection_config

    sources, cfg, secret_keys = _connection_config(
        {
            "name": "acct",
            "auth": {"type": "bearer", "token_env": "TOKEN"},
            "headers": {"X-Version": "v1"},
        },
        {"TOKEN": "sensitive"},
    )
    assert sources == {
        "X-Version": "connection:acct:x-version",
        "Authorization": "connection-secret:acct:authorization",
    }
    assert {cfg[key] for key in secret_keys} == {"sensitive", "Bearer sensitive"}
    assert cfg["connection:acct:x-version"] == "v1"


def test_ac_105_spec_auth_is_independent_and_same_origin_only_for_reuse() -> None:
    entry = {
        "name": "api",
        "kind": "openapi",
        "base_url": "https://api.example.com",
        "spec_url": "https://docs.example.com/openapi.json",
        "spec_reuse_api_auth": True,
    }
    with pytest.raises(ValueError, match="same-origin"):
        validate_entry(entry)


@pytest.mark.asyncio
async def test_ac_105_probe_external_spec_does_not_inherit_api_credentials() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "openapi": "3.0.0",
                "info": {"title": "t", "version": "1"},
                "paths": {},
            },
        )

    from healer.gateway import probe

    result = await probe(
        {
            "name": "docs",
            "kind": "openapi",
            "base_url": "https://api.example",
            "token_env": "API_TOKEN",
            "spec_url": "https://docs.example/openapi.json",
        },
        {"API_TOKEN": "private"},
        httpx.MockTransport(handler),
    )
    assert result["ok"] is True
    assert len(requests) == 1
    assert "authorization" not in requests[0].headers


@pytest.mark.asyncio
async def test_ac_104_mcp_selected_operations_filter_every_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from healer import gateway
    from healer.models import LoadedSpec

    class Session:
        pass

    class Registry:
        def __init__(self, client, config, cfg, store, jev, **kwargs):
            self.config = config
            self.source = kwargs["spec_source"]

        async def load(self) -> None:
            self.loaded = await self.source()

    async def source() -> LoadedSpec:
        return LoadedSpec(
            {"tools": [{"name": "keep"}, {"name": "drop"}]},
            {"srv__keep": {}, "srv__drop": {}},
            "hash",
        )

    monkeypatch.setattr(gateway.mcp_upstream, "mcp_source", lambda *_: source)
    monkeypatch.setattr(gateway, "Registry", Registry)
    registry = await gateway.upstream_registry(
        "srv", Session(), object(), {}, selected_operations=["keep"]
    )
    assert set(registry.loaded.ops) == {"srv__keep"}
    assert set(registry.config["tools"]) == {"srv__keep"}


_RAW = {"paths": {"/items": {"get": {"operationId": "list_items", "responses": {}}}}}


async def _registry_for(client, config, cfg, raw=_RAW, **kwargs):
    from healer.models import LoadedSpec
    from healer.openapi_loader import operations
    from healer.registry import Registry

    loaded = LoadedSpec(
        raw, {f"api__{k}": v for k, v in operations(raw).items()}, "hash"
    )

    async def source() -> LoadedSpec:
        return loaded

    registry = Registry(client, config, cfg, spec_source=source, **kwargs)
    await registry.load()
    return registry


@pytest.mark.asyncio
async def test_ac_107_no_empty_credential_headers_and_no_client_defaults() -> None:
    seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers)
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://x.test",
        headers={"Authorization": "client-default", "Cookie": "client-cookie"},
    ) as client:
        registry = await _registry_for(
            client,
            {"header_sources": {}, "tools": {"api__list_items": {"postchecks": []}}},
            {},
        )
        assert await registry.call("api__list_items", {}) == []
    assert "authorization" not in seen[0]
    assert "cookie" not in seen[0]


@pytest.mark.asyncio
async def test_ac_107_header_sources_are_sent_when_declared_or_connection_keyed() -> None:
    seen: list[httpx.Headers] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers)
        return httpx.Response(200, json=[])

    raw = {
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "parameters": [
                        {
                            "name": "X-Account",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {},
                }
            }
        }
    }
    config = {
        "header_sources": {
            "X-Account": "acct-key",
            "Authorization": "connection-secret:api:authorization",
            "X-Candidate": "candidate-key",  # a healing candidate only
        },
        "tools": {"api__list_items": {"postchecks": []}},
    }
    cfg = {
        "acct-key": "acct-1",
        "connection-secret:api:authorization": "Bearer abcdef123",
        "candidate-key": "cand",
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://x.test"
    ) as client:
        registry = await _registry_for(client, config, cfg, raw)
        assert await registry.call("api__list_items", {}) == []
    assert seen[0]["x-account"] == "acct-1"
    assert seen[0]["authorization"] == "Bearer abcdef123"
    assert "x-candidate" not in seen[0]


@pytest.mark.asyncio
async def test_ac_111_rest_agent_schema_is_unchanged_but_unknown_arguments_are_refused() -> None:
    body = {"content": {"application/json": {"schema": {"type": "object", "properties": {"name": {"type": "string"}}}}}}
    raw = {"paths": {"/items": {"post": {"operationId": "make", "requestBody": body, "responses": {}}}}}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        base_url="https://x.test",
    ) as client:
        registry = await _registry_for(
            client,
            {"header_sources": {}, "tools": {"api__make": {"postchecks": [], "write": True}}},
            {},
            raw,
        )
        schema = registry.tools()[0]["parameters"]
        assert "additionalProperties" not in schema
        assert await registry.call("api__make", {"name": "a", "extra": 1}) == {
            "error": "AGENT_ARG_ERROR",
            "tool": "api__make",
            "retry": False,
        }


@pytest.mark.asyncio
async def test_ac_107_unavailable_header_source_is_not_retried() -> None:
    calls: list[str] = []
    raw = {
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "parameters": [
                        {
                            "name": "X-Account",
                            "in": "header",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {},
                }
            }
        }
    }

    async def sleep(_: float) -> None:
        calls.append("sleep")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: calls.append("sent") or httpx.Response(200, json=[])
        ),
        base_url="https://x.test",
    ) as client:
        registry = await _registry_for(
            client,
            {
                "header_sources": {"X-Account": "missing"},
                "tools": {"api__list_items": {"postchecks": []}},
            },
            {},
            raw,
            sleep=sleep,
        )
        result = await registry.call("api__list_items", {})
    assert (result["class"], result["status"]) == (
        "BUSINESS",
        "HEADER_SOURCE_UNAVAILABLE",
    )
    assert calls == []
