# Chaos suites summary (no LLM, offline except where stated)

No LLM was used anywhere: no `claude -p`, no NVIDIA/OpenRouter key (stripped from every child env), the healer always ran
with `--no-repair`. Calls go through the healer's MCP front door (python `mcp` client, Streamable HTTP). The healer's heal deadline
is 30 s (`src/healer/settings.py`). Every process started was stopped; logs were scanned for key patterns (none found; the only
credential-like strings are the fake test values `k-test-123` and `sk_test_chaos_fake_not_a_real_key`).

Run date 2026-10-17, branch test/chaos-suite, nothing committed. Per-suite detail, oracle logs and raw rows are in `bench/chaos/<suite>/REPORT.md` and `proof/`.

## Suites run / skipped

| Suite | Status | Cases | Pre-registration (cases.yaml sha256 prefix) |
|---|---|---|---|
| petstore | run | 26 | 4b7c267f754d94d9 (+ addenda 0d6ff67284e9f3a8, 10562414b6536c8d) |
| faults | run (F10 and call-time private-DNS not run) | 15 | 046823628e67ab85 |
| spec_mcp_faults | run (S4 spec-changes-during-heal not run) | 17 | eb69799f84c56c30 |
| graphql | run (live baseline + project-mock drift) | 9 | c41a2a32b5bcc50a |
| stripe | run, but the gateway hung on startup so no call was possible | 4 | eabe8d7bea302f2a |

Skipped for cost/need: Docker targets (stripe-mock, go-httpbin/T4 httpbin), GitHub REST version diffs (T2), live Stripe, agent-driven (`claude -p`) runs. Existing GitHub MCP suite (`bench/chaos/github`) was not re-run.

## petstore

| Case | Expected | Observed | Verdict |
|---|---|---|---|
| D1_body_rename | heal | landed_reported_fail | LANDED_REPORTED_FAIL |
| D2_query_rename | heal | crashed | CRASHED |
| D3_path_param_rename | pass_through | pass_through | PASS |
| D4_route_move | heal | heal_correct | PASS |
| D5_str_to_int | heal | heal_correct | PASS |
| D6_str_to_int_nonnum | refuse | refused | PASS |
| D6b_str_to_int_leadzero | refuse | refused | PASS |
| D7_wrap | heal | refused | REFUSED |
| D8_unwrap | heal | refused | REFUSED |
| D9a_enum_case | heal | refused | REFUSED |
| D9b_enum_synonym | refuse | refused | PASS |
| D10_required_default | heal | refused | REFUSED |
| D11_required_nodefault | refuse | refused | PASS |
| D12_header_rename | heal | missed | MISSED |
| D13_method_change | refuse | heal_correct | UNEXPECTED_HEAL_VALID |
| D14_response_rename | heal | refused | REFUSED |
| D15_field_split | refuse | refused | PASS |
| D16_units_change | known_miss | pass_through | PASS(known miss confirmed) |
| D17_swap_same_type | known_miss | pass_through | PASS(known miss confirmed) |
| D19_description_only | pass_through | pass_through | PASS |
| D20_flipflop | heal | pass_through | PASS_THROUGH |
| D21_two_drifts | heal | refused | REFUSED |
| D1b_body_rename_request_only | heal | heal_correct | PASS |
| A1_array_root_baseline | pass_through | crashed | CRASHED |
| D12b_auth_header_rename | heal | refused | REFUSED |
| D20b_flipflop_request_only | heal | refused | REFUSED |

Totals: 26 cases, 12 as expected, 0 false patches, 2 crashed, 0 hung, 1 write-landed-but-error-reported, 9 safe misses/refusals where a heal was expected, 2 other deviations.

## faults

