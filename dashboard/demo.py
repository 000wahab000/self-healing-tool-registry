"""Terminal demo, the fallback for the pitch: `python -m dashboard.demo`.

Scripted agents (no LLM, no network) on two in-process mock APIs, one act per scenario.
Output is ASCII so it survives any console encoding.
"""

from __future__ import annotations

import asyncio
import tempfile
from itertools import groupby
from pathlib import Path

from dashboard.app import Dashboard
from healer import metrics
from healer.jev import render_option
from healer.models import AuditEvent

ACTS = [
    (None, "Clean start: no drift, both agents finish the task"),
    ("M5", "M5 hits get_user mid-run: nested payload plus a required tenant header"),
    ("M3", "M3 on another run: the get_user response comes back nested"),
    ("M8", "M8 hits create_ticket: a new required `priority` with no source for it"),
]


def task_done(data: dict) -> bool:
    user = data["users"]["123"]
    return (
        user["email"] == "ada.new@example.com"
        and user["manager_id"] == "456"
        and [t["title"] for t in data["tickets"]] == ["Email changed"]
    )


def fix_text(fix: dict | None) -> str:
    return render_option(fix) if fix else "no fix"


def print_act(s: dict) -> None:
    for agent, run in s["runs"].items():
        calls = [(e["tool"], e["class"]) for e in s["events"] if e["agent"] == agent]
        flow = ", ".join(
            f"{tool} {cls}" + (f" x{n}" if (n := len(list(g))) > 1 else "")
            for (tool, cls), g in groupby(calls)
        )
        end = "iteration cap" if run["hit_limit"] else run["status"]
        done = "yes" if task_done(s["mocks"][agent]["data"]) else "NO"
        print(f"  {agent:<9} {flow}")
        print(
            f"  {'':<9} -> {end} after {run['tool_calls']} calls, task complete: {done}"
        )
    for h in s["heals"]:
        verdict = h["outcome"] + (f" ({h['reason']})" if h["reason"] else "")
        print(
            f"  HEAL {h['tool']} {h['class']} tier {h['tier']}: {verdict} in {h['mttr_ms']} ms"
        )
        print(f"       {fix_text(h['fix'])}")
    tickets = {a: len(m["data"]["tickets"]) for a, m in s["mocks"].items()}
    print(f"  tickets created: {tickets}")


def print_summary(events: list[AuditEvent], dash: Dashboard) -> None:
    print("\n== Patch log ==")
    print(
        f"  {'tool':<14}{'class':<6}{'tier':<5}{'path':<7}{'outcome':<11}{'reason':<15}{'mttr':<9}fix"
    )
    for e in events:
        fix = dash.store.get_fix(e.fix_id) if e.fix_id is not None else None
        ops = fix_text(
            {"request_ops": fix.request_ops, "response_ops": fix.response_ops}
            if fix
            else None
        )
        print(
            f"  {e.tool:<14}{e.cls:<6}{e.tier:<5}{e.path or '-':<7}{e.outcome:<11}"
            f"{e.reason or '-':<15}{str(e.mttr_ms) + ' ms':<9}{ops}"
        )
    print("\n== MTTR (recovered heals) ==")
    for tier, m in metrics.mttr_summary(events).items():
        print(
            f"  tier {int(tier)}: n={m['n']} p50={m['p50_ms']:.0f} ms p95={m['p95_ms']:.0f} ms"
        )
    counts = metrics.outcome_counts(events)
    print(f"  outcomes: {counts['by_outcome']}  reasons: {counts['by_reason']}")


async def main(step: float = 0.15) -> list[AuditEvent]:
    """Run every act from a cold store; `step` is the agents' pause between calls."""
    dash = Dashboard(str(Path(tempfile.mkdtemp()) / "demo.db"))
    try:
        for mutation, title in ACTS:
            print(f"\n== {title} ==")
            await dash.start("scripted", step)
            if mutation:  # the agents wait LEAD_IN_STEPS steps before their first call
                await dash.mutate(mutation)
            await dash.wait()
            print_act(dash.state())
        events = dash.store.audit_events()
        print_summary(events, dash)
        return events
    finally:
        await dash.aclose()


if __name__ == "__main__":
    asyncio.run(main())
