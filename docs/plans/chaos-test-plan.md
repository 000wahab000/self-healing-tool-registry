# Chaos test plan: external APIs, schema manipulation, crash scenarios

Status: proposal, 2026-10-17. Nothing here has run yet.

## 1. Goal and honesty rules

Find where the registry breaks on APIs we did not build, with drift we did not hand-pick.

1. **Pre-registered outcomes.** Every case and its expected outcome (`heal`, `refuse`, `pass_through`, `out_of_scope`) goes in `bench/chaos/cases.yaml`, committed before the first run. The report cites the commit hash. No case is dropped or edited after a run; a wrong expectation is fixed in a new, separate commit and reported as such.
2. **Independent oracle.** The judge of a healed call is never our own verifier. It is Prism / stripe-mock request validation against the new spec, httpbin's echo of what it received, or the upstream MCP server's own result.
3. **Real drift first.** Where an API has version history, drifts come from real consecutive spec versions, not from our catalog. Synthetic drifts are a second, labelled set.
4. **Report everything.** Every case appears in the report: healed, refused, missed, wrong (false patch), crashed, timed out.

## 2. The test agent

A fresh, small agent with exactly one tool connection: the healer's MCP front door.

```
claude -p "<task>" --model haiku \
  --mcp-config bench/chaos/mcp-healer.json --strict-mcp-config \
  --allowedTools "mcp__healer" \
  --disallowedTools "Bash,Read,Write,Edit,WebFetch,WebSearch,Task" \
  --output-format stream-json --session-id <uuid>
```

- `mcp-healer.json` lists one server: `http://127.0.0.1:8097/mcp`. No GitHub, Stripe or other MCP is visible to the agent; those sit behind the registry as upstreams.
- Tasks run in sequence in one session (`--resume <session-id>`), so the agent carries context and stale assumptions from task to task. That is how a real agent meets drift.
- A separate **chaos controller** (`bench/chaos/controller.py`, no LLM) changes the world between and during tasks. It records a timeline of what was live when.
- The **recorder** joins three logs by time: agent stream-json (what the agent sent and saw), registry audit + `call_events`, and the oracle's request log.

### Manipulating the schema in the agent's tool context

Two separate kinds of damage. The registry is only supposed to fix the first.

| Kind | How | Expected |
|---|---|---|
| A. API drifts, agent schema frozen | Controller swaps the upstream spec / MCP `inputSchema`; the agent keeps its frozen v1 tool schema | Registry heals or refuses safely |
| B. Agent's context is wrong | The task text carries stale or wrong tool docs ("`get_user` takes `uid`"), old example arguments, a hallucinated tool name, wrong types, extra fields, prompt injection in an error body | Registry rejects bad agent input with a structured error (`AGENT_ARG_ERROR`, `UNKNOWN_TOOL`) and never "heals" agent mistakes into a wrong write |

For kind B we do not touch the agent's tool list itself. The rule is one MCP connection, so the skew is injected through the task text only.

## 3. Targets

| # | Target | How it is wired | What is real | Drift source |
|---|---|---|---|---|
| T1 | **GitHub MCP** (official `github/github-mcp-server`) | Upstream MCP in `config/mcp_servers.json`, token env `MCP_GITHUB_TOKEN` | Real GitHub, fine-grained PAT scoped to one sandbox repo the user owns | **Drift shim**: a small MCP proxy between registry and GitHub MCP that rewrites `tools/list` `inputSchema` (rename, type, wrap, required) and maps the call back, the same idea as `mock_api/mcp_drift_server.py` |
| T2 | **GitHub REST** | `apis` entry, `kind: openapi` | Spec: `github/rest-api-description`. Live: read-only GETs to `api.github.com` for the baseline only | **Real version diffs** between tagged releases of the description, served by Prism |
| T3 | **Stripe** | `apis` entry, `kind: openapi` | Specs: `stripe/openapi` tags. Server: `stripe-mock` (offline, no key) | **Real API version changes**: consecutive `stripe/openapi` versions, plus the `Stripe-Version` header switch |
| T4 | **httpbin** (local docker `kennethreitz/httpbin` or `go-httpbin` binary) | `apis` entry | Real HTTP behaviour: status codes, delays, malformed bodies | Transport faults (section 4) |
| T5 | **Petstore v3** | `apis` entry, Prism | Classic third-party spec | Synthetic drift catalog on a spec we did not write |
| T6 | **Countries GraphQL** (`countries.trevorblades.com`, read-only, public) | `apis` entry, `kind: graphql` | Live public GraphQL | Live baseline, plus a local schema-drift copy |

