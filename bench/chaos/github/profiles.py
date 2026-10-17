"""Drift profiles for the GitHub MCP chaos test.

A profile turns a tool's REAL inputSchema into the FALSE ("fake") schema the registry freezes,
and carries the inverse arg mapping the shim uses in fake mode (fake args -> real args) plus the
forward mapping the driver uses to write control calls (real args -> fake args).

Each profile is data: pure functions of (tool, value). No profile invents values.
`REAL_SCHEMAS` (tool -> real inputSchema) is filled by the shim / driver from the upstream's
real tools/list before any profile function that needs types or enums is called.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Schema = dict[str, Any]
Args = dict[str, Any]

REAL_SCHEMAS: dict[str, Schema] = {}


@dataclass(frozen=True)
class Profile:
    name: str
    schema: Callable[[str, Schema], Schema]  # real inputSchema -> fake inputSchema
    to_real: Callable[[str, Args], Args]  # fake args -> real args (shim, fake mode)
    to_fake: Callable[[str, Args], Args]  # real args -> fake args (driver control calls)


def _props(schema: Schema) -> dict[str, Any]:
    return schema.get("properties") or {}


def _prop_matches(tool: str, key: str, test: Callable[[Schema], bool]) -> bool:
    return test(_props(REAL_SCHEMAS.get(tool, {})).get(key, {}))


def rename(name: str, mapping: dict[str, str], only: set[str] | None = None) -> Profile:
    """Rename properties (real name -> fake name) on every tool that has them."""
    inverse = {v: k for k, v in mapping.items()}

    def applies(tool: str) -> bool:
        return only is None or tool in only

    def schema(tool: str, s: Schema) -> Schema:
        if not applies(tool):
            return s
        out = copy.deepcopy(s)
        out["properties"] = {mapping.get(k, k): v for k, v in _props(s).items()}
        if "required" in s:
            out["required"] = [mapping.get(k, k) for k in s["required"]]
        return out

    def to_real(tool: str, a: Args) -> Args:
        return {inverse.get(k, k): v for k, v in a.items()} if applies(tool) else a

    def to_fake(tool: str, a: Args) -> Args:
        return {mapping.get(k, k): v for k, v in a.items()} if applies(tool) else a

    return Profile(name, schema, to_real, to_fake)


def int_to_string() -> Profile:
    def schema(tool: str, s: Schema) -> Schema:
        out = copy.deepcopy(s)
        for p in _props(out).values():
            if p.get("type") == "integer":
                p["type"] = "string"
                p.pop("minimum", None)
                p.pop("maximum", None)
        return out

    def is_int(tool: str, key: str) -> bool:
        return _prop_matches(tool, key, lambda p: p.get("type") == "integer")

    def to_real(tool: str, a: Args) -> Args:
        return {
            k: int(v) if is_int(tool, k) and isinstance(v, str) and v.lstrip("-").isdigit() else v
            for k, v in a.items()
        }

    def to_fake(tool: str, a: Args) -> Args:
        return {k: str(v) if is_int(tool, k) and isinstance(v, int) else v for k, v in a.items()}

    return Profile("int_to_string", schema, to_real, to_fake)


def wrap() -> Profile:
    """All arguments wrapped under one object property `args`. Tools without properties untouched."""

    def schema(tool: str, s: Schema) -> Schema:
        if not _props(s):
            return s
        return {"type": "object", "properties": {"args": copy.deepcopy(s)}, "required": ["args"]}

    def to_real(tool: str, a: Args) -> Args:
        inner = a.get("args")
        return inner if isinstance(inner, dict) else a

    def to_fake(tool: str, a: Args) -> Args:
        return {"args": a} if _props(REAL_SCHEMAS.get(tool, {})) else a

    return Profile("wrap_args", schema, to_real, to_fake)


def nest_repo() -> Profile:
    """owner and repo nested under `repository`."""

    def schema(tool: str, s: Schema) -> Schema:
        p = _props(s)
        if "owner" not in p or "repo" not in p:
            return s
        out = copy.deepcopy(s)
        inner = {k: out["properties"].pop(k) for k in ("owner", "repo")}
        out["properties"]["repository"] = {
            "type": "object",
            "properties": inner,
            "required": ["owner", "repo"],
            "additionalProperties": False,
        }
        out["required"] = [r for r in out.get("required", []) if r not in inner] + ["repository"]
        return out

    def to_real(tool: str, a: Args) -> Args:
        if isinstance(a.get("repository"), dict):
            rest = {k: v for k, v in a.items() if k != "repository"}
            return {**a["repository"], **rest}
        return a

    def to_fake(tool: str, a: Args) -> Args:
        if "owner" in a and "repo" in a:
            rest = {k: v for k, v in a.items() if k not in ("owner", "repo")}
            return {"repository": {"owner": a["owner"], "repo": a["repo"]}, **rest}
        return a

    return Profile("nest_repo", schema, to_real, to_fake)


def enum_rename(name: str, mapping: dict[str, str]) -> Profile:
    """Rename the values of any enum whose real values are exactly mapping's keys."""
    inverse = {v: k for k, v in mapping.items()}

    def is_target(tool: str, key: str) -> bool:
        return _prop_matches(tool, key, lambda p: set(p.get("enum", [])) == set(mapping))

    def schema(tool: str, s: Schema) -> Schema:
        out = copy.deepcopy(s)
        for p in _props(out).values():
            if set(p.get("enum", [])) == set(mapping):
                p["enum"] = [mapping[v] for v in p["enum"]]
        return out

    def swap(tool: str, a: Args, table: dict[str, str]) -> Args:
        return {
            k: table.get(v, v) if isinstance(v, str) and is_target(tool, k) else v
            for k, v in a.items()
        }

    return Profile(
        name,
        schema,
        lambda t, a: swap(t, a, inverse),
        lambda t, a: swap(t, a, mapping),
    )


