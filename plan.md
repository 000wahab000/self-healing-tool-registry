# plan.md: Build Plan

> Ordered build plan for PS 01. Inputs: `product.md` (what, FR/AC ids) and `agent.md` (rules). Design details: `technical-approach.md`.
>
> **Order principle:** build the self-healing tool registry first and prove it through integration tests (phases 0–7). Then build the parts around it: the demo mock API, agents, benchmark and dashboard (phases 8–11). Phase 12 aligns the build with the revised spec (`product.md` v3). STRETCH work comes last (phase 13+).
>
> **Status:** phases 0–11 are built (see the progress log). Their task lists below are kept as the record of what was built; their checkboxes were not ticked one by one, so read the progress log as the status. Where `product.md` v3 changed a rule that a phase built, the line is annotated and the change is a task in phase 12.
>
> Work one phase at a time. Every phase ends with a gate; do not start the next phase until it passes. Before ticking any box, run `pytest -q` and `ruff check .`.

---

## Phase 0: Scaffold

**Goal:** an empty project that installs, lints and runs tests.

- [ ] `pyproject.toml`:
  - runtime dependencies: fastapi, uvicorn, pydantic v2, httpx, jsonschema,
  - dev dependencies: pytest, pytest-asyncio, respx, ruff,
  - optional `agents` extra: langgraph, langchain-openai.
- [ ] The directory layout from `agent.md` §3 (empty modules with docstrings).
- [ ] `.env.example` listing every variable. Current live agents use `NVIDIA_API_KEY` and `LLM_MODEL` (default `openai/gpt-oss-20b`); Jev is optional and independent, using direct `JEV_API_KEY`, `JEV_URL`, `JEV_MODEL` or the Jev-only `OPENROUTER_API_KEY` fallback. Other variables: `OAUTH_BEARER`, `TENANT_ID`, `DB_PATH`, `MOCK_PORT`, `DASHBOARD_PORT`, `RUN_E2E`.
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

  Product spec v3 labels everything here except the audit log as STRETCH: the persistent `fixes` and `spec_snapshots` tables, reload at startup and retirement are S6, and the negative cache is S7. They are built and tested (see "Already built" before the STRETCH table).
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

  As built: `POST /v1/systemone` on TypeSafe (`JEV_API_KEY`), or `https://openrouter.ai/api/v1/systemone` with model `~typesafe/jev-latest` (`OPENROUTER_API_KEY`, Jev-only fallback). The NVIDIA agent key is separate. Confirm the exact request and response fields against TypeSafe's docs [A]. Keep the client behind an interface.
- [ ] `heal.py`, implementing FR-10 and FR-11:
  - fingerprint, single-flight lock (S7), negative cache (S7),
  - tier 0 lookup (S6), otherwise diagnose and build candidates; Jev only for 2+ candidates (phase 12 puts the deterministic tie-breaker before Jev and makes Jev optional),
  - safety gate,
  - replay once or remap,
  - verify (detector + contract),
  - commit (fix, in-memory definition update with `version + 1`, audit) or rollback (negative cache, loss, audit),
  - 3.5 s deadline throughout,
  - structured error with `retry: false`.
- [ ] `retry.py`: the `E1` policy (3 retries, backoff plus jitter, `Retry-After`), with no fingerprint and no heal.
- [ ] Wire everything into `Registry.call`.

