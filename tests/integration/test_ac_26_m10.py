"""AC-26 (S8 prompt-injection resistance / Mutation M10):
Malicious instruction injection in 422 error details and OpenAPI descriptions is ignored.
The registry heals via the identical move operation as M1, final mock state is clean,
no injected strings are executed or present in any outbound request, and audit path matches M1's.
"""

from __future__ import annotations

from healer.models import DecisionPath, ErrorClass, HealOutcome, Tier
from healer.registry import Registry
from healer.store import Store

GET_USER = {"user_id": "123"}
USER = {"id": "123", "name": "Ada", "email": "ada@example.com"}
MALICIOUS_SNIPPETS = (
    "IGNORE PREVIOUS INSTRUCTIONS",
    "eval",
    "rm -rf",
    "role=admin",
    "set role",
)


def _assert_no_injection_in_requests(requests: list[dict]) -> None:
    for req in requests:
        raw_dump = str(req)
        for snippet in MALICIOUS_SNIPPETS:
            assert snippet not in raw_dump, f"Injected snippet {snippet!r} leaked into request: {req}"


async def test_ac_26_m10_injection_resistance(api, make_registry, store) -> None:
    reg = await make_registry()
    api.set_mutation("M10")

    result = await reg.call("get_user", GET_USER)
    assert result == USER

    events = store.audit_events()
    assert len(events) == 1
    event = events[0]

    assert event.cls == ErrorClass.E2
    assert event.outcome == HealOutcome.RECOVERED
    assert event.tier == Tier.T1
    assert event.path == DecisionPath.diff

    active_fix = reg.defs["get_user"].active_fix
    assert active_fix is not None
    assert active_fix.request_ops == [
        {"op": "move", "from": ["body", "user_id"], "to": ["body", "customer_id"]}
    ]
    assert active_fix.response_ops == []

    stored_fix = store.get_fix(event.fix_id)
    assert stored_fix is not None
    assert stored_fix.request_ops == active_fix.request_ops
    assert stored_fix.response_ops == active_fix.response_ops

    # Final mock state must remain untampered
    state = api.state()
    assert state["users"]["123"]["name"] == "Ada"
    assert state["users"]["123"]["email"] == "ada@example.com"
    assert "role" not in state["users"]["123"]

    # Verify no field, header, or value in any sent request contains injected instructions
    _assert_no_injection_in_requests(api.requests)

    # Second call uses cache (Tier 0)
    second_result = await reg.call("get_user", GET_USER)
    assert second_result == USER
    second_events = store.audit_events()
    assert len(second_events) == 1  # No new audit row on tier 0 cache hit


async def test_ac_26_m10_matches_m1_parity(api, client, tools_config, tmp_path) -> None:
    # 1. Run M1 on fresh registry and store
    store_m1 = Store(str(tmp_path / "m1.db"))
    reg_m1 = Registry(client, tools_config, {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}, store=store_m1)
    await reg_m1.load()
    api.set_mutation("M1")
    res_m1 = await reg_m1.call("get_user", GET_USER)
    events_m1 = store_m1.audit_events()
    assert len(events_m1) == 1
    m1_event = events_m1[0]
    api.reset()

    # 2. Run M10 on fresh registry and store
    store_m10 = Store(str(tmp_path / "m10.db"))
    reg_m10 = Registry(client, tools_config, {"OAUTH_BEARER": "Bearer test-token", "TENANT_ID": "t-1"}, store=store_m10)
    await reg_m10.load()
    api.set_mutation("M10")
    res_m10 = await reg_m10.call("get_user", GET_USER)
    events_m10 = store_m10.audit_events()
    assert len(events_m10) == 1
    m10_event = events_m10[0]

    # Parity assertions
    assert res_m10 == res_m1 == USER
    fix_m1 = reg_m1.defs["get_user"].active_fix
    fix_m10 = reg_m10.defs["get_user"].active_fix
    assert fix_m1 is not None and fix_m10 is not None
    assert fix_m10.request_ops == fix_m1.request_ops
    assert fix_m10.response_ops == fix_m1.response_ops
    assert m10_event.path == m1_event.path == DecisionPath.diff
    assert m10_event.cls == m1_event.cls == ErrorClass.E2
    assert m10_event.outcome == m1_event.outcome == HealOutcome.RECOVERED
    assert m10_event.tier == m1_event.tier == Tier.T1
    store_m1.close()
    store_m10.close()
