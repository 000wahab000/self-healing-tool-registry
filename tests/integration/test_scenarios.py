"""Phase 7 scenario suite: each mutation of the catalog, end to end through Registry.call."""

from __future__ import annotations

import json
import re

import httpx
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
    "M9": ErrorClass.E2,
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
        "M6-D": ("set_manager", {"user_id": "123", "manager_id": "456"}),
        "M6-N": ("set_manager", {"user_id": "123", "manager_id": "456"}),
        "M7": ("update_email", {"user_id": "123", "email": "new@example.com"}),
        "M8": ("create_ticket", {"user_id": "123", "title": "t"}),
        "M9": ("update_email", {"user_id": "123", "email": f"new{n}@example.com"}),
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


def check_m9(api, reg, n, args, result) -> None:
    assert result == {"id": "123", "email": args["email"]}
    assert api.state()["users"]["123"]["email"] == args["email"]
    sent = calls_to(api, "/users/email")[-1]["body"]
    assert sent == {"payload": {"user_id": "123", "email": args["email"]}}


CHECKS = {
    "M1": check_m1,
    "M2": check_m2,
    "M3": check_m3,
    "M4": check_m4,
    "M5": check_m5,
    "M9": check_m9,
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


async def test_ac_22_m9_request_nesting(api, store, make_registry):
    event = await assert_first_heal("M9", api, store, await make_registry())
    assert event.path is DecisionPath.diff


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
        # raw_error is an opaque blob (FR-5.7), but it is canonical JSON whose violations are
        # [side, path, kind] triples. The API's own error body is the only free text in it.
        blob = json.loads(e.raw_error)
        assert canonical.dumps(blob) == e.raw_error
        assert blob["code"] == e.raw_code
        for side, path, kind in blob["violations"]:
            assert side in {s.value for s in Side}
            assert all(isinstance(step, str | int) for step in path)
            assert re.fullmatch(r"[a-z_]+", kind)


async def test_ac_13_healable_mutations_heal_with_jev_down(
    api, store, jev, respx_mock, make_registry
):
    route = respx_mock.post("https://api.typesafe.ai/v1/systemone").mock(
        side_effect=httpx.ReadTimeout("down")
    )
    reg = await make_registry(jev=jev)

    for mid in ("M1", "M2", "M3", "M4", "M5", "M9"):
        api.reset()
        await reg.load()  # fresh tools against the v1 API, as after a restart
        api.set_mutation(mid)
        await run(mid, 0, api, reg)

    api.reset()
    await reg.load()
    api.set_mutation("M7")
    args = {"user_id": "123", "email": "new@example.com"}
    assert await reg.call("update_email", args) == {"id": "123", "email": args["email"]}

    assert route.call_count == 0  # one candidate each: Jev was never needed
    events = store.audit_events()
    assert [e.outcome for e in events] == [HealOutcome.RECOVERED] * 7
    assert {e.path for e in events} == {DecisionPath.diff}


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


async def test_ac_23_error_only_ablation(api, store, make_registry):
    """FR-15.7: Error-only ablation with spec_mode='off'.

    Run each mutation M1–M9 with the spec endpoint disabled (error-clue mode).
    Single-clue mutations (M1, M2, M4) recover; M3 needs the spec for E5 remap
    and aborts cleanly.  Combined/nested/ambiguous/silent/unfillable mutations abort
    with NO_CANDIDATE/LOW_CONFIDENCE/NO_SAFE_VALUE and never false-patch.
    False-Patch Rate must stay 0.
    """
    CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}
    reg = await make_registry(spec_mode="off")

    false_patch_count = 0

    for mid in ("M1", "M2", "M3", "M4", "M5", "M6-D", "M6-N", "M7", "M8", "M9"):
        api.set_mutation(mid)
        tool, args = call_for(mid)
        result = await reg.call(tool, args)

        # Detect false‑patch: a success result with wrong final mock state
        has_error = "error" in result
        if not has_error:
            # recovered – verify state correctness per mutation; count as false
            # patch only if state ends up wrong
            if mid == "M1":
                if result != USER or calls_to(api, "/users/lookup")[-1]["body"] != {"customer_id": "123"}:
                    false_patch_count += 1
            elif mid == "M2":
                if result != {"id": "123", "email": args["email"]} or api.state()["users"]["123"]["email"] != args["email"] or calls_to(api, "/users/email")[-1]["body"] != {"user_id": 123, "email": args["email"]}:
                    false_patch_count += 1
            elif mid == "M4":
                tickets = api.state()["tickets"]
                if len(tickets) != 1 or result.get("ticket_id") != tickets[-1]["ticket_id"] or calls_to(api, "/tickets")[-1].get("headers", {}).get("authorization") != CFG["OAUTH_BEARER"]:
                    false_patch_count += 1
            # M3, M5–M9 should not recover in error-clue mode; if they do, it's a false patch
            if mid != "M1" and mid != "M2" and mid != "M4":
                false_patch_count += 1

        # Enforce expected outcomes per mutation
        if mid in ("M1", "M2", "M4"):
            assert "error" not in result, (
                f"{mid} should RECOVERED in error-clue mode, got {result}"
            )
        elif mid == "M3":
            # E5 needs the spec for response remap; abort cleanly in error-clue mode
            assert "error" in result, (
                f"{mid} should abort (E5 needs spec) in error-clue mode, got {result}"
            )
        else:
            # Combined/nested/ambiguous/silent/unfillable mutations must abort cleanly
            if has_error:
                reason = result.get("reason", "")
                cls = result.get("class", "")
                acceptable = reason in ("NO_CANDIDATE", "LOW_CONFIDENCE", "NO_SAFE_VALUE", "KNOWN_UNFIXABLE", "POSTCHECK_FAILED_AFTER_WRITE")
                if not acceptable and cls != "E6":
                    raise AssertionError(
                        f"{mid} should abort with NO_CANDIDATE/LOW_CONFIDENCE/NO_SAFE_VALUE "
                        f"or leave E6 unhealed, got error={result}"
                    )
            else:
                # Unexpected recovery without error – count as false patch and fail
                raise AssertionError(
                    f"{mid} should not recover in error-clue mode, got {result}"
                )

    assert false_patch_count == 0, (
        f"False-Patch Rate must be 0, got {false_patch_count} false patches"
    )
