# Technical Approach: Self-Healing Tool Registry (PS 01)

> How we build what `product.md` defines. Requirement IDs (FR-x, AC-x) refer to `product.md`. Build order: `plan.md`. **[A]** = assumption to confirm during the build.

---

## 1. Proposed Approach

We wrap every tool call in a registry that owns the tool definitions. Agents never call APIs directly.

1. **Freeze what the agent sees.** Tool definitions are generated from the v1 OpenAPI spec. The agent-facing schema never changes. The registry translates between that frozen shape and whatever the API currently accepts.
2. **Detect drift on every response.** Every response is normalized into one Outcome and classified as `OK`, `BUSINESS` or `E1`–`E6`. Some drift returns `200`, so the status code alone is not enough. The registry also checks the response against the output schema and runs the tool's postchecks.
3. **Diagnose from evidence.** The main evidence is a structural diff between the stored v1 spec and the API's current spec. The structured error body (FastAPI `422` `loc`/`type`) and the agent's original arguments are supporting evidence.
4. **Build fixes with deterministic code.** A small operation set (`move`, `cast`, `header`, `route`) expresses the four required mutations. The builder lists every valid fix. **Jev** is called only when more than one valid fix exists, and it only chooses among them.
5. **Prove before committing.** Each fix goes through a safety gate, one replay (or a local remap) and full re-verification. Only then is it stored and activated.
6. **Remember.** Fixes are stored by fingerprint as machine-readable data. A repeat of the same break is fixed from the store in milliseconds (tier 0).
7. **Stop safely.** When no safe fix exists, the agent gets a structured error with `retry: false`. Nothing is invented and nothing loops.

Why deterministic code instead of an LLM for healing:
- **Speed:** MTTR must be under 4 s.
- **Safety:** an LLM can invent values, which the problem statement explicitly forbids.
- **Auditability:** identical inputs always produce identical fixes.
- **Tokens:** the token-overhead metric rewards spending as few tokens as possible.

## 2. Technology Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Fastest path for agents, FastAPI and testing; async support |
| Mock API | FastAPI + Uvicorn | Emits an OpenAPI 3.1 spec automatically; default `422` bodies carry machine-readable `loc` and `type`, which serve as diagnosis clues |
| Mock API types | Pydantic v2, strict mode | Strict mode rejects `"123"` for an `int` field, so type changes show up as `422` instead of being coerced away |
| HTTP client | httpx (async) | Timeouts and `ASGITransport` for in-process tests with no network |
| Schema validation | `jsonschema` (Draft 2020-12) | OpenAPI 3.1 schemas are JSON Schema 2020-12, so one library validates both arguments and responses |
| Store | SQLite (stdlib `sqlite3`, WAL) | Zero setup, single file, durable. Enough for single-host volume (§3.3). |
| Classifier | Jev (TypeSafe AI, hosted) via httpx, `POST /v1/systemone` on TypeSafe or OpenRouter (`~typesafe/jev-latest`) | The Choice primitive returns a selected option with per-option probabilities and a confidence value. That is exactly the "pick one candidate" decision we need. |
| Agents | LangGraph `create_react_agent` + `langchain-openai` | The problem statement requires a baseline on a standard framework. Using the same framework for both agents isolates the registry as the only difference. A scripted, no-LLM agent (the demo task as fixed tool calls) is used for keyless benchmark runs and paced demos. |
| LLM | Claude via OpenRouter's OpenAI-compatible API, default `anthropic/claude-haiku-5.5`, temperature 0, same for both agents | A fair comparison at low cost; the model is set with `LLM_MODEL` |
| Dashboard | FastAPI + one static HTML page with vanilla JS polling | No extra dependency; the dashboard runs both agents and two isolated mock instances in one process |
| Tests | pytest, pytest-asyncio, respx | Async tests; respx mocks the Jev HTTP API |
| Lint/format | ruff | One tool |
| STRETCH | Strawberry + graphql-core; grpcio + grpcio-reflection + grpcio-status | GraphQL introspection and gRPC reflection provide the "current spec" for those protocols |

## 3. System Architecture

### 3.1 Components

