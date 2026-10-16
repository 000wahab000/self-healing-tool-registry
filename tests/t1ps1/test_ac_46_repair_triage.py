"""AC-46: Jev triages a tier-1 refusal: repair it, or send the error straight to the agent."""

from __future__ import annotations

import json

import pytest

from healer.heal import REPAIRABLE, TRIAGE_QUESTION, _Heal
from healer.jev import JevChoice, JevUnavailable
from healer.models import ErrorClass, Outcome, Reason, Tier

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


class FakeLlm:
    def __init__(self, answer: str) -> None:
        self.answer, self.calls = answer, 0

    async def __call__(self, system: str, user: str) -> tuple[str, int]:
        self.calls += 1
        return self.answer, 10


class FakeJev:
    """Answers only the triage question; records what it was shown."""

    def __init__(
        self, index: int = 0, confidence: float = 0.9, down: bool = False
    ) -> None:
        self.index, self.confidence, self.down = index, confidence, down
        self.states: list[str] = []

    async def choose(self, state: str, question: str, options: list[str]) -> JevChoice:
        assert question == TRIAGE_QUESTION and len(options) == 2
        self.states.append(state)
        if self.down:
            raise JevUnavailable
        return JevChoice(self.index, self.confidence, 7)


@pytest.mark.asyncio
async def test_ac_46_jev_says_repair_and_the_agent_heals(repair_registry):
    jev, llm = FakeJev(), FakeLlm(GOOD)
    async with repair_registry(llm, jev) as (registry, drift, store):
        drift.apply_mutation("T-MOVE")
        result = await registry.call(TOOL, ARGS)
        events = store.audit_events()
    assert result["id"] == "123"
    assert len(jev.states) == 1 and llm.calls == 1
    assert "123" not in jev.states[0] and "NO_CANDIDATE" in jev.states[0]
    (event,) = events
    assert (event.outcome.value, event.tier, event.path.value) == (
        "RECOVERED",
        2,
        "repair",
    )
    assert event.jev_tokens == 7 and event.llm_tokens == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "jev",
    [
        FakeJev(index=1),  # "report": the error goes to the agent
        FakeJev(down=True),  # no judge, no repair
        FakeJev(confidence=0.3),  # below the read threshold
    ],
)
async def test_ac_46_jev_report_unavailable_or_unsure_sends_the_error(
    repair_registry, jev
):
    llm = FakeLlm(GOOD)
    async with repair_registry(llm, jev) as (registry, drift, store):
        drift.apply_mutation("T-MOVE")
        result = await registry.call(TOOL, ARGS)
        events = store.audit_events()
    assert (
        result["error"] == "SCHEMA_DRIFT_UNRECOVERABLE"
        and result["reason"] == "NO_CANDIDATE"
    )
    assert llm.calls == 0
    assert [e.outcome.value for e in events] == ["ABORTED"]


@pytest.mark.asyncio
async def test_ac_46_missing_value_is_never_triaged_or_repaired(repair_registry):
    jev, llm = FakeJev(), FakeLlm(GOOD)
    async with repair_registry(llm, jev) as (registry, drift, _):
        drift.apply_mutation("M8")
        result = await registry.call(
            "users__create_ticket", {"user_id": "123", "title": "x"}
        )
    assert result["reason"] == "NO_SAFE_VALUE"
    assert jev.states == [] and llm.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "write", "transient", "expected"),
    [
        (Reason.NO_CANDIDATE, False, False, True),
        (Reason.LOW_CONFIDENCE, False, False, True),
        (Reason.UNSAFE_PATCH, False, False, True),
        (Reason.VERIFY_FAILED, False, False, True),
        (Reason.VERIFY_FAILED, True, False, False),  # the replay may have written
        (Reason.VERIFY_FAILED, False, True, False),  # transient: says nothing
        (Reason.NO_SAFE_VALUE, False, False, False),  # would need an invented value
        (Reason.NOT_DRIFT, False, False, False),
        (Reason.KNOWN_UNFIXABLE, False, False, False),
        (Reason.POSTCHECK_FAILED_AFTER_WRITE, True, False, False),
    ],
)
async def test_ac_46_only_repairable_refusals_reach_jev(
    repair_registry, reason, write, transient, expected
):
    jev = FakeJev()
    async with repair_registry(FakeLlm(GOOD), jev) as (registry, _, _):
        tool = registry.defs[TOOL]
        tool.config = {**tool.config, "write": write}
        h = _Heal(
            tool,
            registry.base_doc(tool, ARGS),
            Outcome(ErrorClass.E2, "mcp", "isError"),
            0,
            0,
        )
        h.ops = (await registry.spec_source()).ops
        h.tier, h.transient = Tier.T1, transient
        allowed = await registry.healer._triage(h, reason)
    assert allowed is expected
    assert (len(jev.states) == 1) is expected
    assert (reason in REPAIRABLE) or not expected
