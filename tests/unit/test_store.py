from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

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
from healer.settings import NEG_CACHE_TTL_S
from healer.store import RAW_ERROR_MAX, Store, sanitize

FP = "9f2c41d0a7b3e815"
SIGNATURE = {
    "tool": "get_user",
    "proto": "rest",
    "class": "E2",
    "code": "422",
    "v": [["req", ["body", "target"], "missing"]],
}
REQUEST_OPS = [
    {"op": "move", "from": ["body", "user_id"], "to": ["body", "target", "id"]},
    {"op": "cast", "path": ["body", "target", "id"], "to": "int"},
    {
        "op": "header",
        "name": "X-Tenant-Id",
        "src": {"ref": "config", "key": "TENANT_ID"},
    },
]


class FakeClock:
    def __init__(self, t: float = 1_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def make_fix(fp: str = FP, **kw) -> Fix:
    fields = {
        "fingerprint": fp,
        "signature": SIGNATURE,
        "tool": "get_user",
        "cls": ErrorClass.E2,
        "request_ops": REQUEST_OPS,
        "response_ops": [],
        "tier": Tier.T1,
        "source": DecisionPath.diff,
        "schema_hash": "abc123",
        "created_ms": 5,
    }
    return Fix(**(fields | kw))


def make_event(**kw) -> AuditEvent:
    fields = {
        "ts_ms": 1_700_000_000_000,
        "tool": "get_user",
        "fingerprint": FP,
        "cls": ErrorClass.E2,
        "raw_code": "422",
        "tier": Tier.T1,
        "path": DecisionPath.diff,
        "fix_id": 1,
        "outcome": HealOutcome.RECOVERED,
        "reason": None,
        "mttr_ms": 812,
        "heal_ms": 140,
        "jev_tokens": 0,
        "llm_tokens": 0,
        "raw_error": '{"detail":[{"loc":["body","target"],"msg":"Field required é"}]}',
    }
    return AuditEvent(**(fields | kw))


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "healer.db")


@pytest.fixture
def open_store(db_path: str, clock: FakeClock):
    opened: list[Store] = []

    def _open() -> Store:
        s = Store(db_path, clock)
        opened.append(s)
        return s

    yield _open
    for s in opened:
        s.close()


def rows(db_path: str, sql: str, *args) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def test_wal_mode_is_on(open_store, db_path):
    open_store()
    assert rows(db_path, "PRAGMA journal_mode") == [("wal",)]


def test_fix_round_trip_survives_restart(open_store, db_path):
    store = open_store()
    fix = make_fix()
    fix_id = store.save_fix(fix)
    assert fix_id == fix.fix_id
    assert store.get_active(FP) == fix
    assert store.get_active("0000000000000000") is None
    store.close()

    reopened = open_store()
    loaded = reopened.get_active(FP)
    assert loaded == make_fix(fix_id=fix_id)
    assert loaded.tier is Tier.T1 and loaded.source is DecisionPath.diff
    assert loaded.status is FixStatus.active
    assert rows(db_path, "SELECT signature, request_ops, response_ops FROM fixes") == [
        (
            canonical.dumps(SIGNATURE),
            canonical.dumps(REQUEST_OPS),
            canonical.dumps([]),
        )
    ]


def test_one_active_fix_per_fingerprint(open_store, db_path):
    store = open_store()
    first = make_fix(schema_hash="v1")
    second = make_fix(schema_hash="v2", request_ops=[])
    other = make_fix("aaaaaaaaaaaaaaaa")
    first_id = store.save_fix(first)
    other_id = store.save_fix(other)
    second_id = store.save_fix(second)
    assert len({first_id, second_id, other_id}) == 3

    assert store.get_active(FP) is second
    assert store.get_active("aaaaaaaaaaaaaaaa") is other
    assert rows(
        db_path,
        "SELECT fix_id, status FROM fixes WHERE fingerprint=? ORDER BY fix_id",
        FP,
    ) == [(first_id, "retired"), (second_id, "active")]

    # a non-active fix is stored but does not displace the active one
    cand = make_fix(status=FixStatus.candidate, schema_hash="v3")
    store.save_fix(cand)
    assert store.get_active(FP) is second
    store.close()
    assert open_store().get_active(FP).fix_id == second_id


