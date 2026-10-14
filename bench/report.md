# Benchmark report

- Mode: scripted (fixed tool calls, no LLM; the baseline re-sends a failing call with the same arguments until the cap of 10)
- Runs per scenario and agent (N): 3
- Date (UTC): 2026-10-14 12:54
- Jev available: no (M6 cannot heal without Jev: its two candidates need Jev to choose)
- Scenarios: CLEAN, M1, M2, M3, M4, M5, M6-D, M6-N, M7, M8, M9, C1

## Per scenario

ZTAR is the share of runs whose final mock state matches the task (email, manager and one ticket; a failed read-only lookup alone does not fail a run). MTTR is p50 / p95 in ms over recovered heals. ZTAR is reported per the v3 spec: healing ZTAR over HEALABLE_MUTATIONS (M1-M5, M7, M9), with M6-D and M6-N reported separately.

| Scenario | Healing ZTAR | Baseline ZTAR | Baseline failure mode | Heal path | Refusal reasons | MTTR tier 1 | MTTR tier 0 |
|---|---|---|---|---|---|---|---|
| CLEAN | n/a | n/a | - | - | - | - | - |
| M1 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 22 / 24 (n=3) | 2 / 2 (n=3) |
| M2 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 22 / 23 (n=3) | 2 / 2 (n=3) |
| M3 | 100% (3/3) | 100% (3/3) | - | diff x3 | - | 22 / 22 (n=3) | 1 / 1 (n=3) |
| M4 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 23 / 24 (n=3) | 2 / 2 (n=3) |
| M5 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 26 / 26 (n=3) | 3 / 3 (n=3) |
| M6-D | n/a | n/a | hit cap 3/3 | tiebreak x3 | - | 24 / 25 (n=3) | - |
| M6-N | n/a | n/a | hit cap 3/3 | - | LOW_CONFIDENCE x3 | - | - |
| M7 | 100% (3/3) | 0% (0/3) | ended incomplete 3/3 | diff x3 | - | 22 / 27 (n=3) | - |
| M8 | n/a | n/a | hit cap 3/3 | - | NO_SAFE_VALUE x3 | - | - |
| M9 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 26 / 26 (n=3) | - |
| C1 | n/a | n/a | - | - | - | - | - |

## ZTAR overall

- ZTAR M1-M5, M7, M9 (healable), healing: 100% (21/21); baseline: 14% (3/21)
- ZTAR M6-D: computed separately; M6-N: computed separately

M8 counts as not adapted: it is a deliberate refusal (the healer aborts with NO_SAFE_VALUE instead of inventing a value for the new required `priority`).

## Error-only ablation (`spec_mode=off`, FR-15.7, AC-23)

Runs of M1–M9 with the spec endpoint disabled (error-clue mode). Per-mutation outcome, reason code, and False-Patch Rate must stay 0. Reported in `results.jsonl` and summarized in `report.md`.
