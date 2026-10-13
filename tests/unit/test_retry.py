from __future__ import annotations

import pytest

from healer import retry
from healer.models import ErrorClass, Outcome
from healer.settings import E1_BACKOFF_S, E1_JITTER_MAX_S

E1 = Outcome(ErrorClass.E1, "rest", "503")
OK = Outcome(ErrorClass.OK, "rest", "200", data={"id": "1"})
E2 = Outcome(ErrorClass.E2, "rest", "422")


def hinted(seconds: float) -> Outcome:
    return Outcome(ErrorClass.E1, "rest", "429", data={"retry_after": seconds})


class Script:
    """Attempt callable that replays a fixed list of outcomes and records sleeps."""

    def __init__(self, *outcomes: Outcome) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0
        self.sleeps: list[float] = []

    async def attempt(self) -> Outcome:
        self.calls += 1
        return self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)

    async def run(self, *, jitter=lambda: 0.0, remaining=lambda: 3.5) -> Outcome:
        return await retry.with_retries(
            self.attempt, remaining=remaining, sleep=self.sleep, jitter=jitter
        )


async def test_backoff_sequence_then_gives_up_after_three_retries():
    s = Script(E1)
    assert (await s.run()).cls is ErrorClass.E1
    assert s.calls == 4
    assert s.sleeps == pytest.approx(list(E1_BACKOFF_S))


async def test_success_stops_retrying():
    s = Script(E1, E1, OK)
    assert await s.run() == OK
    assert (s.calls, s.sleeps) == (3, pytest.approx([0.1, 0.2]))


@pytest.mark.parametrize("first", [OK, E2])
async def test_only_e1_is_retried(first):
    s = Script(first)
    assert await s.run() == first
    assert (s.calls, s.sleeps) == (1, [])


async def test_jitter_is_added_to_each_backoff():
    s = Script(E1)
    await s.run(jitter=lambda: E1_JITTER_MAX_S)
    assert s.sleeps == pytest.approx([b + E1_JITTER_MAX_S for b in E1_BACKOFF_S])


async def test_default_jitter_stays_within_bound():
    for _ in range(50):
        s = Script(E1)
        await retry.with_retries(s.attempt, remaining=lambda: 3.5, sleep=s.sleep)
        for slept, backoff in zip(s.sleeps, E1_BACKOFF_S, strict=True):
            assert backoff <= slept <= backoff + E1_JITTER_MAX_S


async def test_retry_after_longer_than_backoff_is_honoured():
    s = Script(hinted(1.5), OK)
    assert await s.run() == OK
    assert s.sleeps == [1.5]


async def test_retry_after_shorter_than_backoff_keeps_backoff():
    s = Script(hinted(0.01), OK)
    await s.run()
    assert s.sleeps == pytest.approx([0.1])


async def test_retry_after_beyond_remaining_budget_gives_up_without_sleeping():
    s = Script(hinted(10.0), OK)
    out = await s.run(remaining=lambda: 3.5)
    assert out.cls is ErrorClass.E1
    assert (s.calls, s.sleeps) == (1, [])


async def test_budget_shrinks_between_retries():
    left = iter([1.0, 0.15, 0.15])
    s = Script(E1)
    await s.run(remaining=lambda: next(left))
    assert s.sleeps == pytest.approx([0.1])  # 0.2 > 0.15 left
    assert s.calls == 2
