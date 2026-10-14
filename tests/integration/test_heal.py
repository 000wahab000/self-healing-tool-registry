from __future__ import annotations

import asyncio
import json
import sqlite3

import httpx
import pytest

from healer import canonical
from healer.fingerprint import fingerprint
from healer.models import (
    DecisionPath,
    ErrorClass,
    Fix,
    HealOutcome,
    Outcome,
    Reason,
    Side,
    Tier,
    Violation,
)
from healer.registry import Registry
from healer.store import RAW_ERROR_MAX, Store

JEV_URL = "https://api.typesafe.ai/v1/systemone"
RIGHT = "body.user_id -> body.subject"  # M6: the pairing that sets the right manager
USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}
GET_USER = {"user_id": "123"}
SET_MANAGER = {"user_id": "123", "manager_id": "456"}
MOVE_CUSTOMER = {
    "op": "move",
    "from": ["body", "user_id"],
    "to": ["body", "customer_id"],
}


def calls_to(api, path: str) -> list[dict]:
    return [r for r in api.requests if r["path"] == path]


def jev_reply(pick, confidence: float):
    """respx side effect: choose the option whose text satisfies `pick`, reading the real criteria."""

    def respond(request: httpx.Request) -> httpx.Response:
        criteria = json.loads(request.content)["questions"]["fix"]["criteria"]
        label = next(k for k, text in criteria.items() if pick(text))
        answer = {"type": "choice", "choice": label, "confidence": confidence}
        usage = {"input_tokens": 300, "output_tokens": 20}
        return httpx.Response(200, json={"answers": {"fix": answer}, "usage": usage})

    return respond


def m1_fix(request_ops, response_ops=()) -> Fix:
    """A stored fix for the M1 break on get_user: 422, body.customer_id missing."""
    broken = Outcome(
        ErrorClass.E2,
        "rest",
        "422",
        violations=[Violation(Side.REQ, ["body", "customer_id"], "missing")],
    )
    fp, signature = fingerprint("get_user", broken)
    return Fix(
        fp,
        signature,
        "get_user",
        ErrorClass.E2,
        list(request_ops),
        list(response_ops),
        Tier.T1,
        DecisionPath.diff,
        "h",
    )


class StepClock:
    """Monotonic clock that jumps `step` seconds on every read."""

    def __init__(self) -> None:
        self.t, self.step = 0.0, 0.0

    def __call__(self) -> float:
        now, self.t = self.t, self.t + self.step
        return now


def unrecoverable(result: dict, reason: Reason, cls: str = "E2") -> None:
    assert result["error"] == "SCHEMA_DRIFT_UNRECOVERABLE"
    assert (result["reason"], result["class"], result["retry"]) == (reason, cls, False)


async def test_m1_first_call_heals_then_active_fix_serves_next_call(
    api, store, make_registry
):
    reg = await make_registry()
    tool = reg.defs["get_user"]
    frozen = canonical.dumps(tool.agent_schema)
    api.set_mutation("M1")
    spec_fetches = len(calls_to(api, "/openapi.json"))

    assert await reg.call("get_user", GET_USER) == USER

    (event,) = store.audit_events()
    assert (event.outcome, event.tier, event.path) == (
        HealOutcome.RECOVERED,
        Tier.T1,
        DecisionPath.diff,
    )
    assert (event.cls, event.reason, event.jev_tokens) == (ErrorClass.E2, None, 0)
    assert event.mttr_ms >= 0 and event.fix_id
    assert tool.active_fix.request_ops == [MOVE_CUSTOMER]
    assert store.get_active(event.fingerprint).fix_id == event.fix_id
    assert tool.version == 2
    assert "customer_id" in tool.wire_op["body_schema"]["properties"]
    assert canonical.dumps(tool.agent_schema) == frozen

    assert await reg.call("get_user", GET_USER) == USER
    assert len(store.audit_events()) == 1
    assert len(calls_to(api, "/openapi.json")) == spec_fetches + 1


