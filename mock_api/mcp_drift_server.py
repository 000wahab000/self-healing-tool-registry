"""Mock drift MCP server with runtime mutation controls (Contract 8).

Exposes mock tool definitions over the official Model Context Protocol (MCP) low-level
Server interface, supporting both stdio and Streamable HTTP transports.

Contract 8: Mock Drift Control
-----------------------------
This server provides programmatic Python methods and MCP admin tools to apply, inspect,
and reset API schema mutations at runtime:

Python API:
    - apply_mutation(name: str | None) -> None: Apply a named mutation, or None to reset.
    - reset() -> None: Clear active mutation and re-seed in-memory data to baseline.
    - list_mutations() -> list[str]: Return list of supported mutation names.
    - current_mutation -> str | None: Property returning the currently active mutation.

Admin MCP Tools:
    - __admin_apply(name: str): Apply a mutation via MCP tool call.
    - __admin_reset(): Reset mutations and data via MCP tool call.
    - __admin_list(): List available mutations and active status via MCP tool call.

Profiles:
    - "users": default profile mirroring the REST mock API.
      Tools: get_user, update_email, set_manager, create_ticket.
    - "tickets": secondary profile for multi-server topologies.
      Tools: create_ticket, list_tickets.

Mutations:
    - "M1": Argument renamed on get_user: 'user_id' -> 'customer_id'.
    - "M2": Argument retyped on update_email: 'user_id' string -> integer.
    - "T-RENAME": Tool renamed: 'get_user' -> 'fetch_user'.
    - "T-REQUIRED": New required argument on update_email: 'reason' (string).
    - "T-ENUM": Enum values changed on update_email: 'email_type' ['personal', 'work'] -> ['PERSONAL', 'WORK'].
    - "M8": Unsafe required argument added to create_ticket: 'priority' with no safe default.

Failure semantics:
    - Unknown tool: JSON-RPC error code -32601 ("Method not found").
    - Schema validation failure: CallToolResult with isError=True and validation explanation.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
from typing import Any, Literal

import jsonschema
from mcp import MCPError
from mcp.server import stdio
from mcp.server.lowlevel import Server
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool
from starlette.applications import Starlette

from healer import canonical

MUTATIONS: tuple[str, ...] = (
    "M1",
    "M2",
    "T-RENAME",
    "T-REQUIRED",
    "T-ENUM",
    "M8",
)

SEED: dict[str, Any] = {
    "users": {
        "123": {"name": "Ada", "email": "ada@example.com", "manager_id": None},
        "456": {"name": "Bob", "email": "bob@example.com", "manager_id": None},
    },
    "tickets": [],
}


def _users_baseline_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_user",
            "description": "Retrieve user details by user ID",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier",
                    }
                },
                "required": ["user_id"],
            },
        },
        {
            "name": "update_email",
            "description": "Update a user's email address",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier",
                    },
                    "email": {
                        "type": "string",
                        "description": "New email address",
                    },
                    "email_type": {
                        "type": "string",
                        "description": "Email category",
                        "enum": ["personal", "work"],
                    },
                },
                "required": ["user_id", "email", "email_type"],
            },
        },
        {
            "name": "set_manager",
            "description": "Assign a manager to a user",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Employee to update",
                    },
                    "manager_id": {
                        "type": "string",
                        "description": "Manager to assign",
                    },
                },
                "required": ["user_id", "manager_id"],
            },
        },
        {
            "name": "create_ticket",
            "description": "Create a support ticket",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier",
                    },
                    "title": {
                        "type": "string",
                        "description": "Ticket title",
                    },
                },
                "required": ["user_id", "title"],
            },
        },
    ]


def _tickets_baseline_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "create_ticket",
            "description": "Create a support ticket",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "User identifier",
                    },
                    "title": {
                        "type": "string",
                        "description": "Ticket title",
                    },
                },
                "required": ["user_id", "title"],
            },
        },
        {
            "name": "list_tickets",
            "description": "List existing support tickets",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Filter by user identifier",
                    }
                },
            },
        },
    ]


def _admin_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "__admin_apply",
            "description": "Apply a schema drift mutation by name (Contract 8)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Mutation identifier (M1, M2, T-RENAME, T-REQUIRED, T-ENUM, M8)",
                    }
                },
                "required": ["name"],
            },
        },
        {
            "name": "__admin_reset",
            "description": "Reset mutations and restore data to baseline (Contract 8)",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "__admin_list",
            "description": "List available mutation identifiers and current status (Contract 8)",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


class McpDriftServer:
    """Mock drift MCP server implementing Contract 8."""

    def __init__(
        self,
        profile: Literal["users", "tickets"] = "users",
        name: str | None = None,
    ) -> None:
        if profile not in ("users", "tickets"):
            raise ValueError(f"Unknown profile: {profile!r}. Expected 'users' or 'tickets'.")
        self.profile = profile
        self.server_name = name or f"mock-drift-{profile}"
        self.data: dict[str, Any] = {}
        self._current_mutation: str | None = None
        self.reset()
        self.server: Server = self._build_lowlevel_server()

    @property
    def current_mutation(self) -> str | None:
        return self._current_mutation

    def list_mutations(self) -> list[str]:
        return list(MUTATIONS)

    def apply_mutation(self, name: str | None) -> None:
        if name is None:
            self._current_mutation = None
            return
        if name not in MUTATIONS:
            raise ValueError(f"Unknown mutation: {name!r}. Supported: {list(MUTATIONS)}")
        self._current_mutation = name

    def reset(self) -> None:
        self.data = copy.deepcopy(SEED)
        self._current_mutation = None

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        base = (
            _users_baseline_tools()
            if self.profile == "users"
            else _tickets_baseline_tools()
        )
        tools = copy.deepcopy(base)
        mutation = self._current_mutation

        if mutation == "M1":
            for tool in tools:
                if tool["name"] == "get_user":
                    schema = tool["inputSchema"]
                    schema["properties"] = {
                        "customer_id": {
                            "type": "string",
                            "description": "Customer identifier",
                        }
                    }
                    schema["required"] = ["customer_id"]

        elif mutation == "M2":
            for tool in tools:
                if tool["name"] == "update_email":
                    tool["inputSchema"]["properties"]["user_id"] = {
                        "type": "integer",
                        "description": "User identifier as integer",
                    }

        elif mutation == "T-RENAME":
            for tool in tools:
                if tool["name"] == "get_user":
                    tool["name"] = "fetch_user"

        elif mutation == "T-REQUIRED":
            for tool in tools:
                if tool["name"] == "update_email":
                    schema = tool["inputSchema"]
                    schema["properties"]["reason"] = {
                        "type": "string",
                        "description": "Reason for updating email",
                    }
                    if "reason" not in schema["required"]:
                        schema["required"].append("reason")

        elif mutation == "T-ENUM":
            for tool in tools:
                if tool["name"] == "update_email":
                    tool["inputSchema"]["properties"]["email_type"]["enum"] = [
                        "PERSONAL",
                        "WORK",
                    ]

        elif mutation == "M8":
            for tool in tools:
                if tool["name"] == "create_ticket":
                    schema = tool["inputSchema"]
                    schema["properties"]["priority"] = {
                        "type": "string",
                        "description": "Ticket priority",
                        "enum": ["low", "medium", "high"],
                    }
                    if "priority" not in schema["required"]:
                        schema["required"].append("priority")

        return tools + copy.deepcopy(_admin_tools())

    def _build_lowlevel_server(self) -> Server:
        async def list_tools(_context: Any, _params: Any) -> ListToolsResult:
            defs = self.get_tool_definitions()
            return ListToolsResult(
                tools=[
                    Tool(
                        name=d["name"],
                        description=d.get("description", ""),
                        inputSchema=d["inputSchema"],
                    )
                    for d in defs
                ]
            )

        async def call_tool(_context: Any, params: Any) -> CallToolResult:
            name = params.name
            args = params.arguments or {}
            defs = {d["name"]: d for d in self.get_tool_definitions()}
            if name not in defs:
                raise MCPError(code=-32601, message=f"Tool not found: {name}")

            tool_def = defs[name]
            schema = tool_def["inputSchema"]

            # Validate arguments against the tool's inputSchema
            validator = jsonschema.Draft202012Validator(schema)
            errors = sorted(validator.iter_errors(args), key=lambda e: str(e.path))
            if errors:
                err_msg = errors[0].message
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Validation error: {err_msg}")],
                    structuredContent={"error": "ValidationError", "detail": err_msg},
                    isError=True,
                )

            # Admin tools
            if name == "__admin_apply":
                self.apply_mutation(args["name"])
                res = {"active": self.current_mutation, "mutations": self.list_mutations()}
                return CallToolResult(
                    content=[TextContent(type="text", text=canonical.dumps(res))],
                    structuredContent=res,
                    isError=False,
                )
            if name == "__admin_reset":
                self.reset()
                res = {"active": None, "mutations": self.list_mutations()}
                return CallToolResult(
                    content=[TextContent(type="text", text=canonical.dumps(res))],
                    structuredContent=res,
                    isError=False,
                )
            if name == "__admin_list":
                res = {"active": self.current_mutation, "mutations": self.list_mutations()}
                return CallToolResult(
                    content=[TextContent(type="text", text=canonical.dumps(res))],
                    structuredContent=res,
                    isError=False,
                )

            # Application tool logic
            try:
                result = self._execute_tool(name, args)
                return CallToolResult(
                    content=[TextContent(type="text", text=canonical.dumps(result))],
                    structuredContent=result,
                    isError=False,
                )
            except MCPError:
                raise
            except Exception as e:  # noqa: BLE001
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Tool execution error: {e}")],
                    structuredContent={"error": "ToolExecutionError", "detail": str(e)},
                    isError=True,
                )

        srv = Server(
            self.server_name,
            version="0.1.0",
            on_list_tools=list_tools,
            on_call_tool=call_tool,
        )
        # Bind contract methods onto the low-level server instance for convenience
        srv.apply_mutation = self.apply_mutation  # type: ignore[attr-defined]
        srv.reset = self.reset  # type: ignore[attr-defined]
        srv.list_mutations = self.list_mutations  # type: ignore[attr-defined]
        return srv

    def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name in ("get_user", "fetch_user"):
            uid = str(args.get("customer_id") if "customer_id" in args else args["user_id"])
            users = self.data["users"]
            if uid not in users:
                raise MCPError(code=-32602, message=f"User not found: {uid}")
            return {"id": uid, **users[uid]}

        if name == "update_email":
            uid = str(args["user_id"])
            users = self.data["users"]
            if uid not in users:
                raise MCPError(code=-32602, message=f"User not found: {uid}")
            users[uid]["email"] = args["email"]
            return {"id": uid, "email": args["email"]}

        if name == "set_manager":
            uid = str(args["user_id"])
            manager_id = str(args["manager_id"])
            users = self.data["users"]
            if uid not in users:
                raise MCPError(code=-32602, message=f"User not found: {uid}")
            if manager_id not in users:
                raise MCPError(code=-32602, message=f"Manager not found: {manager_id}")
            users[uid]["manager_id"] = manager_id
            return {"id": uid, "manager_id": manager_id}

        if name == "create_ticket":
            uid = str(args["user_id"])
            users = self.data["users"]
            if uid not in users:
                raise MCPError(code=-32602, message=f"User not found: {uid}")
            ticket = {
                "ticket_id": f"T-{len(self.data['tickets']) + 1}",
                **args,
            }
            self.data["tickets"].append(ticket)
            return ticket

        if name == "list_tickets":
            uid = args.get("user_id")
            tickets = [
                t for t in self.data["tickets"]
                if uid is None or t["user_id"] == str(uid)
            ]
            return {"tickets": tickets}

        raise MCPError(code=-32601, message=f"Tool not found: {name}")

    def create_initialization_options(self) -> Any:
        return self.server.create_initialization_options()

    async def run(
        self,
        read_stream: Any,
        write_stream: Any,
        initialization_options: Any,
        raise_exceptions: bool = False,
    ) -> None:
        await self.server.run(
            read_stream,
            write_stream,
            initialization_options,
            raise_exceptions=raise_exceptions,
        )

    def create_http_app(
        self,
        *,
        host: str = "127.0.0.1",
        allowed_hosts: list[str] | None = None,
        allowed_origins: list[str] | None = None,
    ) -> Starlette:
        local = host in ("127.0.0.1", "localhost", "::1")
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
        return self.server.streamable_http_app(
            json_response=True,
            host=host,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=hosts,
                allowed_origins=origins,
            ),
        )

    async def run_stdio(self) -> None:
        async with stdio.stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def create_drift_server(
    profile: Literal["users", "tickets"] = "users",
    name: str | None = None,
) -> McpDriftServer:
    """Factory creating an McpDriftServer instance."""
    return McpDriftServer(profile=profile, name=name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Mock Drift MCP Server")
    parser.add_argument("--profile", choices=("users", "tickets"), default="users")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    drift_server = create_drift_server(profile=args.profile)

    if args.transport == "stdio":
        asyncio.run(drift_server.run_stdio())
    else:
        import uvicorn

        app = drift_server.create_http_app(host=args.host)
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
