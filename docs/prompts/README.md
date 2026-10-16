# Work prompts

Self-contained task prompts for smaller coding agents (Gemini in Antigravity, opencode MiMo, etc.).
Give an agent **`_PREAMBLE.md` followed by exactly one task file**. One task = one branch = one PR.

## Tasks

| ID | Title | Owns (may edit) | Depends on | AC |
|---|---|---|---|---|
| F1 | Reject off-host spec paths | `src/healer/spec_paths.py` (new), loaders' `operations()` call sites | none | AC-70 |
| F2 | Dashboard auth module + write-route guard | `dashboard/auth.py` (new), `dashboard/app.py` route decorators | none | AC-71 |
| F3 | Connections uses the shared auth module | `dashboard/connections.py` | F2 | AC-72 |
| F4 | Redact upstream tokens in the audit log | `src/healer/gateway.py`, `src/healer/registry.py` (cfg plumbing only) | none | AC-73 |
| F5 | Zero-call explorer run is not "correct" | `dashboard/explorer.py` (`check_data_correctness` only) | none | AC-74 |
| F6 | Mark the Postgres store unsupported | `src/healer/store_pg.py`, `tests/store_pg/` | none (do before F7) | AC-75 |
| F7 | Incremental audit reads for state polls | `src/healer/store.py`, `src/healer/store_pg.py`, `dashboard/app.py` `state()` | F6 | AC-76 |
| F8 | Stop tracking generated graph history | `.gitignore`, `graphify-out/` index only | none | none (no code) |
| V0 | Dashboard panel slot | `dashboard/panels/` (new), small hook in `dashboard/index.html` | none | AC-77 |
| V1 | Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, tokens) | `dashboard/panels/scorecard.js`, `dashboard/metrics_view.py` (new) | V0 | AC-78 |
| V2 | Live safety and timing panel (tier p50/p95, heal_ms, refusals) | `dashboard/panels/live_safety.js`, `dashboard/metrics_view.py` (add a function) | V0, V1 | AC-79 |
| V3 | Fix lifecycle panel (candidates, rules, spec snapshots, precompute) | `dashboard/panels/lifecycle.js`, `dashboard/metrics_view.py` (add a function) | V0, V1 | AC-80 |

## Parallel lanes (no shared files)

- Lane A: F1
- Lane B: F2, then F3
- Lane C: F4
- Lane D: F5
- Lane E: F6, then F7
- Lane F: F8 (any time; merge it alone)
- Lane G: V0, then V1, then V2 and V3 in either order (each adds its own function to `metrics_view.py`, so the second one rebases)

F7 and V2 both read `state()` data. F7 changes only how `state()` reads the audit rows, not what it returns, so they do not conflict.

## Room for future modules

- New spec loaders (gRPC, GraphQL, anything later) call `spec_paths.check_path()` from F1. Nothing else changes.
- New dashboard write routes add `Depends(require_write)` from F2's `dashboard/auth.py`.
- New panels drop a file in `dashboard/panels/` and register with V0's `registerPanel()`. No edit to existing panels.
- New metrics go in `dashboard/metrics_view.py` as one pure function each, plus one route.
- New `FixStore` backends implement the methods F7 adds (contract 3).
