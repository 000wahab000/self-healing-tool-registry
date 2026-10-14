"""Benchmark runner and report (plan.md phase 10).

Every run is in-process and isolated: a fresh mock API, store and registry. Specs are
loaded from the clean API, then the mutation is switched on and the agent runs the demo task.
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
from statistics import median
from types import SimpleNamespace

import httpx

from agents import baseline_agent, common, healing_agent, scripted
from healer.jev import JevClient, from_env
from healer.metrics import mttr_summary
from healer.models import DecisionPath, HealOutcome, Tier
from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app

TOOLS_JSON = Path(__file__).parents[1] / "config" / "tools.json"
DEFAULT_SCENARIOS = "CLEAN,M1,M2,M3,M4,M5,M6,M7,M8,C1"
TIER0_SCENARIOS = ("M1", "M2", "M3", "M4", "M5")
AGENTS = ("healing", "baseline")


def task_done(state: dict) -> bool:
    tickets = [
        t
        for t in state["tickets"]
        if t["user_id"] == "123" and t["title"] == "Email changed"
    ]
    user = state["users"]["123"]
    return (
        user["email"] == "ada.new@example.com"
        and user["manager_id"] == "456"
        and len(tickets) == 1
    )


async def bench(
    mode: str,
    n: int,
    scenarios: list[str],
    jev: JevClient | None = None,
    llm=None,
) -> list[dict]:
    tools = json.loads(TOOLS_JSON.read_text(encoding="utf-8"))
    cfg = {
        "OAUTH_BEARER": os.environ.get("OAUTH_BEARER", "Bearer test-token"),
        "TENANT_ID": os.environ.get("TENANT_ID", "t-1"),
    }

    async def once(api, client, db, agent, scenario, i, phase) -> dict:
        """One run on a new store and registry; calling it again on the same `db` is a restart."""
        api.reset()
        store = Store(db)
        try:
            registry = Registry(client, tools, cfg, store=store, jev=jev)
            await registry.load()
            api.set_mutation(None if scenario == "CLEAN" else scenario)
            seen = len(store.audit_events())
            run_id = f"{scenario}-{agent}-{i}-{phase}"
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
                )
            else:
                llm_agent = (
                    healing_agent.build(registry, llm, store, run_id)
                    if agent == "healing"
                    else baseline_agent.build(client, registry, llm, store, run_id)
                )
                result = await common.run(llm_agent, common.TASK)
            heals = store.audit_events()[seen:]
        finally:
            store.close()
        return {
            "scenario": scenario,
            "agent": agent,
            "mode": mode,
            "run": i,
            "phase": phase,
            "task_done": task_done(api.state()),
            "tool_calls": result.tool_calls,
            "llm_tokens": result.llm_tokens,
            "hit_limit": result.hit_limit,
            "error": result.error,
            "priority_sent": any(
                isinstance(r["body"], dict) and "priority" in r["body"]
                for r in api.requests
            ),
            "heals": [
                {
                    "tool": e.tool,
                    "tier": int(e.tier),
                    "path": e.path.value if e.path else None,
                    "outcome": e.outcome.value,
                    "reason": e.reason.value if e.reason else None,
                    "mttr_ms": e.mttr_ms,
                    "jev_tokens": e.jev_tokens,
                }
                for e in heals
            ],
        }

    rows: list[dict] = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for scenario in scenarios:
            for i in range(n):
                for agent in AGENTS:
                    api = create_app()
                    db = str(Path(tmp) / f"{scenario}-{agent}-{i}.db")
                    transport = httpx.ASGITransport(app=api)
                    async with httpx.AsyncClient(
                        transport=transport, base_url="http://mock"
                    ) as client:
                        rows.append(
                            await once(api, client, db, agent, scenario, i, "main")
                        )
                        if agent == "healing" and scenario in TIER0_SCENARIOS:
                            rows.append(
                                await once(api, client, db, agent, scenario, i, "tier0")
                            )
    return rows


def _pick(
    rows: list[dict], scenario: str, agent: str, phase: str = "main"
) -> list[dict]:
    return [
        r
        for r in rows
        if (r["scenario"], r["agent"], r["phase"]) == (scenario, agent, phase)
    ]


def token_overhead(rows: list[dict]) -> dict[str, dict[str, float]]:
    """Per mutated scenario, from main-phase rows. Empty when there are no CLEAN runs.

    healing  = median tokens - median CLEAN tokens + median Jev tokens per run
    baseline = median tokens - median CLEAN tokens (the tokens wasted on the break)
    """

    def med(scenario: str, agent: str) -> float:
        return median(r["llm_tokens"] for r in _pick(rows, scenario, agent))

    if not any(r["scenario"] == "CLEAN" for r in rows):
        return {}
    out = {}
    for s in dict.fromkeys(r["scenario"] for r in rows if r["scenario"] != "CLEAN"):
        jev = median(
            sum(h["jev_tokens"] for h in r["heals"]) for r in _pick(rows, s, "healing")
        )
        out[s] = {
            "healing": med(s, "healing") - med("CLEAN", "healing") + jev,
            "baseline": med(s, "baseline") - med("CLEAN", "baseline"),
        }
    return out


def _ztar(rows: list[dict]) -> str:
    done = sum(r["task_done"] for r in rows)
    return f"{100 * done / len(rows):.0f}% ({done}/{len(rows)})" if rows else "n/a"


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


def _mttr(rows: list[dict], tier: Tier) -> str:
    events = [
        SimpleNamespace(
            tier=Tier(h["tier"]),
            outcome=HealOutcome(h["outcome"]),
            mttr_ms=h["mttr_ms"],
        )
        for r in rows
        for h in r["heals"]
    ]
    s = mttr_summary(events).get(tier)
    return f"{s['p50_ms']:g} / {s['p95_ms']:g} (n={s['n']})" if s else "-"


def report(
    rows: list[dict], *, mode: str, model: str | None, n: int, jev_configured: bool
) -> str:
    scenarios = list(dict.fromkeys(r["scenario"] for r in rows))
    mode_text = (
        f"llm ({model})"
        if mode == "llm"
        else "scripted (fixed tool calls, no LLM; the baseline re-sends a failing call "
        "with the same arguments until the cap of 10)"
    )
    no_answer = sum(
        h["path"] == DecisionPath.jev_unavailable for r in rows for h in r["heals"]
    )
    if not jev_configured:
        jev_text = (
            "no (M6 cannot heal without Jev: its two candidates need Jev to choose)"
        )
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
        f"- Scenarios: {', '.join(scenarios)}",
        "",
        "## Per scenario",
        "",
        (
            "ZTAR is the share of runs whose final mock state matches the task (email, "
            "manager and one ticket; a failed read-only lookup alone does not fail a run). "
            "MTTR is p50 / p95 in ms over recovered heals."
        ),
        "",
        (
            "| Scenario | Healing ZTAR | Baseline ZTAR | Baseline failure mode "
            "| Heal path | Refusal reasons | MTTR tier 1 | MTTR tier 0 |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in scenarios:
        healing, baseline = _pick(rows, s, "healing"), _pick(rows, s, "baseline")
        events = [h for r in healing for h in r["heals"]]
        recovered = HealOutcome.RECOVERED
        cells = [
            s,
            _ztar(healing),
            _ztar(baseline),
            _failure_mode(baseline),
            _tally(h["path"] for h in events if h["outcome"] == recovered),
            _tally(h["reason"] for h in events if h["reason"]),
            _mttr(healing, Tier.T1),
            _mttr(_pick(rows, s, "healing", "tier0"), Tier.T0),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    def overall(last: int) -> str:
        ids = {f"M{k}" for k in range(1, last + 1)}
        main = [r for r in rows if r["phase"] == "main" and r["scenario"] in ids]
        by = {a: [r for r in main if r["agent"] == a] for a in AGENTS}
        return f"healing: {_ztar(by['healing'])}; baseline: {_ztar(by['baseline'])}"

    lines += [
        "",
        "## ZTAR overall",
        "",
        f"- ZTAR M1-M7, {overall(7)}",
        f"- ZTAR M1-M8, {overall(8)}",
        "",
        (
            "M8 counts as not adapted: it is a deliberate refusal (the healer aborts with "
            "NO_SAFE_VALUE instead of inventing a value for the new required `priority`)."
        ),
    ]
    if mode == "llm":
        lines += [
            "",
            "## Token overhead",
            "",
            (
                "Median LLM tokens per run against the CLEAN median of the same agent. "
                "Healing overhead also adds the median Jev tokens per run."
            ),
            "",
        ]
        overhead = token_overhead(rows)
        if overhead:
            lines += [
                "| Scenario | Healing overhead | Baseline wasted |",
                "|---|---|---|",
                *(
                    f"| {s} | {v['healing']:g} | {v['baseline']:g} |"
                    for s, v in overhead.items()
                ),
            ]
        else:
            lines.append("No CLEAN runs in this benchmark, so no baseline to subtract.")
    return "\n".join(lines) + "\n"


async def _amain(args: argparse.Namespace) -> None:
    jev = from_env()
    llm = common.make_llm() if args.agent == "llm" else None
    try:
        rows = await bench(args.agent, args.n, args.scenarios.split(","), jev, llm)
    finally:
        if jev:
            await jev.aclose()
    args.out.mkdir(parents=True, exist_ok=True)
    results, md = args.out / "results.jsonl", args.out / "report.md"
    results.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    md.write_text(
        report(
            rows,
            mode=args.agent,
            model=llm.model_name if llm else None,
            n=args.n,
            jev_configured=jev is not None,
        ),
        encoding="utf-8",
    )
    print(f"wrote {results} and {md}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m bench.run")
    parser.add_argument("--agent", choices=("scripted", "llm"), default="scripted")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent)
    args = parser.parse_args(argv)
    if args.agent == "llm" and not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("--agent llm needs OPENROUTER_API_KEY in the environment")
    asyncio.run(_amain(args))


if __name__ == "__main__":
    main()
