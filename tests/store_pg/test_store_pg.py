from __future__ import annotations

import pytest

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

FP = "9f2c41d0a7b3e815"


def make_fix(**changes) -> Fix:
    values = {
        "fingerprint": FP,
        "signature": {"tool": "get_user", "class": "E2"},
        "tool": "get_user",
        "cls": ErrorClass.E2,
        "request_ops": [
            {"op": "move", "from": ["body", "id"], "to": ["body", "user_id"]}
        ],
        "response_ops": [],
        "tier": Tier.T1,
        "source": DecisionPath.diff,
        "schema_hash": "abc123",
        "created_ms": 5,
    }
    return Fix(**(values | changes))


def test_ac_39_shared_active_fix_and_database_uniqueness(pg_store):
    import os

    import psycopg

    from healer.store_pg import PostgresStore

    first = make_fix()
    pg_store.save_fix(first)
    other = PostgresStore(os.environ["PG_DSN"])
    try:
        assert other.get_active(FP) == first
        replacement = make_fix(schema_hash="v2", request_ops=[])
        other.save_fix(replacement)
        assert pg_store.get_active(FP) == replacement
        with pg_store._db.cursor() as cur:
            cur.execute(
                "SELECT status FROM fixes WHERE fingerprint = %s ORDER BY fix_id", (FP,)
            )
            assert [row["status"] for row in cur.fetchall()] == ["retired", "active"]
        with (
            pytest.raises(psycopg.errors.UniqueViolation),
            pg_store._db.transaction(),
            pg_store._db.cursor() as cur,
        ):
            cur.execute(
                "INSERT INTO fixes (fingerprint,signature,tool,class,request_ops,response_ops,tier,source,schema_hash,dsl_version,status,wins,losses,created_ms,last_used_ms) "
                "VALUES (%s,'{}','t','E2','[]','[]',1,'diff','h',1,'active',0,0,0,0)",
                (FP,),
            )
    finally:
        other.close()


async def test_ac_39_two_registries_reuse_m1_fix_at_tier0(pg_store):
    import json
    import os
    from pathlib import Path

    import httpx

    from healer.models import Tier
    from healer.registry import Registry
    from healer.store_pg import PostgresStore
    from mock_api.app import create_app

    api = create_app()
    config_path = Path(__file__).parents[2] / "config" / "tools.json"
    config = json.loads(config_path.read_text())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://mock"
    ) as client:
        other_store = PostgresStore(os.environ["PG_DSN"])
        try:
            first = Registry(
                client, config, {}, store=pg_store, sleep=lambda _: _no_sleep()
            )
            await first.load()
            api.set_mutation("M1")
            assert await first.call("get_user", {"user_id": "123"}) == {
                "id": "123",
                "name": "Ada",
                "email": "ada@example.com",
            }

            api.set_mutation(None)
            second = Registry(
                client, config, {}, store=other_store, sleep=lambda _: _no_sleep()
            )
            await second.load()
            api.set_mutation("M1")
            assert await second.call("get_user", {"user_id": "123"}) == {
                "id": "123",
                "name": "Ada",
                "email": "ada@example.com",
            }
            assert [event.tier for event in other_store.audit_events()] == [
                Tier.T1,
                Tier.T0,
            ]
        finally:
            other_store.close()


async def _no_sleep() -> None:
    return None


def test_pg_store_audit_snapshots_calls_and_negative_cache(pg_store):
    import psycopg

    event = AuditEvent(
        1,
        "get_user",
        FP,
        ErrorClass.E2,
        "422",
        Tier.T1,
        DecisionPath.diff,
        None,
        HealOutcome.ABORTED,
        Reason.NO_CANDIDATE,
        4,
        raw_error="{}",
    )
    pg_store.audit(event)
    assert pg_store.audit_events() == [event]
    pg_store.save_spec("h", {"openapi": "3.1.0"})
    pg_store.save_spec("h", {"openapi": "3.0.0"})
    assert pg_store.get_spec("h") == {"openapi": "3.1.0"}
    pg_store.log_call("agent", "run", "get_user", ErrorClass.OK, 12)
    first_id = pg_store.call_events()[0]["event_id"]
    pg_store.log_call("baseline", "run-2", "get_user", ErrorClass.E2, 13)
    assert [row["class"] for row in pg_store.call_events(after_id=first_id)] == ["E2"]
    pg_store.add_negative(FP)
    assert pg_store.is_negative(FP)
    with pytest.raises(psycopg.errors.CheckViolation):
        pg_store.audit(event.__class__(**(event.__dict__ | {"reason": "BOGUS"})))


def test_pg_fix_active_and_candidate_round_trip_and_retired_read(pg_store):
    import os

    from healer.store_pg import PostgresStore

    active = make_fix()
    candidate = make_fix(status=FixStatus.candidate, schema_hash="candidate")
    pg_store.save_fix(active)
    pg_store.save_fix(candidate)
    reopened = PostgresStore(os.environ["PG_DSN"])
    try:
        assert reopened.get_active(FP) == active
        assert reopened.get_fix(candidate.fix_id) == candidate
        replacement = make_fix(schema_hash="replacement")
        reopened.save_fix(replacement)
        assert reopened.get_fix(active.fix_id).status is FixStatus.retired
    finally:
        reopened.close()


def test_pg_negative_cache_expires_and_is_not_shared(pg_store):
    import os

    from healer.settings import NEG_CACHE_TTL_S
    from healer.store_pg import PostgresStore

    class Clock:
        now = 100.0

        def __call__(self) -> float:
            return self.now

    clock = Clock()
    writer = PostgresStore(os.environ["PG_DSN"], clock)
    reader = PostgresStore(os.environ["PG_DSN"], clock)
    try:
        writer.add_negative(FP)
        assert writer.is_negative(FP)
        assert not reader.is_negative(FP)
        clock.now += NEG_CACHE_TTL_S
        assert not writer.is_negative(FP)
    finally:
        writer.close()
        reader.close()


def test_pg_store_retire_after_losses(pg_store):
    fix = make_fix()
    fix_id = pg_store.save_fix(fix)
    pg_store.record_result(fix_id, False)
    pg_store.record_result(fix_id, False)
    assert pg_store.get_active(FP) is None
    assert pg_store.get_fix(fix_id).status is FixStatus.retired


def test_pg_concurrent_saves_leave_one_active_fix(pg_store):
    import os
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from healer.store_pg import PostgresStore

    barrier = Barrier(2)

    def save(schema_hash: str) -> None:
        store = PostgresStore(os.environ["PG_DSN"])
        try:
            barrier.wait()
            store.save_fix(make_fix(schema_hash=schema_hash))
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(save, ("v1", "v2")))

    with pg_store._db.transaction(), pg_store._db.cursor() as cur:
        cur.execute(
            "SELECT status FROM fixes WHERE fingerprint = %s ORDER BY fix_id", (FP,)
        )
        statuses = [row["status"] for row in cur.fetchall()]
    assert statuses.count("active") == 1
    assert statuses.count("retired") == 1


def test_pg_invalid_enum_rolls_back_active_fix_retirement(pg_store):
    import psycopg

    existing = make_fix()
    pg_store.save_fix(existing)
    with pytest.raises(psycopg.errors.CheckViolation):
        pg_store.save_fix(make_fix(tier=7))
    assert pg_store.get_active(FP) == existing