async def test_tier0_repeat_break_uses_stored_fix_without_spec_fetch(
    api, store, tmp_path, make_registry
):
    first = await make_registry()
    api.set_mutation("M1")
    await first.call("get_user", GET_USER)
    (healed,) = store.audit_events()

    # A restart: new store on the same file, registry loaded against the v1 API, then the break returns.
    api.set_mutation(None)
    restarted = Store(str(tmp_path / "heal.db"))
    reg = await make_registry(store=restarted)
    api.set_mutation("M1")
    spec_fetches = len(calls_to(api, "/openapi.json"))

    assert await reg.call("get_user", GET_USER) == USER

    assert len(calls_to(api, "/openapi.json")) == spec_fetches
    healed_again = restarted.audit_events()[1]
    assert (healed_again.outcome, healed_again.tier, healed_again.path) == (
        HealOutcome.RECOVERED,
        Tier.T0,
        DecisionPath.cache,
    )
    assert healed_again.fingerprint == healed.fingerprint
    assert healed_again.fix_id == healed.fix_id
    assert restarted.get_active(healed.fingerprint).wins == 1
    restarted.close()


async def test_ac_07_m6_d_heals_through_the_tiebreaker_without_jev(
    api, store, jev, respx_mock, make_registry
):
    route = respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT in text, 0.95)
    )
    reg = await make_registry(jev=jev)  # configured, and still not asked
    api.set_mutation("M6-D")

    result = await reg.call("set_manager", SET_MANAGER)

    assert result == {"id": "123", "manager_id": "456"}
    users = api.state()["users"]
    assert (users["123"]["manager_id"], users["456"]["manager_id"]) == ("456", None)
    assert route.call_count == 0
    assert (
        calls_to(api, "/users/manager/validate") == []
    )  # a tie-break needs no dry run
    (event,) = store.audit_events()
    assert (event.outcome, event.path, event.tier, event.jev_tokens) == (
        HealOutcome.RECOVERED,
        DecisionPath.tiebreak,
        Tier.T1,
        0,
    )
    assert store.get_active(event.fingerprint).source is DecisionPath.tiebreak


async def test_ac_07_m6_n_jev_at_write_threshold_and_confirming_preverify_recovers(
    api, store, jev, respx_mock, make_registry
):
    route = respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT in text, 0.95)
    )
    reg = await make_registry(jev=jev)
    api.set_mutation("M6-N")

    result = await reg.call("set_manager", SET_MANAGER)

    assert result == {"id": "123", "manager_id": "456"}
    users = api.state()["users"]
    assert (users["123"]["manager_id"], users["456"]["manager_id"]) == ("456", None)
    (event,) = store.audit_events()
    assert (event.outcome, event.path, event.tier) == (
        HealOutcome.RECOVERED,
        DecisionPath.jev,
        Tier.T1,
    )
    assert event.jev_tokens > 0
    assert route.call_count == 1
    # the failing call, one dry run with the chosen request, then the write
    sent = [
        (r["path"], r["body"])
        for r in api.requests
        if r["path"].startswith("/users/manager")
    ]
    chosen = {"subject": "123", "supervisor": "456"}
    assert sent == [
        ("/users/manager", SET_MANAGER),
        ("/users/manager/validate", chosen),
        ("/users/manager", chosen),
    ]


async def test_ac_07_m6_n_low_confidence_no_write(
    api, store, jev, respx_mock, make_registry
):
    respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT in text, 0.6)
    )
    reg = await make_registry(jev=jev)
    api.set_mutation("M6-N")

    result = await reg.call("set_manager", SET_MANAGER)

    unrecoverable(result, Reason.LOW_CONFIDENCE)
    assert len(calls_to(api, "/users/manager")) == 1  # only the failing request
    assert calls_to(api, "/users/manager/validate") == []
    assert api.state()["users"]["123"]["manager_id"] is None
    (event,) = store.audit_events()
    assert (event.outcome, event.reason, event.path) == (
        HealOutcome.ABORTED,
        Reason.LOW_CONFIDENCE,
        DecisionPath.jev,
    )
    assert event.jev_tokens > 0 and event.fingerprint == result["fingerprint"]


