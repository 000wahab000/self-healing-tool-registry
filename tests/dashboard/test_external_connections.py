from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from dashboard.app import create_app


def test_ac_89_presets_are_versioned_suggestions_and_custom_is_optional() -> None:
    from healer.connection_presets import PRESETS

    assert set(PRESETS) == {"github@1", "notion@1"}
    assert all(p["version"] == 1 and p["source"] and p["verified_date"] for p in PRESETS.values())
    assert all("selected_operations" not in p for p in PRESETS.values())


def test_ac_90_authenticated_crud_preserves_secret_refs_and_stdio_readonly(
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
