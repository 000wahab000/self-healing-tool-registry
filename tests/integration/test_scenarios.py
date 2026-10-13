"""Phase 7 scenario suite: each mutation of the catalog, end to end through Registry.call."""

from __future__ import annotations

import json
import re

import pytest

from healer import canonical
from healer.models import (
    AuditEvent,
    DecisionPath,
    ErrorClass,
    HealOutcome,
    Reason,
    Side,
    Tier,
)
from healer.store import Store

USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}
GET_USER = {"user_id": "123"}
CLASS = {
    "M1": ErrorClass.E2,
    "M2": ErrorClass.E2,
    "M3": ErrorClass.E5,
    "M4": ErrorClass.E2,
    "M5": ErrorClass.E2,
}


def calls_to(api, path: str) -> list[dict]:
    return [r for r in api.requests if r["path"] == path]


def unrecoverable(result: dict, reason: Reason, cls: str = "E2") -> None:
    assert result["error"] == "SCHEMA_DRIFT_UNRECOVERABLE"
    assert (result["reason"], result["class"], result["retry"]) == (reason, cls, False)


def call_for(mid: str, n: int = 0) -> tuple[str, dict]:
    """The tool call that exercises `mid`; `n` varies the written values between repeats."""
    return {
        "M1": ("get_user", GET_USER),
        "M2": ("update_email", {"user_id": "123", "email": f"new{n}@example.com"}),
        "M3": ("get_user", GET_USER),
        "M4": ("create_ticket", {"user_id": "123", "title": f"Confirm {n}"}),
        "M5": ("get_user", GET_USER),
    }[mid]


def check_m1(api, reg, n, args, result) -> None:
    assert result == USER
    assert calls_to(api, "/users/lookup")[-1]["body"] == {"customer_id": "123"}


def check_m2(api, reg, n, args, result) -> None:
    assert result == {"id": "123", "email": args["email"]}
    assert api.state()["users"]["123"]["email"] == args["email"]
    sent = calls_to(api, "/users/email")[-1]["body"]
    assert sent == {"user_id": 123, "email": args["email"]}


def check_m3(api, reg, n, args, result) -> None:
    # only the v1 keys: the emptied `data` container may remain
    assert {k: result[k] for k in USER} == USER


def check_m4(api, reg, n, args, result) -> None:
    tickets = api.state()["tickets"]
    assert len(tickets) == n + 1
    assert {k: tickets[-1][k] for k in args} == args
    assert result["ticket_id"] == tickets[-1]["ticket_id"]
    sent = calls_to(api, "/tickets")[-1]
    assert sent["headers"]["authorization"] == reg.cfg["OAUTH_BEARER"]


def check_m5(api, reg, n, args, result) -> None:
    assert result == USER
    sent = calls_to(api, "/users/lookup")[-1]
    assert sent["body"] == {"target": {"id": 123}}
    assert sent["headers"]["x-tenant-id"] == reg.cfg["TENANT_ID"]


CHECKS = {
    "M1": check_m1,
    "M2": check_m2,
    "M3": check_m3,
    "M4": check_m4,
    "M5": check_m5,
}


async def run(mid: str, n: int, api, reg) -> dict:
    """One call of the scenario's tool, then the mutation's final-state checks."""
    tool, args = call_for(mid, n)
    result = await reg.call(tool, args)
    CHECKS[mid](api, reg, n, args, result)
    return result


async def assert_first_heal(mid: str, api, store, reg) -> AuditEvent:
    api.set_mutation(mid)
    await run(mid, 0, api, reg)
    (event,) = store.audit_events()
    assert (event.cls, event.outcome, event.tier) == (
        CLASS[mid],
        HealOutcome.RECOVERED,
        Tier.T1,
    )
    assert event.mttr_ms < 4000
    return event


async def test_ac_06_m1_rename(api, store, make_registry):
    await assert_first_heal("M1", api, store, await make_registry())


async def test_ac_06_m2_type(api, store, make_registry):
    await assert_first_heal("M2", api, store, await make_registry())


async def test_ac_06_m3_response_nesting(api, store, make_registry):
    await assert_first_heal("M3", api, store, await make_registry())


async def test_ac_06_m4_oauth_header(api, store, make_registry):
    await assert_first_heal("M4", api, store, await make_registry())


async def test_ac_06_m5_ps_example(api, store, make_registry):
    await assert_first_heal("M5", api, store, await make_registry())


async def test_ac_08_m7_silent_ignore(api, store, make_registry):
    reg = await make_registry()
    api.set_mutation("M7")
    args = {"user_id": "123", "email": "new@example.com"}

    result = await reg.call("update_email", args)

    assert result == {"id": "123", "email": "new@example.com"}
    assert api.state()["users"]["123"]["email"] == "new@example.com"
    (event,) = store.audit_events()
    assert (event.cls, event.outcome, event.tier) == (
        ErrorClass.E6,
        HealOutcome.RECOVERED,
        Tier.T1,
    )
    assert event.mttr_ms < 4000


async def test_ac_09_m8_no_safe_value(api, store, make_registry):
    reg = await make_registry()
    api.set_mutation("M8")

    result = await reg.call("create_ticket", {"user_id": "123", "title": "t"})

    unrecoverable(result, Reason.NO_SAFE_VALUE)
    sent_keys = {k for r in api.requests for k in (r["body"] or {})}
    assert "priority" not in sent_keys
    assert api.state()["tickets"] == []
    (event,) = store.audit_events()
    assert (event.outcome, event.reason) == (HealOutcome.ABORTED, Reason.NO_SAFE_VALUE)


