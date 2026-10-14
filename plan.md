# plan.md: Build Plan

> Ordered build plan for PS 01. Inputs: `product.md` (what, FR/AC ids) and `agent.md` (rules). Design details: `technical-approach.md`.
>
> **Order principle:** build the self-healing tool registry first and prove it through integration tests (phases 0–7). Then build the parts around it: the demo mock API, agents, benchmark and dashboard (phases 8–11). STRETCH work comes last (phase 12+).
>
> Work one phase at a time. Every phase ends with a gate; do not start the next phase until it passes. Before ticking any box, run `pytest -q` and `ruff check .`.

---

## Phase 0: Scaffold

**Goal:** an empty project that installs, lints and runs tests.

- [ ] `pyproject.toml`:
  - runtime dependencies: fastapi, uvicorn, pydantic v2, httpx, jsonschema,
  - dev dependencies: pytest, pytest-asyncio, respx, ruff.
- [ ] The directory layout from `agent.md` §3 (empty modules with docstrings).
- [ ] `.env.example` listing `JEV_API_KEY`, `LLM_API_KEY`, `LLM_MODEL`, `OAUTH_BEARER`, `TENANT_ID`, `MOCK_API_URL`, `DB_PATH`.
- [ ] `config/tools.json` skeleton containing `header_sources` (`Authorization` → `OAUTH_BEARER`, `X-Tenant-Id` → `TENANT_ID`) and an empty `tools` object.
- [ ] A settings module with every threshold and timeout from `product.md`:
  - heal deadline 3.5 s,
  - Jev timeout 1.5 s,
  - spec fetch timeout 0.5 s,
  - request timeout 2.0 s, replay ≤ 1.0 s,
  - `E1` retries 3, backoff 100/200/400 ms,
  - negative-cache TTL 60 s,
  - retire a fix at 2 losses,
  - Jev thresholds 0.5 (read) / 0.9 (write),
  - max 8 candidates,
  - operation cap 3× violations.
- [ ] One smoke test.

**Gate:** `pip install -e .[dev]`, `pytest -q` and `ruff check .` all pass.

---

## Phase 1: Core models, Op Interpreter, Safety Gate

**Goal:** the pure, deterministic building blocks. No I/O.

- [ ] `models.py`:
  - enums: `ErrorClass` (`OK`, `BUSINESS`, `E1`–`E6`), `Reason` (all codes in `product.md` §8), `Outcome` code (`RECOVERED`, `ABORTED`, `VERIFY_FAILED`, `NOT_DRIFT`), `Tier`, `Side`, `OpName`, `PostcheckType`,
  - records: `Violation`, `Outcome`, `Op`, `Fix`, `AuditEvent`.
- [ ] `canonical.py`: canonical JSON, sha256, and path helpers (get, pop, put) on documents.
- [ ] `ops.py`: implements `move`, `cast`, `header`, `route`. Pure: returns a new document. Rejects unknown operations.
- [ ] Operations JSON Schema, used to validate any externally produced operation list (Jev never produces one, but tier 2 will).
- [ ] `safety.py`: provenance, lossless cast, operation cap, replay rule, and per-tool Jev threshold check (FR-9.1–9.5).
- [ ] Unit tests:
  - every operation (apply, invalid path, unknown operation),
  - lossless cast table (`"123"` passes; `"0123"`, `"12a"` and `"1.5"` fail for int),
  - each safety rejection, mapped to its reason code.

**Gate:** all unit tests pass. FR-9 is fully covered.

---

## Phase 2: OpenAPI Loader, Tool Registry, REST Adapter, minimal mock API

**Goal:** an agent-facing tool can call a real (in-process) API through the registry.

- [ ] `mock_api/` **minimal**: a FastAPI app with only what tests need.
  - The four operations `get_user`, `update_email`, `set_manager`, `create_ticket`, with in-memory data containing users 123 and 456.
  - Strict Pydantic types. Unknown body fields are ignored.
  - Mutations as data (M1–M8, C1–C2). Each mutation is a set of changes to models, routes or behavior, so `/openapi.json` reflects the active one.
  - A test-only helper to switch mutations in-process. (The HTTP admin endpoints come in phase 8.)
