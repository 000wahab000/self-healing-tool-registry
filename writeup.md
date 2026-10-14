# Write-Up: Self-Healing Tool Registry — Diagnosis and Patch Logic

> **PS 01: Self-Healing Tool Registries Under Runtime API Schema Drift**
>
> This document covers the design rationale, detection pipeline, candidate-building logic, and safe-patching strategy. Measured results come from `bench/report.md` (**scripted mode, N = 3**, 2026-10-14, no LLM). Requirement IDs (FR-x, AC-x) and mutation labels (M1–M9, C1–C3) refer to `product.md`.

---

## 1. Architecture and In-Memory Hot-Patching

### The Core Problem

Agent tool schemas are generated once from an OpenAPI spec. When the API changes at runtime — a renamed field, a type change, a new mandatory header, a nested response — every call breaks. Standard frameworks return the raw error to the agent, which then retries the same broken call until the iteration cap, wasting tokens and making no progress. In our scripted benchmark (N = 3), the baseline hit the 10-call iteration cap on M1, M2, M4, M5, M6-D, M6-N, M8, and M9.

### The Facade Pattern

Every tool in the registry holds two distinct schemas:

| Field | Meaning | Mutates? |
|---|---|---|
| `agent_schema` | The v1 schema exposed to the agent framework via `function_calling` format | **Never.** Frozen at load time. |
| `wire_schema` | The schema the API currently accepts | Replaced on every committed fix. |
| `active_fix_id` | Reference to the active operation list in the store/cache | Set on commit, cleared on rollback. |
| `version` | Monotonically incremented integer | `+1` on every commit. |

The agent always speaks the v1 shape. The registry translates at the boundary. This has two practical consequences:
- **Zero extra agent reasoning tokens**: the agent's view of the tool never changes, so it never needs to re-think how to call it.
- **Prompt cache preserved**: function-calling schemas are often included in the prompt; keeping `agent_schema` frozen means the cache stays valid across heals.

### Hot-Patch Mechanics

When a fix is committed (§4 below), the registry executes atomically in memory:

```
wire_schema  ← current_spec[operation]
active_fix_id ← fix.fix_id
version      ← version + 1
```

No restart is needed. The next call through `Registry.call()` picks up the new `wire_schema` and applies `active_fix.request_ops` to the base request document before sending. `response_ops` (for E5 shape-drift) are applied to the received body before it is returned to the agent.

Fixes are always computed against the **base schema** (the original v1 spec), never stacked on each other (FR-7.5). This means an API rollback back to v1 clears the stale fix correctly: the diagnoser finds an empty diff, the stale structural violations indicate the fix is stale, and the base request is replayed once.

### Persistence (S6/S7, already built)

Beyond the in-memory fix for the current process, the STRETCH persistent store (S6) saves fixes to SQLite and reloads them at startup. A fingerprint hit in the store goes to **tier 0** — skipping diagnosis entirely, with p50/p95 of 1–2/4 ms (scripted, N = 3). The negative cache (S7) blocks a failed fingerprint for 60 s to prevent looping at the registry level.

---

## 2. Seven-Stage Detection and Contract Checks

Every response is normalized into an `Outcome` (`class`, `protocol`, `raw_code`, `data`, `violations[]`) before any routing decision. Detection runs in a fixed priority order:

| Stage | Condition | Class | Action |
|---|---|---|---|
| 1 | Exception, timeout, `5xx`, `429` | `E1` | Bounded retry (≤ 3, 100/200/400 ms + jitter). Never healed. |
| 2 | `409` | `BUSINESS` | Returned unchanged. Never healed. |
| 3 | Other `4xx` | `E2` | Heal on the request side. See §2.1 for `NOT_DRIFT` reclassification. |
| 4 | Non-JSON or unparseable body | `E3` | Structured error `UNSUPPORTED_CLASS`, one audit event, no replay. |
| 5 | Error flag inside a `2xx` body | `E4` | Heal on the request side. Replay only for idempotent tools or with `Idempotency-Key`. |
| 6 | Body fails the agent output schema (jsonschema) | `E5` | Heal on the response side (remap the body already received, no replay). |
| 7 | A declarative postcheck fails on a `2xx` | `E6` | Heal on the request side. Replay only for idempotent tools or with `Idempotency-Key`. |

