from __future__ import annotations

from healer.models import ErrorClass
from healer.verify import Verifier


def test_mcp_invalid_params_allows_replay():
    """MCP + -32602 (invalid params) is a pre-execution rejection: replay is allowed."""
    verifier = Verifier()
    base = {"route": {"method": "MCP", "path": "update_email"}, "body": {"user_id": "123"}}
    spec = {
        "operation_id": "update_email",
        "method": "MCP",
        "path": "update_email",
        "body_schema": {"type": "object", "properties": {"user_id": {"type": "integer"}}},
        "params": [],
    }
    tool_cfg = {"write": True, "idempotent": False}
    rows = verifier.preflight(
        base_doc=base,
        current_spec=spec,
        fix={"request_ops": [{"op": "cast", "path": ["body", "user_id"], "to": "int"}], "response_ops": []},
        original_failure=ErrorClass.E2,
        cfg={},
        tool_cfg=tool_cfg,
        original_status="-32602",
        no_side_effect=True,
    )
    assert rows[1]["layer"] == "L2"
    assert rows[1]["status"] == "skip"
    assert rows[1]["detail"] == "protocol_schema"
    assert rows[6]["layer"] == "L7"
    assert rows[6]["status"] == "pass"
    assert rows[6]["detail"] == "ok"


def test_mcp_internal_error_refuses_replay():
    """MCP + internal error (-32603, E1) cannot be proven safe: replay is refused."""
    verifier = Verifier()
    base = {"route": {"method": "MCP", "path": "create_ticket"}, "body": {"title": "Help"}}
    spec = {
        "operation_id": "create_ticket",
        "method": "MCP",
        "path": "create_ticket",
        "body_schema": {"type": "object", "properties": {"title": {"type": "string"}}},
        "params": [],
    }
    tool_cfg = {"write": True, "idempotent": False}
    rows = verifier.preflight(
        base_doc=base,
        current_spec=spec,
        fix={"request_ops": [], "response_ops": []},
        original_failure=ErrorClass.E1,
        cfg={},
        tool_cfg=tool_cfg,
        original_status="-32603",
        no_side_effect=False,
    )
    assert rows[6]["layer"] == "L7"
    assert rows[6]["status"] == "fail"
    assert rows[6]["detail"] == "unsafe_replay"


def test_mcp_unknown_error_refuses_replay():
    """An unknown MCP error code without idempotency config is treated as unsafe."""
    verifier = Verifier()
    base = {"route": {"method": "MCP", "path": "create_ticket"}, "body": {}}
    tool_cfg = {"write": True, "idempotent": False}
    rows = verifier.preflight(
        base_doc=base,
        current_spec=None,
        fix={"request_ops": [], "response_ops": []},
        original_failure=ErrorClass.E2,
        cfg={},
        tool_cfg=tool_cfg,
        original_status="-32000",
        no_side_effect=False,
    )
    assert rows[6]["layer"] == "L7"
    assert rows[6]["status"] == "fail"
    assert rows[6]["detail"] == "unsafe_replay"


def test_mcp_idempotent_hint_allows_replay():
    """When the adapter marks the tool idempotent (from hints), replay is allowed."""
    verifier = Verifier()
    base = {"route": {"method": "MCP", "path": "update_email"}, "body": {}}
    tool_cfg = {"write": True, "idempotent": True}
    rows = verifier.preflight(
        base_doc=base,
        current_spec=None,
        fix={"request_ops": [], "response_ops": []},
        original_failure=ErrorClass.E1,
        cfg={},
        tool_cfg=tool_cfg,
        original_status="-32603",
        no_side_effect=False,
    )
    assert rows[6]["layer"] == "L7"
    assert rows[6]["status"] == "pass"
    assert rows[6]["detail"] == "ok"


def test_mcp_protocol_schema_skips_l2():
    """L2 skips for protocol schema tools rather than validating against HTTP OpenAPI schemas."""
    verifier = Verifier()
    spec = {
        "operation_id": "fetch",
        "method": "MCP",
        "path": "fetch",
        "body_schema": {"type": "object"},
        "params": [],
    }
    rows = verifier.preflight(
        base_doc={"route": {"method": "MCP", "path": "fetch"}},
        current_spec=spec,
        fix={"request_ops": [], "response_ops": []},
        original_failure=ErrorClass.E2,
        cfg={},
        tool_cfg={"idempotent": True},
        original_status="-32601",
        no_side_effect=True,
    )
    assert rows[1]["layer"] == "L2"
    assert rows[1]["status"] == "skip"
    assert rows[1]["detail"] == "protocol_schema"
