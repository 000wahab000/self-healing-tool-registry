# Z11: Never heal non-drift (fault-injection matrix + Retry-After date form)

## Problem

Transient and business errors must never produce a patch. `detect.py` `_retry_after` (around line 63) accepts only the numeric `Retry-After` form. The HTTP-date form (`Retry-After: Wed, 21 Oct 2026 07:28:00 GMT`) may be ignored or misclassified. Check whether `main` already parses it; one grep hit suggests it may be partly done.

## Owns

- `src/healer/detect.py`: `Retry-After` parsing only
- `tests/integration/test_ac_92_fault_matrix.py` (new)
- `product.md`: AC-92

## Build

1. HTTP-date: parse with `email.utils.parsedate_to_datetime`, convert it to seconds from an **injectable clock** (follow how `retry.py` injects time), and clamp it to `>= 0`. Unparseable values give `None` (today's behaviour). Cap at the existing max backoff if one exists.
2. Fault matrix (parametrised, through an `httpx.MockTransport` on a real registry):

| Fault | Expected |
|---|---|
| 429 + `Retry-After: 2` | E1 transient, no patch |
| 429 + HTTP-date | E1 transient with the right delay, no patch |
| timeout | no patch |
| 503 | no patch |
| truncated JSON body | no patch |
| malformed JSON body | no patch |
| 409 conflict | business error passed through, no patch |
| C3 invalid email (400 business) | `NOT_DRIFT`, no patch |
| 5xx during the replay after a heal | no commit; the fix stays uncommitted |

For each, assert: no new row in `fixes`; no `heal_events` row with a commit outcome (RECOVERED); `active_fix` unchanged; the agent gets the upstream error class (not a heal refusal), except the replay-5xx case, which follows the verify-failure contract.

## Done when

All nine faults produce no patch, and both `Retry-After` forms are honoured.
