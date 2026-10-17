"""Benchmark runner and report (PLAN.md phase 10, metrics per phase 12D / FR-15).

Every run is in-process and isolated: a fresh mock API, store and registry. Specs are
loaded from the clean API, then the mutation is switched on and the agent runs the task.

`bench()` makes three passes: the main pass over every scenario for both agents (plus the
tier-0 rerun of M1 to M5, FR-15.1) and the error-only ablation of M1 to M9 with
`spec_mode` off (FR-15.7). One `results.jsonl` row per run, `report.md` summarizes them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

import httpx

from agents import baseline_agent, common, healing_agent, scripted
from bench import overhead
from bench.mcp_session import session
from bench.oracle import classify_run
from healer.gateway import Gateway, upstream_registry
from healer.jev import JevClient, from_env
from healer.metrics import (
    false_patch_rate,
    safe_refusal,
    timing_summary,
    token_overhead,
    token_summary,
    ztar,
)
from healer.models import DecisionPath, HealOutcome, Reason, Tier
from healer.registry import Registry
from healer.repair import RepairAgent
from healer.repair import from_env as repair_from_env
from healer.store import Store
from mock_api.app import SEED, create_app
from mock_api.mcp_drift_server import SEED as MCP_SEED
from mock_api.mcp_drift_server import create_drift_server

TOOLS_JSON = Path(__file__).parents[1] / "config" / "tools.json"
REPORT_MARKER = "<!-- supplementary-evidence -->"


def report_path(output_dir: Path | None) -> Path:
    if output_dir is not None:
        return output_dir / "REPORT.md"
    return Path(__file__).parents[1] / "REPORT.md"


def preserve_supplementary(report_text: str, previous: str) -> str:
    if REPORT_MARKER in previous:
        return report_text + "\n\n" + REPORT_MARKER + previous.split(REPORT_MARKER, 1)[1]
    return report_text


DEFAULT_SCENARIOS = "CLEAN,M1,M2,M3,M4,M5,M6-D,M6-N,M7,M8,M9,C1,C2,C3"
ABLATION_SCENARIOS = ("M1", "M2", "M3", "M4", "M5", "M6-D", "M6-N", "M7", "M8", "M9")
TIER0_SCENARIOS = ("M1", "M2", "M3", "M4", "M5")
HEALABLE_MUTATIONS = ("M1", "M2", "M3", "M4", "M5", "M7", "M9")
M6_SCENARIOS = ("M6-D", "M6-N")  # reported separately from the healable ZTAR (FR-15.4)
ZTAR_SCENARIOS = (*HEALABLE_MUTATIONS, *M6_SCENARIOS)  # M8 and the controls stay out (AC-15)
REFUSAL_REASON = {"M8": "NO_SAFE_VALUE", "M6-N": "LOW_CONFIDENCE"}
# Where a must-refuse run could still send an invented value: a body the agent never asked for.
INVENTED_CHECK = {"M8": ("create_ticket", "/tickets"), "M6-N": ("set_manager", "/users/manager")}
AGENTS = ("healing", "baseline")
# T1-9: the MCP gateway scenarios. "MCP-<mutation>" rows have phase "mcp", so the REST tables skip them.
MCP_HEALABLE = ("M1", "M2", "T-RENAME", "T-ENUM")
MCP_REFUSE = {"T-REQUIRED": "NO_SAFE_VALUE", "M8": "NO_SAFE_VALUE"}
MCP_LLM_ONLY = ("T-MOVE",)  # needs the tier-2 repair agent
NEW_EMAIL = "ada.new@example.com"
MCP_STEPS = [
    ("users__get_user", {"user_id": "123"}),
    ("users__update_email", {"user_id": "123", "email": NEW_EMAIL, "email_type": "work"}),
    ("users__create_ticket", {"user_id": "123", "title": "Email changed"}),
]
# Controls drive their own tool calls; every other scenario runs the demo task.
CONTROL_STEPS = {
    "C2": [("get_user", {"user_id": "999"})],
    "C3": [
        ("get_user", {"user_id": "123"}),
        ("update_email", {"user_id": "123", "email": "not-an-email"}),
    ],
}
CONTROL_TASK = {  # the same controls, as instructions for the LLM agents
    "C2": "Look up user 999 and report exactly what the API answers.",
    "C3": "Set user 123's email to 'not-an-email' and report exactly what the API answers.",
}


def task_done(state: dict) -> bool:
    tickets = [
        t
        for t in state["tickets"]
        if t["user_id"] == "123" and t["title"] == "Email changed"
    ]
    user = state["users"]["123"]
    return user["email"] == NEW_EMAIL and user["manager_id"] == "456" and len(tickets) == 1


def state_ok(state: dict) -> bool:
    """FR-15.2: the final mock data state holds only expected writes.

    Every scenario shares this check, so a healed run whose state is wrong (a false patch)
    can never read as correct: only user 123's email and manager, and at most one known
    ticket, may differ from the seed state.
    """
    if set(state) != set(SEED):
        return False
    users = state.get("users", {})
    if set(users) != set(SEED["users"]) or users["456"] != SEED["users"]["456"]:
        return False
    ada = users["123"]
    if set(ada) != set(SEED["users"]["123"]) or ada["name"] != "Ada":
        return False
    if ada["email"] not in (SEED["users"]["123"]["email"], NEW_EMAIL):
        return False
    if ada["manager_id"] not in (None, "456"):
        return False
    tickets = state.get("tickets", [])
    expected = [{"ticket_id": "T-1", "user_id": "123", "title": "Email changed"}]
    return not tickets or tickets == expected


def steps_for(scenario: str) -> list[tuple[str, dict]]:
    return CONTROL_STEPS.get(scenario, scripted.STEPS)


def expectation(scenario: str, *, jev: bool) -> tuple[str, str | None]:
    """What one run of `scenario` owes: a completed task, a safe refusal or a pass-through,
    plus the refusal reason it must abort with (FR-15.4)."""
    if scenario == "M8":
        return "refuse", REFUSAL_REASON["M8"]
    if scenario == "M6-N" and not jev:  # FR-8.3: without Jev the pick is not ours to make
        return "refuse", REFUSAL_REASON["M6-N"]
    if scenario in CONTROL_STEPS:
        return "pass-through", Reason.NOT_DRIFT.value
    return "task", None


async def _pass(
    mode: str,
    n: int,
    scenarios: list[str],
    jev: JevClient | None,
    llm,
    *,
    spec_mode: str,
    phase: str,
    agents: tuple[str, ...],
    tier0: bool,
) -> list[dict]:
    """One pass of the benchmark: scenarios x agents x n runs, optionally with a tier-0
    rerun (same store and mock, so the stored fix serves the second run)."""
    tools = json.loads(TOOLS_JSON.read_text(encoding="utf-8"))
    cfg = {
        "OAUTH_BEARER": os.environ.get("OAUTH_BEARER", "Bearer test-token"),
        "TENANT_ID": os.environ.get("TENANT_ID", "t-1"),
    }

    async def once(api, client, db, agent, scenario, i, run_phase) -> dict:
        """One run on a new store and registry; calling it again on the same `db` is a restart."""
        api.reset()
        store = Store(db)
        try:
            registry = Registry(
                client, tools, cfg, store=store, jev=jev, spec_mode=spec_mode
            )
            await registry.load()
            api.set_mutation(None if scenario == "CLEAN" else scenario)
            seen = len(store.audit_events())
            run_id = f"{scenario}-{agent}-{i}-{run_phase}"
            if mode == "scripted":
                execute = (
                    healing_agent.executor(registry)
                    if agent == "healing"
                    else baseline_agent.executor(client, registry)
                )
                result = await scripted.run(
                    execute,
                    agent,
                    retry_same_args=agent == "baseline",
                    store=store,
                    run_id=run_id,
                    steps=steps_for(scenario),
                )
            else:
                llm_agent = (
                    healing_agent.build(registry, llm, store, run_id)
                    if agent == "healing"
                    else baseline_agent.build(client, registry, llm, store, run_id)
                )
                result = await common.run(llm_agent, CONTROL_TASK.get(scenario, common.TASK))
            heals = store.audit_events()[seen:]
        finally:
            store.close()
        state = api.state()
        oracle = classify_run(
            api.expected_canonical[scenario], api.requests, api.received, cfg
        ) if scenario in api.expected_canonical else "REJECTED"
        reasons = [e.reason.value for e in heals if e.reason]
        paths = [e.path.value for e in heals if e.path]
        priority = any(
            isinstance(r["body"], dict) and "priority" in r["body"] for r in api.requests
        )
        invented = False
        if (check := INVENTED_CHECK.get(scenario)) is not None:
            # A request carrying an invented value is one whose body is not an argument the
            # agent itself passed (AGENTS.md coding invariant 1); the first, failing request is.
            tool, path = check
            asked = [args for name, args in steps_for(scenario) if name == tool]
            invented = any(
                r["path"] == path and r["body"] not in asked
                for r in api.requests
                if r["body"] is not None
            )
        kind, expected = expectation(scenario, jev=jev is not None)
        must_refuse = agent == "healing" and (
            kind == "refuse"
            or (scenario == "M6-N" and DecisionPath.jev_unavailable.value in paths)
        )
        done, correct = task_done(state), state_ok(state)
        met = False
        if kind == "task":
            met = done and correct
        elif not result.hit_limit and result.error is None:
            met = (
                expected in reasons and not invented and correct
                if kind == "refuse"
                else correct and (agent == "baseline" or expected in reasons)
            )
        return {
            "scenario": scenario,
            "agent": agent,
            "mode": mode,
            "run": i,
            "phase": run_phase,
            "spec_mode": spec_mode,
            "task_done": done,
            "state_ok": correct,
            "expectation_met": met,
            "must_refuse": must_refuse,
            "expected_reason": expected,
            "invented_sent": invented,
            "tool_calls": result.tool_calls,
            "llm_tokens": result.llm_tokens,
            "jev_tokens": sum(e.jev_tokens for e in heals),
            "hit_limit": result.hit_limit,
            "error": result.error,
            "priority_sent": priority,
            "oracle": oracle,
            "requests": api.received,
            "heals": [
                {
                    "tool": e.tool,
                    "tier": int(e.tier),
                    "path": e.path.value if e.path else None,
                    "outcome": e.outcome.value,
                    "reason": e.reason.value if e.reason else None,
                    "mttr_ms": e.mttr_ms,
                    "heal_ms": e.heal_ms,
                    "jev_tokens": e.jev_tokens,
                }
                for e in heals
            ],
        }

    rows: list[dict] = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for scenario in scenarios:
            for i in range(n):
                for agent in agents:
                    api = create_app()
                    db = str(Path(tmp) / f"{scenario}-{agent}-{i}.db")
                    transport = httpx.ASGITransport(app=api)
                    async with httpx.AsyncClient(
                        transport=transport, base_url="http://mock"
                    ) as client:
                        rows.append(await once(api, client, db, agent, scenario, i, phase))
                        if tier0 and agent == "healing" and scenario in TIER0_SCENARIOS:
                            rows.append(
                                await once(api, client, db, agent, scenario, i, "tier0")
                            )
    return rows


async def bench(
    mode: str,
    n: int,
    scenarios: list[str],
    jev: JevClient | None = None,
    llm=None,
) -> list[dict]:
    """The main pass (FR-15.1, FR-15.6) and the error-only ablation (FR-15.7)."""
    rows = await _pass(
        mode,
        n,
        scenarios,
        jev,
        llm,
        spec_mode="on",
        phase="main",
        agents=AGENTS,
        tier0=True,
    )
    # FR-15.7: each mutation once more, spec endpoint disabled (error-clue mode).
    ablation = [s for s in dict.fromkeys(scenarios) if s in ABLATION_SCENARIOS]
    if ablation:
        rows += await _pass(
            mode,
            1,
            ablation,
            jev,
            llm,
            spec_mode="off",
            phase="ablation",
            agents=("healing",),
            tier0=False,
        )
    return rows


def mcp_state_ok(data: dict) -> bool:
    """Only user 123's email may differ from the seed, and at most the one expected ticket."""
    users = {k: dict(v) for k, v in data["users"].items()}
    ada = users.get("123", {})
    if ada.get("email") not in (MCP_SEED["users"]["123"]["email"], NEW_EMAIL):
        return False
    ada["email"] = MCP_SEED["users"]["123"]["email"]
    expected = [{"ticket_id": "T-1", "user_id": "123", "title": "Email changed"}]
    return users == MCP_SEED["users"] and data["tickets"] in ([], expected)


