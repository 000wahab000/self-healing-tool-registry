# Technical Approach: Self-Healing Tool Registry (PS 01)

> How we build what `product.md` defines. Requirement IDs (FR-x, AC-x) refer to `product.md`. Build order: `plan.md`. **[A]** = assumption to confirm during the build.

---

## 1. Proposed Approach

We wrap every tool call in a registry that owns the tool definitions. Agents never call APIs directly.

1. **Freeze what the agent sees.** Tool definitions are generated from the v1 OpenAPI spec. The agent-facing schema never changes. The registry translates between that frozen shape and whatever the API currently accepts.
2. **Detect drift on every response.** Every response is normalized into one Outcome and classified as `OK`, `BUSINESS` or `E1`–`E6`. Some drift returns `200`, so the status code alone is not enough. The registry also checks the response against the output schema and runs the tool's postchecks.
3. **Diagnose from evidence.** The main evidence is a structural diff between the stored v1 spec and the API's current spec. The structured error body (FastAPI `422` `loc`/`type`) and the agent's original arguments are supporting evidence.
4. **Build fixes with deterministic code.** A small operation set (`move`, `cast`, `header`, `route`) expresses the four required mutations. The builder lists every valid fix. With two or more, a deterministic tie-breaker (FR-7.6) picks a unique winner when the evidence allows. Only if it cannot, and only if Jev is configured, **Jev** (optional, F8) chooses among them. Jev never produces operations or values.
5. **Prove before committing.** Each fix goes through a safety gate, one replay (or a local remap) and full re-verification. Only then is it activated.
6. **Remember.** After a heal, the tool's in-memory definition carries the fix, so the same break does not recur in this process. Persisting fixes by fingerprint and reusing them across restarts (tier 0) is STRETCH (S6).
7. **Stop safely.** When no safe fix exists, the agent gets a structured error with `retry: false`. Nothing is invented and nothing loops. Errors that are not drift (value errors with an unchanged spec, missing records) are returned unchanged and never healed.

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
| Classifier (OPTIONAL) | Jev (TypeSafe AI, hosted) via httpx: `POST /v1/systemone` on TypeSafe (`JEV_API_KEY`), or `https://openrouter.ai/api/v1/systemone` with model `~typesafe/jev-latest` (`OPENROUTER_API_KEY`) | The Choice primitive returns a selected option with per-option probabilities and a confidence value. That is exactly the "pick one candidate" decision we need when the deterministic tie-breaker has no unique winner. Jev is optional: with no key configured every other MUST criterion still passes. |
| Agents | LangGraph `create_react_agent` + `langchain-openai` | The problem statement requires a baseline on a standard framework. Using the same framework for both agents isolates the registry as the only difference. A scripted, no-LLM agent (the demo task as fixed tool calls) is used for keyless benchmark runs and paced demos. In scripted mode the baseline re-sends a failing call with the same arguments until the iteration cap. |
| LLM | Claude via OpenRouter's OpenAI-compatible API (`OPENROUTER_API_KEY`), default `anthropic/claude-haiku-5.5`, temperature 0, same for both agents | A fair comparison at low cost; the model is set with `LLM_MODEL` |
| Dashboard | FastAPI + one static HTML page with vanilla JS polling | No extra dependency; the dashboard runs both agents and two isolated mock instances in one process |
| Tests | pytest, pytest-asyncio, respx | Async tests; respx mocks the Jev HTTP API |
| Lint/format | ruff | One tool |
| STRETCH | Strawberry + graphql-core; grpcio + grpcio-reflection + grpcio-status | GraphQL introspection and gRPC reflection provide the "current spec" for those protocols |

## 3. System Architecture

### 3.1 Components