**Tests (Jev mocked with respx):**
- `test_ac_07_m6_jev_correct_recovers` (rewritten in phase 12 for M6-D / M6-N)
- `test_ac_07_m6_low_confidence_no_write` (rewritten in phase 12)
- `test_ac_12_negative_cache_known_unfixable` (S7)
- `test_ac_13_jev_down_m6_aborts_others_heal` (rewritten in phase 12: the abort reason is now `LOW_CONFIDENCE`)
- `test_ac_19_single_flight_concurrency` (S7)
- `test_ac_20_unsafe_replay_non_idempotent` (extended in phase 12 to the FR-9.4 rule)
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
- [ ] `test_ac_11_tier0_repeat_and_restart` (S6): heal once, repeat (tier 0), recreate the registry from the same DB file, repeat again (tier 0).
- [ ] Complete `test_ac_05_one_audit_event_per_attempt` across all scenarios.
- [ ] Check that the final mock state is correct after each recovered scenario.
- [ ] Check `test_ac_01`: `agent_schema` is byte-identical after all heals.
- [ ] `metrics.py`: compute MTTR (by tier) and the heal counts from `heal_events`.

**Gate:** AC-1 to AC-13, AC-19 and AC-20 all pass in-process (AC-11 is S6; AC-12 and AC-19 are S7; AC-7 and AC-13 are re-gated against v3 in phase 12). Tier-1 heals take < 4 s locally. **Do not continue until this gate is green.**

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
  - one system prompt (it includes: "if a tool returns `retry: false`, do not call it again with the same arguments; report the failure"; as built after 12D: on `SCHEMA_DRIFT_UNRECOVERABLE` the tool is unavailable for the rest of the task, report it as skipped and continue),
  - the demo task text,
  - the LLM config (same model, temperature 0). Current config: NVIDIA NIM's OpenAI-compatible API (`https://integrate.api.nvidia.com/v1`, `NVIDIA_API_KEY`), default `openai/gpt-oss-20b`, overridable with `LLM_MODEL`. [Model source](https://build.nvidia.com/openai/gpt-oss-20b).
- [ ] `healing_agent.py`: LangGraph `create_react_agent` with framework tools generated from `registry` exports, executing via `Registry.call`. Structured errors are returned as the tool result.
- [ ] `baseline_agent.py`: the same framework and tools generated from the v1 spec, executing as direct HTTP calls. The raw error JSON is returned as the tool result. Iteration cap 10.
- [ ] `scripted.py`: a scripted no-LLM agent that runs the demo task as fixed tool calls through either path (the baseline re-sends a failing call with the same arguments until the cap). It allows keyless benchmark runs and paced demos.
- [ ] Token accounting per run from the LLM usage metadata, and `call_events` logging for both agents.
- [ ] E2E tests (skipped without keys):
  - a clean run completes for both agents,
  - an M5 run: healing completes, baseline fails,
  - `test_ac_09` at the agent level: the agent stops after `retry: false`.

**Gate:** clean runs succeed for both agents, and the M5 contrast is visible.

---

## Phase 10: Benchmark runner and report

**Goal:** reproducible numbers for all three metrics.

- [x] `bench/run.py` (as built: `python -m bench.run --agent scripted|llm --n N`): for each scenario (M1–M8, C1 as built; v3 adds M9, M6-D/M6-N and C2/C3 in phase 12) × agent (healing, baseline) × N = 10, reset the mock, activate the mutation, run the task, then record the outcome, tokens and final state.
- [x] Clean runs (no mutation), N = 10 per agent, to get the token baselines.
- [x] Tier-0 runs (S6): repeat M1–M5 after the first heal, and after a restart.
- [x] Compute (v1 definitions as built; redefined per FR-15.4 in phase 12):
  - ZTAR (per scenario; overall M1–M7; overall including M8),
  - MTTR p50/p95 by tier,
  - Token Overhead (healing) vs wasted tokens (baseline).
- [x] Write `results.jsonl` and `report.md` (see `technical-approach.md` §8.4).

**Gate:** AC-14, AC-15, AC-16 and AC-17 pass, and the report is generated. The recorded run is scripted mode (no LLM), N = 3, dated 2026-10-14 (`bench/report.md`); token metrics need an LLM-mode run.

---

## Phase 11: Dashboard and demo script ★ milestone: MVP demo-ready

**Goal:** the live demo from the problem statement.

