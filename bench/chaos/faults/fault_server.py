"""Tiny raw-asyncio HTTP fault server with its own OpenAPI spec. No LLM.

  GET  /openapi.json          spec (always fine)
  GET  /health                always 200 {"ok": true}
  GET  /items/{id}            fault-injected per current mode
  POST /items                 fault-injected; a "saved write" is counted when the body parsed and was stored
  POST /__mode  {name, ...}   set mode, reset counters;  GET /__state  counters;  GET /__log  request log
Every request is appended to --log (jsonl). Connection: close on every response.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from email.utils import formatdate

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--log", required=True)
A = ap.parse_args()

SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Fault API", "version": "1"},
    "paths": {
        "/items/{id}": {"get": {"operationId": "getItem", "parameters": [
            {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
            "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {
                "type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}}}}}}},
        "/items": {"post": {"operationId": "createItem", "requestBody": {"required": True, "content": {
            "application/json": {"schema": {"type": "object", "required": ["name"],
                                            "properties": {"name": {"type": "string"}}}}}},
            "responses": {"201": {"description": "created", "content": {"application/json": {"schema": {
                "type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}}}}}}}}},
        "/health": {"get": {"operationId": "health", "responses": {"200": {"description": "ok", "content": {
            "application/json": {"schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}}}}}}}},
    },
}
S = {"mode": {"name": "ok"}, "seen": 0, "faulted": 0, "saved": 0, "arrivals": []}


def log(row: dict) -> None:
    with open(A.log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts_ms": int(time.time() * 1000), "mono": time.monotonic(), **row}) + "\n")


def http(status: int, body: bytes | str, ctype="application/json", extra: dict | None = None) -> bytes:
    b = body.encode() if isinstance(body, str) else body
    head = {"Content-Type": ctype, "Content-Length": str(len(b)), "Connection": "close", **(extra or {})}
    reason = {200: "OK", 201: "Created", 429: "Too Many Requests", 500: "Internal Server Error",
              503: "Service Unavailable"}.get(status, "X")
    return (f"HTTP/1.1 {status} {reason}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in head.items()) + "\r\n").encode() + b


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        raw = await reader.readuntil(b"\r\n\r\n")
        lines = raw.decode("latin1").split("\r\n")
        method, target, _ = lines[0].split(" ", 2)
        hdr = {k.lower(): v.strip() for k, v in (x.split(":", 1) for x in lines[1:] if ":" in x)}
        body = await reader.readexactly(int(hdr.get("content-length", "0")))
        path = target.split("?")[0]
        if path == "/openapi.json":
            writer.write(http(200, json.dumps(SPEC)))
        elif path == "/health":
            log({"m": method, "p": path, "action": "health"})
            writer.write(http(200, '{"ok": true}'))
        elif path == "/__mode":
            S.update(mode=json.loads(body), seen=0, faulted=0, saved=0, arrivals=[])
            writer.write(http(200, json.dumps(S["mode"])))
        elif path == "/__state":
            writer.write(http(200, json.dumps({k: v for k, v in S.items() if k != "mode"} | {"mode": S["mode"]})))
        elif path.startswith("/items"):
            await fault(method, path, body, writer)
        else:
            writer.write(http(404, '{"error":"nope"}'))
        await writer.drain()
    except Exception as e:  # noqa: BLE001
        log({"error": repr(e)})
    finally:
        try:
            writer.close()
        except Exception:  # noqa: BLE001, S110
            pass


async def fault(method: str, path: str, body: bytes, writer: asyncio.StreamWriter) -> None:
    m = S["mode"]
    name = m.get("name", "ok")
    S["seen"] += 1
    S["arrivals"].append(round(time.monotonic(), 3))
    n = m.get("n", 0)
    active = name != "ok" and S["faulted"] < n
    good = json.dumps({"id": 1, "name": "widget"})
    is_write = method == "POST"
    if is_write:
        try:
            json.loads(body)
            if name == "save_then_fail" or not active:
                S["saved"] += 1  # the write is stored before any failure is returned
        except ValueError:
            pass
    log({"m": method, "p": path, "mode": name, "active": active, "n_seen": S["seen"], "saved": S["saved"]})
    if not active:
        writer.write(http(201 if is_write else 200, good))
        return
    S["faulted"] += 1
    if name == "fail_n" or name == "save_then_fail":
        extra = {}
        ra = m.get("retry_after")
        if ra:
            extra["Retry-After"] = formatdate(time.time() + 3, usegmt=True) if ra.startswith("date") else ra
        writer.write(http(m["status"], '{"error":"injected"}', extra=extra))
    elif name == "slow":
        await asyncio.sleep(m["seconds"])
        writer.write(http(200, good))
    elif name == "drop_mid":
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 4000\r\n\r\n{\"id\": 1, ")
        await writer.drain()
        writer.transport.abort()
    elif name == "bad_json":
        writer.write(http(200, "{not json"))
    elif name == "truncated":
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 4000\r\nConnection: close\r\n\r\n{\"id\": 1, \"na")
        await writer.drain()
        writer.close()
    elif name == "big":
        blob = json.dumps({"id": 1, "name": "x" * (m["mb"] * 1024 * 1024)})
        writer.write(http(200, blob))
    else:
        writer.write(http(500, "unknown mode"))


async def main() -> None:
    srv = await asyncio.start_server(handle, "127.0.0.1", A.port)
    async with srv:
        await srv.serve_forever()


asyncio.run(main())