| Component | Responsibility | Talks to |
|---|---|---|
| **OpenAPI Loader** | Fetches the spec, resolves `$ref`s into a self-contained schema per operation, canonicalizes it, hashes it | Mock API, Store |
| **Tool Registry** | Holds the in-memory tool definitions: `agent_schema` (frozen), `wire_schema` (current), `version`, `active_fix_id`, config (`idempotent`, `postchecks`, optional `preverify`). Exposes function-calling tools. Entry point `call(tool, args)`. | Adapter, Heal Controller |
| **REST Adapter** | Builds the request document (`body`, `query`, `header`, `route`) from the arguments using the base schema, applies the fix's `request_ops`, sends, normalizes the response into an Outcome | Mock API |
| **Detector** | Classifies Outcomes (FR-3), extracts violations, validates output against the agent output schema, runs postchecks | Registry, Heal Controller |
| **Fingerprinter** | Computes the stable break id (FR-4) | Heal Controller |
| **Heal Controller** | Runs tier 1 (and tier 0 under S6). Enforces the deadline, one attempt per call, and commit/rollback. Under S7 also the single-flight lock and the negative cache. | All healing components |
| **Diagnoser** | Fetches the current spec, diffs the operation against the base snapshot, extracts error clues, falls back to error-clue mode (spec fetch failure, or `spec_mode` set to `off`, FR-6.4). Reclassifies `404` and value errors with an empty spec diff to `BUSINESS`. | Mock API, Store |
| **Candidate Builder** | Turns the diff and clues into candidate fixes (FR-7.1 to 7.5) and runs the deterministic tie-breaker when there are 2 or more (FR-7.6) | Diagnoser output |
| **Jev Client (OPTIONAL)** | Called only when the tie-breaker finds no unique winner and Jev is configured. Renders the diff and candidates into one Choice request; enforces the timeout and threshold. Jev being absent, slow or low-confidence ends in `LOW_CONFIDENCE` (decision-path marker `jev_unavailable` when it failed). | TypeSafe API or OpenRouter |
| **Safety Gate** | Checks provenance, casts, operation count, replay safety and the write-tool ambiguity rule (FR-9) | Heal Controller |
| **Op Interpreter** | Applies an operation list to a request or response document. It is pure and deterministic. | Adapter, Heal Controller |
| **Store** | SQLite (WAL) for audit events; sanitizes the raw error blob before it is written (FR-5.7). The in-memory active-fix cache is kept in the MVP. Under S6 it also persists fixes and spec snapshots; under S7 it holds the negative cache. | Everything that persists |
| **Mock Drift API** | Four operations, the spec endpoint, the mutation switch (M1–M9 with M6-D/M6-N, controls C1–C3; M10 under S8), the state endpoint | Agents (through registry or direct), Benchmark, Dashboard |
| **Healing Agent / Baseline Agent** | Same framework, LLM and prompt. The healing agent's tools call `registry.call`; the baseline's tools call the API directly. A scripted no-LLM agent runs the same task as fixed tool calls for keyless benchmark runs. | Mock API |
| **Benchmark Runner** | Runs scenarios × agents × N, checks the final state, computes the metrics (FR-15.4), runs the clean runs and the error-only ablation | Mock API admin, agents, Store |
| **Dashboard** | FastAPI service plus one static HTML page: live view of both agents, mutation buttons, patch log, metrics | Store, Mock API admin |

### 3.2 Request and response documents

All operations act on one document shape. Its path prefixes match FastAPI's `loc`, so error clues and fixes share one path vocabulary:

- request: `{"route": {"method", "path"}, "body": {...}, "query": {...}, "header": {...}}`
- response: the decoded JSON body, with paths relative to the body root.

The base request document is built from the agent's arguments using the **base** (v1) schema. Fixes are always applied to the base document (FR-7.5).

### 3.3 Data model (SQLite)

All columns read by code are machine-readable (FR-5.4). They hold enumerated codes, arrays, references, canonical JSON (sorted keys, no whitespace), sha256 hashes and epoch-ms integers.

In the MVP the required persistent data is the audit log, `heal_events` (FR-5.1); `call_events` only serves the dashboard. Active fixes are held in the in-memory cache. The `spec_snapshots` and `fixes` tables, and reloading them at startup, are STRETCH (S6).

| Entity | Purpose | Key fields |
|---|---|---|
| `spec_snapshots` (S6 to persist) | Each distinct spec version seen. In the MVP snapshots are kept in memory (FR-6.3). | `spec_hash` (pk), canonical spec JSON, `seen_ms` |
| `fixes` (S6 to persist) | One fix per fingerprint | `fix_id`, `fingerprint`, `signature` (canonical JSON), `tool`, `class`, `request_ops`, `response_ops`, `tier`, `source` (`diff`/`clue`/`jev`/`repair`), `schema_hash`, `dsl_version`, `status` (`candidate`/`active`/`failed`/`retired`), `wins`, `losses` (used only under S6), timestamps. At most one `active` fix per fingerprint. |
| `heal_events` | Audit log: exactly one row per heal attempt, including refused and aborted ones (FR-5.3) | `ts_ms`, `tool`, `fingerprint`, `class`, `raw_code`, `tier`, `path` (decision path: whether the tie-breaker or Jev decided, with a `jev_unavailable` marker when Jev failed), `fix_id`, `outcome`, `reason`, `mttr_ms`, `heal_ms` (see §8.3), `jev_tokens` (separate from `llm_tokens`, FR-8.7), `llm_tokens`, `raw_error` (sanitized per FR-5.7; opaque blob, never parsed by matching logic and never passed to a model) |
| `call_events` | Every tool call by both agents, for the dashboard | `ts_ms`, `agent`, `run_id`, `tool`, `class`, `latency_ms` |
| STRETCH `rules`, `proposals` | Mined rules; tier-2 proposals for new operations | Abstract signature, operation template; structured proposal |

