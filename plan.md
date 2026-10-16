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

- [x] `pyproject.toml`:
  - runtime dependencies: fastapi, uvicorn, pydantic v2, httpx, jsonschema,
  - dev dependencies: pytest, pytest-asyncio, respx, ruff,
  - optional `agents` extra: langgraph, langchain-openai.
- [x] The directory layout from `agent.md` §3 (empty modules with docstrings).
- [x] `.env.example` listing every variable. Current live agents use `NVIDIA_API_KEY` and `LLM_MODEL` (default `openai/gpt-oss-20b`); Jev is optional and independent, using direct `JEV_API_KEY`, `JEV_URL`, `JEV_MODEL` or the Jev-only `OPENROUTER_API_KEY` fallback. Other variables: `OAUTH_BEARER`, `TENANT_ID`, `DB_PATH`, `MOCK_PORT`, `DASHBOARD_PORT`, `RUN_E2E`.
- [x] `config/tools.json` skeleton containing `header_sources` (`Authorization` → `OAUTH_BEARER`, `X-Tenant-Id` → `TENANT_ID`) and an empty `tools` object.
- [x] A settings module with every threshold and timeout from `product.md`:
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
- [x] One smoke test.

**Gate:** `pip install -e .[dev]`, `pytest -q` and `ruff check .` all pass.

---

## Phase 1: Core models, Op Interpreter, Safety Gate

**Goal:** the pure, deterministic building blocks. No I/O.

- [x] `models.py`:
  - enums: `ErrorClass` (`OK`, `BUSINESS`, `E1`–`E6`), `Reason` (all codes in `product.md` §8), `Outcome` code (`RECOVERED`, `ABORTED`, `VERIFY_FAILED`, `NOT_DRIFT`), `Tier`, `Side`, `OpName`, `PostcheckType`,
  - records: `Violation`, `Outcome`, `Op`, `Fix`, `AuditEvent`.
- [x] `canonical.py`: canonical JSON, sha256, and path helpers (get, pop, put) on documents.
- [x] `ops.py`: implements `move`, `cast`, `header`, `route`. Pure: returns a new document. Rejects unknown operations.
- [x] Operations JSON Schema, used to validate any externally produced operation list (Jev never produces one, but tier 2 will).
- [x] `safety.py`: provenance, lossless cast, operation cap, replay rule, and per-tool Jev threshold check (FR-9.1–9.5).
- [x] Unit tests:
  - every operation (apply, invalid path, unknown operation),
  - lossless cast table (`"123"` passes; `"0123"`, `"12a"` and `"1.5"` fail for int),
  - each safety rejection, mapped to its reason code.

**Gate:** all unit tests pass. FR-9 is fully covered.

---

## Phase 2: OpenAPI Loader, Tool Registry, REST Adapter, minimal mock API

**Goal:** an agent-facing tool can call a real (in-process) API through the registry.

- [x] `mock_api/` **minimal**: a FastAPI app with only what tests need.
  - The four operations `get_user`, `update_email`, `set_manager`, `create_ticket`, with in-memory data containing users 123 and 456.
  - Strict Pydantic types. Unknown body fields are ignored.
  - Mutations as data (M1–M8, C1–C2). Each mutation is a set of changes to models, routes or behavior, so `/openapi.json` reflects the active one.
  - A test-only helper to switch mutations in-process. (The HTTP admin endpoints come in phase 8.)
- [x] `openapi_loader.py`: fetch the spec, resolve `$ref`s into a self-contained schema per operation, canonicalize, hash.
- [x] `registry.py`:
  - `ToolDefinition` (`agent_schema` frozen, `wire_schema`, `version`, `active_fix_id`, config from `tools.json`),
  - export of tools in function-calling format,
  - `Registry.call(tool, args)` covering the healthy path only for now.
