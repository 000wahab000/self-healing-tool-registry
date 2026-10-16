"""SQLite store (WAL) plus the in-memory active-fix cache (FR-5)."""
# Negative cache is persisted in SQLite (negative_cache table).

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Callable, Iterable
from enum import Enum
from typing import Protocol, runtime_checkable

from healer import canonical
from healer.models import (
    AuditEvent,
    DecisionPath,
    ErrorClass,
    Fix,
    FixStatus,
    HealOutcome,
    Reason,
    Tier,
)
from healer.settings import NEG_CACHE_TTL_S, RETIRE_AT_LOSSES

RAW_ERROR_MAX = 2048
REDACTED = "[REDACTED]"
# ponytail: header-shaped `name: value` / `"name": "value"` text, to the end of the line or JSON
# string. A JSON-escaped multi-header string is redacted whole, never leaked.
_HEADER_VALUE = re.compile(
    r'\b(authorization|cookie|set-cookie|[\w-]*api[-_]?key|[\w-]*token)("?\s*[:=]\s*"?)[^"\r\n,}]+',
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bbearer\s+[\w.~+/=-]+", re.IGNORECASE)
_JWT = re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]*")


def sanitize(text: str, secrets: Iterable[str] = ()) -> str:
    """FR-5.7: the audit blob keeps no secret. Redact, then truncate (so a cut cannot expose one)."""
    for secret in sorted(filter(None, secrets), key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    text = _HEADER_VALUE.sub(rf"\1\2{REDACTED}", text)
    text = _BEARER.sub(f"Bearer {REDACTED}", text)
    return _JWT.sub(REDACTED, text)[:RAW_ERROR_MAX]


def _in(col: str, enum: type[Enum]) -> str:
    return f"CHECK ({col} IN ({', '.join(repr(m.value) for m in enum)}))"


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS spec_snapshots (
    spec_hash TEXT PRIMARY KEY,
    spec TEXT NOT NULL,
    seen_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS fixes (
    fix_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL,
    signature TEXT NOT NULL,
    tool TEXT NOT NULL,
    class TEXT NOT NULL {_in("class", ErrorClass)},
    request_ops TEXT NOT NULL,
    response_ops TEXT NOT NULL,
    tier INTEGER NOT NULL {_in("tier", Tier)},
    source TEXT NOT NULL {_in("source", DecisionPath)},
    schema_hash TEXT NOT NULL,
    dsl_version INTEGER NOT NULL,
    status TEXT NOT NULL {_in("status", FixStatus)},
    wins INTEGER NOT NULL,
    losses INTEGER NOT NULL,
    created_ms INTEGER NOT NULL,
    last_used_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS fixes_by_fingerprint ON fixes (fingerprint, status);
CREATE TABLE IF NOT EXISTS heal_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER NOT NULL,
    tool TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    class TEXT NOT NULL {_in("class", ErrorClass)},
    raw_code TEXT NOT NULL,
    tier INTEGER NOT NULL {_in("tier", Tier)},
    path TEXT {_in("path", DecisionPath)},
    fix_id INTEGER,
    outcome TEXT NOT NULL {_in("outcome", HealOutcome)},
    reason TEXT {_in("reason", Reason)},
    mttr_ms INTEGER NOT NULL,
    heal_ms INTEGER NOT NULL,
    jev_tokens INTEGER NOT NULL,
    llm_tokens INTEGER NOT NULL,
    raw_error TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS call_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER NOT NULL,
    agent TEXT NOT NULL,
    run_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    class TEXT NOT NULL {_in("class", ErrorClass)},
    latency_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rules (
    rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL UNIQUE,
    wins INTEGER NOT NULL DEFAULT 1,
    promoted INTEGER NOT NULL DEFAULT 0,
    created_ms INTEGER NOT NULL,
    last_used_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS negative_cache (
    fingerprint TEXT PRIMARY KEY,
    expires_ms INTEGER NOT NULL
);
"""

FIX_COLS = (
    "fix_id, fingerprint, signature, tool, class AS cls, request_ops, response_ops,"
    " tier, source, schema_hash, dsl_version, status, wins, losses, created_ms,"
    " last_used_ms"
)
AUDIT_COLS = (
    "ts_ms, tool, fingerprint, class AS cls, raw_code, tier, path, fix_id, outcome,"
    " reason, mttr_ms, heal_ms, jev_tokens, llm_tokens, raw_error"
)


def _fix(row: sqlite3.Row) -> Fix:
    d = dict(row)
    return Fix(
        **d
        | {
            "signature": json.loads(d["signature"]),
            "cls": ErrorClass(d["cls"]),
            "request_ops": json.loads(d["request_ops"]),
            "response_ops": json.loads(d["response_ops"]),
            "tier": Tier(d["tier"]),
            "source": DecisionPath(d["source"]),
            "status": FixStatus(d["status"]),
        }
    )


def _event(row: sqlite3.Row) -> AuditEvent:
    d = dict(row)
    return AuditEvent(
        **d
        | {
            "cls": ErrorClass(d["cls"]),
            "tier": Tier(d["tier"]),
            "path": DecisionPath(d["path"]) if d["path"] else None,
            "outcome": HealOutcome(d["outcome"]),
            "reason": Reason(d["reason"]) if d["reason"] else None,
        }
    )


@runtime_checkable
class FixStore(Protocol):
    """What the registry, the healer and the demo call on a store. SQLite (`Store`) implements it;
    another backend (Postgres) must too, and must pass the same store tests."""

    def get_active(self, fp: str) -> Fix | None: ...
    def get_fix(self, fix_id: int) -> Fix | None: ...
    def save_fix(self, fix: Fix) -> int: ...
    def record_result(self, fix_id: int, won: bool) -> None: ...
    def audit(self, event: AuditEvent) -> None: ...
    def audit_events(self) -> list[AuditEvent]: ...
    def is_negative(self, fp: str) -> bool: ...
    def add_negative(self, fp: str) -> None: ...
    def save_spec(self, spec_hash: str, spec: dict) -> None: ...
    def get_spec(self, spec_hash: str) -> dict | None: ...
    def log_call(
        self, agent: str, run_id: str, tool: str, cls: ErrorClass, latency_ms: int
    ) -> None: ...
    def call_events(self, after_id: int = 0) -> list[dict]: ...
    def get_candidate(self, fp: str) -> Fix | None: ...
    def promote(self, fix_id: int) -> None: ...
    def record_rule_win(self, pattern: str) -> int: ...
    def is_rule(self, pattern: str) -> bool: ...
    def get_rules(self) -> list[str]: ...
    def close(self) -> None: ...


class Store:
    def __init__(self, db_path: str, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._db = sqlite3.connect(db_path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        self._active = {
            f.fingerprint: f
            for f in map(
                _fix,
                self._db.execute(
                    f"SELECT {FIX_COLS} FROM fixes WHERE status = ?",
                    (FixStatus.active,),
                ),
            )
        }
        self._candidates = {
            f.fingerprint: f
            for f in map(
                _fix,
                self._db.execute(
                    f"SELECT {FIX_COLS} FROM fixes WHERE status = ?",
                    (FixStatus.candidate,),
                ),
            )
        }
        self._promoted_rules = {
            r["pattern"]
            for r in self._db.execute("SELECT pattern FROM rules WHERE promoted = 1")
        }
        # Persisted negative cache; expiry is still checked on read, so stale rows are harmless.
        self._neg = {
            r["fingerprint"]: r["expires_ms"] / 1000.0
            for r in self._db.execute("SELECT fingerprint, expires_ms FROM negative_cache")
        }

    def _now_ms(self) -> int:
        return int(self._clock() * 1000)

    def get_active(self, fp: str) -> Fix | None:
        return self._active.get(fp)

    def get_candidate(self, fp: str) -> Fix | None:
        return self._candidates.get(fp)

    def promote(self, fix_id: int) -> None:
        now = self._now_ms()
        with self._db:
            row = self._db.execute(
                f"SELECT {FIX_COLS} FROM fixes WHERE fix_id = ?", (fix_id,)
            ).fetchone()
            if not row:
                return
            fp = row["fingerprint"]
            self._db.execute(
                "UPDATE fixes SET status = ? WHERE fingerprint = ? AND status = ?",
                (FixStatus.retired, fp, FixStatus.active),
            )
            self._db.execute(
                "UPDATE fixes SET status = ?, last_used_ms = ? WHERE fix_id = ?",
                (FixStatus.active, now, fix_id),
            )
            promoted_row = self._db.execute(
                f"SELECT {FIX_COLS} FROM fixes WHERE fix_id = ?", (fix_id,)
            ).fetchone()
            fix = _fix(promoted_row)
            self._active[fp] = fix
            self._candidates.pop(fp, None)

    def save_fix(self, fix: Fix) -> int:
        with self._db:  # retire-then-insert commits together or not at all
            if fix.status is FixStatus.active:
                self._db.execute(
                    "UPDATE fixes SET status = ? WHERE fingerprint = ? AND status = ?",
                    (FixStatus.retired, fix.fingerprint, FixStatus.active),
                )
            cur = self._db.execute(
                "INSERT INTO fixes (fingerprint, signature, tool, class, request_ops,"
                " response_ops, tier, source, schema_hash, dsl_version, status, wins,"
                " losses, created_ms, last_used_ms) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    fix.fingerprint,
                    canonical.dumps(fix.signature),
                    fix.tool,
                    fix.cls,
                    canonical.dumps(fix.request_ops),
                    canonical.dumps(fix.response_ops),
                    fix.tier,
                    fix.source,
                    fix.schema_hash,
                    fix.dsl_version,
                    fix.status,
                    fix.wins,
                    fix.losses,
                    fix.created_ms or self._now_ms(),
                    fix.last_used_ms,
                ),
            )
        fix.fix_id = cur.lastrowid
        if fix.status is FixStatus.active:
            self._active[fix.fingerprint] = fix
            self._candidates.pop(fix.fingerprint, None)
        elif fix.status is FixStatus.candidate:
            self._candidates[fix.fingerprint] = fix
        return fix.fix_id

    def record_result(self, fix_id: int, won: bool) -> None:
        col = "wins" if won else "losses"
        with self._db:
            fp, wins, losses, used_ms = self._db.execute(
                f"UPDATE fixes SET {col} = {col} + 1, last_used_ms = ? WHERE fix_id = ?"
                " RETURNING fingerprint, wins, losses, last_used_ms",
                (self._now_ms(), fix_id),
            ).fetchone()
            retire = losses >= RETIRE_AT_LOSSES
            if retire:
                self._db.execute(
                    "UPDATE fixes SET status = ? WHERE fix_id = ?",
                    (FixStatus.retired, fix_id),
                )
        cached = self._active.get(fp) or self._candidates.get(fp)
        if cached and cached.fix_id == fix_id:
            cached.wins, cached.losses, cached.last_used_ms = wins, losses, used_ms
            if retire:
                cached.status = FixStatus.retired
                self._active.pop(fp, None)
                self._candidates.pop(fp, None)

    def audit(self, event: AuditEvent) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO heal_events (ts_ms, tool, fingerprint, class, raw_code, tier,"
                " path, fix_id, outcome, reason, mttr_ms, heal_ms, jev_tokens,"
                " llm_tokens, raw_error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    event.ts_ms,
                    event.tool,
                    event.fingerprint,
                    event.cls,
                    event.raw_code,
                    event.tier,
                    event.path,
                    event.fix_id,
                    event.outcome,
                    event.reason,
                    event.mttr_ms,
                    event.heal_ms,
                    event.jev_tokens,
                    event.llm_tokens,
                    event.raw_error,
                ),
            )

    def audit_events(self) -> list[AuditEvent]:
        rows = self._db.execute(
            f"SELECT {AUDIT_COLS} FROM heal_events ORDER BY event_id"
        )
        return [_event(r) for r in rows]

    def is_negative(self, fp: str) -> bool:
        return self._neg.get(fp, 0) > self._clock()

    def add_negative(self, fp: str) -> None:
        expires = self._clock() + NEG_CACHE_TTL_S
        self._neg[fp] = expires
        with self._db:
            self._db.execute(
                "INSERT INTO negative_cache (fingerprint, expires_ms) VALUES (?, ?)"
                " ON CONFLICT(fingerprint) DO UPDATE SET expires_ms = excluded.expires_ms",
                (fp, int(expires * 1000)),
            )

    def save_spec(self, spec_hash: str, spec: dict) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO spec_snapshots (spec_hash, spec, seen_ms)"
                " VALUES (?,?,?)",
                (spec_hash, canonical.dumps(spec), self._now_ms()),
            )

    def get_spec(self, spec_hash: str) -> dict | None:
        row = self._db.execute(
            "SELECT spec FROM spec_snapshots WHERE spec_hash = ?", (spec_hash,)
        ).fetchone()
        return json.loads(row["spec"]) if row else None

    def log_call(
        self, agent: str, run_id: str, tool: str, cls: ErrorClass, latency_ms: int
    ) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO call_events (ts_ms, agent, run_id, tool, class, latency_ms)"
                " VALUES (?,?,?,?,?,?)",
                (self._now_ms(), agent, run_id, tool, cls, latency_ms),
            )

    def call_events(self, after_id: int = 0) -> list[dict]:
        rows = self._db.execute(
            "SELECT event_id, ts_ms, agent, run_id, tool, class, latency_ms"
            " FROM call_events WHERE event_id > ? ORDER BY event_id",
            (after_id,),
        )
        return [dict(r) for r in rows]

    def get_fix(self, fix_id: int) -> Fix | None:
        row = self._db.execute(
            f"SELECT {FIX_COLS} FROM fixes WHERE fix_id = ?", (fix_id,)
        ).fetchone()
        return _fix(row) if row else None

    def record_rule_win(self, pattern: str) -> int:
        now = self._now_ms()
        with self._db:
            row = self._db.execute(
                "SELECT wins FROM rules WHERE pattern = ?", (pattern,)
            ).fetchone()
            if row:
                wins = row["wins"] + 1
                promoted = 1 if wins >= 3 else 0
                self._db.execute(
                    "UPDATE rules SET wins = ?, promoted = ?, last_used_ms = ? WHERE pattern = ?",
                    (wins, promoted, now, pattern),
                )
            else:
                wins = 1
                self._db.execute(
                    "INSERT INTO rules (pattern, wins, promoted, created_ms, last_used_ms) VALUES (?, ?, 0, ?, ?)",
                    (pattern, 1, now, now),
                )
        if wins >= 3:
            self._promoted_rules.add(pattern)
        return wins

    def is_rule(self, pattern: str) -> bool:
        return pattern in self._promoted_rules

    def get_rules(self) -> list[str]:
        return sorted(self._promoted_rules)

    def close(self) -> None:
        self._db.close()
