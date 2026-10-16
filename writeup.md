# Write-up: Self-Healing Gateway

> PS 01: Self-Healing Tool Registries Under Runtime API Schema Drift. FR/AC ids and mutation labels (M1 to M10, C1 to C3, T-*) are in `product.md`; the end-to-end flow is in `FLOW.md`. Every number comes from `bench/report.md`: **scripted mode (fixed calls, no LLM), N = 3, 2026-10-16**. Nothing is measured with an LLM yet.

## 1. Idea

Tools are generated once from a spec or `tools/list`; upstreams change, the tools do not. A standard framework hands the raw error to the agent, which retries the same call until its cap. The gateway sits behind one MCP front door and heals instead: **deterministic code heals, an LLM is optional and confined, nothing is invented, nothing loops.** The pipeline (fingerprint, tiers 0 to 2, safety gate, verify, audit) is in `FLOW.md` section 3.

| Tier | What it does | When |
|---|---|---|
| 0 | Replays a stored fix with a matching fingerprint | A repeat of a known break |
| 1 | Code diffs the spec, builds candidates, breaks ties deterministically | A new break |
| Jev | Optional classifier: picks among tied candidates; in triage decides repair or pass-through | Only when configured |
| 2 | LLM repair agent (`repair.py`, gpt-oss-20b on NVIDIA NIM). On by default when `NVIDIA_API_KEY` is set; `--no-repair` turns it off | A refusal that triage lets through |

## 2. Facade and hot-patching

| Field | Meaning | Changes? |
|---|---|---|
| `agent_schema` | The schema exposed to the agent | **Never** (frozen at load) |
| `wire_schema` | What the upstream accepts now | Replaced on each commit |
| `active_fix_id` | The active operation list | Set on commit |
| `version` | Integer | `+1` per commit |

The agent always speaks the v1 shape; the registry translates (`request_ops` before sending, `response_ops` on the body received). Fixes are computed against the **base schema**, never stacked (FR-7.5), so an API rollback works: the diff is empty, the stale fix's structural violations show it is stale, and the base request is replayed once.

Store (SQLite, WAL; code-read columns are enum codes, arrays, refs, canonical JSON, sha256, epoch-ms): `spec_snapshots`, `fixes` (one active per fingerprint; `candidate`, `active`, `failed`, `retired`; wins and losses), `heal_events` (one row per attempt: tier, decision path, reason, `mttr_ms`, `heal_ms`, token counts, sanitized raw error), `call_events`, `rules`.

## 3. Diagnosis and candidates

**Spec diff.** The diagnoser fetches the current spec (0.5 s) or a fresh `tools/list`, canonicalizes it and diffs the operation against the base snapshot: removed and added fields, type changes, headers and security, route changes, response-schema changes. Paths use FastAPI location prefixes (`["body","target","id"]`, `["header","x-tenant-id"]`), shared by diff, error clues and fixes.

| Diff entry | Candidate rule (FR-7.2) | Op |
|---|---|---|
| Same field, type changed | Only if the value converts losslessly | `cast` |
| Field removed, required field added, shared name token or one-to-one | Move the value | `move` |
| Same, no name evidence | Every type-compatible one-to-one assignment (max 8) | several `move` candidates |
| Field removed, **optional** field added | Only with name evidence and a failure pointing at the removed field | `move` |
| Required header or security requirement | From `header_sources` config | `header` |
| Route or method change; tool renamed | A route or operation that exists in the current spec | `route` |
| Response leaves relocated | Locate in the new shape | response `move` |
| Enum values changed | Bijective mapping | `enum_map` |
| Required field with no source | No candidate | `NO_SAFE_VALUE` |

**Tie-breaker (M6-D).** With two or more candidates, score description match, parameter order and type. A candidate wins only if it strictly beats the rest; on a write tool a win must include a description match. Descriptions are untrusted and compared as tokens only.

**Jev (M6-N).** With no unique winner and Jev configured, one Choice request (1.5 s) returns an index and a confidence. On a write tool it is accepted only at >= 0.9 and with a confirming read-only `preverify` before any write. Otherwise the heal aborts `LOW_CONFIDENCE` before sending anything.

