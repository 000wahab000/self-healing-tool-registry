"""Candidate Builder (FR-7): diff entries or error clues in, candidate fix op lists out."""

from __future__ import annotations

import copy
import re
from collections.abc import Iterable, Iterator, Mapping

from healer.canonical import get
from healer.diagnose import flatten_response
from healer.models import Reason, Side, Violation
from healer.ops import OpError, apply_ops
from healer.settings import MAX_CANDIDATES

_SPLIT = re.compile(r"[_\-]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SCALARS = {"int", "str", "float", "bool"}
_PY_TYPES = {
    bool: "bool",
    int: "int",
    float: "float",
    str: "str",
    list: "arr",
    dict: "obj",
    type(None): "null",
}
_TYPE_KINDS = {
    "int_type": "int",
    "string_type": "str",
    "float_type": "float",
    "bool_type": "bool",
}
Option = tuple[list[dict], list[dict]]  # (request_ops, response_ops)


def _tokens(path: list) -> set[str]:
    return {t.lower() for t in _SPLIT.split(str(path[-1])) if t}


def _has(doc: dict, path: list) -> bool:
    try:
        get(doc, path)
    except KeyError:
        return False
    return True


def _move(src: list, dst: list) -> dict:
    return {"op": "move", "from": src, "to": dst}


def _cast(path: list, to: str) -> dict:
    return {"op": "cast", "path": path, "to": to}


def _dry_run(ops: list[dict], doc: dict, cfg_keys: Iterable[str] = ()) -> bool:
    """Lossless casts and path conflicts are decided by the interpreter itself."""
    try:
        apply_ops(ops, doc, dict.fromkeys(cfg_keys, ""))
    except OpError:
        return False
    return True


def _header_op(
    name: str, header_sources: Mapping[str, str], cfg_keys: set[str]
) -> dict | None:
    for key, cfg_key in header_sources.items():
        if key.lower() == name.lower() and cfg_key in cfg_keys:
            return {
                "op": "header",
                "name": key,
                "src": {"ref": "config", "key": cfg_key},
            }
    return None


def _fill_ops(src: dict, dst: dict) -> list[dict]:
    ops = [_move(src["path"], dst["path"])]
    if src["type"] != dst["type"]:
        ops.append(_cast(dst["path"], dst["type"]))
    return ops


def _evidence(src: dict, dst: dict, gone: list[dict], new: list[dict]) -> bool:
    """A shared name token, or the only removed and the only added leaf in that location."""
    if _tokens(src["path"]) & _tokens(dst["path"]):
        return True
    loc = src["path"][0]
    return (
        dst["path"][0] == loc
        and sum(g["path"][0] == loc for g in gone) == 1
        and sum(n["path"][0] == loc for n in new) == 1
    )


def _assign(
    targets: list[tuple[dict, list[dict], bool]], used: frozenset = frozenset()
) -> Iterator[list[tuple[dict, dict]]]:
    """Every one-to-one source assignment, lexicographic. Targets are (leaf, options, required);
    an optional target with no free option is skipped, a required one kills the branch."""
    if not targets:
        yield []
        return
    (target, options, required), rest = targets[0], targets[1:]
    free = [s for s in options if tuple(s["path"]) not in used]
    if not free and not required:
        yield from _assign(rest, used)
    for src in free:
        for tail in _assign(rest, used | {tuple(src["path"])}):
            yield [(target, src), *tail]


def _finish(
    options: Iterable[Option],
    base_doc: dict,
    cfg_keys: Iterable[str],
    response_data: dict | None = None,
) -> tuple[list[dict], Reason | None]:
    out: list[dict] = []
    dropped = False
    for request_ops, response_ops in options:
        if _dry_run(request_ops, base_doc, cfg_keys) and (
            response_data is None or _dry_run(response_ops, response_data)
        ):
            # Fresh copies: candidates must not share ops with each other or with the input.
            out.append(
                copy.deepcopy(
                    {"request_ops": request_ops, "response_ops": response_ops}
                )
            )
            if len(out) == MAX_CANDIDATES:
                break
        else:
            dropped = True
    if out:
        return out, None
    return [], Reason.UNSAFE_PATCH if dropped else Reason.NO_SAFE_VALUE


def _response_ops(entries: list[dict]) -> list[dict]:
    removed = [e for e in entries if e["change"] == "removed"]
    added = [e for e in entries if e["change"] == "added"]
    ops: list[dict] = []
    for r in removed:
        seg = r["path"][-1]
        twins = [x for x in removed if x["path"][-1] == seg]
        found = [a for a in added if a["path"][-1] == seg]
        if len(twins) != 1 or len(found) != 1:
            continue  # ambiguous: never guess which leaf is the agent's value
        (a,) = found
        if a["type"] == r["type"]:
            ops.append(_move(a["path"], r["path"]))
        elif a["type"] in _SCALARS and r["type"] in _SCALARS:
            ops += [_move(a["path"], r["path"]), _cast(r["path"], r["type"])]
    for e in entries:
        if (
            e["change"] == "type_changed"
            and e["type"] in _SCALARS
            and e["old_type"] in _SCALARS
        ):
            ops.append(_cast(e["path"], e["old_type"]))
    return ops


def build(
    entries: list[dict],
    base_doc: dict,
    header_sources: Mapping[str, str],
    cfg_keys: set[str],
) -> tuple[list[dict], Reason | None]:
    req = [e for e in entries if e["side"] == Side.REQ]
    gone = [e for e in req if e["change"] == "removed"]
    new = [e for e in req if e["change"] == "added"]
    sources = [e for e in gone if _has(base_doc, e["path"])]

    lead = [
        {"op": "route", "method": e["method"], "path": e["path"]}
        for e in req
        if e["change"] == "route_changed"
    ] + [
        _cast(e["path"], e["type"])
        for e in req
        if e["change"] == "type_changed" and _has(base_doc, e["path"])
    ]
    headers = []
    for e in new:
        if e["path"][0] == "header" and e["required"]:
            op = _header_op(e["path"][1], header_sources, cfg_keys)
            if op is None:
                return [], Reason.NO_SAFE_VALUE
            headers.append(op)

    targets: list[tuple[dict, list[dict], bool]] = []
    for t in new:
        if t["path"][0] not in ("body", "query"):
            continue
        usable = [s for s in sources if _dry_run(_fill_ops(s, t), base_doc)]
        named = [s for s in usable if _evidence(s, t, gone, new)]
        if t["required"]:
            if not usable:
                return [], Reason.NO_SAFE_VALUE
            targets.append((t, named or usable, True))
        elif named:
            targets.append((t, named, False))
    targets.sort(key=lambda x: not x[2])  # required leaves claim sources first

    response_ops = _response_ops([e for e in entries if e["side"] == Side.RESP])
    if not (lead or headers or targets or response_ops):
        return [], Reason.NO_CANDIDATE
    options = (
        (
            [*lead, *(op for t, s in pairs for op in _fill_ops(s, t)), *headers],
            response_ops,
        )
        for pairs in _assign(targets)
    )
    return _finish(options, base_doc, cfg_keys)


def _paths(doc: dict, prefix: list[str]) -> Iterator[list[str]]:
    for key, value in doc.items():
        if isinstance(value, dict):
            yield from _paths(value, [*prefix, key])
        else:
            yield [*prefix, key]


def _clue_response_ops(
    items: list[tuple[list, str]], data: dict, expected_schema: dict | None
) -> list[dict] | None:
    expected = (
        flatten_response({"response_schema": expected_schema})
        if expected_schema is not None
        else {}
    )
    leaves = list(_paths(data, []))
    ops: list[dict] = []
    for path, kind in items:
        if kind == "missing":
            found = [p for p in leaves if p[-1] == path[-1] and p != path]
            if len(found) != 1:
                return None
            ops.append(_move(found[0], path))
            value = get(data, found[0])
        elif _has(data, path):
            value = get(data, path)
        else:
            return None
        want = expected.get(tuple(path), {}).get("type")
        if want is not None and _PY_TYPES[type(value)] != want:
            ops.append(_cast(path, want))
        elif kind == "type":
            return None
    return ops


def _clue_fills(missing: list[list], base_doc: dict) -> Iterator[Option]:
    args = [
        {"path": p}
        for loc in ("body", "query")
        for p in sorted(_paths(base_doc.get(loc, {}), [loc]))
    ]
    targets = []
    for path in missing:
        named = [a for a in args if _tokens(a["path"]) & _tokens(path)]
        # ponytail: a lone argument is assumed to be the renamed one; the replay's
        # verification catches a wrong guess.
        if not named and len(args) == 1:
            named = args
        if not named:
            return
        targets.append(({"path": path}, named, True))
    for pairs in _assign(targets):
        yield [_move(s["path"], t["path"]) for t, s in pairs], []


def from_violations(
    violations: list[Violation],
    base_doc: dict,
    header_sources: Mapping[str, str],
    cfg_keys: set[str],
    response_data: dict | None = None,
    expected_schema: dict | None = None,
) -> tuple[list[dict], Reason | None]:
    """Error-clue mode: no spec, so only flat single-family fixes (technical-approach 5.4)."""
    groups: dict[str, list] = {"fill": [], "cast": [], "header": [], "resp": []}
    for v in violations:
        path, area = list(v.path), list(v.path[:1])
        flat = v.side == Side.REQ and len(path) > 1 and area in (["body"], ["query"])
        if v.side == Side.RESP and v.kind in ("missing", "type"):
            groups["resp"].append((path, v.kind))
        elif flat and v.kind == "missing":
            groups["fill"].append(path)
        elif flat and v.kind in _TYPE_KINDS:
            groups["cast"].append((path, _TYPE_KINDS[v.kind]))
        elif (
            v.side == Side.REQ
            and len(path) == 2
            and area == ["header"]
            and v.kind in ("missing", "auth")
        ):
            groups["header"].append(path[1])
        else:
            return [], Reason.NO_CANDIDATE
    used = [name for name, items in groups.items() if items]
    if len(used) != 1:  # nothing to go on, or a combined change that needs the spec
        return [], Reason.NO_CANDIDATE
    options: Iterable[Option]
    if used[0] == "header":
        ops = [_header_op(n, header_sources, cfg_keys) for n in groups["header"]]
        options = [] if None in ops else [(ops, [])]
    elif used[0] == "cast":
        if not all(_has(base_doc, p) for p, _ in groups["cast"]):
            return [], Reason.NO_CANDIDATE
        options = [([_cast(p, to) for p, to in groups["cast"]], [])]
    elif used[0] == "fill":
        options = _clue_fills(groups["fill"], base_doc)
    else:
        if not isinstance(response_data, dict):
            return [], Reason.NO_CANDIDATE
        resp_ops = _clue_response_ops(groups["resp"], response_data, expected_schema)
        if resp_ops is None:
            return [], Reason.NO_CANDIDATE
        options = [([], resp_ops)]
    return _finish(options, base_doc, cfg_keys, response_data)
