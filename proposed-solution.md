# Proposed Solution: Self-Healing Tool Registry (PS 01)

> **PS 01: Self-Healing Tool Registries Under Runtime API Schema Drift**
>
> Related documents: `product.md` (requirements), `technical-approach.md` (design; §4 is the end-to-end workflow), `plan.md` (build order).
>
> **Status labels:** **MVP** = in scope for the hackathon build and demo. **OPTIONAL** = built in the MVP, but every other MVP criterion must pass without it. **STRETCH** = built only after every MVP criterion passes. **FUTURE** = after the hackathon. Phases 0–11 of the build are done (registry, healing core, agents, benchmark, dashboard), and the build is being aligned with the current spec (`plan.md`, phase 12). Two STRETCH items, the persistent fix store (S6) and the negative cache with single-flight (S7), are already built and tested. Numbers below are **targets**, except the scripted-mode results from `bench/report.md` (no LLM, N = 3), which are cited as measured and labelled as such.

---

## 1. Solution Overview

Agents break when an API changes under them. Their tool definitions were generated once from an OpenAPI spec, so a renamed field, a changed type, a nested response or a new mandatory header turns every call into a `4xx` or into silently wrong data. Standard frameworks pass the raw error back to the agent, and the agent retries the same broken call until it runs out of iterations.

**Our solution is a self-healing tool registry.** It is a layer between the agent and the API that:

- **detects** drift at runtime, including drift that returns `200`,
- **diagnoses** it by diffing the API's current OpenAPI spec against the version the agent was built on,
- **builds** the smallest fix from four safe operations,
- **hot-patches** the tool definition in memory,
- **re-sends** the call once and **verifies** the result before keeping the fix,
- **logs** every patch,
- **returns** the result, so the agent finishes its task without noticing the break.

The core idea in one line: **deterministic code heals (including a deterministic tie-breaker), Jev is an optional last-resort tie-breaker, nothing is invented, and nothing loops.**

## 2. Key Components

| Component | What it does | Status |
|---|---|---|
| **Agent** | A tool-calling LLM agent on a standard framework (LangGraph `create_react_agent`, Claude via OpenRouter, default `anthropic/claude-haiku-5.5`). It does the user's task and calls tools only through the registry. A scripted no-LLM agent runs the same task for keyless benchmark runs and paced demos. | MVP |
| **Tool Registry** | Generates tools from the OpenAPI spec. Keeps each tool's agent-facing schema frozen and its wire schema current. Holds the active fix. Entry point for every call. | MVP |
| **Self-Healing Layer** (Heal Controller) | Runs detection, then the diagnosis path (tier 1). Enforces the deadline and one attempt per call. After a heal, the tool's in-memory definition carries the fix. The stored-fix path (tier 0), the negative cache and single-flight are STRETCH and already built. | MVP (tier 0, negative cache, single-flight: STRETCH) |
| **Schema Diagnosis Engine** | Fetches the current spec and diffs it structurally against the stored snapshot. Reads error clues (FastAPI `422` locations and types). Builds candidate fixes. With several, a deterministic tie-breaker scores them on description match, parameter order and type. Falls back to error-clue mode when the spec is unavailable or switched off. | MVP |
| **Jev (TypeSafe AI)** | A hosted, non-generative classifier. Called at most once, only when two or more valid fixes exist and the tie-breaker finds no unique winner. It selects one with a confidence score and never writes values. The system works without it. | OPTIONAL |
| **Patch Validator** (Safety Gate + Verifier) | Before sending: checks value provenance, lossless casts, minimal size, replay safety and the write-tool ambiguity rule. After sending: re-runs every check, including postchecks. | MVP |
| **Audit Logger** | Writes one machine-readable event per heal attempt (recovered, refused or failed), synchronously, before the agent gets a result. The raw error is redacted before it is stored. Persisting fixes for reuse across restarts is STRETCH (S6) and already built. | MVP (fix persistence: STRETCH) |
| **Mock Drift API** | A FastAPI service with four operations, a live OpenAPI spec, a runtime mutation switch and a state endpoint for correctness checks. | MVP |
| **Baseline Agent** | The same framework, LLM, prompt and task, with no registry. | MVP |
| **Benchmark + Dashboard** | Measures ZTAR, Safe-Refusal Rate, False-Patch Rate, MTTR and Token Overhead, plus an error-only ablation. The dashboard is a FastAPI service with one static HTML page; it runs a prompt against both agents on any scenario or a custom drift, shows every tool call's input, wire requests and output, the live tool registry, and a patch log. | MVP |

