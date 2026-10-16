# Technical Approach: Self-Healing Gateway (PS 01)

> How we build what `product.md` defines. FR-x and AC-x refer to `product.md`. Build order and owners: `plan.md`, `AGENTS.md`. **[A]** = assumption to confirm. Section numbers 2, 3.3, 5.1, 5.2, 5.4 and 8.4 are cited from code and other docs; keep them stable.

---

## 1. Approach

Agents call our MCP server (the front door). The registry owns the tool definitions and forwards each call to an upstream MCP server or a REST/OpenAPI API. Agents never call upstreams directly.

```
agent -> front-door MCP server -> Registry / Healer -> MCP client adapter -> N upstream MCP servers
                                                    -> REST adapter       -> OpenAPI APIs
```

1. **Freeze what the agent sees.** `agent_schema` comes from the first spec or `tools/list` and never changes. MCP upstream tools are namespaced `<server>__<tool>`. The front door never sends `tools/list_changed`.
2. **Detect drift on every response.** Each response becomes one `Outcome` and is classified `OK`, `BUSINESS` or `E1` to `E6` (§5.1). A `200` can still be drift.
3. **Diagnose from evidence.** Main evidence: a structural diff between the stored schema and the current one (OpenAPI spec, or a fresh `tools/list` for MCP). Supporting evidence: the structured error (FastAPI `422` `loc`/`type`, JSON-RPC code, `isError` content) and the agent's arguments.
4. **Build fixes with deterministic code.** Operations: `move`, `cast`, `header`, `route`, plus `enum_map` and `encoding` (X3). With 2 or more candidates a deterministic tie-breaker (FR-7.6) picks a unique winner if the evidence allows. Otherwise, only if Jev is configured, **Jev** (optional) selects one. Jev never produces operations or values.
5. **Prove before committing.** Safety gate, one replay (or a local remap), full re-verification, then activation.
6. **Remember.** The tool's in-memory definition carries the fix; S6 persists it by fingerprint for tier-0 reuse after a restart.
7. **Refuse safely.** No safe fix gives `{error: "SCHEMA_DRIFT_UNRECOVERABLE", ..., retry: false}`; the agent skips that tool and finishes the rest. Non-drift errors (business errors, value errors on an unchanged schema) are returned unchanged.

Why code, not an LLM, heals: speed (MTTR under 4 s), safety (an LLM can invent values), auditability (same input, same fix) and token cost.

### MCP path (contract 7, `AGENTS.md`)

| Step | What happens | Owner |
|---|---|---|
| Load | `mcp_upstream_source(server)` reads `tools/list` and maps each `inputSchema` to an `OperationSpec` keyed `<server>__<tool>` | T2-PS1 |
| Call | `adapters/mcp_upstream.py` sends `tools/call` and returns the shared `Outcome`, keeping the JSON-RPC code and message, the `isError` flag and its content | T2-PS1 |
| Classify | `detect.py` maps `-32602`, `-32601`, `isError` results and transport errors onto the existing classes; a business `isError` stays `BUSINESS` | T1-PS1 |
| Diagnose | `diagnose.py` diffs the frozen `OperationSpec` against a fresh `tools/list`: tool renamed, argument renamed or retyped, new required argument, enum changed | T1-PS1 |
| Heal | same pipeline as REST: candidates, tie-breaker, safety gate, one retry, verify, one audit row, fix stored by fingerprint. A tool rename routes to the new upstream name via an op added in `ops.py` where needed | T1-PS1 |
| Precompute | `spec_watcher.py` polls each `SpecSource` and calls `Healer.precompute(old, new)` (contract 5) | T2-PS2 / T1-PS1 |

Config for upstreams is `config/mcp_servers.json` (transport, command or URL, and the name of the env var that holds a token; no secret values). Items and status: `plan.md` Phase 13+.

