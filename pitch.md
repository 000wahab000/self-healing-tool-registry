# PS 01: Self-Healing Gateway, 30-Second Pitch

> Numbers are from `bench/report.md`: **scripted mode (no LLM), N = 3, 2026-10-14, REST mock**. Token overhead and the MCP path are not yet measured.

## The pitch (about 30 seconds spoken)

When an API or an MCP server renames a field or adds a required argument, every agent that calls it breaks and keeps retrying the same broken call until its iteration cap. We put a self-healing gateway between the agent and its tools. It detects the drift, diffs the current schema against the original, and builds a fix from a few operations (`move`, `cast`, `header`, `route`) that cannot write a literal value. If a fix cannot be built without guessing, it refuses cleanly and the agent skips that one tool. The agent-facing schema never changes; we hot-patch the translation in memory. In our scripted REST benchmark: **100% ZTAR** across seven healable mutations, **0% False-Patch Rate**, heals in **49 ms median**, **tier-0 repeats in 4 ms median**.

## Judge Q&A

### What is safety by construction?

Fixes are lists of operations in which literal values cannot be expressed. `move` copies an existing value; `cast` converts it losslessly (`"123"` to `123`, round-tripped to confirm); `header` references a config key, never the secret; `route` names a path that exists in the current spec. When a required field has no source (M8's `priority`), the system returns `NO_SAFE_VALUE` and `retry: false`. It does not guess `"medium"`.

**Measured:** Safe-Refusal Rate 100% (6/6, M8 and M6-N); False-Patch Rate 0% (0/24 healed runs).

### How does in-memory hot-patching work?

Each tool keeps a frozen `agent_schema` (the v1 shape the agent sees) and a `wire_schema` (what the upstream accepts now). On commit the registry sets `wire_schema` to the current schema and bumps `version`, in memory, with no restart. The next call applies the stored operations before sending. The agent sees the same tool signatures throughout. (Token effect: not yet measured.)

### What are your numbers?

| Metric | Value |
|---|---|
| ZTAR (M1 to M5, M7, M9) | **100% (21/21)** healing; 14% (3/21) baseline |
| M6-D (tie-breaker) | **100% (3/3)** healing; 0% baseline |
| M6-N (Jev disabled) | 0% healing by design; refused safely |
| Safe-Refusal Rate (M8 + M6-N) | **100% (6/6)** |
| False-Patch Rate | **0% (0/24)** |
| Tier-1 MTTR (mean / p50 / p95) | **50.7 / 49 / 66 ms** over 24 heals |
| Tier-0 MTTR (mean / p50 / p95) | **4.7 / 4 / 8 ms** over 15 heals |
| Token Overhead | Not measured: scripted mode records 0 LLM tokens |
| Baseline failure mode | Hit the 10-call cap on M1, M2, M4, M5, M6-D, M6-N, M8, M9, C2, C3 |

Timings are wall-clock on a laptop. Per-mutation tier-1 MTTR p50 / p95 (ms): M1 47/48, M2 45/66, M3 47/49, M4 52/53, M5 57/69, M6-D 47/51, M7 52/53, M9 50/58.

### What if Jev is unavailable?

Jev is optional. Order: deterministic tie-breaker, then Jev (only for 2 or more candidates with no unique winner), then abort. M1 to M5, M7, M9 and M6-D heal without a Jev call in the benchmark. M6-N aborts `LOW_CONFIDENCE` before sending anything. The demo does not depend on Jev.

### How do you avoid "fixing" errors that are not drift?

A value error on an unchanged spec (C3, an invalid email) is reclassified `BUSINESS` / `NOT_DRIFT` and returned unchanged: no fix, no replay. A `404` for a record whose route still exists in the spec (C2) is `BUSINESS`. Both passed through correctly in 3/3 runs.

### Does it work for MCP servers?

That is the product direction: the gateway fronts upstream MCP servers and REST APIs with one healing core. The front door is built; the upstream MCP client, MCP drift benchmark and MCP overhead numbers are in progress (`plan.md`, Phase 13+) and are not in the figures above.

### Limitations

- Fixes are limited to what the operations express; value transforms (splitting a field, unit conversion) abort cleanly and count against ZTAR.
- Silent drift (M7) needs a declarative postcheck in `config/tools.json`.
- Write-tool ambiguity (M6-N) refuses when the tie-breaker cannot decide and Jev is absent or below threshold.
- Without the spec (error-clue mode), nested or combined changes abort (M5, M9; M1 to M4 still heal).
- Token Overhead is not yet measured in LLM mode.
