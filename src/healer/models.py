"""Enums and records shared across modules. Stdlib only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

Path = list[str | int]


class ErrorClass(StrEnum):
    OK = "OK"
    BUSINESS = "BUSINESS"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"
    E5 = "E5"
    E6 = "E6"


class Reason(StrEnum):
    NO_CANDIDATE = "NO_CANDIDATE"
    NO_SAFE_VALUE = "NO_SAFE_VALUE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    JEV_UNAVAILABLE = "JEV_UNAVAILABLE"
    UNSAFE_PATCH = "UNSAFE_PATCH"
    UNSAFE_REPLAY = "UNSAFE_REPLAY"
    VERIFY_FAILED = "VERIFY_FAILED"
    POSTCHECK_FAILED_AFTER_WRITE = "POSTCHECK_FAILED_AFTER_WRITE"
    KNOWN_UNFIXABLE = "KNOWN_UNFIXABLE"
    DEADLINE = "DEADLINE"
    NOT_DRIFT = "NOT_DRIFT"


class HealOutcome(StrEnum):
    RECOVERED = "RECOVERED"
    ABORTED = "ABORTED"
    VERIFY_FAILED = "VERIFY_FAILED"
    NOT_DRIFT = "NOT_DRIFT"


class Side(StrEnum):
    REQ = "req"
    RESP = "resp"


class OpName(StrEnum):
    move = "move"
    cast = "cast"
    header = "header"
    route = "route"


class PostcheckType(StrEnum):
    echo = "echo"
    non_empty = "non_empty"


class FixStatus(StrEnum):
    candidate = "candidate"
    active = "active"
    failed = "failed"
    retired = "retired"


class DecisionPath(StrEnum):
    cache = "cache"
    diff = "diff"
    clue = "clue"
    jev = "jev"


class Tier(IntEnum):
    T0 = 0
    T1 = 1
    T2 = 2


@dataclass
class Violation:
    side: Side
    path: Path
    kind: str


@dataclass
class Outcome:
    cls: ErrorClass
    protocol: str
    raw_code: str
    data: Any = None
    violations: list[Violation] = field(default_factory=list)


@dataclass
class Fix:
    fingerprint: str
    signature: dict
    tool: str
    cls: ErrorClass
    request_ops: list[dict]
    response_ops: list[dict]
    tier: Tier
    source: DecisionPath
    schema_hash: str
    dsl_version: int = 1
    status: FixStatus = FixStatus.active
    wins: int = 0
    losses: int = 0
    created_ms: int = 0
    last_used_ms: int = 0
    fix_id: int | None = None


@dataclass
class AuditEvent:
    ts_ms: int
    tool: str
    fingerprint: str
    cls: ErrorClass
    raw_code: str
    tier: Tier
    path: DecisionPath | None
    fix_id: int | None
    outcome: HealOutcome
    reason: Reason | None
    mttr_ms: int
    jev_tokens: int = 0
    llm_tokens: int = 0
    raw_error: str = ""


@dataclass
class HealError:
    tool: str
    cls: ErrorClass
    fingerprint: str
    reason: Reason

    def to_dict(self) -> dict:
        return {
            "error": "SCHEMA_DRIFT_UNRECOVERABLE",
            "tool": self.tool,
            "class": self.cls.value,
            "fingerprint": self.fingerprint,
            "reason": self.reason.value,
            "retry": False,
        }