## 3. How the Solution Works

The full step-by-step flow, with timings, is in `technical-approach.md` §4. In short:

1. **Call.** The agent calls `get_user({"user_id": "123"})`. The registry validates the arguments against the frozen agent schema, applies any active fix, and sends the request.
2. **Detect.** The response is classified:
   - `OK`, or `BUSINESS` (a real error such as "user not found", or a rejected value such as an invalid email when the spec has not changed): returned to the agent unchanged and never healed,
   - `E1` (transient): bounded retry,
   - `E2`, `E4`, `E5`, `E6` (drift): heal. Drift covers rejected requests, errors hidden inside a `200`, changed response shapes, and inputs the API silently ignored,
   - `E3` (an unreadable, non-JSON reply): returned as a structured error (`UNSUPPORTED_CLASS`). Healing it is FUTURE.
3. **Name the break.** A fingerprint is built from what broke (the tool, class, code, and paths with violation kinds), not from message text. After a heal, the tool's definition carries the fix, so the same break does not recur in this process. Reusing stored fixes by fingerprint, including after a restart (tier 0, milliseconds), is STRETCH (S6) and already built.
4. **Diagnose (tier 1).** The engine downloads the API's current OpenAPI spec and diffs it against the stored version: removed fields, added required fields, type changes, new headers or security, route changes, response-shape changes. It then builds every valid fix from four operations (`move`, `cast`, `header`, `route`).
   - **0 fixes:** stop safely.
   - **1 fix:** use it.
   - **2 or more:** a deterministic tie-breaker scores the fixes on description match, parameter order and type. A unique winner is used. With no unique winner, Jev (optional) chooses one. If Jev is missing, slow or not confident, the call stops with `LOW_CONFIDENCE` before anything is sent. On a write tool the rule is stricter: the tie-breaker must win on description evidence, or Jev must be confident at the higher write threshold and a read-only check must confirm its choice before any write.
5. **Validate before sending.** Every value must come from the agent's arguments or from config. Casts must be lossless. The fix must not be bigger than the problem. Replaying must be safe.
6. **Patch in memory.** The fix is applied to the tool definition with no restart. The agent-facing schema does not change; only the translation behind it does.
7. **Re-send once and verify.** All checks run again, including postchecks such as "the response must echo the user id we sent".
8. **Commit or roll back.**
   - **Pass:** record the fix (persisted under S6), bump the tool version, log the event, and return the result. The agent's workflow simply continues.
   - **Fail:** discard the fix, block this fingerprint for 60 s (STRETCH, S7, already built), log the event, and return `retry: false`. The agent treats that tool as unavailable, skips it and finishes the rest of the task instead of looping.

## 4. Handling Schema Mutations

