"""Spec watcher (T2-7, FR-18): poll each SpecSource, snapshot changes, feed Healer.precompute.

Runs as a background task and never blocks a tool call. The clock and the sleep are injected;
a source that fails is backed off on its own and recovers on its next success.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

import httpx

from healer.models import LoadedSpec, SpecSource

if TYPE_CHECKING:
    from healer.store import FixStore

# Defaults for callers that pass none. settings.py is owned by T1-PS1; move these there when the
# watcher interval becomes a shared setting.
WATCH_INTERVAL_S = 30.0
WATCH_BACKOFF_MAX_S = 300.0
_MAX_BACKOFF_EXP = 20  # 2**20 x interval already dwarfs any cap we set


class SpecWatcher:
    def __init__(
        self,
        sources: Mapping[str, SpecSource],
        *,
        store: FixStore | None = None,
        healer: object | None = None,
        interval: float = WATCH_INTERVAL_S,
        backoff_max: float = WATCH_BACKOFF_MAX_S,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        if backoff_max < interval:
            raise ValueError("backoff_max must be >= interval")
        self._sources = dict(sources)
        self._store = store
        self._healer = healer
        self._interval = interval
        self._backoff_max = backoff_max
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, LoadedSpec] = {}
        self._failures: dict[str, int] = {}
        self._next_due: dict[str, float] = {name: clock() for name in self._sources}
        self._task: asyncio.Task[None] | None = None

    async def poll(self) -> list[str]:
        """Poll every due source once. Return the names whose spec changed."""
        now = self._clock()
        changed: list[str] = []
        for name, source in self._sources.items():
            if self._next_due.get(name, 0.0) > now:
                continue
            spec = await self._load(name, source)
            if spec is None:
                continue
            old = self._last.get(name)
            if old is not None and old.spec_hash == spec.spec_hash:
                continue  # unchanged: no snapshot, no precompute
            self._last[name] = spec
            self._snapshot(spec)
            if old is not None:
                await self._precompute(old, spec)
                changed.append(name)
        return changed

    async def _load(self, name: str, source: SpecSource) -> LoadedSpec | None:
        try:
            spec = await source()
        except (httpx.HTTPError, ValueError):
            self._on_failure(name)
            return None
        self._failures[name] = 0
        self._next_due[name] = self._clock() + self._interval
        return spec

    def _on_failure(self, name: str) -> None:
        failures = self._failures[name] = self._failures.get(name, 0) + 1
        delay = min(
            self._interval * 2 ** min(failures, _MAX_BACKOFF_EXP),
            self._backoff_max,
        )
        self._next_due[name] = self._clock() + delay

    def _snapshot(self, spec: LoadedSpec) -> None:
        if self._store is not None:
            sanitize = getattr(self._healer, "sanitize_spec", None)
            raw = sanitize(spec.raw) if callable(sanitize) else spec.raw
            self._store.save_spec(spec.spec_hash, raw)

    async def _precompute(self, old: LoadedSpec, new: LoadedSpec) -> None:
        """Contract 5: only the healer that provides precompute is called; snapshots still save."""
        precompute: Any = getattr(self._healer, "precompute", None)
        if precompute is None:
            return
        result = precompute(old, new)
        if inspect.isawaitable(result):
            await result

    async def run(self) -> None:
        while True:
            try:
                await self.poll()
            except Exception:  # a bad spec or a store error must not stop the watcher for good
                logging.getLogger(__name__).exception("spec watcher poll failed")
            await self._sleep(self._delay())

    def _delay(self) -> float:
        now = self._clock()
        due = min(self._next_due.values(), default=now + self._interval)
        return max(0.0, due - now)

    def start(self) -> asyncio.Task[None]:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @property
    def last(self) -> dict[str, LoadedSpec]:
        """The spec last seen per source (read-only copy)."""
        return dict(self._last)

    def failures(self, name: str) -> int:
        return self._failures.get(name, 0)