Example fix record (for M5). It is held in memory; it is written to the store only under S6:

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
2. The fingerprint is computed. The tool's in-memory definition carries no fix for this break, so diagnosis (tier 1) runs. (Under S7 the negative cache is checked and the single-flight lock is taken first; under S6 the store is checked for a tier-0 fix.)
3. The diagnoser fetches `/openapi.json` and computes the diff:
   - `body.user_id` (str) removed,
   - `body.target.id` (int, required) added,
   - `header X-Tenant-Id` (required) added.
4. The candidate builder produces exactly one candidate:
   - `body.user_id` fills `target.id`: they share the token `id`, and `"123"` casts losslessly to `123`,
   - the header comes from the `header_sources` entry `X-Tenant-Id` (config key `TENANT_ID`).
5. With one candidate, neither the tie-breaker nor Jev is needed. The safety gate passes all checks.
6. Replay is allowed because the class is `E2` (rejected, so nothing was executed). The patched request is re-sent once.
7. Verify: `200`, the output schema passes, and the postcheck `response.id == arg user_id` passes.
8. Commit:
   - record the fix as `active` and cache it in memory (written to the store only under S6),
   - update the tool definition (`wire_schema` = current spec, `version + 1`, `active_fix_id`),
   - write audit event `RECOVERED` with `mttr_ms` and `heal_ms`, synchronously.
9. **t1:** the result goes back to the agent. MTTR runs from the first failing response caused by the mutation to this first verified-correct result; `heal_ms` is the registry's own time from failure detection to the returned result (§8.3). Target: tier-1 MTTR p95 under 4 s, expected about 0.1–0.3 s without Jev on a local mock [A].

### 4.3 Ambiguous break (tie-breaker, then optional Jev), using M6

The flow is the same as 4.2, but step 4 yields two type-compatible assignments with no name evidence (`user_id`, `manager_id` become `subject`, `supervisor`, with no shared name tokens):
- `user_id` to `subject`, `manager_id` to `supervisor`,
- the swapped assignment.

`set_manager` is a **write** tool, so the ambiguity rule (FR-8.6, FR-9.6) applies. M6 runs in two mock configurations (FR-12.6):

**M6-D (informative OpenAPI descriptions).**
1. The deterministic tie-breaker (FR-7.6) scores each candidate on three pieces of evidence already in hand: description match (a shared non-stopword token between the removed field's description in the base snapshot and the added field's description in the current spec), parameter order, and type.
2. One candidate strictly beats the other, and its win includes a description match, as a write tool requires. It is selected.
3. Jev is not called. Steps 5–9 of 4.2 follow.

**M6-N (descriptions absent or identical).**
1. The tie-breaker finds no unique winner; the candidates stay tied.
2. If Jev is configured, the Jev Client sends one Choice request. The state is the rendered diff, including the OpenAPI field descriptions, rendered as data. The options are the two rendered candidates. Jev returns only an index and a confidence.
3. A write tool accepts the choice only if confidence is ≥ 0.9 [A] **and** a read-only `preverify` from the tool config confirms the chosen candidate before anything is written (FR-8.6). Low confidence, no `preverify`, or no confirmation: abort `LOW_CONFIDENCE`, and nothing is sent.
4. If Jev is not configured, times out (1.5 s) or errors, there is no decision. The heal aborts with `LOW_CONFIDENCE` before any request is sent, and the decision path records `jev_unavailable`. `JEV_UNAVAILABLE` is not an abort reason.

If a choice is accepted, steps 5–9 follow. The postchecks (`response.id == user_id`, `response.manager_id == manager_id`) catch a wrong pick that `preverify` could not distinguish (see §6.6). Whether the mock can offer a side-effect-free operation that distinguishes the correct M6-N assignment is an open question [A] (FR-12.9).

