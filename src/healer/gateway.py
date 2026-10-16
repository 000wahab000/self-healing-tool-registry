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
from mcp.client.streamable_http import streamable_http_client

from healer.adapters import mcp_upstream
from healer.connection_discovery import SELECT_ALL, discover
from healer.connection_security import (
    check_egress,
    has_credentials,
    no_redirect_client,
    no_redirect_httpx2,
    origin,
    resolve_headers,
    validate_entry_auth,
)
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
# Credential env names. Never the healer's own secrets (any caller); dashboard-submitted entries
# must also use an allowed name: HEALER_CONNECTION_ENV_ALLOW (comma list; an item ending in "_" is
# a prefix, otherwise an exact name) or, when unset, the default prefixes below.
FORBIDDEN_ENV = re.compile(
    r"NVIDIA|OPENROUTER|OPENCODE|OAUTH_BEARER|^(JEV_|DASHBOARD|CONNECTIONS_TOKEN|MCP_TOKEN_ENV)",
    re.IGNORECASE,
)
DEFAULT_ENV_PREFIXES = ("API_", "MCP_", "CONN_")
ENV_ALLOW_VAR = "HEALER_CONNECTION_ENV_ALLOW"
PROBE_TIMEOUT_S = 10.0
API_TIMEOUT_S = 15.0
_SERVER_KEYS = {
    "name",
    "transport",
    "url",
    "command",
    "token_env",
    "tools",
    "auth",
    "headers",
    "secret_headers",
    "selected_operations",
    "preset",
}
_API_KEYS = {
    "name",
    "kind",
    "base_url",
    "spec_path",
    "spec_url",
    "spec_auth",
    "spec_reuse_api_auth",
    "token_env",
    "auth",
    "headers",
    "secret_headers",
    "selected_operations",
    "preset",
}
_SECRET_PREFIXES = (
    "sk-",
    "sk_",
    "ghp_",
    "gho_",
    "xox",
    "eyj",
    "akia",
    "bearer ",
    "basic ",
)
_SECRET_QUERY = re.compile(r"token|secret|password|passwd|key|auth|sig", re.IGNORECASE)


def _http_url(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError:
        raise ValueError(f"{field} must be a valid http or https URL") from None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"{field} must be an http or https URL")
    if (
        parts.username
        or parts.password
        or parts.fragment
        or any(c in value for c in "\r\n")
    ):
        raise ValueError(f"{field} must not contain credentials")
    if any(_SECRET_QUERY.search(k) for k, _ in parse_qsl(parts.query)):
        raise ValueError(f"{field} must not carry secrets in the query string")
    return value


def credential_envs(entry: dict) -> set[str]:
    """Every env var NAME the entry would read a credential from."""
    names: set[str] = set()
    for block in (entry.get("auth"), entry.get("spec_auth")):
        if isinstance(block, dict):
            names.update(v for k, v in block.items() if k.endswith("_env"))
    if entry.get("token_env"):
        names.add(entry["token_env"])
    if isinstance(entry.get("secret_headers"), dict):
        names.update(entry["secret_headers"].values())
    return {n for n in names if isinstance(n, str)}


def _check_credential_envs(
    entry: dict, *, restrict: bool, allowed: set[str] = frozenset()
) -> None:
    rules = [
        x.strip()
        for x in os.environ.get(ENV_ALLOW_VAR, "").split(",")
        if x.strip()
    ] or list(DEFAULT_ENV_PREFIXES)
    for name in sorted(credential_envs(entry)):
        if FORBIDDEN_ENV.search(name):
            raise ValueError(
                "credential env names must not be one of the healer's own secrets"
            )
        if restrict and name not in allowed and not any(
            name == r or (r.endswith("_") and name.startswith(r)) for r in rules
        ):
            raise ValueError(
                "credential env names added here must start with one of: "
                + ", ".join(r for r in rules)
                + f" (set {ENV_ALLOW_VAR} to change the list)"
            )


