"""Offline stand-in for the GitHub MCP server (127.0.0.1:8100). APPROXIMATION.

Tool names and inputSchema shapes approximate github/github-mcp-server's read tools as I know
them (owner/repo strings, `issue_number` integer, `perPage`/`page` integers, `state` enum
OPEN|CLOSED on list_issues). They are NOT copied from a live server and may differ from the real
ones (enum casing, extra optional fields). The live run uses the real server; this file exists only
to prove the harness offline.

Arguments are validated strictly: unknown or missing properties and wrong types raise JSON-RPC
-32602 with a clear message, as GitHub MCP does. Results are canned and echo the received args.
Every call is appended to --log (the independent oracle: what the upstream actually received).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common
from jsonschema import Draft202012Validator
from mcp import MCPError
from mcp.server.lowlevel import Server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
    ToolAnnotations,
)

_OWNER = {"type": "string", "description": "Repository owner (user or organization)"}
_REPO = {"type": "string", "description": "Repository name"}
_PAGING = {
    "page": {"type": "integer", "minimum": 1, "description": "Page number for pagination"},
    "perPage": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Results per page"},
}


def _schema(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


TOOLS: dict[str, dict[str, Any]] = {
    "get_me": {
        "description": "Get details of the authenticated GitHub user.",
        "inputSchema": _schema({}, []),
    },
    "search_repositories": {
        "description": "Search for GitHub repositories.",
        "inputSchema": _schema(
            {"query": {"type": "string", "description": "Search query"}, **_PAGING}, ["query"]
        ),
    },
    "list_issues": {
        "description": "List issues in a GitHub repository.",
        "inputSchema": _schema(
            {
                "owner": _OWNER,
                "repo": _REPO,
                "state": {"type": "string", "enum": ["OPEN", "CLOSED"], "description": "Filter by state"},
                "labels": {"type": "array", "items": {"type": "string"}, "description": "Filter by labels"},
                "orderBy": {"type": "string", "enum": ["CREATED_AT", "UPDATED_AT", "COMMENTS"]},
                "direction": {"type": "string", "enum": ["ASC", "DESC"]},
                "since": {"type": "string", "description": "ISO 8601 timestamp"},
                "after": {"type": "string", "description": "Cursor for pagination"},
                "perPage": _PAGING["perPage"],
            },
            ["owner", "repo"],
        ),
    },
    "get_issue": {
        "description": "Get details of a specific issue in a GitHub repository.",
        "inputSchema": _schema(
            {
                "owner": _OWNER,
                "repo": _REPO,
                "issue_number": {"type": "integer", "description": "The issue number"},
            },
            ["owner", "repo", "issue_number"],
        ),
    },
    "get_file_contents": {
        "description": "Get the contents of a file or directory from a GitHub repository.",
        "inputSchema": _schema(
            {
                "owner": _OWNER,
                "repo": _REPO,
                "path": {"type": "string", "description": "Path to file/directory", "default": "/"},
                "ref": {"type": "string", "description": "Git ref (branch, tag or ref)"},
                "sha": {"type": "string", "description": "Commit SHA"},
            },
            ["owner", "repo"],
        ),
    },
    "list_commits": {
        "description": "Get a list of commits of a branch in a GitHub repository.",
        "inputSchema": _schema(
            {
                "owner": _OWNER,
                "repo": _REPO,
                "sha": {"type": "string", "description": "Branch, tag or SHA"},
                **_PAGING,
            },
            ["owner", "repo"],
        ),
    },
}

CANNED: dict[str, Any] = {
    "get_me": {"login": "octocat", "id": 1, "type": "User"},
    "search_repositories": {"total_count": 1, "items": [{"full_name": "octocat/hello-world"}]},
    "list_issues": {"issues": [{"number": 1, "title": "First issue", "state": "OPEN"}], "totalCount": 1},
    "get_issue": {"number": 1, "title": "First issue", "state": "open", "body": "canned"},
    "get_file_contents": {"type": "file", "path": "README.md", "content": "# hello-world"},
    "list_commits": [{"sha": "abc123", "message": "init"}],
}

_TYPE_NAMES = {bool: "boolean", int: "integer", float: "number", str: "string", list: "array", dict: "object"}


def validate(name: str, args: dict[str, Any]) -> str | None:
    """None if valid, else a GitHub-MCP-style message."""
    schema = TOOLS[name]["inputSchema"]
    problems: list[str] = []
    missing = [r for r in schema["required"] if r not in args]
    if missing:
        problems.append("missing required parameter(s): " + ", ".join(missing))
    extra = [k for k in args if k not in schema["properties"]]
    if extra:
        problems.append("unexpected additional properties: " + ", ".join(sorted(extra)))
    for err in Draft202012Validator(schema).iter_errors(args):
        if err.validator in ("required", "additionalProperties"):
            continue
        where = ".".join(str(p) for p in err.absolute_path) or "arguments"
        if err.validator == "type":
            got = _TYPE_NAMES.get(type(err.instance), type(err.instance).__name__)
            problems.append(f"parameter {where} must be of type {err.validator_value}, got {got}")
        else:
            problems.append(f"parameter {where}: {err.message}")
    return "; ".join(problems) or None


def create_server(log_path: str | None) -> Server:
    async def list_tools(_ctx: Any, _params: Any) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name=n,
                    description=t["description"],
                    inputSchema=copy.deepcopy(t["inputSchema"]),
                    annotations=ToolAnnotations(readOnlyHint=True),
                )
                for n, t in TOOLS.items()
            ]
        )

    async def call_tool(_ctx: Any, params: Any) -> CallToolResult:
        name, args = params.name, dict(params.arguments or {})
        if name not in TOOLS:
            common.log_jsonl(log_path, {"tool": name, "args": args, "accepted": False, "code": -32601})
            raise MCPError(code=-32601, message=f"unknown tool: {name}")
        problem = validate(name, args)
        if problem:
            common.log_jsonl(
                log_path,
                {"tool": name, "args": args, "accepted": False, "code": -32602, "message": problem},
            )
            raise MCPError(code=-32602, message=f"invalid params: {problem}")
        common.log_jsonl(log_path, {"tool": name, "args": args, "accepted": True})
        result = {"result": CANNED[name], "received": args}
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result))],
            structuredContent=result,
            isError=False,
        )

    return Server("fake-github-mcp", version="0.0.1", on_list_tools=list_tools, on_call_tool=call_tool)


def main() -> None:
    ap = argparse.ArgumentParser(description="Fake GitHub MCP server (offline proof only)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--log", default=str(common.OUT / "upstream_calls.jsonl"))
    a = ap.parse_args()
    import uvicorn

    uvicorn.run(
        common.local_http_app(create_server(a.log), a.host),
        host=a.host,
        port=a.port,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
