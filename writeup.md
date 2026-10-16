# Write-Up: Self-Healing Gateway

> PS 01: Self-Healing Tool Registries Under Runtime API Schema Drift. Requirement IDs (FR-x, AC-x) and mutation labels (M1 to M9, C1 to C3, T-*) refer to `product.md`. Every number comes from `bench/report.md`: **scripted mode (fixed tool calls, no LLM), N = 3, 2026-10-16**. Nothing is measured with an LLM yet.

---

## 1. What it is

Agents call tools generated once from a spec or a `tools/list`. Upstreams change; the tools do not. A standard framework hands the raw error to the agent, which retries the same call until its iteration cap. In the scripted REST benchmark the baseline hit the 10-call cap on M1, M2, M4, M5, M6-D, M6-N, M8 and M9; on the MCP drift server the baseline completed 0 of 3 runs on each of M1, M2, T-RENAME and T-ENUM.

The product is a **self-healing gateway**. The agent calls one MCP front door (`python -m healer.mcp_server`, stdio or Streamable HTTP). The gateway forwards each call to an upstream MCP server or a web API (OpenAPI 3, Swagger 2.0, GraphQL) listed in `config/mcp_servers.json`; the dashboard's Connections page edits the same list. On drift it detects, diagnoses, builds a fix from safe operations, hot-patches in memory, re-sends once, verifies, writes one audit row and returns the result, or a structured refusal. Core idea: **deterministic code heals, an LLM is optional and confined, nothing is invented, nothing loops.**

## 2. Architecture

- **Front door** (`mcp_server.py`): `tools/list` is the frozen `agent_schema` of every tool; `tools/call` goes to `Registry.call()` through the `Gateway`. It adds no healing logic.
- **Gateway** (`gateway.py`): one healing `Registry` per upstream, tools named `<server>__<tool>`. Upstream MCP tools map to `OperationSpec` from their `inputSchema` (`adapters/mcp_upstream.py`); the OpenAPI 3, Swagger 2.0 and GraphQL loaders return the same shape, so diagnosis and candidates do not depend on the protocol.
- **Healing core** (`heal.py`, `diagnose.py`, `ops.py`, `safety.py`, `store.py`): sections 4 to 7.
- **Spec watcher** (`spec_watcher.py`): polls each upstream, stores a snapshot when the spec hash changes and calls `Healer.precompute(old, new)`, so a fix can be ready before the first failing call. It does not rebase `agent_schema`.
- **Dashboard** (`python -m dashboard`): Live demo (editable prompt, "broke here" marker, cost chart), Patch log with a "what changed" animation, Metrics, Report, Connections page, guided tour. `demo/mcp_agent.py` is a scripted (or `--llm`) agent that talks only to the front door.

### Healing tiers

| Tier | What it does | When |
|---|---|---|
| 0 | Replays a stored fix whose fingerprint matches; skips diagnosis | A repeat of a known break |
| 1 | Code diffs the spec, builds candidates, picks by a deterministic tie-breaker | A new break |
| Jev triage | Optional classifier. In tier 1 it picks among tied candidates; after a tier-1 refusal it decides between repair and pass-through | Only when Jev is configured |
| 2 | LLM repair agent (`repair.py`, gpt-oss-20b on NVIDIA NIM). Opt-in with `--repair`, upstream MCP tools only | A refusal of kind `NO_CANDIDATE`, `LOW_CONFIDENCE`, `UNSAFE_PATCH` or `VERIFY_FAILED` that triage lets through |

Triage (`Healer._triage`): without Jev only `NO_CANDIDATE` goes to tier 2; with Jev, Jev decides. A refusal for a missing value (`NO_SAFE_VALUE`) never reaches tier 2, and neither does a `VERIFY_FAILED` on a write tool or after a transient failure, because the replay may have reached the API. The model sees argument types (plus enum values), not argument values, and proposes only DSL operations and a target operation. A proposal naming an unknown operation or an enum value absent from the new schema is rejected; the rest passes the same safety gate, dry run and live verification as tier 1. A wrong or manipulated model ends in a refusal.

## 3. Facade and in-memory hot-patching

Each tool holds:

| Field | Meaning | Changes? |
|---|---|---|
| `agent_schema` | The v1 schema exposed to the agent (function-calling format; MCP `inputSchema`) | **Never.** Frozen at load. |
| `wire_schema` | The schema the upstream currently accepts | Replaced on every committed fix |
| `active_fix_id` | The active operation list | Set on commit |
| `version` | Integer | `+1` on every commit |

