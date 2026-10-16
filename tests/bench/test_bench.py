"""Benchmark runner and report tests (FR-15.1 to 15.8; AC-14, AC-15, AC-16, AC-17, AC-23).

One scripted run of every v3 scenario covers the whole report: the healable mutations, the
M6 split, M8, the controls and the clean baseline (FR-15.1), plus the tier-0 rerun and the
error-only ablation of M1 to M9 (FR-15.7). The run is offline: no Jev, no LLM key.
"""

from __future__ import annotations

import json

import pytest

from bench import run as bench_run
from bench.oracle import classify_request, classify_run
from healer.metrics import (
    false_patch_rate,
    safe_refusal,
    timing_summary,
    token_overhead,
    ztar,
)
from healer.models import Reason, Tier

SCENARIOS = bench_run.DEFAULT_SCENARIOS  # CLEAN, M1-M9 (M6 split), C1-C3 (FR-15.1)


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench")
    with pytest.MonkeyPatch.context() as env:  # offline: no Jev, no LLM
        for key in ("JEV_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY"):
            env.delenv(key, raising=False)
        bench_run.main(["--agent", "scripted", "--n", "1", "--out", str(out)])
    return out


@pytest.fixture(scope="module")
def rows(out):
    text = (out / "results.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


@pytest.fixture(scope="module")
def main(rows):
    return [r for r in rows if r["phase"] == "main"]


@pytest.fixture(scope="module")
def report(out):
    return (out / "report.md").read_text(encoding="utf-8")


def one(rows, scenario, agent, phase="main"):
    (row,) = [
        r for r in rows if (r["scenario"], r["agent"], r["phase"]) == (scenario, agent, phase)
    ]
    return row


def agent_rows(main, agent):
    return [r for r in main if r["agent"] == agent]


def section(report, heading):
    """The text from one `##` heading to the next (or the end of the report)."""
    return report.split(heading, 1)[1].split("\n## ", 1)[0]


def test_one_row_per_scenario_agent_per_tier0_rerun_and_ablation(rows):
    expected = {
        (s, a, "main") for s in SCENARIOS.split(",") for a in bench_run.AGENTS
    }  # FR-15.1: every scenario x both agents
    expected |= {(s, "healing", "tier0") for s in bench_run.TIER0_SCENARIOS}  # FR-15.1
    expected |= {(s, "healing", "ablation") for s in bench_run.ABLATION_SCENARIOS}  # FR-15.7
    assert len(rows) == len(expected)
    assert {(r["scenario"], r["agent"], r["phase"]) for r in rows} == expected
    assert {r["mode"] for r in rows} == {"scripted"}
    # spec_mode on for the main and tier-0 passes, off only for the ablation (FR-6.4)
    assert {r["spec_mode"] for r in rows if r["phase"] != "ablation"} == {"on"}
    assert {r["spec_mode"] for r in rows if r["phase"] == "ablation"} == {"off"}


def test_clean_run_completes_for_both_agents(main):  # FR-15.6 token baselines
    for agent in bench_run.AGENTS:
        row = one(main, "CLEAN", agent)
        assert (row["task_done"], row["tool_calls"], row["heals"]) == (True, 4, [])


@pytest.mark.parametrize("scenario", bench_run.HEALABLE_MUTATIONS)
def test_healing_recovers_every_healable_mutation(main, scenario):
    healing = one(main, scenario, "healing")
    assert (healing["task_done"], healing["state_ok"], healing["expectation_met"]) == (
        True,
        True,
        True,
    )
    assert [h["outcome"] for h in healing["heals"]] == ["RECOVERED"]


@pytest.mark.parametrize("scenario", ["M1", "M2", "M4", "M5"])
def test_baseline_re_sends_the_same_arguments_until_the_cap(main, scenario):
    baseline = one(main, scenario, "baseline")
    assert (baseline["task_done"], baseline["hit_limit"], baseline["tool_calls"]) == (
        False,
        True,
        10,
    )


def test_m8_is_refused_and_no_priority_is_invented(main):
    healing = one(main, "M8", "healing")
    assert healing["task_done"] is False
    assert [h["reason"] for h in healing["heals"]] == ["NO_SAFE_VALUE"]
    assert healing["priority_sent"] is False
    assert healing["invented_sent"] is False
    assert healing["must_refuse"] is True
    assert healing["expectation_met"] is True
    assert healing["oracle"] == "REJECTED"
    assert not any(
        request["path"] == "/tickets" and "priority" in (request["body"] or {})
        for request in healing["requests"]
    )


def test_m7_original_successful_request_is_wrong_even_if_response_is_200(main):
    row = one(main, "M7", "healing")
    assert row["oracle"] == "CORRECT"
    assert row["oracle"] != "WRONG_ACCEPTED"
    assert all(set(request["headers"].values()) <= {True, False} for request in row["requests"])


def test_m7_accepted_original_body_is_wrong_according_to_request_oracle():
    from mock_api.app import EXPECTED_CANONICAL

    expected = EXPECTED_CANONICAL["M7"]
    request = {
        "method": "PATCH",
        "path": "/users/email",
        "body": {"user_id": "123", "email": "ada.new@example.com"},
        "query": {},
        "headers": {},
    }
    received = {**request, "status": 200, "headers": {}}

    assert classify_request(expected, request, 200, {}) == "WRONG_ACCEPTED"
    assert classify_run(expected, [request], [received], {}) == "WRONG_ACCEPTED"


@pytest.mark.parametrize(
    ("scenario", "header", "value"),
    [("M4", "authorization", "Bearer expected"), ("M5", "x-tenant-id", "tenant-expected")],
)
def test_oracle_resolves_secret_references_without_serializing_values(scenario, header, value):
    from mock_api.app import EXPECTED_CANONICAL

    cfg = {"OAUTH_BEARER": "Bearer expected", "TENANT_ID": "tenant-expected"}
    expected = EXPECTED_CANONICAL[scenario]
    request = {
        "method": expected["method"],
        "path": expected["path"],
        "body": expected["body"],
        "query": expected["query"],
        "headers": {header: value},
    }

    assert classify_request(expected, request, 200, cfg) == "CORRECT"
    row = one(
        [
            {
                "scenario": scenario,
                "agent": "healing",
                "phase": "main",
                "oracle": classify_request(expected, request, 200, cfg),
                "requests": [{"headers": {header: True}}],
            }
        ],
        scenario,
        "healing",
    )
    assert value not in json.dumps(row)


def test_bench_rows_have_only_secret_safe_request_metadata(main):
    for row in main:
        for request in row["requests"]:
            assert set(request["headers"].values()) <= {True, False}
            assert "Bearer test-token" not in json.dumps(request)
        assert row["oracle"] in {"CORRECT", "WRONG_ACCEPTED", "REJECTED"}


def test_m6_n_aborts_low_confidence_without_a_write_when_jev_is_absent(main):
    healing = one(main, "M6-N", "healing")
    assert [h["reason"] for h in healing["heals"]] == ["LOW_CONFIDENCE"]
    assert healing["must_refuse"] is True
    assert healing["invented_sent"] is False
    assert (healing["state_ok"], healing["expectation_met"]) == (True, True)


def test_m6_d_heals_through_the_deterministic_tie_breaker(main):
    healing = one(main, "M6-D", "healing")
    assert (healing["task_done"], healing["state_ok"], healing["expectation_met"]) == (
        True,
        True,
        True,
    )
    assert [(h["outcome"], h["path"]) for h in healing["heals"]] == [
        ("RECOVERED", "tiebreak")
    ]


@pytest.mark.parametrize("scenario", ["C2", "C3"])
def test_controls_pass_through_with_not_drift(main, scenario):
    healing = one(main, scenario, "healing")
    assert [h["reason"] for h in healing["heals"]] == ["NOT_DRIFT"]
    assert healing["state_ok"] is True
    assert healing["expectation_met"] is True


@pytest.mark.parametrize("scenario", bench_run.TIER0_SCENARIOS)
def test_tier0_rerun_is_served_from_the_stored_fix(rows, scenario):
    row = one(rows, scenario, "healing", "tier0")
    assert (row["task_done"], row["state_ok"]) == (True, True)
    assert [(h["tier"], h["path"]) for h in row["heals"]] == [(0, "cache")]


def test_ac_14_mttr_and_heal_ms_reported_per_tier_with_p95_targets(main, rows, report):
    """AC-14: tier-1 MTTR p95 < 4.0 s for M1 to M5 (tier 0 < 0.5 s), heal_ms alongside."""
    # both metrics, both tiers, mean/p50/p95 in one table
    assert (
        "| Tier | n | mttr_ms mean / p50 / p95 | heal_ms mean / p50 / p95 |" in report
    )
    tiers = section(report, "## Timings by tier (FR-15.4, AC-14)")
    assert "| 1 |" in tiers and "| 0 |" in tiers
    # and per scenario in the table, next to the ZTAR columns
    assert "| MTTR tier 1 | MTTR tier 0 | heal_ms tier 1 | heal_ms tier 0 |" in report

    healing = agent_rows(main, "healing")
    for scenario in bench_run.TIER0_SCENARIOS:
        stats = timing_summary(
            h for r in healing if r["scenario"] == scenario for h in r["heals"]
        )
        assert stats[Tier.T1]["n"] >= 1
        assert stats[Tier.T1]["mttr_ms"]["p95"] < 4000
        assert stats[Tier.T1]["heal_ms"]["p95"] < 4000
        assert stats[Tier.T1]["heal_ms"]["p50"] > 0  # heal time really is recorded
    tier0 = timing_summary(
        h for r in rows if r["phase"] == "tier0" for h in r["heals"]
    )[Tier.T0]
    assert tier0["n"] == len(bench_run.TIER0_SCENARIOS)
    assert tier0["mttr_ms"]["p95"] < 500
    assert tier0["heal_ms"]["p95"] < 500


def test_ac_15_ztar_safe_refusal_false_patch_and_m6_reported_separately(main, report):
    """AC-15: ZTAR 100% over the healable mutations with Jev absent, M6 separate,
    Safe-Refusal 100% over M8 and M6-N, False-Patch 0."""
    healing, baseline = agent_rows(main, "healing"), agent_rows(main, "baseline")

    # ZTAR counts the healable mutations only; M6, M8 and the controls stay out (AC-15)
    assert not set(bench_run.HEALABLE_MUTATIONS) & {"M6-D", "M6-N", "M8"}
    assert ztar(healing, bench_run.HEALABLE_MUTATIONS) == {"adapted": 7, "runs": 7}
    assert ztar(baseline, bench_run.HEALABLE_MUTATIONS)["runs"] == 7  # measured, not gated
    assert "- Healable mutations (M1, M2, M3, M4, M5, M7, M9), healing: 100% (7/7)" in report

    # M6 in both configurations, reported on its own lines (never folded into the above)
    m6d = next(x for x in report.splitlines() if x.startswith("- M6-D, reported separately"))
    m6n = next(x for x in report.splitlines() if x.startswith("- M6-N, reported separately"))
    assert "healing 100% (1/1)" in m6d
    assert "healing 0% (0/1)" in m6n  # Jev disabled: aborts LOW_CONFIDENCE by design

    # Safe-Refusal Rate over the must-refuse runs, no invented value sent
    assert safe_refusal(healing) == {"refused": 2, "runs": 2}
    assert "Safe-Refusal Rate: 100% (2/2) over M6-N, M8 runs" in report
    assert not any(r["invented_sent"] for r in healing if r["must_refuse"])

    # False-Patch Rate: every healed run ended with the correct final state
    assert false_patch_rate(healing) == {"false_patches": 0, "healed": 8}
    assert "False-Patch Rate: 0% (0/8)" in report
    assert "M8 is a refusal, not an adaptation" in report


def test_ac_16_token_overhead_against_clean_median_with_jev_in_its_own_column(report):
    """AC-16: overhead = mutated total - CLEAN median, baseline waste beside it, the
    healing agent's overhead below the baseline's waste, jev_tokens never added."""

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
    ]
    for scenario in bench_run.HEALABLE_MUTATIONS:
        rows += [row(scenario, "healing", 1400), row(scenario, "baseline", 5000)]
    # M6-D carries a Jev decision: its jev_tokens live outside llm_tokens (FR-8.7)
    rows += [row("M6-D", "healing", 1400, jev=60), row("M6-D", "baseline", 5000)]

    overhead = token_overhead(rows)
    assert overhead["M5"] == {"healing": 300, "baseline": 4100}
    for scenario in (*bench_run.HEALABLE_MUTATIONS, "M6-D"):
        assert overhead[scenario]["healing"] < overhead[scenario]["baseline"]
    # jev usage is never part of the subtraction: 1400 - 1100 = 300, not 360
    assert overhead["M6-D"]["healing"] == 300

    assert "## Tokens (FR-8.7, FR-15.4, FR-15.5, AC-16)" in report
    assert (
        "| Scenario | Healing llm_tokens | Baseline llm_tokens | jev_tokens "
        "| Healing overhead | Baseline wasted | Ratio (healing : baseline) |" in report
    )
    assert "never added to `llm_tokens`" in report