- [x] `adapters/rest.py`: build the base request document (`route`, `body`, `query`, `header`) from the arguments using the base schema, apply `request_ops`, send with a timeout, return the raw response.
- [x] Argument pre-validation against `agent_schema` that returns `AGENT_ARG_ERROR` (FR-2.1).
- [x] Fill in `config/tools.json` for the four tools:
  - `idempotent` flags: `get_user`, `update_email` and `set_manager` true; `create_ticket` false, but it sends an `Idempotency-Key`,
  - postchecks (`echo` / `non_empty`) per `technical-approach.md` §5.1.

**Tests:** `test_ac_01_registry_loads_four_tools`, `test_ac_02_invalid_args_no_heal`, and a healthy call for each tool.

**Gate:** AC-1 and AC-2 pass with no network.

---

## Phase 3: Detector and contract checks

**Goal:** every response becomes a correctly classified Outcome.

- [x] `detect.py`: the classification order from `technical-approach.md` §5.1, plus violation extraction from FastAPI `422` (`loc`, `type`), `401` (`WWW-Authenticate`), and `404`/`405` (kind `route`).
- [x] `contract.py`: output validation against the agent output schema (`jsonschema`) and the `echo` / `non_empty` postchecks from config.
- [x] Wire both into `Registry.call`: `OK` and `BUSINESS` are returned; other classes are returned as unhandled for now.

**Tests:** `test_ac_03_detector_table`, with at least one case per class (`OK`, `BUSINESS`, `E1`–`E6`), using the minimal mock and synthetic responses.

**Gate:** AC-3 passes.

---

## Phase 4: Fingerprint, Store, audit, caches

**Goal:** breaks have stable names, and everything is persisted in machine-readable form.

- [x] `fingerprint.py` (FR-4). `E6` includes the spec-diff signature (use a placeholder until phase 5, then wire it in).
- [x] `store.py`:
  - SQLite in WAL mode with the `spec_snapshots`, `fixes`, `heal_events` and `call_events` tables (`technical-approach.md` §3.3),
  - an in-memory active-fix cache loaded at startup,
  - a negative cache with a TTL, using an injected clock,
  - synchronous audit writes,
  - `wins`/`losses` updates and retirement at 2 losses.

  Product spec v3 labels everything here except the audit log as STRETCH: the persistent `fixes` and `spec_snapshots` tables, reload at startup and retirement are S6, and the negative cache is S7. They are built and tested (see "Already built" before the STRETCH table).
- [x] A schema check: every code-read column holds an enum value, an array, a ref or an integer (AC-5).

**Tests:**
- `test_ac_04_fingerprint_stable` (two runs, plus a new process or a reloaded store),
- `test_ac_05_one_audit_event_per_attempt` (completed in phase 7),
- store unit tests.

**Gate:** AC-4 passes. Store unit tests pass.

---

## Phase 5: Diagnoser and Candidate Builder

**Goal:** given a broken call, code produces the list of valid fixes.

- [x] `diagnose.py`:
  - fetch the current spec (0.5 s timeout), persist a new snapshot when the hash changes,
  - flatten request and response leaves,
  - produce diff entries and the diff signature,
  - error-clue mode when the spec is unavailable,
  - `404` route check that reclassifies to `BUSINESS`.
- [x] `candidates.py`, the rules from FR-7.2:
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

- [x] `jev.py`:
  - render the diff state and the options deterministically,
  - make one Choice request with a 1.5 s timeout,
  - parse the selected index, confidence and token usage (estimate tokens if usage is not returned).

  As built: `POST /v1/systemone` on TypeSafe (`JEV_API_KEY`), or `https://openrouter.ai/api/v1/systemone` with model `~typesafe/jev-latest` (`OPENROUTER_API_KEY`, Jev-only fallback). The NVIDIA agent key is separate. Confirm the exact request and response fields against TypeSafe's docs [A]. Keep the client behind an interface.
- [x] `heal.py`, implementing FR-10 and FR-11:
  - fingerprint, single-flight lock (S7), negative cache (S7),
  - tier 0 lookup (S6), otherwise diagnose and build candidates; Jev only for 2+ candidates (phase 12 puts the deterministic tie-breaker before Jev and makes Jev optional),
  - safety gate,
  - replay once or remap,
  - verify (detector + contract),
  - commit (fix, in-memory definition update with `version + 1`, audit) or rollback (negative cache, loss, audit),
  - 3.5 s deadline throughout,
  - structured error with `retry: false`.