### Stripe money safety (hard rules)

- Default run is **fully offline**: `stripe-mock` plus spec files. No Stripe key exists in that environment.
- Optional live arm uses **test mode only**. The controller refuses to start unless the key starts with `sk_test_` or `rk_test_`, and the env var is named `API_STRIPE_TEST_KEY`. A live key aborts the run.
- **Write block at the proxy.** The logging proxy in front of Stripe returns 403 for `POST` to `/v1/charges`, `/v1/payment_intents/*/confirm`, `/v1/payouts`, `/v1/transfers`, `/v1/refunds`, `/v1/topups`. `selected_operations` exposes read-only GETs plus `POST /v1/customers` (test mode, no money).
- Version simulation uses real Stripe API versions: the same call with `Stripe-Version: <old>` vs `<new>`, and the registry pinned to the old spec while the server answers with the new.

### GitHub safety

- Fine-grained PAT with read-only access to one sandbox repo, for example `<user>/healer-chaos-sandbox`. The only write tool exposed is `create_issue`, on that repo, in the T1 write task.
- `selected_operations` lists the exact tools; nothing else is exposed.

## 4. Error catalog

Each row becomes cases in `cases.yaml` with a pre-registered expected outcome.

### 4.1 Schema drift (kind A)

| Id | Drift | Expected |
|---|---|---|
| D1 | Body field rename | heal |
| D2 | Query param rename | heal |
| D3 | Path param rename | heal |
| D4 | Route move (`/x/{id}` to `/v2/x/{id}`) | heal |
| D5 | String to integer (lossless value) | heal |
| D6 | String to integer (non-numeric value) | refuse |
| D7 | Wrap body under a new object | heal |
| D8 | Unwrap | heal |
| D9 | Enum value renamed | heal if 1:1 mapping in spec, else refuse |
| D10 | New required field with default | heal |
| D11 | New required field, no default | refuse (no invented value) |
| D12 | Auth header or API-key header name change | heal |
| D13 | Method change (POST to PUT) | heal or out_of_scope |
| D14 | Response field rename or nesting | heal (response ops) |
| D15 | Field split (`name` to `first_name` + `last_name`) | refuse |
| D16 | Units change, same name and type (cents to dollars) | out_of_scope (undetectable): report as a known miss |
| D17 | Two same-typed fields swap names | out_of_scope: known miss |
| D18 | Pagination change (page to cursor) | refuse or out_of_scope |
| D19 | Description-only change | pass_through, no heal |
| D20 | Flip-flop: drift, then revert within 5 s | no stale fix after revert |
| D21 | Two drifts at once on one tool | heal or refuse; never wrong |
| D22 | Real version diff (T2, T3) | expected outcome written per diff before the run |

### 4.2 Transport and server crashes

| Id | Fault | Expected |
|---|---|---|
| F1 | 500 once, then OK | retry, success, no heal |
| F2 | 503 with `Retry-After` seconds and HTTP-date | retry honoured |
| F3 | 429 rate limit | backoff, no heal |
| F4 | Timeout longer than `REQUEST_TIMEOUT_S` | E1, retried, structured error |
| F5 | Connection reset / server killed mid-call | structured error, no crash of the gateway |
| F6 | Malformed JSON body | structured error |
| F7 | Truncated body | structured error |
| F8 | 10 MB response | bounded, no hang |
| F9 | 503 after a write was saved | never replay the write (D1/G3 rule) |
| F10 | DNS failure for the API host | E1, retryable |
| F11 | Host resolves to a private IP | blocked egress, non-retryable |

### 4.3 Spec and upstream MCP faults

| Id | Fault | Expected |
|---|---|---|
| S1 | Spec URL unreachable during a heal | clue mode or refuse |
| S2 | Invalid spec document | refuse, no crash |
| S3 | Cyclic `$ref` | load or refuse, no recursion crash |
| S4 | Spec changes during a heal | one audit row, no half-applied fix |
| M1 | Upstream MCP process crashes | structured error; recovers after restart |
| M2 | `tools/list` changes between calls | heal on next call |
| M3 | JSON-RPC `-32602` / `-32603` | correct class, preflight replay only where safe |
| M4 | `isError: true` business error | pass_through |

### 4.4 Agent context skew (kind B)

| Id | Skew | Expected |
|---|---|---|
| A1 | Stale argument name from old docs | `AGENT_ARG_ERROR`, no heal of agent input |
| A2 | Hallucinated tool | `UNKNOWN_TOOL` |
| A3 | Wrong type from the agent | structured error |
| A4 | Extra unknown fields | rejected for REST (strict args) |
| A5 | Prompt injection in the API's error text | ignored by registry and repair |
| A6 | Agent retries a refused call 10 times | bounded; negative cache holds |

