from __future__ import annotations

import json
from typing import Any

import pytest

from healer import canonical
from mock_api.mcp_drift_server import MUTATIONS, McpDriftServer


def _dump_tools(tools: list[Any]) -> str:
    serialized = [t.model_dump(by_alias=True) for t in tools]
    return canonical.dumps(serialized)


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", list(MUTATIONS))
async def test_ac_51_reset_restores_tools_list_byte_for_byte(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
    mutation: str,
) -> None:
    """AC-51: reset restores tools/list byte for byte after any mutation."""
    async with mcp_session_factory(drift_users_server) as session:
        # Record baseline
        baseline_res = await session.list_tools()
        baseline_bytes = _dump_tools(baseline_res.tools)

        # Mutate
        drift_users_server.apply_mutation(mutation)
        mutated_res = await session.list_tools()
        mutated_bytes = _dump_tools(mutated_res.tools)
        assert mutated_bytes != baseline_bytes

        # Reset
        drift_users_server.reset()
        reset_res = await session.list_tools()
        reset_bytes = _dump_tools(reset_res.tools)

        # Byte-for-byte identity check
        assert reset_bytes == baseline_bytes
        assert drift_users_server.current_mutation is None


@pytest.mark.asyncio
async def test_ac_51_reset_restores_data_state(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-51: reset restores in-memory users and tickets to SEED state."""
    async with mcp_session_factory(drift_users_server) as session:
        # Mutate data: update email and add a ticket
        await session.call_tool(
            "update_email",
            {"user_id": "123", "email": "changed@example.com", "email_type": "work"},
        )
        await session.call_tool(
            "create_ticket",
            {"user_id": "123", "title": "Temporary ticket"},
        )
        assert drift_users_server.data["users"]["123"]["email"] == "changed@example.com"
        assert len(drift_users_server.data["tickets"]) == 1

        # Reset restores data
        drift_users_server.reset()
        assert drift_users_server.data["users"]["123"]["email"] == "ada@example.com"
        assert len(drift_users_server.data["tickets"]) == 0


@pytest.mark.asyncio
async def test_ac_51_second_profile_lists_different_tools(
    drift_users_server: McpDriftServer,
    drift_tickets_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-51: profile='tickets' lists a different toolset than profile='users'."""
    async with mcp_session_factory(drift_users_server) as users_session:
        users_res = await users_session.list_tools()
        users_tools = {t.name for t in users_res.tools}

    async with mcp_session_factory(drift_tickets_server) as tickets_session:
        tickets_res = await tickets_session.list_tools()
        tickets_tools = {t.name for t in tickets_res.tools}

    # Verify tool sets differ
    assert users_tools != tickets_tools
    assert "get_user" in users_tools
    assert "get_user" not in tickets_tools
    assert "list_tickets" in tickets_tools
    assert "list_tickets" not in users_tools

    # Test ticket tools work in profile='tickets'
    async with mcp_session_factory(drift_tickets_server) as session:
        t_call = await session.call_tool(
            "create_ticket",
            {"user_id": "123", "title": "Issue in secondary server"},
        )
        assert not t_call.is_error
        t_data = json.loads(t_call.content[0].text)
        assert t_data["ticket_id"] == "T-1"

        l_call = await session.call_tool("list_tickets", {"user_id": "123"})
        assert not l_call.is_error
        l_data = json.loads(l_call.content[0].text)
        assert len(l_data["tickets"]) == 1


@pytest.mark.asyncio
async def test_ac_51_admin_tools_over_mcp(
    drift_users_server: McpDriftServer,
    mcp_session_factory: Any,
) -> None:
    """AC-51 / Contract 8: admin tools (__admin_apply, __admin_list, __admin_reset) operate over MCP."""
    async with mcp_session_factory(drift_users_server) as session:
        # __admin_list
        list_res = await session.call_tool("__admin_list", {})
        assert not list_res.is_error
        info = json.loads(list_res.content[0].text)
        assert info["active"] is None
        assert "M1" in info["mutations"]

        # __admin_apply
        apply_res = await session.call_tool("__admin_apply", {"name": "M1"})
        assert not apply_res.is_error
        info_m1 = json.loads(apply_res.content[0].text)
        assert info_m1["active"] == "M1"
        assert drift_users_server.current_mutation == "M1"

        # Verify mutation is active in tools/list
        tools_m1 = await session.list_tools()
        get_user_tool = next(t for t in tools_m1.tools if t.name == "get_user")
        assert "customer_id" in get_user_tool.input_schema["properties"]

        # __admin_reset
        reset_res = await session.call_tool("__admin_reset", {})
        assert not reset_res.is_error
        info_reset = json.loads(reset_res.content[0].text)
        assert info_reset["active"] is None
        assert drift_users_server.current_mutation is None

        # Verify baseline restored
        tools_restored = await session.list_tools()
        get_user_base = next(t for t in tools_restored.tools if t.name == "get_user")
        assert "user_id" in get_user_base.input_schema["properties"]