- [ ] `openapi_loader.py`: fetch the spec, resolve `$ref`s into a self-contained schema per operation, canonicalize, hash.
- [ ] `registry.py`:
  - `ToolDefinition` (`agent_schema` frozen, `wire_schema`, `version`, `active_fix_id`, config from `tools.json`),
  - export of tools in function-calling format,
  - `Registry.call(tool, args)` covering the healthy path only for now.
- [ ] `adapters/rest.py`: build the base request document (`route`, `body`, `query`, `header`) from the arguments using the base schema, apply `request_ops`, send with a timeout, return the raw response.
- [ ] Argument pre-validation against `agent_schema` that returns `AGENT_ARG_ERROR` (FR-2.1).
- [ ] Fill in `config/tools.json` for the four tools:
  - `idempotent` flags: `get_user`, `update_email` and `set_manager` true; `create_ticket` false, but it sends an `Idempotency-Key`,
  - postchecks (`echo` / `non_empty`) per `technical-approach.md` §5.1.

**Tests:** `test_ac_01_registry_loads_four_tools`, `test_ac_02_invalid_args_no_heal`, and a healthy call for each tool.

**Gate:** AC-1 and AC-2 pass with no network.

---

## Phase 3: Detector and contract checks

**Goal:** every response becomes a correctly classified Outcome.

- [ ] `detect.py`: the classification order from `technical-approach.md` §5.1, plus violation extraction from FastAPI `422` (`loc`, `type`), `401` (`WWW-Authenticate`), and `404`/`405` (kind `route`).
- [ ] `contract.py`: output validation against the agent output schema (`jsonschema`) and the `echo` / `non_empty` postchecks from config.
- [ ] Wire both into `Registry.call`: `OK` and `BUSINESS` are returned; other classes are returned as unhandled for now.

**Tests:** `test_ac_03_detector_table`, with at least one case per class (`OK`, `BUSINESS`, `E1`–`E6`), using the minimal mock and synthetic responses.

**Gate:** AC-3 passes.

---

## Phase 4: Fingerprint, Store, audit, caches

**Goal:** breaks have stable names, and everything is persisted in machine-readable form.

- [ ] `fingerprint.py` (FR-4). `E6` includes the spec-diff signature (use a placeholder until phase 5, then wire it in).
- [ ] `store.py`:
  - SQLite in WAL mode with the `spec_snapshots`, `fixes`, `heal_events` and `call_events` tables (`technical-approach.md` §3.3),
  - an in-memory active-fix cache loaded at startup,
  - a negative cache with a TTL, using an injected clock,
  - synchronous audit writes,
  - `wins`/`losses` updates and retirement at 2 losses.
- [ ] A schema check: every code-read column holds an enum value, an array, a ref or an integer (AC-5).

**Tests:**
- `test_ac_04_fingerprint_stable` (two runs, plus a new process or a reloaded store),
- `test_ac_05_one_audit_event_per_attempt` (completed in phase 7),
- store unit tests.

**Gate:** AC-4 passes. Store unit tests pass.

---

## Phase 5: Diagnoser and Candidate Builder

**Goal:** given a broken call, code produces the list of valid fixes.

- [ ] `diagnose.py`:
  - fetch the current spec (0.5 s timeout), persist a new snapshot when the hash changes,
  - flatten request and response leaves,
  - produce diff entries and the diff signature,
  - error-clue mode when the spec is unavailable,
  - `404` route check that reclassifies to `BUSINESS`.
- [ ] `candidates.py`, the rules from FR-7.2:
  - type change becomes `cast`,
  - removed field fills an added one, using name tokens or the one-to-one rule,
  - with no name evidence, all type-compatible assignments are candidates (capped at 8),
  - header from `header_sources`,
  - `route`,
  - response leaf relocation becomes `move`/`cast`,
  - `NO_SAFE_VALUE` when a required value has no source.

  Output is a list of `{request_ops, response_ops}`. Candidate order must be deterministic.

**Tests (unit, one per mutation):**

