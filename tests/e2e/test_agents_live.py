"""Live agent runs: real LLM through NVIDIA NIM, consuming API credits.

Skipped unless RUN_E2E=1 and NVIDIA_API_KEY are set.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import httpx
import pytest

from agents import baseline_agent, common, healing_agent
from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app

pytestmark = [
    pytest.mark.skipif(
        not (os.environ.get("RUN_E2E") == "1" and os.environ.get("NVIDIA_API_KEY")),
        reason="live LLM run: set RUN_E2E=1 and NVIDIA_API_KEY",
    ),
    # Keep model HTTP clients on one loop; their async clients may outlive an individual test loop.
    pytest.mark.asyncio(loop_scope="module"),
]

CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}
TOOLS_JSON = Path(__file__).parents[2] / "config" / "tools.json"


async def run_live(kind: str, tmp_path, mutation: str | None = None):
    """Run the demo task once; returns (RunResult, mock api, [(tool, class), ...])."""
    api = create_app()
    db = str(tmp_path / "heal.db")
    store = Store(db)
    try:
        transport = httpx.ASGITransport(app=api)
        async with httpx.AsyncClient(transport=transport, base_url="http://mock") as c:
            registry = Registry(c, json.loads(TOOLS_JSON.read_text()), CFG, store=store)
            await registry.load()  # v1 tool specs come from the clean API
            api.set_mutation(mutation)
            llm = common.make_llm()
            if kind == "healing":
                agent = healing_agent.build(registry, llm, store, kind)
            else:
                agent = baseline_agent.build(c, registry, llm, store, kind)
            result = await common.run(agent, common.TASK)
    finally:
        store.close()
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT tool, class FROM call_events").fetchall()
    conn.close()
    return result, api, rows


def completed(api, rows) -> bool:
    """New email, manager 456, one ticket, and the lookup itself succeeded."""
    state = api.state()
    user = state["users"]["123"]
    return (
        ("get_user", "OK") in rows
        and user["email"] == "ada.new@example.com"
        and user["manager_id"] == "456"
        and len(state["tickets"]) == 1
    )


@pytest.mark.parametrize("kind", ["healing", "baseline"])
async def test_clean_run_completes(kind, tmp_path):
    result, api, rows = await run_live(kind, tmp_path)
    assert completed(api, rows), result


async def test_m5_healing_agent_completes(tmp_path):
    result, api, rows = await run_live("healing", tmp_path, "M5")
    assert completed(api, rows), result


async def test_m5_baseline_agent_does_not_complete(tmp_path):
    result, api, rows = await run_live("baseline", tmp_path, "M5")
    assert result.error is None, result
    assert result.tool_calls > 0 and rows, result
    assert not completed(api, rows), result


async def test_ac_09_agent_stops_after_retry_false(tmp_path):
    result, api, rows = await run_live("healing", tmp_path, "M8")
    assert [tool for tool, _ in rows].count("create_ticket") == 1, result
    assert api.state()["tickets"] == []
    assert not result.hit_limit
