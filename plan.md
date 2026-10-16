# plan.md: Build Plan

> Ordered build plan. Inputs: `product.md` (what, FR/AC ids), `agent.md` (rules), `technical-approach.md` (design).
>
> **Status (2026-10-16):** phases 0 to 12 are built and collapsed below to their gate and status; the progress log is the record. The product is now an MCP gateway (phase 13+), built by two teams on four machines. Every phase ends with a gate. Before ticking any box run `pytest -q` and `ruff check .`.

---

## Phases 0 to 12: done

| Phase | Output | Gate | Status |
|---|---|---|---|
| 0 Scaffold | `pyproject.toml`, layout from `agent.md` §3, `.env.example`, `config/tools.json` skeleton, settings module (every threshold and timeout from `product.md`), smoke test | `pip install -e .[dev]`, `pytest -q` and `ruff check .` pass | done |
| 1 Core models, Op Interpreter, Safety Gate | `models.py`, `canonical.py`, `ops.py` (`move`, `cast`, `header`, `route`), operations JSON Schema, `safety.py`, unit tests (FR-9) | All unit tests pass; FR-9 fully covered | done |
| 2 OpenAPI Loader, Registry, REST Adapter, minimal mock | `openapi_loader.py`, `registry.py`, `adapters/rest.py`, argument pre-validation (FR-2.1), `config/tools.json` for the four tools, minimal mock with mutations as data | AC-1, AC-2 pass with no network | done |
| 3 Detector and contract checks | `detect.py` (classification order, violation extraction from `422`, `401`, `404`/`405`), `contract.py` (output schema, `echo` / `non_empty` postchecks), wired into `Registry.call` | AC-3 | done |
| 4 Fingerprint, Store, audit, caches | `fingerprint.py` (FR-4), `store.py` (SQLite WAL: `spec_snapshots`, `fixes`, `heal_events`, `call_events`; active-fix cache; negative cache with injected clock; synchronous audit; retirement at 2 losses), AC-5 schema check. Product spec v3 labels the persistent fixes (S6) and negative cache (S7) STRETCH; both are built. | AC-4; store unit tests | done |
| 5 Diagnoser and Candidate Builder | `diagnose.py` (spec fetch 0.5 s, snapshots, leaf flattening, diff signature, error-clue mode, `404` route check), `candidates.py` (FR-7.2 rules, cap 8, deterministic order, `NO_SAFE_VALUE`) | Per-mutation candidate tests (M1, M2, M3, M4, M5, M6, M7, M8, error-clue mode); same input gives same output | done |
| 6 Jev Client, Heal Controller, retry policy | `jev.py` (one Choice call, 1.5 s timeout; `POST /v1/systemone` on TypeSafe with `JEV_API_KEY`, or `https://openrouter.ai/api/v1/systemone` with model `~typesafe/jev-latest` and `OPENROUTER_API_KEY` as Jev-only fallback; exact fields to confirm against TypeSafe docs [A]), `heal.py` (FR-10, FR-11), `retry.py` (`E1`) | AC-7, AC-12, AC-13, AC-19, AC-20 and a deadline test (Jev mocked with respx) | done |
| 7 Core integration suite (milestone: healing core done) | Integration test per scenario through `Registry.call` (AC-6, AC-8, AC-9, AC-10, AC-11), complete AC-5, AC-1 check, final mock state checks, `metrics.py` | AC-1 to AC-13, AC-19, AC-20 pass in-process; tier-1 heals < 4 s locally | done |
| 8 Demo-grade mock API | Uvicorn mock, admin endpoints (activate, reset, `GET /admin/state`, list), `Idempotency-Key`, OAuth `401`, C1 and C2 behavior | Phase 7 suite passes over HTTP | done |
| 9 Agents | `agents/` shared prompt, LLM config (NVIDIA NIM `https://integrate.api.nvidia.com/v1`, `NVIDIA_API_KEY`, default `openai/gpt-oss-20b`, `LLM_MODEL` override, temperature 0), `healing_agent.py`, `baseline_agent.py` (cap 10), `scripted.py`, token accounting | Clean runs succeed for both agents; M5 contrast visible | done; the keyed E2E tests (clean run, M5 contrast, AC-9 at agent level) are unticked, skipped without keys |
| 10 Benchmark runner and report | `bench/run.py` (`python -m bench.run --agent scripted\|llm --n N`), clean runs, tier-0 runs, metrics, `results.jsonl`, `report.md` | AC-14 to AC-17; recorded run is scripted, N = 3, 2026-10-14 (`bench/report.md`) | done; token metrics need an LLM-mode run |
| 11 Dashboard and demo script (milestone: MVP demo-ready) | FastAPI dashboard with two panes, controls, patch log, metrics panel; scripted 30-second `demo.py` flow; two cold-start runs | AC-18 (manual). MVP frozen here. | done |
| 12 Spec v3 alignment | 12A tie-breaker, optional Jev, write-tool ambiguity (AC-7, AC-13, AC-27); 12B `E3` `UNSUPPORTED_CLASS`, value errors as `NOT_DRIFT`, API-rollback rule, replay rule, C3 (AC-20, AC-21, AC-25); 12C M9, raw-error sanitizer, `spec_mode`, `heal_ms` (AC-22, AC-23, AC-24); 12D v3 metrics, error-only ablation, regenerated report (AC-14 to AC-17, AC-23); 12E write-up (`writeup.md`) and pitch (`pitch.md`) | AC-7, AC-13, AC-15, AC-16, AC-17, AC-20 to AC-25, AC-27 pass; AC-14 and AC-18 re-checked; AC-1 to AC-6, AC-8 to AC-10, AC-11, AC-12, AC-19 still pass; `pytest -q` and `ruff check .` clean | done; open: re-run `dashboard/demo.py` twice from a cold start (also without Jev), AC-16 needs an LLM-mode benchmark run (T1-10) |