| Mutation | Expected candidates |
|---|---|
| M1 | 1 candidate: `move` |
| M2 | 1 candidate: `cast` |
| M3 | 1 candidate: response `move` ×3 |
| M4 | 1 candidate: `header` |
| M5 | 1 candidate: `move` + `cast` + `header` |
| M6 | 2 candidates |
| M7 | 1 candidate: `move` |
| M8 | 0 candidates, reason `NO_SAFE_VALUE` |
| Error-clue mode | handles M1 and M2; aborts M5 with `NO_CANDIDATE` |

**Gate:** all candidate tests pass, and the same input always produces the same output.

---

## Phase 6: Jev Client, Heal Controller, retry policy

**Goal:** the full tier 0 and tier 1 heal loop with every safety bound.

- [ ] `jev.py`:
  - render the diff state and the options deterministically,
  - make one Choice request with a 1.5 s timeout,
  - parse the selected index, confidence and token usage (estimate tokens if usage is not returned).

  Confirm the exact request and response fields against TypeSafe's docs [A]. Keep the client behind an interface.
- [ ] `heal.py`, implementing FR-10 and FR-11:
  - fingerprint, single-flight lock, negative cache,
  - tier 0 lookup, otherwise diagnose and build candidates; Jev only for 2+ candidates,
  - safety gate,
  - replay once or remap,
  - verify (detector + contract),
  - commit (fix, in-memory definition update with `version + 1`, audit) or rollback (negative cache, loss, audit),
  - 3.5 s deadline throughout,
  - structured error with `retry: false`.
- [ ] `retry.py`: the `E1` policy (3 retries, backoff plus jitter, `Retry-After`), with no fingerprint and no heal.
- [ ] Wire everything into `Registry.call`.

**Tests (Jev mocked with respx):**
- `test_ac_07_m6_jev_correct_recovers`
- `test_ac_07_m6_low_confidence_no_write`
- `test_ac_12_negative_cache_known_unfixable`
- `test_ac_13_jev_down_m6_aborts_others_heal`
- `test_ac_19_single_flight_concurrency`
- `test_ac_20_unsafe_replay_non_idempotent`
- a deadline test using an injected slow clock

**Gate:** these AC tests pass.

---

## Phase 7: Core integration suite ★ milestone: healing core done

**Goal:** prove the registry heals every scenario end to end, with no agent and no network.

- [ ] An integration test per scenario, through `Registry.call` against the in-process mock:
  - `test_ac_06_m1_rename`
  - `test_ac_06_m2_type`
  - `test_ac_06_m3_response_nesting`
  - `test_ac_06_m4_oauth_header`
  - `test_ac_06_m5_ps_example`
  - `test_ac_08_m7_silent_ignore`
  - `test_ac_09_m8_no_safe_value` (also assert that no request carrying `priority` was sent)
  - `test_ac_10_c1_transient_c2_business`
- [ ] `test_ac_11_tier0_repeat_and_restart`: heal once, repeat (tier 0), recreate the registry from the same DB file, repeat again (tier 0).
- [ ] Complete `test_ac_05_one_audit_event_per_attempt` across all scenarios.
- [ ] Check that the final mock state is correct after each recovered scenario.
- [ ] Check `test_ac_01`: `agent_schema` is byte-identical after all heals.
- [ ] `metrics.py`: compute MTTR (by tier) and the heal counts from `heal_events`.

**Gate:** AC-1 to AC-13, AC-19 and AC-20 all pass in-process. Tier-1 heals take < 4 s locally. **Do not continue until this gate is green.**

---

## Phase 8: Demo-grade mock API

**Goal:** a running mock that the agents, benchmark and dashboard can drive over HTTP.

- [ ] Run the mock with Uvicorn.
- [ ] Admin endpoints:
  - activate a mutation by id,
  - reset (data plus mutation),
  - `GET /admin/state` for the data state,
  - list mutations.
- [ ] `Idempotency-Key` handling on `create_ticket` (the same key returns the same ticket).
- [ ] OAuth check for M4: `401` with `WWW-Authenticate: Bearer`; accept the configured bearer value.
- [ ] Behavior for C1 (`503` twice, then OK) and C2 (`404` for user 999).
- [ ] Rerun the phase 7 suite against the HTTP server (same tests, different transport).

**Gate:** the phase 7 suite passes over HTTP.

---