| Component | Responsibility | Talks to |
|---|---|---|
| **OpenAPI Loader** | Fetches the spec, resolves `$ref`s into a self-contained schema per operation, canonicalizes it, hashes it | Mock API, Store |
| **Tool Registry** | Holds the in-memory tool definitions: `agent_schema` (frozen), `wire_schema` (current), `version`, `active_fix_id`, config (`idempotent`, `postchecks`). Exposes function-calling tools. Entry point `call(tool, args)`. | Adapter, Heal Controller |
| **REST Adapter** | Builds the request document (`body`, `query`, `header`, `route`) from the arguments using the base schema, applies the fix's `request_ops`, sends, normalizes the response into an Outcome | Mock API |
| **Detector** | Classifies Outcomes (FR-3), extracts violations, validates output against the agent output schema, runs postchecks | Registry, Heal Controller |
| **Fingerprinter** | Computes the stable break id (FR-4) | Heal Controller |
| **Heal Controller** | Runs tiers 0 and 1. Enforces the deadline, single-flight, the negative cache, one attempt per call, and commit/rollback. | All healing components |
| **Diagnoser** | Fetches the current spec, diffs the operation against the base snapshot, extracts error clues, falls back to error-clue mode | Mock API, Store |
| **Candidate Builder** | Turns the diff and clues into candidate fixes (FR-7) | Diagnoser output |
| **Jev Client** | Renders the diff and candidates into one Choice request; enforces the timeout and threshold | TypeSafe API |
| **Safety Gate** | Checks provenance, casts, operation count and replay safety (FR-9) | Heal Controller |
| **Op Interpreter** | Applies an operation list to a request or response document. It is pure and deterministic. | Adapter, Heal Controller |
| **Store** | SQLite tables plus the in-memory active-fix cache and the negative cache | Everything that persists |
| **Mock Drift API** | Four operations, the spec endpoint, the mutation switch, the state endpoint | Agents (through registry or direct), Benchmark, Dashboard |
| **Healing Agent / Baseline Agent** | Same framework, LLM and prompt. The healing agent's tools call `registry.call`; the baseline's tools call the API directly. | Mock API |
| **Benchmark Runner** | Runs scenarios × agents × N, checks the final state, computes metrics | Mock API admin, agents, Store |
| **Dashboard** | Live view of both agents, mutation buttons, patch log, metrics | Store, Mock API admin |

### 3.2 Request and response documents

All operations act on one document shape. Its path prefixes match FastAPI's `loc`, so error clues and fixes share one path vocabulary:

- request: `{"route": {"method", "path"}, "body": {...}, "query": {...}, "header": {...}}`
- response: the decoded JSON body, with paths relative to the body root.

The base request document is built from the agent's arguments using the **base** (v1) schema. Fixes are always applied to the base document (FR-7.5).

### 3.3 Data model (SQLite)

All columns read by code are machine-readable (FR-5.4). They hold enumerated codes, arrays, references, canonical JSON (sorted keys, no whitespace), sha256 hashes and epoch-ms integers.

| Entity | Purpose | Key fields |
|---|---|---|
| `spec_snapshots` | Each distinct spec version seen | `spec_hash` (pk), canonical spec JSON, `seen_ms` |
| `fixes` | One fix per fingerprint | `fix_id`, `fingerprint`, `signature` (canonical JSON), `tool`, `class`, `request_ops`, `response_ops`, `tier`, `source` (`diff`/`clue`/`jev`/`repair`), `schema_hash`, `dsl_version`, `status`, `wins`, `losses`, timestamps. At most one `active` fix per fingerprint. |
| `heal_events` | Audit log: one row per heal attempt | `ts_ms`, `tool`, `fingerprint`, `class`, `raw_code`, `tier`, `path`, `fix_id`, `outcome`, `reason`, `mttr_ms`, `jev_tokens`, `llm_tokens`, `raw_error` (opaque blob, never parsed by matching logic) |
| `call_events` | Every tool call by both agents, for the dashboard | `ts_ms`, `agent`, `run_id`, `tool`, `class`, `latency_ms` |
| STRETCH `rules`, `proposals` | Mined rules; tier-2 proposals for new operations | Abstract signature, operation template; structured proposal |

Example stored fix (for M5):

```json
{"fingerprint":"9f2c41d0a7b3e815",
 "signature":{"tool":"get_user","proto":"rest","class":"E2","code":"422",
              "v":[["req",["body","target"],"missing"],["req",["header","x-tenant-id"],"missing"]]},
 "dsl_version":1,
 "request_ops":[{"op":"move","from":["body","user_id"],"to":["body","target","id"]},
                {"op":"cast","path":["body","target","id"],"to":"int"},
                {"op":"header","name":"X-Tenant-Id","src":{"ref":"config","key":"TENANT_ID"}}],
 "response_ops":[],"tier":1,"source":"diff","status":"active","wins":1,"losses":0}
```

