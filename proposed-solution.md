# Proposed Solution: Self-Healing Tool Registry (PS 01)

> **PS 01: Self-Healing Tool Registries Under Runtime API Schema Drift**
>
> Related documents: `product.md` (requirements), `technical-approach.md` (design; §4 is the end-to-end workflow), `plan.md` (build order).
>
> **Status labels:** **MVP** = in scope for the hackathon build and demo. **STRETCH** = built only if time allows after the MVP is demo-ready. **FUTURE** = after the hackathon. The project is at the design stage. Numbers below are **targets** until the benchmark produces measured results.

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

The core idea in one line: **deterministic code heals, Jev only breaks ties, nothing is invented, and nothing loops.**

## 2. Key Components

| Component | What it does | Status |
|---|---|---|
| **Agent** | A tool-calling LLM agent on a standard framework. It does the user's task and calls tools only through the registry. | MVP |
| **Tool Registry** | Generates tools from the OpenAPI spec. Keeps each tool's agent-facing schema frozen and its wire schema current. Holds the active fix. Entry point for every call. | MVP |
| **Self-Healing Layer** (Heal Controller) | Runs detection, then the stored-fix path (tier 0) or the diagnosis path (tier 1). Enforces the deadline, one attempt per call, the negative cache and single-flight. | MVP |
| **Schema Diagnosis Engine** | Fetches the current spec and diffs it structurally against the stored snapshot. Reads error clues (FastAPI `422` locations and types). Builds candidate fixes. | MVP |
| **Jev (TypeSafe AI)** | A hosted, non-generative classifier. Called once, only when two or more valid fixes exist. It selects one with a confidence score and never writes values. | MVP |
| **Patch Validator** (Safety Gate + Verifier) | Before sending: checks value provenance, lossless casts, minimal size and replay safety. After sending: re-runs every check, including postchecks. | MVP |
| **Audit Logger** | Writes one machine-readable event per heal attempt (recovered, refused or failed), synchronously, before the agent gets a result. Stores fixes for reuse. | MVP |
| **Mock Drift API** | A FastAPI service with four operations, a live OpenAPI spec, a runtime mutation switch and a state endpoint for correctness checks. | MVP |
| **Baseline Agent** | The same framework, LLM, prompt and task, with no registry. | MVP |
| **Benchmark + Dashboard** | Measures ZTAR, MTTR and Token Overhead; shows both agents live with a patch log. | MVP |

## 3. How the Solution Works

The full step-by-step flow, with timings, is in `technical-approach.md` §4. In short:

1. **Call.** The agent calls `get_user({"user_id": "123"})`. The registry validates the arguments against the frozen agent schema, applies any active fix, and sends the request.
2. **Detect.** The response is classified:
   - `OK`, or `BUSINESS` (a real error such as "user not found"): returned to the agent unchanged,
   - `E1` (transient): bounded retry,
   - `E2`–`E6` (drift): heal. Drift covers rejected requests, unreadable replies, errors hidden inside a `200`, changed response shapes, and inputs the API silently ignored.
3. **Name the break.** A fingerprint is built from what broke (the tool, class, code, and paths with violation kinds), not from message text. If a fix for this fingerprint already exists, it is reused (tier 0, milliseconds).
4. **Diagnose (tier 1).** The engine downloads the API's current OpenAPI spec and diffs it against the stored version: removed fields, added required fields, type changes, new headers or security, route changes, response-shape changes. It then builds every valid fix from four operations (`move`, `cast`, `header`, `route`).
   - **0 fixes:** stop safely.
   - **1 fix:** use it.
   - **2 or more:** Jev chooses one, and low confidence means stop.
5. **Validate before sending.** Every value must come from the agent's arguments or from config. Casts must be lossless. The fix must not be bigger than the problem. Replaying must be safe.
6. **Patch in memory.** The fix is applied to the tool definition with no restart. The agent-facing schema does not change; only the translation behind it does.
7. **Re-send once and verify.** All checks run again, including postchecks such as "the response must echo the user id we sent".
8. **Commit or roll back.**
   - **Pass:** store the fix, bump the tool version, log the event, and return the result. The agent's workflow simply continues.
   - **Fail:** discard the fix, block this fingerprint for 60 s, log the event, and return `retry: false`. The agent stops instead of looping.

## 4. Handling Schema Mutations

