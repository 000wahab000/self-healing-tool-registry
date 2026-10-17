| Case | Expected | Observed | Verdict | Category | Note |
|---|---|---|---|---|---|
| G1_country_BR | success | error | FAIL | missed / other | audit: T1/ABORTED/NO_CANDIDATE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_CANDIDATE; latency 129 ms |
| G2_continent_EU | success | error | FAIL | missed / other | audit: T1/ABORTED/NO_CANDIDATE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_CANDIDATE; latency 139 ms |
| G3_language_pt | success | error | FAIL | missed / other | audit: T1/ABORTED/NO_CANDIDATE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_CANDIDATE; latency 134 ms |
| G4_countries_filter | success | error | FAIL | missed / other | audit: T1/ABORTED/UNSUPPORTED_CLASS; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/UNSUPPORTED_CLASS; latency 105 ms |
| G5_unknown_code | null_result | error | FAIL | missed / other | audit: T1/ABORTED/NO_CANDIDATE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_CANDIDATE; latency 635 ms |
| G6_wrong_arg_type | arg_error | arg_error | PASS | refused / structured error | latency 118 ms |
| L0_local_baseline | success | error | FAIL | missed / other | audit: T1/ABORTED/NO_CANDIDATE; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/NO_CANDIDATE; latency 524 ms |
| L1_local_arg_rename | heal | error | FAIL | missed / other | audit: T1/ABORTED/UNSAFE_REPLAY; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/UNSAFE_REPLAY; latency 680 ms |
| L2_local_envelope | heal | error | FAIL | missed / other | audit: T1/ABORTED/UNSAFE_REPLAY; agent saw: SCHEMA_DRIFT_UNRECOVERABLE/UNSAFE_REPLAY; latency 871 ms |
