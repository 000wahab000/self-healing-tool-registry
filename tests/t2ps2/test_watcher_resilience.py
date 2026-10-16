"""The watcher keeps polling after an unexpected error (review fix)."""

from __future__ import annotations

import asyncio

import pytest

from healer.spec_watcher import SpecWatcher


@pytest.mark.asyncio
async def test_watcher_survives_an_unexpected_poll_error():
    calls = 0

    async def source():
        nonlocal calls
        calls += 1
        raise KeyError("malformed spec")  # not HTTPError/ValueError: used to kill the task

    sleeps = 0

    async def sleep(_):
        nonlocal sleeps
        sleeps += 1
        if sleeps >= 3:
            raise asyncio.CancelledError
        await asyncio.sleep(0)

    watcher = SpecWatcher({"spec": source}, interval=1, clock=lambda: 0.0, sleep=sleep)
    with pytest.raises(asyncio.CancelledError):
        await watcher.run()
    assert calls >= 2  # it polled again after the first error
