"""E1 retry policy (FR-11.1): bounded backoff with jitter. E1 is retried here and never healed."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from healer.models import ErrorClass, Outcome
from healer.settings import E1_BACKOFF_S, E1_JITTER_MAX_S


def random_jitter() -> float:
    return random.uniform(0, E1_JITTER_MAX_S)


async def with_retries(
    attempt: Callable[[], Awaitable[Outcome]],
    *,
    remaining: Callable[[], float],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    jitter: Callable[[], float] = random_jitter,
) -> Outcome:
    """Run `attempt`, then retry E1 up to len(E1_BACKOFF_S) times while the budget lasts."""
    outcome = await attempt()
    for backoff in E1_BACKOFF_S:
        if outcome.cls is not ErrorClass.E1:
            break
        hint = outcome.data["retry_after"] if outcome.data else 0.0  # detect.py
        delay = max(backoff + jitter(), hint)
        if delay > remaining():
            break
        await sleep(delay)
        outcome = await attempt()
    return outcome