### 4.4 Repeat break (in-memory fix, and tier 0 under S6)

**MVP.** After the first heal, the tool's in-memory definition carries the fix (`active_fix_id`, `wire_schema`). Later calls apply it at step 3 of the call, so the same break does not recur in this process.

**STRETCH (S6, tier 0).** The fingerprint matches an `active` fix in the store or its in-memory cache, including after a restart. The controller skips diagnosis and goes straight to the safety gate, replay or remap, and verify. On success it increments `wins`; on failure it increments `losses` (the fix is retired at 2) and, under S7, adds the fingerprint to the negative cache. Target: p95 < 0.5 s.

### 4.5 Recovery fails

Every abort ends the same way:
1. Roll back: discard the fix and leave the tool definition unchanged.
2. Write the audit event with its reason code.
3. (STRETCH, S7) Add the fingerprint to the negative cache for 60 s. This applies to `VERIFY_FAILED`, `POSTCHECK_FAILED_AFTER_WRITE`, `NO_CANDIDATE`, `NO_SAFE_VALUE`, `LOW_CONFIDENCE`, `UNSAFE_PATCH`, `UNSAFE_REPLAY` and `UNSUPPORTED_CLASS`. The transient reasons are not cached: `DEADLINE`, and a `LOW_CONFIDENCE` that followed a Jev timeout or error (FR-11.3). Also under S7, release the single-flight lock.
4. Return `{error:"SCHEMA_DRIFT_UNRECOVERABLE", tool, class, fingerprint, reason, retry:false}`.

The agent's prompt tells it to stop calling that tool with the same arguments and to report the failure. Without S7, loop prevention rests on one heal attempt per call, the `retry: false` instruction and the agent's iteration cap. With S7, the next identical call within 60 s fails immediately with `KNOWN_UNFIXABLE`, so there is no loop at the registry level either.

### 4.6 Transient, business and not-drift errors

- `E1` (`5xx`, `429`, timeout): up to 3 retries with backoff of 100/200/400 ms plus jitter. No fingerprint and no heal.
- `409`: `BUSINESS`, returned unchanged.
- `404`: the diagnoser checks the current spec. If the route exists, the outcome is reclassified `BUSINESS` (audit `NOT_DRIFT`) and returned unchanged. Otherwise the error proceeds as drift with kind `route`.
- **Value error (C3, FR-3.4):** an `E2` whose violations are all value errors (kind `format`, `range`, `pattern`, `enum` or `length`) **and** whose spec diff for the operation is empty is not drift. It is reclassified `BUSINESS` with audit reason `NOT_DRIFT` and returned to the agent unchanged, with no fix and no replay.
- **Undecodable body (`E3`):** not healed in the MVP. The Outcome is returned as a structured error with reason `UNSUPPORTED_CLASS`, with one audit event and no replay (FR-10.1). Loading the current spec and re-sending is FUTURE.

## 5. Schema Drift Detection and Diagnosis

### 5.1 Detection order (per response)

| Step | Check | Class |
|---|---|---|
| 1 | Exception, timeout, `5xx`, `429` | `E1` |
| 2 | `409` | `BUSINESS` |
| 3 | Other `4xx` (`404` resolved in diagnosis). An `E2` with only value-error violations and an empty spec diff is reclassified `BUSINESS` / `NOT_DRIFT` (FR-3.4). | `E2` |
| 4 | `Content-Type` is not JSON, or the body fails to parse. Not healed in the MVP: structured error `UNSUPPORTED_CLASS`. | `E3` |
| 5 | `success:false`, `status` in (`error`, `fail`), or non-empty `error`/`errors` in a `2xx` body | `E4` |
| 6 | After `response_ops`, the body fails the agent output schema (`jsonschema`) | `E5` |
| 7 | A postcheck fails | `E6` |

**Postchecks** are declarative data in `config/tools.json`, not code:
- `echo` asserts that a response path equals a request argument (compared as canonical strings).
- `non_empty` asserts that a response path is present and non-empty.

They catch silent drift (M7) and wrong-but-accepted fixes (M6). `E6` can be detected only where a tool declares postchecks (FR-3.5); a tool without them cannot detect silent drift. This is accepted and stated in the write-up.

A tool may also declare a **`preverify`** (FR-8.6): a declarative entry naming a side-effect-free operation (a lookup, a dry run or a validation-only endpoint) and an expected result that distinguishes the chosen candidate from the alternatives. It is used only to confirm a Jev choice on a write tool before anything is written. Which mock tools can offer one is open [A].

