# PS 01: Self-Healing Gateway, Pitch

> Numbers are from `bench/report.md`: **scripted mode (no LLM), N = 3, 2026-10-16**. LLM-mode numbers (token cost, the tier-2 repair agent) are not measured yet.

## The pitch (about 75 seconds spoken)

Agents call tools that were generated once from a spec. The services behind those tools keep changing: a field gets renamed, an argument becomes required, a value set shifts. The agent does not know. It sends the old call, gets an error, and tries the same call again until it hits its iteration cap.

We put a self-healing gateway between the agent and its tools. The agent talks to one MCP server. Behind it sit your upstream MCP servers and web APIs: OpenAPI, Swagger 2.0, GraphQL. When a call breaks, the gateway compares the schema the tool was built from with the schema the service has now, and builds a fix out of a few operations: move a value, convert it losslessly, add a configured header, follow a renamed route. None of those operations can write a value of its own. The gateway tries the fix once, checks the answer, and writes one audit row. If a fix would need a value nobody supplied, it refuses and says so, and the agent skips that one tool.

When the code cannot explain a break, an optional LLM repair agent can propose operations. It cannot supply values, and its proposal goes through the same gate and live check.

Measured, in scripted mode with three runs per scenario: on the REST mock the healing agent completed **21 of 21** healable runs against 3 of 21 for the baseline; on the MCP drift server **12 of 12** against 0 of 12. No healed run ended with wrong data, and the 6 of 6 unsafe runs on each side were refused.

## Judge Q&A

### What is safety by construction?

Fixes are lists of operations in which a literal value cannot be expressed. `move` copies an existing value, `cast` converts it losslessly, `header` names a config key and never the secret, `route` names a path in the current spec. When a required field has no source (M8's `priority`), the result is `NO_SAFE_VALUE` with `retry: false`; the gateway does not guess.

**Measured** (scripted, n=3): Safe-Refusal Rate 100% (6/6) on REST (M6-N, M8) and 100% (6/6) on MCP (T-REQUIRED, M8); False-Patch Rate 0% (0/24) on REST and 0% (0/12) on MCP.

### Does the agent still see errors?

Sometimes, by design. A refusal returns a structured error with `retry: false` so the agent can skip that tool. We do not claim the agent never sees an error.

### What does the LLM do, and what can it break?

Tier 2 runs only with `--repair`, after Jev triage when Jev is configured. The model (gpt-oss-20b on NVIDIA NIM) sees argument types, not values, and proposes operations from the same small language plus a target operation. Unknown operations and enum values missing from the new schema are rejected; the rest passes the safety gate and live verification. A missing-value refusal never goes to the model. **Not measured yet:** the LLM-mode benchmark has not been run, so there is no tier-2 success rate and no token figure.

### What are your numbers?

| Metric (scripted, n=3 per scenario) | REST mock | MCP drift server |
|---|---|---|
| Healable ZTAR, healing | 100% (21/21) | 100% (12/12) |
| Healable ZTAR, baseline | 14% (3/21) | 0% (0/12) |
| Safe-Refusal Rate | 100% (6/6) | 100% (6/6) |
| False-Patch Rate | 0% (0/24) | 0% (0/12) |
| Tier-1 heal time, mean / p50 / p95 | 32 / 25.5 / 63 ms (n=24) | mean 6.33333 to 7 ms per mutation (n=3 each) |
| Tier-0 (stored fix) heal time, mean / p50 / p95 | 4.33333 / 4 / 9 ms (n=15) | not measured |
| Healthy-call overhead, p50 | not measured | 0.112 ms (n=250 per side, in-memory) |
| Token overhead | not measured | not measured |

Timings are in-process wall-clock on one machine and exclude network time on the MCP side.

### What if Jev is unavailable?

Jev is optional. Order: deterministic tie-breaker, then Jev (only when two or more candidates remain tied), then abort. In the benchmark Jev was not available: M6-N aborted `LOW_CONFIDENCE` in 3/3 runs, which counts as a safe refusal.

### How do you avoid "fixing" errors that are not drift?

A value error on an unchanged spec (C3) is reclassified `NOT_DRIFT` and returned unchanged, with no fix and no replay. A 404 for a record whose route still exists (C2) is handled the same way. Both passed through in 3/3 runs.

### How do I add my own services?

List them in `config/mcp_servers.json` or use the dashboard's Connections page, which takes a URL and the name of an environment variable holding a token; token values are never stored. Claude Desktop, Cursor and Windsurf connect to the front door as described in `docs/mcp-clients.md`. Real-client UI checks have not been done yet.

### Limitations

- Fixes are limited to what the operations express; value transforms (splitting a field, unit conversion) abort unless tier 2 finds an operation-only fix.
- Silent drift needs a declarative postcheck for the tool.
- Write-tool ambiguity refuses when the tie-breaker cannot decide and Jev is absent.
- Without the spec (error-clue mode), nested or combined changes abort (M5, M7, M9; M1 to M4 still heal).
- gRPC and Postgres are deferred; GraphQL is not benchmarked; streaming responses are not covered.
