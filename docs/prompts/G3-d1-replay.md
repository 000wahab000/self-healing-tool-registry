# G3: D1 (side effect, then 503) gets retried

## Problem

Failing test: `tests/integration/test_failure_layers.py::test_d1_registry_does_not_replay_saved_ticket_after_503`.

The mock's D1 saves the ticket and then answers 503. `registry.call("create_ticket", ...)` returns `{"ticket_id": "T-1", ...}` as a success. A 503 is a transient E-class, so `src/healer/retry.py` retries it. `create_ticket` is `"idempotent": false` with `"idempotency_key": true` in `config/tools.json`.

The test expects: an error returned, exactly one ticket, exactly one `POST /tickets`, and no audit row (it is not drift, so no heal).

## Owns

- `src/healer/retry.py`
- `tests/unit/test_g3_retry_writes.py` (new)
- `tests/integration/test_failure_layers.py`: the D1 test only, and only per the decision in step 2

## Steps

1. Find out what actually happened. Did the retry send an `Idempotency-Key` header? Did the mock dedupe on it (`api.state()["tickets"]` count)? How many `POST /tickets` requests are in `api.requests`? Write the answers in the PR.
2. Decide the rule (write it in `retry.py`'s docstring):
   - **non-idempotent tool, no idempotency key sent**: never retry a 5xx or a timeout; return the error. This case must be fixed.
   - **non-idempotent tool with a key the upstream honours**: a retry is safe in principle. The repo's test still says "do not retry", so **follow the test**: the conservative rule (no automatic retry of non-idempotent writes after a 5xx) is simpler and matches the "never duplicate a write" invariant. Note in the PR that keyed retries could be enabled later.
   - Idempotent tools keep today's retry behaviour.
3. Implement it by passing the tool's `idempotent` flag into the retry decision. Do not read `config/tools.json` again inside `retry.py`; take the flag from the caller.

## Done when

- the D1 test passes
- new unit tests: non-idempotent + 503 gives no retry; idempotent + 503 gives a retry; 429 with `Retry-After` on an idempotent tool still retries
- existing retry tests pass, with jitter injected