| Mutation | What breaks | How it is fixed | Status |
|---|---|---|---|
| **Field rename** (`user_id` becomes `customer_id`) | `422`: `customer_id` missing | The diff shows one field removed and one added with the same type and a shared name token. Fix: `move`. | MVP |
| **Type conversion** (`user_id` string becomes integer) | `422`: wrong type | Fix: `cast`, only if `"123"` converts to `123` and back exactly | MVP |
| **Response nesting** (`{id,...}` becomes `{data:{id,...}}`) | `200`, but the response no longer matches the expected shape | The fields are located under `data` and moved back to the shape the agent expects. Applied to the reply already received, so no extra call is needed. | MVP |
| **New mandatory header** (OAuth bearer) | `401` with `WWW-Authenticate: Bearer` | Fix: `header`, with the token taken from configuration, never generated | MVP |
| **Problem-statement example** (`{"user_id":"123"}` becomes `{"target":{"id":123}}` plus a new header) | `422`: `target` and the header missing | One fix of `move` + `cast` + `header`, built and verified in a single heal | MVP |
| **Ambiguous rename** (two fields renamed with no shared words) | `422` | Two valid fixes exist, so Jev chooses. Postchecks confirm the choice. | MVP |
| **Silent ignore** (the API ignores the old field and returns `200`) | Nothing visible, except that the data didn't change | A postcheck catches it, and the spec diff gives the fix | MVP |
| **Unfillable new field** (new required `priority` with no source) | `422` | Refused with `NO_SAFE_VALUE`. The system never invents `"medium"`. | MVP |
| Value transforms (splitting a field, unit changes) | n/a | Clean refusal in the MVP. A repair LLM that may only emit verified operations is STRETCH. | STRETCH |
| GraphQL and gRPC drift | n/a | The same pipeline behind new adapters | STRETCH |

## 5. Safety and Reliability

| Threat | Prevention |
|---|---|
| **Hallucinated values** | No fix operation can write a literal value. Values come only from the agent's arguments, configuration, or the API's own spec. A required value with no source causes a refusal. Jev only selects among fixes that code built. |
| **Unsafe patches** | The safety gate checks provenance, lossless casts, minimal size and replay safety before anything is sent. A non-idempotent call is never replayed unless the server rejected it or an idempotency key is present. |
| **Infinite retries** | One heal attempt per call. One replay per heal. A 3.5 s deadline. Failed fingerprints are blocked for 60 s. Transient errors get at most 3 retries. The agent is told `retry: false` and stops. |
| **Silent data corruption** | Every fix is verified against the output schema and declarative postchecks before it is kept. The benchmark checks the API's final data state, not just the agent's claim of success. A confident wrong choice on a write tool is flagged loudly in the audit log. |
| **Untraceable changes** | Every heal attempt is logged before the agent sees a result, in machine-readable form: fingerprint, class, tier, operations, reason, timing and tokens. |
| **Bad fixes sticking** | Each fix tracks wins and losses and is retired after 2 losses. Fixes are always computed from the original schema, so an API rollback heals correctly too. |

## 6. Innovation and Differentiation

| Conventional agent | Our approach |
|---|---|
| Treats the tool schema as fixed truth | Treats the live API spec as truth and translates at runtime |
| Detects failure only from `4xx` errors | Also catches drift that returns `200`: changed shapes, ignored inputs, errors hidden in success bodies |
| Sends errors back to the LLM, which guesses and retries | Code diagnoses with a structural spec diff; the LLM never sees the break |
| Retries until it runs out of iterations | One verified attempt, then a clean stop with a reason code |
| Uses expensive LLM reasoning per failure | A deterministic fix for clear breaks; one cheap Jev classification only for ambiguous ones |
| Forgets every incident | Stores each fix by fingerprint; repeats are fixed in milliseconds and survive restarts |
| Fix logic would be free-form generated code | Fixes are a small verifiable data language, easy to audit and impossible to use for inventing values |

Why this works:
- **Speed:** heals without a Jev call need no model at all.
- **Safety:** the operation set makes inventing values structurally impossible.
- **Low tokens:** recovery happens below the agent, so the agent spends no extra reasoning on the break.

## 7. Expected Impact and Evaluation

**Baseline comparison.** Both agents get the same framework, LLM (temperature 0), prompt, task, tools generated from the v1 spec, and iteration cap of 10. The only difference is the registry. Each scenario is run N = 10 times per agent from a reset state:
- the four required mutations,
- the problem-statement example,
- the ambiguous rename, silent ignore and unfillable-field cases,
- the transient and business-error controls.

| Metric | Definition | Target |
|---|---|---|
| **Zero-Touch Adaptation Rate** | Mutation runs completed correctly (task done *and* the API's final data state correct) with no human input, divided by all mutation runs | 100% on the four required mutations and the problem-statement example. Overall rate reported, including the deliberate refusal case. |
| **MTTR** | From the start of the first failing call to the healed result being returned | First occurrence (tier 1): p95 under 4 s. Repeat (tier 0): p95 under 0.5 s. |
| **Token Overhead** | Extra tokens caused by the break (agent LLM + Jev), compared with tokens the baseline wastes in its failed loop | Below the baseline's wasted tokens for every fixable scenario. Expected to be near zero when no Jev call is needed; to be measured. |

**Live demo (about 30 s).**
1. Both agents start the same task.
2. The mock API's schema changes on stage (the problem-statement example).
3. The baseline hits `422` and loops until it fails. Our agent completes in about 2–3 s, and the patch log shows exactly what changed and how it was fixed.
4. A second mutation hits another tool and heals.
5. The unfillable-field mutation shows the system refusing to invent a value.
6. The metrics panel shows the measured ZTAR, MTTR and Token Overhead.

**Expected impact.** Long-lived agents keep working through routine API changes with no redeploy. Every change is traceable. The system fails safely, and loudly, when a change can't be fixed without guessing. This directly targets the interface-drift outages that the problem statement attributes over 40% of tool-call failures to.
