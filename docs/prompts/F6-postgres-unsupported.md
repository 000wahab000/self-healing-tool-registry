# F6: Make the Postgres store fail loudly instead of mid-heal (should fix)

## Problem

`src/healer/store_pg.py` `PostgresStore` is missing five `FixStore` methods: `get_candidate`, `get_rules`, `is_rule`, `promote`, `record_rule_win`. Healing calls `get_candidate` on a first-time heal, so it crashes with `AttributeError` mid-request. Its tests skip without `PG_DSN`, so the normal suite never notices. `plan.md` already lists it as deferred.

This task does **not** implement Postgres. It makes the gap explicit and impossible to hit silently, and leaves a clean slot for whoever implements it later.

## Owns

- `src/healer/store_pg.py`
- `tests/store_pg/` (add a test that runs **without** `PG_DSN`)
- `tests/unit/test_ac_75_store_contract.py` (new)
- `product.md`: one AC row

## Build

1. Add the five missing methods to `PostgresStore`, each raising `NotImplementedError("PostgresStore: <method> not implemented yet, see plan.md (deferred)")`. Match the signatures in `FixStore` (`src/healer/store.py` around line 160) exactly.
2. Add a module docstring line: `UNSUPPORTED: incomplete FixStore; do not use in production.`
3. In `PostgresStore.__init__`, emit `warnings.warn(..., RuntimeWarning)` once.
4. Contract test without a database: for every public method name on `FixStore`, assert that `PostgresStore` has it, that its signature matches (`inspect.signature`), and that it is not inherited from `Protocol` as a stub. This test must run without `PG_DSN`. It is what keeps future `FixStore` additions (for example from F7) from silently missing a backend.

## Done when

The contract test fails whenever `FixStore` gains a method that `PostgresStore` lacks, and calling an unimplemented method raises a clear `NotImplementedError` rather than an `AttributeError`.
