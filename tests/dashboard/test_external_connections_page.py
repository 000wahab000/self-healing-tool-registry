from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from dashboard.app import create_app


def test_ac_108_presets_are_versioned_suggestions_and_custom_is_optional() -> None:
    from healer.connection_presets import PRESETS

    assert set(PRESETS) == {"github@1", "notion@1"}
    assert all(p["version"] == 1 and p["source"] and p["verified_date"] for p in PRESETS.values())
    assert all("selected_operations" not in p for p in PRESETS.values())


def test_ac_109_authenticated_crud_preserves_secret_refs_and_stdio_readonly(
    tmp_path: Path, monkeypatch,
) -> None:
    path = tmp_path / "connections.json"
    path.write_text(json.dumps({"servers": [{"name": "local", "transport": "stdio", "command": ["x"]}], "apis": [{"name": "crm", "kind": "openapi", "base_url": "https://api.example", "auth": {"type": "bearer", "token_env": "CRM_TOKEN"}}]}))
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(path))
    monkeypatch.setenv("CONNECTIONS_TOKEN", "test-token")
    client = TestClient(create_app(":memory:"), client=("203.0.113.8", 50000))
    auth = {"Authorization": "Bearer test-token"}
    assert client.get("/api/connections").status_code == 401
    assert client.get("/api/connections", headers=auth).status_code == 200
    assert client.delete("/api/connections/local", headers=auth).status_code == 403
    response = client.put("/api/connections/crm", headers=auth, json={"name": "crm", "selected_operations": []})
    assert response.json()["pending_restart"] is True
    assert json.loads(path.read_text())["apis"][0]["auth"] == {"type": "bearer", "token_env": "CRM_TOKEN"}
    assert client.put("/api/connections/crm", headers=auth, json={"name": "newname"}).status_code == 400
    assert client.delete("/api/connections/crm", headers=auth).json()["pending_restart"] is True


def _local_client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("MCP_SERVERS_CONFIG", str(tmp_path / "connections.json"))
    return TestClient(create_app(":memory:"), client=("127.0.0.1", 50000))


def test_ac_109_credential_env_names_cannot_name_healer_secrets(tmp_path: Path, monkeypatch) -> None:
    client = _local_client(tmp_path, monkeypatch)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-do-not-leak")
    api = {"name": "evil", "kind": "openapi", "base_url": "https://attacker.example"}
    for var in ("NVIDIA_API_KEY", "OPENROUTER_API_KEY", "CONNECTIONS_TOKEN", "OAUTH_BEARER", "API_OPENCODE_KEY"):
        for route in ("/api/connections/test", "/api/connections"):
            for auth in ({"auth": {"type": "bearer", "token_env": var}}, {"token_env": var}, {"secret_headers": {"X-K": var}}):
                r = client.post(route, json={**api, **auth})
                assert r.status_code == 400, (route, var, auth)
                assert "nvapi-do-not-leak" not in r.text and "own secrets" in r.json()["detail"]
    assert not (tmp_path / "connections.json").exists()


def test_ac_109_dashboard_credential_env_names_need_an_allowed_prefix(tmp_path: Path, monkeypatch) -> None:
    client = _local_client(tmp_path, monkeypatch)
    api = {"name": "crm", "kind": "openapi", "base_url": "https://api.example"}
    r = client.post("/api/connections", json={**api, "token_env": "HOME"})
    assert r.status_code == 400 and "must start with" in r.json()["detail"]
    ok = client.post("/api/connections", json={**api, "auth": {"type": "bearer", "token_env": "API_CRM_TOKEN"}})
    assert ok.status_code == 200
    monkeypatch.setenv("HEALER_CONNECTION_ENV_ALLOW", "ACME_,EXACT_NAME")
    other = {**api, "name": "other"}
    assert client.post("/api/connections", json={**other, "token_env": "API_X"}).status_code == 400
    assert client.post("/api/connections", json={**other, "token_env": "ACME_TOKEN"}).status_code == 200
    assert client.post("/api/connections", json={**api, "name": "third", "token_env": "EXACT_NAME"}).status_code == 200


def test_ac_109_legacy_file_env_names_survive_dashboard_edit(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "connections.json"
    path.write_text(json.dumps({"apis": [{"name": "crm", "kind": "openapi", "base_url": "https://api.example", "token_env": "CRM_TOKEN"}]}))
    client = _local_client(tmp_path, monkeypatch)
    r = client.put("/api/connections/crm", json={"selected_operations": ["a"]})
    assert r.status_code == 200 and json.loads(path.read_text())["apis"][0]["token_env"] == "CRM_TOKEN"