### Already built: STRETCH items S6 and S7

- **S6, persistent fix store.** `fixes` and `spec_snapshots` tables, reload of active fixes at startup, tier-0 reuse by fingerprint including after a restart, retirement at 2 losses. Tests: `test_ac_11_tier0_repeat_and_restart`, and in `tests/unit/test_store.py`: `test_fix_round_trip_survives_restart`, `test_one_active_fix_per_fingerprint`, `test_retired_at_two_losses_and_evicted`. The scripted benchmark in `bench/report.md` shows tier-0 MTTR mean / p50 / p95 of 4.7 / 4 / 8 ms (n = 15, scripted mode, N = 3).
- **S7, negative cache and single-flight.** `KNOWN_UNFIXABLE` for 60 s on a failed fingerprint; concurrent calls with the same fingerprint share one heal. Tests: `test_ac_12_negative_cache_known_unfixable`, `test_ac_19_single_flight_concurrency`, `test_negative_cache_expires_with_injected_clock`.

---

## Phase 13+: MCP gateway, two teams on four machines

**New direction (2026-10-16).** The product becomes a self-healing gateway for external MCP servers:

```
agent -> our MCP server (front door) -> Registry / Healer -> MCP client -> N upstream MCP servers
                                                          -> REST adapter -> OpenAPI APIs (as today)
```

- The gateway connects to the upstream MCP servers listed in `config/mcp_servers.json` (stdio or Streamable HTTP). It reads each server's `tools/list` and maps every tool's `inputSchema` to an `OperationSpec` (contract 1). It exposes them as namespaced tools `<server>__<tool>` with a frozen `agent_schema`.
- The agent only sees the frozen schema. When an upstream tool drifts (tool renamed, argument renamed or retyped, required argument added, enum changed), the call fails with a JSON-RPC error or a result with `isError: true`. The healer re-reads `tools/list` and diagnoses the change from the old and new schemas. It rewrites the call with deterministic `ops.py` operations, verifies the result, writes one audit row and stores the fix. A drift it cannot heal safely gets a structured refusal.
- REST through OpenAPI keeps working, so both protocols share one healing core.
- The demo runs fully against a local mock MCP server that can change its own tools on command. No public MCP server is a required dependency.