| Mutation | What breaks | How it is fixed | Status |
|---|---|---|---|
| **Field rename** (M1: `user_id` becomes `customer_id`) | `422`: `customer_id` missing | The diff shows one field removed and one added with the same type and a shared name token. Fix: `move`. | MVP |
| **Type conversion** (M2: `user_id` string becomes integer) | `422`: wrong type | Fix: `cast`, only if `"123"` converts to `123` and back exactly | MVP |
| **Response nesting** (M3: `{id,...}` becomes `{data:{id,...}}`) | `200`, but the response no longer matches the expected shape | The fields are located under `data` and moved back to the shape the agent expects. Applied to the reply already received, so no extra call is needed. | MVP |
| **New mandatory header** (M4: OAuth bearer) | `401` with `WWW-Authenticate: Bearer` | Fix: `header`, with the token taken from configuration, never generated | MVP |
| **Problem-statement example** (M5: `{"user_id":"123"}` becomes `{"target":{"id":123}}` plus a new header) | `422`: `target` and the header missing | One fix of `move` + `cast` + `header`, built and verified in a single heal | MVP |
| **Ambiguous rename, usable descriptions** (M6-D: two fields renamed with no shared words) | `422` | Two valid fixes exist. The deterministic tie-breaker picks the one the OpenAPI field descriptions support. No Jev call. | MVP |
| **Ambiguous rename, no usable descriptions** (M6-N) | `422` | The tie-breaker cannot decide. With Jev configured, Jev chooses, but on a write tool only at high confidence and after a read-only check confirms the choice. Otherwise the call is refused with `LOW_CONFIDENCE` and nothing is sent. Reported separately, not counted in ZTAR. | OPTIONAL (Jev) |
| **Silent ignore** (M7: the API ignores the old field and returns `200`) | Nothing visible, except that the data didn't change | A postcheck catches it, and the spec diff gives the fix | MVP |
| **Unfillable new field** (M8: new required `priority` with no source) | `422` | Refused with `NO_SAFE_VALUE`. The system never invents `"medium"`. | MVP |
| **Request nesting** (M9: the flat body `{user_id, email}` becomes `{payload:{user_id, email}}`) | `422`: the request shape no longer matches | Fix: `move` ×2, wrapping only (no rename, no type change, no header) | MVP |
| **Value error, not drift** (C3: an invalid email on an unchanged spec) | `422` | Recognized as a legitimate error, not drift. Returned to the agent unchanged (audit reason `NOT_DRIFT`), never "fixed" and never replayed. | MVP |
| **API rolled back to v1** | A stale fix now causes structural `422` violations while the spec diff is empty | The stale fix is dropped and the original request is replayed once and verified. With no active fix, the call is refused with `NO_CANDIDATE`. | MVP |
| **Unreadable reply** (`E3`: non-JSON body) | The reply cannot be parsed | Returned as a structured error (`UNSUPPORTED_CLASS`). Healing it is FUTURE. | FUTURE |
| **Injected instructions** (M10: hostile text in the error message and in a field description) | `422` | Ignored. The same fix as the plain rename is built; nothing is derived from the injected text. | STRETCH |
| Value transforms (splitting a field, unit changes) | n/a | Clean refusal in the MVP. A repair LLM that may only emit verified operations is STRETCH. | STRETCH |
| GraphQL and gRPC drift | n/a | The same pipeline behind new adapters | STRETCH |

## 5. Safety and Reliability

