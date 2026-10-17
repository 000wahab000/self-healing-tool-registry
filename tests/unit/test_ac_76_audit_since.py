from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from dashboard.app import create_app
from dashboard.metrics_view import live_safety
from healer import canonical, metrics
from healer.models import AuditEvent, DecisionPath, ErrorClass, HealOutcome, Tier
from healer.store import Store


def event(ts_ms: int) -> AuditEvent:
    return AuditEvent(
        ts_ms=ts_ms,
        tool="get_user",
        fingerprint="fp",
        cls=ErrorClass.E2,
        raw_code="422",
        tier=Tier.T1,
        path=DecisionPath.diff,
        fix_id=None,
        outcome=HealOutcome.RECOVERED,
        reason=None,
        mttr_ms=1,
    )


def test_ac_76_audit_events_since_uses_ordered_event_ids(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "audit.db"))
    store.audit(event(1))
    first_id = store.audit_events_since(0)[0][0]
    store.audit(event(2))
    store.audit(event(3))
    assert [row.ts_ms for _, row in store.audit_events_since(first_id)] == [2, 3]
    second_id = store.audit_events_since(first_id)[0][0]
    store._db.execute("DELETE FROM heal_events WHERE event_id = ?", (second_id,))

    rows = store.audit_events_since(first_id)
    assert [event.ts_ms for _, event in rows] == [3]
    assert rows[0][0] > second_id
    assert store.audit_events_since(rows[0][0]) == []
    store.close()


@pytest.mark.asyncio
async def test_ac_76_dashboard_caches_incremental_audits_and_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(str(tmp_path / "dashboard.db"))
    dash = app.state.dash
    dash.store.audit(event(1))
    summaries = 0
    original_heal = dash._heal

    def summarize(audit_event: AuditEvent) -> dict:
        nonlocal summaries
        summaries += 1
        return original_heal(audit_event)

    monkeypatch.setattr(dash, "_heal", summarize)
    first = dash.state()
    assert len(first["heals"]) == 1
    assert summaries == 1
    calls = 0
    original = dash.store.audit_events_since

    def incremental(cursor: int) -> list[tuple[int, AuditEvent]]:
        nonlocal calls
        calls += 1
        return original(cursor)

    monkeypatch.setattr(dash.store, "audit_events_since", incremental)
    monkeypatch.setattr(dash.store, "audit_events", lambda: pytest.fail("full audit read"))
    assert dash.state() == first
    assert calls == 1
    assert summaries == 1

    await dash.reset()
    assert dash.state()["heals"] == []
    dash.store.audit(event(2))
    assert len(dash.state()["heals"]) == 1
    assert calls == 4
    assert summaries == 2
    await dash.aclose()


@pytest.mark.asyncio
async def test_ac_76_scripted_state_matches_legacy_render_and_live_reset_counts(
    tmp_path: Path,
) -> None:
    app = create_app(str(tmp_path / "scripted.db"))
    dash = app.state.dash
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://dash"
    ) as client:
        assert (await client.post("/api/start", json={"agent": "scripted", "step_delay": 0.1})).status_code == 200
        assert (await client.post("/api/mutation", json={"id": "M5"})).status_code == 200
        for _ in range(1000):
            response = await client.get("/api/state")
            current = response.json()
            if all(run["status"] == "done" for run in current["runs"].values()):
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("scripted run did not finish")

        audit = dash.store.audit_events()[dash.base_heal :]
        assert audit
        legacy = {
            "epoch": dash.epoch,
            "active_mutation": dash.mutation,
            "active_custom": dash.custom,
            "run_scenario": dash.run_scenario,
            "runs": dash.runs,
            "traces": {
                "healing": dash.traces["healing"],
                "baseline": [{**trace, "heal_event": None} for trace in dash.traces["baseline"]],
            },
            "events": dash.store.call_events(max(0, dash.base_event)),
            "patch_calls": [],
            "heals": [dash._heal(heal) for heal in audit],
            "metrics": {
                "mttr": {str(int(ts)): value for ts, value in metrics.mttr_summary(audit).items()},
                "outcomes": metrics.outcome_counts(audit),
                "impact": dash._impact(audit),
            },
            "mocks": {
                agent: {"mutation": mock.mutation, "data": mock.state()}
                for agent, mock in dash.mocks.items()
            },
        }
        assert canonical.dumps(current) == canonical.dumps(legacy)

        previous_audit = dash.store.audit_events()[dash.base_heal :]
        assert (await client.get("/api/metrics/live")).json() == live_safety(previous_audit)
        await client.post("/api/reset")
        assert dash.base_heal == len(dash.store.audit_events())
        assert (await client.get("/api/metrics/live")).json()["outcomes"]["RECOVERED"] == 0
        await client.post("/api/start", json={"agent": "scripted", "step_delay": 0})
        for _ in range(1000):
            await asyncio.sleep(0.01)
            if all(run["status"] == "done" for run in dash.runs.values()):
                break
        await client.post("/api/reset")
        assert dash.base_heal == len(dash.store.audit_events())
        assert (await client.get("/api/metrics/live")).json()["outcomes"]["RECOVERED"] == 0
    await dash.aclose()
