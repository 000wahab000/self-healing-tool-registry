"""Filter a loaded REST spec to explicitly selected, safely representable operations."""

from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy

from healer.models import LoadedSpec

_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
_READ_ONLY = {"get", "head"}
SELECT_ALL = "*"
_SCALARS = {"string", "integer", "number", "boolean"}
_PATH_PARAM = re.compile(r"\{([^{}]+)\}")


def discover(
    spec: LoadedSpec, entry: dict, configured_headers: set[str]
) -> tuple[LoadedSpec, list[dict]]:
    """Select compatible operations; entry selection contains unnamespaced operation IDs."""
    prefix = f"{entry['name']}__"
    selected = entry.get("selected_operations")
    diagnostics: list[dict] = []
    occurrences: Counter[str] = Counter()
    candidates: dict[str, tuple[str, dict]] = {}
    methods: dict[str, str] = {}
    for path, path_item in spec.raw.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in _METHODS or not isinstance(operation, dict):
                continue
            raw_id = operation.get("operationId")
            if not isinstance(raw_id, str) or not raw_id:
                diagnostics.append({"operation": None, "code": "MISSING_OPERATION_ID"})
                continue
            occurrences[raw_id] += 1
            candidates[raw_id] = (path, operation)
            methods[raw_id] = method.lower()
    for raw_id in sorted(occurrences):
        if occurrences[raw_id] > 1:
            diagnostics.append({"operation": raw_id, "code": "DUPLICATE_OPERATION_ID"})

    # FR-25.3: with no selection only read-only methods are exposed; writes need an explicit
    # list of operation IDs, or the explicit opt-in `selected_operations: "*"` (everything).
    if isinstance(selected, list):
        chosen = sorted({item for item in selected if isinstance(item, str)})
    elif selected == SELECT_ALL:
        chosen = sorted(candidates)
    else:
        chosen = sorted(i for i in candidates if methods[i] in _READ_ONLY)
    if isinstance(selected, list) and any(not isinstance(item, str) for item in selected):
        diagnostics.append({"operation": None, "code": "INVALID_SELECTED_OPERATION"})
    ops = {}
    for raw_id in chosen:
        if not isinstance(raw_id, str) or raw_id not in candidates:
            diagnostics.append({"operation": raw_id, "code": "UNKNOWN_OPERATION"})
            continue
        if occurrences[raw_id] != 1:
            continue
        path, raw_op = candidates[raw_id]
        op = spec.ops.get(prefix + raw_id)
        if op is None:
            diagnostics.append({"operation": raw_id, "code": "OPERATION_UNAVAILABLE"})
            continue
        code = _incompatibility(spec.raw, path, raw_op, entry, configured_headers)
        if code:
            diagnostics.append({"operation": raw_id, "code": code})
        else:
            ops[prefix + raw_id] = op
    return LoadedSpec(deepcopy(spec.raw), ops, spec.spec_hash), diagnostics


def _incompatibility(
    raw: dict, path: str, operation: dict, entry: dict, headers: set[str]
) -> str | None:
    path_item = raw.get("paths", {}).get(path, {})

    def has_external_ref(value: object) -> bool:
        if isinstance(value, dict):
            return any(
                (key == "$ref" and isinstance(child, str) and not child.startswith("#/"))
                or has_external_ref(child)
                for key, child in value.items()
            )
        return isinstance(value, list) and any(has_external_ref(item) for item in value)

    if has_external_ref(operation) or has_external_ref(path_item.get("parameters", [])):
        return "EXTERNAL_REF"

    body = operation.get("requestBody", {})
    content = body.get("content", {})
    if content and "application/json" not in content:
        return "UNSUPPORTED_MEDIA_TYPE"
    body_schema = content.get("application/json", {}).get("schema", {})
    if content and body_schema.get("type") != "object":
        return "UNSUPPORTED_BODY_SCHEMA"
    body_names = set(body_schema.get("properties", {}))

    path_params = path_item.get("parameters", [])
    op_params = operation.get("parameters", [])
    if _duplicate_params(path_params) or _duplicate_params(op_params):
        return "AMBIGUOUS_PARAMETER"
    effective = {(p.get("in"), p.get("name")): p for p in path_params}
    effective.update({(p.get("in"), p.get("name")): p for p in op_params})
    params = list(effective.values())
    seen_names: set[str] = set()
    declared_path: set[str] = set()
    for param in params:
        location, name = param.get("in"), param.get("name")
        if not isinstance(name, str) or name in seen_names:
            return "AMBIGUOUS_PARAMETER"
        seen_names.add(name)
        if location not in {"path", "query", "header"}:
            return "UNSUPPORTED_PARAMETER_LOCATION"
        if name in body_names and location in {"path", "query"}:
            return "AMBIGUOUS_PARAMETER"
        if "content" in param:
            return "UNSUPPORTED_PARAMETER_SERIALIZATION"
        schema = param.get("schema", {})
        if location == "query" and (schema.get("type") == "array" or "items" in schema):
            return "UNSUPPORTED_QUERY_SERIALIZATION"
        if schema.get("type") not in _SCALARS:
            return "UNSUPPORTED_PARAMETER_SCHEMA"
        if location == "path":
            declared_path.add(name)
            if not param.get("required") or param.get("style", "simple") != "simple" or param.get("explode", False):
                return "UNSUPPORTED_PATH_SERIALIZATION"
        elif location == "query":
            if param.get("style", "form") != "form" or param.get("explode", True) is not True:
                return "UNSUPPORTED_QUERY_SERIALIZATION"
        elif param.get("required") and name.casefold() not in {h.casefold() for h in headers}:
            return "MISSING_CONFIGURED_HEADER"
    placeholders = _PATH_PARAM.findall(path)
    if len(placeholders) != len(set(placeholders)) or set(placeholders) != declared_path:
        return "PATH_PARAMETER_MISMATCH"

    schemes = raw.get("components", {}).get("securitySchemes", {})
    alternatives = operation.get("security", raw.get("security", []))
    if alternatives is None:
        alternatives = []
    if alternatives and not any(
        all(_scheme_satisfied(schemes.get(name, {}), entry, headers) for name in requirement)
        for requirement in alternatives
    ):
        return "UNSUPPORTED_SECURITY"
    return None


def _duplicate_params(parameters: list[dict]) -> bool:
    keys = [(param.get("in"), param.get("name")) for param in parameters]
    return len(keys) != len(set(keys))


def _scheme_satisfied(scheme: dict, entry: dict, headers: set[str]) -> bool:
    kind = scheme.get("type")
    profile = entry.get("auth") or ({"type": "bearer"} if entry.get("token_env") else {})
    if kind == "http" and scheme.get("scheme", "").lower() in {"bearer", "basic"}:
        expected = "bearer" if scheme.get("scheme", "").lower() == "bearer" else "basic"
        return profile.get("type") == expected and "authorization" in {h.casefold() for h in headers}
    return (
        kind == "apiKey"
        and scheme.get("in") == "header"
        and scheme.get("name", "").casefold() in {h.casefold() for h in headers}
    )
