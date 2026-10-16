from __future__ import annotations

import httpx
import pytest

from healer.connection_security import resolve_headers, validate_entry_auth
from healer.gateway import validate_entry


def test_ac_83_legacy_token_is_runtime_bearer_without_mutation() -> None:
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


def test_ac_84_auth_profiles_and_conflicts() -> None:
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


def test_ac_84_reject_ambiguous_and_unsafe_config() -> None:
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


def test_ac_84_entry_selection_and_spec_flags_validate() -> None:
    base = {"name": "api", "kind": "openapi", "base_url": "https://api.example"}
    for extra in (
        {"selected_operations": ["x", "x"]},
        {"spec_reuse_api_auth": "yes"},
        {"spec_url": "https://docs.example/spec", "spec_path": "/openapi.json"},
        {"spec_url": "//docs.example/openapi.json"},
    ):
        with pytest.raises(ValueError):
            validate_entry({**base, **extra})


def test_ac_85_auth_resolution_is_per_connection() -> None:
    a = resolve_headers(
        {"auth": {"type": "bearer", "token_env": "A"}}, {"A": "alpha", "B": "beta"}
    )
    b = resolve_headers(
        {"auth": {"type": "bearer", "token_env": "B"}}, {"A": "alpha", "B": "beta"}
    )
    assert a != b
    assert a["Authorization"] == "Bearer alpha"
    assert b["Authorization"] == "Bearer beta"


def test_ac_91_gateway_exports_raw_and_derived_secret_keys_only() -> None:
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


def test_ac_86_spec_auth_is_independent_and_same_origin_only_for_reuse() -> None:
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
async def test_ac_86_probe_external_spec_does_not_inherit_api_credentials() -> None:
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
async def test_ac_85_mcp_selected_operations_filter_every_source(
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
