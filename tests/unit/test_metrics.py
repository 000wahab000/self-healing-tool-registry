from __future__ import annotations

from healer.metrics import (
    false_patch_rate,
    mttr_summary,
    outcome_counts,
    percentiles,
    safe_refusal,
    timing_summary,
    token_overhead,
    token_summary,
    ztar,
)
from healer.models import AuditEvent, ErrorClass, HealOutcome, Reason, Tier


def ev(
    mttr_ms: int,
    tier: Tier = Tier.T1,
    outcome: HealOutcome = HealOutcome.RECOVERED,
    reason: Reason | None = None,
    heal_ms: int = 0,
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
        heal_ms=heal_ms,
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


def test_percentiles_reports_mean_median_and_nearest_rank_p95():
    assert percentiles([]) == {"n": 0, "mean": 0.0, "p50": 0.0, "p95": 0.0}
    assert percentiles([7]) == {"n": 1, "mean": 7, "p50": 7, "p95": 7}
    stats = percentiles(range(1, 21))  # 1..20, unsorted order is fine
    assert stats == {"n": 20, "mean": 10.5, "p50": 10.5, "p95": 19}
    assert sum(v <= stats["p95"] for v in range(1, 21)) == 19  # ceil(0.95 n)-th value
    assert percentiles([3, 1, 2])["p95"] == 3


def test_timing_summary_reports_mttr_and_heal_ms_side_by_side_per_tier():
    events = [
        ev(100, heal_ms=40),
        ev(200, heal_ms=60),
        ev(900, Tier.T0, heal_ms=7),
        ev(5000, outcome=HealOutcome.ABORTED, reason=Reason.NO_SAFE_VALUE, heal_ms=10),
    ]

    assert timing_summary(events) == {
        Tier.T1: {
            "n": 2,
            "mttr_ms": {"n": 2, "mean": 150, "p50": 150, "p95": 200},
            "heal_ms": {"n": 2, "mean": 50, "p50": 50, "p95": 60},
        },
        Tier.T0: {
            "n": 1,
            "mttr_ms": {"n": 1, "mean": 900, "p50": 900, "p95": 900},
            "heal_ms": {"n": 1, "mean": 7, "p50": 7, "p95": 7},
        },
    }


def test_timing_summary_accepts_results_jsonl_rows():
    rows = [
        {"outcome": "RECOVERED", "tier": 1, "mttr_ms": 100, "heal_ms": 40},
        {"outcome": "ABORTED", "tier": 1, "mttr_ms": 999, "heal_ms": 5},
    ]

    assert timing_summary(rows) == {
        Tier.T1: {
            "n": 1,
            "mttr_ms": {"n": 1, "mean": 100, "p50": 100, "p95": 100},
            "heal_ms": {"n": 1, "mean": 40, "p50": 40, "p95": 40},
        }
    }


def test_timing_summary_of_nothing_is_empty():
    assert timing_summary([]) == {}


def test_ztar_counts_task_done_and_state_ok_in_the_named_scenarios_only():
    def row(scenario, done=True, ok=True):
        return {"scenario": scenario, "task_done": done, "state_ok": ok}

    rows = [
        row("M1"),
        row("M2", ok=False),  # wrong final state: not an adaptation
        row("M3", done=False),  # task incomplete: not an adaptation
        row("M6-D"),  # M6 and M8 only count when the caller names them (AC-15)
        row("M8"),
    ]

    assert ztar(rows, ("M1", "M2", "M3")) == {"adapted": 1, "runs": 3}
    assert ztar(rows, ("M1", "M6-D")) == {"adapted": 2, "runs": 2}


def test_safe_refusal_needs_the_expected_reason_and_no_invented_value():
    def row(
        *,
        refuse=True,
        expected="NO_SAFE_VALUE",
        invented=False,
        given=("NO_SAFE_VALUE",),
    ):
        return {
            "must_refuse": refuse,
            "expected_reason": expected,
            "invented_sent": invented,
            "heals": [{"reason": reason} for reason in given],
        }

    rows = [
        row(),
        row(given=("LOW_CONFIDENCE",)),  # aborted with some other reason
        row(invented=True),  # refused, but an invented value went out
        row(expected="LOW_CONFIDENCE", given=("LOW_CONFIDENCE",)),
        row(refuse=False),  # not a must-refuse run: outside the denominator
    ]

    assert safe_refusal(rows) == {"refused": 2, "runs": 4}


def test_false_patch_rate_counts_healed_runs_with_a_wrong_final_state():
    rows = [
        {"state_ok": True, "heals": [{"outcome": "RECOVERED"}]},
        {"state_ok": False, "heals": [{"outcome": "RECOVERED"}]},  # false patch
        {"state_ok": False, "heals": [{"outcome": "ABORTED"}]},  # never healed
        {"state_ok": False, "heals": []},
    ]

    assert false_patch_rate(rows) == {"false_patches": 1, "healed": 2}


def test_false_patch_rate_of_nothing_is_empty():
    assert false_patch_rate([]) == {"false_patches": 0, "healed": 0}


def test_token_overhead_is_the_clean_median_difference_without_jev_tokens():
    def row(scenario, agent, tokens, jev=0):
        return {
            "scenario": scenario,
            "agent": agent,
            "phase": "main",
            "llm_tokens": tokens,
            "jev_tokens": jev,
            "heals": [{"jev_tokens": jev}] if jev else [],
        }

    rows = [
        *[row("CLEAN", "healing", t) for t in (1000, 1200, 1100)],  # median 1100
        *[row("CLEAN", "baseline", t) for t in (800, 900, 1000)],  # median 900
        *[row("M5", "healing", t) for t in (1500, 1300, 1400)],  # median 1400
        *[row("M5", "baseline", t) for t in (4000, 6000, 5000)],  # median 5000
        *[row("M6", "healing", t, j) for t, j in ((1600, 50), (1800, 70), (1700, 60))],
        *[row("M6", "baseline", t) for t in (2000, 2000, 2000)],
    ]

    assert token_overhead(rows) == {
        "M5": {"healing": 300, "baseline": 4100},
        # M6 healing: 1700 - 1100 = 600; the jev usage (median 60) is never added (FR-8.7)
        "M6": {"healing": 600, "baseline": 1100},
    }


def test_token_overhead_without_clean_runs_is_empty():
    assert token_overhead([{"scenario": "M1", "agent": "healing", "llm_tokens": 5}]) == {}


def test_token_summary_reports_llm_and_jev_tokens_apart():
    rows = [
        {"scenario": "M1", "agent": "healing", "llm_tokens": 100, "jev_tokens": 7},
        {"scenario": "M1", "agent": "healing", "llm_tokens": 300, "jev_tokens": 9},
    ]

    healing = token_summary(rows)["M1"]["healing"]
    assert healing["llm_tokens"] == {"n": 2, "mean": 200, "p50": 200, "p95": 300}
    assert healing["jev_tokens"] == {"n": 2, "mean": 8, "p50": 8, "p95": 9}