### 2.1 NOT_DRIFT Reclassification (C3)

An `E2` whose spec diff is **empty** and whose violations are **all value kinds** (`format`, `range`, `pattern`, `enum`, `length`) is not drift. A real example is scenario C3: `update_email` validates the email format and rejects `"not-an-email"` — the API schema hasn't changed, the agent sent an invalid value. This is reclassified `BUSINESS` with audit reason `NOT_DRIFT` and returned to the agent unchanged — no fix, no replay.

The distinguishing rule vs. an API rollback: an empty diff with **structural** violations (`missing`, `extra`, `type`) means the request shape is wrong. If an active fix is present, that fix is stale — the base request is replayed once. If no fix is active, the operation is `NO_CANDIDATE`.

### 2.2 Declarative Postchecks (E6 / M7)

Postchecks in `config/tools.json` catch drift that returns `200`:

- **`echo`**: asserts that a response path equals a request argument (compared as canonical strings). Used to detect M7 (silent ignore): the API silently discarded the `email` field and returned the old value, so `response.email ≠ arg.email`.
- **`non_empty`**: asserts a response path is present and non-empty.

Postchecks also serve as the final verification check after a fix is applied — a wrong fix that passes the replay but returns a stale field value is caught here before it is committed.

**Limitation (FR-3.5):** `E6` detection requires a postcheck declaration per tool. A tool with no postchecks cannot detect that its input was silently discarded.

---

## 3. Diagnosis and Candidate Generation

### 3.1 Structural Spec Diff

The diagnoser fetches the current `/openapi.json` (0.5 s timeout), canonicalizes it, and diffs it operation-by-operation against the stored base snapshot. The diff reports:

- Removed and added fields (path, type, `required` flag, description)
- Type changes at the same path
- Added header parameters and security requirements
- Route or method changes
- Response-schema changes

Paths use FastAPI location prefixes — `["body","target","id"]`, `["query","limit"]`, `["header","x-tenant-id"]` — matching the `loc` arrays in FastAPI `422` bodies, so the diff and error clues share one vocabulary.

### 3.2 Candidate Building (FR-7.2)

The candidate builder applies deterministic mapping rules to the diff:

| Diff entry | Rule | Op produced |
|---|---|---|
| Same field, type changed | `cast`, only if the value converts losslessly | `cast` |
| Field removed, required field added, shared name token | `move` (name evidence or one-to-one) | `move` |
| Field removed, required field added, no shared token | All type-compatible one-to-one assignments (≤ 8 candidates) | multiple `move` candidates |
| Field removed, **optional** field added | Candidate only with name evidence **and** a failure pointing at the removed field (E6 postcheck, or E2 violation at that path) | `move` |
| Required header or security requirement added | `header` from `header_sources` config | `header` |
| Route or method change | `route` | `route` |
| Response leaves relocated | `move` + optional `cast` | response `move`/`cast` |
| Required field with no source | No candidate — stop | `NO_SAFE_VALUE` |

### 3.3 Deterministic Tie-Breaker (M6-D)

When there are 2 or more candidates, a deterministic tie-breaker scores them on three pieces of evidence already in hand (FR-7.6):

1. **Description match**: a shared non-stopword token between the removed field's description in the base snapshot and the added field's description in the current spec.
2. **Parameter order**: the relative position of the removed fields in the base schema matches that of the added fields in the current spec.
3. **Type**.

A candidate wins only if it **strictly beats every other** candidate. For a **write tool**, a win must include a description match — order and type alone do not separate type-compatible assignments. In scenario M6-D, the mock's `set_manager` fields carry informative descriptions, and the tie-breaker picks the correct `user_id → subject` / `manager_id → supervisor` assignment without any Jev call. Confirmed in 3/3 runs (scripted, N = 3).

Descriptions are treated as **untrusted data**: they are tokenized and compared structurally; no value, field name, header or operation is derived from their text.

### 3.4 Optional Jev (M6-N)

When the tie-breaker finds no unique winner and Jev is configured, the Jev client sends one Choice request (1.5 s timeout) with the diff and candidate operations rendered as data. Jev returns only an index and a confidence score — it never produces operations or values.

