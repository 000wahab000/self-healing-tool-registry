"""T1-7: record `tools/list` before and after each mutation (AC-52).

Writes mock_api/fixtures/mcp/<profile>/<mutation>.json = {"before": [...], "after": [...]}
for every mutation that changes the profile's tools, excluding the `__admin*` tools.

    python -m bench.record_mcp_fixtures
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from bench.mcp_session import session
from mock_api.mcp_drift_server import MUTATIONS, create_drift_server

OUT = Path(__file__).resolve().parents[1] / "mock_api" / "fixtures" / "mcp"
PROFILES = ("users", "tickets")


async def _tools(sess) -> list[dict]:
    listed = await sess.list_tools()
    return [
        t.model_dump(by_alias=True, exclude_none=True)
        for t in listed.tools
        if not t.name.startswith("__admin")
    ]


async def record(out: Path = OUT) -> list[Path]:
    written = []
    for profile in PROFILES:
        drift = create_drift_server(profile=profile)
        async with session(drift) as sess:
            before = await _tools(sess)
            for mutation in MUTATIONS:
                drift.apply_mutation(mutation)
                after = await _tools(sess)
                drift.reset()
                if after == before:
                    continue
                path = out / profile / f"{mutation}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps({"before": before, "after": after}, indent=2) + "\n",
                    encoding="utf-8",
                )
                written.append(path)
    return written


if __name__ == "__main__":
    for p in asyncio.run(record()):
        print(p)