File ownership, branches, contracts and review rules: `AGENTS.md` ("Two teams, four machines"). Kickoff prompts: `team-prompts.md`. Every item starts with its FR and AC in `product.md` (`agent.md` invariant 10), one PR per item, with `pytest -q` and `ruff check .` clean.

| Machine | Team | Track | AC range | Branch prefix |
|---|---|---|---|---|
| **T1-PS1** | Team 1 (Wahab) | Healing core for MCP drift | AC-40 to AC-49 | `t1-ps1/` |
| **T1-PS2** | Team 1 (Wahab) | Mock drift server, fixtures, benchmark, evidence | AC-50 to AC-54 | `t1-ps2/` |
| **T2-PS1** | Team 2 (teammate) | MCP client, upstream loader, registry, front-door server | AC-30 to AC-39 (used by the old P1 work), then AC-63 to AC-69 | `t2-ps1/` |
| **T2-PS2** | Team 2 (teammate) | Spec watcher, demo agent, dashboard, docs, pitch | AC-55 to AC-59 | `t2-ps2/` |

### Step 0: land open branches and fix the shared interfaces (before the tracks)

- [x] Merge the clean open branches into `main`: `p4/p4-1-ac18-check`, `plan-hygiene` (P3-1 to P3-3), `p1/p1-1-mcp-stdio` (P1-1 to P1-3). Run `pytest -q` and `ruff check .` after each merge.
- [ ] Close `feat/updateUI` (stale, conflicts in `dashboard/index.html`). Delete the six already-merged remote branches.
- [x] T1-PS1 splits `origin/p2/p2-0-llm-benchmark` into one PR per item (item T1-0). The split PRs merge before T1-1.
- [x] Contract 7 (upstream tool mapping) and contract 8 (mock drift control) are written in `AGENTS.md`. Both teams confirm them on day one.

### Track T1-PS1: healing core for MCP drift (Team 1)

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| T1-0 | Land the old P2 branch | Split `origin/p2/p2-0-llm-benchmark` into one PR per item (S1, S8/M10, X3, S2, X2-E3, X4 precompute). Changes to `registry.py` and `dashboard/` go into separate PRs that the owning machine approves. Keep `Healer.precompute` guarded until T2-PS2's watcher exists. | Each split PR is green and merged; any claim without a test is listed in the PR |
| T1-1 | MCP failure classification | FR/AC first. `detect.py` maps an MCP outcome (JSON-RPC `-32602` invalid params, `-32601` unknown tool, `isError` result, transport error) to the existing `ErrorClass` set, from the `Outcome` that T2-PS1's adapter returns (contract 7). A business error from a tool stays a business error. | Each failure kind classifies correctly in unit tests; a business `isError` is never treated as drift |
| T1-2 | Schema-diff diagnosis | `diagnose.py` compares the frozen `OperationSpec` with the one from a fresh `tools/list`: tool renamed (same schema, new name), argument renamed, argument retyped, new required argument, enum value changed. Every candidate value comes from the agent's call or the new schema, never invented. | Each drift case yields the right candidates; an unexplained drift yields a refusal |
| T1-3 | MCP heal path | `heal.py` heals an MCP call through the existing pipeline: candidates, safety gate, one retry, verification, one audit row, fix stored in `FixStore` by fingerprint. Add ops only where `ops.py` lacks one (for example a tool-rename op that routes to the new upstream name). | M1 to M3 equivalents heal over MCP end to end against T1-PS2's mock; an M8-style unsafe drift refuses with a structured error |
| T1-4 | Precompute for MCP | `Healer.precompute(old, new)` accepts two `tools/list` snapshots, builds and dry-runs candidates, stores them as `candidate`, sends nothing | After the watcher reports a change, the first failing call heals at tier 0 |
| T1-5 | Deferred core items | S3 tier-2 repair agent and X5 Jev check without a spec, only if time is left; FR/AC first | Their own ACs |

