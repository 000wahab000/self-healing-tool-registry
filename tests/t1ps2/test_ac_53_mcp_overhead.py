"""AC-53: the MCP healthy-call overhead bench runs and returns finite numbers."""

from __future__ import annotations

import math

import pytest

from bench import overhead


@pytest.mark.asyncio
async def test_ac_53_mcp_overhead_runs_and_returns_numbers():
    result = await overhead.measure_mcp(samples=200, warmup=5)
    assert result["samples"] == 200
    for series in ("registry", "direct", "overhead"):
        for key in ("p50_ms", "p95_ms", "mean_ms"):
            assert math.isfinite(result[series][key])
    assert result["registry"]["p50_ms"] >= 0 and result["direct"]["p50_ms"] >= 0
