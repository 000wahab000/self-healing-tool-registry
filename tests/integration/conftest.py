from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from healer.jev import JevClient
from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app

CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}
TOOLS_JSON = Path(__file__).parents[2] / "config" / "tools.json"


class Wire(httpx.AsyncBaseTransport):
    """The in-process mock API, with knobs: per-request delay (lets calls interleave) and dead paths."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self.inner = inner
        self.delay = 0.0
        self.down: set[str] = set()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path in self.down:
            raise httpx.ConnectError("down", request=request)
        if self.delay:
            await asyncio.sleep(self.delay)
        return await self.inner.handle_async_request(request)


@pytest.fixture
def api():
    return create_app()


@pytest.fixture
def wire(api) -> Wire:
    return Wire(httpx.ASGITransport(app=api))


@pytest.fixture
async def client(wire):
    async with httpx.AsyncClient(transport=wire, base_url="http://mock") as c:
        yield c


@pytest.fixture
def tools_config() -> dict:
    return json.loads(TOOLS_JSON.read_text())


@pytest.fixture
async def registry(client, tools_config):
    reg = Registry(client, tools_config, CFG)
    await reg.load()
    return reg


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "heal.db"))
    yield s
    s.close()


@pytest.fixture
async def jev():
    async with httpx.AsyncClient() as http:
        yield JevClient("sk-test", client=http)


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def make_registry(client, tools_config, store, sleeps):
    """Healing registry (store, no Jev, no real sleeping); keyword arguments override."""

    async def make(**kw) -> Registry:
        async def sleep(seconds: float) -> None:
            sleeps.append(seconds)

        defaults = {"store": store, "sleep": sleep, "jitter": lambda: 0.0}
        reg = Registry(client, tools_config, CFG, **defaults | kw)
        await reg.load()
        return reg

    return make