def merge_owner_repo() -> Profile:
    """owner + repo merged into one `repo_full_name` ("owner/repo")."""

    def schema(tool: str, s: Schema) -> Schema:
        p = _props(s)
        if "owner" not in p or "repo" not in p:
            return s
        out = copy.deepcopy(s)
        for k in ("owner", "repo"):
            out["properties"].pop(k)
        out["properties"]["repo_full_name"] = {
            "type": "string",
            "description": "Repository as owner/name",
        }
        out["required"] = [r for r in out.get("required", []) if r not in ("owner", "repo")] + [
            "repo_full_name"
        ]
        return out

    def to_real(tool: str, a: Args) -> Args:
        if "/" in str(a.get("repo_full_name", "")):
            owner, repo = str(a["repo_full_name"]).split("/", 1)
            rest = {k: v for k, v in a.items() if k != "repo_full_name"}
            return {"owner": owner, "repo": repo, **rest}
        return a

    def to_fake(tool: str, a: Args) -> Args:
        if "owner" in a and "repo" in a:
            rest = {k: v for k, v in a.items() if k not in ("owner", "repo")}
            return {"repo_full_name": f"{a['owner']}/{a['repo']}", **rest}
        return a

    return Profile("merge_owner_repo", schema, to_real, to_fake)


def decoy(name: str) -> Profile:
    """An optional boolean `include_details` the real tool does not have."""

    def schema(tool: str, s: Schema) -> Schema:
        out = copy.deepcopy(s)
        out["type"] = "object"
        out.setdefault("properties", {})["include_details"] = {
            "type": "boolean",
            "description": "Include extra details in the result.",
        }
        return out

    def to_real(tool: str, a: Args) -> Args:
        return {k: v for k, v in a.items() if k != "include_details"}

    return Profile(name, schema, to_real, lambda t, a: dict(a))


PROFILES: dict[str, Profile] = {
    p.name: p
    for p in (
        Profile("identity", lambda t, s: s, lambda t, a: a, lambda t, a: a),
        rename("rename_owner_repo", {"owner": "repo_owner", "repo": "repository"}),
        rename("rename_issue_number", {"issue_number": "number"}, only={"get_issue"}),
        int_to_string(),
        wrap(),
        nest_repo(),
        enum_rename("enum_case", {"OPEN": "open", "CLOSED": "closed"}),
        enum_rename("enum_synonym", {"OPEN": "opened", "CLOSED": "shut"}),
        merge_owner_repo(),
        decoy("decoy_unused"),
        decoy("decoy_used"),
    )
}


def get(name: str) -> Profile:
    return PROFILES[name]


def load_real_schemas(tools: list[dict]) -> None:
    """Fill REAL_SCHEMAS from an upstream tools/list result (list of tool dicts)."""
    REAL_SCHEMAS.clear()
    REAL_SCHEMAS.update({t["name"]: t.get("inputSchema") or {} for t in tools})
