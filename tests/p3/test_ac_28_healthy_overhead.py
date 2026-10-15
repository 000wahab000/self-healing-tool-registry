"""AC-28 (FR-17.1): a healthy Registry.call() adds < 10 ms p95 over the raw transport.

The measurement lives in `bench/overhead.py`; this test checks the acceptance criterion.
"""

from __future__ import annotations

from bench import overhead


async def test_ac_28_healthy_overhead() -> None:
    result = await overhead.measure()

    assert result["samples"] >= 200
    for series in ("registry", "direct", "overhead"):
        assert "p50_ms" in result[series] and "p95_ms" in result[series]

    # AC-28: the registry's own work, excluding network, stays under 10 ms p95.
    assert result["overhead"]["p95_ms"] < 10.0
