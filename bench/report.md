# Benchmark report

- Mode: scripted (fixed tool calls, no LLM; the baseline re-sends a failing call with the same arguments until the cap of 10)
- Runs per scenario and agent (N): 3
- Date (UTC): 2026-10-13 20:04
- Jev available: configured, but gave no usable answer in 3 heals (JEV_UNAVAILABLE)
- Scenarios: CLEAN, M1, M2, M3, M4, M5, M6, M7, M8, C1

## Per scenario

ZTAR is the share of runs whose final mock state matches the task (email, manager and one ticket; a failed read-only lookup alone does not fail a run). MTTR is p50 / p95 in ms over recovered heals.

| Scenario | Healing ZTAR | Baseline ZTAR | Baseline failure mode | Heal path | Refusal reasons | MTTR tier 1 | MTTR tier 0 |
|---|---|---|---|---|---|---|---|
| CLEAN | 100% (3/3) | 100% (3/3) | - | - | - | - | - |
| M1 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 16 / 17 (n=3) | 5 / 5 (n=3) |
| M2 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 17 / 18 (n=3) | 3 / 3 (n=3) |
| M3 | 100% (3/3) | 100% (3/3) | - | diff x3 | - | 17 / 18 (n=3) | 5 / 5 (n=3) |
| M4 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 17 / 24 (n=3) | 4 / 5 (n=3) |
| M5 | 100% (3/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 19 / 44 (n=3) | 7 / 7 (n=3) |
| M6 | 0% (0/3) | 0% (0/3) | hit cap 3/3 | - | JEV_UNAVAILABLE x3 | - | - |
| M7 | 100% (3/3) | 0% (0/3) | ended incomplete 3/3 | diff x3 | - | 17 / 17 (n=3) | - |
| M8 | 0% (0/3) | 0% (0/3) | hit cap 3/3 | - | NO_SAFE_VALUE x3 | - | - |
| C1 | 100% (3/3) | 100% (3/3) | - | - | - | - | - |

## ZTAR overall

- ZTAR M1-M7, healing: 86% (18/21); baseline: 14% (3/21)
- ZTAR M1-M8, healing: 75% (18/24); baseline: 12% (3/24)

M8 counts as not adapted: it is a deliberate refusal (the healer aborts with NO_SAFE_VALUE instead of inventing a value for the new required `priority`).