The agent always speaks the v1 shape; the registry translates at the boundary. On commit, in memory and with no restart: `wire_schema` = current spec, `active_fix_id` = the fix, `version + 1`. The next call applies `request_ops` to the base request before sending and `response_ops` (E5) to the received body.

Fixes are always computed against the **base schema**, never stacked (FR-7.5). An API rollback to v1 therefore works: the diff is empty, the stale fix's structural violations show it is stale, and the base request is replayed once.

S6 (built) persists fixes to SQLite and reloads them at startup; a fingerprint hit goes to tier 0 and skips diagnosis. S7 (built) blocks a failed fingerprint for 60 s.

## 4. Detection and contract checks

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

## 5. Diagnosis and candidates

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

## 6. Safe patching

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

**Apply, verify, commit or roll back (FR-10).** A request-side fix is re-sent once (at most 1.0 s of the 3.5 s heal deadline). A response-side fix remaps the received body. The whole detection pipeline reruns; only `OK` counts. On pass: fix active, definition updated, one `heal_events` row written synchronously before the result is returned. On fail: fix discarded, fingerprint negative-cached (S7), one audit row, and `{error:"SCHEMA_DRIFT_UNRECOVERABLE", tool, class, fingerprint, reason, retry:false}` returned. The agent is told to treat that tool as unavailable and continue; a refusal skips one tool, not the task.

**Audit and redaction (FR-5).** One row per attempt, including refusals. The raw error is sanitized before storage: auth, cookie, API-key and token header values; strings equal to a configured secret; bearer-token and JWT-shaped strings; truncated to a maximum size. Only machine-readable data is stored.

**Bounds (FR-11):**

| Mechanism | Bound |
|---|---|
| `E1` retries | 3, backoff 100/200/400 ms + jitter |
| Heal attempts per call / replays per heal | 1 / 1 |
| Heal deadline | 3.5 s; Jev 1.5 s; spec fetch 0.5 s; replay <= 1.0 s |
| Negative cache (S7) | 60 s per failed fingerprint |
| Fix retirement (S6) | 2 losses |

## 7. Threats and prevention

| Threat | Prevention |
|---|---|
| Hallucinated values | No operation writes a literal; values come only from arguments, config or the spec; a required value with no source is a refusal; Jev only selects among code-built fixes |
| Unsafe patches or double writes | Safety gate; replay rule above |
| Guessing between equally valid fixes | Write-tool rule: tie-breaker with description evidence, or Jev at the write threshold plus `preverify`; residual risk is caught by postchecks after the write and flagged |
| Legitimate error mistaken for drift | `409`, missing record, value error on an unchanged spec are returned unchanged (`NOT_DRIFT`) |
| Prompt injection via error text or descriptions | Untrusted data matched against structure and compared as tokens; Jev output limited to an index |
| Infinite retries | One attempt, one replay, 3.5 s deadline, 3 `E1` retries, `retry: false` to the agent, 60 s negative cache |
| Silent data corruption | Output schema and postchecks before keeping a fix; the benchmark checks the final data state and reports the False-Patch Rate |
| Untraceable changes | One audit row per attempt before the agent sees a result |
| Secrets in logs | Redaction; header ops store config keys |
| Bad fixes sticking | Fixes computed from the base schema; retired at 2 losses (S6) |

## 8. Evaluation (scripted mode, N = 3, 2026-10-16)

Source: `bench/report.md`. Jev not available (M6-N aborts `LOW_CONFIDENCE`, counted as a safe refusal). The baseline re-sends a failing call with the same arguments up to the 10-call cap.

**REST mock**

| Metric | Result |
|---|---|
| ZTAR (M1 to M5, M7, M9) | **100% (21/21)** healing; 14% (3/21) baseline |
| M6-D (tie-breaker) | 100% (3/3) healing; 0% (0/3) baseline |
| M6-N (Jev disabled) | 0% (0/3) ZTAR by design; refused `LOW_CONFIDENCE` in 3/3 runs |
| Safe-Refusal Rate (M6-N, M8) | **100% (6/6)**, no invented value sent |
| False-Patch Rate | **0% (0/24 healed runs)** |
| Tier-1 MTTR and heal_ms (mean / p50 / p95) | 32 / 25.5 / 63 ms (n = 24) |
| Tier-0 MTTR and heal_ms (mean / p50 / p95) | 4.33333 / 4 / 9 ms (n = 15) |
| Token overhead | Not measured: scripted mode makes no LLM call (every `llm_tokens` is 0) |

