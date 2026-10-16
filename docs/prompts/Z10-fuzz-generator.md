# Z10: Seeded drift fuzzer for held-out ZTAR

**Depends on Z7** (the catalog).

## Why

M1-M11 are hand-written, so the healer could be tuned to them. A seeded generator of composed drifts gives a held-out ZTAR that is reported **separately**.

## Owns

- `bench/fuzz.py` (new): generator + runner, CLI `python -m bench.fuzz --seed 7 --n 50`
- `mock_api/app.py`: one hook that lets the mock serve a generated mutation spec. Keep it small; prefer passing a mutation description object over adding per-case branches.
- `tests/bench/test_ac_91_fuzz.py` (new)
- `product.md`: AC-91

Do **not** edit `bench/run.py` or the report. Z14 wires fuzz results into the report.

## Build

1. Primitives: rename field, type change (int/str), nesting/wrapper, new required header (sourced from `header_sources`), route rename. Each primitive knows how it transforms (a) the spec, (b) the mock's accepted request, and (c) `expected_canonical`.
2. `generate(seed, n) -> list[FuzzCase]`: uses `random.Random(seed)` only (no global random), composing 1-3 primitives per case on one of the four registered tools.
3. Label from the composition, deterministically:
   - `healable` if every value in `expected_canonical` traces to agent args, a config key or the spec
   - `must_refuse` if any primitive would need a value with no source (for example a new required body field with no default in the spec)
   - Write the labelling rule as a docstring table.
4. Each case registers as a catalog `Mutation` (`id="FZ-<seed>-<i>"`) in a run-local catalog extension. Do not write to the static `CATALOG`.
5. The runner executes each case through the scripted healing agent with the oracle and prints: the seed, n, fuzz ZTAR (healable only), Safe-Refusal (must_refuse only), False-Patch, and the failures listed by case id + primitives. It writes `bench/results/fuzz-<seed>.json` (gitignored).

## Tests (`test_ac_91_*`)

- the same seed gives identical cases; a different seed gives different cases
- labelling: rename-only is healable; a new required field with no source is must_refuse
- a small run (`n=5`, fixed seed) completes, with no WRONG_ACCEPTED on cases the healer marks recovered
- the output includes the seed

## Done when

`python -m bench.fuzz --seed S --n N` is reproducible and reports fuzz ZTAR separately from M1-M11.
