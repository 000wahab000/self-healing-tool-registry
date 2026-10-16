# F5: A run that calls no tools is not "data-correct" (correctness, must fix)

## Problem

`dashboard/explorer.py` `check_data_correctness(data, mutation, touched)`: its docstring says an empty or `None` `touched` means "check the full four-step task", but the code sets `full = touched is None`. With `touched == set()`, every `check_*` flag is False and `all_ok` is True, so an LLM run that did nothing shows a green "correct".

## Owns

- `dashboard/explorer.py`: `check_data_correctness` only
- `tests/dashboard/test_ac_74_zero_call_run.py` (new)
- `product.md`: one AC row

## Build

Change `full = touched is None` to `full = not touched`. Nothing else.

## Tests (`test_ac_74_*`)

- Seeded, untouched mock state with `touched=set()` and `mutation=None` gives `False`.
- The same state with `touched=None` gives `False` (the same as before).
- A completed state with `touched={"update_email"}` gives `True` (the scoped check still works).
- Control mutations (C2/C3) with the seeded state and `touched=set()` give `True`, because for controls the seeded state is the expected state. If this fails, report it in the PR rather than changing control logic.

## Done when

A zero-tool-call run can never be marked correct unless the task's expected final state is the untouched state.
