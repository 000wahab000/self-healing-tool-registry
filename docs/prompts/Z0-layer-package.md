# Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)

## Why

`src/healer/verify.py` (~244 lines) holds all seven layers. Z1-Z6 each change one layer. If they all edit `verify.py`, every PR conflicts. This task moves each layer behind a small interface, **with no change in behaviour**, so later tasks each own one file.

## Owns

- `src/healer/layers/__init__.py` (new): the ordered layer list
- `src/healer/layers/l1_provenance.py` ... `l7_replay.py` (new, seven files)
- `src/healer/verify.py`: becomes a thin orchestrator
- `tests/unit/test_ac_81_layer_package.py` (new)
- `product.md`: one AC row (AC-81)

## Build

1. Read `verify.py` fully first. List in the PR which existing function moves to which layer file.
2. A shared result helper (`_row`, `_skip_from`) goes in `layers/__init__.py`. Each layer module exposes one function with a uniform signature, for example:
   ```python
   NAME = "provenance"
   LAYER = 1
   def check(ctx: LayerContext) -> LayerResult: ...   # async if the layer does I/O (L5)
   ```
   `LayerContext` is a small frozen dataclass holding what the layers already receive today (base_doc, patched doc, current spec, fix, response, tool config, sleep). Add no new fields that nothing uses yet.
3. `verify.py` keeps its public API (`Verifier`, `preflight`, `verify`) and **identical return values**. It loops over `layers.ORDERED`, applies the same "stop at first fail, mark the rest `skip/not_reached`" rule, and keeps the special skips (`spec_unavailable`, `protocol_schema`, `not_healed_write`).
4. No behaviour change. No new checks. Do not touch `heal.py`.

## Room for later

A future L8 = one new file + one entry in `layers.ORDERED`. Z1-Z6 each edit only their own file.

## Tests (`test_ac_81_*`)

- `layers.ORDERED` has 7 entries with layers 1..7 in order and the same names `verify.py` used before.
- Golden test: for a handful of existing fixtures (take them from `tests/unit/` verify tests or build minimal ones), the per-layer rows from the new `verify()` equal the rows from the old one. Capture the old output in the test as literal expected data before refactoring.
- The whole existing suite passes unchanged.

## Done when

`verify.py` contains no layer logic, every layer is its own module, and every pre-existing layer row is byte-identical.
