# Spec, upstream-MCP and restart chaos

Date: 2026-10-17. Plan sections 4.3 and 4.5. REST cases use `strict_api.py` (v1 needs `?q=`, v2 needs `?query=`, anything else 422; port 4050) behind
an `apis` entry, reading `searchWidgets`. MCP cases use `mock_api/mcp_drift_server.py` over Streamable HTTP (port 8120) and `bizmcp.py`
(isError / -32603 results; port 8121). Oracles: strict_api's own request log (`proof/strict_api_requests.jsonl`) and the upstream MCP's own results.

`cases.yaml` sha256 prefix `eb69799f84c56c30`, written before the run, not edited.

**Harness corrections** (rows kept in `proof/results.jsonl`, last row per case is scored): M3a and M4 first failed only because my check demanded
*zero* audit rows although the registered expectation was "no RECOVERED heal"; the gateway writes a `NOT_DRIFT` audit row for them, which is
correct, so they were re-run with the check matching the registered text. M1 first showed a harness exception that was really the gateway
dying; it was re-run with a dedicated function that records the gateway exit.

No LLM was used anywhere: no `claude -p`, no NVIDIA/OpenRouter key (stripped from every child env), the healer always ran
with `--no-repair`. Calls go through the healer's MCP front door (python `mcp` client, Streamable HTTP). The healer's heal deadline
is 30 s (`src/healer/settings.py`). Every process started was stopped; logs were scanned for key patterns (none found; the only
credential-like strings are the fake test values `k-test-123` and `sk_test_chaos_fake_not_a_real_key`).

## Every case

| Case | Expected | Observed | Verdict | Category | Note |
|---|---|---|---|---|---|
| S1a_spec_500_during_heal | refuse_or_clue | refused | PASS | refused / structured error | audit: T1/ABORTED/NO_CANDIDATE; latency 382 ms |
| S1b_spec_hangs_during_heal | refuse_or_clue | refused | PASS | refused / structured error | audit: T1/ABORTED/NO_CANDIDATE; latency 890 ms |
| S2a_spec_not_json | refuse | refused | PASS | refused / structured error | audit: T1/ABORTED/NO_CANDIDATE; latency 385 ms |
| S2b_spec_not_openapi | refuse | refused | PASS | refused / structured error | audit: T1/ABORTED/NO_CANDIDATE; latency 390 ms |
| S2c_spec_paths_wrong_type | refuse | refused | PASS | refused / structured error | audit: T1/VERIFY_FAILED/VERIFY_FAILED; latency 369 ms |
| S2d_spec_html_200 | refuse | refused | PASS | refused / structured error | audit: T1/ABORTED/NO_CANDIDATE; latency 466 ms |
| S2e_invalid_spec_at_startup | structured_error | startup_abort | PASS(clear failure) | startup abort (whole gateway down) | exit=1 log tail: healer MCP server failed to start or stopped unexpectedly |
| S3a_cyclic_ref_at_startup | structured_error | started_call_ok | PASS | pass-through |  |
| S3b_cyclic_ref_drifted | refuse_or_clue | heal_correct | PASS | healed / recovered | audit: T1/RECOVERED; latency 413 ms |
| M1_mcp_killed_restarted | recover | gateway_crashed | CRASH | crashed | gateway process exited (code 1) after the upstream HTTP MCP died; first call after kill returned a structured E1 error |
| M2_tools_list_changes | heal | heal_correct | PASS | healed / recovered | audit: T1/RECOVERED; latency 88 ms |
| M2b_tool_renamed | refuse_or_clue | refused | PASS | refused / structured error | audit: T1/ABORTED/NO_CANDIDATE; latency 53 ms |
| M3a_jsonrpc_32602_not_drift | pass_through | pass_through | PASS | pass-through | audit rows=['NOT_DRIFT']; audit: T1/NOT_DRIFT/NOT_DRIFT; latency 35 ms |
| M3b_jsonrpc_32603 | structured_error | structured_error | PASS | refused / structured error | latency 24 ms |
| M4_iserror_business | pass_through | pass_through | PASS | pass-through | audit: T1/NOT_DRIFT/NOT_DRIFT; latency 39 ms |
| R1_gateway_restart_tier0 | tier0 | old_args_rejected_after_restart | FAIL | missed / other | old-schema agent call after a gateway restart was not served by the stored fix |
| R3_concurrent_one_heal | single_flight | single_flight | PASS | healed / recovered | audit: T1/RECOVERED |
