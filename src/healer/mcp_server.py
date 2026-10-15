"""MCP stdio transport for a frozen :class:`healer.registry.Registry`."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import MCPError
from mcp.server import stdio
from mcp.server.lowlevel import Server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from healer import canonical
from healer.openapi_loader import openapi_source
from healer.registry import Registry
from healer.settings import REQUEST_TIMEOUT_S
from healer.store import Store


def create_server(registry: Registry) -> Server:
    """Expose registry tools and calls without adding healing behavior."""

    async def list_tools(_context: Any, _params: Any) -> ListToolsResult:
        try:
            return ListToolsResult(
                tools=[
                    Tool(
                        name=tool["name"],
                        description=tool["description"],
                        inputSchema=tool["parameters"],
                    )
                    for tool in registry.tools()
                ]
            )
        except Exception:  # noqa: BLE001 - do not expose registry exceptions through MCP
            raise MCPError(code=-32603, message="MCP_LIST_ERROR") from None

    async def call_tool(_context: Any, params: Any) -> CallToolResult:
        try:
            result = await registry.call(params.name, params.arguments or {})
        except Exception:  # noqa: BLE001 - do not expose registry exceptions through MCP
            result = {"error": "MCP_TOOL_ERROR", "retry": False}
        is_error = isinstance(result, dict) and "error" in result
        return CallToolResult(
            content=[TextContent(text=canonical.dumps(result))],
            structuredContent=result,
            isError=is_error,
        )

    return Server(
        "healer",
        version="0.1.0",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a healer registry over MCP stdio"
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--spec-path", default="/openapi.json")
    parser.add_argument("--tools", default="config/tools.json")
    parser.add_argument("--db", default=":memory:")
    return parser.parse_args(argv)


async def _serve(args: argparse.Namespace) -> None:
    tools_config = json.loads(
        await asyncio.to_thread(Path(args.tools).read_text, encoding="utf-8")
    )

    client = httpx.AsyncClient(
        base_url=args.base_url,
        timeout=REQUEST_TIMEOUT_S,
    )
    try:
        store = Store(args.db)
        try:
            registry = Registry(
                client,
                tools_config,
                os.environ,
                store,
                spec_source=openapi_source(client, args.spec_path),
            )
            await registry.load()
            server = create_server(registry)
            async with stdio.stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
        finally:
            store.close()
    finally:
        await client.aclose()


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    load_dotenv()
    args = _arguments()
    try:
        asyncio.run(_serve(args))
    except Exception:  # noqa: BLE001 - suppress details that may contain secrets or URLs
        # Startup diagnostics must not disclose environment values or request URLs.
        print(
            "healer MCP server failed to start or stopped unexpectedly", file=sys.stderr
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
