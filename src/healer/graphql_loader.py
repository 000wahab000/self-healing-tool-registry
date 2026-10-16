"""Load GraphQL operations from an endpoint's standard introspection result."""

from __future__ import annotations

import httpx

from healer.canonical import sha256
from healer.models import LoadedSpec, OperationSpec, SpecSource
from healer.settings import SPEC_FETCH_TIMEOUT_S

_INTROSPECTION = """query IntrospectionQuery { __schema { queryType { name } mutationType { name } types { kind name enumValues { name } fields { name description args { name description type { kind name ofType { kind name ofType { kind name } } } } type { kind name ofType { kind name ofType { kind name } } } } inputFields { name description type { kind name ofType { kind name ofType { kind name } } } } } } }"""


def _type_ref(ref: dict) -> dict:
    while ref.get("kind") in ("NON_NULL", "LIST"):
        ref = ref.get("ofType") or {}
    return ref


def _schema(ref: dict, types: dict[str, dict], seen: frozenset[str] = frozenset()) -> dict:
    kind, name = ref.get("kind"), ref.get("name")
    if kind in ("NON_NULL", "LIST"):
        return _schema(ref.get("ofType") or {}, types, seen)
    if kind == "SCALAR":
        scalar_types = {"String": "string", "ID": "string", "Int": "integer", "Float": "number", "Boolean": "boolean"}
        if name not in scalar_types:
            raise ValueError("unsupported GraphQL scalar")
        return {"type": scalar_types[name]}
    if kind == "ENUM":
        return {"type": "string", "enum": [v["name"] for v in types.get(name, {}).get("enumValues", [])]}
    if kind == "INPUT_OBJECT" and name not in seen:
        item = types.get(name, {})
        props = {f["name"]: _schema(f["type"], types, seen | {name}) for f in item.get("inputFields", [])}
        required = [f["name"] for f in item.get("inputFields", []) if f["type"].get("kind") == "NON_NULL"]
        return {"type": "object", "properties": props, "required": required, "additionalProperties": False}
    if kind == "OBJECT" and name not in seen:
        item = types.get(name, {})
        props = {f["name"]: _schema(f["type"], types, seen | {name}) for f in item.get("fields", []) if not f["name"].startswith("__")}
        return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
    return {}


def operations(raw: dict) -> dict[str, OperationSpec]:
    schema = raw.get("data", {}).get("__schema", {})
    types = {t["name"]: t for t in schema.get("types", []) if t.get("name")}
    out: dict[str, OperationSpec] = {}
    for root_name, method in (("queryType", "QUERY"), ("mutationType", "MUTATION")):
        root = types.get((schema.get(root_name) or {}).get("name"), {})
        for field in root.get("fields", []):
            args = field.get("args", [])
            properties = {a["name"]: _schema(a["type"], types) for a in args}
            required = [a["name"] for a in args if a["type"].get("kind") == "NON_NULL"]
            out[field["name"]] = {
                "operation_id": field["name"], "method": "GRAPHQL", "path": "/graphql",
                "body_schema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
                "params": [], "security": [], "response_schema": _schema(field["type"], types),
                "description": field.get("description") or "",
            }
    return out


def graphql_source(client: httpx.AsyncClient, path: str = "/graphql", timeout: float = SPEC_FETCH_TIMEOUT_S) -> SpecSource:
    async def load() -> LoadedSpec:
        response = await client.post(path, json={"query": _INTROSPECTION}, timeout=timeout)
        response.raise_for_status()
        raw = response.json()
        if raw.get("errors") or "__schema" not in raw.get("data", {}):
            raise ValueError("GraphQL introspection unavailable")
        return LoadedSpec(raw, operations(raw), sha256(raw))

    return load
