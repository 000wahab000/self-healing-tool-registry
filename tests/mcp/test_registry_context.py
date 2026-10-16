from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import httpx
import pytest

pytest.importorskip("mcp")


@pytest.mark.parametrize("raise_inside", [False, True])
async def test_registry_context_closes_resources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raise_inside: bool
) -> None:
    from healer import mcp_server
    from healer.store import Store

    clients: list[Any] = []
    original_client = httpx.AsyncClient

    def tracked_client(**kwargs: Any) -> httpx.AsyncClient:
        client = original_client(**kwargs)
        original_aclose = client.aclose
        client.closed = False

        async def close() -> None:
            client.closed = True
            await original_aclose()

        client.aclose = close
        clients.append(client)
        return client

    stores: list[bool] = []
    original_store = Store

    class TrackedStore(original_store):
        def __init__(self, db: str) -> None:
            super().__init__(db)
            stores.append(False)

        def close(self) -> None:
            stores.append(True)
            super().close()

    async def load(self: Any) -> None:
        return None

    monkeypatch.setattr(mcp_server.httpx, "AsyncClient", tracked_client)
    monkeypatch.setattr(mcp_server, "Store", TrackedStore)
    monkeypatch.setattr(mcp_server.Registry, "load", load)
    args = argparse.Namespace(
        base_url="http://localhost:8000",
        spec_path="/openapi.json",
        tools=str(Path(__file__).parents[2] / "config" / "tools.json"),
        db=str(tmp_path / "context.db"),
    )

    if raise_inside:
        with pytest.raises(RuntimeError):
            async with mcp_server.registry_context(args):
                raise RuntimeError("test failure")
    else:
        async with mcp_server.registry_context(args) as registry:
            assert registry is not None

    assert clients[0].closed
    assert stores == [False, True]


async def test_registry_context_closes_resources_on_startup_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from healer import mcp_server
    from healer.store import Store

    clients: list[str] = []
    original_client = httpx.AsyncClient

    def tracked_client(**kwargs: Any) -> httpx.AsyncClient:
        client = original_client(**kwargs)
        original_aclose = client.aclose

        async def close() -> None:
            clients.append("closed")
            await original_aclose()

        client.aclose = close
        return client

    stores: list[bool] = []
    original_store = Store

    class TrackedStore(original_store):
        def __init__(self, db: str) -> None:
            super().__init__(db)
            stores.append(False)

        def close(self) -> None:
            stores[-1] = True
            super().close()

    monkeypatch.setattr(mcp_server.httpx, "AsyncClient", tracked_client)
    monkeypatch.setattr(mcp_server, "Store", TrackedStore)
    args = argparse.Namespace(
        base_url="http://localhost:8000",
        spec_path="/openapi.json",
        tools=str(Path(__file__).parents[2] / "config" / "tools.json"),
        db=str(tmp_path / "context.db"),
        no_rest=True,
    )

    with pytest.raises(ValueError):
        async with mcp_server.registry_context(args):
            pytest.fail("startup should fail without registries")

    assert clients == ["closed"]
    assert stores == [True]