| Case | Expected | Observed | Verdict |
|---|---|---|---|
| F1_500_once | retry_success | retried_success | PASS |
| F2a_503_retry_after_seconds | retry_success | retried_success | PASS |
| F2b_503_retry_after_httpdate | retry_success | retried_too_soon | FAIL |
| F3a_429_once | retry_success | retried_success | PASS |
| F3b_429_always | structured_error | structured_error | PASS |
| F4a_slow_always | structured_error | structured_error | PASS |
| F4b_slow_once | retry_success | retried_success | PASS |
| F5_drop_mid_response | structured_error | structured_error | PASS |
| F6_malformed_json | structured_error | structured_error | PASS |
| F7_truncated_body | structured_error | structured_error | PASS |
| F8_big_body_10mb | bounded | bounded_success | PASS |
| F9_503_after_saved_write | no_replay | saved_writes=1 | PASS |
| F9b_503_then_ok_write | no_replay | saved_writes=1 | PASS |
| F11a_loopback_not_allowlisted | blocked | startup_abort | FAIL |
| F11b_metadata_ip | blocked | startup_abort | FAIL |

Totals: 15 cases, 12 as expected, 0 false patches, 0 crashed, 0 hung, 0 write-landed-but-error-reported, 0 safe misses/refusals where a heal was expected, 3 other deviations.

## spec_mcp_faults

| Case | Expected | Observed | Verdict |
|---|---|---|---|
| S1a_spec_500_during_heal | refuse_or_clue | refused | PASS |
| S1b_spec_hangs_during_heal | refuse_or_clue | refused | PASS |
| S2a_spec_not_json | refuse | refused | PASS |
| S2b_spec_not_openapi | refuse | refused | PASS |
| S2c_spec_paths_wrong_type | refuse | refused | PASS |
| S2d_spec_html_200 | refuse | refused | PASS |
| S2e_invalid_spec_at_startup | structured_error | startup_abort | PASS(clear failure) |
| S3a_cyclic_ref_at_startup | structured_error | started_call_ok | PASS |
| S3b_cyclic_ref_drifted | refuse_or_clue | heal_correct | PASS |
| M1_mcp_killed_restarted | recover | gateway_crashed | CRASH |
| M2_tools_list_changes | heal | heal_correct | PASS |
| M2b_tool_renamed | refuse_or_clue | refused | PASS |
| M3a_jsonrpc_32602_not_drift | pass_through | pass_through | PASS |
| M3b_jsonrpc_32603 | structured_error | structured_error | PASS |
| M4_iserror_business | pass_through | pass_through | PASS |
| R1_gateway_restart_tier0 | tier0 | old_args_rejected_after_restart | FAIL |
| R3_concurrent_one_heal | single_flight | single_flight | PASS |

Totals: 17 cases, 15 as expected, 0 false patches, 1 crashed, 0 hung, 0 write-landed-but-error-reported, 0 safe misses/refusals where a heal was expected, 1 other deviations.

## graphql

| Case | Expected | Observed | Verdict |
|---|---|---|---|
| G1_country_BR | success | error | FAIL |
| G2_continent_EU | success | error | FAIL |
| G3_language_pt | success | error | FAIL |
| G4_countries_filter | success | error | FAIL |
| G5_unknown_code | null_result | error | FAIL |
| G6_wrong_arg_type | arg_error | arg_error | PASS |
| L0_local_baseline | success | error | FAIL |
| L1_local_arg_rename | heal | error | FAIL |
| L2_local_envelope | heal | error | FAIL |

Totals: 9 cases, 1 as expected, 0 false patches, 0 crashed, 0 hung, 0 write-landed-but-error-reported, 0 safe misses/refusals where a heal was expected, 8 other deviations.

## stripe

| Case | Expected | Observed | Verdict |
|---|---|---|---|
| ST1_post_customers_exposed | not_exposed | startup_hang | HUNG |
| ST2_get_customer_exposed | exposed | startup_hang | HUNG |
| ST3_list_customers_exposed | not_exposed | startup_hang | HUNG |
| ST4_retrieve_across_real_version_diff | pass_through | startup_hang | HUNG |

Totals: 4 cases, 0 as expected, 0 false patches, 0 crashed, 4 hung, 0 write-landed-but-error-reported, 0 safe misses/refusals where a heal was expected, 0 other deviations.

