from __future__ import annotations

import asyncio
import json
import sqlite3

import httpx

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
from healer.store import Store

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


async def test_ac_07_m6_jev_correct_recovers(
    api, store, jev, respx_mock, make_registry
):
    route = respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT in text, 0.95)
    )
    reg = await make_registry(jev=jev)
    api.set_mutation("M6")

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


async def test_ac_07_m6_low_confidence_no_write(
    api, store, jev, respx_mock, make_registry
):
    respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT in text, 0.6)
    )
    reg = await make_registry(jev=jev)
    api.set_mutation("M6")

    result = await reg.call("set_manager", SET_MANAGER)

    unrecoverable(result, Reason.LOW_CONFIDENCE)
    assert (
        len(calls_to(api, "/users/manager")) == 1
    )  # only the original failing request
    assert api.state()["users"]["123"]["manager_id"] is None
    (event,) = store.audit_events()
    assert (event.outcome, event.reason, event.path) == (
        HealOutcome.ABORTED,
        Reason.LOW_CONFIDENCE,
        DecisionPath.jev,
    )
    assert event.jev_tokens > 0 and event.fingerprint == result["fingerprint"]


async def test_m6_confident_wrong_pick_is_caught_by_postcheck(
    api, store, jev, respx_mock, make_registry
):
    respx_mock.post(JEV_URL).mock(
        side_effect=jev_reply(lambda text: RIGHT not in text, 0.95)
    )
    reg = await make_registry(jev=jev)
    api.set_mutation("M6")

    result = await reg.call("set_manager", SET_MANAGER)

    unrecoverable(result, Reason.POSTCHECK_FAILED_AFTER_WRITE)
    (event,) = store.audit_events()
    assert (event.outcome, event.reason) == (
        HealOutcome.VERIFY_FAILED,
        Reason.POSTCHECK_FAILED_AFTER_WRITE,
    )
    assert reg.defs["set_manager"].active_fix is None
    assert store.get_active(event.fingerprint) is None
    again = await reg.call("set_manager", SET_MANAGER)
    unrecoverable(again, Reason.KNOWN_UNFIXABLE)


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


async def test_ac_13_jev_down_m6_aborts_others_heal(
    api, store, jev, respx_mock, make_registry
):
    route = respx_mock.post(JEV_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    reg = await make_registry(jev=jev)
    api.set_mutation("M6")

    for _ in range(2):
        down = await reg.call("set_manager", SET_MANAGER)
        unrecoverable(down, Reason.JEV_UNAVAILABLE)
    assert (
        route.call_count == 2
    )  # the second attempt was not short-circuited by the cache

    api.set_mutation("M1")
    assert await reg.call("get_user", GET_USER) == USER
    assert route.call_count == 2  # one candidate: Jev not consulted
    assert [e.reason for e in store.audit_events()] == [
        Reason.JEV_UNAVAILABLE,
        Reason.JEV_UNAVAILABLE,
        None,
    ]
    assert api.state()["users"]["123"]["manager_id"] is None


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
