"""Benchmark metrics (FR-15.4, FR-15.5) over audit events and benchmark run rows.

Inputs are either `AuditEvent`s from the store or their `results.jsonl` shape (a dict with
the same fields, codes as strings). A *run row* is one benchmark run; the keys read here are
`scenario`, `agent`, `task_done`, `state_ok`, `must_refuse`, `expected_reason`,
`invented_sent`, `llm_tokens`, `jev_tokens` and `heals` (each with `outcome`, `reason`,
`tier`, `mttr_ms`, `heal_ms`, `jev_tokens`).

`jev_tokens` is never added to `llm_tokens` (FR-8.7); it is reported in its own column.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from statistics import mean, median
from typing import Any

from healer.models import AuditEvent, HealOutcome, Tier

RunRow = Mapping[str, Any]


def _val(record: Any, key: str, default: Any = None) -> Any:
    return record.get(key, default) if isinstance(record, Mapping) else getattr(record, key, default)


def percentiles(values: Iterable[float]) -> dict[str, float]:
    """FR-15.5: count, mean, median (p50) and nearest-rank p95 of one sample."""
    sample = sorted(values)
    n = len(sample)
    return {
        "n": n,
        "mean": mean(sample) if sample else 0.0,
        "p50": median(sample) if sample else 0.0,
        "p95": sample[(95 * n + 99) // 100 - 1] if sample else 0.0,  # ceil(0.95 n)-th
    }


def timing_summary(events: Iterable[Any]) -> dict[Tier, dict]:
    """Per tier: count and mean/p50/p95 of `mttr_ms` and of `heal_ms`, over RECOVERED events.

    MTTR (first failing response -> first verified-correct result) and the registry's own
    heal time (failure detection -> result, `heal_ms`) are reported side by side (AC-14).
    """
    recovered: dict[Tier, list[tuple[int, int]]] = {}
    for e in events:
        if HealOutcome(_val(e, "outcome")) is not HealOutcome.RECOVERED:
            continue
        recovered.setdefault(Tier(_val(e, "tier")), []).append(
            (_val(e, "mttr_ms", 0), _val(e, "heal_ms", 0))
        )
    return {
        tier: {
            "n": len(pairs),
            "mttr_ms": percentiles(mttr for mttr, _ in pairs),
            "heal_ms": percentiles(heal for _, heal in pairs),
        }
        for tier, pairs in sorted(recovered.items())
    }


def mttr_summary(events: Iterable[AuditEvent]) -> dict[Tier, dict[str, float]]:
    """Per tier: count, median and nearest-rank p95 of `mttr_ms` over RECOVERED events."""
    return {
        tier: {
            "n": stats["n"],
            "p50_ms": stats["mttr_ms"]["p50"],
            "p95_ms": stats["mttr_ms"]["p95"],
        }
        for tier, stats in timing_summary(events).items()
    }


def outcome_counts(events: Iterable[AuditEvent]) -> dict[str, dict[str, int]]:
    events = list(events)
    return {
        "by_outcome": dict(Counter(e.outcome.value for e in events)),
        "by_reason": dict(Counter(e.reason.value for e in events if e.reason)),
    }


def ztar(rows: Iterable[RunRow], scenarios: Iterable[str]) -> dict[str, int]:
    """FR-15.4 ZTAR: over `scenarios` only, the runs where the task completed and the final
    mock state is correct. The caller passes the healable mutations; M6 is reported
    separately and M8 (a refusal) and the controls are never folded in (AC-15)."""
    wanted = set(scenarios)
    picked = [r for r in rows if r["scenario"] in wanted]
    return {
        "adapted": sum(1 for r in picked if r["task_done"] and r["state_ok"]),
        "runs": len(picked),
    }


def safe_refusal(rows: Iterable[RunRow]) -> dict[str, int]:
    """FR-15.4 Safe-Refusal Rate: over the runs marked `must_refuse` (M8, and M6-N with Jev
    disabled or unavailable), the runs that aborted with `expected_reason` and sent no
    request carrying an invented value."""
    picked = [r for r in rows if r["must_refuse"]]
    return {
        "refused": sum(
            1
            for r in picked
            if not r["invented_sent"]
            and r["expected_reason"] in {h["reason"] for h in r["heals"]}
        ),
        "runs": len(picked),
    }


def false_patch_rate(rows: Iterable[RunRow]) -> dict[str, int]:
    """Count wrong accepted requests when the request-level oracle is available."""
    healed = [
        r
        for r in rows
        if any(h["outcome"] == HealOutcome.RECOVERED for h in r["heals"])
    ]
    return {
        "false_patches": sum(
            1
            for r in healed
            if (
                r["oracle"] == "WRONG_ACCEPTED"
                if "oracle" in r
                else not r["state_ok"]
            )
        ),
        "healed": len(healed),
    }


def token_overhead(
    rows: Iterable[RunRow], *, clean: str = "CLEAN"
) -> dict[str, dict[str, int]]:
    """FR-15.4 Token Overhead (healing) and wasted tokens (baseline): the mutated run's
    total `llm_tokens` minus the same agent's median `llm_tokens` on `clean` runs.

    `jev_tokens` is never added to that subtraction (FR-8.7); `token_summary` reports it in
    its own column. Returns {} when the benchmark has no clean runs to subtract."""
    rows = list(rows)

    def med(scenario: str, agent: str) -> float | None:
        tokens = [
            r["llm_tokens"]
            for r in rows
            if (r["scenario"], r["agent"]) == (scenario, agent)
        ]
        return median(tokens) if tokens else None

    agents = ("healing", "baseline")
    clean_tokens = {a: med(clean, a) for a in agents}
    if any(v is None for v in clean_tokens.values()):
        return {}
    overhead: dict[str, dict[str, int]] = {}
    for scenario in dict.fromkeys(r["scenario"] for r in rows if r["scenario"] != clean):
        mutated = {a: med(scenario, a) for a in agents}
        if any(v is None for v in mutated.values()):
            continue
        overhead[scenario] = {
            a: int(mutated[a] - clean_tokens[a])  # type: ignore[operator]
            for a in agents
        }
    return overhead


def token_summary(rows: Iterable[RunRow]) -> dict[str, dict[str, dict[str, dict[str, float]]]]:
    """FR-15.5, per scenario and agent: mean/p50/p95 of `llm_tokens` per run and of
    `jev_tokens` per run, kept apart (FR-8.7)."""
    pooled: dict[str, dict[str, dict[str, list[float]]]] = {}
    for r in rows:
        by_agent = pooled.setdefault(r["scenario"], {})
        for key, value in (
            ("llm_tokens", r["llm_tokens"]),
            ("jev_tokens", r["jev_tokens"]),
        ):
            by_agent.setdefault(r["agent"], {}).setdefault(key, []).append(value)
    return {
        scenario: {
            agent: {key: percentiles(vals) for key, vals in metrics.items()}
            for agent, metrics in by_agent.items()
        }
        for scenario, by_agent in pooled.items()
    }
