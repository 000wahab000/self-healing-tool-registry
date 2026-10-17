"""MCP stdio transport for a frozen :class:`healer.registry.Registry`."""

from __future__ import annotations

import argparse
import asyncio
import hmac
import json
import logging
import os
import sys
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp import MCPError
from mcp.server import stdio
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from healer import canonical, jev, repair
from healer.gateway import Gateway, connect_upstreams
from healer.models import ErrorClass
from healer.openapi_loader import openapi_source
from healer.registry import Registry
from healer.settings import REQUEST_TIMEOUT_S
from healer.spec_watcher import SpecWatcher
from healer.store import Store


def _call_class(result: Any) -> ErrorClass:
    """OK without an "error" key; else the result's own class if valid, else BUSINESS."""
    if not (isinstance(result, dict) and "error" in result):
        return ErrorClass.OK
    try:
        return ErrorClass(result.get("class"))
    except ValueError:
        return ErrorClass.BUSINESS


def create_server(registry: Registry, *, store: Store | None = None) -> Server:
    """Expose registry tools and calls without adding healing behavior.

    With a store, each tools/call is logged as one call_events row (logging only).
    """
    run_id = uuid.uuid4().hex[:8]

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
        t0 = time.monotonic()
        try:
            result = await registry.call(params.name, params.arguments or {})
        except Exception:  # noqa: BLE001 - do not expose registry exceptions through MCP
            result = {"error": "MCP_TOOL_ERROR", "retry": False}
        if store is not None:
            with suppress(Exception):  # logging must never break a call
                store.log_call(
                    "mcp",
                    run_id,
                    params.name,
                    _call_class(result),
                    int((time.monotonic() - t0) * 1000),
                )
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


def create_http_app(
    registry: Registry,
    *,
    host: str = "127.0.0.1",
    bearer_token: str | None = None,
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    store: Store | None = None,
) -> Starlette:
    local = host in ("127.0.0.1", "localhost", "::1")
    if bearer_token is not None and not bearer_token:
        raise ValueError("bearer token must not be empty")
    if not local and (not bearer_token or not allowed_hosts):
        raise ValueError(
            "remote HTTP binding requires a bearer token and allowed hosts"
        )
    hosts = (
        allowed_hosts
        if allowed_hosts is not None
        else [
            "127.0.0.1",
            "127.0.0.1:*",
            "localhost",
            "localhost:*",
            "[::1]",
            "[::1]:*",
        ]
        if local
        else []
    )
    origins = (
        allowed_origins
        if allowed_origins is not None
        else ["http://127.0.0.1", "http://localhost", "http://[::1]"]
        if local
        else []
    )
    hosts = [
        host.removesuffix(":*") if host.endswith(":*") else host for host in hosts
    ] + hosts
    if any("*" in origin for origin in origins):
        raise ValueError("wildcard origins are not allowed")
    if any("*" in allowed_host.removesuffix(":*") for allowed_host in hosts):
        raise ValueError("allowed hosts may only wildcard the port")
    if any(allowed_host.startswith(("0.0.0.0", "[::]")) for allowed_host in hosts):
        raise ValueError(
            "allowed hosts must name request hosts, not wildcard bind addresses"
        )

    app = create_server(registry, store=store).streamable_http_app(
        json_response=True,
        host=host,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=origins,
        ),
    )
    if bearer_token is not None:
        expected = f"Bearer {bearer_token}".encode()

        async def require_bearer(request: Request, call_next: Any) -> Response:
            authorization = request.headers.get("authorization", "").encode("utf-8")
            if not hmac.compare_digest(authorization, expected):
                return Response(status_code=401)
            return await call_next(request)

        app.add_middleware(BaseHTTPMiddleware, dispatch=require_bearer)

    return app


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a healer registry over MCP stdio"
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--spec-path", default="/openapi.json")
    parser.add_argument("--tools", default="config/tools.json")
    parser.add_argument("--db", default=":memory:")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--token-env")
    parser.add_argument(
        "--mcp-servers",
        help="upstream MCP servers and APIs config (config/mcp_servers.json)",
    )
    parser.add_argument(
        "--no-rest", action="store_true", help="serve only the upstream MCP tools"
    )
    parser.add_argument(
        "--repair",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="tier-2 LLM repair agent, on by default; uses NVIDIA_API_KEY and LLM_MODEL "
        "(the same key and model as the agents). --no-repair turns it off.",
    )
    parser.add_argument("--allowed-host", action="append")
    parser.add_argument("--allowed-origin", action="append")
    return parser.parse_args(argv)


@asynccontextmanager
async def registry_context(args: argparse.Namespace) -> AsyncIterator[Registry | Gateway]:
    """Build registries and keep their backing resources alive until exit."""
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
            async with AsyncExitStack() as stack:
                registries = []
                # One repair agent and one Jev for every registry, from the same environment.
                agent = repair.from_env() if getattr(args, "repair", True) else None
                if getattr(args, "repair", True) and agent is None:
                    print(
                        "repair agent off: NVIDIA_API_KEY is not set (tier 1 still heals)",
                        file=sys.stderr,
                    )
                judge = jev.from_env()
                if not getattr(args, "no_rest", False):
                    rest_registry = Registry(
                        client,
                        tools_config,
                        # Only the header-source variables: the whole environment would let any env
                        # var become a header value and would garble audit redaction.
                        {
                            v: os.environ[v]
                            for v in tools_config.get("header_sources", {}).values()
                            if v in os.environ
                        },
                        store,
                        judge,
                        spec_source=openapi_source(client, args.spec_path),
                        repair=agent,
                    )
                    await rest_registry.load()
                    registries.append(rest_registry)
                if getattr(args, "mcp_servers", None):
                    upstreams = await stack.enter_async_context(
                        connect_upstreams(
                            args.mcp_servers,
                            store,
                            # Jev picks among tier-1 candidates and triages refusals for repair.
                            jev=judge,
                            repair=agent,
                        )
                    )
                    registries += upstreams
                    # Watch each upstream's tools/list: a change is snapshotted and its
                    # fixes precomputed before the first failing call (contract 5).
                    for reg in upstreams:
                        watcher = SpecWatcher(
                            {"spec": reg.spec_source}, store=store, healer=reg.healer
                        )
                        watcher.start()
                        stack.push_async_callback(watcher.stop)
                if not registries:
                    raise ValueError("nothing to serve: --no-rest needs --mcp-servers")
                registry = (
                    registries[0] if len(registries) == 1 else Gateway(registries)
                )
                # The same store backs the call log; callers read it to log MCP calls.
                registry.log_store = store
                yield registry
        finally:
            store.close()
    finally:
        await client.aclose()


async def _serve(args: argparse.Namespace) -> None:
    async with registry_context(args) as registry:
        if getattr(args, "transport", "stdio") == "http":
            import uvicorn

            token_name = getattr(args, "token_env", None)
            token = os.environ.get(token_name) if token_name else None
            if token_name and not token:
                raise ValueError(
                    "configured bearer-token environment variable is empty"
                )
            app = create_http_app(
                registry,
                host=args.host,
                bearer_token=token,
                allowed_hosts=getattr(args, "allowed_host", None),
                allowed_origins=getattr(args, "allowed_origin", None),
                store=getattr(registry, "log_store", None),
            )
            config = uvicorn.Config(
                app,
                host=args.host,
                port=args.port,
                access_log=False,
            )
            await uvicorn.Server(config).serve()
        else:
            server = create_server(registry)
            async with stdio.stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )


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
