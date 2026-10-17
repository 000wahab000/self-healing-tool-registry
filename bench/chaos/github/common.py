"""Shared helpers: JSONL logging and a local-only Streamable-HTTP MCP app."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

_lock = threading.Lock()


def log_jsonl(path: Path | str | None, row: dict[str, Any]) -> None:
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts_ms": int(time.time() * 1000), **row}
    with _lock, p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def local_http_app(server: Server, host: str = "127.0.0.1") -> Starlette:
    hosts = ["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"]
    return server.streamable_http_app(
        json_response=True,
        host=host,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=["http://127.0.0.1", "http://localhost"],
        ),
    )
