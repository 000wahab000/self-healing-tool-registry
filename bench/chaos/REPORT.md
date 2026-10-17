# Chaos test report (consolidated)

Date: 2026-10-17. Heal deadline: 30 s (raised from 3.5 s on this branch).
Per-suite detail and proof: `github/REPORT.md`, `SUMMARY.md`, and each suite's `REPORT.md` and `proof/`.

## Method

- The registry is driven through its MCP front door, never patched for the test.
- Expected outcomes are pre-registered in each suite's `cases.yaml` (sha256 prefix recorded) before any run. Corrections are separate, labelled addenda, never edits.
- The oracle is the upstream itself: Prism request validation, the fault server's log, the GitHub MCP, or the GraphQL server. It is never our own verifier.
- No LLM in the registry for these suites (`--no-repair`). The GitHub suite also has an agent phase (Haiku, one MCP connection).

## Totals

| Suite | Upstream | Cases | As expected | False patches | Crashes / hangs |
|---|---|---|---|---|---|
| github (offline + live) | GitHub MCP (real) behind a false-schema shim | 66 + 66 control, 20 + 20 agent | see `github/REPORT.md` | 0 after fix (1 before, fixed in #72) | 0 |
| petstore | Prism, public Petstore v3 | 26 | 12 | 0 | 2 crashes |
| faults | local fault server | 15 | 12 | 0 | 0 |
| spec_mcp_faults | strict local API + MCP servers | 17 | 15 | 0 | 1 crash |
| graphql | live Countries API + local mock | 9 | 1 | 0 | 0 |
| stripe | Prism, two real Stripe spec versions | 4 | 0 | 0 | 4 hangs |
| **Total (new suites)** | | **71** | **40** | **0** | **3 crashes, 4 hangs** |

Safety held everywhere: **0 false patches** across all suites after the #72 fix. The failures are about availability and coverage (crashes, hangs, refusals where a heal was possible), not wrong writes.

## Bugs found

| Id | Sev | Bug | Cause | Repro |
|---|---|---|---|---|
| B1 | high | Killing an upstream HTTP MCP server crashes the whole gateway (~3 s after the next call) | `src/healer/gateway.py:359-396` `_open` | `spec_mcp_faults/run.py M1_mcp_killed_restarted` |
| B2 | high | A REST endpoint returning a JSON array fails at the front door ("invalid result"), even with no drift | `src/healer/mcp_server.py:89-91` passes a list as `structuredContent` | `petstore/run.py A1_array_root_baseline` |
| B3 | high | No GraphQL call with arguments works through an `apis` entry, even with no drift | `src/healer/adapters/graphql.py:76-79` looks up the raw op name; the gateway keys `<api>__<op>` | `graphql/run.py L0_local_baseline` |
| B6 | high | A Stripe-sized spec hangs gateway startup (> 170 s) | `src/healer/openapi_loader.py:19-41` `resolve_refs` inlines shared refs with no memo | `stripe/loader_probe.py` |
| B7 | high | A stored fix is not dropped when the API reverts; calls keep failing | `src/healer/registry.py:341-344` applies the stale fix first and never retries the original | `petstore/run.py D20b_flipflop_request_only` |
| B4 | med | Null `mutationType` (any read-only GraphQL API) raises AttributeError | `src/healer/adapters/graphql.py:89` | `graphql/adapter_probe.py` |
| B5 | med | Generated GraphQL queries lack selection sets for list-of-object and cyclic fields; the live API rejects them | `src/healer/graphql_loader.py:11,35-40` | `graphql/query_probe.py` |
| B8 | med | A rename in request and response: the write lands but the agent gets VERIFY_FAILED, so a retry duplicates it | inferred: `src/healer/heal.py:475-478` | `petstore/run.py D1` |
| B10 | med | One egress-refused API aborts the whole gateway at startup with an opaque error | `src/healer/mcp_server.py:322-327`, `gateway.py:747` | `faults/run.py F11a_loopback_not_allowlisted` |
| B12 | med | After a gateway restart, an agent with the old schema gets `AGENT_ARG_ERROR`, so the stored fix is never served | `src/healer/registry.py:333` | `spec_mcp_faults/run.py R1_gateway_restart_tier0` |
| G2 | med | Two same-typed fields renamed at once are refused | `src/healer/candidates.py:85-111` | `github/run.py` profile `rename_owner_repo` |
| B9 | low | `Retry-After` as an HTTP-date is ignored (seconds form works) | `src/healer/detect.py:64-70` | `faults/run.py F2b_503_retry_after_httpdate` |
| B11 | low | No response size cap: a 10 MB body goes to the agent in full | none | `faults/run.py F8_big_body_10mb` |
| B13 | info | Auth-header rename gives 401 then NO_CANDIDATE; discovery silently drops operations with unsatisfied security; Stripe form-encoded writes are rejected by design | discovery | `petstore/run.py D12b` |

## What worked

- **Healed:** request-only body rename, route move, lossless string to int, method change via route op, cyclic-`$ref` drifted spec, MCP argument rename, nested-object unwrap (GitHub), single-field rename, cast and enum case (GitHub). Concurrent calls gave one heal and one audit row (single-flight).
- **Refused correctly:** non-numeric and leading-zero casts, field split, new required field with no default, synonym enum rename, invalid or unreachable spec, merged fields (GitHub), decoy fields.
- **Passed through correctly:** description-only change, business errors (`isError`, -32602), and the known undetectable cases (units change, field swap).
- **Writes never replayed after a 5xx** (F9, F9b).

## Not covered

- Docker targets (stripe-mock, httpbin), GitHub REST version diffs, live Stripe (no keys by design), agent-driven runs for the new suites.
- S4 (spec changes during a heal), F10 (DNS failure).
- One run per case: these are counts, not rates.

## Suggested fix order

B1, B6 and B2 (crash, hang, and broken baseline calls), then B7 (stale fix after revert), then B3 to B5 (GraphQL unusable through the gateway), then B8, B10, B12.
