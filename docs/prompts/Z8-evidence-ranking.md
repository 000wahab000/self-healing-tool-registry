# Z8: Evidence ranking, and refusal on a tie

## Problem

`src/healer/candidates.py` builds candidate fixes and `tiebreak()` (around line 296) picks one. The rule must be explicit: evidence strength ranks **spec diff > structured error details (422 `loc`/`type`) > error-message clues**. If candidates are still tied after the deterministic tie-breaker and Jev is disabled, the healer must **refuse, never guess**.

## Owns

- `src/healer/candidates.py`: ranking and tie handling only
- `tests/unit/test_ac_89_evidence_ranking.py` (new)
- `product.md`: AC-89

## Build

1. Read `candidates.py` and `diagnose.py`. Write in the PR how evidence sources are tagged today. If candidates do not record which source produced them, add an `evidence` field with values `"spec_diff" | "error_detail" | "error_message"` at creation. This is internal only; it is not stored in fixes unless a store field already exists.
2. Sort candidates by evidence rank first, then by the existing tie-breaker.
3. If the top two are still equal on every key and Jev is disabled or unavailable: return no candidate. The heal path must then emit the existing `LOW_CONFIDENCE` refusal (check the exact `Reason` name in `models.py`).
4. If Jev is enabled, keep today's behaviour (Jev picks one of ours, never produces a value).

## Tests (`test_ac_89_*`)

- spec_diff vs error_message candidates: spec_diff wins even if the tie-breaker alone prefers the other
- two identical-rank, identical-key candidates, Jev disabled: refusal (`LOW_CONFIDENCE`), no fix created, one audit row
- same with Jev enabled (stub Jev): Jev's pick is used
- M6-D still heals via tiebreak; M6-N still refuses (bench regression)

## Done when

A tie that the evidence cannot break always ends in a refusal, never a guess.
