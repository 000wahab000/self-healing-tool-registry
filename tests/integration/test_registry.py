from __future__ import annotations

import pytest

from healer import canonical
from healer.models import DecisionPath, ErrorClass, Fix, Tier
from healer.registry import Registry
from healer.store import Store

V1_BODY = {
    "get_user": {"user_id"},
    "update_email": {"user_id", "email"},
    "set_manager": {"user_id", "manager_id"},
    "create_ticket": {"user_id", "title"},
}
ROUTES = {
    "get_user": "/users/lookup",
    "update_email": "/users/email",
    "set_manager": "/users/manager",
    "create_ticket": "/tickets",
}
USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}


def calls_to(api, path: str) -> list[dict]:
    return [r for r in api.requests if r["path"] == path]


def fix_for(tool: str, request_ops=(), response_ops=()) -> Fix:
    return Fix(
        fingerprint="f" * 16,
        signature={},
        tool=tool,
        cls=ErrorClass.E2,
        request_ops=list(request_ops),
        response_ops=list(response_ops),
        tier=Tier.T1,
        source=DecisionPath.diff,
        schema_hash="h",
    )


async def test_ac_01_registry_loads_four_tools(registry):
    tools = {t["name"]: t for t in registry.tools()}
    assert set(tools) == set(V1_BODY)
    for name, fields in V1_BODY.items():
        params = tools[name]["parameters"]
        assert set(tools[name]) == {"name", "description", "parameters"}
        assert params["type"] == "object"
        assert set(params["properties"]) == fields
        assert set(params["required"]) == fields
        assert {p["type"] for p in params["properties"].values()} == {"string"}
    manager = tools["set_manager"]["parameters"]["properties"]
    assert manager["user_id"]["description"] == "Employee to update"
    assert manager["manager_id"]["description"] == "Manager to assign"
    assert len(registry.spec_hash) == 64


async def test_load_saves_spec_snapshot(client, tools_config, tmp_path):
    store = Store(str(tmp_path / "s.db"))
    reg = Registry(client, tools_config, {}, store=store)
    await reg.load()
    assert "/users/lookup" in store.get_spec(reg.spec_hash)["paths"]
    store.close()


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("get_user", {"user_id": 123}),
        ("get_user", {}),
        ("update_email", {"user_id": "123"}),
        ("set_manager", {"user_id": "123", "manager_id": None}),
        ("create_ticket", {"title": "x"}),
    ],
)
async def test_ac_02_invalid_args_no_heal(api, registry, tool, args):
    result = await registry.call(tool, args)
    assert result == {"error": "AGENT_ARG_ERROR", "tool": tool, "retry": False}
    assert calls_to(api, ROUTES[tool]) == []


async def test_unknown_tool(registry):
    result = await registry.call("nope", {})
    assert result["error"] == "UNKNOWN_TOOL"


@pytest.mark.parametrize(
    ("tool", "args", "expected"),
    [
        ("get_user", {"user_id": "123"}, USER),
        (
            "update_email",
            {"user_id": "123", "email": "new@example.com"},
            {"id": "123", "email": "new@example.com"},
        ),
        (
            "set_manager",
            {"user_id": "123", "manager_id": "456"},
            {"id": "123", "manager_id": "456"},
        ),
    ],
)
async def test_healthy_call(api, registry, tool, args, expected):
    assert await registry.call(tool, args) == expected
    (sent,) = calls_to(api, ROUTES[tool])
    assert sent["body"] == args


async def test_healthy_create_ticket_sends_idempotency_key(api, registry):
    args = {"user_id": "123", "title": "Confirm"}
    first = await registry.call("create_ticket", args)
    second = await registry.call("create_ticket", args)
    assert first["ticket_id"] and first["ticket_id"] != second["ticket_id"]
    assert {k: first[k] for k in args} == args
    keys = [r["headers"]["idempotency-key"] for r in calls_to(api, "/tickets")]
    assert len(keys) == 2 and all(keys) and keys[0] != keys[1]
    assert len(api.state()["tickets"]) == 2


async def test_base_doc_routes_args_and_key(registry):
    get_user = registry.defs["get_user"]
    assert registry.base_doc(get_user, {"user_id": "123"}) == {
        "route": {"method": "POST", "path": "/users/lookup"},
        "body": {"user_id": "123"},
        "query": {},
        "header": {},
    }
    ticket = registry.defs["create_ticket"]
    args = {"user_id": "123", "title": "t"}
    a, b = registry.base_doc(ticket, args), registry.base_doc(ticket, args)
    assert a["body"] == args and a["route"]["path"] == "/tickets"
    assert a["header"]["idempotency-key"] != b["header"]["idempotency-key"]


async def test_m1_v1_call_is_detected_as_e2(api, registry):
    frozen = canonical.dumps(
        [(t.agent_schema, t.base_op) for t in registry.defs.values()]
    )
    api.set_mutation("M1")
    result = await registry.call("get_user", {"user_id": "123"})
    assert result["error"] == "API_ERROR"
    assert (result["class"], result["status"]) == ("E2", "422")
    assert (
        canonical.dumps([(t.agent_schema, t.base_op) for t in registry.defs.values()])
        == frozen
    )


async def test_active_fix_request_ops_are_applied(api, registry):
    api.set_mutation("M1")
    moved = {"op": "move", "from": ["body", "user_id"], "to": ["body", "customer_id"]}
    registry.defs["get_user"].active_fix = fix_for("get_user", request_ops=[moved])
    assert await registry.call("get_user", {"user_id": "123"}) == USER
    assert calls_to(api, "/users/lookup")[-1]["body"] == {"customer_id": "123"}


async def test_active_fix_response_ops_reshape_before_contract(api, registry):
    api.set_mutation("M3")
    unfixed = await registry.call("get_user", {"user_id": "123"})
    assert (unfixed["error"], unfixed["class"]) == ("API_ERROR", "E5")
    unwrap = [
        {"op": "move", "from": ["data", f], "to": [f]} for f in ("id", "name", "email")
    ]
    registry.defs["get_user"].active_fix = fix_for("get_user", response_ops=unwrap)
    result = await registry.call("get_user", {"user_id": "123"})
    assert {k: result[k] for k in USER} == USER
    assert "error" not in result


async def test_fr_3_4_value_rules_are_left_to_the_api(api, registry):
    # The spec carries an email pattern, but a bad value is the API's 422 to report (BUSINESS
    # once the heal controller sees an unchanged spec), not an agent-argument error.
    props = registry.defs["update_email"].agent_schema["properties"]
    assert "pattern" in props["email"]  # the agent still sees the rule
    result = await registry.call("update_email", {"user_id": "123", "email": "nope"})
    assert (result["error"], result["class"], result["status"]) == (
        "API_ERROR",
        "E2",
        "422",
    )
    assert len(calls_to(api, "/users/email")) == 1
    still_typed = await registry.call("update_email", {"user_id": "123", "email": 7})
    assert still_typed["error"] == "AGENT_ARG_ERROR"
