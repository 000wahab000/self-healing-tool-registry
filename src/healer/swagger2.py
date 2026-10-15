"""Convert a Swagger 2.0 document to the OpenAPI 3 shape `operations()` reads (F18, P3-3).

The registry and the healer only ever read `operations()`, so an API that publishes
Swagger 2.0 needs no healing changes: `convert` reshapes its document offline and
`swagger2_source` wraps that as a `SpecSource`.
"""

from __future__ import annotations

from typing import Any

import httpx

from healer.canonical import sha256
from healer.models import LoadedSpec, SpecSource
from healer.openapi_loader import operations, resolve_refs
from healer.settings import SPEC_FETCH_TIMEOUT_S

_JSON = "application/json"
_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
_REF = "#/definitions/"
_TARGET = "#/components/schemas/"
# A Swagger 2.0 non-body parameter carries its type keywords directly, not under `schema`.
_TYPE_KEYS = ("type", "format", "items")
_OTHER_KEYS = (
    "title",
    "pattern",
    "enum",
    "default",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "uniqueItems",
    "multipleOf",
)
_OAUTH_FLOWS = {
    "implicit": "implicit",
    "password": "password",
    "application": "clientCredentials",
    "accessCode": "authorizationCode",
}


def _rewrite_refs(node: Any) -> Any:
    """Deep copy `node`, pointing every local `#/definitions/...` ref at `components/schemas`."""

    if isinstance(node, list):
        return [_rewrite_refs(x) for x in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key == "$ref" and isinstance(value, str) and value.startswith(_REF):
            out[key] = _TARGET + value[len(_REF) :]
        else:
            out[key] = _rewrite_refs(value)
    return out


def _param_schema(param: dict) -> dict:
    """Lift a 2.0 non-body parameter's type keywords into the OpenAPI 3 `schema` object.

    2.0 has no `null` type, so an optional (not required) scalar is written the way the
    API publishes it in its OpenAPI 3 document: `anyOf [<type>, null]`.
    """
    typed = {key: param[key] for key in _TYPE_KEYS if key in param}
    rest = {key: param[key] for key in _OTHER_KEYS if key in param}
    if not typed:
        return rest
    if param.get("required", False):
        return {**typed, **rest}
    return {"anyOf": [typed, {"type": "null"}], **rest}


def _request_body(param: dict, consumes: list[str]) -> dict:
    media = consumes or [_JSON]
    return {
        "required": param.get("required", False),
        "content": {name: {"schema": param.get("schema", {})} for name in media},
    }


def _responses(responses: dict, produces: list[str]) -> dict:
    media = produces or [_JSON]
    out: dict[str, Any] = {}
    for code, response in responses.items():
        wrapped = {key: value for key, value in response.items() if key != "schema"}
        if "schema" in response:
            wrapped["content"] = {name: {"schema": response["schema"]} for name in media}
        out[str(code)] = wrapped
    return out


def _security_schemes(definitions: dict) -> dict:
    schemes: dict[str, Any] = {}
    for name, scheme in definitions.items():
        kind = scheme.get("type")
        if kind == "basic":
            schemes[name] = {"type": "http", "scheme": "basic"}
        elif kind == "apiKey":
            schemes[name] = {
                "type": "apiKey",
                "name": scheme["name"],
                "in": scheme["in"],
            }
        elif kind == "oauth2":
            flow = _OAUTH_FLOWS.get(scheme.get("flow", ""), scheme.get("flow", "implicit"))
            detail: dict[str, Any] = {"scopes": scheme.get("scopes", {})}
            for key in ("authorizationUrl", "tokenUrl"):
                if key in scheme:
                    detail[key] = scheme[key]
            schemes[name] = {"type": "oauth2", "flows": {flow: detail}}
        else:
            schemes[name] = dict(scheme)
    return schemes


def _operation(op: dict, consumes: list[str], produces: list[str]) -> dict:
    params: list[dict] = []
    body: dict | None = None
    for param in op.get("parameters", []):
        if param.get("in") == "body":
            body = param
        else:
            params.append(
                {
                    "name": param["name"],
                    "in": param["in"],
                    "required": param.get("required", False),
                    "schema": _param_schema(param),
                    "description": param.get("description", ""),
                }
            )
    out = {
        key: value
        for key, value in op.items()
        if key not in ("parameters", "responses", "consumes", "produces")
    }
    if params:
        out["parameters"] = params
    if body is not None:
        out["requestBody"] = _request_body(body, op.get("consumes", consumes))
    out["responses"] = _responses(op.get("responses", {}), op.get("produces", produces))
    return out


def convert(doc: dict) -> dict:
    """Reshape a Swagger 2.0 document into the OpenAPI 3 shape `operations()` reads.

    The input is never mutated. Raises `ValueError` when `doc` is not a Swagger 2.0
    document, so a malformed spec falls back to error-clue mode instead of loading empty.
    """
    try:
        paths = doc["paths"]
    except (KeyError, TypeError):
        raise ValueError("not a Swagger 2.0 document: missing `paths`") from None
    if not hasattr(paths, "items"):
        raise ValueError("not a Swagger 2.0 document: `paths` must be an object")
    source = _rewrite_refs(doc)
    consumes = source.get("consumes", [])
    produces = source.get("produces", [])
    out = {
        key: value
        for key, value in source.items()
        if key
        not in ("swagger", "definitions", "securityDefinitions", "consumes", "produces", "paths")
    }
    out["openapi"] = "3.1.0"
    out["paths"] = {
        path: {
            method: (
                _operation(op, consumes, produces) if method in _METHODS else op
            )
            for method, op in item.items()
        }
        for path, item in source["paths"].items()
    }
    components = dict(out.get("components", {}))
    if "definitions" in source:
        components["schemas"] = source["definitions"]
    if "securityDefinitions" in source:
        components["securitySchemes"] = _security_schemes(source["securityDefinitions"])
    if components:
        out["components"] = components
    return out


def swagger2_source(client: httpx.AsyncClient, path: str = "/swagger.json") -> SpecSource:
    """A `SpecSource` for an API that publishes a Swagger 2.0 document at `path`."""

    async def load() -> LoadedSpec:
        resp = await client.get(path, timeout=SPEC_FETCH_TIMEOUT_S)
        resp.raise_for_status()
        converted = convert(resp.json())
        resolved = resolve_refs(converted)
        return LoadedSpec(resolved, operations(resolved), sha256(converted))

    return load