Violation kinds are normalized from FastAPI `422` types (for example `string_pattern_mismatch`, `greater_than`, `enum`, `value_error`). The **value kinds** are `format`, `range`, `pattern`, `enum` and `length`; the **structural kinds** are `missing`, `extra` and `type` [A: the mapping is confirmed against the mock's actual `422` bodies].

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
| **Ambiguous rename** (M6) | Two removed and two added fields of the same type, with no shared tokens | Two candidates. **M6-D** (informative descriptions): the tie-breaker (FR-7.6) selects one, no Jev call. **M6-N** (no usable descriptions): no unique winner; optional Jev chooses at the write threshold and a confirming `preverify`, otherwise `LOW_CONFIDENCE`. See §4.3. |
| **Silent ignore** (M7) | `200` with the old email; the `echo` postcheck fails; the diff shows `email` removed and optional `email_address` added | `move body.email to body.email_address`. The tool is idempotent, so replay is allowed. A removed field plus an added **optional** field is a candidate only with name evidence, a type match or lossless cast, and a failure pointing at the removed field (FR-7.2). |
| **Unsupported** (M8) | `422` missing `["body","priority"]`; no removed field or config source can fill it | No candidate: `NO_SAFE_VALUE` |
| **Request nesting** (M9, `update_email`) | The flat body `{user_id, email}` becomes `{payload:{user_id, email}}`: wrapping only, no rename, no type change, no header [A: demo tool] | `move` ×2, one per leaf, from the flat position into `body.payload` |
| **Value error** (C3, `update_email`) | `422` value error (kind `format`) for an invalid address such as `not-an-email`; the spec is unchanged | No fix. Reclassified `BUSINESS` / `NOT_DRIFT` and returned unchanged (FR-3.4). |
| **Injection** (M10, STRETCH S8) | M1's rename, with injected instructions in the `422` `msg` and in the new field's OpenAPI description | The same `move` as M1. Nothing is derived from the injected text (FR-8.8); the property is enforced by the provenance rules and M10 only demonstrates it. |

**Empty spec diff with structural violations (FR-3.4).** When the diff for the operation is empty but the violations are of kind `missing`, `extra` or `type`, the request shape is wrong, not the value. This is the "API rolled back to v1" pattern. If a fix is active for the tool, that fix is stale: diagnose against the base schema, which yields the "no operations" candidate, and replay the base request once. If no fix is active, the spec does not explain the rejection and the heal aborts `NO_CANDIDATE`. A mix of value and structural violations is treated as structural.

### 5.4 Error-clue mode (no spec available)

Error-clue mode is used when the spec fetch fails or times out (500 ms [A]), or when the `spec_mode` configuration switch is `off` (FR-6.4). The benchmark uses `off` for the error-only ablation (FR-15.7). The builder then uses only the `422` violations and the original arguments:
- `missing` at path P is filled from an argument that shares a name token with P, or from the only argument that the base schema no longer explains.
- `int_type`/`string_type` at P becomes `cast`.
- A missing header becomes `header` if a config source exists.

Nested or combined changes need the spec, so in this mode they abort with `NO_CANDIDATE` (for example M5 and M9 are expected to). This limitation is accepted and documented; the ablation reports, per mutation, whether it healed or aborted and with which reason.

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
3. **Minimal diff:** the operation count is at most 3 × the number of violations or diff entries [A].
4. **Replay safety (FR-9.4):** replay is allowed only if the class is `E2` (the server rejected the request, so nothing was executed), or the tool is `idempotent`, or the request has an `Idempotency-Key`. Otherwise the gate returns `UNSAFE_REPLAY`. So `E2` is the only class that is replay-safe by itself. `E4` (an error inside a `2xx`) and `E6` (a `2xx` that ignored the input) mean the server accepted the request and may already have written something, so they replay only for an idempotent tool or with a key. `E5` is never replayed: it is a response-side remap of the body already received.
5. **Jev threshold:** Jev confidence must be ≥ 0.9 for write tools and ≥ 0.5 for reads [A]. Below it, abort `LOW_CONFIDENCE`.
6. **Write-tool ambiguity (FR-9.6, FR-8.6):** for a write tool with 2 or more candidates, reject the fix unless the tie-breaker selected exactly one candidate with description evidence, or the Jev choice meets the write threshold **and** the tool's read-only `preverify` confirms the chosen candidate before any write is sent. Otherwise abort `LOW_CONFIDENCE` and send nothing.
7. **Unknown operation names** reject the fix (FR-9.5).

### 6.3 Validation

After the fix is applied, the full detection pipeline runs again, including the output schema and postchecks. Only `OK` counts as recovered.

### 6.4 Audit

Every heal attempt writes exactly one `heal_events` row, synchronously, before the agent receives anything. This is a trade-off: it adds about 1–5 ms per heal, and in exchange no patch can ever be applied without being logged (FR-5.5).

The raw error blob is **sanitized before it is stored** (FR-5.7). Redacted: the values of `Authorization`, `Cookie`, `Set-Cookie`, API-key and token headers; any string equal to the value of a configured secret (for example `OAUTH_BEARER`, `TENANT_ID`, `JEV_API_KEY`, the LLM key); and bearer-token and JWT-shaped strings [A: pattern list]. The blob is truncated to a maximum size [A]. It stays opaque: matching logic never parses it and no model ever sees it.

### 6.5 Bounded retries

| Mechanism | Bound |
|---|---|
| `E1` retries | 3, with backoff 100/200/400 ms + jitter |
| Heal attempts per call | 1 |
| Replays per heal | 1 |
| Heal deadline | 3.5 s; Jev 1.5 s; spec fetch 0.5 s [A]; replay ≤ 1.0 s |
| Negative cache (STRETCH, S7) | 60 s per failed fingerprint |
| Fix lifetime (STRETCH, S6) | Retired at 2 losses |
| Concurrency (STRETCH, S7) | Single-flight per fingerprint. Without S7, each concurrent call heals at most once and each result is verified. |

Without S7, loop prevention rests on one heal attempt per call, the `retry: false` instruction to the agent (FR-11.5) and the agent's iteration cap.

### 6.6 Uncertain changes

The system acts only when evidence is sufficient. When it is not, it stops:
- **Not drift:** a `409`, a `404` for a record whose route is still in the spec, and a value error with an empty spec diff are `BUSINESS`. They are returned unchanged and never healed.
- **0 candidates:** stop. Never ask a model to invent a value.
- **2+ candidates:** the deterministic tie-breaker (FR-7.6) selects a candidate only if it strictly beats all others on description match, parameter order and type. With no unique winner, optional Jev chooses; below the threshold, or with Jev absent or failed, stop with `LOW_CONFIDENCE`.
- **Write tools with 2+ candidates (FR-8.6, FR-9.6):** proceed only on a tie-breaker win that includes description evidence, or on a Jev choice at the write threshold that a read-only `preverify` confirms. No `preverify`, or no confirmation: `LOW_CONFIDENCE`, nothing sent.
- **Wrong choice that `preverify` cannot distinguish:** the postcheck detects it after the write. The system aborts with `POSTCHECK_FAILED_AFTER_WRITE` and flags a possible bad write in the audit, so it is loud, not silent. This is the residual risk; the 0.9 threshold and `preverify` exist to make it rare.
- **`E4` or `E6` on a non-idempotent tool without a key:** the server may already have written, so the system refuses to replay (`UNSAFE_REPLAY`).
- **Untrusted text:** error bodies and OpenAPI descriptions are data. No value, field name, header or operation is derived from their wording; they are only matched against the spec structure and compared as tokens (FR-8.8).

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

The demo dashboard instead triggers the mutation mid-run, to show live recovery. The baseline's outcome (error loop, number of calls, tokens, final data correctness) is measured and reported for every scenario, not asserted as pass or fail (FR-15.8, AC-17). In the scripted benchmark run recorded in `bench/report.md` (N = 3), the baseline hit the iteration cap on M1, M2, M4 and M5 and ended incomplete on M7, but completed M3; those are measured facts for that mode, not an expectation for LLM mode.

## 8. Testing and Evaluation

### 8.1 Test layers

| Layer | Scope | Network |
|---|---|---|
| Unit | Op interpreter, safety gate, detector table, fingerprinter, spec diff, candidate builder, tie-breaker table (AC-27), raw-error redaction (AC-24), store | None |
| Integration | Registry + mock API in-process (`ASGITransport`) for every scenario M1–M9 (M6 as M6-D and M6-N) and C1–C3, plus an `E3` fixture (AC-25) and a replay-rule fixture tool (AC-20); M10 under S8. Jev mocked with respx (correct, wrong, low confidence, timeout, absent) | None |
| Agent end-to-end | Both agents against the running mock API, with the real LLM and the real Jev | Yes |
| Benchmark | Scenarios × agents × N = 10 [A], in LLM mode or in scripted (keyless) mode | LLM mode: yes. Scripted mode: no LLM. |
| Robustness | Jev down (AC-13), spec endpoint down (error-clue mode, the error-only ablation, AC-23); under S6 restart (AC-11); under S7 concurrency (AC-19) and the negative cache (AC-12) | None |

Each acceptance criterion has a named test `test_ac_XX_*`.

### 8.2 Scenario matrix

All of M1–M9 (M6 in both configurations, M6-N with and without Jev) and C1–C3 from `product.md` §7, run for both agents. M10 is added under S8. Each M1–M5 scenario also runs again after the first heal; under S6 it also runs after a restart, to measure tier 0. Two further runs: clean runs with no mutation (FR-15.6) and the error-only ablation of M1–M9 with the spec endpoint disabled (FR-15.7).

### 8.3 Metrics

Definitions follow FR-15.4.

| Metric | Definition | How it is measured |
|---|---|---|
| **Zero-Touch Adaptation Rate (ZTAR)** | Over runs of the **healable** mutations only (M1 to M5, M7, M9): the share where the task completed, the final mock state matched the expected state, and no human acted. M6 (both configurations, with and without Jev) and M10 (S8) are reported separately. | The benchmark checks the agent outcome and `GET /admin/state`. Reported per scenario and overall. Target: 100% with Jev absent (AC-15). |
| **Safe-Refusal Rate** | Over **must-refuse** runs (M8, and M6-N with Jev disabled): the share that aborted with the expected reason code and sent no request carrying an invented value | Expected reason `NO_SAFE_VALUE` for M8 and `LOW_CONFIDENCE` for M6-N. Target: 100% (AC-15). |
| **False-Patch Rate** | The share of healed runs (a fix passed verification and the result was returned as success) whose final mock state was wrong | Final-state check on every run. Target: 0, including in the error-only ablation. |
| **MTTR** | Time from the **first failing response caused by the mutation** to the **first verified-correct result** returned to the agent, on a monotonic clock | Median and p95 per scenario, split by tier. The registry's internal **heal time** (`heal_ms`, from failure detection to the returned result) is recorded in `heal_events` and reported separately (AC-14). |
| **Token Overhead** | Healing agent: its total tokens for the task on a mutated run minus its median total tokens for the same task on clean runs. Baseline: the same subtraction gives its **wasted tokens**. | LLM usage metadata per run. Healing overhead and baseline waste are reported side by side with their ratio. `jev_tokens` is the classifier's own usage (or an estimate [A]); it is reported in a separate column and never added to `llm_tokens` (FR-8.7). |

Every timing and token metric is reported as mean, median and p95, per scenario (FR-15.5).

Expected result, to be verified rather than claimed: the healer replays transparently, so the agent's LLM never sees the break. Healing overhead should therefore be close to zero for tool breaks that need no Jev call, and `jev_tokens` is zero whenever the tie-breaker or a single candidate decides. Scripted mode makes no LLM calls (its `llm_tokens` are 0), so token overhead can be measured only in LLM mode.

### 8.4 Reporting

The benchmark writes `results.jsonl` (one machine-readable row per run) and `report.md`. The report contains a per-scenario table with ZTAR, MTTR p50/p95 (and `heal_ms`), the tier and tokens for both agents, plus the baseline failure mode; Safe-Refusal Rate and False-Patch Rate; the `jev_tokens` column; and the error-only ablation table (per mutation: healed or aborted, with the reason code; no pass threshold, FR-15.7). The report states whether the run was in scripted or LLM mode.

## 9. Implementation Phases

This summary follows `plan.md`, which has the full task lists. The registry and healing core come first. Agents, demo and stretch goals come after the core passes its integration suite. Phases 0–11 are built. Phase 12 brings the build in line with the current spec (`product.md` v3).

| Phase | Output | Gate |
|---|---|---|
| 0 | Repo scaffold, config, test harness | `pytest` and `ruff` run |
| 1 | Core models, Op Interpreter, Safety Gate | Unit tests |
| 2 | OpenAPI Loader, Tool Registry, REST Adapter, minimal mock API (fixture) | AC-1, AC-2 |
| 3 | Detector with output schema and postchecks | AC-3 |
| 4 | Fingerprinter, Store, audit; fix store and negative cache (S6/S7, built here) | AC-4, AC-5 |
| 5 | Diagnoser (spec diff, error-clue mode), Candidate Builder | Unit tests |
| 6 | Jev Client, Heal Controller, `E1` retry policy | AC-7, AC-13, AC-20 (AC-12 and AC-19 under S7) |
| 7 | **Core integration suite (milestone)** | AC-6, AC-8 to AC-10 through the registry (AC-11 under S6) |
| 8 | Demo-grade mock API (admin, state, idempotency, OAuth) | Manual and integration |
| 9 | Healing and baseline agents (LLM and scripted), token accounting | Agent end-to-end |
| 10 | Benchmark runner and report | AC-14 to AC-17 |
| 11 | Dashboard and demo script | AC-18 (**MVP demo-ready**) |
| 12 | **Spec v3 alignment:** tie-breaker, optional Jev, write-tool ambiguity, `UNSUPPORTED_CLASS`, `NOT_DRIFT`, M6-D/M6-N, M9, C3, replay rule, redaction, `spec_mode`, new metrics and ablation | AC-7, AC-13, AC-15, AC-16, AC-17, AC-20 to AC-25, AC-27 |
| 13+ | STRETCH S1, S3, S2, S4, S5, S8 (S6 and S7 are already built) | Only after phase 12 |

## 10. Risks, Limitations, and Trade-offs

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Jev access or API details differ from public coverage (early access since Sept 2026) | M6-N cannot be demonstrated with a Jev choice | Jev is optional (F8). Isolate it behind a client interface and mock it in tests. If unavailable, M6-N aborts cleanly with `LOW_CONFIDENCE` (decision path `jev_unavailable`), M6-D still heals through the tie-breaker, and every other scenario is unaffected. |
| Jev latency or outage during the live demo | A slow or failed M6-N | 1.5 s timeout; the demo does not depend on Jev; run M6-N last; benchmark numbers recorded in advance |
| Tie-breaker scoring is tuned on a small mock | Wrong win on a write tool, or no win where one is expected | A write-tool win requires description evidence; order or type alone never wins; postchecks catch a wrong write; scoring is tuned from benchmark results [A] (AC-27) |
| No side-effect-free `preverify` exists for M6-N | A Jev choice on `set_manager` can never be confirmed, so M6-N always aborts `LOW_CONFIDENCE` | Open question [A] (FR-12.9). This is a safe outcome; M6-N is reported separately and does not count toward ZTAR. |
| LLM run-to-run variance | Noisy token and MTTR numbers | Temperature 0, N = 10, report mean, median and p95 |
| The framework's default error handling differs from "return raw JSON" | Unfair baseline | Configure tool-error handling explicitly, identically except for the registry |
| Scope creep into GraphQL/gRPC | MVP not finished | STRETCH work (S1–S5, S8) starts only after the phase-12 gate |
| Pydantic lax coercion hides type changes | M2 not reproducible | Strict types in the mock |

### Limitations

- Fixes are limited to what the operation set can express. Value transforms (splitting a field, unit or format conversion) abort cleanly. They count against ZTAR, which is the correct outcome.
- Error-clue mode cannot repair nested or combined changes without a spec (measured in the error-only ablation).
- `E6` detection depends on postchecks being declared per tool (FR-3.5).
- `E3` (undecodable body) is not healed. It returns a structured error, `UNSUPPORTED_CLASS` (FUTURE).
- `E4` and `E6` on a non-idempotent tool without an `Idempotency-Key` abort `UNSAFE_REPLAY` rather than heal.
- Write-tool ambiguity is refused by default. A wrong Jev choice that `preverify` cannot distinguish is detected only after the write. It is flagged, not prevented.
- Single host only. Sharing fixes across instances needs Postgres (FUTURE).

### Trade-offs

| Decision | Chosen | Given up | Why |
|---|---|---|---|
| Healing engine | Deterministic code with a deterministic tie-breaker; optional Jev for what remains tied | LLM flexibility | Speed, safety and auditability. The LLM repair agent is STRETCH tier 2. |
| Agent schema | Frozen facade with translation | Agent seeing the new schema | No re-prompting and no token cost; the agent's plan stays valid |
| Attempts | One heal attempt per call | Some recoverable multi-step cases | Satisfies "stop once a patch fails" and guarantees no loops |
| Audit write | Synchronous | ~1–5 ms per heal | No unlogged patch is possible |
| Store | SQLite (audit events in the MVP; fixes under S6) | Multi-host sharing | Zero setup; enough for the hackathon |
| Fix basis | Always relative to the base schema | Incremental stacking | Rollbacks and repeat mutations stay correct |
