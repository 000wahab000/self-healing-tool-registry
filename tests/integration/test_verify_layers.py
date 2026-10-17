from __future__ import annotations

import asyncio

from healer.models import ErrorClass, Outcome
from healer.verify import Verifier


def test_patched_request_must_match_fresh_spec():
    spec = {"method": "POST", "path": "/x", "body_schema": {
        "type": "object", "properties": {"new": {"type": "string"}},
        "required": ["new"],
    }, "params": []}
    rows = Verifier().preflight(
        base_doc={"body": {"old": "value"}}, current_spec=spec,
        fix={"request_ops": [], "response_ops": []}, original_failure=ErrorClass.E2,
        cfg={}, tool_cfg={}, original_status="422", no_side_effect=True,
    )
    assert rows[1]["status"] == "fail"
    assert rows[2:6] == [{"layer": f"L{i}", "name": name, "status": "skip", "detail": "not_reached"}
        for i, name in enumerate(("response_schema", "postchecks", "readback", "invariants"), 3)]


def test_response_layers_reject_bad_base_shape():
    async def run():
        rows = Verifier().preflight(base_doc={}, current_spec=None,
            fix={"request_ops": [], "response_ops": []}, original_failure=ErrorClass.E5,
            cfg={}, tool_cfg={"idempotent": True})
        return await Verifier().verify_response(results=rows,
            outcome=Outcome(ErrorClass.OK, "rest", "200", data={"unexpected": 1}),
            agent_output_schema={"type": "object", "properties": {"id": {"type": "integer"}},
                                 "required": ["id"]}, base_doc={}, tool_cfg={})
    result = asyncio.run(run())
    assert result[2]["status"] == "fail"
    assert result[3:6] == [{"layer": f"L{i}", "name": name, "status": "skip", "detail": "not_reached"}
        for i, name in enumerate(("postchecks", "readback", "invariants"), 4)]


async def test_m7_layers_audited_and_registry_only_commits_after_pass(
    api, store, make_registry
):
    registry = await make_registry()
    before_schema = registry.tools()
    tool = registry.defs["update_email"]
    before_version, before_wire = tool.version, tool.wire_op.copy()
    api.set_mutation("M7")

    result = await registry.call("update_email", {"user_id": "123", "email": "new@example.com"})

    assert result == {"id": "123", "email": "new@example.com"}
    (event,) = store.audit_events()
    assert [(row["layer"], row["status"]) for row in event.layers] == [
        (f"L{i}", "pass") for i in range(1, 8)
    ]
    assert registry.tools() == before_schema
    assert tool.version == before_version + 1 and tool.wire_op != before_wire


def test_w1_readback_mismatch_and_invariant_failure_are_separate_layers():
    async def run():
        verifier = Verifier(sleep=lambda _: asyncio.sleep(0))
        base = {"body": {"user_id": "123", "email": "intended@example.com"}}
        config = {
            "write": True,
            "idempotent": True,
            "readback": {"key_from": ["body", "user_id"], "compare": ["email"]},
            "invariants": [{"type": "id_equals_request", "response": ["id"],
                            "request": ["body", "user_id"]}],
        }
        rows = verifier.preflight(
            base_doc=base, current_spec=None,
            fix={"request_ops": [], "response_ops": []},
            original_failure=ErrorClass.E2, cfg={}, tool_cfg=config,
            original_status="422", no_side_effect=True,
        )
        return await verifier.verify_response(
            results=rows, outcome=Outcome(ErrorClass.OK, "rest", "200",
                data={"id": "123", "email": "spoofed@example.com"}),
            agent_output_schema=None, base_doc=base, tool_cfg=config,
            healed_write=True,
            readback=lambda: _async_value({"id": "123", "email": "old@example.com"}),
            readback_expected=base,
        )

    rows = asyncio.run(run())
    assert rows[4]["status"] == "fail"  # W1: API response is not persisted state.
    assert rows[5]["status"] == "pass"


async def _async_value(value):
    return value


def test_l6_invariant_and_l7_unsafe_write_fail_independently():
    async def run():
        verifier = Verifier()
        base = {"body": {"user_id": "123"}}
        cfg = {"write": True, "invariants": [{"type": "id_equals_request",
            "response": ["id"], "request": ["body", "user_id"]}]}
        rows = verifier.preflight(base_doc=base, current_spec=None,
            fix={"request_ops": [], "response_ops": []}, original_failure=ErrorClass.E2,
            cfg={}, tool_cfg=cfg, original_status="422", no_side_effect=True)
        rows = await verifier.verify_response(results=rows,
            outcome=Outcome(ErrorClass.OK, "rest", "200", data={"id": "other"}),
            agent_output_schema=None, base_doc=base, tool_cfg=cfg)
        unsafe = verifier.preflight(base_doc=base, current_spec=None,
            fix={"request_ops": [], "response_ops": []}, original_failure=ErrorClass.E4,
            cfg={}, tool_cfg=cfg)
        return rows, unsafe

    rows, unsafe = asyncio.run(run())
    assert rows[5]["status"] == "fail"
    assert unsafe[6]["status"] == "fail"


# Live GitHub MCP finding: a partial unwrap left {"args": {"state": ...}} behind; GitHub ignores
# unknown keys, so the call "worked" and the filter was silently dropped.
_LIST_ISSUES = {"method": "MCP", "path": "list_issues", "params": [], "body_schema": {
    "type": "object",
    "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "state": {"type": "string"}},
    "required": ["owner", "repo"],
}}


def _l2(base_body: dict, ops: list[dict]) -> dict:
    return Verifier().preflight(
        base_doc={"body": base_body}, current_spec=_LIST_ISSUES,
        fix={"request_ops": ops, "response_ops": []}, original_failure=ErrorClass.E2,
        cfg={}, tool_cfg={}, original_status="-32602", no_side_effect=True,
    )[1]


def test_mcp_partial_unwrap_fails_request_schema():
    wrapped = {"args": {"owner": "o", "repo": "r", "state": "OPEN"}}
    partial = [{"op": "move", "from": ["body", "args", k], "to": ["body", k]} for k in ("owner", "repo")]
    assert _l2(wrapped, partial) == {"layer": "L2", "name": "request_schema", "status": "fail", "detail": "schema_invalid"}


def test_mcp_full_unwrap_drops_the_empty_wrapper_and_passes():
    wrapped = {"args": {"owner": "o", "repo": "r", "state": "OPEN"}}
    full = [{"op": "move", "from": ["body", "args", k], "to": ["body", k]} for k in ("owner", "repo", "state")]
    assert _l2(wrapped, full)["status"] == "pass"
