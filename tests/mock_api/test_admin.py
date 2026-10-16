from __future__ import annotations

import socket
import threading
import time

import httpx
import pytest
import uvicorn

from mock_api.app import create_app

IDS = ["M1", "M2", "M3", "M4", "M5", "M6-D", "M6-N", "M7", "M8", "M9", "M10", "M11", "W1", "U1", "D1", "C1", "C2", "C3"]
SEED_USERS = {
    "123": {"name": "Ada", "email": "ada@example.com", "manager_id": None},
    "456": {"name": "Bob", "email": "bob@example.com", "manager_id": None},
}


@pytest.fixture
def api():
    return create_app()


@pytest.fixture
async def client(api):
    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as c:
        yield c


async def test_mutations_lists_ids_and_active(client):
    body = (await client.get("/admin/mutations")).json()
    assert body == {"active": None, "ids": IDS}


async def test_set_mutation_changes_spec_and_clears(client):
    r = await client.post("/admin/mutation", json={"id": "M1"})
    assert r.status_code == 200
    assert (await client.get("/admin/mutations")).json()["active"] == "M1"
    assert "customer_id" in (await client.get("/openapi.json")).text

    r = await client.post("/admin/mutation", json={"id": None})
    assert r.status_code == 200
    assert (await client.get("/admin/mutations")).json()["active"] is None
    assert "customer_id" not in (await client.get("/openapi.json")).text


async def test_m6_alias_is_accepted_but_not_listed(client):
    r = await client.post("/admin/mutation", json={"id": "M6"})
    assert r.status_code == 200
    assert r.json()["ids"] == IDS
    assert "supervisor" in (await client.get("/openapi.json")).text


async def test_unknown_mutation_is_400_and_keeps_active(client):
    await client.post("/admin/mutation", json={"id": "M2"})
    r = await client.post("/admin/mutation", json={"id": "M99"})
    assert r.status_code == 400
    assert (await client.get("/admin/mutations")).json()["active"] == "M2"


async def test_state_and_reset(client, api):
    patch = {"user_id": "123", "email": "new@example.com"}
    await client.patch("/users/email", json=patch)
    await client.post("/admin/mutation", json={"id": "M3"})

    state = (await client.get("/admin/state")).json()
    assert state["users"]["123"]["email"] == "new@example.com"
    assert state == api.state()

    r = await client.post("/admin/reset")
    assert r.status_code == 200
    assert (await client.get("/admin/state")).json() == {
        "users": SEED_USERS,
        "tickets": [],
    }
    assert (await client.get("/admin/mutations")).json()["active"] is None


async def test_admin_routes_not_in_openapi(client):
    paths = (await client.get("/openapi.json")).json()["paths"]
    assert not [p for p in paths if p.startswith("/admin")]


async def test_admin_calls_not_recorded(client, api):
    await client.post("/admin/mutation", json={"id": "M1"})
    await client.get("/admin/state")
    await client.get("/admin/mutations")
    await client.post("/admin/reset")
    assert api.requests == []

    await client.post("/users/lookup", json={"user_id": "123"})
    assert [r["path"] for r in api.requests] == ["/users/lookup"]


async def test_received_logs_real_request_without_secrets(client, api):
    await client.post("/admin/mutation", json={"id": "M5"})
    response = await client.post(
        "/users/lookup?trace=1",
        json={"target": {"id": 123}},
        headers={"X-Tenant-Id": "tenant-1", "Authorization": "Bearer hidden", "Cookie": "hidden"},
    )
    assert response.status_code == 200
    rows = (await client.get("/admin/received")).json()
    assert rows == [{
        "method": "POST",
        "path": "/users/lookup",
        "body": {"target": {"id": 123}},
        "query": {"trace": "1"},
        "headers": {"authorization_present": True, "x-tenant-id_present": True},
        "status": 200,
    }]
    assert "hidden" not in (await client.get("/admin/received")).text
    assert api.requests[0]["headers"]["authorization"] == "Bearer hidden"
    await client.post("/admin/reset")
    assert (await client.get("/admin/received")).json() == []


def test_expected_canonical_has_scripted_tool_requests(api):
    assert api.expected_canonical == {
        "M1": {"method": "POST", "path": "/users/lookup", "body": {"customer_id": "123"}, "query": {}, "headers": {}},
        "M2": {"method": "PATCH", "path": "/users/email", "body": {"user_id": 123, "email": "ada.new@example.com"}, "query": {}, "headers": {}},
        "M3": {"method": "POST", "path": "/users/lookup", "body": {"user_id": "123"}, "query": {}, "headers": {}},
        "M4": {"method": "POST", "path": "/tickets", "body": {"user_id": "123", "title": "Email changed"}, "query": {}, "headers": {"authorization": {"ref": "config", "key": "OAUTH_BEARER"}}},
        "M5": {"method": "POST", "path": "/users/lookup", "body": {"target": {"id": 123}}, "query": {}, "headers": {"x-tenant-id": {"ref": "config", "key": "TENANT_ID"}}},
        "M6-D": {"method": "POST", "path": "/users/manager", "body": {"subject": "123", "supervisor": "456"}, "query": {}, "headers": {}},
        "M6-N": {"method": "POST", "path": "/users/manager", "body": {"subject": "123", "supervisor": "456"}, "query": {}, "headers": {}},
        "M7": {"method": "PATCH", "path": "/users/email", "body": {"user_id": "123", "email_address": "ada.new@example.com"}, "query": {}, "headers": {}},
        "M8": {"method": None, "path": None, "body": None, "query": None, "headers": None, "must_refuse": True},
        "M9": {"method": "PATCH", "path": "/users/email", "body": {"payload": {"user_id": "123", "email": "ada.new@example.com"}}, "query": {}, "headers": {}},
        "M10": {"method": "POST", "path": "/users/lookup", "body": {"customer_id": "123"}, "query": {}, "headers": {}},
        "M11": {"method": "POST", "path": "/customers/lookup", "body": {"customer_id": "123"}, "query": {}, "headers": {}},
        "W1": {"method": "PATCH", "path": "/users/email", "body": {"user_id": "123", "email": "ada.new@example.com"}, "query": {}, "headers": {}},
        "U1": {"method": "POST", "path": "/payments", "body": {"amount_cents": 1250}, "query": {}, "headers": {}},
        "D1": {"method": "POST", "path": "/tickets", "body": {"user_id": "123", "title": "Email changed"}, "query": {}, "headers": {}},
        "C1": {"method": "POST", "path": "/users/lookup", "body": {"user_id": "123"}, "query": {}, "headers": {}},
        "C2": {"method": "POST", "path": "/users/lookup", "body": {"user_id": "123"}, "query": {}, "headers": {}},
        "C3": {"method": "POST", "path": "/users/lookup", "body": {"user_id": "123"}, "query": {}, "headers": {}},
    }


def test_real_http_switch_to_m1():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(), log_level="warning", lifespan="on")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline
            time.sleep(0.01)
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False) as c:
            assert c.post("/admin/mutation", json={"id": "M1"}).status_code == 200
            assert c.post("/users/lookup", json={"user_id": "123"}).status_code == 422
            assert "customer_id" in c.get("/openapi.json").text
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
    assert not thread.is_alive()
