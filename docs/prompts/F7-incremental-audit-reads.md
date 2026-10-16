# F7: State polls read only new audit rows (should fix, performance)

**Do after F6** (its contract test will check your new store method on both backends).

## Problem

The dashboard polls `GET /api/state` every 500 ms. `dashboard/app.py` `state()` runs `self.store.audit_events()[self.base_heal:]`, which loads **every** row in `heal_events` and slices in Python, then builds a heal summary for each one. Cost grows with history and is paid per browser per poll.

## Owns

- `src/healer/store.py`: one new `FixStore` method + SQLite implementation
- `src/healer/store_pg.py`: the same method (a real query if trivial, otherwise `NotImplementedError` per F6's pattern)
- `dashboard/app.py`: `state()` and `_impact` call sites only
- `tests/unit/test_ac_76_audit_since.py` (new); the store test suite if it lists methods
- `product.md`: one AC row

This **changes contract 3** (`FixStore`), which AGENTS.md allows only with matching tests in the same PR. Say so in the PR title.

## Build

1. `FixStore.audit_events_since(after_event_id: int) -> list[AuditEvent]` returns rows with `event_id > after_event_id` in `event_id` order, implemented with `WHERE event_id > ?`. Check that `AuditEvent` exposes `event_id`. If it does not, return `(event_id, AuditEvent)` pairs and document that.
2. In the dashboard, keep an in-memory cache: `self._audit: list[AuditEvent]` and `self._audit_last_id`. Each `state()` call appends only `audit_events_since(self._audit_last_id)`. Clear the cache in `reset()` and wherever `base_heal` is reset.
3. Cache the per-event heal summary (`self._heal(e)`) the same way, so it is computed once per event.
4. The JSON `state()` returns must be byte-identical to before for the same store contents. Do not change the response shape (other panels and the offline demo stub depend on it).

## Tests (`test_ac_76_*`)

- Store: insert 3 events, `audit_events_since(id_of_first)` returns the last 2.
- Dashboard: snapshot `state()` before and after the change for a scripted run. The outputs are equal.
- After `reset()`, `state()["heals"]` is empty, and new events still appear.
- Spy on the store: a second `state()` call with no new events issues no full-table `audit_events()` call.

## Done when

Poll cost no longer depends on total audit history, and the response is unchanged.
