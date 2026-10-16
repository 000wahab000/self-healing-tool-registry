"""AC-52: every recorded MCP drift fixture loads, and its tools differ before and after."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mock_api.mcp_drift_server import MUTATIONS

ROOT = Path(__file__).resolve().parents[2] / "mock_api" / "fixtures" / "mcp"
FILES = sorted(ROOT.glob("*/*.json"))


def test_ac_52_every_mutation_has_a_users_fixture():
    assert {p.stem for p in (ROOT / "users").glob("*.json")} == set(MUTATIONS)


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_ac_52_fixture_loads_and_differs(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert set(doc) == {"before", "after"}
    assert doc["before"] and doc["after"] and doc["before"] != doc["after"]
    for tool in (*doc["before"], *doc["after"]):
        assert not tool["name"].startswith("__admin")
        assert "inputSchema" in tool


@pytest.mark.asyncio
async def test_ac_52_fixtures_match_a_fresh_recording(tmp_path):
    from bench.record_mcp_fixtures import record

    written = await record(tmp_path)
    assert sorted(p.relative_to(tmp_path) for p in written) == sorted(
        p.relative_to(ROOT) for p in FILES
    )
    for p in written:
        recorded = json.loads(p.read_text(encoding="utf-8"))
        assert recorded == json.loads(
            (ROOT / p.relative_to(tmp_path)).read_text(encoding="utf-8")
        )