@pytest.mark.parametrize("mid", list(CHECKS))
async def test_ac_11_tier0_repeat_and_restart(mid, api, store, tmp_path, make_registry):
    reg = await make_registry()
    first = await assert_first_heal(mid, api, store, reg)

    # Same registry: the active fix already serves the repeat, so nothing is healed.
    await run(mid, 1, api, reg)
    assert len(store.audit_events()) == 1

    # The API flaps back and the break returns to a fresh registry on the live store.
    api.set_mutation(None)
    repeat = await make_registry()
    api.set_mutation(mid)
    spec_fetches = len(calls_to(api, "/openapi.json"))
    await run(mid, 2, api, repeat)
    assert len(calls_to(api, "/openapi.json")) == spec_fetches
    again = store.audit_events()[1]

    # A restart: a new store on the same DB file.
    api.set_mutation(None)
    restarted = Store(str(tmp_path / "heal.db"))
    reborn = await make_registry(store=restarted)
    api.set_mutation(mid)
    await run(mid, 3, api, reborn)
    after_restart = restarted.audit_events()[2]
    restarted.close()

    for event in (again, after_restart):
        assert (event.tier, event.path, event.outcome) == (
            Tier.T0,
            DecisionPath.cache,
            HealOutcome.RECOVERED,
        )
        assert (event.fingerprint, event.fix_id) == (first.fingerprint, first.fix_id)
        assert event.mttr_ms < 500


async def test_ac_05_one_audit_event_per_attempt(api, store, make_registry):
    reg = await make_registry()
    attempts = 0  # counted here, from what each call is known to do, not from the store

    api.set_mutation("M1")
    assert await reg.call("get_user", GET_USER) == USER  # recovered
    attempts += 1
    assert await reg.call("get_user", GET_USER) == USER  # the active fix: no heal
    missing = await reg.call("get_user", {"user_id": "999"})  # C2: not drift
    assert (missing["error"], missing["class"]) == ("API_ERROR", "BUSINESS")
    attempts += 1
    bad = await reg.call("get_user", {"user_id": 123})  # agent mistake: no heal
    assert bad["error"] == "AGENT_ARG_ERROR"

    api.set_mutation("M7")
    args = {"user_id": "123", "email": "new@example.com"}
    assert (await reg.call("update_email", args))["email"] == args["email"]  # recovered
    attempts += 1

    api.set_mutation("M8")
    ticket = {"user_id": "123", "title": "t"}
    unrecoverable(await reg.call("create_ticket", ticket), Reason.NO_SAFE_VALUE)
    attempts += 1
    unrecoverable(await reg.call("create_ticket", ticket), Reason.KNOWN_UNFIXABLE)
    attempts += 1

    events = store.audit_events()
    assert len(events) == attempts
    assert [(e.outcome, e.reason) for e in events] == [
        (HealOutcome.RECOVERED, None),
        (HealOutcome.NOT_DRIFT, Reason.NOT_DRIFT),
        (HealOutcome.RECOVERED, None),
        (HealOutcome.ABORTED, Reason.NO_SAFE_VALUE),
        (HealOutcome.ABORTED, Reason.KNOWN_UNFIXABLE),
    ]
    for e in events:
        assert isinstance(e.cls, ErrorClass) and isinstance(e.outcome, HealOutcome)
        assert isinstance(e.tier, Tier)
        assert e.path is None or isinstance(e.path, DecisionPath)
        assert e.reason is None or isinstance(e.reason, Reason)
        assert e.tool in reg.defs
        assert re.fullmatch(r"[0-9a-f]{16}", e.fingerprint)
        assert re.fullmatch(r"[A-Za-z0-9]+", e.raw_code)
        assert (e.fix_id is not None) == (e.outcome is HealOutcome.RECOVERED)
        # raw_error is the violations as canonical JSON: [side, path, kind] triples, no prose.
        violations = json.loads(e.raw_error)
        assert canonical.dumps(violations) == e.raw_error
        for side, path, kind in violations:
            assert side in {s.value for s in Side}
            assert all(isinstance(step, str | int) for step in path)
            assert re.fullmatch(r"[a-z_]+", kind)


async def test_ac_01_agent_schema_frozen_after_all_heals(api, store, make_registry):
    reg = await make_registry()

    def frozen() -> dict:
        return {
            name: canonical.dumps([t.agent_schema, t.base_op])
            for name, t in reg.defs.items()
        } | {"": canonical.dumps(reg.tools())}

    loaded = frozen()

    for mid in ("M1", "M2", "M4"):
        api.set_mutation(mid)
        assert "error" not in await run(mid, 0, api, reg)
    api.set_mutation("M8")  # a refused heal leaves the schema alone too
    refused = await reg.call("create_ticket", {"user_id": "123", "title": "t"})
    unrecoverable(refused, Reason.NO_SAFE_VALUE)

    assert len(store.audit_events()) == 4
    assert [
        reg.defs[n].version for n in ("get_user", "update_email", "create_ticket")
    ] == [
        2,
        2,
        2,
    ]
    assert frozen() == loaded
