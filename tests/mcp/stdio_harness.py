from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
from mcp.server import stdio

from healer.mcp_server import create_server
from healer.registry import Registry
from healer.store import Store
from mock_api.app import create_app


async def main() -> None:
    root = Path(__file__).parents[2]
    api = create_app()
    config = json.loads((root / "config" / "tools.json").read_text())
    store = Store(":memory:")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://mock"
    ) as client:
        try:
            registry = Registry(
                client,
                config,
                {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"},
                store=store,
            )
            await registry.load()
            api.set_mutation("M1")
            server = create_server(registry)
            async with stdio.stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
        finally:
            store.close()


if __name__ == "__main__":
    asyncio.run(main())
