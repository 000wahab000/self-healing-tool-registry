# Write-Up: Self-Healing Gateway, Diagnosis and Patch Logic

> PS 01: Self-Healing Tool Registries Under Runtime API Schema Drift. Requirement IDs (FR-x, AC-x) and mutation labels (M1 to M9, C1 to C3) refer to `product.md`. Every measured number comes from `bench/report.md`: **scripted mode (fixed tool calls, no LLM), N = 3, 2026-10-14, REST mock**. Nothing here is measured for MCP upstreams or with an LLM yet.

---

## 1. What it is

Agents call tools that were generated once from a spec or a `tools/list`. Upstreams change; the tools do not. Standard frameworks return the raw error to the agent, which retries the same broken call until its iteration cap. In the scripted benchmark the baseline hit the 10-call cap on M1, M2, M4, M5, M6-D, M6-N, M8 and M9.

The product is a **self-healing gateway** (direction of 2026-10-16). Agents call our MCP server. The registry forwards each call to an upstream MCP server or a REST/OpenAPI API. On drift it detects, diagnoses, builds a fix from safe operations, hot-patches in memory, re-sends once, verifies, logs, and returns the result. Both protocols share one healing core; the REST path is built and benchmarked, the MCP front door is built, and the upstream MCP client and healing are in progress (`plan.md`, Phase 13+).

Core idea: **deterministic code heals (including a deterministic tie-breaker), Jev is an optional last-resort tie-breaker, nothing is invented, nothing loops.**

## 2. Facade and in-memory hot-patching

Each tool holds:

| Field | Meaning | Changes? |
|---|---|---|
| `agent_schema` | The v1 schema exposed to the agent (function-calling format; MCP `inputSchema`) | **Never.** Frozen at load. |
| `wire_schema` | The schema the upstream currently accepts | Replaced on every committed fix |
| `active_fix_id` | The active operation list | Set on commit |
| `version` | Integer | `+1` on every commit |

The agent always speaks the v1 shape; the registry translates at the boundary. On commit, in memory and with no restart: `wire_schema` = current spec, `active_fix_id` = the fix, `version + 1`. The next call applies `request_ops` to the base request before sending and `response_ops` (E5) to the received body. The effect on agent token use is not yet measured.

Fixes are always computed against the **base schema**, never stacked (FR-7.5). An API rollback to v1 therefore works: the diff is empty, the stale fix's structural violations show it is stale, and the base request is replayed once.

S6 (built) persists fixes to SQLite and reloads them at startup; a fingerprint hit goes to tier 0 and skips diagnosis. S7 (built) blocks a failed fingerprint for 60 s.

## 3. Detection and contract checks

Every response becomes an `Outcome` (`class`, `protocol`, `raw_code`, `data`, `violations[]`), classified in a fixed order:

| Stage | Condition | Class | Action |
|---|---|---|---|
| 1 | Exception, timeout, `5xx`, `429` | `E1` | Up to 3 retries (100/200/400 ms + jitter). Never healed. |
| 2 | `409` | `BUSINESS` | Returned unchanged |
| 3 | Other `4xx` | `E2` | Heal the request (see NOT_DRIFT below) |
| 4 | Non-JSON or unparseable body | `E3` | Structured error `UNSUPPORTED_CLASS`, one audit event, no replay |
| 5 | Error flag inside a `2xx` body | `E4` | Heal the request; replay only if idempotent or keyed |
| 6 | Body fails the output schema | `E5` | Remap the received body; no replay |
| 7 | A declarative postcheck fails on a `2xx` | `E6` | Heal the request; replay only if idempotent or keyed |

**NOT_DRIFT (C3).** An `E2` whose spec diff is empty and whose violations are all value kinds (`format`, `range`, `pattern`, `enum`, `length`) is not drift: it becomes `BUSINESS` / `NOT_DRIFT`, returned unchanged with no fix and no replay. An empty diff with structural violations (`missing`, `extra`, `type`) means the request shape is wrong: with an active fix that fix is stale (replay the base request once); with none, abort `NO_CANDIDATE`.

**Postchecks** (`config/tools.json`): `echo` (a response path equals a request argument) and `non_empty`. They catch M7, where the API silently drops the `email` field and returns the old value, and they re-verify every fix. Limitation (FR-3.5): `E6` is detectable only for tools that declare postchecks.

## 4. Diagnosis and candidates

**Spec diff.** The diagnoser fetches the current spec (0.5 s timeout) or, for MCP, a fresh `tools/list`, canonicalizes it and diffs the operation against the base snapshot: removed and added fields (with type and required flag), type changes, added headers and security, route or method changes, response-schema changes. Paths use FastAPI location prefixes (`["body","target","id"]`, `["query","limit"]`, `["header","x-tenant-id"]`), so diff and error clues share one vocabulary.

**Candidate rules (FR-7.2):**

