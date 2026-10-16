# Z1: L1 provenance checks enum targets against the current spec

**Depends on Z0.**

## Problem

L1 checks that every op source exists (args, config or spec) before replay. When an op maps a value into a field whose **current** spec schema has an `enum`, L1 does not check that the mapped value is one of the current enum values. The T-ENUM drift (an enum value renamed upstream) can therefore pass L1 with a stale value and only fail later, or be accepted wrongly.

## Owns

- `src/healer/layers/l1_provenance.py`
- the helper in `verify.py`/`layers` that collects spec constraints (`_spec_constraints` already gathers enum values separately. Reuse it, do not duplicate it)
- `tests/unit/test_ac_82_l1_enum.py` (new)
- `product.md`: AC-82

## Build

1. Confirm the gap: write a failing test where an op writes a value not in the current spec enum, and L1 passes it.
2. In L1: for each op target path whose current schema has an `enum`, the resolved value (from args, config or a spec-sourced mapping) must be in that enum, after the same normalisation `canonical.py` uses. Otherwise fail with `detail="enum_not_in_spec:<path>"`.
3. An enum **value mapping** (old to new value) is allowed only if both values come from the old and new spec enums (spec provenance). It is never invented. If ops cannot express this mapping, say so in the PR and stop. Do not add a literal-carrying op.
4. If the spec is unavailable, L1 keeps today's behaviour; it does not fail closed on enums it cannot see. Note this in the detail string.

## Tests (`test_ac_82_*`)

- value in the current enum: pass
- value only in the old enum: fail, `enum_not_in_spec`
- spec-sourced old-to-new mapping: pass
- integration: the MCP `T-ENUM` scenario (or the REST equivalent if it exists) still heals, and a hand-made op with a non-enum value is refused with exactly one audit row and `retry: false`

## Done when

No patched request can carry an enum value that the current spec does not list.