For a **write tool** (FR-8.6, FR-9.6): a Jev choice is accepted only if confidence is ≥ 0.9 **and** a declarative `preverify` (a side-effect-free operation in `config/tools.json`) confirms the chosen candidate before any write is sent. Without a confirming `preverify`, or with confidence below the threshold, the heal aborts `LOW_CONFIDENCE` and sends nothing.

In M6-N with Jev disabled, the heal aborts `LOW_CONFIDENCE` before any request is sent. The audit decision path records `jev_unavailable` when Jev failed or timed out (not an abort reason itself, just a marker).

### 3.5 Error-Clue Fallback (`spec_mode="off"`)

When the spec endpoint is unavailable, or when `spec_mode` is set to `off` in settings (used for the benchmark's error-only ablation, FR-15.7), the candidate builder uses only the structured error body and the original arguments:

- A `missing` violation at path P: filled from an argument that shares a name token with P, or from the only argument the base schema no longer explains.
- `int_type`/`string_type` at P: `cast`.
- A missing header: `header` if a config source exists.

Nested or combined changes require the spec, so M5 and M9 abort `NO_CANDIDATE` in this mode. M1–M4 still heal on the error clue alone (measured in the ablation table in §5).

---

## 4. Safe Patching Strategy

### 4.1 The 4-Operation DSL

All fixes are expressed in a versioned DSL (`dsl_version: 1`) with exactly four operations:

| Op | Side | Effect | Allowed value source |
|---|---|---|---|
| `move` | request, response | Moves a value from one path to another (rename, nest, unnest) | The existing value at the source path |
| `cast` | request, response | Converts a value's type | The same value, lossless only |
| `header` | request | Sets a header | `{"ref":"config","key":...}` only |
| `route` | request | Sets the method and/or path | A route that exists in the current spec |

**No operation can write a literal value.** The DSL is interpreted by `ops.py`, a pure function (input document in, new document out; no side effects, no mutation in place). Unknown operation names are rejected outright.

### 4.2 Safety Gate (FR-9)

Before anything is sent, every fix passes through a mandatory safety gate:

1. **Provenance (FR-9.1)**: every `move` source exists in the original arguments; every `header` key exists in config; every `route` target exists in the current spec.
2. **Lossless cast (FR-9.2)**: `str(int(v)) == v`. The round-trip rule applies to `float` and `bool`. A lossy cast (e.g., `"12a"` → int) causes `UNSAFE_PATCH`.
3. **Minimal size (FR-9.3)**: the operation count may not exceed 3× the number of violations or diff entries.
4. **Replay safety (FR-9.4)**:
   - `E2` (server rejected the request): replay always safe — the server never executed the call.
   - `E4` and `E6` (server accepted the request and may have written something): replay only for an idempotent tool or with an `Idempotency-Key`. Otherwise `UNSAFE_REPLAY`.
   - `E5` (response-side shape drift): never replayed — the body already received is remapped locally.
5. **Write-tool ambiguity (FR-9.6)**: for a write tool with 2+ candidates, reject unless the tie-breaker won on description evidence, or Jev met the write threshold and a `preverify` confirmed.
6. **Unknown ops (FR-9.5)**: reject the fix.

### 4.3 Apply, Replay, Verify, Commit or Rollback (FR-10)

For a request-side fix, the patched request is re-sent **once** (at most 1.0 s left before the 3.5 s heal deadline). For a response-side fix (E5), the received body is remapped locally with no re-send.

After the fix is applied, the full detection pipeline runs again — class check, output schema validation, and all postchecks. Only `OK` counts as recovered.

**On pass:** the fix is recorded as `active`, the in-memory tool definition is updated (`wire_schema`, `active_fix_id`, `version + 1`), one `heal_events` row is written synchronously to SQLite (before the result is returned to the agent), and the result is returned. Under S6, the fix is also persisted to the `fixes` table.

**On fail:** the fix is discarded, the tool definition is left unchanged, the fingerprint is added to the negative cache (S7) for 60 s, one `heal_events` row is written with the failure reason, and a structured error `{"error":"SCHEMA_DRIFT_UNRECOVERABLE", "tool":..., "class":..., "fingerprint":..., "reason":..., "retry":false}` is returned. The agent's system prompt instructs it to stop calling a tool after `retry: false`.

### 4.4 Synchronous Audit and Secret Redaction (FR-5, FR-5.7)

Every heal attempt — including refused and aborted ones — writes exactly one `heal_events` row **before** the result is returned. This is a deliberate trade-off: it adds ~1–5 ms per heal and guarantees no patch is ever applied without a log entry.

The raw error blob is **sanitized before storage**:
- Values of `Authorization`, `Cookie`, `Set-Cookie`, API-key and token headers are redacted.
- Strings equal to any configured secret (`OAUTH_BEARER`, `TENANT_ID`, `JEV_API_KEY`, the LLM key) are replaced.
- Bearer-token and JWT-shaped strings are redacted.
- The blob is truncated to a maximum size.

Header operations store config keys (`{"ref":"config","key":"OAUTH_BEARER"}`), never the bearer value itself.

The `heal_events` schema stores only machine-readable data: enumerated codes, array paths, value references, canonical JSON, and epoch-ms integers. No code-read field contains free text.

### 4.5 Bounded Loops (FR-11)

| Mechanism | Bound |
|---|---|
| `E1` retries | ≤ 3, with backoff 100/200/400 ms + jitter |
| Heal attempts per call | 1 |
| Replays per heal | 1 |
| Heal deadline | 3.5 s total; Jev sub-timeout 1.5 s; spec fetch 0.5 s; replay ≤ 1.0 s |
| Negative cache (S7) | 60 s per failed fingerprint |
| Fix retirement (S6) | Retired after 2 losses |

---

## 5. Benchmark Evaluation and Limitations

### 5.1 Setup

- **Mode:** scripted (fixed tool calls, no LLM; the baseline re-sends a failing call with the same arguments until the iteration cap of 10)
- **N:** 3 runs per scenario per agent
- **Date (UTC):** 2026-10-14 14:05
- **Jev available:** no (M6-N aborts `LOW_CONFIDENCE`, counted as a safe refusal)
- **Spec mode:** `on` for main and tier-0 passes; `off` for the error-only ablation

### 5.2 Per-Scenario Results

| Scenario | Healing ZTAR | Baseline ZTAR | Baseline failure mode | Heal path | MTTR tier 1 (mean/p50/p95 ms) | MTTR tier 0 (mean/p50/p95 ms) |
|---|---|---|---|---|---|---|
| CLEAN | n/a, 100% (3/3) | n/a, 100% (3/3) | — | — | — | — |
| M1 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff ×3 | 11.7/12/13 | 2.3/2/3 |
| M2 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff ×3 | 11.3/12/12 | 1.7/1/3 |
| M3 | 100% (3/3) | 100% (3/3) | — | diff ×3 | 13.7/13/17 | 1/1/1 |
| M4 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff ×3 | 11.7/12/12 | 1/1/1 |
| M5 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff ×3 | 15/15/17 | 3.7/4/4 |
| M6-D | 100% (3/3) | 0% (0/3) | hit cap 3/3 | tiebreak ×3 | 12.7/12/14 | — |
| M6-N | 0% (0/3)† | 0% (0/3) | hit cap 3/3 | — | — | — |
| M7 | 100% (3/3) | 0% (0/3) | ended incomplete 3/3 | diff ×3 | 12/12/13 | — |
| M8 | n/a, 100%‡ | n/a, 0% | hit cap 3/3 | — | — | — |
| M9 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff ×3 | 13.3/13/14 | — |
| C1 | n/a, 100% (3/3) | n/a, 100% (3/3) | — | — | — | — |
| C2 | n/a, 100% (3/3) | n/a, 0% (0/3) | hit cap 3/3 | NOT_DRIFT ×3 | — | — |
| C3 | n/a, 100% (3/3) | n/a, 0% (0/3) | hit cap 3/3 | NOT_DRIFT ×3 | — | — |

† M6-N ZTAR is 0% by design with Jev disabled; the Safe-Refusal Rate is 100% (3/3 `LOW_CONFIDENCE`, no write sent).
‡ M8 is a safe refusal, not an adaptation; counted in Safe-Refusal Rate, not ZTAR.

### 5.3 Summary Metrics

| Metric | Result |
|---|---|
| **ZTAR** (M1–M5, M7, M9) | **100% (21/21)** healing · 14% (3/21) baseline |
| **M6-D** (tie-breaker) | **100% (3/3)** healing · 0% baseline |
| **M6-N** (Jev disabled) | 0% by design · 100% Safe-Refusal Rate |
| **Safe-Refusal Rate** (M8 + M6-N) | **100% (6/6)** |
| **False-Patch Rate** | **0% (0/24 healed runs)** |
| **Tier-1 MTTR** (mean / p50 / p95) | **12.7 / 12 / 17 ms** (n=24) |
| **Tier-0 MTTR** (mean / p50 / p95) | **1.9 / 1 / 4 ms** (n=15) |
| **Token Overhead** | Not measured — scripted mode records 0 LLM tokens; requires `--agent llm` |

### 5.4 Timings by Tier

| Tier | n | mttr_ms mean/p50/p95 | heal_ms mean/p50/p95 |
|---|---|---|---|
| 0 | 15 | 1.9/1/4 | 1.9/1/4 |
| 1 | 24 | 12.7/12/17 | 12.7/12/17 |

### 5.5 Error-Only Ablation (`spec_mode=off`)

Each mutation re-run once with the spec endpoint disabled — diagnosis runs on error clues only. No pass threshold; False-Patch Rate must stay 0.

| Mutation | Outcome | Reason | Final state | False patch |
|---|---|---|---|---|
| M1 | **healed** | — | correct | no |
| M2 | **healed** | — | correct | no |
| M3 | **healed** | — | correct | no |
| M4 | **healed** | — | correct | no |
| M5 | aborted | `NO_CANDIDATE` | correct | no |
| M6-D | aborted | `NO_SAFE_VALUE` | correct | no |
| M6-N | aborted | `NO_SAFE_VALUE` | correct | no |
| M7 | aborted | `NO_CANDIDATE` | correct | no |
| M8 | aborted | `NO_SAFE_VALUE` | correct | no |
| M9 | aborted | `NO_SAFE_VALUE` | correct | no |

**False-Patch Rate (ablation): 0% (0/4 healed runs).** M1–M4 heal on error clues alone; M5, M7, M9 (nested/combined) and M6, M8 (no safe source) abort cleanly as expected.

### 5.6 Limitations

1. **DSL expressiveness.** Fixes are limited to what `move`, `cast`, `header`, `route` can express. Value transforms (splitting a field, unit conversion, format mapping) abort cleanly with `NO_CANDIDATE` or `NO_SAFE_VALUE`. These count against ZTAR, which is the correct outcome. A Tier-2 repair LLM (STRETCH S3) would handle these by emitting validated operation lists within a 30 s budget, never executing generated code.

2. **Silent-drift detection requires postchecks.** `E6` can only be detected for tools that declare postchecks (`echo`/`non_empty`) in `config/tools.json`. An undeclared tool would never see M7-class drift.

3. **Write-tool ambiguity.** M6-N refuses by default when both the tie-breaker and Jev (absent or below threshold) cannot decide. This is intentional. The residual risk — a wrong Jev choice that `preverify` cannot distinguish — is caught only by postchecks after the write and is loud, not silent.

4. **Error-clue mode cannot fix nested or combined changes.** M5 (move + cast + header) and M9 (request nesting) abort `NO_CANDIDATE` without a spec. Measured and reported in the ablation.

5. **Token Overhead not yet measured.** The recorded run is scripted (no LLM), so all `llm_tokens` are 0. An LLM-mode run with `--agent llm` is needed for AC-16.

6. **Single-host only.** The fix store is SQLite. Sharing fixes across instances requires Postgres (FUTURE).

7. **`E3` (undecodable body) not healed.** It returns a structured error with reason `UNSUPPORTED_CLASS`. Healing undecodable bodies is FUTURE.

8. **`agent_schema` rebase watcher not yet built.** The current design freezes `agent_schema` at startup. A future drift watcher would poll spec hashes and precompute fixes before calls fail, allowing an atomic `agent_schema` rebase without a restart when the API version changes significantly enough to warrant it.

---

*Sources: `product.md` §4, §8, §16; `technical-approach.md` §5, §6, §8, §10; `bench/report.md` (2026-10-14, scripted mode, N = 3).*
