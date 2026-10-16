# G2: W1 (200 but not saved) is never caught

## Problem

Failing test: `tests/integration/test_failure_layers.py::test_w1_registry_audits_unsaved_success_at_readback`.

The mock's W1 (`mock_api/app.py` around lines 370-372) returns `200 {"id": "123", "email": <new>}` but does not save. There is **no drift**, so no error occurs, no heal starts, and L5 read-back (which by rule runs **only for healed writes**) never runs. The test expects an audit row with L5 `fail`.

The test and the design disagree. Resolve it in the design's favour (read-back only on healed writes keeps the healthy-path overhead at 0, AC-28). **W1 must be a drift that gets healed, followed by a write that does not persist.**

## Owns

- `mock_api/app.py`: the W1 branch only
- `tests/integration/test_failure_layers.py`: the W1 test only, and only if step 2 makes its arrange step out of date
- `src/healer/verify.py` / `heal.py`: only if L5 still does not fire after step 2

## Steps

1. Change W1 so the update route also drifts, for example renaming `email` to `email_address` the same way M7 does (reuse M7's code path; do not copy it). The healer must therefore heal, replay, get a 200, and then read back.
2. Keep W1's `expected_canonical` (around line 56) consistent with the drifted request.
3. Run the test. If the heal now happens but L5 passes, debug L5 (`readback` config for `update_email` in `config/tools.json`: `route: /users/lookup`, `compare: ["email"]`) and fix the narrowest thing.
4. The test's assertions stay as they are: an error is returned, the email is unchanged, exactly one audit row, outcome not RECOVERED, and an L5 `fail` row.

## Done when

The W1 test passes, M7 tests still pass, and a normal (non-drift) `update_email` call issues **no** read-back request (add that assertion to a new small test `tests/integration/test_g2_no_readback_on_healthy.py`).
