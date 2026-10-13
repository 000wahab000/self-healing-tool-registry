from __future__ import annotations

import json

import pytest

from bench import run as bench_run

SCENARIOS = "CLEAN,M1,M5,M8"


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench")
    with pytest.MonkeyPatch.context() as env:  # offline: no Jev, no LLM
        for key in ("JEV_API_KEY", "OPENROUTER_API_KEY"):
            env.delenv(key, raising=False)
        argv = ["--agent", "scripted", "--n", "1", "--scenarios", SCENARIOS]
        bench_run.main([*argv, "--out", str(out)])
    return out


@pytest.fixture(scope="module")
def rows(out):
    text = (out / "results.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def one(rows, scenario, agent, phase="main"):
    (row,) = [
        r
        for r in rows
        if (r["scenario"], r["agent"], r["phase"]) == (scenario, agent, phase)
    ]
    return row


def test_one_row_per_scenario_agent_and_per_tier0_rerun(rows):
    expected = {
        (s, a, "main") for s in SCENARIOS.split(",") for a in ("healing", "baseline")
    }
    expected |= {("M1", "healing", "tier0"), ("M5", "healing", "tier0")}
    assert len(rows) == len(expected)
    assert {(r["scenario"], r["agent"], r["phase"]) for r in rows} == expected
    assert {r["mode"] for r in rows} == {"scripted"}


def test_clean_run_completes_for_both_agents(rows):
    for agent in ("healing", "baseline"):
        row = one(rows, "CLEAN", agent)
        assert (row["task_done"], row["tool_calls"], row["heals"]) == (True, 4, [])


@pytest.mark.parametrize("scenario", ["M1", "M5"])
def test_healing_completes_and_baseline_hits_the_cap(rows, scenario):
    healing, baseline = one(rows, scenario, "healing"), one(rows, scenario, "baseline")
    assert (healing["task_done"], healing["hit_limit"]) == (True, False)
    assert [h["outcome"] for h in healing["heals"]] == ["RECOVERED"]
    assert (baseline["task_done"], baseline["hit_limit"]) == (False, True)


def test_m8_is_refused_and_no_priority_is_invented(rows):
    healing = one(rows, "M8", "healing")
    assert healing["task_done"] is False
    assert [h["reason"] for h in healing["heals"]] == ["NO_SAFE_VALUE"]
    assert healing["priority_sent"] is False


@pytest.mark.parametrize("scenario", ["M1", "M5"])
def test_tier0_rerun_after_restart_heals_from_the_stored_fix(rows, scenario):
    row = one(rows, scenario, "healing", "tier0")
    assert row["task_done"] is True
    assert [(h["tier"], h["path"]) for h in row["heals"]] == [(0, "cache")]


def test_report_lists_ztar_over_m1_m7_and_with_m8(out):
    lines = (out / "report.md").read_text(encoding="utf-8").splitlines()
    (m7,) = [x for x in lines if x.startswith("- ZTAR M1-M7")]
    (m8,) = [x for x in lines if x.startswith("- ZTAR M1-M8")]
    assert "healing: 100% (2/2)" in m7 and "baseline: 0% (0/2)" in m7
    assert "healing: 67% (2/3)" in m8 and "baseline: 0% (0/3)" in m8


def test_token_overhead_is_median_difference_to_clean_plus_jev_tokens():
    def row(scenario, agent, tokens, jev=0):
        heals = [{"jev_tokens": jev}] if jev else []
        return {
            "scenario": scenario,
            "agent": agent,
            "phase": "main",
            "llm_tokens": tokens,
            "heals": heals,
        }

    rows = [
        *[row("CLEAN", "healing", t) for t in (1000, 1200, 1100)],
        *[row("CLEAN", "baseline", t) for t in (800, 900, 1000)],
        *[row("M5", "healing", t) for t in (1500, 1300, 1400)],
        *[row("M5", "baseline", t) for t in (4000, 6000, 5000)],
        *[row("M6", "healing", t, j) for t, j in ((1600, 50), (1800, 70), (1700, 60))],
        *[row("M6", "baseline", t) for t in (2000, 2000, 2000)],
    ]
    assert bench_run.token_overhead(rows) == {
        "M5": {"healing": 300, "baseline": 4100},
        "M6": {"healing": 660, "baseline": 1100},
    }
