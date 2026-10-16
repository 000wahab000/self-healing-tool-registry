from __future__ import annotations

from healer.models import ErrorClass, Outcome
from healer.verify import verify


def test_verification_has_ordered_seven_machine_readable_results():
    result = asyncio_result(verify(
        base_doc={"body": {"id": 1}}, current_spec=None, fix={"request_ops": [], "response_ops": []},
        cfg={}, tool_cfg={}, response=Outcome(ErrorClass.OK, "rest", "200", data={"id": 1}),
    ))
    assert [row["layer"] for row in result] == [f"L{i}" for i in range(1, 8)]
    assert all(set(row) == {"layer", "name", "status", "detail"} for row in result)
    assert all(row["status"] in {"pass", "fail", "skip"} for row in result)


def test_spec_unavailable_does_not_claim_l2_pass():
    import asyncio

    result = asyncio.run(verify(
        base_doc={}, current_spec=None, fix={"request_ops": [], "response_ops": []},
        cfg={}, tool_cfg={}, response=Outcome(ErrorClass.OK, "rest", "200", data={}),
    ))
    assert result[1]["status"] == "skip"


def test_write_readback_and_invariant_layers():
    import asyncio

    calls = 0

    async def readback():
        nonlocal calls
        calls += 1
        return {"id": 1}

    from healer.verify import Verifier

    verifier = Verifier()
    base = {"body": {"id": 1}}
    fix = {"request_ops": [{"op": "cast", "path": ["body", "id"], "to": "str"}], "response_ops": []}
    cfg = {"write": True, "invariants": [{"type": "non_empty", "response": ["id"]}]}
    preflight = verifier.preflight(base_doc=base, current_spec=None, fix=fix,
        original_failure=ErrorClass.E2, cfg={}, tool_cfg=cfg,
        original_status="400", no_side_effect=True)
    result = asyncio.run(verifier.verify_response(results=preflight,
        outcome=Outcome(ErrorClass.OK, "rest", "200", data={"id": 1}),
        agent_output_schema=None, base_doc=base, tool_cfg=cfg, healed_write=True, readback=readback))
    assert result[4]["status"] == "pass"
    assert result[5]["status"] == "pass"
    assert calls == 1


def test_non_idempotent_write_requires_safe_rejection_or_actual_key():
    args = {
        "base_doc": {}, "current_spec": None,
        "fix": {"request_ops": [], "response_ops": []}, "cfg": {},
        "tool_cfg": {"write": True},
        "response": Outcome(ErrorClass.OK, "rest", "200", data={}),
    }
    from healer.verify import Verifier

    verifier = Verifier()
    preflight = verifier.preflight(base_doc=args["base_doc"], current_spec=None, fix=args["fix"],
        original_failure=ErrorClass.E4, cfg={}, tool_cfg=args["tool_cfg"])
    result = preflight
    assert result[6]["status"] == "fail"
    args["base_doc"] = {"header": {"Idempotency-Key": "key"}}
    keyed = verifier.preflight(base_doc=args["base_doc"], current_spec=None, fix=args["fix"],
        original_failure=ErrorClass.E4, cfg={}, tool_cfg=args["tool_cfg"])
    assert keyed[6]["status"] == "pass"


def test_preflight_validates_patched_document_strictly():
    from healer.verify import Verifier

    spec = {
        "method": "POST", "path": "/x", "body_schema": {
            "type": "object", "properties": {"id": {"type": "integer"}},
            "required": ["id"],
        }, "params": [],
    }
    result = Verifier().preflight(
        base_doc={"body": {"id": "4", "unknown": True}}, current_spec=spec,
        fix={"request_ops": [{"op": "cast", "path": ["body", "id"], "to": "int"}], "response_ops": []},
        original_failure=ErrorClass.E2, cfg={}, tool_cfg={},
    )
    assert result[1]["status"] == "fail"
    assert result[1]["detail"] == "schema_invalid"


def asyncio_result(awaitable):
    import asyncio

    return asyncio.run(awaitable)