**Error-clue mode** (no spec, or `spec_mode=off`): only the structured error and the arguments. A `missing` violation is filled from an argument sharing a name token; `int_type` becomes `cast`; a missing header becomes `header` if configured. Nested or combined changes abort `NO_CANDIDATE`.

**Silent drift** (M7) is caught by declarative postchecks in `config/tools.json` (`echo`, `non_empty`); `E6` is detectable only for tools that declare them (FR-3.5).

## 4. Safe patching

| Op | Value source |
|---|---|
| `move` | The existing value at the source path |
| `cast` | The same value, lossless only (`"12a"` to int is `UNSAFE_PATCH`) |
| `header` | `{"ref":"config","key":...}` only; stores the key, never the secret |
| `route` | A route in the current spec |
| `enum_map` | A value listed in the new enum |
| `encoding` | A `Content-Type` declared in the spec |

All are interpreted by pure `ops.py`; unknown operations are rejected and none can write a literal. Gate rules, bounds and the refusal shape are in `FLOW.md`. The audit row stores a sanitized raw error: auth, cookie, API-key and token header values, configured secrets, and bearer and JWT-shaped strings are removed, and the blob is truncated (FR-5).

## 5. Threats and prevention

| Threat | Prevention |
|---|---|
| Hallucinated values | No operation writes a literal; a required value with no source is a refusal; Jev only selects among code-built fixes; tier 2 sees types, not values |
| Unsafe patches, double writes | Safety gate and replay rule |
| Guessing between equal fixes | Write-tool rule: tie-breaker with description evidence, or Jev at the write threshold plus `preverify`; residual risk is flagged by postchecks (`POSTCHECK_FAILED_AFTER_WRITE`) |
| Legitimate error mistaken for drift | `409`, missing record, value error on an unchanged spec return unchanged (`NOT_DRIFT`) |
| Prompt injection (M10) | Error text and descriptions are data matched against structure; Jev output is an index |
| Infinite retries | One attempt, one replay, deadline, `retry: false`, 60 s negative cache |
| Silent corruption | Output schema and postchecks before a fix is kept; the benchmark checks final state (False-Patch Rate) |
| Secrets in logs | Redaction; header ops store config keys |
| Bad fixes sticking | Base-schema fixes; retirement at 2 losses |

## 6. Evaluation (scripted mode, N = 3, 2026-10-16)

Source: `bench/report.md`. Jev not available (M6-N aborts `LOW_CONFIDENCE`, counted as a safe refusal). The baseline re-sends a failing call with the same arguments up to the 10-call cap.

**REST mock**

| Metric | Result |
|---|---|
| ZTAR (M1 to M5, M7, M9) | **100% (21/21)** healing; 14% (3/21) baseline |
| M6-D (tie-breaker) | 100% (3/3) healing; 0% (0/3) baseline |
| M6-N (Jev disabled) | 0% (0/3) ZTAR by design; refused `LOW_CONFIDENCE` in 3/3 runs |
| Safe-Refusal Rate (M6-N, M8) | **100% (6/6)**, no invented value sent |
| False-Patch Rate | **0% (0/24 healed runs)** |
| Tier-1 MTTR and heal_ms (mean / p50 / p95) | 32 / 25.5 / 63 ms (n = 24) |
| Tier-0 MTTR and heal_ms (mean / p50 / p95) | 4.33333 / 4 / 9 ms (n = 15) |
| Token overhead | Not measured: scripted mode makes no LLM call |

Controls: C2 (404 on an unchanged route) and C3 (invalid value on an unchanged spec) passed through as `NOT_DRIFT` in 3/3 runs. Error-only ablation (`spec_mode=off`): M1 to M4 healed, M5 and M7 aborted `NO_CANDIDATE`, M6-D, M6-N, M8 and M9 aborted `NO_SAFE_VALUE`; False-Patch Rate 0% (0/4).

**MCP drift server** (three-call task through the `Gateway`; the baseline is an upstream registry with no store)