## Phase 9: Agents

**Goal:** a healing agent and a baseline agent, identical except for the registry.

- [ ] `agents/shared`:
  - one system prompt (it includes: "if a tool returns `retry: false`, do not call it again with the same arguments; report the failure"),
  - the demo task text,
  - the LLM config (same model, temperature 0).
- [ ] `healing_agent.py`: framework tools generated from `registry` exports, executing via `Registry.call`. Structured errors are returned as the tool result.
- [ ] `baseline_agent.py`: the same tools generated from the v1 spec, executing as direct HTTP calls. The raw error JSON is returned as the tool result. Iteration cap 10.
- [ ] Token accounting per run from the LLM usage metadata, and `call_events` logging for both agents.
- [ ] E2E tests (skipped without keys):
  - a clean run completes for both agents,
  - an M5 run: healing completes, baseline fails,
  - `test_ac_09` at the agent level: the agent stops after `retry: false`.

**Gate:** clean runs succeed for both agents, and the M5 contrast is visible.

---

## Phase 10: Benchmark runner and report

**Goal:** reproducible numbers for all three metrics.

- [ ] `bench/run.py`: for each scenario (M1–M8, C1–C2) × agent (healing, baseline) × N = 10, reset the mock, activate the mutation, run the task, then record the outcome, tokens and final state.
- [ ] Clean runs (no mutation), N = 10 per agent, to get the token baselines.
- [ ] Tier-0 runs: repeat M1–M5 after the first heal, and after a restart.
- [ ] Compute:
  - ZTAR (per scenario; overall M1–M7; overall including M8),
  - MTTR p50/p95 by tier,
  - Token Overhead (healing) vs wasted tokens (baseline).
- [ ] Write `results.jsonl` and `report.md` (see `technical-approach.md` §8.4).

**Gate:** AC-14, AC-15, AC-16 and AC-17 pass, and the report is generated.

---

## Phase 11: Dashboard and demo script ★ milestone: MVP demo-ready

**Goal:** the live demo from the problem statement.

- [ ] Dashboard (FastAPI + one static HTML page, vanilla JS polling):
  - two panes (healing vs baseline) with a live `call_events` stream,
  - mutation buttons (calls the mock admin endpoints),
  - patch log from `heal_events` (tier, fix operations, reason, MTTR),
  - metrics panel from the latest `report.md` data and live `heal_events`.
- [ ] `demo.py`, a scripted 30-second flow:
  1. start both agents on the task,
  2. trigger M5 mid-run,
  3. baseline loops on `422`; the healing agent completes in about 2–3 s,
  4. trigger M3 or M4 on another tool,
  5. show the patch log,
  6. trigger M8 to show the clean refusal,
  7. show the metrics.
- [ ] Run the full demo twice from a cold start.

**Gate:** AC-18 passes manually. **MVP is frozen here.** Only bug fixes to MVP code from this point.

---

## Phase 12+: STRETCH (only after phase 11)

Take these in order, one at a time. Each one keeps the full test suite green.

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| 12 | S1 sibling propagation | After a commit, create `candidate` fixes for tools with the same removed field (same name and type). Use them only when their fingerprint matches, and always verify. | A second tool hit by the same rename heals at tier 0 speed on its first occurrence |
| 13 | S3 tier-2 repair agent | Structured clue bundle in; operations JSON out, validated against the schema; same safety gate and verification; 30 s budget; `proposals` table for inexpressible fixes; MTTR reported separately | A scenario that tier 1 cannot build is healed or produces a proposal, and no code is ever executed |
| 14 | S2 rule mining | An abstract signature per fix; after 3 wins, a `rules` row that skips Jev | A repeated ambiguous pattern on a new field heals without a Jev call |
| 15 | S4 GraphQL | Strawberry mock with introspection; a GraphQL adapter producing the same Outcome model; selection and argument fixes | M1, M2 and M3 equivalents heal over GraphQL |
| 16 | S5 gRPC (unary) | grpcio mock with reflection and rich error details; an adapter producing the same Outcome model | M1 and M2 equivalents heal over gRPC |

---

## Progress log

| Date | Phase | Status | Notes |
|---|---|---|---|
| | 0 | not started | |
