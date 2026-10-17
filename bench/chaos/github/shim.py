"""Drift shim: a Streamable-HTTP MCP proxy between the healer and an upstream MCP server.

    healer  --MCP-->  shim (127.0.0.1:8099/mcp)  --MCP-->  upstream (fake_upstream or GitHub)

Modes, switched at runtime with  POST /control {"mode": "fake"|"real", "profile": "<name>"}
(GET /control shows the state):

  fake  tools/list returns the upstream tools with inputSchema rewritten by the active profile;
        tools/call translates the FALSE args back to REAL args and forwards, so the registry's
        initial load (and any probe) works against the false schema.
  real  pure passthrough of tools/list and tools/call. No translation.

Only the allowlisted tools (--tools) are exposed or forwarded. Every forwarded call is appended
to --log as JSONL: tool, args in, args forwarded, mode/profile and upstream status. The bearer
token (--token-env names the env var) is only ever put in the upstream Authorization header and
is never logged.

Live (needs a token; not run offline):
  --upstream-url https://api.githubcopilot.com/mcp/ --token-env MCP_GITHUB_TOKEN
"""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common
import profiles
from mcp import ClientSession, MCPError
from mcp.client.streamable_http import streamable_http_client
from mcp.server.lowlevel import Server
from mcp.types import CallToolResult, ListToolsResult, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

DEFAULT_TOOLS = "get_me,search_repositories,list_issues,get_issue,get_file_contents,list_commits"


class Shim:
    def __init__(self, upstream_url: str, token_env: str | None, allow: list[str], log: str,
                 mode: str = "fake", profile: str = "identity") -> None:
        self.upstream_url = upstream_url
        self.token_env = token_env
        self.allow = allow
        self.log = log
        self.mode = mode
        self.profile = profile
        self.session: ClientSession | None = None
        self.calls = 0

    # -- upstream ------------------------------------------------------------------------------
    @asynccontextmanager
    async def connect(self):
        async with AsyncExitStack() as stack:
            client = None
            if self.token_env:
                token = os.environ.get(self.token_env)
                if not token:
                    raise SystemExit(f"environment variable {self.token_env} is empty or unset")
                import httpx2

                client = await stack.enter_async_context(
                    httpx2.AsyncClient(
                        headers={"Authorization": f"Bearer {token}"}, follow_redirects=False
                    )
                )
            streams = await stack.enter_async_context(
                streamable_http_client(self.upstream_url, http_client=client)
            )
            read, write, *_ = streams
            self.session = await stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            await self._real_tools()  # primes profiles.REAL_SCHEMAS
            yield

    async def _real_tools(self) -> list[dict[str, Any]]:
        assert self.session is not None
        listed = await self.session.list_tools()
        tools = [
            t.model_dump(by_alias=True, exclude_none=True)
            for t in listed.tools
            if t.name in self.allow
        ]
        profiles.load_real_schemas(tools)
        return tools

    # -- server ----------------------------------------------------------------------------------
    def server(self) -> Server:
        async def list_tools(_ctx: Any, _params: Any) -> ListToolsResult:
            tools = await self._real_tools()
            if self.mode == "fake":
                prof = profiles.get(self.profile)
                tools = [
                    {**t, "inputSchema": prof.schema(t["name"], t.get("inputSchema") or {})}
                    for t in tools
                ]
            return ListToolsResult(tools=[Tool.model_validate(t) for t in tools])

        async def call_tool(_ctx: Any, params: Any) -> CallToolResult:
            assert self.session is not None
            name, args_in = params.name, dict(params.arguments or {})
            if name not in self.allow:
                self._log(name, args_in, args_in, "blocked", code=-32601)
                raise MCPError(code=-32601, message=f"tool not exposed by shim: {name}")
            args_out = args_in
            if self.mode == "fake":
                try:
                    args_out = profiles.get(self.profile).to_real(name, args_in)
                except Exception:  # noqa: BLE001 - forward untranslated; upstream will judge
                    args_out = args_in
            try:
                result = await self.session.call_tool(name, args_out)
            except MCPError as exc:
                self._log(name, args_in, args_out, "rpc_error", code=exc.code, message=exc.message)
                raise
            status = "tool_error" if result.is_error else "ok"
            self._log(name, args_in, args_out, status)
            return CallToolResult(
                content=result.content,
                structuredContent=result.structured_content,
                isError=result.is_error,
            )

        return Server("chaos-shim", version="0.1.0", on_list_tools=list_tools, on_call_tool=call_tool)

    def _log(self, tool: str, args_in: dict, args_out: dict, status: str, **extra: Any) -> None:
        self.calls += 1
        common.log_jsonl(
            self.log,
            {
                "seq": self.calls,
                "mode": self.mode,
                "profile": self.profile,
                "tool": tool,
                "args_in": args_in,
                "args_forwarded": args_out,
                "status": status,
                **extra,
            },
        )

    # -- app -----------------------------------------------------------------------------------------
    def app(self) -> Starlette:
        inner = common.local_http_app(self.server())

        async def control(request: Request) -> JSONResponse:
            if request.method == "POST":
                try:
                    body = await request.json()
                    mode = body.get("mode", self.mode)
                    profile = body.get("profile", self.profile)
                    if mode not in ("fake", "real") or profile not in profiles.PROFILES:
                        raise ValueError
                except Exception:  # noqa: BLE001
                    return JSONResponse(
                        {"error": "bad request", "profiles": sorted(profiles.PROFILES)}, status_code=400
                    )
                self.mode, self.profile = mode, profile
            return JSONResponse(
                {
                    "mode": self.mode,
                    "profile": self.profile,
                    "calls": self.calls,
                    "tools": self.allow,
                    "profiles": sorted(profiles.PROFILES),
                }
            )

        @asynccontextmanager
        async def lifespan(_: Starlette):
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(self.connect())
                await stack.enter_async_context(inner.router.lifespan_context(inner))
                yield

        return Starlette(
            routes=[Route("/control", control, methods=["GET", "POST"]), Mount("/", app=inner)],
            lifespan=lifespan,
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Drift shim MCP proxy")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--upstream-url", required=True)
    ap.add_argument("--token-env", help="NAME of the env var holding the upstream bearer token")
    ap.add_argument("--tools", default=DEFAULT_TOOLS, help="comma list of exposed tools")
    ap.add_argument("--log", default=str(common.OUT / "shim_calls.jsonl"))
    ap.add_argument("--mode", choices=("fake", "real"), default="fake")
    ap.add_argument("--profile", default="identity", choices=sorted(profiles.PROFILES))
    a = ap.parse_args()
    shim = Shim(
        a.upstream_url,
        a.token_env,
        [t.strip() for t in a.tools.split(",") if t.strip()],
        a.log,
        a.mode,
        a.profile,
    )
    import uvicorn

    uvicorn.run(shim.app(), host=a.host, port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
