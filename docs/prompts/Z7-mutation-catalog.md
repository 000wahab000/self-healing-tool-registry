# Z7: One catalog of mutation labels, and an honest denominator

## Problem

Mutation labels are scattered. `bench/run.py` has `HEALABLE_MUTATIONS`, `M6_SCENARIOS`, `ZTAR_SCENARIOS`, `MCP_HEALABLE`, `MCP_REFUSE`; `mock_api/app.py` has `expected_canonical` and a mutation list; `bench/oracle.py` and `metrics.py` check `must_refuse` separately. A new mutation (W1, U1, D1, M10, M11, fuzz cases) can be labelled in one place and missed in another, which silently changes the ZTAR denominator.

## Owns

- `mock_api/catalog.py` (new): the single source of truth
- `bench/run.py`, `bench/oracle.py`, `mock_api/app.py`: replace the local constants with imports from the catalog; no logic change
- `src/healer/metrics.py`: add `correct_handling_rate()` only
- `tests/bench/test_ac_88_catalog.py` (new)
- `product.md`: AC-88

## Build

1. `catalog.py`:
   ```python
   @dataclass(frozen=True)
   class Mutation:
       id: str                 # "M1", "W1", "MCP-T-ENUM", ...
       kind: str               # "rename" | "type" | "nesting" | "header" | "route" | "write_not_saved" | "units" | "side_effect" | "control" | ...
       label: str              # "healable" | "must_refuse" | "control"
       expected_reason: str | None   # for must_refuse, e.g. "NO_SAFE_VALUE"
       protocol: str           # "rest" | "mcp" | "graphql"
   CATALOG: dict[str, Mutation]
   def healable(protocol="rest") -> tuple[str, ...]: ...
   def must_refuse(protocol="rest") -> tuple[str, ...]: ...
   ```
   Fill it from the current constants. **The labels must not change.** Make a table in the PR of every mutation with its old and new label, and they must match. M8, M10 and M6-N are `must_refuse`. Label W1, U1 and D1 per their current tests; if no test decides it, mark it in the PR as needing an owner decision and pick `must_refuse` (the conservative choice).
2. `correct_handling_rate(rows)` = (correctly healed healable + correctly refused must_refuse + controls passed through untouched) / all runs. ZTAR stays healable-only. Safe-Refusal stays must_refuse-only. Never fold one set into another.
3. Keep `expected_canonical` in the mock but key it by catalog id. Add a test that every healable and must_refuse id in the catalog has an `expected_canonical`.

## Room for later

Z10's fuzz cases register as `Mutation` objects with `protocol="rest"` and `id="FZ-<seed>-<i>"`. New protocols add rows here, not new constants.

## Tests (`test_ac_88_*`)

- every id is used by the mock or the bench (no dead rows), and every mutation the mock implements is in the catalog
- the healable and must_refuse sets are disjoint
- `ZTAR_SCENARIOS` derived from the catalog equals the old constant (regression guard)
- `correct_handling_rate` on a hand-built row set

## Done when

Adding a mutation means adding one catalog row, and every metric picks it up with the right label.