def test_retired_at_two_losses_and_evicted(open_store, db_path):
    store = open_store()
    fix_id = store.save_fix(make_fix())

    store.record_result(fix_id, won=True)
    store.record_result(fix_id, won=False)
    cached = store.get_active(FP)
    assert (cached.wins, cached.losses) == (1, 1)
    assert cached.status is FixStatus.active
    assert cached.last_used_ms == 1_000_000

    store.record_result(fix_id, won=False)
    assert store.get_active(FP) is None
    assert rows(db_path, "SELECT status, wins, losses FROM fixes") == [
        ("retired", 1, 2)
    ]
    store.close()
    assert open_store().get_active(FP) is None


def test_wins_alone_never_retire(open_store):
    store = open_store()
    fix_id = store.save_fix(make_fix())
    for _ in range(5):
        store.record_result(fix_id, won=True)
    assert store.get_active(FP).wins == 5


def test_audit_round_trip(open_store):
    store = open_store()
    events = [
        make_event(),
        make_event(
            ts_ms=1_700_000_000_500,
            cls=ErrorClass.E5,
            tier=Tier.T2,
            path=None,
            fix_id=None,
            outcome=HealOutcome.ABORTED,
            reason=Reason.NO_CANDIDATE,
            heal_ms=0,
            jev_tokens=312,
            llm_tokens=7,
            raw_error="",
        ),
    ]
    for e in events:
        store.audit(e)
    assert store.audit_events() == events
    store.close()
    assert open_store().audit_events() == events


def test_audit_layers_round_trip_and_redaction(open_store):
    store = open_store()
    layers = [
        {"layer": "L1", "name": "safety", "status": "pass", "detail": "ok"},
        {"layer": "L2", "name": "request_schema", "status": "fail", "detail": "tenant-77"},
    ]
    event = make_event(raw_error="Authorization: Bearer secret-value", layers=layers)
    store.audit(event)
    loaded = store.audit_events()[0]
    assert loaded.layers == [layers[0], {**layers[1], "detail": "[REDACTED]"}]
    assert "secret-value" not in loaded.raw_error


def test_audit_layers_column_migrates_existing_database(tmp_path: Path):
    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE heal_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "ts_ms INTEGER NOT NULL, tool TEXT NOT NULL, fingerprint TEXT NOT NULL, "
        "class TEXT NOT NULL, raw_code TEXT NOT NULL, tier INTEGER NOT NULL, path TEXT, "
        "fix_id INTEGER, outcome TEXT NOT NULL, reason TEXT, mttr_ms INTEGER NOT NULL, "
        "heal_ms INTEGER NOT NULL, jev_tokens INTEGER NOT NULL, llm_tokens INTEGER NOT NULL, "
        "raw_error TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()

    store = Store(db_path)
    assert rows(db_path, "PRAGMA table_info(heal_events)")[-1][1:6] == (
        "layers", "TEXT", 1, "'[]'", 0
    )
    store.close()


def test_heal_ms_is_its_own_column(open_store, db_path):
    store = open_store()
    store.audit(make_event(mttr_ms=900, heal_ms=140))
    assert rows(db_path, "SELECT mttr_ms, heal_ms FROM heal_events") == [(900, 140)]
    assert store.audit_events()[0].heal_ms == 140


def test_c11_enum_values_are_stored_and_the_old_reason_is_gone(open_store):
    store = open_store()
    for path in (DecisionPath.tiebreak, DecisionPath.jev_unavailable):
        store.audit(make_event(path=path))
    store.audit(
        make_event(outcome=HealOutcome.ABORTED, reason=Reason.UNSUPPORTED_CLASS)
    )
    assert [e.path for e in store.audit_events()[:2]] == [
        DecisionPath.tiebreak,
        DecisionPath.jev_unavailable,
    ]
    assert store.audit_events()[2].reason is Reason.UNSUPPORTED_CLASS
    assert "JEV_UNAVAILABLE" not in {r.value for r in Reason}
    with pytest.raises(sqlite3.IntegrityError):
        store.audit(make_event(reason="JEV_UNAVAILABLE"))