### Track T1-PS2: mock drift server, benchmark and evidence (Team 1)

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| T1-6 (done) | Mock drift MCP server | FR/AC first. `mock_api/mcp_drift_server.py` on the official `mcp` SDK, stdio and Streamable HTTP. Its tools mirror the REST mock (`get_user`, `create_order` and the rest). A control interface (contract 8) applies and resets mutations: rename tool, rename argument, retype argument, add required argument, change enum, and an M8-style unsafe change. A second instance with a different tool set covers the "2+ servers" case. | Each mutation changes `tools/list` and makes the old call fail; reset restores the original |
| T1-7 | Drift fixtures | `mock_api/fixtures/mcp/`: recorded `tools/list` before and after each mutation, used by T1-PS1 and T2-PS1 unit tests without a running server | Fixture tests load every snapshot pair |
| T1-8 | Healthy-call overhead over MCP | Extend `bench/overhead.py`: time 200+ healthy calls through the gateway against the same calls sent straight upstream; report p50 and p95 | Numbers printed and recorded in `bench/report.md` |
| T1-9 | MCP drift benchmark | Add the MCP mutations to `bench/run.py` as scenarios beside the REST ones; same metrics (ZTAR, Safe-Refusal, False-Patch, MTTR) | `bench/report.md` has an MCP section from a scripted run |
| T1-10 | Real-LLM evidence (old P2-0) | Live runs on gpt-oss-20b (NVIDIA NIM), N = 10 per agent and scenario, REST and MCP, misses included; model and provider recorded | `report.md` regenerated from an LLM-mode run |

### Track T2-PS1: MCP client, loader and front door (Team 2)

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| T2-1 | Upstream MCP client adapter | FR/AC first. `src/healer/adapters/mcp_upstream.py`: one client session per upstream server (stdio or Streamable HTTP); call tools; return the same `Outcome` model as the REST adapter, keeping the JSON-RPC error code and the `isError` content for T1-PS1 (contract 7) | A call to each mock server returns a correct `Outcome` for success, `isError` and JSON-RPC errors |
| T2-2 | Upstream loader | `mcp_upstream_source(server)`: a `SpecSource` that reads `tools/list` and maps each `inputSchema` to an `OperationSpec` keyed `<server>__<tool>` | Mapping tests pass on every T1-7 fixture |
| T2-3 | Multi-server config | `config/mcp_servers.json`: name, transport, command or URL, and the *name* of the env var that holds a token. No secrets in the file. Loaded once at start-up. | Two mock servers load from config; a missing env var gives a clear start-up error |
| T2-4 | Registry dispatch | `registry.py` routes each tool to the REST or the MCP adapter by protocol; `tools()` stays frozen across upstream changes | REST and MCP tools appear in one `tools()` list and both call paths work |
| T2-5 | Front door over both transports | Extend `mcp_server.py` (old P1-1, P1-2): expose the merged registry over stdio and Streamable HTTP; never emit `tools/list_changed`; heal errors become `isError` results | An MCP client lists REST and MCP tools, and survives an upstream rename mid-session with no `list_changed` |
| T2-6 | Deferred protocols | GraphQL, gRPC, Postgres fix store, streaming: start only after T2-5, FR/AC first | Their own ACs |