| Threat | Prevention |
|---|---|
| **Hallucinated values** | No fix operation can write a literal value. Values come only from the agent's arguments, configuration, or the API's own spec. A required value with no source causes a refusal. Jev (optional) only selects among fixes that code built. |
| **Unsafe patches** | The safety gate checks provenance, lossless casts, minimal size and replay safety before anything is sent. A replay is allowed only when the server rejected the request (`E2`), the tool is idempotent, or an idempotency key is present. A call the server may already have accepted (`E4`, `E6`) is replayed only for an idempotent tool or with a key. A changed response shape (`E5`) is never replayed: the reply already received is remapped locally. |
| **Guessing between equally valid fixes** | On a write tool with two or more valid fixes, the system refuses unless the deterministic tie-breaker wins on description evidence, or Jev is confident at the write threshold and a read-only check (`preverify`) confirms the choice before anything is written. Otherwise `LOW_CONFIDENCE`, and nothing is sent. Residual risk: a wrong choice that the check cannot distinguish is caught only by postchecks after the write, and flagged. |
| **Mistaking a legitimate error for drift** | A `409`, a missing record, and a value error on an unchanged spec are returned unchanged and never healed or replayed (`NOT_DRIFT`). |
| **Prompt injection through error text or descriptions** | Error bodies and OpenAPI descriptions are data. They are matched against the spec structure and compared as tokens only; no value, field, header or operation is derived from their wording. Jev's output is limited to an index from a list that code built. The M10 scenario demonstrates this (STRETCH). |
| **Infinite retries** | One heal attempt per call. One replay per heal. A 3.5 s deadline. Transient errors get at most 3 retries. The agent is told `retry: false`, skips that tool and carries on. Failed fingerprints are also blocked for 60 s (STRETCH, S7, already built). |
| **Silent data corruption** | Every fix is verified against the output schema and declarative postchecks before it is kept. The benchmark checks the API's final data state, not just the agent's claim of success, and reports the False-Patch Rate (target 0). |
| **Untraceable changes** | Every heal attempt is logged before the agent sees a result, in machine-readable form: fingerprint, class, tier, decision path, operations, reason, timing and tokens. |
| **Secrets leaking into logs** | The raw error is redacted before it is stored: auth and cookie headers, configured secret values, and bearer-token and JWT-shaped strings. Header operations store config keys, never values. |
| **Bad fixes sticking** | Fixes are always computed from the original schema, so an API rollback heals correctly too. Each fix also tracks wins and losses and is retired after 2 losses (STRETCH, S6, already built). |

## 6. Innovation and Differentiation

| Conventional agent | Our approach |
|---|---|
| Treats the tool schema as fixed truth | Treats the live API spec as truth and translates at runtime |
| Detects failure only from `4xx` errors | Also catches drift that returns `200`: changed shapes, ignored inputs, errors hidden in success bodies |
| Sends errors back to the LLM, which guesses and retries | Code diagnoses with a structural spec diff; the LLM never sees the break |
| Retries until it runs out of iterations | One verified attempt, then a clean refusal with a reason code; the agent skips that tool and finishes the rest |
| Uses expensive LLM reasoning per failure | A deterministic fix for clear breaks and a deterministic tie-breaker for ambiguous ones; one optional Jev classification only if that still ties |
| Forgets every incident | The tool's definition carries the fix after a heal, so the same break does not recur in this process. A persistent fix store gives repeats millisecond fixes that survive restarts (STRETCH, S6, already built) |
| Fix logic would be free-form generated code | Fixes are a small verifiable data language, easy to audit and impossible to use for inventing values |

Why this works:
- **Speed:** heals without a Jev call need no model at all.
- **Safety:** the operation set makes inventing values structurally impossible.
- **Low tokens:** recovery happens below the agent, so the agent spends no extra reasoning on the break.

## 7. Expected Impact and Evaluation

**Baseline comparison.** Both agents get the same framework, LLM (temperature 0), prompt, task, tools generated from the v1 spec, and iteration cap of 10. The only difference is the registry. Each scenario is run N = 10 times per agent from a reset state:
- the four required mutations,
- the problem-statement example,
- the ambiguous rename (with and without usable descriptions), silent ignore, request nesting and unfillable-field cases,
- the transient, business-error and value-error controls,
- clean runs with no mutation, to set the token baseline.

