from __future__ import annotations

import asyncio

import pytest

from healer.models import DecisionPath, ErrorClass, Fix, FixStatus, Tier
from healer.patch_trace import collect_patch_call, request_applied


@pytest.mark.asyncio
async def test_ac_112_concurrent_call_patch_traces_are_isolated() -> None:
    move = {"op": "move", "from": ["query", "old"], "to": ["query", "new"]}
    fixes = [
        Fix(
            fingerprint=f"{i:016x}",
            signature={},
            tool=f"tool{i}",
            cls=ErrorClass.E2,
            request_ops=[{**move, "from": ["query", f"old{i}"]}],
            response_ops=[],
            tier=Tier.T1,
            source=DecisionPath.diff,
            schema_hash="schema",
            status=FixStatus.active,
            fix_id=i,
        )
        for i in (1, 2)
    ]
    barrier = asyncio.Barrier(2)

    async def record(fix: Fix) -> list[dict]:
        with collect_patch_call() as trace:
            await barrier.wait()
            request_applied(fix)
            return trace.as_list()

    one, two = await asyncio.gather(*(record(fix) for fix in fixes))
    assert one[0]["request_ops"][0]["from"] == ["query", "old1"]
    assert two[0]["request_ops"][0]["from"] == ["query", "old2"]
