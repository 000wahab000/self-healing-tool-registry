# Stress test summary (2026-10-17)

Raw data and harnesses: worktree `stress-test`, folder `bench/stress/` (`tier2/REPORT.md`, `tier2/results.json`; `prism/` harness only, no results).

## 1. Tier-2 repair agent (live LLM)

Model `openai/gpt-oss-20b` on NVIDIA NIM. Jev returned 401, so a stub Jev answered only the tier-2 triage question in the main arms.

| Measure | Result |
|---|---|
| Scenario invocations | 44 (28 at the shipped 30 s deadline, 16 at 100 s) |
| Model answered in time | 6 of 44 (14%) |
| Healed | 5 of 44 (2 of 28 at 30 s, 3 of 16 at 100 s) |
| Answered proposals that were correct | 6 of 6 |
| False patches | 0 of 92 rows and 0 of 12 direct calls |
| Safe refusals (M8, new required field) | 4 of 4, all at tier 1 with no LLM call |
| Latency of answered calls | p50 30.9 s, p95 49.7 s (n=6) |
| Tokens per answered heal | 822 to 972 (mean 876) |
| Stored fix reused at tier 0 | 3 of 3 checked |
| M11 with tier 2 off vs on | 0/1 vs 3/14 |
| M6-N with tier 2 off vs on | safe refusal vs 2/9 |

The 11% heal rate mostly measures the endpoint timing out, not model quality. N is small and comes from one day on one degraded endpoint.

## 2. MCP server in Claude Code

`claude -p` (Haiku) used only the healer tools over `http://127.0.0.1:8097/mcp` with M1 drift live. It looked up user 123 and changed the email; both calls succeeded. `get_user` was healed at tier 1 (spec diff). The MCP tab logged both calls.

## 3. Prism drifting external API

Stopped by request before it produced results. The harness (`api_v1.yaml`, drift driver, MCP load client) is kept for a later run.

## 4. Failure cases

| # | Failure | Cause |
|---|---|---|
| 1 | Tier 2 can never recover a write tool that has no `preverify` route, even with a correct proposal (H13: right ops in 17.7 s, still aborted) | `src/healer/heal.py:515`, `:580-581` |
| 2 | Tier 1 reports VERIFY_FAILED for `update_email` after a `user_id` rename (H1, H2, H8), even though the write landed (PATCH 200). Triage then skips it, so tier 2 cannot rescue it | readback reuses the renamed key on `/users/lookup`, `heal.py:353`, `:359` |
| 3 | Repair deadline too short for the endpoint: 25 of 28 calls got no answer at 30 s, 13 of 16 at 100 s | `src/healer/repair.py:43`, `:77` |
| 4 | Without Jev only NO_CANDIDATE reaches tier 2, so only M11 is eligible | `heal.py:473-474`, `:489` |
| 5 | The model over-refuses: `operation: null` although a valid operation was listed (D2, D3, D4) | model behaviour |
| 6 | Two same-typed fields with swapped names (H10) are invisible to every tier. The result is a business 404, not a false patch | detection limit |
| 7 | A repair HTTP error may put the fingerprint in the 60 s negative cache (seen only in code; every failure observed was DEADLINE) | `heal.py:506-507`, `:70-82` |
| 8 | The bench's `task_done` ignores `get_user`, so an M11 run whose `get_user` failed still reads as done | `bench/run.py` |
| 9 | On Windows the gateway hangs at startup with the default config: upstream stdio servers start as plain `python`, not the venv | `config/mcp_servers.json` |
| 10 | Both Jev routes return 401 with the current keys | credentials |