### Track T2-PS2: watcher, demo, dashboard and docs (Team 2)

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| T2-7 (done) | Spec watcher | FR/AC first. `spec_watcher.py`: poll each `SpecSource` (OpenAPI and upstream MCP) on an interval, hash and snapshot changes, call `Healer.precompute(old, new)` once it exists (guarded until then); injected clock, bounded backoff, never blocks a call | A change is snapshotted within one interval; an unchanged spec causes no work |
| T2-8 | Demo agent | `demo/mcp_agent.py`: a LangGraph agent that connects only to our front door and uses tools from 2+ upstream mock servers in one task; a script triggers a mutation mid-task | The task finishes after a mid-task rename, with one heal event in the audit log |
| T2-9 | Dashboard MCP view | Show upstream servers, their tools, live MCP calls and heal events; buttons for the MCP mutations through contract 8 | Dashboard tests pass; new buttons covered by the button-coverage test |
| T2-10 (done) | Client guides | `docs/mcp-clients.md` from `tests/mcp/client-handoff.md`: Claude Desktop, Cursor, Windsurf, stdio and HTTP, plus how to add an upstream server | A fresh user connects a client by following the guide |
| T2-11 | README, pitch, writeup | Rewrite around the gateway story after T1-9; every number from `bench/report.md`; LangGraph migration (old P4-5) if still needed | Every number in the docs appears in `report.md` |

### Old items: kept, merged, dropped

| Old | Now |
|---|---|
| P1-1, P1-2, P1-3 | Land in step 0; remaining P1-2 work moves to T2-5 |
| P1-4 GraphQL, P1-5 gRPC, P1-6 Postgres, P1-8 streaming | Deferred to T2-6 |
| P1-7 upstream MCP healing | Becomes the main track: T2-1, T2-2, T1-1 to T1-3 |
| P2-0 benchmark | T1-10 |
| P2-1, P2-2, P2-3, P2-5, P2-6 | Land through T1-0 |
| P2-4 S3, P2-7 X5 | Deferred to T1-5 |
| P2-8 precompute | T1-4 (MCP snapshots added) |
| P3-1, P3-2, P3-3 | Land in step 0; P3-2 extended by T1-8 |
| P4-1 | Lands in step 0 |
| P4-2 watcher | T2-7 |
| P4-3 guides | T2-10 |
| P4-4 dashboard | T2-9 |
| P4-5 LangGraph, P4-6 docs | T2-11 |

### Hand-offs

- T1-6 and T1-7 come first on T1-PS2, because T1-PS1 and T2-PS1 test against the mock and the fixtures. Until they land, unit tests use hand-written `tools/list` dicts.
- T2-1 defines the MCP `Outcome` that T1-1 classifies (contract 7). Agree on its shape on day one.
- T1-3 needs T2-1, T2-2 and T1-6. T2-5 needs T2-4.
- T2-7 ships with the precompute hook guarded; T1-4 switches it on.
- T2-8 and T2-9 need T2-5 and T1-6. T2-11 needs T1-9 and T1-10.

---

## Progress log

