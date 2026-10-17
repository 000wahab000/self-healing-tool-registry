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
