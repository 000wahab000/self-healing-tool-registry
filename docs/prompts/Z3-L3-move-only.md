# Z3: L3 / E5 allows only move or unwrap, with response-source provenance

**Depends on Z0.**

## Problem

When a response no longer matches the frozen agent-facing output schema (E5), the healer may remap it locally. Today that remap **can still cast** a value (for example str to int). The rule is: the response side may only **move or unwrap** existing values, never change their type or create values. Response-side ops also lack the provenance check: every value in the remapped output must come from a path in the actual response.

## Owns

- `src/healer/layers/l3_output.py`
- `tests/unit/test_ac_86_l3_move_only.py` (new)
- `product.md`: AC-86

If the cast is generated upstream of L3 (in `candidates.py` or `diagnose.py`), **do not edit those files**. L3 rejects the candidate, and the PR lists where the cast candidate is produced as a follow-up.

## Build

1. Failing test first: an E5 drift where the only candidate is a response cast. Today it passes L3.
2. In L3, before validating the remapped output, inspect the response-side ops of the fix. Allowed kinds: those in `ops.py` that only relocate a value (move, rename, unwrap, or whatever names `ops.py` actually uses; list them in the PR). Anything else on the response side gives `fail` with `detail="response_op_not_allowed:<op>"`.
3. Provenance: every source path of a response op must exist in the actual response body. Otherwise `fail`, `detail="response_source_missing:<path>"`.
4. Then the existing check: the remapped output validates against the frozen agent schema.

## Tests (`test_ac_86_*`)

- unwrap `{data:{...}}` to `{...}`: pass (the M3 nesting path stays green)
- move/rename a response field: pass
- cast str to int on the response side: fail
- a response op whose source path is absent: fail
- the failure leaves the registry unchanged, writes one audit row and returns `retry: false`

## Done when

A response-side fix can only relocate values that really exist in the response.