English appears only at runtime boundaries, and it is generated from this structure: the text sent to Jev, the agent's error message, and the dashboard labels. It is never stored as a source of truth.

## 4. End-to-End Workflow

### 4.1 Healthy call (most calls)

1. The agent calls `get_user({"user_id":"123"})`.
2. The registry validates the arguments against `agent_schema`. If they are invalid, it returns `AGENT_ARG_ERROR`.
3. The adapter builds the base document, applies `active_fix.request_ops` (if any) and sends.
4. The detector finds a `2xx` JSON response, applies `response_ops`, validates the output schema and runs the postchecks: `OK`.
5. The result goes back to the agent. Added overhead target: < 10 ms p95.

### 4.2 First-time break (tier 1), using M5

1. **t0:** the call starts. The API returns `422` with `body.target` missing and `header.x-tenant-id` missing. Class `E2`.
2. The fingerprint is computed, and the single-flight lock for it is taken. It is not in the negative cache and not in the store.
3. The diagnoser fetches `/openapi.json` and computes the diff:
   - `body.user_id` (str) removed,
   - `body.target.id` (int, required) added,
   - `header X-Tenant-Id` (required) added.
4. The candidate builder produces exactly one candidate:
   - `body.user_id` fills `target.id`: they share the token `id`, and `"123"` casts losslessly to `123`,
   - the header comes from the `header_sources` entry `X-Tenant-Id` (config key `TENANT_ID`).
5. With one candidate, Jev is not called. The safety gate passes all checks.
6. Replay is allowed because the class is `E2` (rejected, so nothing was executed). The patched request is re-sent once.
7. Verify: `200`, the output schema passes, and the postcheck `response.id == arg user_id` passes.
8. Commit:
   - insert the fix as `active` and cache it in memory,
   - update the tool definition (`wire_schema` = current spec, `version + 1`, `active_fix_id`),
   - write audit event `RECOVERED` with `mttr_ms`, synchronously.
9. **t1:** the result goes back to the agent. MTTR = t1 − t0. Target: under 4 s, expected about 0.1–0.3 s without Jev on a local mock [A].

### 4.3 Ambiguous break (tier 1 + Jev), using M6

The flow is the same as 4.2, but step 4 yields two type-compatible assignments with no name evidence:
- `user_id` to `subject`, `manager_id` to `supervisor`,
- the swapped assignment.

The Jev Client then:
1. sends one Choice request. The state is the rendered diff, including the OpenAPI field descriptions. The options are the two rendered candidates.
2. checks the response. `set_manager` is a write tool, so it requires confidence ≥ 0.9 [A]. A timeout or lower confidence aborts before any request is sent.

Steps 5–9 follow. The postchecks (`response.id == user_id`, `response.manager_id == manager_id`) catch a confident wrong pick (see §6.6).

### 4.4 Repeat break (tier 0)

The fingerprint matches an `active` fix in the in-memory cache. The controller skips diagnosis and goes straight to the safety gate, replay or remap, and verify. On success it increments `wins`; on failure it increments `losses` (the fix is retired at 2) and adds the fingerprint to the negative cache. Target: p95 < 0.5 s.

### 4.5 Recovery fails

Every abort ends the same way:
1. Write the audit event with its reason code.
2. Add the fingerprint to the negative cache for 60 s. This applies to `VERIFY_FAILED`, `POSTCHECK_FAILED_AFTER_WRITE`, `NO_CANDIDATE`, `NO_SAFE_VALUE`, `LOW_CONFIDENCE` and `UNSAFE_*`. The transient reasons `JEV_UNAVAILABLE` and `DEADLINE` are not cached (FR-11.3).
3. Release the single-flight lock.
4. Return `{error:"SCHEMA_DRIFT_UNRECOVERABLE", tool, class, fingerprint, reason, retry:false}`.

The agent's prompt tells it to stop calling that tool with the same arguments and to report the failure. The next identical call within 60 s fails immediately with `KNOWN_UNFIXABLE`, so there is no loop at either the registry or the agent level.

### 4.6 Transient and business errors

- `E1` (`5xx`, `429`, timeout): up to 3 retries with backoff of 100/200/400 ms plus jitter. No fingerprint and no heal.
- `409`: `BUSINESS`, returned unchanged.
- `404`: the diagnoser checks the current spec. If the route exists, the outcome is reclassified `BUSINESS` (audit `NOT_DRIFT`) and returned unchanged. Otherwise the error proceeds as drift with kind `route`.

