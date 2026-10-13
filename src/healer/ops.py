"""Op Interpreter: fix operations are plain JSON dicts applied to a document, purely."""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping
from typing import Any

from jsonschema import Draft202012Validator

from healer.canonical import get, pop, put
from healer.models import OpName, Reason

_PATH = {"type": "array", "minItems": 1, "items": {"type": ["string", "integer"]}}
_STR = {"type": "string", "minLength": 1}


def _op(kind: OpName, /, **props: dict) -> dict:
    return {
        "type": "object",
        "properties": {"op": {"const": kind.value}, **props},
        "required": ["op", *props],
        "additionalProperties": False,
    }


# No op carries a literal value: header values are config refs, route/move/cast reuse existing data.
OPS_SCHEMA: dict = {
    "type": "array",
    "items": {
        "oneOf": [
            _op(OpName.move, **{"from": _PATH, "to": _PATH}),
            _op(OpName.cast, path=_PATH, to={"enum": ["int", "str", "float", "bool"]}),
            _op(
                OpName.header,
                name=_STR,
                src={
                    "type": "object",
                    "properties": {"ref": {"const": "config"}, "key": _STR},
                    "required": ["ref", "key"],
                    "additionalProperties": False,
                },
            ),
            _op(OpName.route, method=_STR, path=_STR),
        ]
    },
}
_VALIDATOR = Draft202012Validator(OPS_SCHEMA)


class OpError(Exception):
    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_ops(ops: Any) -> None:
    if not _VALIDATOR.is_valid(ops):
        raise OpError(Reason.UNSAFE_PATCH)


_TYPES: dict[str, type] = {"int": int, "str": str, "float": float, "bool": bool}


def _cast_value(value: Any, to: str) -> Any:
    target = _TYPES[to]
    if type(value) is target:
        return value
    if target is bool:
        if value not in ("true", "false"):
            raise OpError(Reason.UNSAFE_PATCH)
        return value == "true"
    # bool sources are excluded: str(True) == "True" is a made-up representation.
    if type(value) not in (str, int, float):
        raise OpError(Reason.UNSAFE_PATCH)
    try:
        out = target(value)
        # ponytail: "nan"/"inf" strings round-trip, so they pass as floats.
        lossless = type(value)(out) == value
    except (ValueError, TypeError, OverflowError):
        lossless = False
    if not lossless:
        raise OpError(Reason.UNSAFE_PATCH)
    return out


def _move(op: dict, doc: dict, cfg: Mapping[str, str]) -> None:
    put(doc, op["to"], pop(doc, op["from"]))


def _cast(op: dict, doc: dict, cfg: Mapping[str, str]) -> None:
    put(doc, op["path"], _cast_value(get(doc, op["path"]), op["to"]))


def _header(op: dict, doc: dict, cfg: Mapping[str, str]) -> None:
    key = op["src"]["key"]
    if key not in cfg:
        raise OpError(Reason.NO_SAFE_VALUE)
    doc.setdefault("header", {})[op["name"].lower()] = cfg[key]


def _route(op: dict, doc: dict, cfg: Mapping[str, str]) -> None:
    doc["route"] = {"method": op["method"], "path": op["path"]}


_APPLY: dict[str, Callable[[dict, dict, Mapping[str, str]], None]] = {
    OpName.move: _move,
    OpName.cast: _cast,
    OpName.header: _header,
    OpName.route: _route,
}


def apply_ops(ops: list[dict], doc: dict, cfg: Mapping[str, str]) -> dict:
    validate_ops(ops)
    out = copy.deepcopy(doc)
    for op in ops:
        try:
            _APPLY[op["op"]](op, out, cfg)
        except KeyError:
            raise OpError(Reason.UNSAFE_PATCH) from None
    return out
