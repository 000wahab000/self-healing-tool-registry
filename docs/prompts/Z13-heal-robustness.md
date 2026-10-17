# Z13: Heal-path robustness (error typing and bounded memory)

## Problems (confirm each on `main` first; line numbers drift)

1. **Error typing in `heal.py`** (the `except (...)` around line 183): an unexpected exception inside the heal path can be reported as a verification failure. It must surface as an `INTERNAL_ERROR` refusal and be logged with a traceback, so it is never confused with a schema problem and never counted as a safe refusal.
2. **Unbounded `_first_seen` dict** (`heal.py` around line 161): one entry per fingerprint, removed only on success, so a stream of distinct unhealable failures grows it forever.

## Owns

- `src/healer/heal.py`: those two spots only
- `src/healer/models.py`: add `INTERNAL_ERROR` to `Reason` only if it does not exist (check that the store's `CHECK` constraint picks it up, since `store.py` builds CHECKs from the enums; if a migration is needed, do it in `store.py` the way earlier enum additions were done and list it in the PR)
- `tests/unit/test_ac_96_heal_robustness.py` (new)
- `product.md`: AC-96

## Build

1. Narrow the catch to the expected types (`OpError`, `httpx.HTTPError`, `ValueError`, `TimeoutError`, `jsonschema.ValidationError`, whatever the code really raises; list them in the PR). For anything else: `logger.exception(...)`, write one audit row with reason `INTERNAL_ERROR`, return a refusal with `retry: false`, and leave the registry unchanged. Do not re-raise to the agent.
2. `_first_seen`: cap it (for example 10 000 entries, as a named constant) with oldest-first eviction (`OrderedDict`), **or** TTL eviction using the injected clock. Pick one, explain it, and keep MTTR semantics for live fingerprints.
3. Metrics: make sure `INTERNAL_ERROR` rows are **not** counted as safe refusals in `metrics.safe_refusal` (add an assertion test; if they would be counted, the fix belongs in this PR).

## Tests (`test_ac_96_*`)

- a candidate apply that raises `RuntimeError` gives an `INTERNAL_ERROR` refusal, one audit row, a traceback in the log (`caplog`), and an unchanged registry
- an `OpError` still gives today's reason
- insert cap+1 distinct fingerprints: the dict size stays at the cap, the oldest is evicted, and a live fingerprint's MTTR is still correct

## Done when

Unexpected errors are never disguised as verification refusals, and heal memory is bounded.
