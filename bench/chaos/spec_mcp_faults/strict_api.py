"""Strict mini REST API + its own (swappable) OpenAPI spec endpoint. No LLM.

  GET /widgets?q=..        (shape v1)   or  GET /widgets?query=.. (shape v2); the other form => 422
  GET /openapi.json        spec built from the current spec_kind, or forced status/raw text
  POST /__control          {"shape": "v1"|"v2", "spec_kind": "v1"|"v2"|"cyclic_v1"|"cyclic_v2",
                            "spec_status": 200|500|"hang", "spec_raw": str|null}
  GET /__state             counters
Every request is appended to --log (jsonl): the oracle for what the upstream actually received.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--log", required=True)
ap.add_argument("--shape", default="v1")
ap.add_argument("--spec-kind", default="v1")
A = ap.parse_args()
S = {"shape": A.shape, "spec_kind": A.spec_kind, "spec_status": 200, "spec_raw": None}
N = {"spec_fetches": 0, "ok": 0, "rejected": 0}


def log(row: dict) -> None:
    with open(A.log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts_ms": int(time.time() * 1000), **row}) + "\n")


def build_spec(kind: str) -> dict:
    param = "q" if kind.endswith("v1") else "query"
    spec = {
        "openapi": "3.0.3", "info": {"title": "Widgets", "version": "1"},
        "paths": {"/widgets": {"get": {"operationId": "searchWidgets", "parameters": [
            {"name": param, "in": "query", "required": True, "schema": {"type": "string"}}],
            "responses": {"200": {"description": "ok", "content": {"application/json": {"schema": {
                "type": "object", "properties": {"results": {"type": "array", "items": {"type": "object"}},
                                                 "received_query": {"type": "string"}}}}}}}}},
            "/health": {"get": {"operationId": "health", "responses": {"200": {"description": "ok", "content": {
                "application/json": {"schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}}}}}}}}},
    }
    if kind.startswith("cyclic"):
        spec["components"] = {"schemas": {"Widget": {"type": "object", "properties": {
            "id": {"type": "integer"}, "parent": {"$ref": "#/components/schemas/Widget"}}}}}
        spec["paths"]["/widgets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["properties"][
            "results"]["items"] = {"$ref": "#/components/schemas/Widget"}
    return spec


async def openapi(request: Request) -> Response:
    N["spec_fetches"] += 1
    log({"kind": "spec_fetch", "status": S["spec_status"], "spec_kind": S["spec_kind"]})
    if S["spec_status"] == "hang":
        await asyncio.sleep(30)
    if S["spec_status"] not in (200, "hang"):
        return Response("down", status_code=int(S["spec_status"]))
    if S["spec_raw"] is not None:
        return Response(S["spec_raw"], media_type="application/json")
    return JSONResponse(build_spec(S["spec_kind"]))


async def widgets(request: Request) -> Response:
    want = "q" if S["shape"] == "v1" else "query"
    qp = dict(request.query_params)
    if want not in qp:
        N["rejected"] += 1
        log({"kind": "req", "query": qp, "status": 422})
        return JSONResponse({"detail": [{"loc": ["query", want], "msg": "field required"}]}, status_code=422)
    N["ok"] += 1
    log({"kind": "req", "query": qp, "status": 200})
    return JSONResponse({"results": [{"id": 1}], "received_query": qp[want]})


async def health(request: Request) -> Response:
    return JSONResponse({"ok": True})


async def control(request: Request) -> Response:
    if request.method == "POST":
        S.update(await request.json())
    return JSONResponse({**S, **N})


app = Starlette(routes=[Route("/openapi.json", openapi), Route("/widgets", widgets), Route("/health", health),
                        Route("/__control", control, methods=["GET", "POST"])])
uvicorn.run(app, host="127.0.0.1", port=A.port, log_level="warning")