- [x] `retry.py`: the `E1` policy (3 retries, backoff plus jitter, `Retry-After`), with no fingerprint and no heal.
- [x] Wire everything into `Registry.call`.

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

- [x] An integration test per scenario, through `Registry.call` against the in-process mock:
  - `test_ac_06_m1_rename`
  - `test_ac_06_m2_type`
  - `test_ac_06_m3_response_nesting`
  - `test_ac_06_m4_oauth_header`
  - `test_ac_06_m5_ps_example`
  - `test_ac_08_m7_silent_ignore`
  - `test_ac_09_m8_no_safe_value` (also assert that no request carrying `priority` was sent)
  - `test_ac_10_c1_transient_c2_business`
- [x] `test_ac_11_tier0_repeat_and_restart` (S6): heal once, repeat (tier 0), recreate the registry from the same DB file, repeat again (tier 0).
- [x] Complete `test_ac_05_one_audit_event_per_attempt` across all scenarios.
- [x] Check that the final mock state is correct after each recovered scenario.
- [x] Check `test_ac_01`: `agent_schema` is byte-identical after all heals.
- [x] `metrics.py`: compute MTTR (by tier) and the heal counts from `heal_events`.

**Gate:** AC-1 to AC-13, AC-19 and AC-20 all pass in-process (AC-11 is S6; AC-12 and AC-19 are S7; AC-7 and AC-13 are re-gated against v3 in phase 12). Tier-1 heals take < 4 s locally. **Do not continue until this gate is green.**

---

## Phase 8: Demo-grade mock API

**Goal:** a running mock that the agents, benchmark and dashboard can drive over HTTP.

- [x] Run the mock with Uvicorn.
- [x] Admin endpoints:
  - activate a mutation by id,
  - reset (data plus mutation),
  - `GET /admin/state` for the data state,
  - list mutations.
- [x] `Idempotency-Key` handling on `create_ticket` (the same key returns the same ticket).
- [x] OAuth check for M4: `401` with `WWW-Authenticate: Bearer`; accept the configured bearer value.
- [x] Behavior for C1 (`503` twice, then OK) and C2 (`404` for user 999).
- [x] Rerun the phase 7 suite against the HTTP server (same tests, different transport).

**Gate:** the phase 7 suite passes over HTTP.

---

## Phase 9: Agents

**Goal:** a healing agent and a baseline agent, identical except for the registry.

- [x] `agents/shared`:
  - one system prompt (it includes: "if a tool returns `retry: false`, do not call it again with the same arguments; report the failure"; as built after 12D: on `SCHEMA_DRIFT_UNRECOVERABLE` the tool is unavailable for the rest of the task, report it as skipped and continue),
  - the demo task text,
  - the LLM config (same model, temperature 0). Current config: NVIDIA NIM's OpenAI-compatible API (`https://integrate.api.nvidia.com/v1`, `NVIDIA_API_KEY`), default `openai/gpt-oss-20b`, overridable with `LLM_MODEL`. [Model source](https://build.nvidia.com/openai/gpt-oss-20b).
- [x] `healing_agent.py`: LangGraph `create_react_agent` with framework tools generated from `registry` exports, executing via `Registry.call`. Structured errors are returned as the tool result.
- [x] `baseline_agent.py`: the same framework and tools generated from the v1 spec, executing as direct HTTP calls. The raw error JSON is returned as the tool result. Iteration cap 10.
- [x] `scripted.py`: a scripted no-LLM agent that runs the demo task as fixed tool calls through either path (the baseline re-sends a failing call with the same arguments until the cap). It allows keyless benchmark runs and paced demos.
- [x] Token accounting per run from the LLM usage metadata, and `call_events` logging for both agents.
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

- [x] Dashboard (FastAPI + one static HTML page, vanilla JS polling; it runs both agents and two isolated mock instances in one process):
  - two panes (healing vs baseline) with a live `call_events` stream,
  - Start (scripted), Start (LLM) and Reset controls,
  - mutation buttons (calls the mock admin endpoints),
  - patch log from `heal_events` (tier, fix operations, reason, MTTR),
  - metrics panel from the latest `report.md` data and live `heal_events`.
