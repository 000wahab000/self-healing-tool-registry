from __future__ import annotations

import httpx
import pytest

from mock_api.app import create_app

TOKEN = "test-token"
LOOKUP, EMAIL, MANAGER, TICKETS = (
    "/users/lookup",
    "/users/email",
    "/users/manager",
    "/tickets",
)
SEED = {
    "users": {
        "123": {"name": "Ada", "email": "ada@example.com", "manager_id": None},
        "456": {"name": "Bob", "email": "bob@example.com", "manager_id": None},
    },
    "tickets": [],
}


@pytest.fixture
def api():
    return create_app(TOKEN)


@pytest.fixture
async def client(api):
    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as c:
        yield c


def deref(spec: dict, node: dict) -> dict:
    if "$ref" not in node:
        return node
    target = spec
    for part in node["$ref"][2:].split("/"):
        target = target[part]
    return target


def operation(spec: dict, op_id: str) -> tuple[str, str, dict]:
    for path, item in spec["paths"].items():
        for method, op in item.items():
            if op["operationId"] == op_id:
                return method.upper(), path, op
    raise AssertionError(f"no operation {op_id}")


def request_schema(spec: dict, op_id: str) -> dict:
    op = operation(spec, op_id)[2]
    return deref(spec, op["requestBody"]["content"]["application/json"]["schema"])


def response_schema(spec: dict, op_id: str) -> dict:
    op = operation(spec, op_id)[2]
    return deref(spec, op["responses"]["200"]["content"]["application/json"]["schema"])


def params(spec: dict, op_id: str) -> list[tuple[str, str, bool]]:
    op = operation(spec, op_id)[2]
    return [(p["name"], p["in"], p["required"]) for p in op.get("parameters", [])]


async def get_spec(client: httpx.AsyncClient) -> dict:
    return (await client.get("/openapi.json")).json()


def errors(resp: httpx.Response) -> set[tuple[tuple, str]]:
    return {(tuple(e["loc"]), e["type"]) for e in resp.json()["detail"]}


async def test_v1_spec(client):
    spec = await get_spec(client)
    ids = {op["operationId"] for item in spec["paths"].values() for op in item.values()}
    assert ids == {"get_user", "update_email", "set_manager", "create_ticket"}
    assert operation(spec, "get_user")[:2] == ("POST", LOOKUP)
    assert operation(spec, "update_email")[:2] == ("PATCH", EMAIL)
    assert operation(spec, "set_manager")[:2] == ("POST", MANAGER)
    assert operation(spec, "create_ticket")[:2] == ("POST", TICKETS)
    manager = request_schema(spec, "set_manager")["properties"]
    assert {k: v["description"] for k, v in manager.items()} == {
        "user_id": "ID of the user",
        "manager_id": "ID of the manager",
    }
    assert params(spec, "create_ticket") == [("idempotency-key", "header", False)]
    assert "securitySchemes" not in spec.get("components", {})


async def test_v1_happy_path(client, api):
    r = await client.post(LOOKUP, json={"user_id": "123"})
    assert (r.status_code, r.json()) == (
        200,
        {"id": "123", "name": "Ada", "email": "ada@example.com"},
    )
    r = await client.patch(EMAIL, json={"user_id": "123", "email": "new@example.com"})
    assert (r.status_code, r.json()) == (200, {"id": "123", "email": "new@example.com"})
    r = await client.post(MANAGER, json={"user_id": "123", "manager_id": "456"})
    assert (r.status_code, r.json()) == (200, {"id": "123", "manager_id": "456"})
    r = await client.post(TICKETS, json={"user_id": "123", "title": "Confirm"})
    ticket = r.json()
    assert r.status_code == 200
    assert set(ticket) == {"ticket_id", "user_id", "title"} and ticket["ticket_id"]
    assert (ticket["user_id"], ticket["title"]) == ("123", "Confirm")
    state = api.state()
    assert state["users"]["123"] == {
        "name": "Ada",
        "email": "new@example.com",
        "manager_id": "456",
    }
    assert state["tickets"] == [ticket]
    state["users"]["123"]["name"] = "changed"
    assert api.state()["users"]["123"]["name"] == "Ada"


async def test_v1_strict_types_and_unknown_fields(client):
    r = await client.post(LOOKUP, json={"user_id": 123})
    assert r.status_code == 422
    assert errors(r) == {(("body", "user_id"), "string_type")}
    r = await client.post(LOOKUP, json={"user_id": "123", "extra": 1})
    assert r.status_code == 200


async def test_m1_rename_user_id(client, api):
    api.set_mutation("M1")
    schema = request_schema(await get_spec(client), "get_user")
    assert set(schema["properties"]) == {"customer_id"}
    assert schema["required"] == ["customer_id"]
    r = await client.post(LOOKUP, json={"user_id": "123"})
    assert r.status_code == 422
    assert errors(r) == {(("body", "customer_id"), "missing")}
    r = await client.post(LOOKUP, json={"customer_id": "123"})
    assert (r.status_code, r.json()["id"]) == (200, "123")