| Diff entry | Rule | Op |
|---|---|---|
| Same field, type changed | Only if the value converts losslessly | `cast` |
| Field removed, required field added, shared name token or one-to-one | Move the value | `move` |
| Same, no name evidence | Every type-compatible one-to-one assignment (at most 8) | several `move` candidates |
| Field removed, **optional** field added | Candidate only with name evidence **and** a failure pointing at the removed field | `move` |
| Required header or security requirement | From `header_sources` config | `header` |
| Route or method change | Route that exists in the spec | `route` |
| Response leaves relocated | Locate in the new shape | response `move` (+ `cast`) |
| Required field with no source | No candidate | `NO_SAFE_VALUE` |

**Deterministic tie-breaker (M6-D, FR-7.6).** With 2 or more candidates, score on (1) description match (a shared non-stopword token between the removed field's base description and the added field's current description), (2) parameter order, (3) type. A candidate wins only if it strictly beats all others; on a **write** tool a win must include a description match. M6-D heals this way with no Jev call (3 of 3 runs). Descriptions are untrusted data, compared as tokens only.

**Optional Jev (M6-N).** With no unique winner and Jev configured, one Choice request (1.5 s timeout) renders the diff and candidates as data. Jev returns only an index and a confidence. On a write tool the choice is accepted only at confidence >= 0.9 **and** with a confirming read-only `preverify` before any write. Otherwise, or with Jev absent, timed out or failed, the heal aborts `LOW_CONFIDENCE` before sending anything; the decision path records the `jev_unavailable` marker.

**Error-clue mode** (spec unavailable or `spec_mode=off`, FR-6.4): only the structured error and the original arguments. A `missing` violation is filled from an argument sharing a name token (or the only unexplained argument); `int_type`/`string_type` becomes `cast`; a missing header becomes `header` if configured. Nested or combined changes abort `NO_CANDIDATE`.

## 5. Safe patching

**Operations (DSL version 1).** The core four are `move`, `cast`, `header`, `route`; `enum_map` (bijective) and `encoding` (`Content-Type` declared in the spec) were added under X3. All are interpreted by pure `ops.py`; unknown operations are rejected. **No operation can write a literal value.**

| Op | Value source |
|---|---|
| `move` | The existing value at the source path |
| `cast` | The same value, lossless only |
| `header` | `{"ref":"config","key":...}` only; stores the key, never the secret |
| `route` | A route that exists in the current spec |

**Safety gate (FR-9), before anything is sent:**

1. Provenance: every `move` source exists in the arguments, every `header` key in config, every `route` target in the spec.
2. Lossless cast: `str(int(v)) == v` (same for `float`, `bool`); `"12a"` to int gives `UNSAFE_PATCH`.
3. Operation count <= 3 x violations or diff entries.
4. Replay: `E2` is safe by itself (the server rejected the request). `E4` and `E6` replay only for an idempotent tool or with an `Idempotency-Key`, else `UNSAFE_REPLAY`. `E5` is never replayed.
5. Write-tool ambiguity (FR-9.6): with 2 or more candidates, reject unless the tie-breaker won on description evidence or Jev met the write threshold with a confirming `preverify`.
6. Unknown operation: reject.

**Apply, verify, commit or roll back (FR-10).** A request-side fix is re-sent once (at most 1.0 s of the 3.5 s heal deadline). A response-side fix remaps the received body. The whole detection pipeline reruns; only `OK` counts. On pass: fix active, definition updated, one `heal_events` row written synchronously before the result is returned. On fail: fix discarded, fingerprint negative-cached (S7), one audit row, and `{error:"SCHEMA_DRIFT_UNRECOVERABLE", tool, class, fingerprint, reason, retry:false}` returned. The agent's prompt treats that tool as unavailable, reports it as skipped and continues; a refusal skips one tool, not the task.

**Audit and redaction (FR-5).** One row per attempt, including refusals, about 1 to 5 ms per heal. The raw error is sanitized before storage: auth, cookie, API-key and token header values; strings equal to a configured secret; bearer-token and JWT-shaped strings; truncated to a maximum size. Only machine-readable data is stored.

**Bounds (FR-11):**

| Mechanism | Bound |
|---|---|
| `E1` retries | 3, backoff 100/200/400 ms + jitter |
| Heal attempts per call / replays per heal | 1 / 1 |
| Heal deadline | 3.5 s; Jev 1.5 s; spec fetch 0.5 s; replay <= 1.0 s |
| Negative cache (S7) | 60 s per failed fingerprint |
| Fix retirement (S6) | 2 losses |

## 6. Threats and prevention

