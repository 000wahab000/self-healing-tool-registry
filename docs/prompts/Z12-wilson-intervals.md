# Z12: Wilson 95% confidence intervals and N=30

## Why

With N=3 per mutation, "100% ZTAR" means little. Rates need intervals, and the default sample has to be big enough for the intervals to be useful.

## Owns

- `src/healer/metrics.py`: add `wilson(successes, n, z=1.96) -> tuple[float, float]`, plus `with_ci()` wrappers for `ztar`, `safe_refusal` and `false_patch_rate` that add `{"low":..,"high":..}` without changing their existing return keys
- `bench/run.py`: only the `--n` default (from 10 to 30) for scripted mode; keep the LLM-mode default low and note why (cost)
- `tests/unit/test_ac_93_wilson.py` (new)
- `product.md`: AC-93

Do not edit the report layout; Z14 does that.

## Build

- Wilson score interval, pure Python (`math` only). `n == 0` gives `(0.0, 1.0)`. Clamp to [0, 1].
- Per-mutation-kind grouping helper: `rates_by_kind(rows, catalog)` returns `{kind: {rate, low, high, n}}`. Use Z7's catalog if merged; otherwise group by scenario id and leave a TODO naming Z7.
- Existing callers of `ztar()` etc. are unaffected (new keys are additive or come from new functions).

## Tests (`test_ac_93_*`)

- known values, e.g. `wilson(30, 30)` gives about (0.886, 1.0), and `wilson(0, 30)` about (0.0, 0.114); check to 3 decimals against a reference you compute in the test docstring
- `n=0` edge case
- monotonic: more successes never lowers `low`
- existing metrics tests stay unchanged

## Done when

Every headline rate can be reported as `rate [low, high]`, and scripted benches default to 30 runs per mutation.
