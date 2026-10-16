# ZTAR: bare-minimum path

The smallest set of tasks that closes every **partial** and **missing** ZTAR item. It reuses the Z prompts with their scope cut down. Give an agent `_PREAMBLE.md` + `_ZTAR_RULES.md` + the task file + **the "Minimum scope" lines for that task below** (they override the task file where they differ).

## Step 0: make main green (blocking)

`main` fails 3 tests and **every MCP heal aborts** (MCP ZTAR is 0 today). Fix this first, or every later task starts red.

| Order | Prompt | Fixes |
|---|---|---|
| 1 | `G1-mcp-unsafe-patch.md` | `test_ac_54_mcp_scenarios`; all MCP heals refused with UNSAFE_PATCH |
| 2 | `G2-w1-readback.md` | `test_w1_...`; W1 never triggers a heal, so L5 never runs |
| 3 | `G3-d1-replay.md` | `test_d1_...`; 503 after a saved write is retried |

G1, G2 and G3 touch different files and can run in parallel. After all three, re-run `python -m bench.run --agent scripted --n 3` and commit the new `bench/report.md`, since the current one may predate #63.

## Step 1: partial layers (one agent, sequential, no Z0)

**Skip Z0** (the layer-package refactor). It exists only so many agents can work in parallel. On the minimum path, one agent edits `verify.py` directly, in this order:

| Order | Task | Minimum scope |
|---|---|---|
| 4 | Z1 L1 enum | Only "value must be in the current spec enum". Skip the enum value-mapping op. |
| 5 | Z2 L2 request | Only unknown **headers** + MCP `inputSchema` validation. GraphQL/gRPC: keep `skip` with a detail string. |
| 6 | Z3 L3 move-only | Only "a response-side cast fails L3". Skip the response-source provenance check unless it is under 15 lines. |
| 7 | Z4 L5 read-back | Only `set_manager` (same route as `update_email`). `create_ticket` is covered by G3's no-replay rule; add it only if `key_from_response` is under 20 lines. |
| 8 | Z5 L6 U1 | Only the investigation + PR note. U1 hits `/payments`, which none of the four tools uses, so it cannot be proven without changing the frozen tool set. Mark it "not provable" in the report. |
| 9 | Z6 L7 MCP | Covered by G1 if G1 implemented the `-32602` rule. Otherwise do only that rule. |

## Step 2: missing pieces (parallel, independent)

| Order | Task | Minimum scope |
|---|---|---|
| 10 | Z7 catalog | Only the catalog module + replacing the bench constants. Skip `correct_handling_rate`. |
| 11 | Z8 evidence tie | Only "a tie with Jev disabled gives a refusal" + its test. Skip adding the `evidence` field if the tie-breaker already orders spec diff first. |
| 12 | Z11 fault matrix | Only the HTTP-date `Retry-After` parse + matrix rows for 429 (both forms), 503, malformed JSON and C3. |
| 13 | Z12 Wilson | Only `wilson()` + CIs on ZTAR, Safe-Refusal and False-Patch. Keep `--n` at 10 unless the bench takes under 2 minutes at 30. |
| 14 | Z13 robustness | Both items (they are small). |
| 15 | Z14 loader gaps | Only MCP pagination. Cyclic `$ref` and jitter are nice-to-have. |
| 16 | Z10 fuzz | Only rename + type-change + header primitives, single-primitive cases, `--seed --n`. |

## Step 3: prove it

| Order | Task | Minimum scope |
|---|---|---|
| 17 | Z9 proof matrix | All seven rows; U1 is `skip` with the reason from step 8. |
| 18 | Z15 report | Layer table, ZTAR + CIs (hand-written and fuzz), Safe-Refusal, False-Patch, MTTR p50/p95, "which layer caught what". |

## Not on the minimum path

Z0 (refactor), the response-source provenance check, `create_ticket` read-back, correct-handling rate, cyclic `$ref` marking, the jitter guard, and multi-primitive fuzz. All of them are in their full Z prompts for later.
