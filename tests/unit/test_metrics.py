from __future__ import annotations

from healer.metrics import mttr_summary, outcome_counts
from healer.models import AuditEvent, ErrorClass, HealOutcome, Reason, Tier


def ev(
    mttr_ms: int,
    tier: Tier = Tier.T1,
    outcome: HealOutcome = HealOutcome.RECOVERED,
    reason: Reason | None = None,
) -> AuditEvent:
    return AuditEvent(
        ts_ms=0,
        tool="get_user",
        fingerprint="f" * 16,
        cls=ErrorClass.E2,
        raw_code="422",
        tier=tier,
        path=None,
        fix_id=None,
        outcome=outcome,
        reason=reason,
        mttr_ms=mttr_ms,
    )


def test_mttr_summary_by_tier_uses_median_and_nearest_rank_p95():
    t1 = [ev(ms) for ms in range(2000, 0, -100)]  # 100..2000, unsorted on purpose
    t0 = [ev(ms, Tier.T0) for ms in (9, 5, 7)]

    summary = mttr_summary(t1 + t0)

    assert summary == {
        Tier.T1: {"n": 20, "p50_ms": 1050, "p95_ms": 1900},
        Tier.T0: {"n": 3, "p50_ms": 7, "p95_ms": 9},
    }


def test_mttr_summary_counts_only_recovered_events():
    events = [
        ev(300),
        ev(9000, outcome=HealOutcome.ABORTED, reason=Reason.NO_SAFE_VALUE),
        ev(8000, outcome=HealOutcome.VERIFY_FAILED, reason=Reason.VERIFY_FAILED),
        ev(7000, Tier.T0, HealOutcome.ABORTED, Reason.KNOWN_UNFIXABLE),
    ]

    assert mttr_summary(events) == {Tier.T1: {"n": 1, "p50_ms": 300, "p95_ms": 300}}


def test_mttr_summary_of_nothing_is_empty():
    assert mttr_summary([]) == {}


def test_outcome_counts_by_outcome_and_by_reason():
    events = [
        ev(1),
        ev(2),
        ev(3, outcome=HealOutcome.ABORTED, reason=Reason.NO_SAFE_VALUE),
        ev(4, outcome=HealOutcome.ABORTED, reason=Reason.NO_SAFE_VALUE),
        ev(5, Tier.T0, HealOutcome.ABORTED, Reason.KNOWN_UNFIXABLE),
        ev(6, outcome=HealOutcome.NOT_DRIFT, reason=Reason.NOT_DRIFT),
    ]

    assert outcome_counts(events) == {
        "by_outcome": {"RECOVERED": 2, "ABORTED": 3, "NOT_DRIFT": 1},
        "by_reason": {"NO_SAFE_VALUE": 2, "KNOWN_UNFIXABLE": 1, "NOT_DRIFT": 1},
    }


def test_outcome_counts_of_nothing_is_empty():
    assert outcome_counts([]) == {"by_outcome": {}, "by_reason": {}}
