"""AC-78: Benchmark scorecard panel metrics and endpoint."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from dashboard.app import create_app
from dashboard.metrics_view import parse_report_markdown, scorecard

ROOT = Path(__file__).parents[2]

FIXTURE_REPORT = """# Benchmark report

## Per scenario

| Scenario | Healing ZTAR | Healing expected outcome | Baseline ZTAR | Baseline expected outcome | Baseline failure mode | Heal path | Refusal reasons | MTTR tier 1 | MTTR tier 0 | heal_ms tier 1 | heal_ms tier 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CLEAN | n/a | 100% (3/3) | n/a | 100% (3/3) | - | - | - | - | - | - | - |
| M1 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 29/30/32 (n=3) | 4/4/5 (n=3) | 29/30/32 (n=3) | 4/4/5 (n=3) |
| M8 | n/a | 100% (3/3) | n/a | 0% (0/3) | hit cap 3/3 | - | NO_SAFE_VALUE x3 | - | - | - | - |

## ZTAR (FR-15.4, AC-15)

- Healable mutations (M1, M2, M3, M4, M5, M7, M9), healing: 100% (21/21); baseline: 14% (3/21)

## Safe-Refusal Rate and False-Patch Rate (FR-15.4, AC-15)

- Safe-Refusal Rate: 100% (6/6) over M6-N, M8 runs, and no request carrying an invented value was sent in any of them.
- False-Patch Rate: 0% (0/24) of the healed runs ended with a wrong final mock state.

## Tokens (FR-8.7, FR-15.4, FR-15.5, AC-16)

| Scenario | Healing llm_tokens | Baseline llm_tokens | jev_tokens | Healing overhead | Baseline wasted | Ratio (healing : baseline) |
|---|---|---|---|---|---|---|
| CLEAN | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | - | - | - |
| M1 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
"""


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ("JEV_API_KEY", "OPENROUTER_API_KEY", "NVIDIA_API_KEY", "DB_PATH"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "dash.db"))


@pytest.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dash") as c:
        yield c
    await app.state.dash.aclose()


async def test_ac_78_scorecard_endpoint_with_committed_report(client):
    res = await client.get("/api/metrics/scorecard")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True
    assert "bench" in data["source"]
    assert "generated_at" in data

    # Assert ZTAR
    assert data["ztar"]["healing"]["adapted"] == 21
    assert data["ztar"]["healing"]["runs"] == 21
    assert data["ztar"]["baseline"]["adapted"] == 3
    assert data["ztar"]["baseline"]["runs"] == 21

    # Assert safety rates
    assert data["false_patch"]["false_patches"] == 0
    assert data["false_patch"]["healed"] == 24
    assert data["safe_refusal"]["refused"] == 6
    assert data["safe_refusal"]["runs"] == 6

    # Assert per-scenario cells match report
    m1 = next(s for s in data["per_scenario"] if s["scenario"] == "M1")
    assert m1["healing"] == "3/3"
    assert m1["baseline"] == "0/3"
    assert m1["baseline_failure"] == "hit cap 3/3"
    assert m1["refusal_reason"] is None

    m8 = next(s for s in data["per_scenario"] if s["scenario"] == "M8")
    assert m8["refusal_reason"] == "NO_SAFE_VALUE x3"

    # Assert tokens list
    m1_tokens = next(t for t in data["tokens"] if t["scenario"] == "M1")
    assert m1_tokens["healing_overhead"] == 0
    assert m1_tokens["baseline_wasted"] == 0


async def test_ac_78_scorecard_endpoint_when_report_missing(monkeypatch, client):
    import dashboard.metrics_view as mv

    monkeypatch.setattr(mv, "ROOT", Path("/nonexistent/directory"))

    res = await client.get("/api/metrics/scorecard")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is False
    assert "hint" in data


def test_ac_78_metrics_view_pure_function_on_fixture_text():
    parsed = parse_report_markdown(FIXTURE_REPORT)
    assert parsed["ztar"]["healing"]["adapted"] == 21
    assert parsed["ztar"]["baseline"]["adapted"] == 3
    assert parsed["false_patch"]["false_patches"] == 0
    assert parsed["false_patch"]["healed"] == 24
    assert parsed["safe_refusal"]["refused"] == 6
    assert len(parsed["per_scenario"]) == 2
    assert parsed["per_scenario"][0]["scenario"] == "M1"
    assert parsed["per_scenario"][0]["healing"] == "3/3"
    assert parsed["per_scenario"][0]["baseline"] == "0/3"
    assert parsed["per_scenario"][1]["scenario"] == "M8"
    assert parsed["per_scenario"][1]["refusal_reason"] == "NO_SAFE_VALUE x3"
    assert len(parsed["tokens"]) == 1
    assert parsed["tokens"][0]["scenario"] == "M1"


def test_ac_78_scorecard_function_pure(tmp_path):
    report_file = tmp_path / "report.md"
    report_file.write_text(FIXTURE_REPORT, encoding="utf-8")
    data = scorecard(report_file)
    assert data["available"] is True
    assert data["ztar"]["healing"]["adapted"] == 21


async def test_ac_78_scorecard_panel_script_served(client):
    res = await client.get("/panels/scorecard.js")
    assert res.status_code == 200
    assert "javascript" in res.headers["content-type"].lower()
    assert "HealerPanels.register" in res.text
    assert '"scorecard"' in res.text