## 5. Schema Drift Detection and Diagnosis

### 5.1 Detection order (per response)

| Step | Check | Class |
|---|---|---|
| 1 | Exception, timeout, `5xx`, `429` | `E1` |
| 2 | `409` | `BUSINESS` |
| 3 | Other `4xx` (`404` resolved in diagnosis) | `E2` |
| 4 | `Content-Type` is not JSON, or the body fails to parse | `E3` |
| 5 | `success:false`, `status` in (`error`, `fail`), or non-empty `error`/`errors` in a `2xx` body | `E4` |
| 6 | After `response_ops`, the body fails the agent output schema (`jsonschema`) | `E5` |
| 7 | A postcheck fails | `E6` |

**Postchecks** are declarative data in `config/tools.json`, not code:
- `echo` asserts that a response path equals a request argument (compared as canonical strings).
- `non_empty` asserts that a response path is present and non-empty.

They catch silent drift (M7) and wrong-but-accepted fixes (M6).

### 5.2 Spec diff

1. Match operations by `operationId`. A changed path or method for the same `operationId` is a route change.
2. Flatten the request into leaves `(path, type, required, description)`:
   - body properties under `["body", ...]`,
   - query parameters under `["query", ...]`,
   - header parameters and security schemes under `["header", ...]`.
3. Flatten the `2xx` response schema the same way, with paths relative to the body root.
4. The diff is a list of entries `{change: removed|added|type_changed|required_changed, path, type, required}`. The diff signature is the canonical JSON of these entries, without descriptions.

### 5.3 Handling each mutation

| Mutation | Evidence | Fix built |
|---|---|---|
| **Field rename** (M1: `user_id` becomes `customer_id`) | `422` missing `["body","customer_id"]`; diff shows `user_id` removed, `customer_id` added, same type | `move body.user_id to body.customer_id`. Name token `id` is shared, and there is one removed and one added field. |
| **Type conversion** (M2: `user_id` str becomes int) | `422` `int_type` at `["body","user_id"]`; diff shows `type_changed` | `cast body.user_id to int`, if `"123"` round-trips to `123`. Otherwise `UNSAFE_PATCH`. |
| **Response nesting** (M3: fields wrapped in `data`) | Output schema fails with `id`, `name`, `email` missing at the root; the response diff shows those leaves under `data` | Response `move data.id to id`, and the same for `name` and `email`. Applied locally to the received body; no replay. |
| **Mandatory header** (M4: OAuth bearer) | `401` with `WWW-Authenticate: Bearer`; the diff adds a bearer security requirement | `header Authorization` from `config:OAUTH_BEARER`. If the config key is absent: `NO_SAFE_VALUE`. |
| **Combined** (M5) | See §4.2 | `move` + `cast` + `header` |
| **Ambiguous rename** (M6) | Two removed and two added fields of the same type, with no shared tokens | Two candidates; Jev chooses |
| **Silent ignore** (M7) | `200` with the old email; the `echo` postcheck fails; the diff shows `email` removed and optional `email_address` added | `move body.email to body.email_address`. The tool is idempotent, so replay is allowed. |
| **Unsupported** (M8) | `422` missing `["body","priority"]`; no removed field or config source can fill it | No candidate: `NO_SAFE_VALUE` |

### 5.4 Error-clue mode (no spec available)

If the spec fetch fails or times out (500 ms [A]), the builder uses only the `422` violations and the original arguments:
- `missing` at path P is filled from an argument that shares a name token with P, or from the only argument that the base schema no longer explains.
- `int_type`/`string_type` at P becomes `cast`.
- A missing header becomes `header` if a config source exists.

Nested or combined changes need the spec, so in this mode they abort with `NO_CANDIDATE`. This limitation is accepted and documented.

## 6. Safe Patching Strategy

### 6.1 Operation DSL

The DSL has four operations (`move`, `cast`, `header`, `route`), versioned as `dsl_version` 1. The Op Interpreter:
- is pure (input document in, new document out; it never mutates in place),
- rejects unknown operations.

No operation writes a literal value. Values come from:
- an existing path (`move`),
- the same value converted (`cast`),
- a config reference (`header`),
- the current spec (`route`).

### 6.2 Safety gate (before anything is sent)

1. **Provenance:**
   - every `move` source exists in the base document,
   - every `header` key exists in config,
   - every `route` target and destination path exists in the current spec.
