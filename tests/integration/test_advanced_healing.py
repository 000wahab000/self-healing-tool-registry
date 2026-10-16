from __future__ import annotations

from healer import fingerprint
from healer.models import (
    ErrorClass,
    FixStatus,
    HealOutcome,
    Outcome,
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
