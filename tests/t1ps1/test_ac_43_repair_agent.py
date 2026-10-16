"""AC-43 and AC-45: the tier-2 repair agent heals a break tier 1 cannot explain, and can only
ever propose operations that pass the same checks as tier 1."""

from __future__ import annotations

import asyncio
import json

import pytest

from healer.repair import RepairUnavailable


class FakeLlm:
    """Scripted model: returns `answer` and records every prompt it was sent."""

    def __init__(self, answer: str | Exception) -> None:
        self.answer, self.prompts = answer, []

    async def __call__(self, system: str, user: str) -> tuple[str, int]:
        self.prompts.append(user)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer, 42


TOOL, ARGS = "users__get_user", {"user_id": "123"}
GOOD = json.dumps(
    {
        "operation": "users__fetch_user",
        "request_ops": [
            {"op": "move", "from": ["body", "user_id"], "to": ["body", "customer_id"]}
        ],
        "response_ops": [],
    }
)


@pytest.mark.asyncio
async def test_ac_43_repair_agent_heals_unexplained_drift_and_fix_is_reused(
    repair_registry,
):
    llm = FakeLlm("Here is the fix:\n" + GOOD)
    async with repair_registry(llm) as (registry, drift, store):
        frozen = registry.tools()
        drift.apply_mutation("T-MOVE")
        first = await registry.call(TOOL, ARGS)
        second = await registry.call(TOOL, ARGS)
        events = store.audit_events()
        assert registry.tools() == frozen
    assert first["id"] == "123" and second["id"] == "123"
    assert (
        len(llm.prompts) == 1
    )  # the stored fix is reused at tier 0, no second model call
    assert len(events) == 1
    event = events[0]
    assert (event.outcome.value, event.tier, event.path.value) == (
        "RECOVERED",
        2,
        "repair",
    )
    assert event.llm_tokens == 42


@pytest.mark.asyncio
async def test_ac_43_without_agent_the_same_drift_is_refused(repair_registry):
    async with repair_registry(None) as (registry, drift, _):
        drift.apply_mutation("T-MOVE")
        result = await registry.call(TOOL, ARGS)
    assert (
        result["error"] == "SCHEMA_DRIFT_UNRECOVERABLE"
        and result["reason"] == "NO_CANDIDATE"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer",
    [RepairUnavailable("timeout"), "I cannot help", json.dumps({"operation": None})],
)
async def test_ac_43_unavailable_or_declining_model_refuses(repair_registry, answer):
    async with repair_registry(FakeLlm(answer)) as (registry, drift, _):
        drift.apply_mutation("T-MOVE")
        result = await registry.call(TOOL, ARGS)
    assert result["reason"] == "NO_CANDIDATE" and result["retry"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "proposal",
    [
        # an operation the spec does not have
        {"operation": "users__steal_data", "request_ops": [], "response_ops": []},
        # the model routes by itself instead of naming an operation
        {
            "operation": "users__fetch_user",
            "request_ops": [{"op": "route", "method": "MCP", "path": "__admin_reset"}],
        },
        # moving to a field the chosen operation does not have
        {
            "operation": "users__fetch_user",
            "request_ops": [
                {"op": "move", "from": ["body", "user_id"], "to": ["body", "role"]}
            ],
        },
        # an op outside the DSL (no code, no free values)
        {
            "operation": "users__fetch_user",
            "request_ops": [{"op": "eval", "code": "1"}],
        },
    ],
)
async def test_ac_45_unsafe_proposals_are_refused(repair_registry, proposal):
    async with repair_registry(FakeLlm(json.dumps(proposal))) as (
        registry,
        drift,
        store,
    ):
        drift.apply_mutation("T-MOVE")
        result = await registry.call(TOOL, ARGS)
        events = store.audit_events()
        assert drift.current_mutation == "T-MOVE"  # the admin reset was never reached
    assert result["reason"] == "UNSAFE_PATCH"
    assert [e.outcome.value for e in events] == ["ABORTED"]


@pytest.mark.asyncio
async def test_ac_45_model_is_never_asked_for_a_value_and_never_sees_one(
    repair_registry,
):
    llm = FakeLlm(GOOD)
    async with repair_registry(llm) as (registry, drift, _):
        drift.apply_mutation("M8")  # a new required value: tier 1 says NO_SAFE_VALUE
        refused = await registry.call(
            "users__create_ticket", {"user_id": "123", "title": "x"}
        )
        drift.apply_mutation("T-MOVE")
        await registry.call(TOOL, {"user_id": "456"})
    assert refused["error"] == "SCHEMA_DRIFT_UNRECOVERABLE"
    assert len(llm.prompts) == 1  # only the T-MOVE break reached the model
    assert "456" not in llm.prompts[0] and "body.user_id: str" in llm.prompts[0]


class SlowLlm(FakeLlm):
    async def __call__(self, system: str, user: str) -> tuple[str, int]:
        await asyncio.sleep(0.3)
        return await super().__call__(system, user)


@pytest.mark.asyncio
async def test_ac_43_repair_gets_its_own_budget_beyond_the_heal_deadline(
    repair_registry, monkeypatch
):
    from healer import heal
    from healer import registry as registry_module

    monkeypatch.setattr(heal, "HEAL_DEADLINE_S", 0.1)  # tier 1 would time out at 0.1 s
    monkeypatch.setattr(registry_module, "HEAL_DEADLINE_S", 0.1)
    async with repair_registry(SlowLlm(GOOD)) as (registry, drift, _):
        drift.apply_mutation("T-MOVE")
        result = await registry.call(TOOL, ARGS)
    assert result.get("id") == "123", result
