# Z4: L5 read-back for every write tool

**Depends on Z0.**

## Problem

L5 read-back works for `update_email` only, so W1 (a 200 response that saved nothing) is caught there. `set_manager` and `create_ticket` are also writes (`"write": true` in `config/tools.json`) but have no `readback` config, so a healed write that silently did not persist is committed.

## Owns

- `config/tools.json`: `readback` entries only
- `src/healer/layers/l5_readback.py`: only if a new shape is needed (for example "read back a created resource by the id returned in the response")
- `mock_api/app.py`: only the W1 variants needed for the new tools, plus a read endpoint if a tool has none. Follow the existing W1 pattern; add no new mutation framework.
- `tests/integration/test_ac_87_readback_writes.py` (new)
- `product.md`: AC-87

## Build

1. Read how `update_email`'s `readback` is consumed (`method`, `route`, `key_from`, `compare`) and its bounded retry (max 2 tries, 100 ms apart, injectable `sleep`).
2. `set_manager`: read back the user via the same lookup route; compare `manager_id`.
3. `create_ticket`: the key comes from the **response** (`ticket_id`), not the request. If `key_from` only supports request paths, add `key_from_response` in L5 (support exactly one of the two; it is an error if both are set). Read the ticket back and compare `title` and `user_id`. If the mock has no ticket read endpoint, add a minimal `GET /tickets/{id}`.
4. Read-back runs **only for healed writes**. A failed read-back aborts and never commits.

## Tests (`test_ac_87_*`)

For each of `set_manager` and `create_ticket`:
- a healed write that persisted: L5 passes and the fix commits
- the W1 variant (200, not persisted): L5 fails, no commit, one audit row, `retry: false`
- a non-healed (normal) call: L5 is `skip / not_healed_write`, and the mock received no read-back request
- eventual consistency: the mock persists on the 2nd read; L5 passes using the injected sleep (no real waiting)

## Done when

Every tool with `"write": true` has read-back verification on healed writes.
