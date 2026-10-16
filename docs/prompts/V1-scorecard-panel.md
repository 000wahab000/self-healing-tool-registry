# V1: Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, Token Overhead)

**Depends on V0.**

## Why

The problem statement judges on three metrics: Zero-Touch Adaptation Rate, MTTR and Token Overhead against a baseline. The safety story rests on False-Patch Rate 0 and Safe-Refusal. All of these are computed by `src/healer/metrics.py` (`ztar`, `false_patch_rate`, `safe_refusal`, `token_overhead`, `token_summary`) and written to `bench/report.md`, but the dashboard only shows the report as raw `<pre>` text. A judge watching the demo never sees the headline numbers.

## Owns

- `dashboard/metrics_view.py` (new): pure functions, no FastAPI imports
- `dashboard/app.py`: one route `GET /api/metrics/scorecard`
- `dashboard/panels/scorecard.js` (new)
- `dashboard/index.html`: one `<script>` tag; one stub entry in the offline demo for this endpoint
- `tests/dashboard/test_ac_78_scorecard.py` (new)
- `product.md`: one AC row

## Data source

Read what the benchmark already measured. **Never recompute or invent numbers** (the AGENTS.md claims rule).
- Find where `bench/run.py` keeps per-run rows (`RunRow`). Look in `bench/results*` (gitignored) for a JSON or JSONL artefact. If a machine-readable artefact exists, load it and call the `metrics.py` functions on it.
- If only `bench/report.md` exists, parse its markdown tables (sections "ZTAR", "Safe-Refusal Rate and False-Patch Rate", "Baseline outcomes", "Tokens") with a small, tolerant table parser.
- Either way, include `source` (file path) and `generated_at` (file mtime) in the response.
- No data: return `{"available": false, "hint": "python -m bench.run --agent scripted --n 3"}`.

## Response shape

```json
{
  "available": true, "source": "...", "generated_at": "...",
  "ztar": {"healing": {"adapted": 0, "runs": 0}, "baseline": {...}},
  "false_patch": {"false_patches": 0, "healed": 0},
  "safe_refusal": {"refused": 0, "runs": 0},
  "per_scenario": [{"scenario": "M1", "healing": "3/3", "baseline": "0/3", "baseline_failure": "hit cap 3/3", "refusal_reason": null}],
  "tokens": [{"scenario": "M1", "healing_overhead": 0, "baseline_wasted": 0}]
}
```

## Panel

- Top row: four stat tiles: ZTAR healing vs baseline, False-Patch Rate (show "0 / N healed" and make it visibly green only when 0), Safe-Refusal, and the token-overhead median.
- Below: a compact per-scenario table (M1-M9, C1-C3): healing ✓/✗, baseline ✓/✗ with failure mode, refusal reason.
- Footer: source, timestamp, "measured by bench/run.py".
- Use existing theme tokens only.

## Tests (`test_ac_78_*`)

- With the committed `bench/report.md`, the route returns `available: true` and the values match the report text (assert a few cells, such as M1 healing 3/3 and baseline 0/3).
- With the report path monkeypatched to missing: `available: false`.
- `metrics_view` functions are pure (call them directly on fixture text).

## Done when

The headline metrics are visible on the dashboard, sourced only from measured benchmark output.