def test_negative_cache_expires_with_injected_clock(open_store, clock):
    store = open_store()
    assert not store.is_negative(FP)
    store.add_negative(FP)
    assert store.is_negative(FP)
    assert not store.is_negative("aaaaaaaaaaaaaaaa")

    clock.t += NEG_CACHE_TTL_S - 1
    assert store.is_negative(FP)
    clock.t += 1
    assert not store.is_negative(FP)

    store.add_negative(FP)
    assert store.is_negative(FP)


def test_negative_cache_is_persisted(open_store):
    store = open_store()
    store.add_negative(FP)
    store.close()
    assert open_store().is_negative(FP)


@pytest.mark.parametrize(
    "bad",
    [
        lambda s: s.save_fix(make_fix(status="bogus")),
        lambda s: s.save_fix(make_fix(source="bogus")),
        lambda s: s.save_fix(make_fix(cls="bogus")),
        lambda s: s.save_fix(make_fix(tier=7)),
        lambda s: s.audit(make_event(outcome="bogus")),
        lambda s: s.audit(make_event(reason="bogus")),
        lambda s: s.audit(make_event(path="bogus")),
        lambda s: s.log_call("healing", "run-1", "get_user", "bogus", 12),
    ],
)
def test_enum_check_rejects_bad_value(open_store, bad):
    store = open_store()
    with pytest.raises(sqlite3.IntegrityError):
        bad(store)
    assert store.get_active(FP) is None
    assert store.audit_events() == []


def test_failed_save_keeps_existing_active_fix(open_store, db_path):
    store = open_store()
    good = make_fix()
    store.save_fix(good)
    with pytest.raises(sqlite3.IntegrityError):
        store.save_fix(make_fix(tier=7))
    assert store.get_active(FP) is good
    assert rows(db_path, "SELECT status FROM fixes") == [("active",)]


def test_fix_and_audit_commit_atomically(open_store, db_path):
    store = open_store()
    original = make_fix()
    store.save_fix(original)
    replacement = make_fix(schema_hash="new")
    with pytest.raises(sqlite3.IntegrityError):
        store.save_fix_and_audit(replacement, make_event(outcome="bogus"))
    assert store.get_active(FP) is original
    assert rows(db_path, "SELECT status FROM fixes") == [("active",)]
    assert store.audit_events() == []

    event = make_event()
    fix_id = store.save_fix_and_audit(replacement, event)
    assert store.get_active(FP) is replacement
    assert replacement.fix_id == fix_id
<<<<<<< HEAD
    assert store.audit_events() == [event]
=======
    assert store.audit_events()[0].fix_id == fix_id
    assert event.fix_id == 1
>>>>>>> 59d60c9236144eb80cbf8d119a18900340fef15a


def test_spec_snapshot_round_trip(open_store):
    spec = {
        "openapi": "3.1.0",
        "paths": {"/users/lookup": {"post": {"operationId": "get_user"}}},
    }
    store = open_store()
    assert store.get_spec("h1") is None
    store.save_spec("h1", spec)
    store.save_spec("h1", spec)  # same version seen again
    assert store.get_spec("h1") == spec
    store.close()
    assert open_store().get_spec("h1") == spec


def test_log_call_row(open_store, db_path, clock):
    store = open_store()
    store.log_call("healing", "run-1", "get_user", ErrorClass.OK, 12)
    assert rows(
        db_path, "SELECT ts_ms, agent, run_id, tool, class, latency_ms FROM call_events"
    ) == [(1_000_000, "healing", "run-1", "get_user", "OK", 12)]


def test_call_events_returns_rows_after_the_cursor(open_store, clock):
    store = open_store()
    assert store.call_events() == []
    store.log_call("healing", "run-1", "get_user", ErrorClass.OK, 12)
    clock.t += 1
    store.log_call("baseline", "run-2", "update_email", ErrorClass.E2, 7)
    first = {
        "event_id": 1,
        "ts_ms": 1_000_000,
        "agent": "healing",
        "run_id": "run-1",
        "tool": "get_user",
        "class": "OK",
        "latency_ms": 12,
    }
    second = {
        "event_id": 2,
        "ts_ms": 1_001_000,
        "agent": "baseline",
        "run_id": "run-2",
        "tool": "update_email",
        "class": "E2",
        "latency_ms": 7,
    }
    assert store.call_events() == [first, second]
    assert store.call_events(after_id=1) == [second]
    assert store.call_events(after_id=2) == []


