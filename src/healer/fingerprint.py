"""Stable break identity (FR-4): same break, same fingerprint, across runs and restarts."""

from __future__ import annotations

import json

from healer import canonical
from healer.models import ErrorClass, Outcome


def fingerprint(
    tool: str, outcome: Outcome, diff_signature: str | None = None
) -> tuple[str, dict]:
    triples = {
        canonical.dumps(
            [v.side.value, ["[]" if isinstance(p, int) else p for p in v.path], v.kind]
        )
        for v in outcome.violations
    }
    signature: dict = {
        "tool": tool,
        "proto": outcome.protocol,
        "class": outcome.cls.value,
        "code": outcome.raw_code,
        # sorted canonical strings give a deterministic order across processes
        "v": [json.loads(t) for t in sorted(triples)],
    }
    if outcome.cls is ErrorClass.E6:
        signature["diff"] = diff_signature
    return canonical.sha256(signature)[:16], signature
