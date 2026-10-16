from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import pytest

pytest.importorskip("mcp")
httpx2 = pytest.importorskip("httpx2")

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).parents[2]


def _load_target(path: str | Path, client_name: str) -> tuple[str, dict]:
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
        servers = config["mcpServers"]
        entry = servers[client_name]
        if not isinstance(servers, dict) or not isinstance(entry, dict):
            raise TypeError

        endpoints = [key for key in ("url", "serverUrl") if key in entry]
        if "command" in entry and not endpoints:
            command, args, env = entry["command"], entry.get("args", []), entry.get("env", {})
            if (
                isinstance(command, str)
                and command
                and isinstance(args, list)
                and all(isinstance(arg, str) for arg in args)
                and isinstance(env, dict)
                and all(isinstance(key, str) and isinstance(value, str) for key, value in env.items())
            ):
                return "stdio", {"command": command, "args": args, "env": env}
        if "command" not in entry and len(endpoints) == 1:
            url = entry[endpoints[0]]
            headers = entry.get("headers", {})
            parsed = urlsplit(url) if isinstance(url, str) else None
            if (
                parsed is not None
                and parsed.scheme in ("http", "https")
                and parsed.netloc
                and isinstance(headers, dict)
                and all(
                    isinstance(key, str) and isinstance(value, str)
                    for key, value in headers.items()
                )
            ):
                return "http", {"url": url, "headers": headers}
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    raise ValueError("invalid MCP client configuration") from None


@asynccontextmanager
async def _connect(target: tuple[str, dict]):
    transport, config = target
    if transport == "stdio":
        params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config["env"],
        )
        with open(os.devnull, "w", encoding="utf-8") as errlog:  # noqa: ASYNC230 - OS null device, not disk I/O
            async with (
                stdio_client(params, errlog=errlog) as streams,
                ClientSession(*streams) as session,
            ):
                await session.initialize()
                yield session
    else:
        async with (
            httpx2.AsyncClient(headers=config["headers"]) as client,
            streamable_http_client(config["url"], http_client=client) as streams,
            ClientSession(*streams) as session,
        ):
            await session.initialize()
            yield session


async def _smoke(target: tuple[str, dict]) -> None:
    async with asyncio.timeout(30):
        async with _connect(target) as session:
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            assert "get_user" in names, "configured MCP server lacks get_user"
            result = await session.call_tool("get_user", {"user_id": "123"})
            response = result.model_dump(by_alias=True)
            assert response["isError"] is False, "configured MCP call failed"
            assert response["structuredContent"]["id"] == "123", "unexpected tool data"


async def _safe_smoke(target: tuple[str, dict]) -> None:
    # shortcut: log suppression is process-wide; isolate concurrent smoke runs in subprocesses.
    previous_disable = logging.root.manager.disable
    logging.disable(sys.maxsize)
    try:
        await _smoke(target)
    except Exception:  # noqa: BLE001 - external command/HTTP errors can contain secrets
        raise pytest.fail.Exception(
            "MCP client smoke failed or timed out; external details suppressed",
            pytrace=False,
        ) from None
    finally:
        logging.disable(previous_disable)


def test_ac_37_invalid_transport_configs_fail_without_echoing_secrets(tmp_path):
    secret = "SYNTHETIC_CONFIG_SECRET"
    invalid = [
        {},
        {"command": "", "args": []},
        {"command": "/bin/echo", "args": "not-an-array", "env": {"KEY": secret}},
        {"command": "/bin/echo", "url": "https://example.invalid", "headers": {"X-Key": secret}},
        {"url": "relative/path", "headers": {"X-Key": secret}},
        {
            "url": "https://example.invalid/mcp",
            "serverUrl": "https://example.invalid/mcp",
        },
    ]
    path = tmp_path / "client.json"
    for entry in invalid:
        path.write_text(json.dumps({"mcpServers": {"healer": entry}}))
        with pytest.raises(ValueError) as error:
            _load_target(path, "healer")
        assert str(error.value) == "invalid MCP client configuration"
        assert secret not in str(error.value)


async def test_ac_37_offline_trusted_stdio_config_uses_shared_sdk_launcher(tmp_path):
    config_path = tmp_path / "trusted-client.json"
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "healer": {
                        "command": sys.executable,
                        "args": [str(ROOT / "tests" / "mcp" / "stdio_harness.py")],
                        "env": {
                            "PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT)
                        },
                    }
                }
            }
        )
    )

    await _safe_smoke(_load_target(config_path, "healer"))


@pytest.mark.skipif(
    os.environ.get("RUN_MCP_CLIENT_E2E") != "1"
    or not os.environ.get("MCP_CLIENT_CONFIG"),
    reason="set RUN_MCP_CLIENT_E2E=1 and MCP_CLIENT_CONFIG to opt into a trusted live MCP client",
)
async def test_ac_37_live_client_config():
    config_path = os.environ["MCP_CLIENT_CONFIG"]
    client_name = os.environ.get("MCP_CLIENT_NAME", "healer")
    try:
        target = _load_target(config_path, client_name)
    except Exception:  # noqa: BLE001 - config read errors must not expose path/contents
        raise pytest.fail.Exception(
            "invalid selected MCP client configuration; details suppressed",
            pytrace=False,
        ) from None
    await _safe_smoke(target)
