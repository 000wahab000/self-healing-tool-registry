"""Upstream MCP servers as a protocol (contract 7): tools/list -> OperationSpec, tools/call -> Outcome.

An upstream tool becomes an operation with method "MCP", path = its upstream name and
body_schema = its inputSchema, so diagnosis reads it like any other spec. A renamed tool is
then a route change, and a renamed or retyped argument is a body change.
"""

from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession, MCPError

from healer import canonical
from healer.models import (
    ErrorClass,
    LoadedSpec,
    OperationSpec,
    Outcome,
    Side,
    SpecSource,
    Violation,
)

PROTOCOL = "mcp"
METHOD = "MCP"
SEP = "__"  # gateway tool name: <server>__<tool>
UNKNOWN_TOOL = -32601


def to_operation(server: str, tool: dict) -> OperationSpec:
    return {
        "operation_id": tool["name"],
        "method": METHOD,
        "path": tool["name"],
        "body_schema": tool.get("inputSchema") or {"type": "object", "properties": {}},
        "params": [],
        "security": [],
        "response_schema": tool.get("outputSchema"),
        "description": tool.get("description") or "",
    }


def mcp_source(session: ClientSession, server: str) -> SpecSource:
    """Read the upstream's tools/list. Names starting with `__` are reserved (admin tools, our separator)."""

    async def source() -> LoadedSpec:
        try:
            listed = await session.list_tools()
        except MCPError as exc:
            raise ValueError(f"tools/list failed on {server}") from exc
        # ponytail: first page only; paginated tools/list is not followed.
        tools = [
            t.model_dump(by_alias=True, exclude_none=True)
            for t in listed.tools
            if not t.name.startswith(SEP)
        ]
        raw = {"server": server, "tools": tools}
        ops = {f"{server}{SEP}{t['name']}": to_operation(server, t) for t in tools}
        return LoadedSpec(raw=raw, ops=ops, spec_hash=canonical.sha256(raw))

    return source


def tool_config(tool: dict) -> dict:
    """Default registry config: a tool is a write unless the upstream says it is read-only."""
    hints = tool.get("annotations") or {}
    read_only = bool(hints.get("readOnlyHint"))
    return {
        "write": not read_only,
        "idempotent": read_only or bool(hints.get("idempotentHint")),
        "postchecks": [],
    }


def _payload(result: Any) -> Any:
    if result.structured_content is not None:
        return result.structured_content
    text = "".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    try:
        return json.loads(text)
    except ValueError:
        return {"text": text}


async def send(session: ClientSession, doc: dict, timeout: float) -> Outcome:
    name = doc["route"]["path"]
    try:
        result = await session.call_tool(
            name, doc.get("body") or {}, read_timeout_seconds=timeout
        )
    except MCPError as exc:
        if exc.code == UNKNOWN_TOOL:
            return Outcome(
                ErrorClass.E2,
                PROTOCOL,
                str(exc.code),
                exc.message,
                [Violation(Side.REQ, ["route"], "route")],
            )
        if (
            exc.code == -32602
        ):  # invalid params: drift or a bad value; the spec diff decides
            return Outcome(
                ErrorClass.E2,
                PROTOCOL,
                str(exc.code),
                exc.message,
                [Violation(Side.REQ, [], "rejected")],
            )
        return Outcome(ErrorClass.E1, PROTOCOL, str(exc.code))
    except (TimeoutError, OSError) as exc:
        return Outcome(ErrorClass.E1, PROTOCOL, type(exc).__name__)
    data = _payload(result)
    if result.is_error:
        return Outcome(
            ErrorClass.E2,
            PROTOCOL,
            "isError",
            data,
            [Violation(Side.REQ, [], "rejected")],
        )
    return Outcome(ErrorClass.OK, PROTOCOL, "ok", data)
