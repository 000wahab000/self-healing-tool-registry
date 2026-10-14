# Benchmark report

- Mode: scripted (fixed tool calls, no LLM; the baseline re-sends a failing call with the same arguments until the cap of 10)
- Runs per scenario and agent (N): 3
- Date (UTC): 2026-10-14 18:29
- Jev available: no (M6-N then aborts LOW_CONFIDENCE, which counts as a safe refusal)
- Spec mode: `on` for the main and tier-0 passes, `off` for the error-only ablation
- Scenarios: CLEAN, M1, M2, M3, M4, M5, M6-D, M6-N, M7, M8, M9, C1, C2, C3

## Per scenario

ZTAR is the share of runs whose task completed and whose final mock state is correct (FR-15.4); it is only defined for the healable mutations and for M6-D / M6-N, so the other rows read `n/a`. Expected outcome is the scenario's own expectation: the completed task for CLEAN, C1 and the mutations, a safe refusal for M8 (and for M6-N while Jev is disabled), a pass-through for C2 and C3. MTTR and heal_ms are mean / p50 / p95 in ms over recovered heals; tier 0 is the M1-M5 rerun served from the stored fix.

| Scenario | Healing ZTAR | Healing expected outcome | Baseline ZTAR | Baseline expected outcome | Baseline failure mode | Heal path | Refusal reasons | MTTR tier 1 | MTTR tier 0 | heal_ms tier 1 | heal_ms tier 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CLEAN | n/a | 100% (3/3) | n/a | 100% (3/3) | - | - | - | - | - | - | - |
| M1 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 46.3333/47/48 (n=3) | 4/4/5 (n=3) | 46.3333/47/48 (n=3) | 4/4/5 (n=3) |
| M2 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 51.3333/45/66 (n=3) | 4.33333/4/5 (n=3) | 51.3333/45/66 (n=3) | 4.33333/4/5 (n=3) |
| M3 | 100% (3/3) | 100% (3/3) | 100% (3/3) | 100% (3/3) | - | diff x3 | - | 46/47/49 (n=3) | 2.66667/3/3 (n=3) | 46/47/49 (n=3) | 2.66667/3/3 (n=3) |
| M4 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 51/52/53 (n=3) | 4.66667/5/5 (n=3) | 51/52/53 (n=3) | 4.66667/5/5 (n=3) |
| M5 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 60.3333/57/69 (n=3) | 8/8/8 (n=3) | 60.3333/57/69 (n=3) | 8/8/8 (n=3) |
| M6-D | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | tiebreak x3 | - | 48/47/51 (n=3) | - | 48/47/51 (n=3) | - |
| M6-N | 0% (0/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | - | LOW_CONFIDENCE x3 | - | - | - | - |
| M7 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | ended incomplete 3/3 | diff x3 | - | 50/52/53 (n=3) | - | 50/52/53 (n=3) | - |
| M8 | n/a | 100% (3/3) | n/a | 0% (0/3) | hit cap 3/3 | - | NO_SAFE_VALUE x3 | - | - | - | - |
| M9 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 52.3333/50/58 (n=3) | - | 52.3333/50/58 (n=3) | - |
| C1 | n/a | 100% (3/3) | n/a | 100% (3/3) | - | - | - | - | - | - | - |
| C2 | n/a | 100% (3/3) | n/a | 0% (0/3) | hit cap 3/3 | - | NOT_DRIFT x3 | - | - | - | - |
| C3 | n/a | 100% (3/3) | n/a | 0% (0/3) | hit cap 3/3 | - | NOT_DRIFT x3 | - | - | - | - |

## ZTAR (FR-15.4, AC-15)

- Healable mutations (M1, M2, M3, M4, M5, M7, M9), healing: 100% (21/21); baseline: 14% (3/21)
- M6-D, reported separately: healing 100% (3/3); baseline 0% (0/3)
- M6-N, reported separately: healing 0% (0/3); baseline 0% (0/3)

M8 is a refusal, not an adaptation: it is counted in the Safe-Refusal Rate below and never in ZTAR. C1, C2 and C3 are controls, and CLEAN only sets the token baseline. M6 never enters the healable denominator.
With Jev disabled every M6-N run aborts LOW_CONFIDENCE without writing, so its ZTAR is 0% by design and its refusal is counted below.

## Safe-Refusal Rate and False-Patch Rate (FR-15.4, AC-15)

- Safe-Refusal Rate: 100% (6/6) over M6-N, M8 runs, and no request carrying an invented value was sent in any of them.
- False-Patch Rate: 0% (0/24) of the healed runs ended with a wrong final mock state.

## Baseline outcomes (FR-15.8, AC-17)

Measured for every scenario, never asserted as pass or fail: the error loop (the baseline re-sends the same arguments until the iteration cap), the calls it made, and the final data. `Task state correct` is the demo task's end state reached with only expected writes (`n/a` where the scenario has no task: M8, M6-N without Jev and the controls). `State integrity` is FR-15.2's final-state check, no wrong or invented data, which is what the False-Patch Rate uses. Tokens are below.

| Scenario | Runs | Error loop | Calls (mean) | Task state correct | State integrity |
|---|---|---|---|---|---|
| CLEAN | 3 | 0 hit cap | 4 | 100% (3/3) | 100% (3/3) |
| M1 | 3 | 3 hit cap | 10 | 0% (0/3) | 100% (3/3) |
| M2 | 3 | 3 hit cap | 10 | 0% (0/3) | 100% (3/3) |
| M3 | 3 | 0 hit cap | 4 | 100% (3/3) | 100% (3/3) |
| M4 | 3 | 3 hit cap | 10 | 0% (0/3) | 100% (3/3) |
| M5 | 3 | 3 hit cap | 10 | 0% (0/3) | 100% (3/3) |
| M6-D | 3 | 3 hit cap | 10 | 0% (0/3) | 100% (3/3) |
| M6-N | 3 | 3 hit cap | 10 | n/a | 100% (3/3) |
| M7 | 3 | 0 hit cap | 4 | 0% (0/3) | 100% (3/3) |
| M8 | 3 | 3 hit cap | 10 | n/a | 100% (3/3) |
| M9 | 3 | 3 hit cap | 10 | 0% (0/3) | 100% (3/3) |
| C1 | 3 | 0 hit cap | 6 | 100% (3/3) | 100% (3/3) |
| C2 | 3 | 3 hit cap | 10 | n/a | 100% (3/3) |
| C3 | 3 | 3 hit cap | 10 | n/a | 100% (3/3) |

## Timings by tier (FR-15.4, AC-14)

Main and tier-0 passes, recovered heals. MTTR runs from the first failing response caused by the mutation to the first verified-correct result; `heal_ms` is the registry's internal heal time, reported separately.

| Tier | n | mttr_ms mean / p50 / p95 | heal_ms mean / p50 / p95 |
|---|---|---|---|
| 0 | 15 | 4.73333/4/8 (n=15) | 4.73333/4/8 (n=15) |
| 1 | 24 | 50.6667/49/66 (n=24) | 50.6667/49/66 (n=24) |

## Tokens (FR-8.7, FR-15.4, FR-15.5, AC-16)

Per run: mean / p50 / p95. `jev_tokens` is the classifier's own usage, reported in its own column and never added to `llm_tokens`. Overhead is the mutated run's total minus this agent's CLEAN-run median; for the baseline the same subtraction is its wasted tokens. The ratio is healing overhead divided by baseline waste, `n/a` when the baseline waste is 0.

| Scenario | Healing llm_tokens | Baseline llm_tokens | jev_tokens | Healing overhead | Baseline wasted | Ratio (healing : baseline) |
|---|---|---|---|---|---|---|
| CLEAN | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | - | - | - |
| M1 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M2 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M3 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M4 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M5 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M6-D | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M6-N | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M7 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M8 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| M9 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | 0 | 0 | n/a |
| C1 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | - | - | - |
| C2 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | - | - | - |
| C3 | 0/0/0 (n=3) | 0/0/0 (n=3) | 0/0/0 (n=3) | - | - | - |

Scripted mode makes no LLM call, so every `llm_tokens` value above is 0; run `--agent llm` to measure token overhead (AC-16).

## Error-only ablation (`spec_mode=off`, FR-15.7, AC-23)

Each mutation re-run once with the spec endpoint disabled, so diagnosis runs on the error clue alone. There is no heal-rate threshold here; the False-Patch Rate must stay 0. Combined or nested mutations (M5, M9) are expected to abort rather than patch, and so are the refusals.

| Mutation | Outcome | Reason | Final state | False patch |
|---|---|---|---|---|
| M1 | healed | - | correct | no |
| M2 | healed | - | correct | no |
| M3 | healed | - | correct | no |
| M4 | healed | - | correct | no |
| M5 | aborted | NO_CANDIDATE | correct | no |
| M6-D | aborted | NO_SAFE_VALUE | correct | no |
| M6-N | aborted | NO_SAFE_VALUE | correct | no |
| M7 | aborted | NO_CANDIDATE | correct | no |
| M8 | aborted | NO_SAFE_VALUE | correct | no |
| M9 | aborted | NO_SAFE_VALUE | correct | no |

- False-Patch Rate (ablation): 0% (0/4) of the healed runs.
