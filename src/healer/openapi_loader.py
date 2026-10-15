"""Fetch an OpenAPI 3.x spec, inline its local $refs, and index its operations."""

from __future__ import annotations

import re
from typing import Any

import httpx

from healer.canonical import sha256
from healer.models import LoadedSpec, OperationSpec, SpecSource
from healer.settings import SPEC_FETCH_TIMEOUT_S

_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_JSON = "application/json"
_SUCCESS = re.compile(r"2(\d\d|XX)")


def resolve_refs(spec: dict) -> dict:
    """Inline every local `#/...` ref; keywords next to a $ref override the target's."""

    def walk(node: Any, seen: tuple[str, ...]) -> Any:
        if isinstance(node, list):
            return [walk(x, seen) for x in node]
        if not isinstance(node, dict):
            return node
        ref = node.get("$ref")
        if not (isinstance(ref, str) and ref.startswith("#/")):
            return {k: walk(v, seen) for k, v in node.items()}
        if ref in seen:
            return {}  # ponytail: a cyclic schema is cut to "anything" at the second visit
        target: Any = spec
        try:
            for part in ref[2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError):
            raise ValueError(f"unresolvable ref {ref}") from None
        siblings = {k: walk(v, seen) for k, v in node.items() if k != "$ref"}
        return {**walk(target, (*seen, ref)), **siblings}

    return walk(spec, ())


async def fetch_spec(
    client: httpx.AsyncClient,
    path: str = "/openapi.json",
    timeout: float = SPEC_FETCH_TIMEOUT_S,
) -> tuple[dict, str]:
    resp = await client.get(path, timeout=timeout)
    resp.raise_for_status()
    raw = resp.json()
    return resolve_refs(raw), sha256(raw)


def _is_bearer(scheme: dict) -> bool:
    return scheme.get("type") == "oauth2" or (
        scheme.get("type") == "http" and scheme.get("scheme", "").lower() == "bearer"
    )


def _security(spec: dict, op: dict) -> list[str]:
    # ponytail: only bearer-style schemes are mapped (http bearer, oauth2); apiKey/basic are not.
    schemes = spec.get("components", {}).get("securitySchemes", {})
    required = op.get("security", spec.get("security", []))
    bearer = any(_is_bearer(schemes.get(name, {})) for req in required for name in req)
    return ["bearer"] if bearer else []


def _json_schema(content: dict) -> dict | None:
    return content.get("content", {}).get(_JSON, {}).get("schema")


def _response_schema(op: dict) -> dict | None:
    responses = op.get("responses", {})
    for code in sorted(str(c) for c in responses):
        if _SUCCESS.fullmatch(code):
            schema = _json_schema(responses[code])
            if schema is not None:
                return schema
    return None


def operations(resolved_spec: dict) -> dict[str, OperationSpec]:
    out: dict[str, OperationSpec] = {}
    for path, item in resolved_spec.get("paths", {}).items():
        for method in _METHODS:
            op = item.get(method)
            if not op or "operationId" not in op:
                continue
            out[op["operationId"]] = {
                "operation_id": op["operationId"],
                "method": method.upper(),
                "path": path,
                "body_schema": _json_schema(op.get("requestBody", {})),
                "params": [
                    {
                        "name": p["name"],
                        "in": p["in"],
                        "required": p.get("required", False),
                        "schema": p.get("schema", {}),
                        "description": p.get("description", ""),
                    }
                    for p in op.get("parameters", [])
                ],
                "security": _security(resolved_spec, op),
                "response_schema": _response_schema(op),
                "description": op.get("description") or op.get("summary", ""),
            }
    return out


def openapi_source(
    client: httpx.AsyncClient, path: str = "/openapi.json"
) -> SpecSource:
    """The default `SpecSource`: the API's OpenAPI 3 document at `path`."""

    async def load() -> LoadedSpec:
        spec, spec_hash = await fetch_spec(client, path)
        return LoadedSpec(spec, operations(spec), spec_hash)

    return load
