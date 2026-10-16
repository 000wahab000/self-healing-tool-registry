from __future__ import annotations

import asyncio

from demo.mcp_agent import run_demo
from healer.models import HealOutcome


def test_ac_67_scripted_demo_heals_mid_task_rename(tmp_path, capsys):
    out = asyncio.run(run_demo("scripted", db=str(tmp_path / "demo.db")))

    assert out["calls"] == 4
    assert out["errors"] == 0  # the agent never received an error
    audit = out["audit"]
    assert [(e.tool, e.outcome) for e in audit] == [
        ("users__get_user", HealOutcome.RECOVERED)
    ]
    assert "heal  users__get_user: RECOVERED" in capsys.readouterr().out
