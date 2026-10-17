| Case | Expected | Observed | Verdict | Category | Note |
|---|---|---|---|---|---|
| D1_body_rename | heal | landed_reported_fail | LANDED_REPORTED_FAIL | missed (write landed, error reported) | Prism accepted the intended request but the agent got an error (VERIFY_FAILED/VERIFY_FAILED); audit: T1/VERIFY_FAILED/VERIFY_FAILED; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/VERIFY_FAILED; latency [615] ms |
| D2_query_rename | heal | crashed | CRASHED | crashed | MCPError: Handler returned an invalid result; audit: T1/RECOVERED; latency [701] ms |
| D3_path_param_rename | pass_through | pass_through | PASS | pass-through | latency [561] ms |
| D4_route_move | heal | heal_correct | PASS | healed / recovered | audit: T1/RECOVERED; latency [554] ms |
| D5_str_to_int | heal | heal_correct | PASS | healed / recovered | audit: T1/RECOVERED; latency [620] ms |
| D6_str_to_int_nonnum | refuse | refused | PASS | refused / structured error | ABORTED/UNSAFE_PATCH; audit: T1/ABORTED/UNSAFE_PATCH; latency [707] ms |
| D6b_str_to_int_leadzero | refuse | refused | PASS | refused / structured error | ABORTED/UNSAFE_PATCH; audit: T1/ABORTED/UNSAFE_PATCH; latency [520] ms |
| D7_wrap | heal | refused | REFUSED | refused / structured error | ABORTED/UNSAFE_PATCH; audit: T1/ABORTED/UNSAFE_PATCH; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/UNSAFE_PATCH; latency [560] ms |
| D8_unwrap | heal | refused | REFUSED | refused / structured error | ABORTED/UNSAFE_PATCH; audit: T1/ABORTED/UNSAFE_PATCH; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/UNSAFE_PATCH; latency [507] ms |
| D9a_enum_case | heal | refused | REFUSED | refused / structured error | ABORTED/UNSAFE_PATCH; audit: T1/ABORTED/UNSAFE_PATCH; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/UNSAFE_PATCH; latency [632] ms |
| D9b_enum_synonym | refuse | refused | PASS | refused / structured error | ABORTED/NO_CANDIDATE; audit: T1/ABORTED/NO_CANDIDATE; latency [582] ms |
| D10_required_default | heal | refused | REFUSED | refused / structured error | ABORTED/NO_SAFE_VALUE; audit: T1/ABORTED/NO_SAFE_VALUE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_SAFE_VALUE; latency [583] ms |
| D11_required_nodefault | refuse | refused | PASS | refused / structured error | ABORTED/NO_SAFE_VALUE; audit: T1/ABORTED/NO_SAFE_VALUE; latency [1854] ms |
| D12_header_rename | heal | missed | MISSED | missed / other | no accepted request; no audit row; result={'error': 'AGENT_ARG_ERROR', 'tool': 'pet__deletePet', 'retry': False}; agent saw: AGENT_ARG_ERROR/; latency [345] ms |
| D13_method_change | refuse | heal_correct | UNEXPECTED_HEAL_VALID | healed / recovered | audit: T1/RECOVERED; latency [2184] ms |
| D14_response_rename | heal | refused | REFUSED | refused / structured error | read accepted by Prism but agent got an error (ABORTED/NO_CANDIDATE); audit: T1/ABORTED/NO_CANDIDATE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_CANDIDATE; latency [2115] ms |
| D15_field_split | refuse | refused | PASS | refused / structured error | ABORTED/NO_SAFE_VALUE; audit: T1/ABORTED/NO_SAFE_VALUE; latency [1158] ms |
| D16_units_change | known_miss | pass_through | PASS(known miss confirmed) | pass-through | latency [707] ms |
| D17_swap_same_type | known_miss | pass_through | PASS(known miss confirmed) | pass-through | latency [618] ms |
| D19_description_only | pass_through | pass_through | PASS | pass-through | latency [782] ms |
| D20_flipflop | heal | pass_through | PASS_THROUGH | pass-through | audit: T1/VERIFY_FAILED/VERIFY_FAILED; call 1: landed_reported_fail; latency [805, 94] ms |
| D21_two_drifts | heal | refused | REFUSED | refused / structured error | ABORTED/NO_SAFE_VALUE; audit: T1/ABORTED/NO_SAFE_VALUE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_SAFE_VALUE; latency [547] ms |
| D1b_body_rename_request_only | heal | heal_correct | PASS | healed / recovered | audit: T1/RECOVERED; latency [554] ms |
| A1_array_root_baseline | pass_through | crashed | CRASHED | crashed | MCPError: Handler returned an invalid result; latency [564] ms |
| D12b_auth_header_rename | heal | refused | REFUSED | refused / structured error | ABORTED/NO_CANDIDATE; audit: T1/ABORTED/NO_CANDIDATE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_CANDIDATE; latency [632] ms |
| D20b_flipflop_request_only | heal | refused | REFUSED | refused / structured error | VERIFY_FAILED/VERIFY_FAILED; audit: T1/RECOVERED, T0/VERIFY_FAILED/VERIFY_FAILED, T0/ABORTED/KNOWN_UNFIXABLE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/KNOWN_UNFIXABLE; call 1: heal_correct; calls after revert: refused, refused, refused, refused; latency [1665, 979, 320, 368, 327] ms |