def test_get_fix_reads_any_status_from_the_database(open_store):
    store = open_store()
    first_id = store.save_fix(make_fix(schema_hash="v1"))
    second_id = store.save_fix(make_fix(schema_hash="v2", request_ops=[]))

    retired = store.get_fix(first_id)  # no longer in the active cache
    assert retired == make_fix(
        schema_hash="v1", fix_id=first_id, status=FixStatus.retired
    )
    assert store.get_fix(second_id).request_ops == []
    assert store.get_fix(second_id + 1) is None


JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
)
SECRETS = ["Bearer test-token", "tenant-77", "sk-live-0123456789"]
RAW_ERROR = canonical.dumps(
    {
        "code": "401",
        "body": {
            "detail": "Not authenticated",
            "input": "Bearer test-token",
            "echo": {"tenant": "tenant-77", "key": "sk-live-0123456789"},
            "headers": "Authorization: Bearer abc.def-123\nCookie: sid=s3cr3t; theme=dark\n"
            "Set-Cookie: sid=n3w; HttpOnly\nX-Api-Key: k-998877\nx-auth-token: t0k3n",
            "access_token": "opaque-access-value",
            "jwt": f"see {JWT} for details",
            "authorization": "Basic dXNlcjpwYXNz",
        },
    }
)
LEAKS = [
    "test-token",
    "tenant-77",
    "sk-live-0123456789",
    "abc.def-123",
    "s3cr3t",
    "n3w",
    "k-998877",
    "t0k3n",
    "opaque-access-value",
    "dXNlcjpwYXNz",
    JWT,
    "dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk",
]


def test_ac_24_raw_error_redacted():
    clean = sanitize(RAW_ERROR, SECRETS)

    assert [leak for leak in LEAKS if leak in clean] == []
    assert json.loads(clean)["body"]["detail"] == "Not authenticated"  # still useful


def test_sanitize_truncates_after_redacting():
    long = "x" * 5000 + "Bearer test-token"
    assert len(sanitize(long, ["Bearer test-token"])) == RAW_ERROR_MAX
    tail = "y" * (RAW_ERROR_MAX - 5) + "Bearer test-token"  # secret straddles the limit
    assert "test-token" not in sanitize(tail, ["Bearer test-token"])


def test_sanitize_ignores_empty_secret_values():
    assert sanitize("plain text", ["", "plain"]) == "[REDACTED] text"


def test_candidate_fix_save_and_promote(tmp_path: Path):
    store = Store(str(tmp_path / "test.db"))
    cand = make_fix("cand_fp_1", status=FixStatus.candidate)
    fix_id = store.save_fix(cand)

    assert store.get_active("cand_fp_1") is None
    loaded_cand = store.get_candidate("cand_fp_1")
    assert loaded_cand is not None
    assert loaded_cand.fix_id == fix_id
    assert loaded_cand.status == FixStatus.candidate

    # Promote candidate to active
    store.promote(fix_id)
    assert store.get_candidate("cand_fp_1") is None
    active = store.get_active("cand_fp_1")
    assert active is not None
    assert active.fix_id == fix_id
    assert active.status == FixStatus.active


def test_rule_mining_promotes_after_three_wins(tmp_path: Path):
    store = Store(str(tmp_path / "test.db"))
    pattern = '["$from_0->$to_0"]'

    assert store.is_rule(pattern) is False
    assert store.get_rules() == []

    # 1st win
    assert store.record_rule_win(pattern) == 1
    assert store.is_rule(pattern) is False

    # 2nd win
    assert store.record_rule_win(pattern) == 2
    assert store.is_rule(pattern) is False

    # 3rd win -> promoted!
    assert store.record_rule_win(pattern) == 3
    assert store.is_rule(pattern) is True
    assert store.get_rules() == [pattern]

    # Survives restart
    store.close()
    restarted = Store(str(tmp_path / "test.db"))
    assert restarted.is_rule(pattern) is True
    assert restarted.get_rules() == [pattern]
