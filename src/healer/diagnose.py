"""Spec diagnosis: flatten operations into leaves and diff them (FR-6.1, technical-approach 5.2)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from healer.canonical import dumps, sha256
from healer.models import Side

_TYPES = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "arr",
    "object": "obj",
    "null": "null",
}


def _unwrap(schema: dict) -> dict:
    """Optional[X] (anyOf/oneOf with a null member) -> X, keeping the outer keywords."""
    for key in ("anyOf", "oneOf"):
        members = [m for m in schema.get(key, ()) if m.get("type") != "null"]
        if members:
            # ponytail: a union of several non-null types is read as its first member.
            outer = {k: v for k, v in schema.items() if k != key}
            return _unwrap({**members[0], **outer})
    return schema


def _type(schema: dict) -> str:
    t = schema.get("type")
    if isinstance(t, list):  # OpenAPI 3.1 nullable form: ["string", "null"]
        t = next((x for x in t if x != "null"), "null")
    # ponytail: untyped schemas (enum/const only, {}) are read as "obj".
    return _TYPES.get(t, "obj")


def _leaf(path: list[str], type_: str, required: bool, description: str = "") -> dict:
    return {
        "path": path,
        "type": type_,
        "required": required,
        "description": description,
    }


def _leaves(schema: dict, path: list[str], required: bool) -> Iterator[dict]:
    """Scalar, array and free-form object leaves; `required` needs every ancestor required."""
    schema = _unwrap(schema)
    props = schema.get("properties")
    if props:
        needed = set(schema.get("required", ()))
        for name, sub in props.items():
            yield from _leaves(sub, [*path, name], required and name in needed)
    elif path:
        yield _leaf(path, _type(schema), required, schema.get("description", ""))


def _index(leaves: Iterable[dict]) -> dict[tuple, dict]:
    return {tuple(leaf["path"]): leaf for leaf in leaves}


def flatten_request(op: dict) -> dict[tuple, dict]:
    body = op["body_schema"]
    out = _index(_leaves(body, ["body"], True)) if body is not None else {}
    for p in op["params"]:
        if p["in"] not in ("query", "header"):
            continue
        name = p["name"].lower() if p["in"] == "header" else p["name"]
        out[(p["in"], name)] = _leaf(
            [p["in"], name],
            _type(_unwrap(p["schema"])),
            p["required"],
            p["description"],
        )
    if "bearer" in op["security"]:
        out[("header", "authorization")] = _leaf(
            ["header", "authorization"], "str", True
        )
    return out


def flatten_response(op: dict) -> dict[tuple, dict]:
    schema = op["response_schema"]
    return _index(_leaves(schema, [], True)) if schema is not None else {}


def _entry(change: str, side: Side, leaf: dict, **extra: str) -> dict:
    return {
        "change": change,
        "side": side,
        "path": leaf["path"],
        "type": leaf["type"],
        "required": leaf["required"],
        "description": leaf["description"],
        **extra,
    }


def _diff_leaves(side: Side, old: dict, new: dict) -> Iterator[dict]:
    for key in old.keys() - new.keys():
        yield _entry("removed", side, old[key])
    for key in new.keys() - old.keys():
        yield _entry("added", side, new[key])
    for key in old.keys() & new.keys():
        if old[key]["type"] != new[key]["type"]:
            yield _entry("type_changed", side, new[key], old_type=old[key]["type"])
        if old[key]["required"] != new[key]["required"]:
            yield _entry("required_changed", side, new[key])


def _order(entry: dict) -> tuple:
    path = () if entry["change"] == "route_changed" else tuple(entry["path"])
    return (entry["side"], path, entry["change"])


def diff(old_op: dict, new_op: dict) -> list[dict]:
    entries = [
        *_diff_leaves(Side.REQ, flatten_request(old_op), flatten_request(new_op)),
        *_diff_leaves(Side.RESP, flatten_response(old_op), flatten_response(new_op)),
    ]
    if (old_op["method"], old_op["path"]) != (new_op["method"], new_op["path"]):
        entries.append(
            {
                "change": "route_changed",
                "side": Side.REQ,
                "method": new_op["method"],
                "path": new_op["path"],
            }
        )
    return sorted(entries, key=_order)


def diff_signature(entries: list[dict]) -> str:
    return sha256([{k: v for k, v in e.items() if k != "description"} for e in entries])


def abstract_signature(ops: list[dict], entries: list[dict]) -> str:
    """FR-17.8: abstract structural signature with roles replacing concrete names."""
    removed = [tuple(e["path"]) for e in entries if e.get("change") == "removed"]
    added = [tuple(e["path"]) for e in entries if e.get("change") == "added"]

    from_roles = {p: f"$from_{i}" for i, p in enumerate(removed)}
    to_roles = {p: f"$to_{i}" for i, p in enumerate(added)}

    def abstract_path(path: list, roles: dict[tuple, str]) -> list:
        tp = tuple(path)
        if tp in roles:
            return [*path[:-1], roles[tp]]
        return path

    abstract_ops = []
    for op in ops:
        ab = dict(op)
        if "from" in ab:
            ab["from"] = abstract_path(ab["from"], from_roles)
        if "to" in ab:
            ab["to"] = abstract_path(ab["to"], to_roles)
        if "path" in ab:
            tp = tuple(ab["path"])
            roles = from_roles if tp in from_roles else to_roles
            ab["path"] = abstract_path(ab["path"], roles)
        abstract_ops.append(ab)

    return dumps(abstract_ops)


def route_exists(ops: dict[str, dict], method: str, path: str) -> bool:
    return any(
        o["method"] == method.upper() and o["path"] == path for o in ops.values()
    )
