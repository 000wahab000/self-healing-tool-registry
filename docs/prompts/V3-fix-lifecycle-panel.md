# V3: Fix lifecycle panel (candidates, promoted rules, spec snapshots)

**Depends on V0 and V1** (add one function to `metrics_view.py`).

## Why

The backend learns: a diagnosed fix starts as a **candidate**, gets **promoted** once verified, becomes a reusable **rule** (`record_rule_win`), and is replayed at tier 0 on the next identical break. The spec watcher (`src/healer/spec_watcher.py`) stores **spec snapshots** and calls `Healer.precompute(old, new)` to prepare fixes before any error happens. None of this is visible, yet it is the strongest answer to "hot-patch and log every patch" and "complete without downtime".

## Owns

- `dashboard/metrics_view.py`: add `fix_lifecycle(store: FixStore) -> dict` (read-only)
- `dashboard/app.py`: one route `GET /api/metrics/lifecycle`
- `dashboard/panels/lifecycle.js` (new)
- `dashboard/index.html`: one `<script>` tag + one offline-stub entry
- `tests/dashboard/test_ac_80_lifecycle.py` (new)
- `product.md`: one AC row

**Use only methods that already exist on `FixStore`** (`src/healer/store.py` around line 160). If you need a list query that does not exist (for example "all fixes" or "all snapshots"), **stop**: do not add it here. Note it in the PR as a follow-up, because adding a `FixStore` method changes contract 3 and must also update `store_pg.py` (see F6/F7). Render only what the existing methods give, and show "not available yet" for the rest.

## Build

`fix_lifecycle(store)` returns what it can, for example:
```json
{
  "rules": ["<fingerprint>", ...],
  "fixes": [{"fix_id": 1, "tool": "...", "fingerprint": "...", "state": "candidate|active|rule", "ops": [...]}],
  "snapshots": {"count": 0, "latest_ms": null},
  "unavailable": ["snapshots"]
}
```
Join with the session's audit rows (`fix_id`, `fingerprint`, `tier`) to show, per fingerprint, the first heal (tier 1) and later replays (tier 0).

Panel:
- Per fingerprint, a row of chips: `detected` → `candidate` → `verified/promoted` → `rule (N replays)`.
- Show the patch ops (rename, nest, coerce, add header) as plain text. Ops come from `ops.py`; use their names as stored, without inventing labels.
- If precompute or snapshot data is unavailable, show one muted line saying so. Do not fake it.

## Tests (`test_ac_80_*`)

- Empty store: 200 with empty lists.
- After a scripted M1 run twice: one fingerprint, the first heal at tier 1, a later replay at tier 0, and the rule listed if the store promotes it in this flow. Assert only what the store actually records.
- `fix_lifecycle` performs no writes (wrap the store in a spy and assert no write methods were called).

## Done when

A viewer can follow one break from first detection to a reusable rule, using only data the store already holds.
