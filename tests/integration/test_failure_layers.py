from __future__ import annotations

from healer.models import HealOutcome


async def test_w1_registry_audits_unsaved_success_at_readback(api, store, make_registry):
    registry = await make_registry()
<<<<<<< HEAD
=======
    tool = registry.defs["update_email"]
    version, wire_op = tool.version, tool.wire_op.copy()
    agent_schema = registry.tools()
>>>>>>> 59d60c9236144eb80cbf8d119a18900340fef15a
    api.set_mutation("W1")

    result = await registry.call(
        "update_email", {"user_id": "123", "email": "ada.new@example.com"}
    )

    assert result.get("error")
    assert api.state()["users"]["123"]["email"] == "ada@example.com"
<<<<<<< HEAD
    (event,) = store.audit_events()
    assert event.outcome is not HealOutcome.RECOVERED
    assert any(layer["layer"] == "L5" and layer["status"] == "fail" for layer in event.layers)


async def test_d1_registry_does_not_replay_saved_ticket_after_503(api, store, make_registry):
=======
    events = store.audit_events()
    assert len(events) == 1
    (event,) = events
    assert event.outcome is not HealOutcome.RECOVERED
    assert any(layer["layer"] == "L5" and layer["status"] == "fail" for layer in event.layers)
    assert registry.tools() == agent_schema
    assert (tool.version, tool.wire_op) == (version, wire_op)


async def test_d1_registry_does_not_replay_saved_ticket_after_503(
    api, store, make_registry, tools_config
):
    tools_config["tools"]["create_ticket"]["idempotency_key"] = False
>>>>>>> 59d60c9236144eb80cbf8d119a18900340fef15a
    registry = await make_registry()
    api.set_mutation("D1")

    result = await registry.call("create_ticket", {"user_id": "123", "title": "once"})

    assert result.get("error")
    assert len(api.state()["tickets"]) == 1
    assert len([request for request in api.requests if request["path"] == "/tickets"]) == 1
    assert store.audit_events() == []
