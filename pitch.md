# PS 01: Self-Healing Gateway, Pitch

> Numbers are from `bench/report.md`: scripted mode (no LLM), N = 3, 2026-10-16. LLM-mode numbers (token cost, tier-2 repair) are not measured yet.

## The pitch (about 75 seconds spoken)

Agents call tools that were generated once from a spec. The services behind those tools keep changing: a field is renamed, an argument becomes required, a value set shifts. The agent does not know. It sends the old call, gets an error, and tries the same call again until it hits its iteration cap.

We put a self-healing gateway between the agent and its tools. The agent talks to one MCP server. Behind it sit your upstream MCP servers and web APIs: OpenAPI, Swagger 2.0, GraphQL. When a call breaks, the gateway compares the schema the tool was built from with the schema the service has now, and builds a fix from a few operations: move a value, convert it losslessly, add a configured header, follow a renamed route. None of them can write a value of its own. The gateway tries the fix once, checks the answer, and writes one audit row. If a fix would need a value nobody supplied, it refuses and says so, and the agent skips that one tool.

When the code cannot explain a break, an optional LLM repair agent can propose operations. It cannot supply values, and its proposal goes through the same gate and live check.

Measured, three runs per scenario: on the REST mock the healing agent completed **21 of 21** healable runs against 3 of 21 for the baseline; on the MCP drift server **12 of 12** against 0 of 12. No healed run ended with wrong data, and the unsafe runs were refused every time.

## Judge Q&A

**What is safety by construction?** Fixes are operation lists in which a literal value cannot be expressed. When a required field has no source (M8's `priority`), the result is `NO_SAFE_VALUE` with `retry: false`; the gateway does not guess. Safe-Refusal Rate 100% (6/6) on REST and on MCP; False-Patch Rate 0% (0/24 REST, 0/12 MCP).

**Does the agent still see errors?** Sometimes, by design. A refusal returns a structured error with `retry: false` so the agent can skip that tool. We do not claim the agent never sees an error.

**What does the LLM do, and what can it break?** Tier 2 sees argument types, not values, and proposes operations from the same small language. Unknown operations are rejected and the rest passes the safety gate and live verification. A missing-value refusal never goes to the model. There is no tier-2 success rate or token figure yet.

**How fast is it?** Tier-1 heal on the REST mock: 32 / 25.5 / 63 ms (mean / p50 / p95, n=24); tier 0 (stored fix): 4.33333 / 4 / 9 ms (n=15). Healthy-call overhead over MCP: p50 0.112 ms. In-process wall-clock, no network time.

**What if Jev is unavailable?** It is optional. Order: deterministic tie-breaker, then Jev (only for ties), then abort. Without Jev, M6-N aborted `LOW_CONFIDENCE` in 3/3 runs, a safe refusal.

**How do you avoid "fixing" errors that are not drift?** A value error on an unchanged spec (C3) and a 404 on a route that still exists (C2) are returned unchanged as `NOT_DRIFT`; both passed through in 3/3 runs.

**How do I add my own services?** List them in `config/mcp_servers.json` or use the dashboard's Connections page (URL plus the name of an environment variable holding a token; token values are never stored). Client setup: `docs/mcp-clients.md`.

**Limitations and design:** `writeup.md`. What is next: `plan.md`.
