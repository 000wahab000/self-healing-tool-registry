"""AC-59: the Connections page backend (config validation, routes, probe, API registries)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from healer import gateway
from healer.store import Store
from mock_api.app import create_app as create_rest_mock

MCP = {"name": "billing", "transport": "http", "url": "https://example.com/mcp"}
API = {"name": "crm", "kind": "openapi", "base_url": "https://api.example.com"}


@pytest.fixture
def cfg_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "mcp_servers.json"
    path.write_text(
        json.dumps(
            {
                "servers": [
                    {"name": "users", "transport": "stdio", "command": ["python", "x"]}
                ]
            }
        )
    )
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(path))
    monkeypatch.delenv("CONNECTIONS_TOKEN", raising=False)
    return path


@pytest.fixture
def client(cfg_file: Path):
    # No `with`: lifespan shutdown would close the SQLite store from another thread.
    return TestClient(create_app(":memory:"), client=("127.0.0.1", 50000))


# validation


@pytest.mark.parametrize(
    "entry",
    [
        {**MCP, "name": "Bad"},
        {**MCP, "name": "1abc"},
        {**MCP, "name": "a" * 33},
        {**MCP, "name": "my__tool"},
        {**MCP, "url": "file:///etc/passwd"},
        {**MCP, "url": "ftp://example.com/mcp"},
        {**MCP, "url": "https://user:pw@example.com/mcp"},
        {**MCP, "url": "https://example.com/mcp?api_key=abc"},
        {**MCP, "token_env": "sk-abcdef123456"},
        {**MCP, "token_env": "Bearer abc"},
        {**MCP, "token_env": "has space"},
        {"name": "x", "transport": "stdio", "command": ["python", "-c", "1"]},
        {**MCP, "command": ["python"]},
        {**MCP, "password": "hunter2"},
        {**API, "base_url": "gopher://example.com"},
        {**API, "kind": "grpc"},
        {**API, "spec_path": "http://evil/openapi.json"},
    ],
)
def test_ac_59_invalid_entries_rejected(entry: dict) -> None:
    with pytest.raises(ValueError):
        gateway.validate_entry(entry, http_only=True)


def test_ac_59_valid_entries_accepted() -> None:
    gateway.validate_entry({**MCP, "token_env": "API_BILLING_TOKEN"}, http_only=True)
    gateway.validate_entry({**API, "spec_path": "/v1/openapi.json"}, http_only=True)
    gateway.validate_entry(
        {"name": "s", "transport": "stdio", "command": ["python"]}
    )  # stdio stays valid in the file


def test_ac_59_duplicate_names_across_servers_and_apis(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    path.write_text(
        json.dumps({"servers": [MCP], "apis": [{**API, "name": "billing"}]})
    )
    with pytest.raises(ValueError, match="unique"):
        gateway.load_config(path)
    with pytest.raises(ValueError, match="unique"):
        gateway.load_apis(path)


def test_ac_59_load_apis_and_legacy_config() -> None:
    root = Path(__file__).parents[2] / "config" / "mcp_servers.json"
    assert [s["name"] for s in gateway.load_config(root)] == ["users", "tickets"]
    assert gateway.load_apis(root) == []


# routes


def test_ac_59_round_trip(client: TestClient, cfg_file: Path) -> None:
    assert client.get("/connections").status_code == 200
    first = client.get("/api/connections").json()
    assert [s["name"] for s in first["servers"]] == ["users"]
    assert first["servers"][0]["readonly"] is True
    assert "command" not in first["servers"][0]

    assert (
        client.post("/api/connections", json={**MCP, "token_env": "API_BILL"}).status_code
        == 200
    )
    assert (
        client.post("/api/connections", json={**API, "spec_path": ""}).status_code
        == 200
    )
    listed = client.get("/api/connections").json()
    assert [s["name"] for s in listed["servers"]] == ["users", "billing"]
    assert (
        listed["apis"][0]["name"] == "crm"
        and listed["servers"][1]["token_env"] == "API_BILL"
    )
    on_disk = json.loads(cfg_file.read_text())
    assert on_disk["apis"] == [API]  # blank optional fields are not stored
    assert not list(
        cfg_file.parent.glob(".mcp_servers-*")
    )  # temp file replaced, not left

    assert client.post("/api/connections", json=MCP).status_code == 409
    assert (
        client.post("/api/connections", json={**API, "name": "billing"}).status_code
        == 409
    )

    assert client.delete("/api/connections/billing").status_code == 200
    assert client.delete("/api/connections/billing").status_code == 404
    assert client.delete("/api/connections/crm").status_code == 200
    assert [s["name"] for s in client.get("/api/connections").json()["servers"]] == [
        "users"
    ]
    assert json.loads(cfg_file.read_text())["servers"][0]["command"] == ["python", "x"]


def test_ac_59_routes_reject_stdio_and_bad_input(client: TestClient) -> None:
    for body in (
        {"name": "x", "transport": "stdio", "command": ["python"]},
        {**MCP, "url": "file:///x"},
        {**MCP, "name": "a__b"},
    ):
        assert client.post("/api/connections", json=body).status_code == 400
        assert client.post("/api/connections/test", json=body).status_code == 400


def test_ac_59_remote_mode_needs_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fwd = {"X-Forwarded-For": "203.0.113.9"}  # behind a proxy: never local
    assert client.get("/api/connections").json()["auth_required"] is False
    assert client.get("/api/connections", headers=fwd).status_code == 403  # list needs the token too
    for call in (
        lambda h: client.post("/api/connections", json=MCP, headers=h),
        lambda h: client.delete("/api/connections/users", headers=h),
        lambda h: client.post("/api/connections/test", json=MCP, headers=h),
    ):
        assert call(fwd).status_code == 403  # CONNECTIONS_TOKEN unset
    monkeypatch.setenv("CONNECTIONS_TOKEN", "s3cret")
    assert client.post("/api/connections", json=MCP, headers=fwd).status_code == 401
    bad = {**fwd, "Authorization": "Bearer nope"}
    assert client.post("/api/connections", json=MCP, headers=bad).status_code == 401
    good = {**fwd, "Authorization": "Bearer s3cret"}
    assert client.get("/api/connections", headers=fwd).status_code == 401
    assert client.get("/api/connections", headers=good).json()["auth_required"] is True
    assert client.post("/api/connections", json=MCP, headers=good).status_code == 200
    assert client.delete("/api/connections/billing", headers=good).status_code == 200


def test_ac_59_test_route_calls_probe(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = []

    async def fake(entry: dict, *a, **k) -> dict:
        seen.append(entry)
        return {"ok": True, "tools": ["billing__x"], "error": None}

    monkeypatch.setattr(gateway, "probe", fake)
    r = client.post("/api/connections/test", json={**MCP, "token_env": ""})
    assert r.json() == {"ok": True, "tools": ["billing__x"], "error": None}
    assert seen == [MCP]


# probe and api_registry


async def test_ac_59_probe_openapi_against_rest_mock() -> None:
    transport = httpx.ASGITransport(app=create_rest_mock())
    out = await gateway.probe(
        {**API, "base_url": "http://mock", "selected_operations": "*"}, {}, transport
    )
    assert out["ok"] and out["error"] is None
    assert "crm__get_user" in out["tools"]


async def test_ac_59_probe_reports_short_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    entry = {**API, "base_url": "http://secret-host.invalid", "token_env": "TOK"}
    missing = await gateway.probe(entry, {}, httpx.MockTransport(handler))
    assert (missing["ok"], missing["tools"], missing["error"]) == (
        False,
        [],
        "environment variable TOK is not set",
    )
    out = await gateway.probe(entry, {"TOK": "hunter2"}, httpx.MockTransport(handler))
    assert out["ok"] is False and out["error"] == "HTTP 404"
    assert "hunter2" not in json.dumps(out) and "secret-host" not in json.dumps(out)


async def test_ac_59_probe_mcp_server_over_http() -> None:
    httpx2 = pytest.importorskip("httpx2")
    from mock_api.mcp_drift_server import create_drift_server

    app = create_drift_server().create_http_app()
    async with app.router.lifespan_context(app):
        out = await gateway.probe(
            {"name": "users", "transport": "http", "url": "http://127.0.0.1/mcp"},
            {},
            httpx2.ASGITransport(app=app),
        )
    assert out["ok"], out
    assert out["tools"] and all(t.startswith("users__") for t in out["tools"])


async def test_ac_59_probe_mcp_unreachable() -> None:
    httpx2 = pytest.importorskip("httpx2")

    def handler(request):
        return httpx2.Response(500)

    out = await gateway.probe(
        {"name": "users", "transport": "http", "url": "http://127.0.0.1/mcp"},
        {},
        httpx2.MockTransport(handler),
    )
    assert out["ok"] is False and out["error"]
    assert "127.0.0.1" not in out["error"] and "Traceback" not in out["error"]


async def test_ac_59_api_registry_namespaces_and_calls(tmp_path: Path) -> None:
    transport = httpx.ASGITransport(app=create_rest_mock())
    store = Store(str(tmp_path / "api.db"))
    api = {
        **API,
        "base_url": "http://mock",
        "token_env": "CRM_TOKEN",
        "selected_operations": "*",
    }
    cfg = {"TENANT_ID": "t-1"}
    try:
        async with gateway.api_registry(
            api, store, cfg, {"CRM_TOKEN": "test-token"}, transport=transport
        ) as registry:
            names = {t["name"] for t in registry.tools()}
            assert "crm__get_user" in names and "get_user" not in names
            # the mock's get_user is a POST, so the method rule makes it a non-idempotent write
            assert registry.defs["crm__get_user"].config == {
                "write": True,
                "idempotent": False,
                "postchecks": [],
            }
            assert registry.defs["crm__update_email"].config["idempotent"] is False
            assert registry.defs["crm__set_manager"].config["write"] is True
            assert "crm__create_ticket" not in registry.defs  # UNSUPPORTED_PARAMETER_SCHEMA
            result = await registry.call("crm__get_user", {"user_id": "123"})
            assert "error" not in result, result
            assert result["id"] == "123"
            client = registry.client
        assert client.is_closed
    finally:
        store.close()


def test_ac_59_api_tool_config_by_method() -> None:
    cases = {
        "GET": (False, True),
        "HEAD": (False, True),
        "PUT": (True, True),
        "DELETE": (True, True),
        "POST": (True, False),
        "PATCH": (True, False),
    }
    for method, (write, idem) in cases.items():
        cfg = gateway.api_tool_config({"method": method})
        assert (cfg["write"], cfg["idempotent"], cfg["postchecks"]) == (write, idem, [])


def test_ac_59_non_local_client_needs_token_even_on_a_local_bind(cfg_file):
    remote = TestClient(create_app(":memory:"), client=("203.0.113.9", 50000))
    resp = remote.post(
        "/api/connections", json={"kind": "mcp", "name": "x", "url": "http://a"}
    )
    assert resp.status_code == 403
