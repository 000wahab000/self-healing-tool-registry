# Benchmark report

- Mode: scripted (fixed tool calls, no LLM; the baseline re-sends a failing call with the same arguments until the cap of 10)
- Runs per scenario and agent (N): 3
- Date (UTC): 2026-10-16 10:33
- Jev available: no (M6-N then aborts LOW_CONFIDENCE, which counts as a safe refusal)
- Spec mode: `on` for the main and tier-0 passes, `off` for the error-only ablation
- Scenarios: CLEAN, M1, M2, M3, M4, M5, M6-D, M6-N, M7, M8, M9, C1, C2, C3

## Per scenario

ZTAR is the share of runs whose task completed and whose final mock state is correct (FR-15.4); it is only defined for the healable mutations and for M6-D / M6-N, so the other rows read `n/a`. Expected outcome is the scenario's own expectation: the completed task for CLEAN, C1 and the mutations, a safe refusal for M8 (and for M6-N while Jev is disabled), a pass-through for C2 and C3. MTTR and heal_ms are mean / p50 / p95 in ms over recovered heals; tier 0 is the M1-M5 rerun served from the stored fix.

| Scenario | Healing ZTAR | Healing expected outcome | Baseline ZTAR | Baseline expected outcome | Baseline failure mode | Heal path | Refusal reasons | MTTR tier 1 | MTTR tier 0 | heal_ms tier 1 | heal_ms tier 0 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CLEAN | n/a | 100% (3/3) | n/a | 100% (3/3) | - | - | - | - | - | - | - |
| M1 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 29/30/32 (n=3) | 4/4/5 (n=3) | 29/30/32 (n=3) | 4/4/5 (n=3) |
| M2 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 22.6667/22/24 (n=3) | 2.33333/2/3 (n=3) | 22.6667/22/24 (n=3) | 2.33333/2/3 (n=3) |
| M3 | 100% (3/3) | 100% (3/3) | 100% (3/3) | 100% (3/3) | - | diff x3 | - | 37.3333/28/63 (n=3) | 5.33333/5/7 (n=3) | 37.3333/28/63 (n=3) | 5.33333/5/7 (n=3) |
| M4 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 21.6667/22/22 (n=3) | 3.33333/3/5 (n=3) | 21.6667/22/22 (n=3) | 3.33333/3/5 (n=3) |
| M5 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 30.6667/30/37 (n=3) | 6.66667/6/9 (n=3) | 30.6667/30/37 (n=3) | 6.66667/6/9 (n=3) |
| M6-D | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | tiebreak x3 | - | 25.3333/26/28 (n=3) | - | 25.3333/26/28 (n=3) | - |
| M6-N | 0% (0/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | - | LOW_CONFIDENCE x3 | - | - | - | - |
| M7 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | ended incomplete 3/3 | diff x3 | - | 62/23/142 (n=3) | - | 62/23/142 (n=3) | - |
| M8 | n/a | 100% (3/3) | n/a | 0% (0/3) | hit cap 3/3 | - | NO_SAFE_VALUE x3 | - | - | - | - |
| M9 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | hit cap 3/3 | diff x3 | - | 27.3333/27/29 (n=3) | - | 27.3333/27/29 (n=3) | - |
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
| 0 | 15 | 4.33333/4/9 (n=15) | 4.33333/4/9 (n=15) |
| 1 | 24 | 32/25.5/63 (n=24) | 32/25.5/63 (n=24) |

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

## MCP gateway (T1-8, T1-9, AC-53, AC-54)

Each drift-server mutation runs a fixed three-call task (`get_user`, `update_email`, `create_ticket`) through a healing `Gateway` and through a baseline `upstream_registry` with no store (errors pass through; the baseline re-sends a failing call until the cap of 10 calls). Everything is in-memory. ZTAR, Safe-Refusal and False-Patch use the same definitions as the REST tables.

| Mutation | Healing ZTAR | Healing expected outcome | Baseline ZTAR | Baseline expected outcome | Heal path | Refusal reasons | MTTR tier 1 | heal_ms tier 1 |
|---|---|---|---|---|---|---|---|---|
| M1 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | diff x3 | - | 7/6/9 (n=3) | 7/6/9 (n=3) |
| M2 | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | diff x3 | - | 6.33333/6/7 (n=3) | 6.33333/6/7 (n=3) |
| T-RENAME | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | diff x3 | - | 6.33333/6/7 (n=3) | 6.33333/6/7 (n=3) |
| T-ENUM | 100% (3/3) | 100% (3/3) | 0% (0/3) | 0% (0/3) | diff x3 | - | 7/7/8 (n=3) | 7/7/8 (n=3) |
| T-REQUIRED | n/a | 100% (3/3) | n/a | 100% (3/3) | - | NO_SAFE_VALUE x3 | - | - |
| M8 | n/a | 100% (3/3) | n/a | 100% (3/3) | - | NO_SAFE_VALUE x3 | - | - |

- Healable ZTAR (M1, M2, T-RENAME, T-ENUM), healing: 100% (12/12); baseline: 0% (0/12)
- Safe-Refusal Rate (T-REQUIRED, M8): 100% (6/6)
- False-Patch Rate: 0% (0/12) of the healed runs ended with a wrong final state.
- T-MOVE needs the tier-2 repair agent and was skipped in scripted mode (run `--agent llm`).

Healthy-call overhead over MCP (`users__get_user`, n=250 per side, in-memory; gateway call minus a direct `ClientSession.call_tool`):

| Series | p50 ms | p95 ms | mean ms |
|---|---|---|---|
| gateway | 0.895 | 2.381 | 1.227 |
| direct | 0.795 | 3.354 | 1.129 |
| overhead | 0.112 | 0.802 | 0.098 |

<!-- supplementary-evidence -->

## Supplementary empirical evidence (separate runs; not part of the REST scorecard)

The sections below preserve evidence produced after the scorecard above. They use different harnesses, dates, samples, and environments; do not combine their counts with the dated REST/MCP benchmark tables or treat them as a rerun of that benchmark.

### Tier-2 stress test and MCP client (2026-10-17)

Source label: pre-consolidation `bench/stress-summary.md` (2026-10-17), available in repository history. The source named a separate `stress-test` worktree's `bench/stress/tier2/REPORT.md` and `tier2/results.json`; those stress raw files are not retained in this checkout, and the referenced Prism harness had no results. These figures are preserved from the source summary, not independently reproducible from the current tree.

The live repair-agent test used `openai/gpt-oss-20b` on NVIDIA NIM. Jev returned 401, so a stub Jev answered only the tier-2 triage question in the main arms.

| Measure | Result |
|---|---|
| Scenario invocations | 44 (28 at the shipped 30 s deadline, 16 at 100 s) |
| Model answered in time | 6 of 44 (14%) |
| Healed | 5 of 44 (2 of 28 at 30 s, 3 of 16 at 100 s) |
| Answered proposals that were correct | 6 of 6 |
| False patches | 0 of 92 rows and 0 of 12 direct calls |
| Safe refusals (M8, new required field) | 4 of 4, all at tier 1 with no LLM call |
| Latency of answered calls | p50 30.9 s, p95 49.7 s (n=6) |
| Tokens per answered heal | 822 to 972 (mean 876) |
| Stored fix reused at tier 0 | 3 of 3 checked |
| M11 with tier 2 off vs on | 0/1 vs 3/14 |
| M6-N with tier 2 off vs on | safe refusal vs 2/9 |

The source summary states the 11% heal rate mostly measures endpoint timeouts, not model quality; N is small and comes from one day on one degraded endpoint. In a separate Claude Code run (`claude -p`, Haiku) using only healer tools over `http://127.0.0.1:8097/mcp` with M1 drift, it looked up user 123 and changed the email successfully; `get_user` healed at tier 1 (spec diff), and the MCP tab logged both calls. The Prism external-API harness was stopped before results.

The source also records failure cases: a write tool without `preverify` cannot recover through tier 2; readback after a `user_id` rename can report `VERIFY_FAILED` despite a landed write; many repair calls missed even the 100 s deadline; without Jev only `NO_CANDIDATE` reaches tier 2; model over-refusal; same-typed field renames invisible to detection; a potential negative-cache path on repair HTTP error (not observed); a benchmark task-completion check that ignores `get_user`; Windows stdio startup trouble with the default config; and the two Jev routes returning 401. These are source observations, not verified current defects.

### GitHub MCP chaos (2026-10-17)

Source label: pre-consolidation `bench/chaos/github/REPORT.md` (2026-10-17), available in repository history. The experiment froze a false MCP `inputSchema`, switched the shim to passthrough, and compared calls accepted by a strict offline fake or live GitHub MCP against intended arguments. The live target was an empty sandbox repository; only read tools were exposed. Expected outcomes were fixed in `bench/chaos/github/cases.yaml` before the run (sha256 prefix `c5e549dd73a34ca7`). Harness/source files remain at `bench/chaos/github/run.py`, `shim.py`, `profiles.py`, `common.py`, and `fake_upstream.py`.

**Final runs after the fix:** offline controls used six calls per profile and the agent ran two tasks per profile. Offline reported **0 false patches and 0 crashes**; misses were limited to `rename_owner_repo` (4 control, 2 agent) and three partial `wrap_args` controls, all safe refusals. Live GitHub reported **0 real false patches** and one successful live heal (`nest_repo`, agent). Two scorer `FALSE_PATCH` rows were `enum_case` cases where GitHub accepted lowercase `open` as well as `OPEN`, so no heal ran; the report labels these a scoring artifact. Several live “misses” were because the empty repository lacked issue #1, `README.md`, and commits.

Offline profile outcomes (source table; counts, not rates):

| Profile | Control (6 calls) | Agent |
|---|---|---|
| identity | 6 pass-through | not run |
| rename_owner_repo | 2 pass-through, 4 refused | 2 refused |
| rename_issue_number | 1 healed, 5 pass-through | 1 healed, 1 pass-through |
| int_to_string | 2 healed, 4 pass-through | 1 healed, 1 pass-through |
| wrap_args | 2 healed, 1 pass-through, 3 refused | 1 healed, 1 refused |
| nest_repo | 4 healed, 2 pass-through | 2 healed |
| enum_case | 1 healed, 5 pass-through | 1 healed, 1 pass-through |
| enum_synonym | 1 refused (expected), 5 pass-through | 1 refused, 2 pass-through, 1 agent arg error |
| merge_owner_repo | 4 refused (expected), 2 pass-through | 2 refused (expected) |
| decoy_unused | 6 pass-through | not run |
| decoy_used | 6 refused (expected) | not run |

Before/after comparison from the same chaos report:

| | Before (live) | After (live) | After (offline) |
|---|---|---|---|
| Real false patches | 1 (`wrap_args`: `state` filter silently dropped) | 0 | 0 |
| `nest_repo` heals | 0 (leftover `"repository": {}`) | 1 | 6 of 6 |
| `wrap_args` heals | 0 | 0 | 3 |

The before/after report records one real false patch before the fix (`wrap_args`: the `state` filter was silently dropped), versus zero after; offline `nest_repo` healed 6/6. The described fix added MCP `inputSchema` request validation at L2 and made `move` remove wrappers it empties, so partial unwrap fails verification and is refused. The live post-fix summary still includes one `enum_case` scorer row; do not reinterpret it as an actual wrong request.

This is one run per profile per mode, so counts are not rates. The offline fake approximates GitHub's schema; live checks are ground truth but the empty sandbox caused business errors. The Oct 17, 2026 source report lists remaining limits at that time: live healing often exceeded the 3.5 s deadline; two simultaneous same-typed field renames were refused; a live GitHub `E1 -32001` was treated as transient; partial wrapper mappings were safely refused; and the scorer mislabelled a valid case-insensitive enum. Its provider-coverage statement was also specific to that run date and is not a claim about current coverage. Regression tests for the fix are `tests/integration/test_verify_layers.py::test_mcp_partial_unwrap_fails_request_schema`, `tests/integration/test_verify_layers.py::test_mcp_full_unwrap_drops_the_empty_wrapper_and_passes`, and `tests/unit/test_ops.py::test_move_removes_wrappers_it_empties_only`.

Retained raw proof files: [`bench/chaos/github/proof/offline/results.jsonl`](bench/chaos/github/proof/offline/results.jsonl), [`bench/chaos/github/proof/offline/shim_calls.jsonl`](bench/chaos/github/proof/offline/shim_calls.jsonl), [`bench/chaos/github/proof/offline/upstream_calls.jsonl`](bench/chaos/github/proof/offline/upstream_calls.jsonl), [`bench/chaos/github/proof/live/results.jsonl`](bench/chaos/github/proof/live/results.jsonl), and [`bench/chaos/github/proof/live/shim_calls.jsonl`](bench/chaos/github/proof/live/shim_calls.jsonl). Run logs and agent transcripts remain alongside these JSONL files. The source report and summary Markdown are in repository history, not required to interpret the preserved tables above.