async def mcp_bench(n: int, repair: RepairAgent | None = None) -> list[dict]:
    """The scripted MCP task per drift-server mutation, through a healing gateway and a
    baseline (`store=None`, so errors pass through). T-MOVE runs only when `repair` is set."""
    scenarios = (*MCP_HEALABLE, *MCP_REFUSE, *(MCP_LLM_ONLY if repair else ()))
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for mutation in scenarios:
            for i in range(n):
                for agent in AGENTS:
                    drift = create_drift_server(profile="users")
                    store = Store(str(Path(tmp) / f"{mutation}-{agent}-{i}.db"))
                    try:
                        async with session(drift) as sess:
                            registry = await upstream_registry(
                                "users",
                                sess,
                                store if agent == "healing" else None,
                                {},
                                repair=repair if agent == "healing" else None,
                            )
                            drift.apply_mutation(mutation)
                            result = await scripted.run(
                                healing_agent.executor(Gateway([registry])),
                                agent,
                                retry_same_args=agent == "baseline",
                                steps=MCP_STEPS,
                            )
                        heals = store.audit_events() if agent == "healing" else []
                    finally:
                        store.close()
                    users, tickets = drift.data["users"], drift.data["tickets"]
                    done = users["123"]["email"] == NEW_EMAIL and len(tickets) == 1
                    correct = mcp_state_ok(drift.data)
                    reason = MCP_REFUSE.get(mutation)
                    reasons = [e.reason.value for e in heals if e.reason]
                    invented = mutation == "M8" and bool(tickets)  # no safe value existed
                    if reason:
                        met = (
                            correct
                            and not invented
                            and (agent == "baseline" or reason in reasons)
                        )
                    else:
                        met = done and correct
                    rows.append(
                        {
                            "scenario": f"MCP-{mutation}",
                            "agent": agent,
                            "mode": "scripted",
                            "run": i,
                            "phase": "mcp",
                            "spec_mode": "on",
                            "task_done": done,
                            "state_ok": correct,
                            "expectation_met": met,
                            "must_refuse": agent == "healing" and reason is not None,
                            "expected_reason": reason,
                            "invented_sent": invented,
                            "tool_calls": result.tool_calls,
                            "llm_tokens": sum(e.llm_tokens for e in heals),
                            "jev_tokens": sum(e.jev_tokens for e in heals),
                            "hit_limit": result.hit_limit,
                            "error": result.error,
                            "priority_sent": False,
                            "heals": [
                                {
                                    "tool": e.tool,
                                    "tier": int(e.tier),
                                    "path": e.path.value if e.path else None,
                                    "outcome": e.outcome.value,
                                    "reason": e.reason.value if e.reason else None,
                                    "mttr_ms": e.mttr_ms,
                                    "heal_ms": e.heal_ms,
                                    "jev_tokens": e.jev_tokens,
                                }
                                for e in heals
                            ],
                        }
                    )
    return rows


