# GraphQL chaos (live Countries baseline + project mock)

Date: 2026-10-17. Plan target T6. Live: `https://countries.trevorblades.com/graphql` through an `apis` entry (kind graphql, read-only queries,
default operation selection). Local: the project's own strawberry mock (`mock_api/graphql_app.py`) behind `gql_local.py` with a runtime mutation switch;
NOT an independent third-party schema. Oracle for live cases: the same question asked directly with a hand-written query.

`cases.yaml` sha256 prefix `c41a2a32b5bcc50a`, written before the run, not edited.

Result in one line: **no GraphQL read works through a gateway `apis` entry**, even with zero drift. Three stacked adapter defects, each reproduced
(`adapter_probe.py` and `query_probe.py` give the evidence in `proof/adapter_probe.txt` and `proof/generated_queries.txt`). See SUMMARY.md bugs B3 to B5.

No LLM was used anywhere: no `claude -p`, no NVIDIA/OpenRouter key (stripped from every child env), the healer always ran
with `--no-repair`. Calls go through the healer's MCP front door (python `mcp` client, Streamable HTTP). The healer's heal deadline
is 30 s (`src/healer/settings.py`). Every process started was stopped; logs were scanned for key patterns (none found; the only
credential-like strings are the fake test values `k-test-123` and `sk_test_chaos_fake_not_a_real_key`).

## Every case

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
