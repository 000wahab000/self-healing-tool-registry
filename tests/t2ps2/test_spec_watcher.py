"""AC-55: the spec watcher snapshots changes, idles on unchanged specs, backs off failures
and calls Healer.precompute only when the healer provides it (FR-18)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from healer.models import LoadedSpec
from healer.spec_watcher import SpecWatcher


class Clock:
    """Injected clock/sleep pair: sleeping moves time forward with no real wait."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class Recorder:
    """A SpecSource that serves a scripted sequence and counts its own calls."""

    def __init__(self, *results: object) -> None:
        self._results = list(results)
        self.calls = 0

    async def __call__(self) -> LoadedSpec:
        self.calls += 1
        result = self._results[min(self.calls - 1, len(self._results) - 1)]
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, LoadedSpec)
        return result


class Store:
    """Minimal FixStore stand-in: records the snapshots the watcher saves."""

    def __init__(self) -> None:
        self.saved: list[str] = []

    def save_spec(self, spec_hash: str, spec: dict) -> None:
        self.saved.append(spec_hash)


def spec(tag: str) -> LoadedSpec:
    return LoadedSpec({"tag": tag}, {}, tag)


class SpyHealer:
    def __init__(self) -> None:
        self.pairs: list[tuple[str, str]] = []

    async def precompute(self, old: LoadedSpec, new: LoadedSpec) -> int:
        self.pairs.append((old.spec_hash, new.spec_hash))
        return len(self.pairs)


def watcher(
    source, clock, *, store=None, healer=None, interval=10.0, backoff_max=100.0
):
    return SpecWatcher(
        {"api": source},
        store=store,
        healer=healer,
        interval=interval,
        backoff_max=backoff_max,
        clock=clock,
    )


async def test_ac_55_change_is_snapshotted_within_one_interval():
    clock = Clock()
    source = Recorder(spec("v1"), spec("v2"))
    store = Store()
    healer = SpyHealer()
    w = watcher(source, clock, store=store, healer=healer)

    assert await w.poll() == []  # first observation: baseline only
    assert store.saved == ["v1"]
    assert healer.pairs == []
    assert source.calls == 1

    clock.now = 5.0
    assert await w.poll() == []  # not due yet: the source is not polled again
    assert source.calls == 1

    clock.now = 10.0  # one interval later
    assert await w.poll() == ["api"]
    assert store.saved == ["v1", "v2"]
    assert healer.pairs == [("v1", "v2")]
    assert w.last["api"].spec_hash == "v2"


async def test_ac_55_unchanged_spec_causes_no_work():
    clock = Clock()
    source = Recorder(spec("v1"))
    store = Store()
    healer = SpyHealer()
    w = watcher(source, clock, store=store, healer=healer)

    assert await w.poll() == []
    clock.now = 10.0
    assert await w.poll() == []  # polled again, but the hash is identical

    assert source.calls == 2
    assert store.saved == ["v1"]  # no second snapshot
    assert healer.pairs == []  # no precompute


async def test_ac_55_failing_source_backs_off_and_recovers():
    clock = Clock()
    source = Recorder(
        httpx.ConnectError("down"), httpx.ConnectError("down"), spec("v1")
    )
    store = Store()
    w = watcher(source, clock, store=store, interval=10.0, backoff_max=30.0)

    assert await w.poll() == []  # 1st failure: next due at 0 + 20
    assert w.failures("api") == 1
    assert source.calls == 1

    clock.now = 5.0
    assert await w.poll() == []  # too soon: backed off
    assert source.calls == 1

    clock.now = 20.0
    assert await w.poll() == []  # 2nd failure: 40 capped at backoff_max 30 -> due at 50
    assert w.failures("api") == 2
    assert source.calls == 2

    clock.now = 30.0
    assert await w.poll() == []  # still backed off
    assert source.calls == 2

    clock.now = 50.0
    assert await w.poll() == []  # recovers: baseline snapshot, no change pair
    assert w.failures("api") == 0
    assert source.calls == 3
    assert store.saved == ["v1"]


async def test_ac_55_precompute_guarded_when_healer_lacks_it():
    clock = Clock()
    source = Recorder(spec("v1"), spec("v2"))
    store = Store()
    w = watcher(source, clock, store=store, healer=object())  # no precompute attribute

    await w.poll()
    clock.now = 10.0
    assert await w.poll() == ["api"]  # the change is recorded without a healer
    assert store.saved == ["v1", "v2"]


async def test_ac_55_precompute_not_called_without_a_healer():
    clock = Clock()
    source = Recorder(spec("v1"), spec("v2"))
    w = watcher(source, clock, store=Store(), healer=None)

    await w.poll()
    clock.now = 10.0
    assert await w.poll() == ["api"]  # no AttributeError, the hook is simply absent


async def test_ac_55_start_runs_in_the_background_and_stops():
    clock = Clock()
    source = Recorder(spec("v1"))

    async def sleep(seconds: float) -> None:
        clock.now += seconds
        await asyncio.sleep(0)  # yield, like a real sleep

    w = SpecWatcher({"api": source}, interval=10.0, clock=clock, sleep=sleep)
    task = w.start()
    for _ in range(3):
        await asyncio.sleep(0)

    assert not task.done()  # still looping in the background
    assert source.calls >= 1

    await w.stop()
    assert task.done()
    assert task.cancelled()


async def test_interval_must_be_positive():
    with pytest.raises(ValueError):
        SpecWatcher({}, interval=0.0)


async def test_backoff_max_must_cover_the_interval():
    with pytest.raises(ValueError):
        SpecWatcher({}, interval=10.0, backoff_max=5.0)
