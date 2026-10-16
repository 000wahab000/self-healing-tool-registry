"""AC-63 to AC-66: upstream MCP servers behind the gateway, healed through the shared core."""

from __future__ import annotations

import copy

import pytest

from healer.gateway import load_config

USER = {"user_id": "123"}


@pytest.mark.asyncio
async def test_ac_63_tools_are_namespaced_merged_and_hide_admin_tools(gateway_factory):
    async with gateway_factory("users", "tickets") as (gw, _, _):
        names = {t["name"] for t in gw.tools()}
    assert {"users__get_user", "users__update_email", "tickets__list_tickets"} <= names
    assert not any("__admin" in n for n in names)


@pytest.mark.asyncio
async def test_ac_63_healthy_call_and_unknown_tool(gateway_factory):
    async with gateway_factory("users") as (gw, _, store):
        result = await gw.call("users__get_user", USER)
        missing = await gw.call("users__nope", {})
        events = store.audit_events()
    assert result["id"] == "123"
    assert missing["error"] == "UNKNOWN_TOOL"
    assert events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "tool", "args", "check"),
    [
        ("M1", "users__get_user", USER, ("id", "123")),
        ("T-RENAME", "users__get_user", USER, ("id", "123")),
        (
            "M2",
            "users__update_email",
            {"user_id": "123", "email": "m2@example.com", "email_type": "work"},
            ("email", "m2@example.com"),
        ),
        (
            "T-ENUM",
            "users__update_email",
            {"user_id": "123", "email": "enum@example.com", "email_type": "work"},
            ("email", "enum@example.com"),
        ),
    ],
)
async def test_ac_64_upstream_drift_heals_with_frozen_schema(
    gateway_factory, mutation, tool, args, check
):
    async with gateway_factory("users") as (gw, drifts, store):
        frozen = copy.deepcopy(gw.tools())
        drifts["users"].apply_mutation(mutation)
        result = await gw.call(tool, args)
        again = await gw.call(tool, args)  # tier 0: the stored fix, no new heal
        events = store.audit_events()
        assert gw.tools() == frozen
    key, value = check
    assert result[key] == value and again[key] == value
    assert len(events) == 1 and events[0].outcome.value == "RECOVERED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "tool", "args"),
    [
        ("T-REQUIRED", "users__update_email", {"user_id": "123", "email": "x@example.com", "email_type": "work"}),
        ("M8", "users__create_ticket", {"user_id": "123", "title": "help"}),
    ],
)
async def test_ac_65_unexplainable_drift_refuses(gateway_factory, mutation, tool, args):
    async with gateway_factory("users") as (gw, drifts, store):
        drifts["users"].apply_mutation(mutation)
        result = await gw.call(tool, args)
        events = store.audit_events()
    assert result["error"] == "SCHEMA_DRIFT_UNRECOVERABLE" and result["retry"] is False
    assert len(events) == 1 and events[0].outcome.value != "RECOVERED"


@pytest.mark.asyncio
async def test_ac_65_business_error_is_not_healed(gateway_factory):
    async with gateway_factory("users") as (gw, _, store):
        result = await gw.call("users__get_user", {"user_id": "999"})
        events = store.audit_events()
    assert result["error"] == "API_ERROR" and result["class"] == "BUSINESS"
    assert all(e.outcome.value == "NOT_DRIFT" for e in events)


def test_ac_66_config_has_no_secrets_and_rejects_bad_names(tmp_path):
    servers = load_config("config/mcp_servers.json")
    assert {s["name"] for s in servers} == {"users", "tickets"}
    assert all("token" not in s or s["token"] is None for s in servers)
    bad = tmp_path / "bad.json"
    bad.write_text('{"servers": [{"name": "a__b", "transport": "stdio", "command": ["x"]}]}')
    with pytest.raises(ValueError):
        load_config(bad)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["M1", "T-RENAME"])
async def test_ac_64_precompute_prepares_mcp_fix_before_any_failure(gateway_factory, mutation):
    async with gateway_factory("users") as (gw, drifts, store):
        registry = gw.registries[0]
        old = await registry.spec_source()
        drifts["users"].apply_mutation(mutation)
        new = await registry.spec_source()
        stored = await registry.healer.precompute(old, new)
        result = await gw.call("users__get_user", USER)
        events = store.audit_events()
    assert stored >= 1
    assert result["id"] == "123"
    assert len(events) == 1 and events[0].tier == 0