def validate_entry(
    entry: object, *, http_only: bool = False, existing: dict | None = None
) -> dict:
    """Check one config entry (an MCP server, or an API when it has `kind`) and return it.

    `http_only` is the dashboard rule: no stdio, no command, http/https URLs only.
    """
    if not isinstance(entry, dict):
        raise ValueError("entry must be an object")  # noqa: TRY004 - callers catch ValueError
    is_api = "kind" in entry
    validate_entry_auth(entry)
    unknown = set(entry) - (_API_KEYS if is_api else _SERVER_KEYS)
    if unknown:
        raise ValueError(f"unknown field: {min(unknown)}")
    _check_credential_envs(
        entry,
        restrict=http_only,
        allowed=credential_envs(existing) if existing else set(),
    )
    name = entry.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ValueError("name must match ^[a-z][a-z0-9_-]{0,31}$")
    if mcp_upstream.SEP in name:
        raise ValueError("name must not contain '__'")
    var = entry.get("token_env")
    if (
        var is not None
        and var != ""
        and (
            not isinstance(var, str)
            or not ENV_NAME_RE.match(var)
            or var.lower().startswith(_SECRET_PREFIXES)
        )
    ):
        raise ValueError(
            "token_env must be an environment variable NAME, never the token itself"
        )
    if is_api:
        if entry["kind"] not in API_KINDS:
            raise ValueError("kind must be openapi, swagger2 or graphql")
        _http_url(entry.get("base_url"), "base_url")
        if entry.get("spec_path") and entry.get("spec_url"):
            raise ValueError("spec_url and spec_path are mutually exclusive")
        if entry.get("spec_reuse_api_auth") and entry.get("spec_auth"):
            raise ValueError("spec_auth and spec_reuse_api_auth are mutually exclusive")
        if "spec_reuse_api_auth" in entry and not isinstance(
            entry["spec_reuse_api_auth"], bool
        ):
            raise ValueError("spec_reuse_api_auth must be boolean")
        if entry.get("spec_url"):
            _http_url(entry["spec_url"], "spec_url")
            if entry.get("spec_reuse_api_auth") and origin(entry["spec_url"]) != origin(
                entry["base_url"]
            ):
                raise ValueError("spec credentials require same-origin reuse")
        path = entry.get("spec_path")
        if (
            path is not None
            and path != ""
            and (
                not isinstance(path, str)
                or not path.startswith("/")
                or path.startswith("//")
                or "://" in path
                or any(c in path for c in "\r\n#")
            )
        ):
            raise ValueError("spec_path must be a path starting with '/'")
        if path and any(
            _SECRET_QUERY.search(key) for key, _ in parse_qsl(urlsplit(path).query)
        ):
            raise ValueError("spec_path must not carry secrets in its query string")
        selected = entry.get("selected_operations")
        if selected is not None and selected != SELECT_ALL and (
            not isinstance(selected, list)
            or any(not isinstance(x, str) or not x for x in selected)
            or len(set(selected)) != len(selected)
        ):
            raise ValueError(
                'selected_operations must be unique non-empty strings, or "*" for every operation'
            )
        if entry.get("preset") not in (None, "github@1", "notion@1"):
            raise ValueError("unknown preset")
    else:
        transport = entry.get("transport")
        selected = entry.get("selected_operations")
        if selected is not None and (
            not isinstance(selected, list)
            or any(not isinstance(x, str) or not x for x in selected)
            or len(set(selected)) != len(selected)
        ):
            raise ValueError("selected_operations must be unique non-empty strings")
        if entry.get("preset") not in (None, "github@1", "notion@1"):
            raise ValueError("unknown preset")
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
    return resolve_headers(server, env)


