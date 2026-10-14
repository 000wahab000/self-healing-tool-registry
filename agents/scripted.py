"""Scripted agent: the demo task as fixed tool calls. No LLM and no tokens.

It stands in for the LLM agents when no key is available, and paces the live demo.
The baseline variant re-sends a failing call with the same arguments until the
iteration cap, which is the loop the problem statement describes for standard
frameworks; the healing variant moves on after a `retry: false` error, as its prompt says.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence

from agents.common import MAX_ITERATIONS, Execute, RunResult
from healer.models import ErrorClass

STEPS = [
    ("get_user", {"user_id": "123"}),
    ("update_email", {"user_id": "123", "email": "ada.new@example.com"}),
    ("set_manager", {"user_id": "123", "manager_id": "456"}),
    ("create_ticket", {"user_id": "123", "title": "Email changed"}),
]


async def run(
    execute: Execute,
    agent: str,
    *,
    retry_same_args: bool,
    store=None,
    run_id: str = "",
    step_delay: float = 0.0,
    steps: Sequence[tuple[str, dict]] = STEPS,
) -> RunResult:
    calls = 0
    for name, args in steps:
        while True:
            if calls == MAX_ITERATIONS:
                return RunResult("iteration cap reached", calls, 0, True, None)
            calls += 1
            t0 = time.perf_counter()
            _, cls = await execute(name, dict(args))
            if store:
                store.log_call(
                    agent, run_id, name, cls, round((time.perf_counter() - t0) * 1000)
                )
            await asyncio.sleep(step_delay)
            if cls is ErrorClass.OK or not retry_same_args:
                break
    return RunResult("done", calls, 0, False, None)
