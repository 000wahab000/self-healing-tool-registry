"""P3-owned fixtures. Mirrors `tests/integration/conftest.py` for the p3 track."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app

CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}
TOOLS_JSON = Path(__file__).parents[2] / "config" / "tools.json"


@pytest.fixture
def api():
    return create_app()


@pytest.fixture
async def client(api):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://mock"
    ) as c:
        yield c


@pytest.fixture
def tools_config() -> dict:
    return json.loads(TOOLS_JSON.read_text())


@pytest.fixture
def store(tmp_path):
    s = Store(str(tmp_path / "heal.db"))
    yield s
    s.close()


@pytest.fixture
def make_registry(client, tools_config, store):
    """Healing registry (store, no Jev, no real sleeping); keyword arguments override."""

    async def make(**kw) -> Registry:
        async def sleep(seconds: float) -> None:
            pass

        defaults = {"store": store, "sleep": sleep, "jitter": lambda: 0.0}
        reg = Registry(client, tools_config, CFG, **defaults | kw)
        await reg.load()
        return reg

    return make
