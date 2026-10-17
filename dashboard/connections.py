"""Connections page backend: add, list, remove and test upstream MCP servers and third-party APIs.

These routes write config and make outbound requests, so: http/https URLs only, no stdio or command
fields, the config path comes from the environment (never the request), and when the dashboard is
bound to a non-local host every write/test call needs `Authorization: Bearer $CONNECTIONS_TOKEN`.
"""

from __future__ import annotations

import hmac
import json
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from healer import gateway
from healer.connection_presets import PRESETS

HERE = Path(__file__).parent
router = APIRouter()


def config_path(request: Request | None = None) -> Path:
    if request is not None:
        path = getattr(request.app.state.dash, "upstream_config_path", None)
        if path is not None:
            return Path(path)
    return Path(os.environ.get("MCP_SERVERS_CONFIG") or "config/mcp_servers.json")


def is_remote(request: Request) -> bool:
    """Local = the browser runs on this machine and no proxy forwarded the request. The bind
    address does not matter: a hosted or proxied dashboard always needs the token."""
    client = request.client.host if request.client else ""
    forwarded = "x-forwarded-for" in request.headers or "forwarded" in request.headers
    return forwarded or client not in ("127.0.0.1", "::1")


def require_write(request: Request) -> None:
    if not is_remote(request):
        return
    expected = os.environ.get("CONNECTIONS_TOKEN")
    if not expected:
        raise HTTPException(403, "CONNECTIONS_TOKEN is not set on the server")
    given = request.headers.get("authorization", "")
    if not hmac.compare_digest(given.encode(), f"Bearer {expected}".encode()):
        raise HTTPException(401, "missing or wrong connections token")


def read_saved_config(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    data.setdefault("servers", [])
    data.setdefault("apis", [])
    return data


def _load(request: Request | None = None) -> dict:
    return read_saved_config(config_path(request))


def _save(data: dict, request: Request | None = None) -> None:
    path = config_path(request)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".mcp_servers-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def clean_entry(body: object, existing: dict | None = None) -> dict:
    """Validate a dashboard-submitted entry (http only) and drop blank optional fields."""
    if not isinstance(body, dict):
        raise HTTPException(400, "entry must be an object")
    entry = {k: v for k, v in body.items() if v not in (None, "")}
    try:
        return gateway.validate_entry(entry, http_only=True, existing=existing)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def _view_server(s: dict) -> dict:
    http = s.get("transport") == "http"
    return {
        "name": s["name"],
        "transport": s.get("transport"),
        "url": s.get("url") if http else None,
        "token_env": s.get("token_env"),
        **{k: s[k] for k in ("auth", "headers", "secret_headers", "selected_operations", "preset") if k in s},
        "readonly": not http,
    }


def _runtime_status(entry: dict, collection: str, request: Request) -> str:
    active_config = getattr(request.app.state, "connection_startup_config", None)
    if active_config is None:
        return "unknown"
    return "active" if entry in active_config.get(collection, []) else "pending"


@router.get("/connections", include_in_schema=False)
async def page() -> FileResponse:
    return FileResponse(
        HERE / "connections.html", headers={"Cache-Control": "no-cache"}
    )


@router.get("/api/connections", dependencies=[Depends(require_write)])
async def list_connections(request: Request) -> dict:
    data = _load(request)
    return {
        "servers": [
            {**_view_server(s), "runtime_status": _runtime_status(s, "servers", request)}
            for s in data["servers"]
        ],
        "apis": [
            {
                k: a.get(k)
                for k in ("name", "kind", "base_url", "spec_path", "spec_url", "token_env", "auth", "spec_auth", "spec_reuse_api_auth", "headers", "secret_headers", "selected_operations", "preset")
            } | {"runtime_status": _runtime_status(a, "apis", request)}
            for a in data["apis"]
        ],
        "auth_required": is_remote(request),
        "defaults": {k: v[0] for k, v in gateway.API_KINDS.items()},
        "presets": PRESETS,
    }


@router.post("/api/connections", dependencies=[Depends(require_write)])
async def add_connection(body: dict, request: Request) -> dict:
    entry = clean_entry(body)
    data = _load(request)
    if any(e["name"] == entry["name"] for e in data["servers"] + data["apis"]):
        raise HTTPException(409, "name already in use")
    data["apis" if "kind" in entry else "servers"].append(entry)
    _save(data, request)
    return {"ok": True, "name": entry["name"], "pending_restart": True}


@router.put("/api/connections/{name}", dependencies=[Depends(require_write)])
async def update_connection(name: str, body: dict, request: Request) -> dict:
    data = _load(request)
    for collection in ("servers", "apis"):
        for index, existing in enumerate(data[collection]):
            if existing["name"] != name:
                continue
            if existing.get("transport") == "stdio":
                raise HTTPException(403, "stdio connections are file-only")
            if body.get("name", name) != name or body.get("kind", existing.get("kind")) != existing.get("kind") or body.get("transport", existing.get("transport")) != existing.get("transport"):
                raise HTTPException(400, "connection name and type cannot change")
            merged = {**existing, **{k: v for k, v in body.items() if v is not None}}
            # Blank secret references mean preserve; only explicit clear_secret_refs removes them.
            if not body.get("clear_secret_refs"):
                for key in ("auth", "spec_auth", "token_env", "secret_headers"):
                    if not body.get(key):
                        merged[key] = existing.get(key)
                if isinstance(body.get("secret_headers"), dict):
                    merged["secret_headers"] = {**existing.get("secret_headers", {}), **body["secret_headers"]}
            merged.pop("clear_secret_refs", None)
            data[collection][index] = clean_entry(merged, existing)
            _save(data, request)
            return {"ok": True, "name": name, "pending_restart": True}
    raise HTTPException(404, "no such connection")


@router.delete("/api/connections/{name}", dependencies=[Depends(require_write)])
async def remove_connection(name: str, request: Request) -> dict:
    data = _load(request)
    for key in ("servers", "apis"):
        if key == "servers" and any(
            server["name"] == name and server.get("transport") == "stdio"
            for server in data[key]
        ):
            raise HTTPException(403, "stdio connections are file-only")
        kept = [e for e in data[key] if e["name"] != name]
        if len(kept) != len(data[key]):
            data[key] = kept
            _save(data, request)
            return {"ok": True, "pending_restart": True}
    raise HTTPException(404, "no such connection")


@router.post("/api/connections/test", dependencies=[Depends(require_write)])
async def test_connection(body: dict) -> dict:
    return await gateway.probe(clean_entry(body))