def _connection_config(
    entry: dict, env: Mapping[str, str]
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    headers = resolve_headers(entry, env)
    sources: dict[str, str] = {}
    values: dict[str, str] = {}
    secret_keys: list[str] = []
    secret_envs = list(entry.get("secret_headers", {}).values())
    auth = entry.get("auth") or (
        {"token_env": entry["token_env"]} if entry.get("token_env") else {}
    )
    secret_envs.extend(value for field, value in auth.items() if field.endswith("_env"))
    secret_headers = {name.casefold() for name in entry.get("secret_headers", {})}
    if auth.get("type") in {"bearer", "basic"}:
        secret_headers.add("authorization")
    elif auth.get("type") == "api_key":
        secret_headers.add(auth["header"].casefold())
    for env_name in secret_envs:
        if env.get(env_name):
            key = f"connection-secret:{entry['name']}:{env_name}"
            values[key] = env[env_name]
            secret_keys.append(key)
    for header, value in headers.items():
        prefix = (
            "connection-secret" if header.casefold() in secret_headers else "connection"
        )
        key = f"{prefix}:{entry['name']}:{header.casefold()}"
        sources[header] = key
        values[key] = value
        if header.casefold() in secret_headers:
            secret_keys.append(key)
    return sources, values, secret_keys


@asynccontextmanager
async def _open(
    server: dict, env: Mapping[str, str], transport: object | None = None
) -> AsyncIterator[ClientSession]:
    """`transport` (an httpx2 transport) is for tests: it replaces the network."""
    validate_entry(server)
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
            check_egress(
                server["url"],
                credentials=has_credentials(server),
                mock_transport=transport is not None,
                env=env,
            )
            client = no_redirect_httpx2(
                server["url"],
                headers,
                transport,
                env=env,
                credentials=has_credentials(server),
            )
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
    selected_operations: list[str] | None = None,
    connection_entry: dict | None = None,
    env: Mapping[str, str] = os.environ,
) -> Registry:
    """One healing registry over one upstream server, exposing every tool it lists."""
    source = mcp_upstream.mcp_source(session, name)
    if selected_operations is not None:
        selected = set(selected_operations)
        original = source

        async def source() -> LoadedSpec:
            spec = await original()
            return LoadedSpec(
                spec.raw,
                {
                    k: v
                    for k, v in spec.ops.items()
                    if k.split(mcp_upstream.SEP, 1)[-1] in selected
                },
                spec.spec_hash,
            )

    spec = await source()
    tools = {
        f"{name}{mcp_upstream.SEP}{t['name']}": t
        for t in spec.raw["tools"]
        if selected_operations is None or t["name"] in selected_operations
    }
    config = {
        "header_sources": {},
        "secret_keys": _connection_config(connection_entry, env)[2]
        if connection_entry
        else [],
        "tools": {
            key: {**mcp_upstream.tool_config(tool), **(overrides or {}).get(key, {})}
            for key, tool in tools.items()
        },
    }
    registry = Registry(
        None,
        config,
        _connection_config(connection_entry, env)[1] if connection_entry else cfg,
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
    check_egress(
        api["base_url"],
        credentials=has_credentials(api),
        mock_transport=transport is not None,
        env=env,
    )
    return no_redirect_client(
        base_url=api["base_url"],
        headers=_token_headers(api, env),
        timeout=API_TIMEOUT_S,
        transport=transport,
        egress_env=env,
        egress_credentials=has_credentials(api),
    )


def _api_source(api: dict, client: httpx.AsyncClient) -> SpecSource:
    default, factory = API_KINDS[api["kind"]]
    return namespaced(factory(client, api.get("spec_path") or default), api["name"])


def _discovered_source(
    api: dict,
    source: SpecSource,
    env: Mapping[str, str],
    diagnostics: list[dict] | None = None,
) -> SpecSource:
    headers = set(resolve_headers(api, env))

    async def load() -> LoadedSpec:
        selected, found = discover(await source(), api, headers)
        if diagnostics is not None:
            diagnostics[:] = found
        return selected

    return load


def _graphql_selected(
    api: dict, source: SpecSource, diagnostics: list[dict] | None = None
) -> SpecSource:
    """FR-25.3 for GraphQL: explicit names, or "*", else queries only (no mutations)."""
    prefix = f"{api['name']}{mcp_upstream.SEP}"
    selected = api.get("selected_operations")

    async def load() -> LoadedSpec:
        spec = await source()
        found: list[dict] = []
        if isinstance(selected, list):
            keep = set(selected)
            found = [
                {"operation": n, "code": "UNKNOWN_OPERATION"}
                for n in sorted(keep)
                if prefix + n not in spec.ops
            ]
        elif selected == SELECT_ALL:
            keep = {k.removeprefix(prefix) for k in spec.ops}
        else:
            schema = spec.raw.get("data", {}).get("__schema", {})
            root = (schema.get("queryType") or {}).get("name")
            keep = {
                f["name"]
                for t in schema.get("types", [])
                if t.get("name") == root
                for f in t.get("fields") or []
            }
        if diagnostics is not None:
            diagnostics[:] = found
        ops = {k: v for k, v in spec.ops.items() if k.removeprefix(prefix) in keep}
        return LoadedSpec(spec.raw, ops, spec.spec_hash)

    return load


async def _spec_source(
    api: dict,
    env: Mapping[str, str],
    transport: httpx.AsyncBaseTransport | None,
    stack: AsyncExitStack,
    api_client: httpx.AsyncClient,
    diagnostics: list[dict] | None = None,
) -> SpecSource:
    reuse = api.get("spec_reuse_api_auth", False)
    if api.get("spec_auth"):
        spec_headers = resolve_headers({"auth": api["spec_auth"]}, env)
    elif reuse or not api.get("spec_url"):
        spec_headers = _token_headers(api, env)
    else:
        spec_headers = {}
    target = api.get("spec_url") or api["base_url"]
    if reuse and origin(target) != origin(api["base_url"]):
        raise ValueError("spec credentials require same-origin reuse")
    check_egress(
        target,
        credentials=bool(spec_headers)
        and (
            has_credentials(api)
            if not api.get("spec_url") or reuse
            else bool(api.get("spec_auth"))
        ),
        mock_transport=transport is not None,
        env=env,
    )
    spec_client = await stack.enter_async_context(
        no_redirect_client(
            base_url=target,
            headers=spec_headers,
            timeout=API_TIMEOUT_S,
            transport=transport,
            egress_env=env,
            egress_credentials=bool(spec_headers)
            and (
                has_credentials(api)
                if not api.get("spec_url") or reuse
                else bool(api.get("spec_auth"))
            ),
        )
    )
    location = api.get("spec_url") or api.get("spec_path") or API_KINDS[api["kind"]][0]
    factory = API_KINDS[api["kind"]][1]
    source = namespaced(factory(spec_client, location), api["name"])
    if api["kind"] == "graphql":
        return _graphql_selected(api, source, diagnostics)
    return _discovered_source(api, source, env, diagnostics)


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
    validate_entry(api)
    async with AsyncExitStack() as stack:
        client = await stack.enter_async_context(_api_client(api, env, transport))
        source = await _spec_source(api, env, transport, stack, client)
        spec = await source()
        registry = Registry(
            client,
            {
                "header_sources": _connection_config(api, env)[0],
                "secret_keys": _connection_config(api, env)[2],
                "tools": {k: api_tool_config(op) for k, op in spec.ops.items()},
            },
            _connection_config(api, env)[1],
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

    diagnostics: list[dict] = []

    async def run() -> list[str]:
        if "kind" in entry:
            validate_entry(entry)
            async with AsyncExitStack() as stack:
                api_client = await stack.enter_async_context(
                    _api_client(entry, env, transport)
                )
                source = await _spec_source(
                    entry, env, transport, stack, api_client, diagnostics
                )
                spec = await source()
                return sorted(spec.ops)
        async with _open(entry, env, transport) as session:
            listed = await session.list_tools()
            selected = entry.get("selected_operations")
            offered = {t.name for t in listed.tools}
            if selected is not None:
                diagnostics.extend(
                    {"operation": name, "code": "UNKNOWN_OPERATION"}
                    for name in selected
                    if name not in offered
                )
            return sorted(
                f"{entry['name']}{mcp_upstream.SEP}{t.name}"
                for t in listed.tools
                if selected is None or t.name in selected
            )

    try:
        validate_entry(entry)
        async with asyncio.timeout(PROBE_TIMEOUT_S):
            tools = await run()
        result = {"ok": True, "tools": tools, "error": None}
        result.update(
            step="discovery",
            status="ok",
            count=len(tools),
            credentials_verified=False if "kind" in entry else None,
            diagnostics=diagnostics,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - report a short message only
        result = {"ok": False, "tools": [], "error": _short_error(exc)}
        result.update(
            step="discovery",
            status="error",
            count=0,
            credentials_verified=False if "kind" in entry else None,
            diagnostics=diagnostics,
        )
        return result


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
                    server.get("selected_operations"),
                    server,
                    env,
                )
            )
        for api in load_apis(config_path):
            registries.append(
                await stack.enter_async_context(
                    api_registry(api, store, cfg or {}, env, jev, repair)
                )
            )
        yield registries
