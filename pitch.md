# PS 01 — Self-Healing Tool Registry: 30-Second Pitch

> Numbers below are measured in **scripted mode, N = 3** (fixed tool calls, no LLM), 2026-10-14, from `bench/report.md`. Token overhead requires an LLM-mode run and is not yet measured.

---

## The Pitch (~85 words, ~30 seconds spoken)

When an API renames a field or adds a required header, every LLM agent that calls it breaks — and keeps retrying the same broken call until it hits the iteration cap. We put a self-healing registry between the agent and the API. It detects the drift, diffs the OpenAPI spec, and builds a fix from four operations — `move`, `cast`, `header`, `route` — that cannot write a literal value. When a fix can't be built without guessing, we refuse cleanly. The agent-facing schema never changes; we hot-patch the wire translation in memory. In our scripted benchmark: **100% ZTAR** across seven healable mutations, **0% False-Patch Rate**, heals in **12 ms median**, **tier-0 repeats in 1–2 ms**.

---

## Judge Q&A Cheat Sheet

### "What is Safety by Construction?"

Fixes are built from a 4-operation DSL — `move`, `cast`, `header`, `route` — where **literal values cannot be expressed by design**. A `move` copies an existing value from the base document; a `cast` converts it losslessly (e.g., `"123"` → `123`, round-tripped back to confirm); a `header` references a config key, never the secret value; a `route` names a path that already exists in the current spec. When a required field has no source — like M8's `priority` — the system emits `NO_SAFE_VALUE` and returns `retry: false`. It does not guess `"medium"`.

**Measured:** Safe-Refusal Rate = **100% (6/6)** over M8 and M6-N (scripted, N = 3). False-Patch Rate = **0% (0/24 healed runs)** (scripted, N = 3).

---

### "How does in-memory hot-patching work?"

Each `ToolDefinition` holds two schemas:

| Field | Role | Changes? |
|---|---|---|
| `agent_schema` | The v1 schema exposed to the agent via the framework | **Never.** Frozen at load. |
| `wire_schema` | The schema the API currently accepts | Updated on commit. |
| `active_fix_id` | Points to the active operation list | Updated on commit. |
| `version` | Incremented by 1 on each commit | Updated on commit. |

When the healer commits a fix, it writes `wire_schema ← current spec` and `version + 1` **in memory** (no restart). The next call through the same tool applies the stored ops at the adapter layer before sending. The agent sees the same frozen schema and the same tool signatures — **zero extra reasoning tokens, prompt cache preserved**.

---

### "What are your numbers?"

All numbers are from `bench/report.md`, **scripted mode, N = 3**, 2026-10-14.

| Metric | Value |
|---|---|
| ZTAR (M1–M5, M7, M9) | **100% (21/21)** healing; 14% (3/21) baseline |
| M6-D (deterministic tie-breaker) | **100% (3/3)** healing; 0% baseline |
| M6-N (Jev disabled, safe refusal) | 0% healing by design; 100% Safe-Refusal Rate |
| Safe-Refusal Rate (M8 + M6-N) | **100% (6/6)** |
| False-Patch Rate | **0% (0/24)** |
| Tier-1 MTTR (mean / p50 / p95) | **12.7 / 12 / 17 ms** over 24 heals |
| Tier-0 MTTR (mean / p50 / p95) | **1.9 / 1 / 4 ms** over 15 heals |
| Token Overhead | Not yet measured — scripted mode records 0 LLM tokens; run `--agent llm` for this number |
| Baseline failure mode | Hit iteration cap (10 calls) on M1, M2, M4, M5, M6-D, M6-N, M8, M9 |

Per-mutation tier-1 MTTR p50 / p95 (ms): M1 12/13 · M2 12/12 · M3 13/17 · M4 12/12 · M5 15/17 · M6-D 12/14 · M7 12/13 · M9 13/14.

---

### "What if Jev is unavailable?"

Jev is **optional**. The decision order is: (1) deterministic tie-breaker, (2) Jev (only for 2+ candidates where the tie-breaker found no unique winner), (3) abort. All seven healable mutations (M1–M5, M7, M9) and M6-D heal without any Jev call — confirmed in our benchmark. M6-N aborts `LOW_CONFIDENCE` without sending anything (100% Safe-Refusal Rate). The live demo does not depend on Jev.

---

### "How do you avoid fixing non-drift errors?"

Two mechanisms:
1. **Value errors with an empty spec diff** (e.g., an invalid email address on an unchanged spec, scenario C3) are reclassified `BUSINESS`/`NOT_DRIFT` and returned to the agent unchanged — no fix, no replay, one audit event.
2. **404 for a missing record** (scenario C2) — the diagnoser checks the current spec; if the route still exists, the outcome is `BUSINESS`, not drift.

Both confirmed: C2 and C3 passed through correctly in 3/3 runs (scripted, N = 3).

---

### "What are the limitations?"

- Fixes are limited to what `move`, `cast`, `header`, `route` can express. Value transforms (splitting a field, unit conversion) abort cleanly — counted against ZTAR, which is the correct outcome.
- `E6` (silent-ignore drift, M7) requires a declarative postcheck in `config/tools.json`. A tool without one cannot detect that its input was silently discarded.
- Write-tool ambiguity (M6-N) refuses by default when the tie-breaker cannot decide and Jev is absent or below threshold. This is intentional: the cost of a wrong write outweighs a clean refusal.
- Error-clue mode (spec endpoint disabled) cannot repair nested or combined changes (M5, M9 abort `NO_CANDIDATE` in the ablation; M1–M4 still heal).
- Token Overhead not yet measured in LLM mode (scripted mode records 0 LLM tokens).