| Metric | Definition | Target |
|---|---|---|
| **Zero-Touch Adaptation Rate** | Over the healable mutations only (M1 to M5, M7, M9): runs completed correctly (task done *and* the API's final data state correct) with no human input, divided by all such runs. The ambiguous rename (M6) and injection (M10) cases are reported separately. | 100% with Jev absent |
| **Safe-Refusal Rate** | Over the runs that must be refused (the unfillable field M8, and M6-N with Jev disabled): the share that aborted with the expected reason code and sent no invented value | 100% |
| **False-Patch Rate** | The share of healed runs (a fix passed verification and success was returned) whose final data state was wrong | 0 |
| **MTTR** | From the first failing response caused by the mutation to the first verified-correct result returned to the agent. Mean, median and p95. The registry's own heal time (`heal_ms`) is reported separately. | First occurrence (tier 1): p95 under 4 s. Repeat (tier 0, STRETCH and already built): p95 under 0.5 s. |
| **Token Overhead** | The healing agent's extra tokens on a mutated run, compared with its median on clean runs, set against the tokens the baseline wastes in its failed loop. Jev's own usage is reported in a separate column and never added. | Below the baseline's wasted tokens for M1 to M7 and M9. Expected to be near zero when no Jev call is needed; to be measured. |

Also reported: an **error-only ablation** (M1 to M9 re-run with the spec endpoint disabled, healed or aborted per mutation with the reason code; no pass threshold, and the False-Patch Rate must stay 0), and the baseline's outcome in every scenario (error loop, calls made, tokens, final data correctness), measured but not asserted.

**Measured so far (scripted mode only).** The run recorded in `bench/report.md` uses fixed tool calls with no LLM (N = 3 per scenario and agent, 2026-10-14) under the current metric definitions, including M9 and the M6-D / M6-N split; it is local and tiny, so treat it as indicative:
- ZTAR over the healable mutations (M1 to M5, M7, M9): the healing agent completed the task with the correct final mock state in 21 of 21 runs, the baseline in 3 of 21. The baseline completed M3 in 3 of 3 runs, hit its 10-call cap on M1, M2, M4, M5, M6-D, M6-N, M8, M9, C2 and C3, and ended incomplete on M7.
- M6 reported separately: M6-D healed through the deterministic tie-breaker in 3 of 3 runs with no Jev call; M6-N aborted `LOW_CONFIDENCE` without writing in 3 of 3 runs (Jev disabled), which counts as a safe refusal.
- Registry-internal heal time for tier-1 heals, median / p95 in ms: M1 47 / 48, M2 45 / 66, M3 47 / 49, M4 52 / 53, M5 57 / 69, M6-D 47 / 51, M7 52 / 53, M9 50 / 58. Repeat (tier-0) heals took 3 to 8 ms. Timings are wall-clock on a shared laptop and move with machine load: across benchmark runs on 2026-10-14 the tier-1 p50 ranged from 12 to 49 ms. Every run stayed far under the 4 s MTTR budget.
- Safe-Refusal Rate: 6 of 6 (M8 refused `NO_SAFE_VALUE` in 3 of 3 runs with no request carrying `priority`; M6-N as above). False-Patch Rate: 0 of the 24 healed runs ended with a wrong final state.
- Error-only ablation (reported without a pass threshold): M1 to M4 healed on the error clue alone; M5 and M7 aborted `NO_CANDIDATE`; M6-D, M6-N, M8 and M9 aborted `NO_SAFE_VALUE`; no false patches.
- Scripted mode records 0 LLM tokens, so Token Overhead is not yet measured. It needs a run with a real LLM.

**Live demo (about 30 s).**
1. Both agents start the same task.
2. The mock API's schema changes on stage (the problem-statement example).
3. The baseline hits `422` and loops until it fails. Our agent completes in about 2–3 s, and the patch log shows exactly what changed and how it was fixed.
4. A second mutation hits another tool and heals.
5. The unfillable-field mutation shows the system refusing to invent a value.
6. The metrics panel shows the measured ZTAR, MTTR and Token Overhead.

The demo does not depend on Jev: every step above heals or refuses without it.

**Expected impact.** Long-lived agents keep working through routine API changes with no redeploy. Every change is traceable. The system fails safely, and loudly, when a change can't be fixed without guessing. This directly targets the interface-drift outages that the problem statement attributes over 40% of tool-call failures to.
