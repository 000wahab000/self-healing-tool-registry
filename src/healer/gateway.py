"""Many registries behind one frozen tool list: the shape the MCP front door serves (contract 4).

`connect_upstreams` reads `config/mcp_servers.json`, opens one MCP client session per upstream
server and builds one healing Registry per server. Tool names are `<server>__<tool>`.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections.abc import AsyncIterator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import httpx
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from healer.adapters import mcp_upstream
from healer.graphql_loader import graphql_source
from healer.jev import JevClient
from healer.models import LoadedSpec, SpecSource
from healer.openapi_loader import openapi_source
from healer.registry import Registry
from healer.repair import RepairAgent
from healer.store import FixStore
from healer.swagger2 import swagger2_source


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


NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
API_KINDS = {
    "openapi": ("/openapi.json", openapi_source),
    "swagger2": ("/swagger.json", swagger2_source),
    "graphql": ("/graphql", graphql_source),
}
PROBE_TIMEOUT_S = 10.0
API_TIMEOUT_S = 15.0
_SERVER_KEYS = {"name", "transport", "url", "command", "token_env", "tools"}
_API_KEYS = {"name", "kind", "base_url", "spec_path", "token_env"}
_SECRET_PREFIXES = ("sk-", "sk_", "ghp_", "gho_", "xox", "eyj", "akia", "bearer ", "basic ")
_SECRET_QUERY = re.compile(r"token|secret|password|passwd|key|auth|sig", re.IGNORECASE)


def _http_url(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"{field} must be an http or https URL")
    if parts.username or parts.password:
        raise ValueError(f"{field} must not contain credentials")
    if any(_SECRET_QUERY.search(k) for k, _ in parse_qsl(parts.query)):
        raise ValueError(f"{field} must not carry secrets in the query string")
    return value


def validate_entry(entry: object, *, http_only: bool = False) -> dict:
    """Check one config entry (an MCP server, or an API when it has `kind`) and return it.

    `http_only` is the dashboard rule: no stdio, no command, http/https URLs only.
    """
    if not isinstance(entry, dict):
        raise ValueError("entry must be an object")  # noqa: TRY004 - callers catch ValueError
    is_api = "kind" in entry
    unknown = set(entry) - (_API_KEYS if is_api else _SERVER_KEYS)
    if unknown:
        raise ValueError(f"unknown field: {min(unknown)}")
    name = entry.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ValueError("name must match ^[a-z][a-z0-9_-]{0,31}$")
    if mcp_upstream.SEP in name:
        raise ValueError("name must not contain '__'")
    var = entry.get("token_env")
    if var is not None and var != "" and (
        not isinstance(var, str)
        or not ENV_NAME_RE.match(var)
        or var.lower().startswith(_SECRET_PREFIXES)
    ):
        raise ValueError(
            "token_env must be an environment variable NAME, never the token itself"
        )
    if is_api:
        if entry["kind"] not in API_KINDS:
            raise ValueError("kind must be openapi, swagger2 or graphql")
        _http_url(entry.get("base_url"), "base_url")
        path = entry.get("spec_path")
        if path is not None and path != "" and (
            not isinstance(path, str) or not path.startswith("/") or "://" in path
        ):
            raise ValueError("spec_path must be a path starting with '/'")
    else:
        transport = entry.get("transport")
        if http_only and (transport != "http" or "command" in entry):
            raise ValueError("only http MCP servers can be added here")
        if transport == "http":
            _http_url(entry.get("url"), "url")
        elif transport == "stdio":
            command = entry.get("command")
            if not isinstance(command, list) or not command:
                raise ValueError("stdio server needs a command list")
        else:
            raise ValueError("transport must be 'stdio' or 'http'")
    return entry


def _read(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _check_names(entries: list[dict]) -> None:
    names = [e["name"] for e in entries]
    if len(set(names)) != len(names):
        raise ValueError("names must be unique across servers and apis")


def load_config(path: str | Path) -> list[dict]:
    data = _read(path)
    servers = data.get("servers", [])
    for s in servers:
        if "kind" in s:
            raise ValueError("servers entries cannot have 'kind'")
        validate_entry(s)
    _check_names(servers + data.get("apis", []))
    return servers


def load_apis(path: str | Path) -> list[dict]:
    data = _read(path)
    apis = data.get("apis", [])
    for a in apis:
        if "kind" not in a:
            raise ValueError("apis entries need a 'kind'")
        validate_entry(a)
    _check_names(data.get("servers", []) + apis)
    return apis


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
async def _open(
    server: dict, env: Mapping[str, str], transport: object | None = None
) -> AsyncIterator[ClientSession]:
    """`transport` (an httpx2 transport) is for tests: it replaces the network."""
    async with AsyncExitStack() as stack:
        if server["transport"] == "stdio":
            command = [
                sys.executable if c == "python" else c for c in server["command"]
            ]
            streams = stdio_client(
                StdioServerParameters(command=command[0], args=command[1:])
            )
        elif server["transport"] == "http":
            headers = _token_headers(server, env)
            if transport is None:
                client = create_mcp_http_client(headers=headers)
            else:
                import httpx2

                client = httpx2.AsyncClient(headers=headers, transport=transport)
            client = await stack.enter_async_context(client)
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


def namespaced(source: SpecSource, name: str) -> SpecSource:
    """Wrap a spec source so operation keys become `<name>__<operation_id>`."""

    async def load() -> LoadedSpec:
        spec = await source()
        ops = {f"{name}{mcp_upstream.SEP}{k}": v for k, v in spec.ops.items()}
        return LoadedSpec(spec.raw, ops, spec.spec_hash)

    return load


def api_tool_config(op: dict) -> dict:
    method = str(op["method"]).upper()
    return {
        "write": method not in ("GET", "HEAD"),
        "idempotent": method in ("GET", "HEAD", "PUT", "DELETE"),
        "postchecks": [],
    }


def _api_client(
    api: dict, env: Mapping[str, str], transport: httpx.AsyncBaseTransport | None
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=api["base_url"],
        headers=_token_headers(api, env),
        timeout=API_TIMEOUT_S,
        transport=transport,
    )


def _api_source(api: dict, client: httpx.AsyncClient) -> SpecSource:
    default, factory = API_KINDS[api["kind"]]
    return namespaced(factory(client, api.get("spec_path") or default), api["name"])


@asynccontextmanager
async def api_registry(
    api: dict,
    store: FixStore,
    cfg: Mapping[str, str],
    env: Mapping[str, str] = os.environ,
    jev: JevClient | None = None,
    repair: RepairAgent | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[Registry]:
    """One healing registry over one third-party API; the HTTP client closes on exit."""
    async with AsyncExitStack() as stack:
        client = await stack.enter_async_context(_api_client(api, env, transport))
        source = _api_source(api, client)
        spec = await source()
        registry = Registry(
            client,
            {
                "header_sources": {},
                "tools": {k: api_tool_config(op) for k, op in spec.ops.items()},
            },
            cfg,
            store,
            jev,
            spec_source=source,
            repair=repair,
        )
        await registry.load()
        yield registry


def _short_error(exc: BaseException) -> str:
    """One line, no URLs, headers or traces."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    if isinstance(exc, TimeoutError):
        return f"timed out after {PROBE_TIMEOUT_S:g} s"
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if isinstance(status, int):
        return f"HTTP {status}"
    if isinstance(exc, ValueError) and "environment variable" in str(exc):
        return str(exc).split(": ", 1)[-1]
    if isinstance(exc, ValueError) and "GraphQL introspection" in str(exc):
        return "GraphQL introspection unavailable"
    if isinstance(exc, ValueError):
        return "spec could not be read"
    return f"connection failed ({type(exc).__name__})"


async def probe(
    entry: dict, env: Mapping[str, str] = os.environ, transport: object | None = None
) -> dict:
    """Connect once to an MCP server or API and list what it offers. Never raises."""

    async def run() -> list[str]:
        if "kind" in entry:
            async with _api_client(entry, env, transport) as client:  # type: ignore[arg-type]
                spec = await _api_source(entry, client)()
                return sorted(spec.ops)
        async with _open(entry, env, transport) as session:
            listed = await session.list_tools()
            return sorted(
                f"{entry['name']}{mcp_upstream.SEP}{t.name}" for t in listed.tools
            )

    try:
        async with asyncio.timeout(PROBE_TIMEOUT_S):
            tools = await run()
        return {"ok": True, "tools": tools, "error": None}
    except Exception as exc:  # noqa: BLE001 - report a short message only
        return {"ok": False, "tools": [], "error": _short_error(exc)}


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
        for api in load_apis(config_path):
            registries.append(
                await stack.enter_async_context(
                    api_registry(api, store, cfg or {}, env, jev, repair)
                )
            )
        yield registries