def mcp_section(rows: list[dict], overhead_result: dict | None, *, llm: bool) -> list[str]:
    """The "## MCP gateway" report section (T1-8, T1-9)."""
    lines = [
        "",
        "## MCP gateway (T1-8, T1-9, AC-53, AC-54)",
        "",
        (
            "Each drift-server mutation runs a fixed three-call task (`get_user`, "
            "`update_email`, `create_ticket`) through a healing `Gateway` and through a "
            "baseline `upstream_registry` with no store (errors pass through; the baseline "
            "re-sends a failing call until the cap of 10 calls). Everything is in-memory. "
            "ZTAR, Safe-Refusal and False-Patch use the same definitions as the REST tables."
        ),
        "",
        (
            "| Mutation | Healing ZTAR | Healing expected outcome | Baseline ZTAR "
            "| Baseline expected outcome | Heal path | Refusal reasons | MTTR tier 1 "
            "| heal_ms tier 1 |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    ztar_set = tuple(f"MCP-{m}" for m in (*MCP_HEALABLE, *MCP_LLM_ONLY))
    for s in dict.fromkeys(r["scenario"] for r in rows):
        healing, baseline = _pick(rows, s, "healing", "mcp"), _pick(rows, s, "baseline", "mcp")
        events = [h for r in healing for h in r["heals"]]
        recovered = HealOutcome.RECOVERED.value
        cells = [
            s.removeprefix("MCP-"),
            _ztar(healing, ztar_set) if s in ztar_set else "n/a",
            _outcome(healing),
            _ztar(baseline, ztar_set) if s in ztar_set else "n/a",
            _outcome(baseline),
            _tally(h["path"] for h in events if h["outcome"] == recovered),
            _tally(h["reason"] for h in events if h["reason"]),
            _timing(healing, Tier.T1, "mttr_ms"),
            _timing(healing, Tier.T1, "heal_ms"),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    healing_rows = [r for r in rows if r["agent"] == "healing"]
    baseline_rows = [r for r in rows if r["agent"] == "baseline"]
    healable = tuple(f"MCP-{m}" for m in MCP_HEALABLE)
    refusal, patches = safe_refusal(healing_rows), false_patch_rate(healing_rows)
    lines += [
        "",
        (
            f"- Healable ZTAR ({', '.join(MCP_HEALABLE)}), healing: "
            f"{_ztar(healing_rows, healable)}; baseline: {_ztar(baseline_rows, healable)}"
        ),
        f"- Safe-Refusal Rate (T-REQUIRED, M8): {_rate(refusal['refused'], refusal['runs'])}",
        (
            f"- False-Patch Rate: {_rate(patches['false_patches'], patches['healed'])} of the "
            "healed runs ended with a wrong final state."
        ),
    ]
    if not llm:
        lines.append(
            "- T-MOVE needs the tier-2 repair agent and was skipped in scripted mode "
            "(run `--agent llm`)."
        )
    if overhead_result:
        o = overhead_result
        lines += [
            "",
            (
                f"Healthy-call overhead over MCP (`users__get_user`, n={o['samples']} per side, "
                "in-memory; gateway call minus a direct `ClientSession.call_tool`):"
            ),
            "",
            "| Series | p50 ms | p95 ms | mean ms |",
            "|---|---|---|---|",
        ]
        for series, label in (
            ("registry", "gateway"),
            ("direct", "direct"),
            ("overhead", "overhead"),
        ):
            v = o[series]
            lines.append(f"| {label} | {v['p50_ms']:.3f} | {v['p95_ms']:.3f} | {v['mean_ms']:.3f} |")
    return lines


def _pick(rows: list[dict], scenario: str, agent: str, phase: str = "main") -> list[dict]:
    return [
        r
        for r in rows
        if (r["scenario"], r["agent"], r["phase"]) == (scenario, agent, phase)
    ]


def _rate(count: int, runs: int) -> str:
    return f"{100 * count / runs:.0f}% ({count}/{runs})" if runs else "n/a"


def _ztar(rows: list[dict], scenarios=HEALABLE_MUTATIONS) -> str:
    d = ztar(rows, scenarios)
    return _rate(d["adapted"], d["runs"])


def _stats_cell(stats: dict | None) -> str:
    """mean/p50/p95 with the sample size, the shape FR-15.5 asks for."""
    if stats is None:
        return "-"
    return f"{stats['mean']:g}/{stats['p50']:g}/{stats['p95']:g} (n={stats['n']})"


def _timing(rows: list[dict], tier: Tier, key: str) -> str:
    """mean/p50/p95 of `mttr_ms` or `heal_ms` over recovered heals of one tier."""
    summary = timing_summary(h for r in rows for h in r["heals"]).get(tier)
    return "-" if summary is None else _stats_cell(summary[key])


def _tally(items) -> str:
    return ", ".join(f"{k} x{v}" for k, v in Counter(items).items()) or "-"


def _failure_mode(rows: list[dict]) -> str:
    counts = {
        "hit cap": sum(r["hit_limit"] for r in rows),
        "errors": sum(r["error"] is not None for r in rows),
        "ended incomplete": sum(
            not r["task_done"] and not r["hit_limit"] and r["error"] is None
            for r in rows
        ),
    }
    return ", ".join(f"{k} {v}/{len(rows)}" for k, v in counts.items() if v) or "-"


def _outcome(rows: list[dict]) -> str:
    """Share of runs that met the scenario's own expectation."""
    return _rate(sum(r["expectation_met"] for r in rows), len(rows))


def _ablation_cell(row: dict) -> tuple[str, str, str, str]:
    """One ablation row -> (outcome, reason, final state, false patch)."""
    outcomes = {h["outcome"] for h in row["heals"]}
    if HealOutcome.RECOVERED.value in outcomes:
        outcome = "healed"
    elif outcomes:
        outcome = "aborted"
    else:
        outcome = "no heal attempt"
    reason = next((h["reason"] for h in row["heals"] if h["reason"]), "-")
    false_patch = HealOutcome.RECOVERED.value in outcomes and not row["state_ok"]
    return (
        outcome,
        reason,
        "correct" if row["state_ok"] else "wrong",
        "yes" if false_patch else "no",
    )


def report(
    rows: list[dict],
    *,
    mode: str,
    model: str | None,
    n: int,
    jev_configured: bool,
    mcp_rows: list[dict] | None = None,
    mcp_overhead: dict | None = None,
) -> str:
    main = [r for r in rows if r["phase"] == "main"]
    tier0 = [r for r in rows if r["phase"] == "tier0"]
    ablation = [r for r in rows if r["phase"] == "ablation"]
    scenarios = list(dict.fromkeys(r["scenario"] for r in main))
    healing_rows = [r for r in main if r["agent"] == "healing"]
    baseline_rows = [r for r in main if r["agent"] == "baseline"]
    mode_text = (
        f"llm ({model})"
        if mode == "llm"
        else "scripted (fixed tool calls, no LLM; the baseline re-sends a failing call "
        "with the same arguments until the cap of 10)"
    )
    no_answer = sum(
        h["path"] == DecisionPath.jev_unavailable
        for r in rows
        for h in r["heals"]
    )
    spec_text = "`on` for the main and tier-0 passes"
    if any(r["spec_mode"] == "off" for r in rows):
        spec_text += ", `off` for the error-only ablation"
    if not jev_configured:
        jev_text = "no (M6-N then aborts LOW_CONFIDENCE, which counts as a safe refusal)"
    elif no_answer:
        jev_text = f"configured, but gave no usable answer in {no_answer} heals (jev_unavailable)"
    else:
        jev_text = "yes"
    lines = [
        "# Benchmark report",
        "",
        f"- Mode: {mode_text}",
        f"- Runs per scenario and agent (N): {n}",
        f"- Date (UTC): {datetime.now(UTC):%Y-%m-%d %H:%M}",
        f"- Jev available: {jev_text}",
        f"- Spec mode: {spec_text}",
        f"- Scenarios: {', '.join(scenarios)}",
        "",
        "## Per scenario",
        "",
        (
            "ZTAR is the share of runs whose task completed and whose final mock state is "
            "correct (FR-15.4); it is only defined for the healable mutations and for M6-D / "
            "M6-N, so the other rows read `n/a`. Expected outcome is the scenario's own "
            "expectation: the completed task for CLEAN, C1 and the mutations, a safe refusal "
            "for M8 (and for M6-N while Jev is disabled), a pass-through for C2 and C3. "
            "MTTR and heal_ms are mean / p50 / p95 in ms over recovered heals; tier 0 is the "
            "M1-M5 rerun served from the stored fix."
        ),
        "",
        (
            "| Scenario | Healing ZTAR | Healing expected outcome | Baseline ZTAR "
            "| Baseline expected outcome | Baseline failure mode | Heal path "
            "| Refusal reasons | MTTR tier 1 | MTTR tier 0 | heal_ms tier 1 "
            "| heal_ms tier 0 |"
        ),
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in scenarios:
        healing = _pick(main, s, "healing")
        baseline = _pick(main, s, "baseline")
        events = [h for r in healing for h in r["heals"]]
        recovered = HealOutcome.RECOVERED.value
        cells = [
            s,
            _ztar(healing, ZTAR_SCENARIOS),
            _outcome(healing),
            _ztar(baseline, ZTAR_SCENARIOS),
            _outcome(baseline),
            _failure_mode(baseline),
            _tally(h["path"] for h in events if h["outcome"] == recovered),
            _tally(h["reason"] for h in events if h["reason"]),
            _timing(healing, Tier.T1, "mttr_ms"),
            _timing(_pick(tier0, s, "healing", "tier0"), Tier.T0, "mttr_ms"),
            _timing(healing, Tier.T1, "heal_ms"),
            _timing(_pick(tier0, s, "healing", "tier0"), Tier.T0, "heal_ms"),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    lines += [
        "",
        "## ZTAR (FR-15.4, AC-15)",
        "",
        (
            f"- Healable mutations ({', '.join(HEALABLE_MUTATIONS)}), healing: "
            f"{_ztar(healing_rows)}; baseline: {_ztar(baseline_rows)}"
        ),
        (
            "- M6-D, reported separately: "
            f"healing {_ztar(healing_rows, ('M6-D',))}; "
            f"baseline {_ztar(baseline_rows, ('M6-D',))}"
        ),
        (
            "- M6-N, reported separately: "
            f"healing {_ztar(healing_rows, ('M6-N',))}; "
            f"baseline {_ztar(baseline_rows, ('M6-N',))}"
        ),
        "",
        (
            "M8 is a refusal, not an adaptation: it is counted in the Safe-Refusal Rate below "
            "and never in ZTAR. C1, C2 and C3 are controls, and CLEAN only sets the token "
            "baseline. M6 never enters the healable denominator."
        ),
    ]
    if not jev_configured:
        lines.append(
            "With Jev disabled every M6-N run aborts LOW_CONFIDENCE without writing, so its "
            "ZTAR is 0% by design and its refusal is counted below."
        )

    refusal = safe_refusal(healing_rows)
    patches = false_patch_rate(healing_rows)
    required = sorted({r["scenario"] for r in healing_rows if r["must_refuse"]})
    lines += [
        "",
        "## Safe-Refusal Rate and False-Patch Rate (FR-15.4, AC-15)",
        "",
        (
            f"- Safe-Refusal Rate: {_rate(refusal['refused'], refusal['runs'])} over "
            f"{', '.join(required) or 'no'} runs, and no request carrying an invented value "
            "was sent in any of them."
        ),
        (
            f"- False-Patch Rate: {_rate(patches['false_patches'], patches['healed'])} of the "
            "healed runs ended with a wrong final mock state."
        ),
    ]

    lines += [
        "",
        "## Baseline outcomes (FR-15.8, AC-17)",
        "",
        (
            "Measured for every scenario, never asserted as pass or fail: the error loop (the "
            "baseline re-sends the same arguments until the iteration cap), the calls it made, "
            "and the final data. `Task state correct` is the demo task's end state reached with "
            "only expected writes (`n/a` where the scenario has no task: M8, M6-N without Jev "
            "and the controls). `State integrity` is FR-15.2's final-state check, no wrong or "
            "invented data, which is what the False-Patch Rate uses. Tokens are below."
        ),
        "",
        "| Scenario | Runs | Error loop | Calls (mean) | Task state correct | State integrity |",
        "|---|---|---|---|---|---|",
    ]
    for s in scenarios:
        base = _pick(main, s, "baseline")
        done = sum(r["task_done"] and r["state_ok"] for r in base)
        task = _rate(done, len(base)) if expectation(s, jev=jev_configured)[0] == "task" else "n/a"
        calls = f"{mean(r['tool_calls'] for r in base):g}" if base else "-"
        lines.append(
            f"| {s} | {len(base)} | {sum(r['hit_limit'] for r in base)} hit cap "
            f"| {calls} | {task} | {_rate(sum(r['state_ok'] for r in base), len(base))} |"
        )

    lines += [
        "",
        "## Timings by tier (FR-15.4, AC-14)",
        "",
        (
            "Main and tier-0 passes, recovered heals. MTTR runs from the first failing response "
            "caused by the mutation to the first verified-correct result; `heal_ms` is the "
            "registry's internal heal time, reported separately."
        ),
        "",
        "| Tier | n | mttr_ms mean / p50 / p95 | heal_ms mean / p50 / p95 |",
        "|---|---|---|---|",
    ]
    for tier, stats in timing_summary(
        h for r in (*healing_rows, *tier0) for h in r["heals"]
    ).items():
        lines.append(
            f"| {int(tier)} | {stats['n']} | {_stats_cell(stats['mttr_ms'])} "
            f"| {_stats_cell(stats['heal_ms'])} |"
        )

    overhead, tokens = token_overhead(main), token_summary(main)
    lines += [
        "",
        "## Tokens (FR-8.7, FR-15.4, FR-15.5, AC-16)",
        "",
        ("Per run: mean / p50 / p95. `jev_tokens` is the classifier's own usage, reported in "
         "its own column and never added to `llm_tokens`. Overhead is the mutated run's total "
         "minus this agent's CLEAN-run median; for the baseline the same subtraction is its "
         "wasted tokens. The ratio is healing overhead divided by baseline waste, `n/a` when "
         "the baseline waste is 0."),
        "",
        (
            "| Scenario | Healing llm_tokens | Baseline llm_tokens | jev_tokens "
            "| Healing overhead | Baseline wasted | Ratio (healing : baseline) |"
        ),
        "|---|---|---|---|---|---|---|",
    ]
    for s in scenarios:
        per_agent = tokens.get(s, {})
        cells = [
            s,
            _stats_cell(per_agent.get("healing", {}).get("llm_tokens")),
            _stats_cell(per_agent.get("baseline", {}).get("llm_tokens")),
            _stats_cell(per_agent.get("healing", {}).get("jev_tokens")),
        ]
        gain = overhead.get(s)
        mutated = bool(gain) and s.startswith("M")
        wasted = gain["baseline"] if mutated else 0
        cells += [
            f"{gain['healing']:g}" if mutated else "-",
            f"{wasted:g}" if mutated else "-",
            (f"{gain['healing'] / wasted:.2f}" if wasted else "n/a") if mutated else "-",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    if mode == "scripted":
        lines += [
            "",
            (
                "Scripted mode makes no LLM call, so every `llm_tokens` value above is 0; run "
                "`--agent llm` to measure token overhead (AC-16)."
            ),
        ]

    lines += [
        "",
        "## Error-only ablation (`spec_mode=off`, FR-15.7, AC-23)",
        "",
        (
            "Each mutation re-run once with the spec endpoint disabled, so diagnosis runs on "
            "the error clue alone. There is no heal-rate threshold here; the False-Patch Rate "
            "must stay 0. Combined or nested mutations (M5, M9) are expected to abort rather "
            "than patch, and so are the refusals."
        ),
        "",
    ]
    if ablation:
        lines += [
            "| Mutation | Outcome | Reason | Final state | False patch |",
            "|---|---|---|---|---|",
        ]
        for mid in ABLATION_SCENARIOS:
            (row,) = [r for r in ablation if r["scenario"] == mid]
            lines.append("| " + " | ".join((mid, *_ablation_cell(row))) + " |")
        ablation_patches = false_patch_rate(ablation)
        lines += [
            "",
            (
                f"- False-Patch Rate (ablation): "
                f"{_rate(ablation_patches['false_patches'], ablation_patches['healed'])} of "
                "the healed runs."
            ),
        ]
    else:
        lines.append("No M1-M9 scenario in this run, so no ablation was made.")
    if mcp_rows:
        lines += mcp_section(mcp_rows, mcp_overhead, llm=mode == "llm")
    return "\n".join(lines) + "\n"


async def _amain(args: argparse.Namespace) -> None:
    jev = from_env()
    llm = common.make_llm() if args.agent == "llm" else None
    try:
        rows = await bench(args.agent, args.n, args.scenarios.split(","), jev, llm)
    finally:
        if jev:
            await jev.aclose()
    mcp_rows, mcp_overhead = [], None
    if args.mcp:
        repair = repair_from_env() if args.agent == "llm" else None
        mcp_rows = await mcp_bench(args.n, repair)
        mcp_overhead = await overhead.measure_mcp()
    output_dir = args.out or Path(__file__).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    if mcp_rows:
        (output_dir / "results_mcp.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in mcp_rows), encoding="utf-8"
        )
    results = output_dir / "results.jsonl"
    md = report_path(args.out)
    results.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    previous = md.read_text(encoding="utf-8") if md.is_file() else ""
    md.write_text(
        preserve_supplementary(report(
            rows,
            mode=args.agent,
            model=llm.model_name if llm else None,
            n=args.n,
            jev_configured=jev is not None,
            mcp_rows=mcp_rows,
            mcp_overhead=mcp_overhead,
        ), previous),
        encoding="utf-8",
    )
    print(f"wrote {results} and {md}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m bench.run")
    parser.add_argument("--agent", choices=("scripted", "llm"), default="scripted")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    parser.add_argument("--no-mcp", dest="mcp", action="store_false", help="skip the MCP section")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.agent == "llm" and not os.environ.get("NVIDIA_API_KEY"):
        raise SystemExit("--agent llm needs NVIDIA_API_KEY in the environment")
    asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