## 2. Technology Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Agents, FastAPI, async, testing |
| MCP | Official `mcp` SDK (`pip install -e ".[mcp]"`) | Front door and upstream client over stdio and Streamable HTTP; mock drift MCP server |
| REST mock | FastAPI + Uvicorn, Pydantic v2 strict | Auto OpenAPI 3.1; default `422` bodies carry `loc` and `type`; strict types reject `"123"` for an `int` so type drift shows up as `422` |
| HTTP client | httpx (async) | Timeouts; `ASGITransport` for in-process tests |
| Schema validation | `jsonschema` (Draft 2020-12) | Validates arguments and responses |
| Store | SQLite (stdlib `sqlite3`, WAL) | Zero setup, durable, single host (§3.3) |
| Classifier (OPTIONAL) | Jev via httpx: `POST /v1/systemone` on TypeSafe (`JEV_API_KEY`), or `https://openrouter.ai/api/v1/systemone` with model `~typesafe/jev-latest` (`OPENROUTER_API_KEY`, Jev-only fallback) | Choice primitive returns an option index and confidence. Without it every other MUST criterion still passes. |
| Agents | LangGraph `create_react_agent` + `langchain-openai` | Same framework for both agents isolates the registry as the only difference. A scripted no-LLM agent runs keyless benchmarks and paced demos. |
| LLM | NVIDIA NIM OpenAI-compatible API `https://integrate.api.nvidia.com/v1` (`NVIDIA_API_KEY`), default `openai/gpt-oss-20b`, temperature 0, same for both agents; `LLM_MODEL` overrides ([model](https://build.nvidia.com/openai/gpt-oss-20b)) | Fair comparison |
| Dashboard | FastAPI + static HTML, vanilla JS polling | No extra dependency; runs both agents and two isolated mocks in one process |
| Config | `python-dotenv` | Loads `.env` when the dashboard starts |
| Tests / lint | pytest, pytest-asyncio, respx; ruff | Respx mocks Jev |
| Deferred (T2-6) | graphql (strawberry), grpc (grpcio), postgres (psycopg) optional groups | Not active work |

## 3. System Architecture

### 3.1 Components

| Component | Responsibility |
|---|---|
| **Front door** (`mcp_server.py`) | Serves `Registry.tools()` as MCP `tools/list` (stdio, Streamable HTTP); `tools/call` goes through `Registry.call()` only; heal refusals become `isError` results |
| **Tool Registry** | Holds `ToolDefinition`: `agent_schema` (frozen), `wire_schema`, `version`, `active_fix_id`, config (`idempotent`, `postchecks`, optional `preverify`). Dispatches each tool to the REST or MCP adapter. Entry point `call(tool, args)`. |
| **Spec loaders** | `openapi_loader`, `swagger2`, upstream MCP loader: all return `dict[str, OperationSpec]` plus hash (contracts 1, 2) |
| **Adapters** | REST (request document, send, normalize) and upstream MCP; both return `Outcome` |
| **Detector** | Classifies Outcomes (FR-3), extracts violations, runs the output-schema check and postchecks |
| **Fingerprinter** | Stable break id (FR-4) |
| **Heal Controller** | Tiers 0 and 1, deadline, one attempt per call, commit or rollback, single-flight and negative cache (S7) |
| **Diagnoser** | Fetches the current spec, diffs against the base snapshot, extracts error clues, falls back to error-clue mode (§5.4). Reclassifies `404` and value errors with an empty diff to `BUSINESS`. |
| **Candidate Builder** | Diff and clues become candidate fixes (FR-7.1 to 7.5); runs the tie-breaker (FR-7.6) |
| **Jev Client (OPTIONAL)** | One Choice request, 1.5 s timeout; absent, slow or low confidence ends in `LOW_CONFIDENCE` (decision-path marker `jev_unavailable` on failure). Its credentials are separate from the NVIDIA key. |
| **Safety Gate / Op Interpreter** | Gate: provenance, casts, operation count, replay safety, write-tool ambiguity (FR-9). Interpreter: pure, deterministic `ops.py`. |
| **Store** | SQLite audit log (raw error sanitized, FR-5.7); in-memory active-fix cache; S6 persists fixes and snapshots; S7 holds the negative cache |
| **Spec watcher** | Polls `SpecSource`s, snapshots changes, calls `Healer.precompute` (FR-18) |
| **Mock Drift API / Mock Drift MCP server** | REST mock: four operations, M1 to M9, C1 to C3, admin and state endpoints. MCP mock (`mock_api/mcp_drift_server.py`): `users` and `tickets` profiles, mutations M1, M2, T-RENAME, T-REQUIRED, T-ENUM, M8, control interface = contract 8. |
| **Agents, Benchmark, Dashboard** | Healing and baseline agents (same framework, LLM, prompt); runner computes metrics (FR-15.4); dashboard has a landing page `/` and `/live` (presets, mutation buttons, patch log, metrics) |

### 3.2 Request and response documents

One document shape; path prefixes match FastAPI's `loc`, so clues and fixes share one vocabulary.

- request: `{"route": {"method", "path"}, "body": {...}, "query": {...}, "header": {...}}`
- response: the decoded JSON body, paths relative to the body root.

The base request document is built from the agent's arguments using the **base** schema. Fixes always apply to the base document (FR-7.5).

### 3.3 Data model (SQLite)

Code-read columns hold enum codes, arrays, refs, canonical JSON (sorted keys, no whitespace), sha256 hashes and epoch-ms integers (FR-5.4).

| Entity | Purpose | Key fields |
|---|---|---|
| `spec_snapshots` | Each distinct spec version seen | `spec_hash` (pk), canonical spec JSON, `seen_ms` |
| `fixes` | One fix per fingerprint | `fix_id`, `fingerprint`, `signature`, `tool`, `class`, `request_ops`, `response_ops`, `tier`, `source` (`diff`/`clue`/`jev`/`repair`), `schema_hash`, `dsl_version`, `status` (`candidate`/`active`/`failed`/`retired`), `wins`, `losses`, timestamps. At most one `active` per fingerprint. |
| `heal_events` | Audit log: exactly one row per heal attempt, refused and aborted included (FR-5.3) | `ts_ms`, `tool`, `fingerprint`, `class`, `raw_code`, `tier`, `path` (decision path: tie-breaker or Jev, `jev_unavailable` marker), `fix_id`, `outcome`, `reason`, `mttr_ms`, `heal_ms`, `jev_tokens` (separate from `llm_tokens`), `llm_tokens`, `raw_error` (sanitized, opaque, never parsed or sent to a model) |
| `call_events` | Every tool call by both agents, for the dashboard | `ts_ms`, `agent`, `run_id`, `tool`, `class`, `latency_ms` |
| `rules` | Mined rules (S2) | abstract signature, operation template |

Example fix record (M5):

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

English appears only at runtime boundaries (text sent to Jev, the agent's error message, dashboard labels), generated from this structure.

## 4. Workflows

| Flow | Steps |
|---|---|
| **Healthy call** | Validate args against `agent_schema` (else `AGENT_ARG_ERROR`); build the base document; apply the active fix's `request_ops`; send; detect `OK`; apply `response_ops`; return. Overhead target < 10 ms p95. |
| **First break, tier 1 (M5)** | `422` (`body.target` and `header.x-tenant-id` missing), class `E2`. Fingerprint. Diagnose: `body.user_id` removed, `body.target.id` (int, required) added, `X-Tenant-Id` header added. One candidate: `move` (shared token `id`) + `cast` (`"123"` to `123` is lossless) + `header` from `header_sources`. Gate passes; replay is allowed because `E2` means nothing was executed; re-send once. Verify (`200`, schema, postcheck `response.id == arg user_id`). Commit: fix active in memory, `wire_schema` = current, `version + 1`, audit `RECOVERED` with `mttr_ms` and `heal_ms`, written synchronously. |
| **Ambiguous break (M6)** | Two type-compatible assignments with no shared name tokens. `set_manager` is a write tool (FR-8.6, FR-9.6). **M6-D** (informative descriptions): the tie-breaker scores description match, parameter order and type; one candidate strictly wins with description evidence; no Jev call. **M6-N** (no usable descriptions): no unique winner. With Jev configured, one Choice request; accept only at confidence >= 0.9 [A] and a confirming read-only `preverify` before any write. Otherwise, or with Jev absent, timed out (1.5 s) or failed, abort `LOW_CONFIDENCE` before sending anything. A wrong choice that `preverify` cannot distinguish is caught by postchecks after the write (`POSTCHECK_FAILED_AFTER_WRITE`, flagged). Whether the mock offers a side-effect-free `preverify` for M6-N is open [A] (FR-12.9). |
| **Repeat break** | The tool's definition carries the fix, so the break does not recur in-process. S6 tier 0: the fingerprint matches an `active` fix (also after a restart); skip diagnosis, run gate, replay or remap, verify; `wins + 1` or `losses + 1` (retire at 2). Target p95 < 0.5 s. |
| **Recovery fails** | Roll back; write the audit row with the reason; S7 adds the fingerprint to the negative cache for 60 s (reasons in FR-11.3; `DEADLINE` and a `LOW_CONFIDENCE` after a Jev failure are not cached) and releases single-flight; return `retry: false` error. Without S7, loop prevention is one attempt per call, the `retry: false` instruction and the agent's iteration cap. |
| **Transient, business, not drift** | `E1`: up to 3 retries (100/200/400 ms + jitter), no heal. `409`: `BUSINESS`. `404`: if the route exists in the current spec, `BUSINESS` / `NOT_DRIFT`, else drift kind `route`. Value error (C3, FR-3.4): `E2` with only value kinds and an empty spec diff is `BUSINESS` / `NOT_DRIFT`, no fix, no replay. `E3`: structured error `UNSUPPORTED_CLASS`, one audit row, no replay. |

## 5. Detection and Diagnosis

### 5.1 Detection order (per response)

| Step | Check | Class |
|---|---|---|
| 1 | Exception, timeout, `5xx`, `429` | `E1` |
| 2 | `409` | `BUSINESS` |
| 3 | Other `4xx` (`404` resolved in diagnosis; value-only violations with an empty diff become `BUSINESS` / `NOT_DRIFT`) | `E2` |
| 4 | Non-JSON `Content-Type` or unparseable body | `E3` |
| 5 | `success:false`, `status` in (`error`, `fail`), or non-empty `error`/`errors` in a `2xx` body | `E4` |
| 6 | After `response_ops`, the body fails the agent output schema | `E5` |
| 7 | A postcheck fails | `E6` |

MCP outcomes (JSON-RPC `-32602` invalid params, `-32601` unknown tool, `isError` results, transport errors) map onto the same classes. T1-1 owns the mapping and writes it into `product.md` §17 first; a business `isError` stays `BUSINESS`.

**Postchecks** are declarative data in `config/tools.json`: `echo` (a response path equals a request argument, compared as canonical strings) and `non_empty`. They catch silent drift (M7) and wrong-but-accepted fixes. `E6` is detectable only where a tool declares postchecks (FR-3.5). A tool may declare a **`preverify`** (FR-8.6): a side-effect-free operation plus an expected result, used only to confirm a Jev choice on a write tool.

Violation kinds are normalized from FastAPI `422` types. **Value kinds:** `format`, `range`, `pattern`, `enum`, `length`. **Structural kinds:** `missing`, `extra`, `type` [A: mapping confirmed against the mock's `422` bodies].

### 5.2 Spec diff

1. Match operations by `operationId` (REST) or tool key (MCP). A changed path or method for the same `operationId` is a route change.
2. Flatten the request into leaves `(path, type, required, description)`: body under `["body", ...]`, query under `["query", ...]`, headers and security schemes under `["header", ...]`.
3. Flatten the `2xx` response schema the same way, relative to the body root.
4. The diff is a list of `{change: removed|added|type_changed|required_changed, path, type, required}`. The diff signature is its canonical JSON without descriptions.

### 5.3 Handling each mutation

| Mutation | Evidence | Fix built |
|---|---|---|
| **M1** field rename (`user_id` to `customer_id`) | `422` missing `["body","customer_id"]`; one removed, one added, same type, shared token `id` | `move body.user_id to body.customer_id` |
| **M2** type (`user_id` str to int) | `422` `int_type` at `["body","user_id"]`; `type_changed` | `cast` to int if `"123"` round-trips, else `UNSAFE_PATCH` |
| **M3** response nesting (`data` wrapper) | Output schema fails; response diff shows leaves under `data` | Response `move data.id to id`, same for `name`, `email`; applied locally, no replay |
| **M4** mandatory header (OAuth) | `401` + `WWW-Authenticate: Bearer`; diff adds a bearer requirement | `header Authorization` from `config:OAUTH_BEARER`; key absent gives `NO_SAFE_VALUE` |
| **M5** combined | See §4 | `move` + `cast` + `header` |
| **M6** ambiguous rename | Two removed, two added, same type, no shared tokens | Two candidates. M6-D: tie-breaker, no Jev. M6-N: Jev at write threshold plus `preverify`, else `LOW_CONFIDENCE`. |
| **M7** silent ignore | `200` with the old email; `echo` postcheck fails; `email` removed, optional `email_address` added | `move body.email to body.email_address`. A removed field plus an added **optional** field is a candidate only with name evidence, a type match or lossless cast, and a failure pointing at the removed field (FR-7.2). |
| **M8** unsupported | `422` missing `["body","priority"]`; no source | No candidate: `NO_SAFE_VALUE` |
| **M9** request nesting | Flat body becomes `{payload:{...}}`; wrapping only | `move` x2 into `body.payload` |
| **C3** value error | `422` kind `format`, spec unchanged | No fix; `BUSINESS` / `NOT_DRIFT` |
| **M10** injection (S8) | M1's rename with injected text in `msg` and description | Same `move` as M1; nothing derived from the text (FR-8.8) |
| **MCP equivalents** | Fresh `tools/list` differs from the frozen `OperationSpec` | Argument renamed: `move`. Argument retyped: `cast`. Tool renamed: route to the new upstream name. Enum value changed: `enum_map` if bijective (FR-17.3). New required argument with no source: refusal (M8-style). |

**Empty diff with structural violations (FR-3.4).** The request shape is wrong, not the value (an API rolled back to v1). With an active fix, that fix is stale: diagnose against the base schema (the "no operations" candidate) and replay the base request once. With no active fix, abort `NO_CANDIDATE`. A mix of value and structural violations counts as structural.

### 5.4 Error-clue mode (no spec available)

Used when the spec fetch fails or exceeds 0.5 s [A], or `spec_mode` is `off` (FR-6.4; the benchmark's error-only ablation, FR-15.7). Only the violations and the original arguments are used:

- `missing` at path P is filled from an argument sharing a name token with P, or from the only argument the base schema no longer explains.
- `int_type` / `string_type` at P becomes `cast`.
- A missing header becomes `header` if a config source exists.

Nested or combined changes need the spec and abort `NO_CANDIDATE` (M5, M9 in the ablation).

## 6. Safe Patching

### 6.1 Operation DSL

Versioned `dsl_version` 1, interpreted by pure `ops.py` (new document out, no in-place mutation, unknown ops rejected). Operation table: `product.md` §8. No operation writes a literal value; values come from an existing path (`move`), the same value converted (`cast`), a config reference (`header`), or the current spec (`route`).

### 6.2 Safety gate (before anything is sent)

1. **Provenance:** every `move` source exists in the base document; every `header` key exists in config; every `route` target exists in the current spec.
2. **Lossless cast:** `str(int(v)) == v`; same round-trip rule for `float` and `bool`.
3. **Minimal diff:** operations <= 3 x violations or diff entries [A].
4. **Replay safety (FR-9.4):** `E2` is replay-safe by itself. `E4` and `E6` replay only for an idempotent tool or with an `Idempotency-Key`, else `UNSAFE_REPLAY`. `E5` is never replayed (response-side remap).
5. **Jev threshold:** >= 0.9 write, >= 0.5 read [A]; below it `LOW_CONFIDENCE`.
6. **Write-tool ambiguity (FR-9.6, FR-8.6):** with 2 or more candidates, reject unless the tie-breaker won on description evidence, or the Jev choice meets the write threshold and `preverify` confirms it. Otherwise `LOW_CONFIDENCE`, nothing sent.
7. **Unknown operation names** reject the fix (FR-9.5).

After the fix, the whole detection pipeline runs again; only `OK` counts as recovered.

### 6.3 Audit

One `heal_events` row per attempt, written synchronously before the agent gets a result (about 1 to 5 ms per heal; no patch is ever unlogged, FR-5.5). The raw error is sanitized first (FR-5.7): `Authorization`, `Cookie`, `Set-Cookie`, API-key and token header values; strings equal to a configured secret; bearer-token and JWT-shaped strings [A: pattern list]; truncated to a maximum size [A].

### 6.4 Bounds

| Mechanism | Bound |
|---|---|
| `E1` retries | 3, backoff 100/200/400 ms + jitter |
| Heal attempts per call / replays per heal | 1 / 1 |
| Heal deadline | 3.5 s; Jev 1.5 s; spec fetch 0.5 s [A]; replay <= 1.0 s |
| Negative cache (S7) | 60 s per failed fingerprint |
| Fix lifetime (S6) | Retired at 2 losses |
| Concurrency (S7) | Single-flight per fingerprint; without S7 each concurrent call heals at most once and each result is verified |

### 6.5 When the system stops

0 candidates: stop, never ask a model for a value. 2 or more: tie-breaker, then optional Jev, then `LOW_CONFIDENCE`. `E4` or `E6` on a non-idempotent tool without a key: `UNSAFE_REPLAY`. Error bodies, OpenAPI descriptions and MCP tool descriptions are untrusted data: matched against schema structure and compared as tokens, never a source of values, fields, headers or operations (FR-8.8).

## 7. Baseline Comparison

| Control | Healing agent | Baseline agent |
|---|---|---|
| Framework, LLM, prompt, task, iteration cap (10 [A]) | Same | Same |
| Tools | From the v1 spec, executed through `registry.call` | From the v1 spec, direct HTTP call |
| Error handling | Structured result or `retry: false` error | Raw API error JSON as the tool result |
| Mock state | Reset before each run | Same |

Per scenario: reset the mock, activate the mutation, run the demo task, record events, tokens, outcome and final state. The dashboard triggers the mutation mid-run instead. Baseline outcomes are measured and reported for every scenario, not asserted (FR-15.8, AC-17). The recorded scripted run (`bench/report.md`, N = 3) is the only measured data; see that file for its baseline failure modes.

## 8. Testing and Evaluation

### 8.1 Test layers

| Layer | Scope | Network |
|---|---|---|
| Unit | Op interpreter, safety gate, detector table, fingerprinter, spec diff, candidate builder, tie-breaker (AC-27), redaction (AC-24), store | None |
| Integration | Registry + mock in-process (`ASGITransport`) for M1 to M9 (M6-D, M6-N), C1 to C3, an `E3` fixture (AC-25), a replay-rule fixture tool (AC-20); Jev mocked with respx; MCP path against the mock drift MCP server or its fixtures | None |
| Agent end-to-end | Both agents against the running mock with the real LLM and Jev (`tests/e2e/`, skipped without env vars) | Yes |
| Benchmark | Scenarios x agents x N = 10 [A], LLM or scripted mode | LLM mode only |
| Robustness | Jev down (AC-13), spec endpoint down (AC-23), restart (AC-11), concurrency (AC-19), negative cache (AC-12) | None |

Each AC has a `test_ac_XX_*` test.

### 8.2 Scenario matrix

M1 to M9 (M6 in both configurations), C1 to C3, M10 (S8), for both agents. M1 to M5 also rerun after the first heal (tier 0), and after a restart under S6. Also: clean runs (FR-15.6) and the error-only ablation of M1 to M9 (FR-15.7). MCP scenarios join the matrix under T1-9.

### 8.3 Metrics

Definitions are FR-15.4 (ZTAR, Safe-Refusal Rate, False-Patch Rate, MTTR with `heal_ms` separate, Token Overhead with `jev_tokens` separate). Every timing and token metric is reported as mean, median and p95 per scenario (FR-15.5). Scripted mode records 0 LLM tokens, so token overhead needs an LLM-mode run.

### 8.4 Reporting

The runner writes `results.jsonl` (one row per run) and `report.md`: per-scenario table (ZTAR, MTTR p50/p95, `heal_ms`, tier, tokens, baseline failure mode), Safe-Refusal and False-Patch Rates, the `jev_tokens` column, and the error-only ablation table (healed or aborted with reason; no threshold). It states whether the run was scripted or LLM mode.

## 9. Risks, Limitations, Trade-offs

| Risk | Mitigation |
|---|---|
| Jev access or API details differ from public coverage | Jev is optional behind a client interface; without it M6-N aborts `LOW_CONFIDENCE`, M6-D heals through the tie-breaker, all else unaffected |
| Tie-breaker tuned on a small mock | Write-tool win needs description evidence; postchecks catch a wrong write (AC-27) |
| No side-effect-free `preverify` for M6-N | Open [A] (FR-12.9); M6-N then always refuses, reported separately from ZTAR |
| LLM run-to-run variance | Temperature 0, N = 10, mean, median, p95 |
| Unfair baseline | Tool-error handling configured identically except for the registry |
| Upstream MCP servers differ in how they report errors | Contract 7 keeps the JSON-RPC code and `isError` content; classification is table-driven in `detect.py` and tested against fixtures |
| Scope creep into GraphQL, gRPC, Postgres | Deferred to T2-6 |

**Limitations.** Fixes are limited to what the operations express; value transforms abort cleanly and count against ZTAR. Error-clue mode cannot repair nested or combined changes. `E6` detection needs declared postchecks. `E3` is not healed. `E4`/`E6` on a non-idempotent tool without a key abort `UNSAFE_REPLAY`. A wrong Jev choice that `preverify` cannot distinguish is flagged after the write, not prevented. Fix sharing is single host until the Postgres backend (T2-6).

**Trade-offs.** Deterministic code with an optional Jev for what stays tied, over LLM flexibility. Frozen agent schema with translation, so no re-prompting. One heal attempt per call, so no loops. Synchronous audit, about 1 to 5 ms. SQLite, zero setup. Fixes always relative to the base schema, so rollbacks and repeat mutations stay correct.
