from __future__ import annotations

from healer import diagnose, fingerprint
from healer.models import (
    ErrorClass,
    FixStatus,
    HealOutcome,
    Outcome,
    Reason,
    Side,
    Tier,
    Violation,
)

USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}


async def test_ac_40_sibling_propagation(api, make_registry, store):
    """(STRETCH, S1) Sibling propagation: a second tool hit by the same rename
    heals at Tier-0 speed (<500 ms) on its first occurrence (FR-17.1, FR-17.2, AC-40)."""
    reg = await make_registry()
    api.set_mutation("S1")  # user_id -> customer_id on both get_user and update_email

    # 1. Call get_user: Tier-1 heals it and post-commit propagates candidate to update_email
    user = await reg.call("get_user", {"user_id": "123"})
    assert user["id"] == "123"

    events = store.audit_events()
    assert len(events) == 1
    assert events[0].tool == "get_user"
    assert events[0].tier == Tier.T1
    assert events[0].outcome == HealOutcome.RECOVERED

    # Sibling candidate fix should be stored in the store with status=candidate
    cand_fp, _ = fingerprint.fingerprint(
        "update_email",
        Outcome(
            ErrorClass.E2,
            "rest",
            "422",
            violations=[Violation(Side.REQ, ["body", "customer_id"], "missing")],
        ),
    )
    cand = store.get_candidate(cand_fp)
    assert cand is not None
    assert cand.status == FixStatus.candidate
    assert cand.tool == "update_email"

    # 2. Call update_email: sibling experiences the break for the first time.
    # It recovers at Tier-0 speed (<500 ms) using the pre-generated candidate fix.
    email_res = await reg.call(
        "update_email", {"user_id": "123", "email": "ada.sibling@example.com"}
    )
    assert email_res == {"id": "123", "email": "ada.sibling@example.com"}

    events2 = store.audit_events()
    assert len(events2) == 2
    sibling_event = events2[1]
    assert sibling_event.tool == "update_email"
    assert sibling_event.tier == Tier.T0
    assert sibling_event.outcome == HealOutcome.RECOVERED
    assert sibling_event.heal_ms < 500

    # Candidate should now be promoted to active in the store
    assert store.get_candidate(cand_fp) is None
    active = store.get_active(cand_fp)
    assert active is not None
    assert active.status == FixStatus.active


async def test_ac_44_rule_mining(api, make_registry, store):
    """(STRETCH, S2) Rule mining: after 3 wins of the same pattern, subsequent ambiguous breaks
    heal without Jev (FR-17.8, AC-44)."""
    # 1. Without Jev and without a mined rule, M6-N aborts LOW_CONFIDENCE on write tool
    reg = await make_registry(jev=None)
    api.set_mutation("M6-N")

    broken = await reg.call("set_manager", {"user_id": "123", "manager_id": "456"})
    assert broken["error"] == "SCHEMA_DRIFT_UNRECOVERABLE"
    assert broken["reason"] == Reason.LOW_CONFIDENCE.value

    # Compute abstract signature for straight rename pattern
    # In M6-N: removed [user_id, manager_id], added [subject, supervisor]
    # Straight mapping: user_id -> subject, manager_id -> supervisor
    entries = [
        {"change": "removed", "side": Side.REQ, "path": ["body", "user_id"]},
        {"change": "removed", "side": Side.REQ, "path": ["body", "manager_id"]},
        {"change": "added", "side": Side.REQ, "path": ["body", "subject"]},
        {"change": "added", "side": Side.REQ, "path": ["body", "supervisor"]},
    ]
    straight_ops = [
        {"op": "move", "from": ["body", "user_id"], "to": ["body", "subject"]},
        {"op": "move", "from": ["body", "manager_id"], "to": ["body", "supervisor"]},
    ]
    pattern = diagnose.abstract_signature(straight_ops, entries)

    # 2. Record 3 wins for this structural pattern
    assert store.is_rule(pattern) is False
    store.record_rule_win(pattern)
    store.record_rule_win(pattern)
    store.record_rule_win(pattern)
    assert store.is_rule(pattern) is True

    # 3. Clear negative cache so the same fingerprint can be retried with the mined rule
    store._neg.clear()
    recovered = await reg.call(
        "set_manager", {"user_id": "123", "manager_id": "456"}
    )
    assert recovered == {"id": "123", "manager_id": "456"}
    assert api.state()["users"]["123"]["manager_id"] == "456"

    events = [e for e in store.audit_events() if e.outcome == HealOutcome.RECOVERED]
    assert len(events) == 1
    assert events[0].tool == "set_manager"

