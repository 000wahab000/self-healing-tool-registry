"""Safety Gate (FR-9): reject a fix before anything is sent."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from healer import settings
from healer.canonical import get
from healer.models import ErrorClass, OpName, Reason
from healer.ops import OpError, apply_ops, validate_ops


def check(
    fix: dict,
    *,
    base_doc: dict,
    cfg: Mapping[str, str],
    cls: ErrorClass,
    tool_cfg: dict,
    n_evidence: int,
    spec_paths: set[tuple] | None = None,
    spec_routes: set[tuple[str, str]] | None = None,
    spec_enums: Mapping[tuple, set[Any]] | None = None,
) -> Reason | None:
    req, resp = fix["request_ops"], fix["response_ops"]
    try:
        validate_ops(req)
        validate_ops(resp)
        if len(req) + len(resp) > settings.OP_CAP_FACTOR * max(1, n_evidence):
            return Reason.UNSAFE_PATCH
        for op in req:
            if op["op"] == OpName.move:
                try:
                    get(base_doc, op["from"])
                except KeyError:
                    return Reason.NO_SAFE_VALUE
            elif op["op"] == OpName.enum_map:
                try:
                    get(base_doc, op["path"])
                except KeyError:
                    return Reason.NO_SAFE_VALUE
        for op in req + resp:
            name = op["op"]
            if name == OpName.enum_map:
                mapping = op.get("mapping", {})
                if len(set(mapping.values())) != len(mapping):
                    return Reason.UNSAFE_PATCH
<<<<<<< HEAD
                if spec_enums is not None:
                    allowed = spec_enums.get(tuple(op["path"]))
                    if allowed is None or not set(mapping.values()) <= allowed:
                        return Reason.UNSAFE_PATCH
=======
                allowed = spec_enums.get(tuple(op["path"])) if spec_enums is not None else None
                if allowed is None or not set(mapping.values()) <= allowed:
                    return Reason.UNSAFE_PATCH
>>>>>>> 59d60c9236144eb80cbf8d119a18900340fef15a
            if name in (OpName.move, OpName.cast, OpName.enum_map) and spec_paths is not None:
                dest = op["to"] if name == OpName.move else op["path"]
                if tuple(dest) not in spec_paths:
                    return Reason.UNSAFE_PATCH
            if (
                name == OpName.route
                and spec_routes is not None
                and (op["method"], op["path"]) not in spec_routes
            ):
                return Reason.UNSAFE_PATCH
        # Dry run covers lossy casts and missing header config (NO_SAFE_VALUE).
        apply_ops(req, base_doc, cfg)
    except OpError as e:
        return e.reason
    # FR-9.4: only an E2 (the server rejected the request) is safe to re-send unconditionally.
    if (
        replays(cls, req, resp)
        and cls is not ErrorClass.E2
        and not (tool_cfg.get("idempotent") or tool_cfg.get("idempotency_key"))
    ):
        return Reason.UNSAFE_REPLAY
    return None


def replays(cls: ErrorClass, request_ops: list[dict], response_ops: list[dict]) -> bool:
    """Everything is re-sent except the E5 remap of a body that was already received."""
    return not (cls is ErrorClass.E5 and response_ops and not request_ops)


def jev_ok(confidence: float, is_write: bool) -> bool:
    return confidence >= (
        settings.JEV_THRESHOLD_WRITE if is_write else settings.JEV_THRESHOLD_READ
    )