def test_ac_17_baseline_outcomes_measured_for_every_scenario_not_asserted(main, report):
    """AC-17: error loop, calls, tokens and final data are measured per scenario and
    never asserted as pass or fail."""
    text = section(report, "## Baseline outcomes (FR-15.8, AC-17)")
    assert "never asserted as pass or fail" in text
    assert (
        "| Scenario | Runs | Error loop | Calls (mean) | Task state correct "
        "| State integrity |" in text
    )
    for scenario in SCENARIOS.split(","):
        assert f"| {scenario} | " in text
    for row in agent_rows(main, "baseline"):
        assert all(
            k in row
            for k in ("tool_calls", "hit_limit", "state_ok", "llm_tokens", "expectation_met")
        )


def test_ac_23_error_only_ablation_report_without_a_heal_threshold(rows, report):
    """AC-23: M1 to M9 re-run with spec_mode=off, per mutation healed or aborted with a
    reason code, False-Patch Rate 0, no heal-rate threshold asserted."""
    ablation = [r for r in rows if r["phase"] == "ablation"]
    assert {r["scenario"] for r in ablation} == set(bench_run.ABLATION_SCENARIOS)
    assert {r["spec_mode"] for r in ablation} == {"off"}
    assert {r["agent"] for r in ablation} == {"healing"}

    text = section(report, "## Error-only ablation (`spec_mode=off`, FR-15.7, AC-23)")
    assert "no heal-rate threshold" in text
    reasons = {reason.value for reason in Reason}
    for mid in bench_run.ABLATION_SCENARIOS:
        (line,) = [x for x in text.splitlines() if x.startswith(f"| {mid} |")]
        _, outcome, reason, final_state, false_patch = (
            c.strip() for c in line.strip("|").split("|")
        )
        assert outcome in {"healed", "aborted", "no heal attempt"}
        if outcome == "aborted":
            assert reason in reasons  # every abort carries a reason code
        assert final_state in {"correct", "wrong"}
        assert false_patch in {"yes", "no"}

    assert false_patch_rate(ablation)["false_patches"] == 0
    assert "False-Patch Rate (ablation): 0%" in text