| Mutation | Healing ZTAR | Baseline ZTAR | Tier-1 MTTR mean / p50 / p95 |
|---|---|---|---|
| M1 | 100% (3/3) | 0% (0/3) | 7 / 6 / 9 ms (n = 3) |
| M2 | 100% (3/3) | 0% (0/3) | 6.33333 / 6 / 7 ms (n = 3) |
| T-RENAME | 100% (3/3) | 0% (0/3) | 6.33333 / 6 / 7 ms (n = 3) |
| T-ENUM | 100% (3/3) | 0% (0/3) | 7 / 7 / 8 ms (n = 3) |
| T-REQUIRED, M8 | n/a | n/a | refused `NO_SAFE_VALUE` in 3/3 runs each |

Healable ZTAR 100% (12/12) against 0% (0/12) for the baseline; Safe-Refusal Rate 100% (6/6); False-Patch Rate 0% (0/12). Healthy-call overhead over MCP (`users__get_user`, n = 250 per side, in-memory): p50 0.112 ms, p95 0.802 ms, mean 0.098 ms. T-MOVE needs tier 2 and was skipped in scripted mode. Timings are wall-clock, in-process, on one machine, so they exclude network time.

## 7. Limitations

1. **No LLM-mode numbers.** `--agent llm` has not been run, so tier 2, token overhead (AC-16) and T-MOVE are unmeasured.
2. **Operation expressiveness.** Value transforms (splitting a field, unit conversion) abort unless tier 2 finds an operation-only fix; generated code is never executed.
3. **Write-tool ambiguity refuses by default** (M6-N); a wrong Jev choice that `preverify` cannot distinguish is caught only after the write.
4. **Error-clue mode** cannot fix nested or combined changes (M5, M7, M9 in the ablation). `E3` is not healed.
5. **Not covered.** gRPC and Postgres are deferred, GraphQL is loadable but not benchmarked, streaming is not covered, and real-client UI checks (Claude Desktop, Cursor, Windsurf) were not done. Single host, in-memory registry.

A refusal is a structured error by design: the agent is told the tool is unavailable (`retry: false`) and skips it. This document does not claim the agent never sees an error. Next steps: `plan.md`.

## References

Titles, authors and years were checked on each page on 2026-10-14; arXiv entries are preprints. None is a requirement.

- Serbout and Pautasso, *How Many Web APIs Evolve Following Semantic Versioning?*, ICWE 2024 (https://link.springer.com/chapter/10.1007/978-3-031-62362-2_25): only 517 of 3,075 APIs always bumped the major version on a breaking change; version numbers are not a break signal.
- Robles et al., *Exploratory Analysis of the Structural Evolution of public REST APIs*, CIbSE 2023: taxonomy of client-breaking API changes.
- Fan et al., *Skill Drift Is Contract Violation*, arXiv 2605.10990 (2026): detect, localize, repair once; violated contracts lifted one-round repair from 10% to 78%.
- Zheng, Wu and Chang, *ToolRobustBench*, arXiv 2608.23635 (2026): stage-wise failure attribution under tool perturbation.
- Liu et al., *CodeUpdateArena*, arXiv 2407.06249 (2024): models do not absorb an API update from documentation alone.
- Schmiedmayer, Bauer and Bruegge, *Reducing the Impact of Breaking Changes to Web Service Clients During Web API Evolution*, MOBILESoft 2023: closest prior art to spec diff then deterministic fix (design time).
- Yamagishi et al., *Automated Program Repair Based on REST API Specifications Using LLMs*, arXiv 2510.25148 (2025).
- Qi, Qian and Li, *Semantic Test Repair for Web Applications*, ESEC/FSE 2023.
- Sigdel and Baral, *ToolMisuseBench*, arXiv 2604.01508 (2026): budgeted retry loops as the baseline shape.
- Wang et al., *AgentNoiseBench*, arXiv 2602.11348 (ICML 2026); Guo et al., *StableToolBench*, Findings of ACL 2024: offline, deterministic replay for stable evaluation.
