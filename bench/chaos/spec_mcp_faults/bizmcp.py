"""Tiny Streamable-HTTP MCP upstream with business errors. No LLM.

  lookup(item_id)  -> 'missing' returns CallToolResult(isError=True, 'Item not found: missing'); else ok
  boom(item_id)    -> raises JSON-RPC -32603 internal error
Every call is appended to --log.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

import uvicorn
from mcp import MCPError
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--log", required=True)
A = ap.parse_args()
SCHEMA = {"type": "object", "properties": {"item_id": {"type": "string"}}, "required": ["item_id"]}


def log(row: dict) -> None:
    with open(A.log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts_ms": int(time.time() * 1000), **row}) + "\n")


async def list_tools(_c: Any, _p: Any) -> ListToolsResult:
    return ListToolsResult(tools=[Tool(name="lookup", description="Look up an item", inputSchema=SCHEMA),
                                  Tool(name="boom", description="Always fails", inputSchema=SCHEMA)])


async def call_tool(_c: Any, params: Any) -> CallToolResult:
    args = dict(params.arguments or {})
    log({"tool": params.name, "args": args})
    if params.name == "boom":
        raise MCPError(code=-32603, message="internal error: kaboom")
    if args.get("item_id") == "missing":
        return CallToolResult(content=[TextContent(type="text", text="Item not found: missing")],
                              structuredContent={"error": "not_found", "item_id": "missing"}, isError=True)
    res = {"item_id": args.get("item_id"), "ok": True}
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(res))], structuredContent=res, isError=False)


srv = Server("bizmcp", version="0.0.1", on_list_tools=list_tools, on_call_tool=call_tool)
app = srv.streamable_http_app(json_response=True, host="127.0.0.1", transport_security=TransportSecuritySettings(
    enable_dns_rebinding_protection=True, allowed_hosts=["127.0.0.1", "127.0.0.1:*", "localhost", "localhost:*"],
    allowed_origins=["http://127.0.0.1", "http://localhost"]))
uvicorn.run(app, host="127.0.0.1", port=A.port, log_level="warning")