- [ ] Dashboard (FastAPI + one static HTML page, vanilla JS polling; it runs both agents and two isolated mock instances in one process):
  - two panes (healing vs baseline) with a live `call_events` stream,
  - Start (scripted), Start (LLM) and Reset controls,
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

**Gate:** AC-18 passes manually. **MVP was frozen here.** From this point only bug fixes to MVP code, plus the planned spec v3 alignment in phase 12.

---

## Phase 12: Spec v3 alignment

**Goal:** bring the built system in line with the revised `product.md`. The healing core stays. This phase adds the deterministic tie-breaker, makes Jev optional, tightens the safety rules, adds the new scenarios and redefines the metrics. Work the groups in order and keep the full suite green after each (`pytest -q`, `ruff check .`). Test names below are suggestions; each AC still needs a `test_ac_XX_*` test (`agent.md` §5).

### 12A. Tie-breaker, optional Jev, write-tool ambiguity (AC-7, AC-13, AC-27)

- [ ] `candidates.py`: the deterministic tie-breaker for 2 or more candidates (FR-7.6). Score on (1) description match (a shared non-stopword token between the removed field's description in the base snapshot and the added field's description in the current spec), (2) parameter order, (3) type. A candidate wins only if it strictly beats every other. For a **write** tool, a win must include a description match. Descriptions are compared as tokens only (FR-8.8). Candidate order stays deterministic.
- [ ] `heal.py`: decision order is candidates, then tie-breaker, then Jev, then abort. Call Jev only when there are 2 or more candidates, the tie-breaker found no unique winner and Jev is configured (FR-8.1).
- [ ] Jev absent, timeout or error: abort `LOW_CONFIDENCE` before any request is sent, and record the `jev_unavailable` marker in the decision path (FR-8.3, FR-5.3). `JEV_UNAVAILABLE` stops being an abort reason; it survives only as the marker. Under S7, a `LOW_CONFIDENCE` that followed a Jev timeout or error is not negative-cached (FR-11.3).
- [ ] Write-tool ambiguity (FR-8.6, FR-9.6): add an optional `preverify` entry to `config/tools.json` (a side-effect-free operation plus the expected result that distinguishes the chosen candidate). For a write tool with 2 or more candidates, accept only a tie-breaker win with description evidence, or a Jev choice at confidence ≥ 0.9 that `preverify` confirms before any write. Otherwise `LOW_CONFIDENCE`, nothing sent. Enforce it in `safety.py`.
- [ ] Mock: M6-D (informative OpenAPI descriptions on the `set_manager` fields) and M6-N (descriptions absent or identical) (FR-12.6). If a side-effect-free operation can distinguish the correct M6-N assignment, expose it for `preverify`; whether one exists is an open question [A] (FR-12.9).
- [ ] The audit decision path records whether the tie-breaker or Jev decided (FR-5.3).

**Tests:**
- `test_ac_27_tiebreaker_table`: M6-D yields exactly one winner, M6-N yields none, and on a write tool an order-only or type-only advantage is not a win.
- `test_ac_07_m6d_tiebreaker_no_jev_call`
- `test_ac_07_m6n_jev_confident_preverify_recovers` (Jev mocked)
- `test_ac_07_m6n_below_threshold_or_no_preverify_no_write` (final mock state unchanged)
- `test_ac_13_jev_down`: M1 to M5, M7 and M9 still heal; M6-N aborts `LOW_CONFIDENCE` within the deadline with no write; M6-D still heals.

### 12B. Classification and replay rules (AC-20, AC-21, AC-25)