| Date | Phase | Status | Notes |
|---|---|---|---|
| by 2026-10-14 | 0 | done | Scaffold; status recorded from the repo state, per-phase completion dates were not tracked |
| by 2026-10-14 | 1 | done | Core models, Op Interpreter, Safety Gate |
| by 2026-10-14 | 2 | done | OpenAPI Loader, Tool Registry, REST Adapter, minimal mock API |
| by 2026-10-14 | 3 | done | Detector and contract checks |
| by 2026-10-14 | 4 | done | Fingerprint, Store, audit, caches (S6 and S7 parts built here) |
| by 2026-10-14 | 5 | done | Diagnoser and Candidate Builder |
| by 2026-10-14 | 6 | done | Jev Client, Heal Controller, retry policy |
| by 2026-10-14 | 7 | done | Core integration suite (healing core milestone) |
| by 2026-10-14 | 8 | done | Demo-grade mock API with admin endpoints |
| by 2026-10-14 | 9 | done | LangGraph healing and baseline agents, plus the scripted no-LLM agent |
| 2026-10-13 | 10 | done | Benchmark runner; recorded run is scripted mode, N = 3 (`bench/report.md`) |
| by 2026-10-14 | 11 | done | Dashboard and terminal demo (MVP demo-ready) |
| 2026-10-14 | 12 | in progress | Spec v3 alignment; docs updated first, code and tests follow the checklist above |
| 2026-10-14 | 12D | done | v3 metrics (ZTAR/Safe-Refusal/False-Patch/MTTR+heal_ms/tokens) in `metrics.py` and `bench/run.py`, error-only ablation pass, report regenerated (scripted, N = 3); tests for AC-14 to AC-17 and AC-23; dashboard buttons cover all scenarios |
| 2026-10-14 | 12E | done | Dashboard Demo view (cofounder.co style): prompt + scenario or dashboard-only `CUSTOM` drift, side-by-side replay with step trackers, per-call input / wire / output, registry view, readable patch log with `heal_ms`; refused tools are skipped and the task continues (prompt and Demo run); `python-dotenv` declared |
| 2026-10-15 | 13 step 0 | done | Two-person tracks and ownership (`AGENTS.md`); `OperationSpec`, `SpecSource`, `FixStore` contracts with `tests/integration/test_contracts.py` |
| 2026-10-16 | 13 re-plan | done | Direction changed to an MCP gateway that heals upstream MCP servers; work split into two teams on four machines (T1-PS1, T1-PS2, T2-PS1, T2-PS2); old P1 to P4 items mapped to new ones |

From phase 13 on, each machine appends rows only to its own table below. Separate tables keep parallel PRs from conflicting on the last line of the file.

### Progress log: T1-PS1

| Date | Item | Status | Notes |
|---|---|---|---|
| 2026-10-16 | T1-0 (S1) | done | S1 sibling-tool candidate propagation (AC-40) |
| 2026-10-16 | T1-0 (S8/M10) | done | S8 injection resistance scenario (M10, AC-26) |
| 2026-10-16 | T1-0 (S2) | done | S2 rule mining with rules table (AC-44) |
| 2026-10-16 | T1-0 (X3) | done | X3 new operations enum_map and encoding (AC-41, AC-42) |
| 2026-10-16 | T1-0 (X4) | done | X4 fix precompute contract (AC-47, guarded) |
| 2026-10-16 | T1-1 to T1-4 | done | MCP outcomes classified in the adapter (FR-24.2), tool-rename diagnosis (`diagnose.renamed_op`), MCP heal path and MCP precompute (AC-64, AC-65) |
| 2026-10-16 | T1-5 (S3) | done | Tier-2 repair agent `src/healer/repair.py` (FR-17.12 to 17.14, AC-43, AC-45). Mock mutation T-MOVE added. Live check on gpt-oss-20b: T-MOVE healed 6 of 6 runs, M8 refused 2 of 2 without a model call (one manual run, not a benchmark) |

### Progress log: T1-PS2

| Date | Item | Status | Notes |
|---|---|---|---|
| 2026-10-15 | P3-2 | done | Healthy-call overhead (AC-28, FR-21.1): `bench/overhead.py` and `tests/p3/test_ac_28_healthy_overhead.py`; local run adds 0.3 ms p95 over the raw transport (n = 250 per side), under the 10 ms budget |
| 2026-10-15 | P3-3 | done | Swagger 2.0 loader (F22, AC-60 to AC-62): `src/healer/swagger2.py` (`convert` + `swagger2_source`), `mock_api/fixtures/swagger2.json`, `tests/p3/`; the 2.0 fixture converts to the mock's OpenAPI 3 `operations()` exactly (5 ops) and M1 heals when the base spec loads through `swagger2_source` |
| 2026-10-16 | T1-6 | done | Mock drift MCP server (AC-50, AC-51, Contract 8): `mock_api/mcp_drift_server.py` on low-level MCP SDK Server, stdio and Streamable HTTP, users and tickets profiles, mutations M1, M2, T-RENAME, T-REQUIRED, T-ENUM, M8, Python and __admin_* MCP controls; in-process tests in `tests/t1ps2/` |

