"""AC-100: fake a tool's input schema from the dashboard and watch the registry heal it."""

from __future__ import annotations

import asyncio
import copy
import time

import httpx
import pytest

from dashboard.app import create_app
from dashboard.drift_editor import custom_from_schema
from healer.models import HealOutcome

GET_USER = {
    "type": "object",
    "properties": {"user_id": {"type": "string", "description": "User identifier"}},
    "required": ["user_id"],
}
UPDATE_EMAIL = {
    "type": "object",
    "properties": {"user_id": {"type": "string"}, "email": {"type": "string"}},
    "required": ["user_id", "email"],
}


def fake(schema: dict, **edits) -> dict:
    out = copy.deepcopy(schema)
    for key, value in edits.items():
        out[key] = value
    return out


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ("JEV_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY", "DB_PATH"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
async def client(tmp_path):
    app = create_app(str(tmp_path / "dash.db"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dash") as c:
        yield c
    await app.state.dash.aclose()


async def finished(client, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        s = (await client.get("/api/state")).json()
        if all(r["status"] not in ("idle", "running") for r in s["runs"].values()):
            return s
        await asyncio.sleep(0.02)
    raise AssertionError("runs did not finish")


def test_ac_100_rename_property():
    f = fake(GET_USER, properties={"account": {"type": "string"}}, required=["account"])
    assert custom_from_schema("get_user", GET_USER, f) == {
        "tool": "get_user",
        "rename": {"user_id": "account"},
    }


def test_ac_100_string_to_integer():
    f = fake(GET_USER, properties={"user_id": {"type": "integer"}})
    assert custom_from_schema("get_user", GET_USER, f) == {
        "tool": "get_user",
        "rename": {},
        "to_int": "user_id",
    }


def test_ac_100_wrap_in_one_object():
    f = {"type": "object", "properties": {"payload": GET_USER}, "required": ["payload"]}
    assert custom_from_schema("get_user", GET_USER, f) == {
        "tool": "get_user",
        "rename": {},
        "wrap": "payload",
    }


def test_ac_100_wrap_combined_with_rename_and_int():
    inner = fake(GET_USER, properties={"account": {"type": "integer"}}, required=["account"])
    f = {"type": "object", "properties": {"payload": inner}, "required": ["payload"]}
    assert custom_from_schema("get_user", GET_USER, f) == {
        "tool": "get_user",
        "rename": {"user_id": "account"},
        "to_int": "user_id",
        "wrap": "payload",
    }


def test_ac_100_new_required_property():
    props = {**GET_USER["properties"], "priority": {"type": "string"}}
    f = fake(GET_USER, properties=props, required=["user_id", "priority"])
    assert custom_from_schema("get_user", GET_USER, f)["require"] == "priority"


def test_ac_100_header_only_is_a_change():
    spec = custom_from_schema("get_user", GET_USER, GET_USER, header=" X-Tenant-Id ")
    assert spec == {"tool": "get_user", "rename": {}, "header": "X-Tenant-Id"}


def test_ac_100_rename_pairs_by_order_among_same_types():
    f = fake(
        UPDATE_EMAIL,
        properties={"user_id": {"type": "string"}, "address": {"type": "string"}},
        required=["user_id", "address"],
    )
    assert custom_from_schema("update_email", UPDATE_EMAIL, f)["rename"] == {"email": "address"}


@pytest.mark.parametrize(
    "edit",
    [
        {"properties": {}, "required": []},  # deleting a field
        {"properties": {"user_id": {"type": "boolean"}}},  # unsupported type change
        {"properties": {"user_id": {"type": "string", "pattern": "^x"}}},  # constraint edit
        {"required": []},  # required set changed
        {"properties": None},  # not a schema
    ],
)
def test_ac_100_unsupported_edit_raises_and_lists_what_is_supported(edit):
    with pytest.raises(ValueError, match="rename|properties"):
        custom_from_schema("get_user", GET_USER, fake(GET_USER, **edit))


def test_ac_100_no_change_raises():
    with pytest.raises(ValueError, match="equals the actual"):
        custom_from_schema("get_user", GET_USER, copy.deepcopy(GET_USER))


def test_ac_100_unknown_tool_raises():
    with pytest.raises(ValueError, match="tool"):
        custom_from_schema("nope", GET_USER, fake(GET_USER, properties={"a": {"type": "string"}}))


async def test_ac_100_schemas_endpoint_returns_the_agent_input_per_tool(client):
    tools = (await client.get("/api/drift-editor/schemas")).json()["tools"]
    assert set(tools) == {"get_user", "update_email", "set_manager", "create_ticket"}
    assert tools["get_user"]["properties"]["user_id"]["type"] == "string"


async def test_ac_100_fake_rename_is_healed_by_the_registry(client):
    actual = (await client.get("/api/drift-editor/schemas")).json()["tools"]["get_user"]
    edited = copy.deepcopy(actual)
    edited["properties"] = {"account": edited["properties"]["user_id"]}
    edited["required"] = ["account"]

    r = await client.post(
        "/api/mutation",
        json={"id": "CUSTOM", "custom": {"tool": "get_user"}, "fake_schema": edited},
    )
    assert r.status_code == 200
    assert r.json()["active_mutation"] == "CUSTOM"
    assert r.json()["active_custom"]["rename"] == {"user_id": "account"}

    s = await finished(client)
    heals = [h for h in s["heals"] if h["tool"] == "get_user"]
    assert heals and heals[0]["outcome"] == HealOutcome.RECOVERED
    assert s["runs"]["healing"]["status"] == "done"
    assert s["runs"]["baseline"]["hit_limit"] is True


async def test_ac_100_ready_custom_spec_is_accepted(client):
    r = await client.post(
        "/api/mutation",
        json={"id": "CUSTOM", "custom": {"tool": "get_user", "wrap": "payload"}},
    )
    assert r.status_code == 200
    assert r.json()["mocks"]["healing"]["mutation"] == "CUSTOM"
    await finished(client)


async def test_ac_100_bad_fake_schema_is_a_400_and_changes_nothing(client):
    for body in (
        {"id": "CUSTOM", "custom": {"tool": "get_user"}, "fake_schema": {"type": "object", "properties": {}}},
        {"id": "CUSTOM", "custom": {"tool": "nope"}, "fake_schema": {"properties": {}}},
        {"id": "CUSTOM"},
    ):
        r = await client.post("/api/mutation", json=body)
        assert r.status_code == 400, body
    s = (await client.get("/api/state")).json()
    assert (s["active_mutation"], s["active_custom"]) == (None, None)


async def test_ac_100_reset_and_clear_drop_the_custom_spec(client):
    await client.post(
        "/api/mutation", json={"id": "CUSTOM", "custom": {"tool": "get_user", "wrap": "p"}}
    )
    await finished(client)
    await client.post("/api/mutation", json={"id": None})
    s = (await client.get("/api/state")).json()
    assert (s["active_mutation"], s["active_custom"]) == (None, None)


async def test_ac_100_write_rename_reads_back_on_the_undrifted_lookup(client):
    # update_email's user_id renamed; /users/lookup (the read-back route) did not drift.
    r = await client.post(
        "/api/mutation",
        json={"id": "CUSTOM", "custom": {"tool": "update_email", "rename": {"user_id": "account"}}},
    )
    assert r.status_code == 200
    s = await finished(client)
    heals = [h for h in s["heals"] if h["tool"] == "update_email"]
    assert heals and heals[0]["outcome"] == HealOutcome.RECOVERED, heals
