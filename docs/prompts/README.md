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

---

# ZTAR series (Z0-Z15)

Give an agent **`_PREAMBLE.md`, then `_ZTAR_RULES.md`, then exactly one Z task file**.

Skipped as already on `main`: Phase 0 audit (its result is the status table in `_ZTAR_RULES.md`), Phase 1 oracle (`bench/oracle.py`, mock request log, `expected_canonical`), the core of Phase 2 (`verify.py`, the `layers` audit field, W1/U1/D1), and L4 echo (working).

| ID | Title | Owns (may edit) | Depends on | AC |
|---|---|---|---|---|
| Z0 | Split `verify.py` into one module per layer | `src/healer/layers/` (new), `verify.py` | none | AC-83 |
| Z1 | L1: enum targets checked against the current spec | `layers/l1_provenance.py` | Z0 | AC-84 |
| Z2 | L2: unknown headers; MCP/GraphQL/gRPC requests | `layers/l2_request.py` | Z0 | AC-85 |
| Z3 | L3: E5 move/unwrap only; response-source provenance | `layers/l3_output.py` | Z0 | AC-86 |
| Z4 | L5: read-back for `set_manager` and `create_ticket` | `layers/l5_readback.py`, `config/tools.json` (readback), mock W1 variants | Z0 | AC-87 |
| Z5 | L6: U1 wrong units through the frozen registry | `layers/l6_invariants.py`, `config/tools.json` (invariants) | Z0 | AC-88 |
| Z6 | L7: MCP replay guard | `layers/l7_replay.py` | Z0 | AC-89 |
| Z7 | One mutation catalog; honest denominator | `mock_api/catalog.py` (new), constants in bench/mock | none | AC-90 |
| Z8 | Evidence ranking; refuse on a tie | `candidates.py` | none | AC-91 |
| Z9 | Verify-before-commit proof matrix (tests only) | `tests/integration/test_ac_92_*` | best after Z1-Z6 | AC-92 |
| Z10 | Seeded fuzz generator | `bench/fuzz.py` (new), mock hook | Z7 | AC-93 |
| Z11 | Fault-injection matrix; `Retry-After` date | `detect.py` | none | AC-94 |
| Z12 | Wilson CIs; N=30 | `metrics.py`, `bench/run.py` `--n` | none (Z7 optional) | AC-95 |
| Z13 | `INTERNAL_ERROR` typing; bounded `_first_seen` | `heal.py` (two spots), `models.py` | none | AC-96 |
| Z14 | Cyclic `$ref`, MCP pagination, retry jitter | `openapi_loader.py`, `mcp_upstream.py`, retry tests | none | AC-97 |
| Z15 | Report: layers, CIs, fuzz | `bench/run.py` report functions, `bench/report.md` | Z7, Z9, Z10, Z12 | AC-98 |

## ZTAR lanes

- Lane H: Z0, then Z1, Z2, Z3, Z4, Z5 and Z6 in parallel (each owns one layer file; Z4 and Z5 both touch `config/tools.json` in different keys, so the second rebases)
- Lane I: Z7, then Z10
- Lane J: Z8 · Lane K: Z11 · Lane L: Z12 · Lane M: Z13 · Lane N: Z14 (all independent)
- Last: Z9 (after the layer tasks), then Z15

Conflict watch: `mock_api/app.py` (Z4, Z5, Z7, Z10) and `bench/run.py` (Z7, Z12, Z15). Merge those in lane order and rebase each before its PR.

## Room for later (ZTAR)

- New layer = one file in `src/healer/layers/` + one `ORDERED` entry.
- New mutation = one `mock_api/catalog.py` row + `expected_canonical`.
- New fuzz primitive = one class in `bench/fuzz.py` with spec, request and canonical transforms.

---

# Start here for ZTAR: `ZTAR_MINIMUM.md`

`main` is red (3 failing tests; all MCP heals abort). Run **G1, G2 and G3** first, then follow `ZTAR_MINIMUM.md`, which picks a cut-down scope from each Z prompt.

| ID | Title | Owns | Fixes |
|---|---|---|---|
| G1 | MCP heals abort with UNSAFE_PATCH | `verify.py` / `safety.py` | `test_ac_54_mcp_scenarios` |
| G2 | W1 never triggers a heal | `mock_api/app.py` W1 branch | `test_w1_registry_audits_unsaved_success_at_readback` |
| G3 | D1 503 after a saved write is retried | `retry.py` | `test_d1_registry_does_not_replay_saved_ticket_after_503` |
