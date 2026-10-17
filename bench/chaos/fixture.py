"""Fixture server: logging reverse proxy to an upstream + a swappable spec endpoint. No LLM.

  GET  /__spec.json   current spec document (file set via control)
  POST /__control     {"spec_file": path, "spec_status": 200|404|500|"hang", "spec_raw": "text"}
  anything else       forwarded to UPSTREAM; every request/response logged to LOG (jsonl)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--upstream", required=True)
ap.add_argument("--log", required=True)
ap.add_argument("--spec-file", required=True)
A = ap.parse_args()
state = {"spec_file": A.spec_file, "spec_status": 200, "spec_raw": None, "spec_fetches": 0}
client = httpx.AsyncClient(timeout=20)
HOP = {"host", "content-length", "connection", "keep-alive", "transfer-encoding", "accept-encoding"}
SENSITIVE = {"authorization", "x-api-key", "cookie", "api_key"}


def log(row: dict) -> None:
    with open(A.log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts_ms": int(time.time() * 1000), **row}, default=str) + "\n")


async def spec(request: Request) -> Response:
    state["spec_fetches"] += 1
    log({"kind": "spec_fetch", "file": state["spec_file"], "status": state["spec_status"]})
    if state["spec_status"] == "hang":
        await asyncio.sleep(30)
    if state["spec_status"] not in (200, "hang"):
        return Response("spec unavailable", status_code=int(state["spec_status"]))
    body = state["spec_raw"] if state["spec_raw"] is not None else Path(state["spec_file"]).read_text(encoding="utf-8")
    return Response(body, media_type="application/json")


async def control(request: Request) -> Response:
    body = await request.json() if request.method == "POST" else {}
    state.update({k: v for k, v in body.items() if k in state})
    if "spec_file" in body and "spec_raw" not in body:
        state["spec_raw"] = None
    return Response(json.dumps(state), media_type="application/json")


def _hdrs(request: Request) -> dict:
    return {k: ("<redacted>" if k.lower() in SENSITIVE else v) for k, v in request.headers.items()}


async def proxy(request: Request) -> Response:
    body = await request.body()
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP}
    url = A.upstream + request.url.path + (("?" + request.url.query) if request.url.query else "")
    t0 = time.time()
    base = {"kind": "req", "method": request.method, "path": request.url.path, "query": request.url.query,
            "headers": _hdrs(request), "body": body.decode("utf-8", "replace")[:2000]}
    try:
        r = await client.request(request.method, url, content=body, headers=headers)
    except httpx.HTTPError as e:
        log({**base, "status": 502, "error": str(e)})
        return Response("bad gateway", status_code=502)
    log({**base, "status": r.status_code, "resp": r.text[:1500], "ms": int((time.time() - t0) * 1000)})
    rh = {k: v for k, v in r.headers.items() if k.lower() not in HOP | {"content-encoding"}}
    return Response(r.content, status_code=r.status_code, headers=rh)


app = Starlette(routes=[
    Route("/__spec.json", spec),
    Route("/__control", control, methods=["GET", "POST"]),
    Route("/{path:path}", proxy, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]),
])
uvicorn.run(app, host="127.0.0.1", port=A.port, log_level="warning")
