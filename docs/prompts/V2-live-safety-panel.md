# V2: Live safety and timing panel (this session's heals)

**Depends on V0 and V1** (V1 creates `metrics_view.py`; you add one function to it).

## Why

V1 shows the offline benchmark. This panel shows **the live demo session**: how fast each heal was and which calls were refused instead of patched. `state()` already returns `metrics.mttr` (per tier) and `metrics.outcomes`, but the UI (`renderMetrics` in `index.html`, around line 1384) shows only part of it. The audit rows also carry `heal_ms`, `tier`, `reason`, `jev_tokens` and `llm_tokens`, and `metrics.timing_summary()` and `percentiles()` exist but are unused in the dashboard.

## Owns

- `dashboard/metrics_view.py`: add `live_safety(audit: list[AuditEvent]) -> dict` (pure)
- `dashboard/app.py`: one route `GET /api/metrics/live`
- `dashboard/panels/live_safety.js` (new)
- `dashboard/index.html`: one `<script>` tag + one offline-stub entry
- `tests/dashboard/test_ac_79_live_safety.py` (new)
- `product.md`: one AC row

Do **not** edit `renderMetrics` or the existing `state()` payload.

## Build

`live_safety(audit)` returns:
```json
{
  "by_tier": {"0": {"n": 0, "mttr_ms": {"mean": 0, "p50": 0, "p95": 0}, "heal_ms": {...}}, "1": {...}},
  "outcomes": {"RECOVERED": 0, "REFUSED": 0, ...},
  "refusals": [{"tool": "...", "reason": "NO_SAFE_VALUE", "ts_ms": 0}],
  "tokens": {"jev": 0, "llm": 0}
}
```
Use `metrics.timing_summary` and `metrics.outcome_counts`. Do not reimplement percentiles. The route reads the same session slice the dashboard uses (`audit_events()[base_heal:]`, or F7's incremental cache if F7 has merged).

Panel:
- A tier table: Tier 0 (cached fix) and Tier 1 (diagnosed), with n, MTTR p50/p95 and heal_ms p50/p95.
- An outcome bar: recovered vs refused vs failed.
- A refusal list: the last 10 refused heals with their reason. Label them "refused safely: no value invented".
- Do not show a target such as "< 4 s" as a pass/fail badge unless the number comes from these rows.

## Tests (`test_ac_79_*`)

- `live_safety([])` returns zeros and empty lists, with no exceptions.
- Feed hand-built `AuditEvent`s (2 tier-0, 1 tier-1, 1 refused). Check n, p50 and the refusal entry.
- The route returns 200 after a scripted run in the existing dashboard test harness.

## Done when

During a live demo, every heal's tier, time and outcome (including refusals) is visible in one card.