- [x] `demo.py`, a scripted 30-second flow:
  1. start both agents on the task,
  2. trigger M5 mid-run,
  3. baseline loops on `422`; the healing agent completes in about 2–3 s,
  4. trigger M3 or M4 on another tool,
  5. show the patch log,
  6. trigger M8 to show the clean refusal,
  7. show the metrics.
- [x] Run the full demo twice from a cold start.

**Gate:** AC-18 passes manually. **MVP was frozen here.** From this point only bug fixes to MVP code, plus the planned spec v3 alignment in phase 12.

---

## Phase 12: Spec v3 alignment

**Goal:** bring the built system in line with the revised `product.md`. The healing core stays. This phase adds the deterministic tie-breaker, makes Jev optional, tightens the safety rules, adds the new scenarios and redefines the metrics. Work the groups in order and keep the full suite green after each (`pytest -q`, `ruff check .`). Test names below are suggestions; each AC still needs a `test_ac_XX_*` test (`agent.md` §5).

### 12A. Tie-breaker, optional Jev, write-tool ambiguity (AC-7, AC-13, AC-27)

- [x] `candidates.py`: the deterministic tie-breaker for 2 or more candidates (FR-7.6). Score on (1) description match (a shared non-stopword token between the removed field's description in the base snapshot and the added field's description in the current spec), (2) parameter order, (3) type. A candidate wins only if it strictly beats every other. For a **write** tool, a win must include a description match. Descriptions are compared as tokens only (FR-8.8). Candidate order stays deterministic.
- [x] `heal.py`: decision order is candidates, then tie-breaker, then Jev, then abort. Call Jev only when there are 2 or more candidates, the tie-breaker found no unique winner and Jev is configured (FR-8.1).
- [x] Jev absent, timeout or error: abort `LOW_CONFIDENCE` before any request is sent, and record the `jev_unavailable` marker in the decision path (FR-8.3, FR-5.3). `JEV_UNAVAILABLE` stops being an abort reason; it survives only as the marker. Under S7, a `LOW_CONFIDENCE` that followed a Jev timeout or error is not negative-cached (FR-11.3).
- [x] Write-tool ambiguity (FR-8.6, FR-9.6): add an optional `preverify` entry to `config/tools.json` (a side-effect-free operation plus the expected result that distinguishes the chosen candidate). For a write tool with 2 or more candidates, accept only a tie-breaker win with description evidence, or a Jev choice at confidence ≥ 0.9 that `preverify` confirms before any write. Otherwise `LOW_CONFIDENCE`, nothing sent. Enforce it in `safety.py`.
- [x] Mock: M6-D (informative OpenAPI descriptions on the `set_manager` fields) and M6-N (descriptions absent or identical) (FR-12.6). If a side-effect-free operation can distinguish the correct M6-N assignment, expose it for `preverify`; whether one exists is an open question [A] (FR-12.9).
- [x] The audit decision path records whether the tie-breaker or Jev decided (FR-5.3).

**Tests:**
- `test_ac_27_tiebreaker_table`: M6-D yields exactly one winner, M6-N yields none, and on a write tool an order-only or type-only advantage is not a win.
- `test_ac_07_m6d_tiebreaker_no_jev_call`
- `test_ac_07_m6n_jev_confident_preverify_recovers` (Jev mocked)
- `test_ac_07_m6n_below_threshold_or_no_preverify_no_write` (final mock state unchanged)
- `test_ac_13_jev_down`: M1 to M5, M7 and M9 still heal; M6-N aborts `LOW_CONFIDENCE` within the deadline with no write; M6-D still heals.

### 12B. Classification and replay rules (AC-20, AC-21, AC-25)

