# Petstore v3 + Prism drift chaos

Date: 2026-10-17. Target T5 of `docs/plans/chaos-test-plan.md`. The healer's `apis` entry (kind openapi) points at a fixture
proxy (`bench/chaos/fixture.py`, port 4020) that serves the spec and forwards to Prism 5.16 (`npx -y @stoplight/prism-cli@5 mock -d`,
port 4010). Per case: the spec endpoint serves the BASE spec, a fresh healer freezes it, then the spec endpoint and Prism switch to the
DRIFTED spec and one call is made with the original (frozen-schema) arguments. Oracle: Prism's own request validation (2xx / 404 / 405 /
422 / 401) and the exact request Prism received (`proof/prism_requests.jsonl`, `proof/results.jsonl` field `prism_requests`).

**Pre-registration.** `cases.yaml` sha256 prefix `4b7c267f754d94d9` (22 cases), written before any run and not edited.
`cases.addendum.yaml` `0d6ff67284e9f3a8` (D1b) was written after a 2-case smoke run (D1, D4; `proof/smoke_run/`).
`cases.addendum2.yaml` `10562414b6536c8d` (A1, D12b, D20b) was written after the first full run was analysed (reasons inside the file).
Expectations for the addenda were written before those cases ran.

**Spec source and adaptations.** `https://petstore3.swagger.io/api/v3/openapi.json` downloaded once (`openapi.orig.json`, 17 KB). The base spec
is that file with every `security` requirement and `securitySchemes` removed (gateway discovery silently drops operations whose
oauth2/apiKey scheme is not satisfied, which would hide `addPet`, `getPetById` and others; D12b re-adds an apiKey scheme with configured auth).
Prism ignores the relative `servers: /api/v3` prefix, so base_url has no prefix. 12 operations are selected.

**Harness corrections made after the first full run** (first run kept in `proof/results.run1_superseded.jsonl`, final run is `proof/results.jsonl`):
(1) D8's drifted spec was identical to its base (my bug), fixed; (2) D14 and other "read accepted by Prism but the agent got an error"
cases were mis-scored as false patches, now scored as refused; (3) D13's oracle did not accept a valid PATCH, added. No product
code or expectation file was touched. Expectations that turned out wrong (not edited): D13 (I predicted refuse; the healer applied a `route` op
with method PATCH, Prism accepted with every value intact, and the plan allowed heal, so it is reported as a valid unexpected heal) and
D12 (ill-posed: header parameters are not agent-visible arguments, so the call died at the front door with `AGENT_ARG_ERROR`; replaced by D12b).

No LLM was used anywhere: no `claude -p`, no NVIDIA/OpenRouter key (stripped from every child env), the healer always ran
with `--no-repair`. Calls go through the healer's MCP front door (python `mcp` client, Streamable HTTP). The healer's heal deadline
is 30 s (`src/healer/settings.py`). Every process started was stopped; logs were scanned for key patterns (none found; the only
credential-like strings are the fake test values `k-test-123` and `sk_test_chaos_fake_not_a_real_key`).

## Every case

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