async def test_m2_user_id_becomes_integer(client, api):
    api.set_mutation("M2")
    schema = request_schema(await get_spec(client), "update_email")
    assert schema["properties"]["user_id"]["type"] == "integer"
    r = await client.patch(EMAIL, json={"user_id": "123", "email": "n@example.com"})
    assert r.status_code == 422
    assert errors(r) == {(("body", "user_id"), "int_type")}
    r = await client.patch(EMAIL, json={"user_id": 123, "email": "n@example.com"})
    assert (r.status_code, r.json()) == (200, {"id": "123", "email": "n@example.com"})
    assert api.state()["users"]["123"]["email"] == "n@example.com"


async def test_m3_response_nested_under_data(client, api):
    api.set_mutation("M3")
    spec = await get_spec(client)
    resp = response_schema(spec, "get_user")
    assert set(resp["properties"]) == {"data"}
    inner = deref(spec, resp["properties"]["data"])
    assert set(inner["properties"]) == {"id", "name", "email"}
    r = await client.post(LOOKUP, json={"user_id": "123"})
    assert r.status_code == 200
    assert r.json() == {
        "data": {"id": "123", "name": "Ada", "email": "ada@example.com"}
    }


async def test_m4_bearer_required(client, api):
    api.set_mutation("M4")
    spec = await get_spec(client)
    schemes = spec["components"]["securitySchemes"]
    assert [(s["type"], s["scheme"]) for s in schemes.values()] == [("http", "bearer")]
    assert operation(spec, "create_ticket")[2]["security"] == [
        {next(iter(schemes)): []}
    ]
    assert "security" not in operation(spec, "get_user")[2]
    body = {"user_id": "123", "title": "t"}
    for headers in (
        {},
        {"Authorization": "Bearer wrong"},
        {"Authorization": "Basic dGVzdA=="},
    ):
        r = await client.post(TICKETS, json=body, headers=headers)
        assert r.status_code == 401
        assert r.headers["www-authenticate"] == "Bearer"
    assert api.state()["tickets"] == []
    r = await client.post(
        TICKETS, json=body, headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert r.status_code == 200
    assert len(api.state()["tickets"]) == 1


async def test_m5_nested_int_target_and_tenant_header(client, api):
    api.set_mutation("M5")
    spec = await get_spec(client)
    assert params(spec, "get_user") == [("x-tenant-id", "header", True)]
    target = deref(spec, request_schema(spec, "get_user")["properties"]["target"])
    assert target["properties"]["id"]["type"] == "integer"
    r = await client.post(LOOKUP, json={"user_id": "123"})
    assert r.status_code == 422
    assert errors(r) == {
        (("body", "target"), "missing"),
        (("header", "x-tenant-id"), "missing"),
    }
    headers = {"X-Tenant-Id": "t-1"}
    r = await client.post(LOOKUP, json={"target": {"id": "123"}}, headers=headers)
    assert r.status_code == 422
    assert errors(r) == {(("body", "target", "id"), "int_type")}
    r = await client.post(LOOKUP, json={"target": {"id": 123}}, headers=headers)
    assert (r.status_code, r.json()["id"]) == (200, "123")


async def test_m6_set_manager_fields_renamed(client, api):
    api.set_mutation("M6")
    props = request_schema(await get_spec(client), "set_manager")["properties"]
    assert {k: v["description"] for k, v in props.items()} == {
        "subject": "ID of the user whose manager is being set",
        "supervisor": "User ID of the new manager",
    }
    r = await client.post(MANAGER, json={"user_id": "123", "manager_id": "456"})
    assert r.status_code == 422
    assert errors(r) == {
        (("body", "subject"), "missing"),
        (("body", "supervisor"), "missing"),
    }
    r = await client.post(MANAGER, json={"subject": "123", "supervisor": "456"})
    assert (r.status_code, r.json()) == (200, {"id": "123", "manager_id": "456"})
    assert api.state()["users"]["123"]["manager_id"] == "456"


async def test_m7_old_email_field_silently_ignored(client, api):
    api.set_mutation("M7")
    schema = request_schema(await get_spec(client), "update_email")
    assert set(schema["properties"]) == {"user_id", "email_address"}
    assert schema["required"] == ["user_id"]
    r = await client.patch(EMAIL, json={"user_id": "123", "email": "new@example.com"})
    assert (r.status_code, r.json()) == (200, {"id": "123", "email": "ada@example.com"})
    assert api.state()["users"]["123"]["email"] == "ada@example.com"
    r = await client.patch(
        EMAIL, json={"user_id": "123", "email_address": "new@example.com"}
    )
    assert (r.status_code, r.json()) == (200, {"id": "123", "email": "new@example.com"})
    assert api.state()["users"]["123"]["email"] == "new@example.com"


async def test_m8_priority_required_with_no_source(client, api):
    api.set_mutation("M8")
    schema = request_schema(await get_spec(client), "create_ticket")
    assert "priority" in schema["required"]
    assert schema["properties"]["priority"]["enum"] == ["low", "medium", "high"]
    r = await client.post(TICKETS, json={"user_id": "123", "title": "t"})
    assert r.status_code == 422
    assert errors(r) == {(("body", "priority"), "missing")}
    assert api.state()["tickets"] == []
    r = await client.post(
        TICKETS, json={"user_id": "123", "title": "t", "priority": "high"}
    )
    assert r.status_code == 200
    assert len(api.state()["tickets"]) == 1


async def test_c1_two_503_then_ok(client, api):
    base = await get_spec(client)
    api.set_mutation("C1")
    assert await get_spec(client) == base
    codes = [
        (await client.post(LOOKUP, json={"user_id": "123"})).status_code
        for _ in range(3)
    ]
    assert codes == [503, 503, 200]
    api.set_mutation("C1")
    assert (await client.post(LOOKUP, json={"user_id": "123"})).status_code == 503


def lookup_args(mid: str | None, user: str) -> dict:
    if mid == "M1":
        return {"json": {"customer_id": user}}
    if mid == "M5":
        return {
            "json": {"target": {"id": int(user)}},
            "headers": {"X-Tenant-Id": "t-1"},
        }
    return {"json": {"user_id": user}}


@pytest.mark.parametrize("mid", [None, *(f"M{i}" for i in range(1, 9)), "C1"])
async def test_unknown_user_is_404_in_every_variant(client, api, mid):
    api.set_mutation(mid)
    for _ in range(3):  # C1 answers 503 twice first
        r = await client.post(LOOKUP, **lookup_args(mid, "999"))
    assert (r.status_code, r.json()) == (404, {"detail": "User not found"})


async def test_unknown_user_is_404_on_writes(client):
    for r in (
        await client.patch(EMAIL, json={"user_id": "999", "email": "n@example.com"}),
        await client.post(MANAGER, json={"user_id": "123", "manager_id": "999"}),
        await client.post(TICKETS, json={"user_id": "999", "title": "t"}),
    ):
        assert (r.status_code, r.json()) == (404, {"detail": "User not found"})


async def test_idempotency_key_returns_same_ticket(client, api):
    body = {"user_id": "123", "title": "t"}
    a = await client.post(TICKETS, json=body, headers={"Idempotency-Key": "k1"})
    b = await client.post(TICKETS, json=body, headers={"Idempotency-Key": "k1"})
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert len(api.state()["tickets"]) == 1
    c = await client.post(TICKETS, json=body, headers={"Idempotency-Key": "k2"})
    assert c.json()["ticket_id"] != a.json()["ticket_id"]
    await client.post(TICKETS, json=body)
    await client.post(TICKETS, json=body)
    assert len(api.state()["tickets"]) == 4


async def test_request_log_records_what_clients_sent(client, api):
    await client.post(LOOKUP, json={"user_id": "123"}, headers={"X-Tenant-Id": "t-1"})
    await client.get("/openapi.json")
    first, second = api.requests
    assert (first["method"], first["path"]) == ("POST", LOOKUP)
    assert first["body"] == {"user_id": "123"}
    assert first["headers"]["x-tenant-id"] == "t-1"
    assert all(k == k.lower() for k in first["headers"])
    assert (second["method"], second["path"], second["body"]) == (
        "GET",
        "/openapi.json",
        None,
    )


async def test_request_log_keeps_rejected_and_undecodable_bodies(client, api):
    api.set_mutation("M1")
    assert (await client.post(LOOKUP, json={"user_id": "123"})).status_code == 422
    assert api.requests[-1]["body"] == {"user_id": "123"}
    assert (await client.post(LOOKUP, content=b"not json")).status_code == 422
    assert api.requests[-1]["body"] is None


async def test_set_mutation_keeps_data_and_log(client, api):
    await client.patch(EMAIL, json={"user_id": "123", "email": "new@example.com"})
    before, logged = api.state(), len(api.requests)
    assert before["users"]["123"]["email"] == "new@example.com"
    api.set_mutation("M1")
    assert api.state() == before
    assert len(api.requests) == logged


async def test_unknown_mutation_id_is_rejected(api):
    with pytest.raises(ValueError):
        api.set_mutation("M9")


async def test_reset_restores_seed_and_v1(client, api):
    assert api.state() == SEED
    api.set_mutation("M1")
    await client.patch(EMAIL, json={"user_id": "123", "email": "new@example.com"})
    body = {"user_id": "123", "title": "first"}
    await client.post(TICKETS, json=body, headers={"Idempotency-Key": "k"})
    api.reset()
    assert api.state() == SEED
    assert api.requests == []
    assert set(request_schema(await get_spec(client), "get_user")["properties"]) == {
        "user_id"
    }
    r = await client.post(
        TICKETS, json={**body, "title": "second"}, headers={"Idempotency-Key": "k"}
    )
    assert r.json()["title"] == "second"
    assert len(api.state()["tickets"]) == 1