2. **Lossless cast:** `str(int(v)) == v`. The same round-trip rule applies to `float` and `bool`.
3. **Minimal diff:** the operation count is at most 3 × the number of violations or diff entries.
4. **Replay safety:** replay is allowed if the class is `E2`/`E4`, or the tool is `idempotent`, or the request has an `Idempotency-Key`. Otherwise the gate returns `UNSAFE_REPLAY`.
5. **Write threshold:** Jev confidence must be ≥ 0.9 for write tools and ≥ 0.5 for reads [A].

### 6.3 Validation

After the fix is applied, the full detection pipeline runs again, including the output schema and postchecks. Only `OK` counts as recovered.

### 6.4 Audit

Every heal attempt writes exactly one `heal_events` row, synchronously, before the agent receives anything. This is a trade-off: it adds about 1–5 ms per heal, and in exchange no patch can ever be applied without being logged (FR-5.5).

### 6.5 Bounded retries

| Mechanism | Bound |
|---|---|
| `E1` retries | 3, with backoff 100/200/400 ms + jitter |
| Heal attempts per call | 1 |
| Replays per heal | 1 |
| Heal deadline | 3.5 s; Jev 1.5 s; spec fetch 0.5 s [A]; replay ≤ 1.0 s |
| Negative cache | 60 s per failed fingerprint |
| Fix lifetime | Retired at 2 losses |
| Concurrency | Single-flight per fingerprint |

### 6.6 Uncertain changes

The system acts only when evidence is sufficient. When it is not, it stops:
- **0 candidates:** stop. Never ask a model to invent a value.
- **2+ candidates:** Jev chooses. Below the threshold, stop.
- **Confident but wrong on a write tool:** the postcheck detects it after the write. The system aborts with `POSTCHECK_FAILED_AFTER_WRITE` and flags a possible bad write in the audit, so it is loud, not silent. The 0.9 threshold for writes exists because of this case.
- **`E6` on a non-idempotent tool without a key:** the server may already have written, so the system refuses to replay (`UNSAFE_REPLAY`).

## 7. Baseline Comparison

| Control | Healing agent | Baseline agent |
|---|---|---|
| Framework | LangGraph `create_react_agent` (LLM mode) or the scripted agent (keyless mode) | Same |
| LLM and settings | Same model, temperature 0 | Same |
| System prompt and task | Same text | Same |
| Tools | Generated from the v1 spec, executed through `registry.call` | Generated from the v1 spec, executed by a direct HTTP call |
| Error handling | Structured result or `retry:false` error | Raw API error JSON returned as the tool result (framework default behavior) |
| Iteration cap | 10 [A] | 10 |
| Mock state | Reset before each run | Same |

Benchmark procedure per scenario:
1. Reset the mock.
2. Activate the mutation.
3. Run the agent on the demo task.
4. Record the tool-call events, tokens, outcome and final state.

The demo dashboard instead triggers the mutation mid-run, to show live recovery. Expected baseline behavior on M1–M5: repeated `422`/`401` until the iteration cap or task failure (AC-17).

## 8. Testing and Evaluation

### 8.1 Test layers

| Layer | Scope | Network |
|---|---|---|
| Unit | Op interpreter, safety gate, detector table, fingerprinter, spec diff, candidate builder, store | None |
| Integration | Registry + mock API in-process (`ASGITransport`) for every scenario M1–M8 and C1–C2; Jev mocked with respx (correct, wrong, low confidence, timeout) | None |
| Agent end-to-end | Both agents against the running mock API, with the real LLM and the real Jev | Yes |
| Benchmark | Scenarios × agents × N = 10 [A] | Yes |
| Robustness | Concurrency (AC-19), restart (AC-11), Jev down (AC-13), spec endpoint down (error-clue mode) | None |

Each acceptance criterion has a named test `test_ac_XX_*`.

### 8.2 Scenario matrix

All of M1–M8 and C1–C2 from `product.md` §7, run for both agents. Each M1–M5 scenario also runs again after the first heal and after a restart, to measure tier 0.

### 8.3 Metrics

| Metric | Definition | How it is measured |
|---|---|---|
| **Zero-Touch Adaptation Rate (ZTAR)** | Mutation runs where the task completed, the final mock state matched the expected state, and no human acted, divided by all mutation runs | The benchmark checks the agent outcome and `GET /admin/state`. Reported per scenario and overall (M1–M7, and with M8 included). |
| **MTTR** | Time from the start of the first failing call to the healed result being returned to the agent | `mttr_ms` in `heal_events`, from monotonic clock readings. Median and p95 per scenario, split by tier 0 and tier 1. |
| **Token Overhead** | Healing: (healed-run LLM tokens − clean-run median LLM tokens) + Jev tokens + tier-2 tokens. Baseline wasted tokens: mutated-run tokens − clean-run median tokens. | LLM usage metadata per run. Jev tokens come from the Jev response if it reports them; otherwise they are estimated from the rendered state and options [A]. Reported side by side, with the ratio. |

