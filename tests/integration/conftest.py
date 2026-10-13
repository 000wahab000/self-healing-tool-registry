from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from healer.registry import Registry
from mock_api.app import create_app

CFG = {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}
TOOLS_JSON = Path(__file__).parents[2] / "config" / "tools.json"


@pytest.fixture
def api():
    return create_app()


@pytest.fixture
async def client(api):
    transport = httpx.ASGITransport(app=api)
    async with httpx.AsyncClient(transport=transport, base_url="http://mock") as c:
        yield c


@pytest.fixture
def tools_config() -> dict:
    return json.loads(TOOLS_JSON.read_text())


@pytest.fixture
async def registry(client, tools_config):
    reg = Registry(client, tools_config, CFG)
    await reg.load()
    return reg