## Grand totals

- Cases: 71; as expected: 40
- **False patches: 0** (an accepted request with a changed or dropped value). The one apparent case, D13, is a valid heal (see petstore report).
- Crashes: 3 (B1 gateway process death; B2 front-door error twice, gateway stayed up). Hangs: 4 (stripe, B6).
- Write landed but agent told it failed: 1 (B8).
- Safe misses (refused where a heal was expected): 9.
- Other deviations from the pre-registered expectation: 14 (graphql 8; faults 3: F2b, F11a, F11b; spec_mcp 1: R1; petstore 2: D13 valid unexpected heal, D20 whose first call did not heal).

## Bugs found

Severity order. File:line are in the working tree at branch test/chaos-suite. All reproduce offline with the commands given.

| # | Sev | Bug | Cause (file:line) | Reproduction |
|---|---|---|---|---|
| B1 | High | Killing an upstream HTTP MCP server takes the whole gateway down: the first call after the kill returns a structured E1 error (2 s), then the healer process exits with code 1 about 3 s later (all tools, all APIs gone). | `src/healer/gateway.py:359-396` (`_open` enters `streamable_http_client` and `ClientSession` on the serve-wide `AsyncExitStack`, line 392-393); the SDK's POST task (`mcp/client/streamable_http.py:355`) raises `ConnectError` into that task group and cancels the uvicorn lifespan (`mcp_server.py:322-327` then prints the generic failure text). | `python bench/chaos/spec_mcp_faults/run.py M1_mcp_killed_restarted` (steps in `proof/results.jsonl`); healer log `proof/logs/healer_M1.log` |
| B2 | High | Any REST endpoint whose JSON response is an array at the root breaks the MCP front door: the registry call succeeds (audit RECOVERED / upstream 200) but the client gets `MCPError: Handler returned an invalid result`. Even with no drift (A1). | `src/healer/mcp_server.py:89-91` passes `structuredContent=result` where `result` is a list; MCP requires an object. | `python bench/chaos/petstore/run.py A1_array_root_baseline D2_query_rename` (Prism's `GET /pet/findByStatus` returns an array) |
| B3 | High | `kind: graphql` entries through the gateway are unusable: every call with an argument fails with E2 `SCHEMA_VALIDATION` "unknown" for each argument, then `NO_CANDIDATE`. Includes the project's own mock with no drift (L0). | `src/healer/adapters/graphql.py:76-79`: `doc["operation"]` is the raw name (`registry.py:218`) but the gateway's spec ops are keyed `<api>__<op>` (`gateway.py:459-468`), so `latest.ops.get(op)` is None and the empty spec flags all args unknown. | `python bench/chaos/graphql/run.py L0_local_baseline`; `python bench/chaos/graphql/adapter_probe.py` |
| B4 | Medium | A GraphQL schema with a null `mutationType` (any read-only API, e.g. Countries) raises `AttributeError` in the adapter (caught only for HTTP/Key/Type/ValueError) and becomes `MCP_TOOL_ERROR`. | `src/healer/adapters/graphql.py:89` (`.get("mutationType", {}).get("name")` on `None`) | `python bench/chaos/graphql/adapter_probe.py` (first line of output) |
| B5 | Medium | Generated GraphQL queries are invalid for real schemas: list-of-non-null-object fields and cyclic object fields get no selection set (`countries`, `languages`, `continent{countries}`...), so the live server answers `GRAPHQL_VALIDATION_FAILED` for every Countries operation. | `src/healer/graphql_loader.py:11` (introspection `ofType` depth 3 cannot see `[T!]!` objects), `:35-40` (cyclic OBJECT returns `{}`), `src/healer/adapters/graphql.py:12-15` (emits bare field names) | `python bench/chaos/graphql/query_probe.py` (output in `proof/generated_queries.txt`) |
| B6 | High | A Stripe-sized spec hangs gateway startup: `resolve_refs` expands the whole ref graph without memoisation; 835 KB slice not finished after 170 s CPU, port never opens, process alive (not crashed, not serving). Would also block the event loop on a heal-time spec re-fetch. | `src/healer/openapi_loader.py:19-41` (`walk` re-inlines every shared `$ref`; only the current path is cut) | `python bench/chaos/stripe/loader_probe.py bench/chaos/stripe/slice.v1000.json 170`; `python bench/chaos/stripe/run.py` |
| B7 | High | A stored fix is not dropped when the API reverts: after drift D1b (heal stored) and a revert, the pre-emptively applied stale fix sends `petName` and Prism answers 422; the original request (valid again) is never tried. 4 consecutive calls failed (VERIFY_FAILED x2, then KNOWN_UNFIXABLE negative cache) and none recovered inside the test. | `src/healer/registry.py:341-344` applies `tool.active_fix` before any plain attempt; retire needs `RETIRE_AT_LOSSES` (`settings.py:11`) and the neg-cache holds the fingerprint 60 s (`settings.py:10`). | `python bench/chaos/petstore/run.py D20b_flipflop_request_only` |
| B8 | Medium | Write lands but the agent is told it failed: renaming a field in both the request and the response (the normal case for a shared schema, D1) heals the request, Prism accepts the POST (200, value intact), then verification fails and the agent gets `SCHEMA_DRIFT_UNRECOVERABLE` / `VERIFY_FAILED`. An agent that retries creates a duplicate. (Cause inferred: D1b, which renames only the request side, heals fine.) | `src/healer/heal.py` `_apply` verify step (from line 258) and `heal.py:475-478` (a failed verify on a write is treated as "may have reached the API" yet reported as a plain failure) | `python bench/chaos/petstore/run.py D1_body_rename` |
| B9 | Low | `Retry-After` as an HTTP-date is ignored (retry after 0.12 s instead of ~3 s). Seconds form is honoured (2.01 s). Documented as a deliberate shortcut. | `src/healer/detect.py:64-70` | `python bench/chaos/faults/run.py F2b_503_retry_after_httpdate` |
| B10 | Medium | One refused egress origin (not allow-listed loopback / 169.254.169.254) aborts the whole gateway at startup with the opaque text "healer MCP server failed to start or stopped unexpectedly"; the other, allowed API in the same config is not served and no reason is printed. | `src/healer/mcp_server.py:322-327` (generic message) with `gateway.py:747-756` (`api_registry` raised for any entry) | `python bench/chaos/faults/run.py F11a_loopback_not_allowlisted F11b_metadata_ip` |
| B11 | Low | No response-size cap: a 10 MB JSON body is returned to the agent in full (0.44 s). | no limit in `adapters/rest.py` / `mcp_server.py:84-92` | `python bench/chaos/faults/run.py F8_big_body_10mb` |
| B12 | Medium | After a gateway restart a stored fix is never served for an agent that still holds the old schema: the frozen schema is rebuilt from the live (drifted) spec, so old-argument calls are rejected at the front door as `AGENT_ARG_ERROR` before the store is consulted (no tier-0 row). | `src/healer/registry.py:333` (agent args checked against the schema frozen at startup, not persisted) | `python bench/chaos/spec_mcp_faults/run.py R1_gateway_restart_tier0` |
| B13 | Info | Header/auth drift is not healed: apiKey header rename (D12b) gives 401 then `NO_CANDIDATE`. Discovery also silently drops operations whose security scheme (oauth2, unconfigured apiKey) is unsatisfied, with diagnostics only; Stripe form-encoded writes (`application/x-www-form-urlencoded`) are `UNSUPPORTED_MEDIA_TYPE` by design, so no Stripe write can be exposed. | `src/healer/connection_discovery.py:85-100,166-190`; ops catalogue `src/healer/ops.py` (header op takes config refs only) | `python bench/chaos/petstore/run.py D12b_auth_header_rename` |

Not bugs, noted: -32602 "User not found" and `isError:true` business results are correctly classed BUSINESS and pass through (they do write a `NOT_DRIFT` audit row); the structured text of an `isError` result is kept only as structured content.

