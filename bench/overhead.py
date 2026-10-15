"""AC-28 (FR-17.1): healthy-call overhead of the registry over the raw transport.

Times healthy ``Registry.call()`` calls against the in-process mock and subtracts the
same request sent straight through the transport the registry wraps. Prints p50 and p95.

    python -m bench.overhead
"""

from __future__ import annotations

import asyncio
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

import httpx

from healer.adapters import rest
from healer.registry import Registry
from healer.settings import REQUEST_TIMEOUT_S
from mock_api.app import create_app

TOOLS_JSON = Path(__file__).resolve().parents[1] / "config" / "tools.json"
CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}
TOOL = "get_user"
ARGS = {"user_id": "123"}
SAMPLES = 250  # AC-28 requires at least 200 calls per side
WARMUP = 25


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile (no interpolation), matching ``healer.metrics``."""
    if not values:
        raise ValueError("no samples")
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered))
    return ordered[min(max(rank - 1, 0), len(ordered) - 1)]


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.fmean(values) * 1000,
        "p50_ms": percentile(values, 50) * 1000,
        "p95_ms": percentile(values, 95) * 1000,
    }


async def measure(
    samples: int = SAMPLES,
    warmup: int = WARMUP,
    tool: str = TOOL,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-call times for the registry and for the raw transport, and their difference."""
    args = dict(ARGS if args is None else args)
    api = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://mock"
    ) as client:
        registry = Registry(client, json.loads(TOOLS_JSON.read_text()), CFG)
        await registry.load()

        # The identical wire request, built once: the direct baseline only sends it.
        direct_doc = registry.base_doc(registry.defs[tool], args)

        async def registry_call() -> dict:
            return await registry.call(tool, dict(args))

        async def direct_call() -> None:
            await rest.send(client, direct_doc, REQUEST_TIMEOUT_S)

        first = await registry_call()
        if "error" in first:
            raise ValueError(f"healthy baseline call failed: {first}")

        for _ in range(warmup):
            await registry_call()
            await direct_call()

        registry_times: list[float] = []
        direct_times: list[float] = []
        for _ in range(samples):
            start = time.perf_counter()
            await registry_call()
            registry_times.append(time.perf_counter() - start)

            start = time.perf_counter()
            await direct_call()
            direct_times.append(time.perf_counter() - start)

    overhead = [r - d for r, d in zip(registry_times, direct_times, strict=True)]
    return {
        "samples": samples,
        "registry": summarize(registry_times),
        "direct": summarize(direct_times),
        "overhead": summarize(overhead),
    }


async def _main() -> None:
    result = await measure()
    print(f"healthy-call overhead (n={result['samples']} per side, {TOOL})")
    for series in ("registry", "direct", "overhead"):
        s = result[series]
        print(
            f"  {series:9s} p50={s['p50_ms']:.3f} ms  "
            f"p95={s['p95_ms']:.3f} ms  mean={s['mean_ms']:.3f} ms"
        )


if __name__ == "__main__":
    asyncio.run(_main())
