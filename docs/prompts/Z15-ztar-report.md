# Z15: ZTAR report with layers, intervals and fuzz (last)

**Depends on Z7, Z9, Z10 and Z12.** Run it after the layer tasks (Z1-Z6) you intend to ship have merged.

## Owns

- `bench/run.py`: the report-building functions only
- `bench/report.md`: regenerated, never hand-edited
- `tests/bench/test_ac_98_report.py` (new)
- `product.md`: AC-98
- `README.md` / pitch copy: update numbers **only** from the regenerated report (AGENTS.md claims rule)

## Build

Add these sections to the generated report, keeping the existing ones:

1. **Layer table:** per layer L1-L7, the count of pass / fail / skip across all heal events, read from `heal_events.layers`.
2. **Which layer caught what:** per failure class (invented value, missing field, reshaped response, dropped field, not saved, wrong units, duplicate write), the layer that failed, taken from the Z9 proof run's audit rows. If a class was not exercised, write "not exercised", not a guess.
3. **ZTAR with Wilson 95% CIs:** hand-written M-set vs fuzz (from `bench/results/fuzz-<seed>.json` if present; otherwise write "fuzz not run" and the command), overall and per mutation kind.
4. **Safe-Refusal Rate** and **False-Patch Rate (oracle-based)**, with CIs.
5. **Correct-Handling Rate** (Z7).
6. **MTTR p50/p95** by tier (already computed; just make sure it is present).
7. A header line with the exact commands and seeds used, the N per mutation, and the git commit.

## Tests (`test_ac_98_*`)

- build the report from a small fixture result set: every section heading is present; the CI text matches `wilson()` output
- with no fuzz file present: "fuzz not run" appears, with no exception
- no number in the report is absent from the input rows (spot-check 3 values)

## Final PR body must include

What changed per file, new test counts, the full `pytest -q` summary line, the bench commands used, and any layer that could not be implemented, with the reason (collect these from the Z1-Z6 PRs).

## Done when

`bench/report.md` alone proves ZTAR, safety and speed with intervals and layer attribution.
