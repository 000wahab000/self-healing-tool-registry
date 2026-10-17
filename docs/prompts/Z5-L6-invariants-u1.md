# Z5: L6 invariants catch U1 (wrong units) through the real registry

**Depends on Z0.**

## Problem

L6 supports invariant kinds (check which of `id_equals_request`, `non_empty`, `list_not_shrunk`, `type_is`, `range` exist in the L6 code). Only `update_email` configures one (`id_equals_request`). The U1 mutation (an amount silently switching between cents and dollars) exists in the mock, but no test proves L6 refuses it through the **frozen four-tool registry** (`get_user`, `update_email`, `set_manager`, `create_ticket`). None of those four tools carries an amount, so U1 may currently be untestable end to end.

## Owns

- `src/healer/layers/l6_invariants.py`: add only missing invariant kinds from the list above
- `config/tools.json`: `invariants` entries
- `mock_api/app.py`: only if U1 needs a field on one of the four existing tools
- `tests/integration/test_ac_88_u1_units.py` (new)
- `product.md`: AC-88

## Build

1. Investigate first and write in the PR which tool and field U1 actually mutates, and whether that field is reachable through the four registered tools.
2. If it is reachable: add a `range` (or `type_is`) invariant in `tools.json` for that tool, chosen from the field's documented domain in the spec or mock. Do not invent a business range. If the spec gives no bound, say so and use the bound the mock's own validation enforces.
3. If it is **not** reachable: do **not** add a fifth tool (that changes the frozen tool set, contract 4). Instead attach U1 to an existing tool's existing numeric field, if one exists. If none exists, stop and report "U1 not provable through the frozen registry", with the reason.
4. Add any missing invariant kinds from the list, each pure and deterministic, with a unit test.

## Tests (`test_ac_88_*`)

- Unit, one per invariant kind: a pass case and a fail case.
- Integration (if reachable): U1 heals the shape but L6 fails on the value; registry unchanged; one audit row; `retry: false`; the oracle reports no WRONG_ACCEPTED.
- Normal values pass L6.

## Done when

Either U1 is refused by L6 through the real registry, or the PR proves why it cannot be, without changing the tool set.
