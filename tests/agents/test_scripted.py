from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from agents import baseline_agent, healing_agent, scripted
from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app

TOOLS = json.loads((Path(__file__).parents[2] / "config" / "tools.json").read_text())
CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}


@pytest.fixture
async def setup(tmp_path):
    api = create_app()
    store = Store(str(tmp_path / "s.db"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://mock"
    ) as client:
        reg = Registry(client, TOOLS, CFG, store=store)
        await reg.load()  # v1 specs come from the clean API
        yield api, client, reg, store
    store.close()


def task_done(state: dict) -> bool:
    user = state["users"]["123"]
    return (
        user["email"] == "ada.new@example.com"
        and user["manager_id"] == "456"
        and [t["title"] for t in state["tickets"]] == ["Email changed"]
    )


@pytest.mark.parametrize("kind", ["healing", "baseline"])
async def test_clean_run_completes_in_four_calls(setup, kind):
    api, client, reg, store = setup
    execute = (
        healing_agent.executor(reg)
        if kind == "healing"
        else baseline_agent.executor(client, reg)
    )
    result = await scripted.run(
        execute, kind, retry_same_args=kind == "baseline", store=store, run_id="r"
    )
    assert (result.tool_calls, result.hit_limit) == (4, False)
    assert task_done(api.state())


async def test_under_m5_healing_completes_and_baseline_loops_to_the_cap(setup):
    api, client, reg, _ = setup
    api.set_mutation("M5")

    healed = await scripted.run(
        healing_agent.executor(reg), "healing", retry_same_args=False
    )
    assert (healed.tool_calls, healed.hit_limit) == (4, False)
    assert task_done(api.state())

    api.reset()
    api.set_mutation("M5")
    looped = await scripted.run(
        baseline_agent.executor(client, reg), "baseline", retry_same_args=True
    )
    assert (looped.tool_calls, looped.hit_limit) == (10, True)
    assert not task_done(api.state())
