from __future__ import annotations

import json
from typing import Any

import pytest
from mcp.shared.exceptions import MCPError

from healer import canonical
from mock_api.mcp_drift_server import MUTATIONS, McpDriftServer


def _dump_tools(tools: list[Any]) -> str:
    serialized = [t.model_dump(by_alias=True) for t in tools]
    return canonical.dumps(serialized)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", list(MUTATIONS))
async def test_ac_50_mutation_changes_tools_list(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
    mutation: str,
) -> None:
    """AC-50: for each mutation, tools/list differs from baseline."""
    async with mcp_session_factory(drift_users_server) as session:
        baseline_res = await session.list_tools()
        baseline_dump = _dump_tools(baseline_res.tools)

        drift_users_server.apply_mutation(mutation)
        mutated_res = await session.list_tools()
        mutated_dump = _dump_tools(mutated_res.tools)

        assert mutated_dump != baseline_dump, f"tools/list did not change under mutation {mutation}"


@pytest.mark.asyncio
async def test_ac_50_m1_rename_argument_fails_old_call(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-50 (M1): get_user with old user_id argument fails; customer_id succeeds."""
    async with mcp_session_factory(drift_users_server) as session:
        # Baseline call succeeds
        base_res = await session.call_tool("get_user", {"user_id": "123"})
        assert not base_res.is_error
        data = json.loads(base_res.content[0].text)
        assert data["name"] == "Ada"

        # Apply M1 (user_id -> customer_id)
        drift_users_server.apply_mutation("M1")

        # Calling with old shape fails
        old_call = await session.call_tool("get_user", {"user_id": "123"})
        assert old_call.is_error
        assert "customer_id" in old_call.content[0].text

        # Calling with new shape succeeds
        new_call = await session.call_tool("get_user", {"customer_id": "123"})
        assert not new_call.is_error
        new_data = json.loads(new_call.content[0].text)
        assert new_data["name"] == "Ada"


@pytest.mark.asyncio
async def test_ac_50_m2_retype_argument_fails_old_call(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-50 (M2): update_email with string user_id fails; integer user_id succeeds."""
    async with mcp_session_factory(drift_users_server) as session:
        # Baseline call succeeds
        base_res = await session.call_tool(
            "update_email",
            {"user_id": "123", "email": "ada-new@example.com", "email_type": "work"},
        )
        assert not base_res.is_error

        # Apply M2 (user_id string -> integer)
        drift_users_server.apply_mutation("M2")

        # Calling with string user_id fails
        old_call = await session.call_tool(
            "update_email",
            {"user_id": "123", "email": "ada-m2@example.com", "email_type": "work"},
        )
        assert old_call.is_error
        assert "integer" in old_call.content[0].text

        # Calling with integer user_id succeeds
        new_call = await session.call_tool(
            "update_email",
            {"user_id": 123, "email": "ada-m2@example.com", "email_type": "work"},
        )
        assert not new_call.is_error
        data = json.loads(new_call.content[0].text)
        assert data["email"] == "ada-m2@example.com"


@pytest.mark.asyncio
async def test_ac_50_t_rename_tool_fails_old_call(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-50 (T-RENAME): get_user renamed to fetch_user; calling get_user returns JSON-RPC -32601."""
    async with mcp_session_factory(drift_users_server) as session:
        # Apply T-RENAME
        drift_users_server.apply_mutation("T-RENAME")

        tools = await session.list_tools()
        names = [t.name for t in tools.tools]
        assert "get_user" not in names
        assert "fetch_user" in names

        # Calling unknown tool raises MCPError -32601
        with pytest.raises(MCPError) as exc_info:
            await session.call_tool("get_user", {"user_id": "123"})
        assert exc_info.value.error.code == -32601

        # Calling fetch_user succeeds
        new_call = await session.call_tool("fetch_user", {"user_id": "123"})
        assert not new_call.is_error
        data = json.loads(new_call.content[0].text)
        assert data["name"] == "Ada"


@pytest.mark.asyncio
async def test_ac_50_t_required_new_argument_fails_old_call(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-50 (T-REQUIRED): update_email requires 'reason'; old call without 'reason' fails."""
    async with mcp_session_factory(drift_users_server) as session:
        # Apply T-REQUIRED
        drift_users_server.apply_mutation("T-REQUIRED")

        # Calling without reason fails
        old_call = await session.call_tool(
            "update_email",
            {"user_id": "123", "email": "ada-req@example.com", "email_type": "work"},
        )
        assert old_call.is_error
        assert "reason" in old_call.content[0].text

        # Calling with reason succeeds
        new_call = await session.call_tool(
            "update_email",
            {
                "user_id": "123",
                "email": "ada-req@example.com",
                "email_type": "work",
                "reason": "Department change",
            },
        )
        assert not new_call.is_error
        data = json.loads(new_call.content[0].text)
        assert data["email"] == "ada-req@example.com"


@pytest.mark.asyncio
async def test_ac_50_t_enum_changed_fails_old_call(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-50 (T-ENUM): email_type enum changed to uppercase; lowercase 'work' fails."""
    async with mcp_session_factory(drift_users_server) as session:
        # Apply T-ENUM
        drift_users_server.apply_mutation("T-ENUM")

        # Calling with lowercase 'work' fails
        old_call = await session.call_tool(
            "update_email",
            {"user_id": "123", "email": "ada-enum@example.com", "email_type": "work"},
        )
        assert old_call.is_error
        assert "WORK" in old_call.content[0].text

        # Calling with uppercase 'WORK' succeeds
        new_call = await session.call_tool(
            "update_email",
            {"user_id": "123", "email": "ada-enum@example.com", "email_type": "WORK"},
        )
        assert not new_call.is_error
        data = json.loads(new_call.content[0].text)
        assert data["email"] == "ada-enum@example.com"


@pytest.mark.asyncio
async def test_ac_50_m8_unsafe_drift_fails_old_call(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-50 (M8): create_ticket requires priority; call without priority fails."""
    async with mcp_session_factory(drift_users_server) as session:
        # Baseline call succeeds
        base_res = await session.call_tool(
            "create_ticket",
            {"user_id": "123", "title": "Printer broken"},
        )
        assert not base_res.is_error

        # Apply M8
        drift_users_server.apply_mutation("M8")

        # Calling without priority fails
        old_call = await session.call_tool(
            "create_ticket",
            {"user_id": "123", "title": "Network down"},
        )
        assert old_call.is_error
        assert "priority" in old_call.content[0].text

        # Calling with priority succeeds
        new_call = await session.call_tool(
            "create_ticket",
            {"user_id": "123", "title": "Network down", "priority": "high"},
        )
        assert not new_call.is_error
        data = json.loads(new_call.content[0].text)
        assert data["priority"] == "high"
