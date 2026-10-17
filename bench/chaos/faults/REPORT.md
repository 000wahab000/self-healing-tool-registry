# Transport fault chaos

Date: 2026-10-17. Plan section 4.2. A tiny raw-asyncio fault server (`fault_server.py`, port 4030, its own OpenAPI spec) sits behind an `apis` entry.
Faults are injected per case via `POST /__mode`; the server counts attempts and saved writes (the independent oracle) and records arrival
times. After every case a `health` call checks the gateway still answers. One healer instance serves cases F1 to F9b; F11a/F11b start separate healers.

`cases.yaml` sha256 prefix `046823628e67ab85`, written before the run, not edited. Not run: F10 (DNS failure; not requested) and a call-time
DNS-to-private-IP case (needs controllable DNS); F11 is covered as startup-time egress refusal only.

No LLM was used anywhere: no `claude -p`, no NVIDIA/OpenRouter key (stripped from every child env), the healer always ran
with `--no-repair`. Calls go through the healer's MCP front door (python `mcp` client, Streamable HTTP). The healer's heal deadline
is 30 s (`src/healer/settings.py`). Every process started was stopped; logs were scanned for key patterns (none found; the only
credential-like strings are the fake test values `k-test-123` and `sk_test_chaos_fake_not_a_real_key`).

## Every case

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