async def test_ac_07_m6_n_without_preverify_no_write(
    api, store, tools_config, jev, respx_mock, make_registry
):
    del tools_config["tools"]["set_manager"]["preverify"]
    respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT in text, 0.95)
    )
    reg = await make_registry(jev=jev)
    api.set_mutation("M6-N")

    unrecoverable(await reg.call("set_manager", SET_MANAGER), Reason.LOW_CONFIDENCE)

    assert len(calls_to(api, "/users/manager")) == 1
    assert calls_to(api, "/users/manager/validate") == []
    assert api.state()["users"]["123"]["manager_id"] is None
    (event,) = store.audit_events()
    assert (event.reason, event.path) == (Reason.LOW_CONFIDENCE, DecisionPath.jev)


async def test_fr_8_6_preverify_that_refuses_the_pick_stops_the_write(
    api, store, jev, respx_mock, make_registry
):
    respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT not in text, 0.95)
    )
    reg = await make_registry(jev=jev)
    api.set_mutation("M6-N")

    result = await reg.call("set_manager", SET_MANAGER)

    unrecoverable(result, Reason.LOW_CONFIDENCE)
    assert len(calls_to(api, "/users/manager/validate")) == 1
    assert len(calls_to(api, "/users/manager")) == 1  # the wrong pairing never written
    assert api.state()["users"]["123"]["manager_id"] is None
    assert api.state()["users"]["456"]["manager_id"] is None
    assert reg.defs["set_manager"].active_fix is None
    (event,) = store.audit_events()
    assert (event.outcome, event.reason) == (HealOutcome.ABORTED, Reason.LOW_CONFIDENCE)
    unrecoverable(  # a refused pick is a verdict on this break: negative-cached
        await reg.call("set_manager", SET_MANAGER), Reason.KNOWN_UNFIXABLE
    )


async def test_m6_n_wrong_pick_a_preverify_cannot_tell_apart_is_caught_by_postcheck(
    api, store, wire, jev, respx_mock, make_registry
):
    # The residual risk of FR-8.6: a dry run that confirms every pairing.
    inner = wire.handle_async_request

    async def lenient(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/manager/validate":
            return httpx.Response(200, json={"id": "123", "manager_id": "456"})
        return await inner(request)

    wire.handle_async_request = lenient
    respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT not in text, 0.95)
    )
    reg = await make_registry(jev=jev)
    api.set_mutation("M6-N")

    result = await reg.call("set_manager", SET_MANAGER)

    unrecoverable(result, Reason.POSTCHECK_FAILED_AFTER_WRITE)
    (event,) = store.audit_events()
    assert (event.outcome, event.reason) == (
        HealOutcome.VERIFY_FAILED,
        Reason.POSTCHECK_FAILED_AFTER_WRITE,
    )
    assert reg.defs["set_manager"].active_fix is None
    assert store.get_active(event.fingerprint) is None
    unrecoverable(await reg.call("set_manager", SET_MANAGER), Reason.KNOWN_UNFIXABLE)


async def test_fr_7_6_read_tool_parameter_order_breaks_a_description_tie(
    api, store, tools_config, make_registry
):
    # Same M6-N break on a read tool: no descriptions, but the removed fields keep their
    # declaration order among the added ones for exactly one pairing (and that one is right).
    tools_config["tools"]["set_manager"]["write"] = False
    reg = await make_registry()
    api.set_mutation("M6-N")

    result = await reg.call("set_manager", SET_MANAGER)

    assert result == {"id": "123", "manager_id": "456"}
    (event,) = store.audit_events()
    assert (event.outcome, event.path) == (HealOutcome.RECOVERED, DecisionPath.tiebreak)
    assert calls_to(api, "/users/manager/validate") == []