- [ ] `E3` (FR-10.1): return a structured error with reason `UNSUPPORTED_CLASS`, with exactly one audit event and no replay. Add the code to the `Reason` enum and to the S7 negative-cache set.
- [ ] Value errors (FR-3.4). Normalize violation kinds from FastAPI `422` types (value kinds `format`, `range`, `pattern`, `enum`, `length`; structural kinds `missing`, `extra`, `type`) [A: mapping confirmed against the mock's `422` bodies]. An `E2` whose violations are all value kinds **and** whose spec diff is empty becomes `BUSINESS` with audit reason `NOT_DRIFT`: returned unchanged, no fix, no replay.
- [ ] API-rollback rule (FR-3.4): an empty spec diff with structural violations means the request shape is wrong. With an active fix, that fix is stale: diagnose against the base schema, which yields the "no operations" candidate, and replay the base request once. With no active fix, abort `NO_CANDIDATE`. A mix of value and structural violations counts as structural.
- [ ] Mock control C3 (FR-12.7): `update_email` validates the `email` value (format) and returns a FastAPI `422` value-error body for an invalid address, with the spec unchanged [A: demo tool].
- [ ] Replay rule (FR-9.4) in `safety.py` and `heal.py`: `E2` is the only class that is replay-safe by itself. `E4` and `E6` replay only for an idempotent tool or with an `Idempotency-Key`; otherwise `UNSAFE_REPLAY`. `E5` is never replayed (response-side remap).

**Tests:**
- `test_ac_25_e3_unsupported_class`: a non-JSON fixture returns the structured error, writes one audit event and replays nothing.
- `test_ac_21_c3_value_error_not_drift`: `BUSINESS` / `NOT_DRIFT`, no fix built, no request replayed, error returned unchanged.
- `test_ac_20_replay_rule` with a fixture tool: `E4` or `E6` on a non-idempotent tool without a key aborts `UNSAFE_REPLAY`; `E4` on an idempotent tool, or with a key, is replayed.
- An API-rollback test (empty diff, structural violations, stale active fix), covering FR-3.4.

### 12C. M9, redaction, `spec_mode`, audit fields (AC-22, AC-23, AC-24)

- [ ] Mutation M9 (request nesting): in the mock, `update_email` changes from the flat body `{user_id, email}` to `{payload:{user_id, email}}` (wrapping only: no rename, no type change, no header) [A: demo tool]. The candidate builder yields 1 candidate: `move` ×2. Add `test_ac_22_m9_request_nesting` (tier-1 heal on first occurrence, task completes, final mock state correct) and a candidate unit test.
- [ ] Raw-error sanitizer (FR-5.7), applied before the blob is stored. Redact: values of `Authorization`, `Cookie`, `Set-Cookie`, API-key and token headers; any string equal to a configured secret (`OAUTH_BEARER`, `TENANT_ID`, `JEV_API_KEY`, the LLM key); bearer-token and JWT-shaped strings [A: pattern list]. Truncate to a maximum size [A]. Test `test_ac_24_raw_error_redacted` with fixtures that contain secrets.
- [ ] `spec_mode` switch (FR-6.4): `on` or `off` in the settings module. With `off`, the Diagnoser runs in error-clue mode only.
- [ ] Audit event gets `heal_ms` next to `mttr_ms` (FR-5.3, FR-15.4). Update the `heal_events` schema and the AC-5 schema check.

### 12D. Benchmark and metrics (AC-14 to AC-17, AC-23)

- [x] Metrics (FR-15.4, FR-15.5) in `metrics.py` and `bench/run.py`:
  - ZTAR over the healable mutations only (M1 to M5, M7, M9); M6 (both configurations, with and without Jev) and M10 reported separately,
  - Safe-Refusal Rate over M8 and M6-N with Jev disabled,
  - False-Patch Rate: healed runs whose final mock state was wrong (target 0),
  - MTTR from the first failing response caused by the mutation to the first verified-correct result, on a monotonic clock; `heal_ms` reported separately,
  - Token Overhead against the clean-run median, with baseline wasted tokens beside it and `jev_tokens` in its own column,
  - mean, median and p95 for every timing and token metric, per scenario.
- [x] Scenario list: M1 to M9 (M6-D and M6-N), C1 to C3. Clean runs, N = 10 per agent (FR-15.6).
- [x] Error-only ablation (FR-15.7): run M1 to M9 once more with `spec_mode` set to `off`; report per mutation whether it healed or aborted, and the reason. Combined or nested mutations (such as M5 and M9) are expected to abort `NO_CANDIDATE`. No heal-rate threshold; False-Patch Rate must stay 0.
- [x] Baseline outcomes (error loop, calls, tokens, final data correctness) reported for every scenario, not asserted (FR-15.8, AC-17).
- [x] Re-run the benchmark and regenerate `results.jsonl` and `report.md`. The current `bench/report.md` is a scripted run (N = 3) that predates these definitions. AC-16 needs an LLM-mode run, because scripted mode records 0 LLM tokens.
- [x] Dashboard: mutation buttons cover M6-D, M6-N, M9 and C3 (guarded by `test_mutation_buttons_cover_every_scenario_including_m6_m9_and_c3`).
- [ ] Re-check AC-18 by hand (one-click mutation, both agents live, heal event within 1 s); the demo re-run in 12E is the vehicle.

### 12E. Deliverables (`product.md` §16)

- [x] Short write-up of the diagnosis and patch logic, from `product.md` §4 and §8, `technical-approach.md` §5 and §6, and the measured results. Proposed location: `writeup.md` at the repo root [A: `product.md` leaves the location to this plan; confirm with the team].
- [x] 30-second pitch, using only numbers and claims that appear in `report.md`. Proposed location: `pitch.md` at the repo root [A: same].
- [ ] Demo script (`dashboard/demo.py`): re-run it twice from a cold start after 12A to 12D, including the M8 refusal, and confirm it also works with Jev not configured.

**Gate:** AC-7, AC-13, AC-15, AC-16, AC-17, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25 and AC-27 pass. AC-14 and AC-18 are re-checked against the new definitions. AC-1 to AC-6 and AC-8 to AC-10 still pass, and so do the built STRETCH criteria AC-11, AC-12 and AC-19. `pytest -q` and `ruff check .` are clean, and the benchmark report is regenerated.

---

## Already built: STRETCH items S6 and S7

`product.md` v3 labels the persistent fix store (S6) and the negative cache plus single-flight (S7) as STRETCH. Both were built in phases 4, 6 and 7 and are tested, so those STRETCH items are done. Phase 12 must keep them working.

- **S6, persistent fix store.** The `fixes` and `spec_snapshots` tables, reload of active fixes at startup, tier-0 reuse by fingerprint including after a restart, and retirement at 2 losses. Tests: `test_ac_11_tier0_repeat_and_restart`, and in `tests/unit/test_store.py`: `test_fix_round_trip_survives_restart`, `test_one_active_fix_per_fingerprint`, `test_retired_at_two_losses_and_evicted`. The scripted benchmark in `bench/report.md` shows tier-0 heal times of 1 to 4 ms (scripted mode, N = 3).
- **S7, negative cache and single-flight.** `KNOWN_UNFIXABLE` for 60 s on a failed fingerprint, and concurrent calls with the same fingerprint share one heal. Tests: `test_ac_12_negative_cache_known_unfixable`, `test_ac_19_single_flight_concurrency`, and `test_negative_cache_expires_with_injected_clock`.

---

## Phase 13+: STRETCH (only after phase 12)

The order column below was the original single-person plan. The work now runs as the four parallel tracks in the next section; this table keeps the task details and "done when" conditions for the S items.

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| done | S6 persistent fix store | Built in phases 4, 6 and 7 (see above) | AC-11 passes (it does) |
| done | S7 negative cache and single-flight | Built in phases 4 and 6 (see above) | AC-12 and AC-19 pass (they do) |
| 13 | S1 sibling propagation | After a commit, create `candidate` fixes for tools with the same removed field (same name and type). Use them only when their fingerprint matches, and always verify. | A second tool hit by the same rename heals at tier 0 speed on its first occurrence |
| 14 | S3 tier-2 repair agent | Structured clue bundle in; operations JSON out, validated against the schema; same safety gate and verification; 30 s budget; `proposals` table for inexpressible fixes; MTTR reported separately | A scenario that tier 1 cannot build is healed or produces a proposal, and no code is ever executed |
| 15 | S2 rule mining | An abstract signature per fix; after 3 wins, a `rules` row that skips Jev | A repeated ambiguous pattern on a new field heals without a Jev call |
| 16 | S4 GraphQL | Strawberry mock with introspection; a GraphQL adapter producing the same Outcome model; selection and argument fixes | M1, M2 and M3 equivalents heal over GraphQL |
| 17 | S5 gRPC (unary) | grpcio mock with reflection and rich error details; an adapter producing the same Outcome model | M1 and M2 equivalents heal over gRPC |
| 18 | S8 injection resistance (M10) | Mock M10: M1's rename with injected instructions in the `422` `msg` and in the new field's OpenAPI description (FR-12.8); an integration test and a benchmark scenario. The property itself is already enforced by the provenance rules (FR-5.4, FR-8.8); M10 only demonstrates it. | AC-26 passes: same operations as M1, correct final state, nothing derived from the injected text, same decision path as M1 |

---

## Phase 13+: four parallel tracks

Four people build the STRETCH items, the `product.md` §14 future scope and an MCP server at the same time. File ownership, reserved AC numbers, branch names, review rules and the contracts between tracks are in `AGENTS.md` ("Four-person ownership"). Kickoff prompts are in `team-prompts.md`. Each track runs its items in order, one PR per item, and keeps `pytest -q` and `ruff check .` clean.

The §14 items and the MCP server have no requirements yet. Each one starts by adding its FR and AC to `product.md` (owner writes, P2 reviews), as `agent.md` invariant 10 requires. IDs: X1 Swagger 2.0, X2 `E3` healing, X3 new operations, X4 drift watcher, X5 Jev drift-vs-business without a spec, X6 Postgres, X7 streaming, X8 MCP server.

### Step 0: shared contracts (P2, before all tracks)

- [x] `OperationSpec`, `ParamSpec`, `LoadedSpec` and `SpecSource` in `models.py`; `openapi_loader.openapi_source(client)` as the default source.
- [x] `Registry` and `Healer` take a `spec_source` instead of calling `fetch_spec` directly.
- [x] `FixStore` protocol in `store.py`; `Registry` and `Healer` are typed against it.
- [x] Contract tests: OpenAPI operations match `OperationSpec`; `Store` implements `FixStore`; an injected spec source is used by both load and heal.

### Track P1: MCP server and protocols (teammate, GPT with oh-my-opencode-slim)

The MCP server is the top priority. It turns the registry into a drop-in proxy: any MCP client (Claude Desktop, Cursor, Windsurf, LangChain MCP adapters) gets healing with no code changes. Path: agent → MCP → healer → HTTP → live API.

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| P1-1 | X8 MCP server over stdio | FR/AC first (AC-30 onward). `src/healer/mcp_server.py` on the official `mcp` SDK (new `mcp` optional group, pinned to one major version). Use the low-level server so `tools/list` returns `Registry.tools()` exactly (`agent_schema` as `inputSchema`, never derived from Python signatures). `tools/call` goes through `Registry.call()`; a heal error or refusal becomes a tool result with `isError: true` and the `HealError` dict as structured content. Never emit `tools/list_changed` (the schema is frozen). Logs to stderr only. CLI entry `healer-mcp --base-url --spec-path --tools --db`. | An MCP client test against the in-process mock lists the tools, calls `get_user`, survives an M1 mutation mid-session with the same session and no `list_changed`, and gets an `isError` result with its reason for M8 |
| P1-2 | X8 MCP over Streamable HTTP | Same server on Streamable HTTP; one registry shared by concurrent sessions (single-flight still gives one heal for 5 concurrent calls); bind to localhost by default; optional bearer token for remote use | The P1-1 tests pass over HTTP, plus an AC-19-style concurrency test through MCP |
| P1-3 | X8 MCP client hand-off | Config snippets for Claude Desktop, Cursor and Windsurf (stdio and HTTP) handed to P4 for `docs/`; an opt-in live test with a real MCP client config | P4 can follow the snippets on a clean machine |
| P1-4 | S4 GraphQL | Strawberry mock with introspection and admin mutations; `graphql_loader.py` emitting `OperationSpec`; `adapters/graphql.py` classifying into `Outcome`; registry dispatch by protocol | M1, M2 and M3 equivalents heal over GraphQL (any missing operation is requested from P2) |
| P1-5 | S5 gRPC (unary) | grpcio mock with reflection and rich error details; `grpc_loader.py`; `adapters/grpc.py` mapping status codes to `ErrorClass` | M1 and M2 equivalents heal over gRPC |
| P1-6 | X6 Postgres fix sharing | `store_pg.py` implementing `FixStore`; store tests run on both backends; two registries sharing one database see each other's fixes; one active fix per fingerprint enforced by the database | A fix committed by instance A is reused at tier 0 by instance B |
| P1-7 | X8b upstream MCP healing (optional) | FR/AC first. A `SpecSource` that reads an upstream MCP server's `tools/list` into `OperationSpec`, so drift in another MCP server's tool schemas heals the same way | An upstream MCP tool renaming a field heals behind the proxy |
| P1-8 | X7 streaming (optional, last) | FR/AC first: what drift means mid-stream, where a fix applies, when a stream is refused | Defined in `product.md`, then built to its own AC |

### Track P2: Healing core and evidence (Wahab, Claude Code)

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| P2-0 | MVP evidence | Live E2E tests on gpt-oss-20b (NVIDIA NIM); real-LLM benchmark at N = 10 per agent and scenario, clean runs included; AC-14 and AC-16 reported as measured, misses included; model and provider recorded in `report.md` | `report.md` regenerated from an LLM-mode run; `agents/` handed to P4 |
| P2-1 | S8 injection resistance (M10) | Mock M10, its integration test and benchmark scenario | AC-26 passes |
| P2-2 | S1 sibling propagation | Candidate fixes for tools with the same removed field; used only on a fingerprint match, always verified | A second tool hit by the same rename heals at tier 0 speed on first occurrence |
| P2-3 | X3 new operations | `enum_map`, `encoding` (for `415`), lossless value transforms with a round-trip check; schema, `ops.py`, candidates, safety gate, mock mutations | Each new operation heals its mutation; a lossy transform is refused |
| P2-4 | S3 tier-2 repair agent | Operations JSON out, validated; same gate and verification; 30 s budget; `proposals` table and its `FixStore` methods | A scenario tier 1 cannot build is healed or yields a proposal; no code is executed |
| P2-5 | S2 rule mining | Abstract signature per fix; after 3 wins a `rules` row that skips Jev; its `FixStore` methods | A repeated ambiguous pattern heals without a Jev call |
| P2-6 | X2 `E3` healing | Re-send with a defined operation set when the new content type is declared in the spec | A declared content-type change heals; anything else still refuses |
| P2-7 | X5 Jev drift-vs-business without a spec | Jev yes/no check when the spec is off or unavailable; abort when Jev is absent | A business error is never healed |
| P2-8 | X4 fix precomputation (heal side) | `Healer.precompute(old, new)`: build and dry-run candidates from the diff, store as `candidate`, send nothing | After P4's watcher sees a change, the first failing call heals at tier 0 speed |

P2 also reviews every P3 and P4 PR and every contract change.

### Track P3: Small isolated items (OpenCode free tier, no plugins)

Each item touches at most two new files plus their tests, has its acceptance test written below, and is reviewed by P2. Use only zero-retention free models (see `team-prompts.md`), because the repo is private.

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| P3-1 | Plan hygiene | Tick the `plan.md` boxes in phases 0 to 12 that the progress log and passing tests show are done; leave genuinely open ones (AC-18 manual check, live runs) unticked; no other text changes | Every ticked box names work with a passing test or a progress-log row |
| P3-2 | AC-28 healthy-call overhead | FR/AC first (AC-28: the registry adds < 10 ms p95 per call, excluding network, `product.md` §11). `bench/overhead.py`: time 200+ healthy `Registry.call()` calls against the in-process mock, subtract the same calls sent straight through the transport, print p50 and p95. `tests/p3/test_ac_28_healthy_overhead.py` | The test passes and the script prints p50 and p95 |
| P3-3 | X1 Swagger 2.0 converter | FR/AC first. `src/healer/swagger2.py`: a pure function converting a Swagger 2.0 document to the OpenAPI 3 shape `operations()` reads (`definitions` to `components/schemas`, `in: body` to `requestBody`, `consumes`/`produces`, `securityDefinitions`); a `swagger2_source(client, path)`; a 2.0 copy of the mock spec in `mock_api/fixtures/` | `operations(convert(fixture))` equals `operations()` of the mock's OpenAPI 3 spec, and M1 heals when the registry loads the 2.0 fixture |

### Track P4: Demo, docs and integration (Antigravity, Gemini Flash)

Antigravity's built-in browser agent suits the visual checks. Keep to one feature per conversation to stay inside the plan's quota.

| Order | Item | Key tasks | Done when |
|---|---|---|---|
| P4-1 | AC-18 browser check | Run the dashboard locally; in the browser, trigger mutations with one click, confirm both agents update live and the heal event appears within 1 s (compare the click time with the `heal_events` timestamp); two cold-start demo rehearsals, including M8 and a run with Jev not configured; screenshots in the PR | Timings and screenshots recorded in the PR and a progress-log row |
| P4-2 | X4 drift watcher (watch side) | FR/AC first. `spec_watcher.py`: poll a `SpecSource` on an interval, compare hashes, save new snapshots, call `Healer.precompute(old, new)` once P2-8 exists (guarded until then); injected clock and sleep, bounded backoff, never blocks a call | A spec change is snapshotted within one interval; an unchanged spec causes no extra work |
| P4-3 | MCP client guides | `docs/mcp-clients.md` from P1-3's snippets: Claude Desktop, Cursor, Windsurf, stdio and HTTP; tested by hand on one client | A fresh user connects a client by following the guide |
| P4-4 | Dashboard updates | Buttons for new scenarios as P1 and P2 land them (M10, new-op mutations); an MCP view showing calls arriving through the MCP server | Dashboard tests pass; new buttons are covered by the existing button-coverage test |
| P4-5 | LangGraph migration | After P2-0: move both agents from `create_react_agent` to `langchain.agents.create_agent`; pin `langgraph` below 2 until then | Agent tests pass with no deprecation warning |
| P4-6 | Final docs and pitch | After P2-0: README, `pitch.md` and `writeup.md` updated from the measured `report.md`, misses included; record the schema-rebase idea in `writeup.md` as future design, not built (the frozen `agent_schema` is an invariant); an MCP demo recording for the pitch | Every number in the docs appears in `report.md` |

### Hand-offs between the tracks

- P1-1 to P1-3 depend only on step 0 and `Registry`, so they can start now.
- P1-6 must catch up with `FixStore` after P2-4 and P2-5 add tables.
- P2-8 needs P4-2's watcher; P4-2 ships first with the hook guarded.
- P4-3 needs P1-3; P4-5 and P4-6 need P2-0.
- P3-3's converter plugs in through `SpecSource`; P1 reviews the loader side.

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
