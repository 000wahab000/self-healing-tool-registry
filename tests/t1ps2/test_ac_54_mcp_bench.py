"""AC-54: MCP drift scenarios in the benchmark: heal, refuse safely, never false-patch."""

from __future__ import annotations

import pytest

from bench import run
from healer.metrics import false_patch_rate, safe_refusal


@pytest.mark.asyncio
async def test_ac_54_mcp_scenarios():
    rows = await run.mcp_bench(1)  # no repair agent: T-MOVE is skipped
    healing = [r for r in rows if r["agent"] == "healing"]
    assert "MCP-T-MOVE" not in {r["scenario"] for r in rows}
    for r in healing:
        name = r["scenario"].removeprefix("MCP-")
        if name in run.MCP_HEALABLE:
            assert r["task_done"] and r["state_ok"] and r["expectation_met"]
            assert [h["outcome"] for h in r["heals"]] == ["RECOVERED"]
        else:
            assert not r["task_done"] and r["state_ok"] and r["expectation_met"]
            assert [h["reason"] for h in r["heals"]] == ["NO_SAFE_VALUE"]
    assert safe_refusal(healing) == {"refused": 2, "runs": 2}
    assert false_patch_rate(healing)["false_patches"] == 0
    baseline = [r for r in rows if r["agent"] == "baseline"]
    assert not any(r["task_done"] for r in baseline)
    assert not any(r["heals"] for r in baseline)


def test_ac_54_report_has_mcp_section():
    row = {
        "scenario": "MCP-M1",
        "phase": "mcp",
        "task_done": True,
        "state_ok": True,
        "expectation_met": True,
        "must_refuse": False,
        "invented_sent": False,
        "heals": [],
        "hit_limit": False,
        "error": None,
    }
    rows = [{**row, "agent": "healing"}, {**row, "agent": "baseline"}]
    assert any(
        line.startswith("## MCP gateway")
        for line in run.mcp_section(rows, None, llm=False)
    )
