# Z9: Prove "verify before commit" for every layer (tests only)

## Why

The invariant: a failed layer leaves the registry untouched and writes exactly one audit row. It is asserted in places but not as one systematic matrix. This task is **tests only**. If a test exposes a real bug, mark it `xfail(strict=True, reason=...)`, report it, and do not fix it here.

## Owns

- `tests/integration/test_ac_90_verify_before_commit.py` (new)
- `product.md`: AC-90

## Build

One parametrised test over the seven failure classes:

| Case | Layer that must fail | Source |
|---|---|---|
| invented value | L1 | a hand-built fix whose op has an unsourced value |
| missing or mistyped field | L2 | a fix that drops a required field |
| response reshaped wrongly | L3 | an E5 fix that does not satisfy the agent schema |
| field silently dropped | L4 | M7 |
| 200 but nothing saved | L5 | W1 |
| valid but wrong units | L6 | U1 (skip with reason if Z5 proved it unreachable) |
| replay would duplicate a write | L7 | D1 |

For each case assert:
- `tool.active_fix`, the tool version and the wire op are identical before and after
- exactly **one** new `heal_events` row, whose `layers` JSON shows the expected layer as `fail` and every later layer as `skip`
- the agent gets a structured refusal with `retry: false`
- the oracle classification for the run is not `WRONG_ACCEPTED`

Use the existing mock and registry fixtures; read `tests/integration/` and `tests/unit/` for helpers before writing new ones.

## Done when

All seven rows pass (or are strict xfails with a filed reason), in one file anyone can read as the proof table.