### Progress log: T2-PS1

| Date | Item | Status | Notes |
|---|---|---|---|
| 2026-10-15 | P1-1 | implemented; packaging hand-off pending | Official MCP 2.x low-level stdio interface, frozen schemas, structured refusals, no list-change notifications; SDK memory and actual stdio subprocess tests, custom-spec healing and secret-leak regressions in `tests/mcp/`. Launch with `python -m healer.mcp_server`; P2 request: add `[project.scripts] healer-mcp = "healer.mcp_server:main"`. No P2-owned packaging edit made. |
| 2026-10-15 | P1-2 | done | Stateful Streamable HTTP shares one registry; loopback default, optional environment-selected bearer authentication on every method, explicit remote host allowlist and exact origins. SDK clients exercise the ASGI HTTP path without sockets, M1/M8 parity and five overlapping sessions producing one heal. `pytest -q`: 584 passed, 5 skipped; `ruff check .` clean. Remote deployment needs a trusted TLS reverse proxy. |
| 2026-10-16 | P1-3 | hand-off prepared; live acceptance pending | Client-specific stdio/HTTP snippets for P4 are in `tests/mcp/client-handoff.md`; existing opt-in config launcher is in `tests/mcp/test_client_config.py`. Final helper suppresses SDK diagnostic logs and discards child stderr to avoid secret leakage. Static review and lint only after user requested no further tests; final helper runtime validation, live configuration checks and P4 client UI checks remain pending. P2 console-entry request remains unchanged. |
| 2026-10-16 | T2-1 to T2-5 | done | Upstream MCP adapter, loader, `config/mcp_servers.json`, registry `MCP` dispatch, `gateway.Gateway` and `mcp_server --mcp-servers` (FR-24, AC-63 to AC-66). Built by Wahab's session with T2-PS1 paused |

### Progress log: T2-PS2

| Date | Item | Status | Notes |
|---|---|---|---|
| 2026-10-16 | T2-7 | done | Spec watcher (FR-18, AC-55): polls a `SpecSource` list on an interval, saves hash changes to `FixStore.save_spec`, calls `Healer.precompute(old, new)` only when the healer provides it (contract 5), injected clock/sleep, bounded per-source backoff, runs as a background task; tests in `tests/t2ps2/` |
| 2026-10-16 | Dashboard screenshot fixes | done | FR-20.1/20.2, AC-56: scoped one-tool LLM steps, truthful cap/correctness badges, preset stats and readable email; browser-checked at desktop and mobile widths |
| 2026-10-16 | Live LLM call details | done | FR-20.3, AC-57: live LLM calls use the existing trace recorder and expandable call cards; offline fake-LLM API and browser check |
| 2026-10-16 | T2-10 | done | Client guides (FR-19, AC-58): `docs/mcp-clients.md` derived from `tests/mcp/client-handoff.md` covers Claude Desktop, Cursor and Windsurf (stdio + Streamable HTTP), the install/launch commands, upstream-server addition and token handling; every JSON snippet parses, every stdio snippet launches `-m healer.mcp_server`, every documented flag is accepted by the server, no token value; `tests/t2ps2/test_ac_58_mcp_client_docs.py`. Real-client UI checks remain outstanding |
| 2026-10-15 | P4-1 | done | AC-18 browser check: one-click mutation triggers verified (M5, M3, M8), live dual-pane updates confirmed, heal events logged in <1 s (M5 heal_ms=71ms/13ms, M3 heal_ms=13ms/7ms, M8 clean refusal ABORTED/NO_SAFE_VALUE in 12ms/34ms); two cold-start demo rehearsals passed cleanly (default config & without Jev) |
