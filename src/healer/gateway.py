"""Many registries behind one frozen tool list: the shape the MCP front door serves (contract 4).

`connect_upstreams` reads `config/mcp_servers.json`, opens one MCP client session per upstream
server and builds one healing Registry per server. Tool names are `<server>__<tool>`.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from healer.adapters import mcp_upstream
from healer.jev import JevClient
from healer.registry import Registry
from healer.repair import RepairAgent
from healer.store import FixStore


class Gateway:
    def __init__(self, registries: list[Registry]) -> None:
        self.registries = registries

    async def load(self) -> None:
        for registry in self.registries:
            await registry.load()

    def tools(self) -> list[dict]:
        return [tool for registry in self.registries for tool in registry.tools()]

    async def call(self, name: str, args: dict) -> dict:
        for registry in self.registries:
            if name in registry.defs:
                return await registry.call(name, args)
        return {"error": "UNKNOWN_TOOL", "tool": name, "retry": False}


def load_config(path: str | Path) -> list[dict]:
    servers = json.loads(Path(path).read_text(encoding="utf-8"))["servers"]
    names = [s["name"] for s in servers]
    if len(set(names)) != len(names) or any(mcp_upstream.SEP in n for n in names):
        raise ValueError("server names must be unique and must not contain '__'")
    return servers


def _token_headers(server: dict, env: Mapping[str, str]) -> dict[str, str]:
    var = server.get("token_env")
    if not var:
        return {}
    if not env.get(var):  # name the variable, never its value
        raise ValueError(
            f"server {server['name']!r}: environment variable {var} is not set"
        )
    return {"Authorization": f"Bearer {env[var]}"}


@asynccontextmanager
async def _open(server: dict, env: Mapping[str, str]) -> AsyncIterator[ClientSession]:
    async with AsyncExitStack() as stack:
        if server["transport"] == "stdio":
            command = [
                sys.executable if c == "python" else c for c in server["command"]
            ]
            streams = stdio_client(
                StdioServerParameters(command=command[0], args=command[1:])
            )
        elif server["transport"] == "http":
            client = await stack.enter_async_context(
                create_mcp_http_client(headers=_token_headers(server, env))
            )
            streams = streamable_http_client(server["url"], http_client=client)
        else:
            raise ValueError(
                f"server {server['name']!r}: transport must be 'stdio' or 'http'"
            )
        read, write, *_ = await stack.enter_async_context(streams)
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        yield session


async def upstream_registry(
    name: str,
    session: ClientSession,
    store: FixStore,
    cfg: Mapping[str, str],
    jev: JevClient | None = None,
    overrides: Mapping[str, dict] | None = None,
    repair: RepairAgent | None = None,
) -> Registry:
    """One healing registry over one upstream server, exposing every tool it lists."""
    source = mcp_upstream.mcp_source(session, name)
    spec = await source()
    tools = {f"{name}{mcp_upstream.SEP}{t['name']}": t for t in spec.raw["tools"]}
    config = {
        "header_sources": {},
        "tools": {
            key: {**mcp_upstream.tool_config(tool), **(overrides or {}).get(key, {})}
            for key, tool in tools.items()
        },
    }
    registry = Registry(
        None,
        config,
        cfg,
        store,
        jev,
        spec_source=source,
        mcp_session=session,
        repair=repair,
    )
    await registry.load()
    return registry


@asynccontextmanager
async def connect_upstreams(
    config_path: str | Path,
    store: FixStore,
    cfg: Mapping[str, str] | None = None,
    env: Mapping[str, str] = os.environ,
    jev: JevClient | None = None,
    repair: RepairAgent | None = None,
) -> AsyncIterator[list[Registry]]:
    """Open every configured upstream; sessions close when the context exits."""
    async with AsyncExitStack() as stack:
        registries = []
        for server in load_config(config_path):
            session = await stack.enter_async_context(_open(server, env))
            registries.append(
                await upstream_registry(
                    server["name"],
                    session,
                    store,
                    cfg or {},
                    jev,
                    server.get("tools"),
                    repair,
                )
            )
        yield registries
