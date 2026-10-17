| Case | Expected | Observed | Verdict | Category | Note |
|---|---|---|---|---|---|
| F1_500_once | retry_success | retried_success | PASS | healed / recovered | latency 553 ms; server attempts 2, gap 0.15 s |
| F2a_503_retry_after_seconds | retry_success | retried_success | PASS | healed / recovered | latency 2034 ms; server attempts 2, gap 2.01 s |
| F2b_503_retry_after_httpdate | retry_success | retried_too_soon | FAIL | missed / other | gap 0.12s < required 2.5s; latency 130 ms; server attempts 2, gap 0.12 s |
| F3a_429_once | retry_success | retried_success | PASS | healed / recovered | latency 1027 ms; server attempts 2, gap 1.0 s |
| F3b_429_always | structured_error | structured_error | PASS | refused / structured error | latency 833 ms; server attempts 4, gap 0.14 s |
| F4a_slow_always | structured_error | structured_error | PASS | refused / structured error | latency 8846 ms; server attempts 4, gap 2.15 s |
| F4b_slow_once | retry_success | retried_success | PASS | healed / recovered | latency 2159 ms; server attempts 2, gap 2.14 s |
| F5_drop_mid_response | structured_error | structured_error | PASS | refused / structured error | latency 836 ms; server attempts 4, gap 0.15 s |
| F6_malformed_json | structured_error | structured_error | PASS | refused / structured error |  audit=[('ABORTED', 'UNSUPPORTED_CLASS')]; audit: T1/ABORTED/UNSUPPORTED_CLASS; latency 42 ms; server attempts 1, gap None s |
| F7_truncated_body | structured_error | structured_error | PASS | refused / structured error | latency 883 ms; server attempts 4, gap 0.15 s |
| F8_big_body_10mb | bounded | bounded_success | PASS | pass-through | latency 441 ms, result={"id": 1, "name": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...; latency 441 ms; server attempts 1, gap None s |
| F9_503_after_saved_write | no_replay | saved_writes=1 | PASS | refused / structured error (write not replayed) | attempts=1 result={'error': 'API_ERROR', 'class': 'E1', 'status': '503', 'detail': None}; latency 15 ms; server attempts 1, gap None s |
| F9b_503_then_ok_write | no_replay | saved_writes=1 | PASS | refused / structured error (write not replayed) | attempts=1 result={'error': 'API_ERROR', 'class': 'E1', 'status': '503', 'detail': None}; latency 23 ms; server attempts 1, gap None s |
| F11a_loopback_not_allowlisted | blocked | startup_abort | FAIL | startup abort (whole gateway down) | healer exited code=1; log tail: healer MCP server failed to start or stopped unexpectedly; latency 4912 ms |
| F11b_metadata_ip | blocked | startup_abort | FAIL | startup abort (whole gateway down) | healer exited code=1; log tail: healer MCP server failed to start or stopped unexpectedly; latency 4285 ms |