| Threat | Prevention |
|---|---|
| Hallucinated values | No operation writes a literal; values come only from arguments, config or the spec; a required value with no source is a refusal; Jev only selects among code-built fixes |
| Unsafe patches or double writes | Safety gate; replay rule above |
| Guessing between equally valid fixes | Write-tool rule: tie-breaker with description evidence, or Jev at the write threshold plus `preverify`; residual risk is caught by postchecks after the write and flagged |
| Legitimate error mistaken for drift | `409`, missing record, value error on an unchanged spec are returned unchanged (`NOT_DRIFT`) |
| Prompt injection via error text or descriptions | Untrusted data matched against structure and compared as tokens; Jev output limited to an index; M10 demonstrates this (S8) |
| Infinite retries | One attempt, one replay, 3.5 s deadline, 3 `E1` retries, `retry: false` to the agent, 60 s negative cache |
| Silent data corruption | Output schema and postchecks before keeping a fix; the benchmark checks the final data state and reports the False-Patch Rate |
| Untraceable changes | One audit row per attempt before the agent sees a result |
| Secrets in logs | Redaction; header ops store config keys |
| Bad fixes sticking | Fixes computed from the base schema; retired at 2 losses (S6) |

## 7. Results (scripted mode, N = 3, REST mock)

Source: `bench/report.md`, 2026-10-14 18:29 UTC, Jev not available (M6-N aborts `LOW_CONFIDENCE`, counted as a safe refusal). Timings are wall-clock on a laptop.

| Metric | Result |
|---|---|
| **ZTAR** (M1 to M5, M7, M9) | **100% (21/21)** healing; 14% (3/21) baseline |
| **M6-D** (tie-breaker) | **100% (3/3)** healing; 0% baseline |
| **M6-N** (Jev disabled) | 0% ZTAR by design; refused `LOW_CONFIDENCE` in 3/3 runs |
| **Safe-Refusal Rate** (M8 + M6-N) | **100% (6/6)**; no request carried an invented value |
| **False-Patch Rate** | **0% (0/24 healed runs)** |
| **Tier-1 MTTR** (mean / p50 / p95) | 50.7 / 49 / 66 ms (n = 24) |
| **Tier-0 MTTR** (mean / p50 / p95) | 4.7 / 4 / 8 ms (n = 15) |
| **Token Overhead** | Not measured: scripted mode records 0 LLM tokens; needs `--agent llm` |

Tier-1 MTTR p50 / p95 per mutation (ms): M1 47/48, M2 45/66, M3 47/49, M4 52/53, M5 57/69, M6-D 47/51, M7 52/53, M9 50/58. `heal_ms` equals MTTR in this mode. Baseline: hit the 10-call cap on M1, M2, M4, M5, M6-D, M6-N, M8, M9, C2 and C3, ended incomplete on M7, completed M3, C1 and CLEAN. C2 and C3 passed through correctly (`NOT_DRIFT`) in 3/3 runs. Full per-scenario tables are in the report.

**Error-only ablation** (`spec_mode=off`, no pass threshold; False-Patch Rate must stay 0). Healed: M1, M2, M3, M4. Aborted `NO_CANDIDATE`: M5, M7. Aborted `NO_SAFE_VALUE`: M6-D, M6-N, M8, M9. False-Patch Rate 0% (0/4 healed runs).

## 8. Limitations

1. **Operation expressiveness.** Value transforms (splitting a field, unit conversion) abort with `NO_CANDIDATE` or `NO_SAFE_VALUE` and count against ZTAR. A tier-2 repair LLM (S3) emitting validated operation lists is STRETCH; generated code is never executed.
2. **Silent drift needs postchecks** declared per tool (FR-3.5).
3. **Write-tool ambiguity refuses by default** (M6-N). Residual risk: a wrong Jev choice that `preverify` cannot distinguish is caught only after the write.
4. **Error-clue mode** cannot fix nested or combined changes (M5, M7, M9 in the ablation).
5. **Token Overhead is not measured** (AC-16 needs an LLM-mode run, T1-10).
6. **MCP path not yet benchmarked**: the MCP drift benchmark and healthy-call overhead over MCP are T1-8 and T1-9.
7. **`E3` is not healed**; it returns `UNSUPPORTED_CLASS`.
8. **Single host.** Sharing fixes across instances needs the deferred Postgres backend (T2-6).
9. **`agent_schema` is frozen at startup.** The spec watcher (FR-18) snapshots changes and feeds `Healer.precompute`; it does not rebase `agent_schema`.

## 9. Versus a conventional agent

| Conventional agent | This gateway |
|---|---|
| Treats the tool schema as fixed truth | Treats the live spec as truth and translates at runtime |
| Detects failure only from `4xx` | Also catches drift that returns `200`: changed shapes, ignored inputs, errors in success bodies |
| Sends errors to the LLM, which guesses and retries | Code diagnoses with a structural spec diff; the LLM is not asked to guess |
| Retries until the iteration cap | One verified attempt, then a refusal with a reason code; the agent skips that tool |
| Forgets every incident | The definition carries the fix; S6 survives restarts |
| Free-form generated fix logic | A small verifiable data language that cannot invent values |

**Demo (about 30 s, `dashboard/demo.py`).** Both agents start the same task; the schema changes mid-run (M5); the baseline loops on `422` while the healing agent completes; a second mutation on another tool heals; M8 shows the refusal; the metrics panel shows the measured numbers. Every step heals or refuses without Jev.

*Sources: `product.md`, `technical-approach.md`, `bench/report.md`.*
