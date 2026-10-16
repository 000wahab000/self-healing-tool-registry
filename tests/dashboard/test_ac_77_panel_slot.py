"""AC-77: A plug-in slot for dashboard panels (V0 foundation)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from dashboard.app import create_app

ROOT = Path(__file__).parents[2]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ("JEV_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY", "DB_PATH"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "dash.db"))


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dash") as c:
        yield c
    await app.state.dash.aclose()


async def test_ac_77_get_registry_js_returns_200_with_js_content_type(client):
    res = await client.get("/panels/registry.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"].lower()
    assert "window.HealerPanels" in res.text


async def test_ac_77_index_html_contains_container_and_script(client):
    res = await client.get("/live")
    assert res.status_code == 200
    html = res.text
    assert 'id="panels-container"' in html or 'id="panels"' in html
    assert "panels/registry.js" in html
    assert "HealerPanels.refresh" in html


async def test_ac_77_missing_panel_returns_404(client):
    res = await client.get("/panels/nonexistent.js")
    assert res.status_code == 404


async def test_ac_77_path_traversal_returns_404(client):
    res = await client.get("/panels/../app.py")
    assert res.status_code in (404, 400)