- [x] `E3` (FR-10.1): return a structured error with reason `UNSUPPORTED_CLASS`, with exactly one audit event and no replay. Add the code to the `Reason` enum and to the S7 negative-cache set.
- [x] Value errors (FR-3.4). Normalize violation kinds from FastAPI `422` types (value kinds `format`, `range`, `pattern`, `enum`, `length`; structural kinds `missing`, `extra`, `type`) [A: mapping confirmed against the mock's `422` bodies]. An `E2` whose violations are all value kinds **and** whose spec diff is empty becomes `BUSINESS` with audit reason `NOT_DRIFT`: returned unchanged, no fix, no replay.
- [x] API-rollback rule (FR-3.4): an empty spec diff with structural violations means the request shape is wrong. With an active fix, that fix is stale: diagnose against the base schema, which yields the "no operations" candidate, and replay the base request once. With no active fix, abort `NO_CANDIDATE`. A mix of value and structural violations counts as structural.
- [x] Mock control C3 (FR-12.7): `update_email` validates the `email` value (format) and returns a FastAPI `422` value-error body for an invalid address, with the spec unchanged [A: demo tool].
- [x] Replay rule (FR-9.4) in `safety.py` and `heal.py`: `E2` is the only class that is replay-safe by itself. `E4` and `E6` replay only for an idempotent tool or with an `Idempotency-Key`; otherwise `UNSAFE_REPLAY`. `E5` is never replayed (response-side remap).

**Tests:**
- `test_ac_25_e3_unsupported_class`: a non-JSON fixture returns the structured error, writes one audit event and replays nothing.
- `test_ac_21_c3_value_error_not_drift`: `BUSINESS` / `NOT_DRIFT`, no fix built, no request replayed, error returned unchanged.
- `test_ac_20_replay_rule` with a fixture tool: `E4` or `E6` on a non-idempotent tool without a key aborts `UNSAFE_REPLAY`; `E4` on an idempotent tool, or with a key, is replayed.
- An API-rollback test (empty diff, structural violations, stale active fix), covering FR-3.4.

### 12C. M9, redaction, `spec_mode`, audit fields (AC-22, AC-23, AC-24)

- [x] Mutation M9 (request nesting): in the mock, `update_email` changes from the flat body `{user_id, email}` to `{payload:{user_id, email}}` (wrapping only: no rename, no type change, no header) [A: demo tool]. The candidate builder yields 1 candidate: `move` ×2. Add `test_ac_22_m9_request_nesting` (tier-1 heal on first occurrence, task completes, final mock state correct) and a candidate unit test.
- [x] Raw-error sanitizer (FR-5.7), applied before the blob is stored. Redact: values of `Authorization`, `Cookie`, `Set-Cookie`, API-key and token headers; any string equal to a configured secret (`OAUTH_BEARER`, `TENANT_ID`, `JEV_API_KEY`, the LLM key); bearer-token and JWT-shaped strings [A: pattern list]. Truncate to a maximum size [A]. Test `test_ac_24_raw_error_redacted` with fixtures that contain secrets.
- [x] `spec_mode` switch (FR-6.4): `on` or `off` in the settings module. With `off`, the Diagnoser runs in error-clue mode only.
- [x] Audit event gets `heal_ms` next to `mttr_ms` (FR-5.3, FR-15.4). Update the `heal_events` schema and the AC-5 schema check.

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

Two teams of one person each. Each person runs two machines, so four agents work in parallel. File ownership, branches and contracts are in `AGENTS.md` ("Two teams, four machines"). Kickoff prompts are in `team-prompts.md`. Every item starts with its FR and AC in `product.md` (`agent.md` invariant 10), one PR per item, with `pytest -q` and `ruff check .` clean.

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
| T1-6 | Mock drift MCP server | FR/AC first. `mock_api/mcp_drift_server.py` on the official `mcp` SDK, stdio and Streamable HTTP. Its tools mirror the REST mock (`get_user`, `create_order` and the rest). A control interface (contract 8) applies and resets mutations: rename tool, rename argument, retype argument, add required argument, change enum, and an M8-style unsafe change. A second instance with a different tool set covers the "2+ servers" case. | Each mutation changes `tools/list` and makes the old call fail; reset restores the original |
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
| T2-10 | Client guides | `docs/mcp-clients.md` from `tests/mcp/client-handoff.md`: Claude Desktop, Cursor, Windsurf, stdio and HTTP, plus how to add an upstream server | A fresh user connects a client by following the guide |
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
- Wahab reviews every contract change. The teammate reviews Team 1 PRs that touch a contract or a Team 2 file.

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

### Progress log: T1-PS2

| Date | Item | Status | Notes |
|---|---|---|---|
| 2026-10-15 | P3-2 | done | Healthy-call overhead (AC-28, FR-21.1): `bench/overhead.py` and `tests/p3/test_ac_28_healthy_overhead.py`; local run adds 0.3 ms p95 over the raw transport (n = 250 per side), under the 10 ms budget |
| 2026-10-15 | P3-3 | done | Swagger 2.0 loader (F22, AC-60 to AC-62): `src/healer/swagger2.py` (`convert` + `swagger2_source`), `mock_api/fixtures/swagger2.json`, `tests/p3/`; the 2.0 fixture converts to the mock's OpenAPI 3 `operations()` exactly (5 ops) and M1 heals when the base spec loads through `swagger2_source` |

### Progress log: T2-PS1

| Date | Item | Status | Notes |
|---|---|---|---|
| 2026-10-15 | P1-1 | implemented; packaging hand-off pending | Official MCP 2.x low-level stdio interface, frozen schemas, structured refusals, no list-change notifications; SDK memory and actual stdio subprocess tests, custom-spec healing and secret-leak regressions in `tests/mcp/`. Launch with `python -m healer.mcp_server`; P2 request: add `[project.scripts] healer-mcp = "healer.mcp_server:main"`. No P2-owned packaging edit made. |
| 2026-10-15 | P1-2 | done | Stateful Streamable HTTP shares one registry; loopback default, optional environment-selected bearer authentication on every method, explicit remote host allowlist and exact origins. SDK clients exercise the ASGI HTTP path without sockets, M1/M8 parity and five overlapping sessions producing one heal. `pytest -q`: 584 passed, 5 skipped; `ruff check .` clean. Remote deployment needs a trusted TLS reverse proxy. |
| 2026-10-16 | P1-3 | hand-off prepared; live acceptance pending | Client-specific stdio/HTTP snippets for P4 are in `tests/mcp/client-handoff.md`; existing opt-in config launcher is in `tests/mcp/test_client_config.py`. Final helper suppresses SDK diagnostic logs and discards child stderr to avoid secret leakage. Static review and lint only after user requested no further tests; final helper runtime validation, live configuration checks and P4 client UI checks remain pending. P2 console-entry request remains unchanged. |

### Progress log: T2-PS2

| Date | Item | Status | Notes |
|---|---|---|---|
| 2026-10-16 | T2-7 | done | Spec watcher (FR-18, AC-55): polls a `SpecSource` list on an interval, saves hash changes to `FixStore.save_spec`, calls `Healer.precompute(old, new)` only when the healer provides it (contract 5), injected clock/sleep, bounded per-source backoff, runs as a background task; tests in `tests/t2ps2/` |
| 2026-10-16 | T2-9 | partial | MCP front-door view (FR-20, AC-57): `GET /api/mcp` lists exactly the front door's `Registry.tools()` from a clean spec (name, description, frozen inputSchema), reports the stdio + Streamable HTTP (`/mcp`) transports, and reports no upstreams while `config/mcp_servers.json` is absent; new `mcp` tab in `index.html` plus the offline demo handler; `tests/dashboard/test_ac_57_mcp_view.py`. Deferred to dependencies: mutation buttons through contract 8 (T1-6), live per-call MCP traces and the upstream server list (T2-3/T2-5) |
| 2026-10-15 | P4-1 | done | AC-18 browser check: one-click mutation triggers verified (M5, M3, M8), live dual-pane updates confirmed, heal events logged in <1 s (M5 heal_ms=71ms/13ms, M3 heal_ms=13ms/7ms, M8 clean refusal ABORTED/NO_SAFE_VALUE in 12ms/34ms); two cold-start demo rehearsals passed cleanly (default config & without Jev) |