Expected result, to be verified rather than claimed: the healer replays transparently, so the agent's LLM never sees the break. Healing overhead should therefore come down to roughly the Jev tokens, which are zero for single-candidate breaks.

### 8.4 Reporting

The benchmark writes `results.jsonl` (one machine-readable row per run) and `report.md`. The report contains a per-scenario table with ZTAR, MTTR p50/p95, the tier and tokens for both agents, plus the baseline failure mode.

## 9. Implementation Phases

This summary follows `plan.md`, which has the full task lists. The registry and healing core come first. Agents, demo and stretch goals come after the core passes its integration suite.

| Phase | Output | Gate |
|---|---|---|
| 0 | Repo scaffold, config, test harness | `pytest` and `ruff` run |
| 1 | Core models, Op Interpreter, Safety Gate | Unit tests |
| 2 | OpenAPI Loader, Tool Registry, REST Adapter, minimal mock API (fixture) | AC-1, AC-2 |
| 3 | Detector with output schema and postchecks | AC-3 |
| 4 | Fingerprinter, Store, audit, negative cache | AC-4, AC-5 |
| 5 | Diagnoser (spec diff, error-clue mode), Candidate Builder | Unit tests |
| 6 | Jev Client, Heal Controller, `E1` retry policy | AC-7, AC-12, AC-13, AC-19, AC-20 |
| 7 | **Core integration suite (milestone)** | AC-6, AC-8 to AC-11 through the registry |
| 8 | Demo-grade mock API (admin, state, idempotency, OAuth) | Manual and integration |
| 9 | Healing and baseline agents, token accounting | Agent end-to-end |
| 10 | Benchmark runner and report | AC-14 to AC-17 |
| 11 | Dashboard and demo script | AC-18 (**MVP demo-ready**) |
| 12+ | STRETCH S1, S3, S2, S4, S5 | Only after phase 11 |

## 10. Risks, Limitations, and Trade-offs

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Jev access or API details differ from public coverage (early access since Sept 2026) | M6 cannot be demonstrated | Isolate Jev behind a client interface and mock it in tests. If unavailable, M6 aborts cleanly with `JEV_UNAVAILABLE` and every other scenario is unaffected. |
| Jev latency or outage during the live demo | A slow or failed M6 | 1.5 s timeout; run M6 last; benchmark numbers recorded in advance |
| LLM run-to-run variance | Noisy token and MTTR numbers | Temperature 0, N = 10, report median and p95 |
| The framework's default error handling differs from "return raw JSON" | Unfair baseline | Configure tool-error handling explicitly, identically except for the registry |
| Scope creep into GraphQL/gRPC | MVP not finished | STRETCH work starts only after the phase-11 gate |
| Pydantic lax coercion hides type changes | M2 not reproducible | Strict types in the mock |

### Limitations

- Fixes are limited to what the operation set can express. Value transforms (splitting a field, unit or format conversion) abort cleanly. They count against ZTAR, which is the correct outcome.
- Error-clue mode cannot repair nested or combined changes without a spec.
- `E6` detection depends on postchecks being declared per tool.
- A confident wrong Jev choice on a write tool is detected only after the write. It is flagged, not prevented.
- Single host only. Sharing fixes across instances needs Postgres (FUTURE).

### Trade-offs

| Decision | Chosen | Given up | Why |
|---|---|---|---|
| Healing engine | Deterministic code + Jev tie-break | LLM flexibility | Speed, safety and auditability. The LLM repair agent is STRETCH tier 2. |
| Agent schema | Frozen facade with translation | Agent seeing the new schema | No re-prompting and no token cost; the agent's plan stays valid |
| Attempts | One heal attempt per call | Some recoverable multi-step cases | Satisfies "stop once a patch fails" and guarantees no loops |
| Audit write | Synchronous | ~1–5 ms per heal | No unlogged patch is possible |
| Store | SQLite | Multi-host sharing | Zero setup; enough for the hackathon |
| Fix basis | Always relative to the base schema | Incremental stacking | Rollbacks and repeat mutations stay correct |
