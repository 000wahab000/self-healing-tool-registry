"""Heal metrics: pure functions over `Store.audit_events()`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from statistics import median

from healer.models import AuditEvent, HealOutcome, Tier


def mttr_summary(events: Iterable[AuditEvent]) -> dict[Tier, dict[str, float]]:
    """Per tier: count, median and nearest-rank p95 of `mttr_ms` over RECOVERED events."""
    by_tier: dict[Tier, list[int]] = {}
    for e in events:
        if e.outcome is HealOutcome.RECOVERED:
            by_tier.setdefault(e.tier, []).append(e.mttr_ms)
    return {
        tier: {
            "n": len(ms),
            "p50_ms": median(ms),
            "p95_ms": sorted(ms)[(95 * len(ms) + 99) // 100 - 1],  # ceil(0.95 n)-th
        }
        for tier, ms in sorted(by_tier.items())
    }


def outcome_counts(events: Iterable[AuditEvent]) -> dict[str, dict[str, int]]:
    events = list(events)
    return {
        "by_outcome": dict(Counter(e.outcome.value for e in events)),
        "by_reason": dict(Counter(e.reason.value for e in events if e.reason)),
    }