async def test_ac_13_jev_unavailable_m6_n_aborts_low_confidence_without_a_write(
    api, store, jev, respx_mock, make_registry
):
    route = respx_mock.post(JEV_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    reg = await make_registry(jev=jev)
    api.set_mutation("M6-N")

    for _ in range(2):
        down = await reg.call("set_manager", SET_MANAGER)
        unrecoverable(down, Reason.LOW_CONFIDENCE)
    assert route.call_count == 2  # not negative-cached: Jev is asked again

    assert [(e.reason, e.path) for e in store.audit_events()] == [
        (Reason.LOW_CONFIDENCE, DecisionPath.jev_unavailable)
    ] * 2
    assert len(calls_to(api, "/users/manager")) == 2  # the two failing requests only
    assert calls_to(api, "/users/manager/validate") == []
    assert api.state()["users"]["123"]["manager_id"] is None


async def test_ac_13_jev_unconfigured_m6_n_aborts_low_confidence_m6_d_still_heals(
    api, store, make_registry
):
    reg = await make_registry()  # no Jev at all
    api.set_mutation("M6-N")

    unrecoverable(await reg.call("set_manager", SET_MANAGER), Reason.LOW_CONFIDENCE)
    unrecoverable(await reg.call("set_manager", SET_MANAGER), Reason.LOW_CONFIDENCE)

    assert [(e.reason, e.path) for e in store.audit_events()] == [
        (Reason.LOW_CONFIDENCE, DecisionPath.jev_unavailable)
    ] * 2  # the second call got a fresh attempt, not KNOWN_UNFIXABLE
    assert len(calls_to(api, "/users/manager")) == 2
    assert api.state()["users"]["123"]["manager_id"] is None

    api.set_mutation("M6-D")
    assert await reg.call("set_manager", SET_MANAGER) == {
        "id": "123",
        "manager_id": "456",
    }
    assert store.audit_events()[-1].path is DecisionPath.tiebreak


async def test_ac_12_negative_cache_known_unfixable(api, store, make_registry):
    reg = await make_registry()
    api.set_mutation("M8")
    args = {"user_id": "123", "title": "t"}
    before = len(calls_to(api, "/openapi.json"))

    first = await reg.call("create_ticket", args)
    unrecoverable(first, Reason.NO_SAFE_VALUE)
    assert len(calls_to(api, "/openapi.json")) == before + 1

    second = await reg.call("create_ticket", args)
    unrecoverable(second, Reason.KNOWN_UNFIXABLE)
    assert second["fingerprint"] == first["fingerprint"]
    assert len(calls_to(api, "/openapi.json")) == before + 1
    assert [e.reason for e in store.audit_events()] == [
        Reason.NO_SAFE_VALUE,
        Reason.KNOWN_UNFIXABLE,
    ]
    assert len(calls_to(api, "/tickets")) == 2 and api.state()["tickets"] == []


async def test_ac_19_single_flight_concurrency(api, store, wire, make_registry):
    reg = await make_registry()
    api.set_mutation("M1")
    wire.delay = 0.01  # lets the five calls reach the heal together
    before = len(calls_to(api, "/openapi.json"))

    results = await asyncio.gather(*(reg.call("get_user", GET_USER) for _ in range(5)))

    assert results == [USER] * 5
    (event,) = store.audit_events()
    assert event.outcome is HealOutcome.RECOVERED
    assert len(calls_to(api, "/openapi.json")) == before + 1


async def test_ac_20_unsafe_replay_non_idempotent(
    api, store, tools_config, make_registry
):
    tools_config["tools"]["update_email"]["idempotent"] = False
    reg = await make_registry()
    api.set_mutation("M7")

    result = await reg.call(
        "update_email", {"user_id": "123", "email": "new@example.com"}
    )

    unrecoverable(result, Reason.UNSAFE_REPLAY, cls="E6")
    assert len(calls_to(api, "/users/email")) == 1  # never replayed
    assert api.state()["users"]["123"]["email"] == "ada@example.com"
    (event,) = store.audit_events()
    assert (event.cls, event.outcome, event.reason) == (
        ErrorClass.E6,
        HealOutcome.ABORTED,
        Reason.UNSAFE_REPLAY,
    )


async def test_deadline_aborts_and_is_not_negative_cached(
    api, store, wire, make_registry
):
    clock = StepClock()
    reg = await make_registry(clock=clock)
    api.set_mutation("M1")
    wire.delay = 0.001
    clock.step = 4.0  # every clock read now lands past the 3.5 s heal deadline

    unrecoverable(await reg.call("get_user", GET_USER), Reason.DEADLINE)
    assert len(calls_to(api, "/users/lookup")) == 1  # no replay was sent
    assert [(e.outcome, e.reason) for e in store.audit_events()] == [
        (HealOutcome.ABORTED, Reason.DEADLINE)
    ]

    clock.step = 0.0
    assert await reg.call("get_user", GET_USER) == USER  # DEADLINE is transient
    assert store.audit_events()[1].outcome is HealOutcome.RECOVERED


async def test_c1_transient_503_is_retried_without_healing(
    api, store, sleeps, make_registry
):
    reg = await make_registry()
    api.set_mutation("C1")

    assert await reg.call("get_user", GET_USER) == USER

    assert sleeps == [0.1, 0.2]
    assert len(calls_to(api, "/users/lookup")) == 3
    assert store.audit_events() == []
    assert len(calls_to(api, "/openapi.json")) == 1  # the load only


async def test_persistent_e1_passes_through_after_three_retries(
    store, wire, sleeps, make_registry
):
    reg = await make_registry()
    wire.down.add("/users/lookup")

    result = await reg.call("get_user", GET_USER)

    assert (result["error"], result["class"], result["status"]) == (
        "API_ERROR",
        "E1",
        "ConnectError",
    )
    assert sleeps == [0.1, 0.2, 0.4]
    assert store.audit_events() == []


async def test_c2_missing_record_is_not_drift(api, store, make_registry):
    reg = await make_registry()

    result = await reg.call("get_user", {"user_id": "999"})

    assert result == {
        "error": "API_ERROR",
        "class": "BUSINESS",
        "status": "404",
        "detail": {"detail": "User not found"},
    }
    again = await reg.call("get_user", {"user_id": "999"})
    assert again == result  # NOT_DRIFT is never negative-cached
    assert [(e.cls, e.outcome, e.reason) for e in store.audit_events()] == [
        (ErrorClass.E2, HealOutcome.NOT_DRIFT, Reason.NOT_DRIFT)
    ] * 2
    assert reg.defs["get_user"].active_fix is None


async def test_spec_unavailable_flat_rename_heals_in_clue_mode(
    api, store, wire, make_registry
):
    reg = await make_registry()
    api.set_mutation("M1")
    wire.down.add("/openapi.json")

    assert await reg.call("get_user", GET_USER) == USER

    (event,) = store.audit_events()
    assert (event.outcome, event.path) == (HealOutcome.RECOVERED, DecisionPath.clue)
    assert reg.defs["get_user"].active_fix.request_ops == [MOVE_CUSTOMER]


async def test_m3_response_fix_is_applied_locally_without_replay(
    api, store, make_registry
):
    reg = await make_registry()
    api.set_mutation("M3")

    result = await reg.call("get_user", GET_USER)

    assert {k: result[k] for k in USER} == USER
    assert len(calls_to(api, "/users/lookup")) == 1
    (event,) = store.audit_events()
    assert (event.cls, event.outcome) == (ErrorClass.E5, HealOutcome.RECOVERED)


async def test_stale_stored_fix_records_loss_and_is_negative_cached(
    api, store, make_registry
):
    reg = await make_registry()
    api.set_mutation("M1")
    stale = m1_fix([])  # a stored fix that no longer fixes anything
    store.save_fix(stale)

    unrecoverable(await reg.call("get_user", GET_USER), Reason.VERIFY_FAILED)

    assert store.get_active(stale.fingerprint).losses == 1
    (event,) = store.audit_events()
    assert (event.outcome, event.tier, event.path, event.fix_id) == (
        HealOutcome.VERIFY_FAILED,
        Tier.T0,
        DecisionPath.cache,
        stale.fix_id,
    )
    unrecoverable(await reg.call("get_user", GET_USER), Reason.KNOWN_UNFIXABLE)
    assert store.get_active(stale.fingerprint).losses == 1


async def test_op_error_while_applying_a_fix_becomes_an_abort(
    api, store, make_registry
):
    reg = await make_registry()
    api.set_mutation("M1")
    broken = {
        "op": "move",
        "from": ["data", "id"],
        "to": ["id"],
    }  # the reply has no `data`
    store.save_fix(m1_fix([MOVE_CUSTOMER], [broken]))

    unrecoverable(await reg.call("get_user", GET_USER), Reason.UNSAFE_PATCH)

    (event,) = store.audit_events()
    assert (event.outcome, event.reason) == (HealOutcome.ABORTED, Reason.UNSAFE_PATCH)


async def test_store_failure_on_commit_is_a_failed_heal(
    api, store, make_registry, monkeypatch
):
    def boom(fix):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(store, "save_fix", boom)
    reg = await make_registry()
    api.set_mutation("M1")

    unrecoverable(await reg.call("get_user", GET_USER), Reason.VERIFY_FAILED)

    (event,) = store.audit_events()
    assert event.outcome is HealOutcome.VERIFY_FAILED
    assert reg.defs["get_user"].active_fix is None


async def test_transient_replay_failure_is_not_negative_cached(
    api, store, wire, make_registry
):
    reg = await make_registry()
    api.set_mutation("M1")
    inner, lookups = wire.handle_async_request, []

    async def flaky(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/lookup":
            lookups.append(request)
            if len(lookups) == 2:  # the heal's replay
                raise httpx.ConnectError("blip", request=request)
        return await inner(request)

    wire.handle_async_request = flaky

    unrecoverable(await reg.call("get_user", GET_USER), Reason.VERIFY_FAILED)
    assert not store.is_negative(store.audit_events()[0].fingerprint)
    assert await reg.call("get_user", GET_USER) == USER


# ---- spec v3 (C11): value errors, E3, E4/E6 replay, timing, spec mode, redaction ----


def override(wire, path: str, make) -> list[httpx.Request]:
    """Answer requests to `path` with `make(request)` (None passes through); returns those seen."""
    inner, seen = wire.handle_async_request, []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == path and (response := make(request)) is not None:
            seen.append(request)
            return response
        return await inner(request)

    wire.handle_async_request = handler
    return seen


def unprocessable(*items: tuple[str, list[str]]):
    detail = [{"type": t, "loc": loc, "msg": "x"} for t, loc in items]
    return lambda request: httpx.Response(422, json={"detail": detail})


class ManualClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


async def test_ac_21_c3_value_error_is_business_not_drift(
    api, store, client, make_registry
):
    reg = await make_registry()
    args = {"user_id": "123", "email": "not-an-email"}

    result = await reg.call("update_email", args)

    assert len(calls_to(api, "/users/email")) == 1  # no replay
    direct = await client.patch("/users/email", json=args)
    assert direct.status_code == 422
    assert result == {
        "error": "API_ERROR",
        "class": "BUSINESS",
        "status": "422",
        "detail": direct.json(),  # the API's own body, unchanged
    }
    assert api.state()["users"]["123"]["email"] == "ada@example.com"
    assert reg.defs["update_email"].active_fix is None
    (event,) = store.audit_events()
    assert (event.cls, event.outcome, event.reason, event.fix_id) == (
        ErrorClass.E2,
        HealOutcome.NOT_DRIFT,
        Reason.NOT_DRIFT,
        None,
    )
    assert json.loads(event.raw_error)["violations"] == [
        ["req", ["body", "email"], "pattern"]
    ]
    again = await reg.call("update_email", args)  # NOT_DRIFT is never negative-cached
    assert again == result and len(store.audit_events()) == 2


async def test_fr_3_4_empty_diff_with_a_stale_active_fix_replays_the_base_request(
    api, store, make_registry
):
    reg = await make_registry()
    api.set_mutation("M1")
    assert await reg.call("get_user", GET_USER) == USER  # M1 fix is active
    api.set_mutation(None)  # the API rolls back to v1
    before = len(calls_to(api, "/users/lookup"))

    assert await reg.call("get_user", GET_USER) == USER

    # the stale fix is rejected, then the unchanged base request goes out once
    sent = [r["body"] for r in calls_to(api, "/users/lookup")[before:]]
    assert sent == [{"customer_id": "123"}, {"user_id": "123"}]
    event = store.audit_events()[-1]
    assert (event.outcome, event.tier, event.path) == (
        HealOutcome.RECOVERED,
        Tier.T1,
        DecisionPath.diff,
    )
    assert reg.defs["get_user"].active_fix.request_ops == []
    assert await reg.call("get_user", GET_USER) == USER
    assert len(store.audit_events()) == 2  # the empty fix serves the next call


async def test_fr_3_4_empty_diff_without_an_active_fix_is_no_candidate(
    api, store, wire, make_registry
):
    reg = await make_registry()
    seen = override(
        wire, "/users/lookup", unprocessable(("missing", ["body", "user_id"]))
    )

    result = await reg.call("get_user", GET_USER)

    unrecoverable(result, Reason.NO_CANDIDATE)
    assert len(seen) == 1  # the spec explains nothing, so nothing is replayed
    assert reg.defs["get_user"].active_fix is None
    (event,) = store.audit_events()
    assert (event.outcome, event.reason) == (HealOutcome.ABORTED, Reason.NO_CANDIDATE)


async def test_fr_3_4_mixed_value_and_structural_violations_are_structural(
    api, store, wire, make_registry
):
    reg = await make_registry()
    seen = override(
        wire,
        "/users/email",
        unprocessable(
            ("string_pattern_mismatch", ["body", "email"]),
            ("missing", ["body", "nonce"]),
        ),
    )

    result = await reg.call("update_email", {"user_id": "123", "email": "a@b.co"})

    unrecoverable(result, Reason.NO_CANDIDATE)  # not NOT_DRIFT
    assert len(seen) == 1
    assert store.audit_events()[0].outcome is HealOutcome.ABORTED


async def test_ac_25_e3_undecodable_body_is_unsupported_class(
    api, store, wire, make_registry
):
    reg = await make_registry()

    def html(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"<html>down for maintenance</html>",
            headers={"content-type": "text/html"},
        )

    seen = override(wire, "/users/lookup", html)

    result = await reg.call("get_user", GET_USER)

    unrecoverable(result, Reason.UNSUPPORTED_CLASS, cls="E3")
    assert len(seen) == 1  # nothing replayed
    assert len(calls_to(api, "/openapi.json")) == 1  # nor diagnosed: the load only
    (event,) = store.audit_events()
    assert (event.cls, event.outcome, event.reason, event.fix_id) == (
        ErrorClass.E3,
        HealOutcome.ABORTED,
        Reason.UNSUPPORTED_CLASS,
        None,
    )
    assert reg.defs["get_user"].active_fix is None
    # FR-11.3: an unsupported class is remembered like any other unfixable break
    unrecoverable(
        await reg.call("get_user", GET_USER), Reason.KNOWN_UNFIXABLE, cls="E3"
    )
    assert len(seen) == 2  # only the original send


def soft_error_for_old_shape(request: httpx.Request) -> httpx.Response | None:
    """E4: the API answers 200 with an error body to the v1 request, and works for the new one."""
    if b"customer_id" in request.content:
        return None
    return httpx.Response(200, json={"success": False, "error": "unknown field"})


async def test_ac_20_e4_on_non_idempotent_tool_without_key_is_unsafe_replay(
    api, store, wire, tools_config, make_registry
):
    tools_config["tools"]["get_user"]["idempotent"] = False
    reg = await make_registry()
    api.set_mutation("M1")
    seen = override(wire, "/users/lookup", soft_error_for_old_shape)

    result = await reg.call("get_user", GET_USER)

    unrecoverable(result, Reason.UNSAFE_REPLAY, cls="E4")
    assert len(seen) == 1 and calls_to(api, "/users/lookup") == []  # never replayed
    (event,) = store.audit_events()
    assert (event.cls, event.outcome, event.reason) == (
        ErrorClass.E4,
        HealOutcome.ABORTED,
        Reason.UNSAFE_REPLAY,
    )


async def test_ac_20_e4_on_idempotent_tool_is_replayed(api, store, wire, make_registry):
    reg = await make_registry()
    api.set_mutation("M1")
    seen = override(wire, "/users/lookup", soft_error_for_old_shape)

    assert await reg.call("get_user", GET_USER) == USER

    assert len(seen) == 1
    assert [r["body"] for r in calls_to(api, "/users/lookup")] == [
        {"customer_id": "123"}
    ]
    (event,) = store.audit_events()
    assert (event.cls, event.outcome) == (ErrorClass.E4, HealOutcome.RECOVERED)


async def test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal(
    api, store, wire, make_registry
):
    clock = ManualClock()
    reg = await make_registry(clock=clock)
    api.set_mutation("M1")
    lookups, slow_spec = [], []
    inner = wire.handle_async_request

    async def timed(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/users/lookup":
            lookups.append(request)
            if len(lookups) == 2:  # call 1's replay: the connection drops after 2 s
                clock.t += 2.0
                raise httpx.ConnectError("blip", request=request)
        if request.url.path == "/openapi.json" and slow_spec:
            clock.t += 0.3
        return await inner(request)

    wire.handle_async_request = timed

    unrecoverable(await reg.call("get_user", GET_USER), Reason.VERIFY_FAILED)
    clock.t = 10.0
    slow_spec.append(True)
    assert await reg.call("get_user", GET_USER) == USER

    failed, healed = store.audit_events()
    assert (failed.mttr_ms, failed.heal_ms) == (2000, 2000)
    assert healed.fingerprint == failed.fingerprint
    assert healed.heal_ms == 300  # this heal: detected at 10.0, done at 10.3
    assert healed.mttr_ms == 10300  # the break was first seen at 0.0

    # once recovered the fingerprint starts over: no stale first-seen time
    clock.t = 20.0
    reg.defs["get_user"].active_fix = None
    assert await reg.call("get_user", GET_USER) == USER
    again = store.audit_events()[-1]
    assert (again.tier, again.mttr_ms, again.heal_ms) == (Tier.T0, 0, 0)


async def test_fr_6_4_spec_mode_off_diagnoses_from_the_error_alone(
    api, store, make_registry
):
    reg = await make_registry(spec_mode="off")
    api.set_mutation("M1")
    fetches = len(calls_to(api, "/openapi.json"))

    assert await reg.call("get_user", GET_USER) == USER

    assert len(calls_to(api, "/openapi.json")) == fetches
    (event,) = store.audit_events()
    assert (event.outcome, event.path) == (HealOutcome.RECOVERED, DecisionPath.clue)


async def test_fr_6_4_spec_mode_off_aborts_a_combined_change(api, store, make_registry):
    reg = await make_registry(spec_mode="off")
    api.set_mutation("M5")  # nested field plus a header: only the spec explains it

    unrecoverable(await reg.call("get_user", GET_USER), Reason.NO_CANDIDATE)

    assert len(calls_to(api, "/users/lookup")) == 1
    assert store.audit_events()[0].path is DecisionPath.clue


async def test_fr_6_4_spec_mode_must_be_on_or_off(client, tools_config):
    with pytest.raises(ValueError):
        Registry(client, tools_config, {}, spec_mode="OFF")


JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
)


async def test_ac_24_audit_raw_error_is_redacted(api, store, wire, make_registry):
    # An API that echoes the caller's credentials back in its 422 body.
    echo = {
        "detail": [
            {
                "type": "missing",
                "loc": ["body", "customer_id"],
                "msg": "Field required",
                "input": {"auth": "Bearer test-token", "tenant": "t-1"},
                "jwt": JWT,
                "access_token": "opaque-token-value",
            }
        ]
    }

    def old_shape(request: httpx.Request):
        if b"customer_id" in request.content:
            return None
        return httpx.Response(422, json=echo)

    reg = await make_registry()
    assert set(reg.cfg.values()) == {
        "Bearer test-token",
        "t-1",
    }  # what the echo carries
    api.set_mutation("M1")
    override(wire, "/users/lookup", old_shape)

    assert await reg.call("get_user", GET_USER) == USER

    (event,) = store.audit_events()
    leaks = [*reg.cfg.values(), "test-token", JWT, "opaque-token-value"]
    assert [leak for leak in leaks if leak in event.raw_error] == []
    blob = json.loads(event.raw_error)
    assert blob["code"] == "422"
    assert blob["violations"] == [["req", ["body", "customer_id"], "missing"]]
    assert len(event.raw_error) <= RAW_ERROR_MAX