### 4.5 Registry-side crashes

| Id | Fault | Expected |
|---|---|---|
| R1 | Gateway restarted mid-session | stored fix served at tier 0 after restart |
| R2 | SQLite locked by another writer | no data loss, structured error |
| R3 | Two agents hit the same drift at once | single-flight: one heal, one audit row |

## 5. Task sequence for the agent

One session per target, tasks in this order. The controller acts at the marked points.

| Step | Task given to the agent | Controller action |
|---|---|---|
| 1 | Baseline: run the target's read task (GitHub: list issues in the sandbox repo; Stripe: list customers; Petstore: find pet 1) | none |
| 2 | Same task again | apply one drift from 4.1 before the call |
| 3 | A write task (GitHub: create an issue in the sandbox; Stripe: create a test customer; Petstore: add a pet) | apply a write-path drift |
| 4 | A chained task (read, then write using the read's output) | drift between the two calls |
| 5 | Repeat step 2 | revert the drift (flip-flop check) |
| 6 | A task with stale docs in the prompt | kind B skew |
| 7 | Read task | transport fault from 4.2 |
| 8 | Read task | restart the gateway first (R1) |
| 9 | Final summary: agent lists what failed and why | none |

Each drift or fault id runs N = 5 times per target (fresh session each repeat) to separate flakiness from real failures.

## 6. Arms

| Arm | Tier 2 | Purpose |
|---|---|---|
| Main | off | Deterministic healing; no LLM cost in the registry |
| Repair | on, capped at 60 calls, `LLM_MODEL` set to a fast model | Only on cases the main arm missed |
| Baseline | registry bypassed (agent talks to a plain pass-through MCP) | Shows what the registry adds |

## 7. Metrics and report

Per case: outcome vs pre-registered expectation, oracle verdict, false patch (Y/N), tier, MTTR, agent turns, agent-visible errors, tokens (agent and repair).

Headline numbers, each with a 95% Wilson interval: correct-handling rate, false-patch count (target 0), safe-refusal rate, miss rate by drift class, crash count (gateway exceptions or hangs; target 0).

`bench/chaos/REPORT.md` lists every case. It has a "Known misses" section (D16, D17 and anything new) and a "Bugs found" section with reproductions. The dashboard Report tab renders it.

## 8. Build order

| Phase | Work | Owner | Est. |
|---|---|---|---|
| 0 | `cases.yaml` with every expectation; commit before any run | main session | small |
| 1 | Controller, logging proxy, recorder; Prism, stripe-mock, httpbin launch scripts (localhost only) | Sonnet subagent | medium |
| 2 | Drift shim for upstream MCP (T1) | Sonnet subagent | medium |
| 3 | Real-version diff extractor for GitHub and Stripe specs; writes D22 cases (expectations reviewed by a human before commit) | Sonnet subagent | medium |
| 4 | Agent driver: runs the section 5 sequence via `claude -p` with one MCP connection | Sonnet subagent | small |
| 5 | Runs: Petstore, httpbin, Stripe offline first; then GitHub; then live arms | driver | long (runtime) |
| 6 | Report and review: spot-check 10% of cases by hand | main session | small |

## 9. What the user must provide or approve

1. A sandbox GitHub repo and a fine-grained PAT (read on that repo, issues write), stored as `MCP_GITHUB_TOKEN` in `.env`.
2. Docker, or permission to download the `stripe-mock` and `go-httpbin` binaries, and the GitHub MCP server binary or image.
3. Optional: a Stripe **test-mode** key as `API_STRIPE_TEST_KEY` for the live read-only arm.
4. Agent model and budget: Haiku for the agent; a cap on `claude -p` runs (estimate: 6 targets × ~30 ids × 5 repeats is too many; start with 2 repeats on the offline targets).
5. Approval to add the needed `apis` and `servers` entries to a separate `bench/chaos/mcp_servers.chaos.json` (the main `config/mcp_servers.json` is not touched).

## 10. Known limits of this plan

- Kind B tests the registry's input validation, not how a model copes with bad docs.
- The GitHub MCP drift is synthetic (shimmed), because GitHub's MCP schema cannot be changed. Only the GitHub REST and Stripe drifts are real version history.
- `stripe-mock` validates requests but does not model every version-specific behaviour.
- D16 and D17 are expected misses; no current tier can see them.