Controls: C2 (404 on an unchanged route) and C3 (invalid value on an unchanged spec) passed through as `NOT_DRIFT` in 3/3 runs. Error-only ablation (`spec_mode=off`): M1 to M4 healed, M5 and M7 aborted `NO_CANDIDATE`, M6-D, M6-N, M8 and M9 aborted `NO_SAFE_VALUE`; False-Patch Rate 0% (0/4).

**MCP drift server** (three-call task through the `Gateway`; the baseline is an upstream registry with no store)

| Mutation | Healing ZTAR | Baseline ZTAR | Tier-1 MTTR mean / p50 / p95 |
|---|---|---|---|
| M1 | 100% (3/3) | 0% (0/3) | 7 / 6 / 9 ms (n = 3) |
| M2 | 100% (3/3) | 0% (0/3) | 6.33333 / 6 / 7 ms (n = 3) |
| T-RENAME | 100% (3/3) | 0% (0/3) | 6.33333 / 6 / 7 ms (n = 3) |
| T-ENUM | 100% (3/3) | 0% (0/3) | 7 / 7 / 8 ms (n = 3) |
| T-REQUIRED, M8 | n/a | n/a | refused `NO_SAFE_VALUE` in 3/3 runs each |

Healable ZTAR 100% (12/12) against 0% (0/12) for the baseline; Safe-Refusal Rate 100% (6/6); False-Patch Rate 0% (0/12). Healthy-call overhead over MCP (`users__get_user`, n = 250 per side, in-memory, gateway call minus a direct `ClientSession.call_tool`): p50 0.112 ms, p95 0.802 ms, mean 0.098 ms (gateway p50 0.895 ms, direct 0.795 ms). T-MOVE needs tier 2 and was skipped in scripted mode.

Timings are wall-clock, in-process, on one machine; the MCP calls are in-memory, so they exclude network time.

## 9. Limitations

1. **No LLM-mode numbers.** The real-LLM benchmark (`--agent llm`) has not been run, so tier 2, token overhead (AC-16) and T-MOVE are unmeasured. Tier 2 has tests, not a benchmark result.
2. **Operation expressiveness.** Value transforms (splitting a field, unit conversion) abort `NO_CANDIDATE` or `NO_SAFE_VALUE` and count against ZTAR unless tier 2 finds an operation-only fix. Generated code is never executed.
3. **Silent drift needs postchecks** declared per tool (FR-3.5).
4. **Write-tool ambiguity refuses by default** (M6-N). A wrong Jev choice that `preverify` cannot distinguish is caught only after the write.
5. **Error-clue mode** cannot fix nested or combined changes (M5, M7, M9 in the ablation).
6. **Deferred or unbenchmarked.** gRPC and Postgres are deferred. GraphQL is loadable but not benchmarked. Streaming and long-running tool responses are not covered. `E3` (non-JSON) is not healed.
7. **Single host, in-memory registry.** Sharing fixes across instances needs the deferred Postgres backend. `agent_schema` is frozen at startup.
8. **Clients.** Real-client UI checks (Claude Desktop, Cursor, Windsurf) have not been performed; see `docs/mcp-clients.md`.

A refusal is a structured error by design: the agent is told the tool is unavailable (`retry: false`) and skips it. This document does not claim that the agent never sees an error.

## 10. Future work

Run the LLM-mode benchmark (token overhead, tier 2, T-MOVE); measure Jev-assisted M6-N; real-client checks; a shared store (Postgres) for multi-instance fixes; gRPC; streaming responses; benchmark the GraphQL path.

## 11. Versus a conventional agent

| Conventional agent | This gateway |
|---|---|
| Treats the tool schema as fixed truth | Treats the live spec as truth and translates at runtime |
| Detects failure only from `4xx` | Also catches drift that returns `200` when a postcheck is declared |
| Sends errors to the LLM, which guesses and retries | Code diagnoses with a structural spec diff; an LLM, if used, proposes operations that are gated |
| Retries until the iteration cap | One verified attempt, then a refusal with a reason code |
| Forgets every incident | Fixes persist in SQLite; a repeat is served from the stored fix (tier 0) |

*Sources: `product.md`, `technical-approach.md`, `bench/report.md`.*
