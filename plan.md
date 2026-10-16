# plan.md: Status and next steps

> Status as of 2026-10-17. How it works: `FLOW.md`. Requirements: `product.md`. Before ticking or claiming anything run `pytest -q` and `ruff check .`. One strict xfail (GraphQL M3) is known.

## Built

| Area | What exists |
|---|---|
| Healing core | Detection classes `E1` to `E6` and `BUSINESS`; fingerprint; spec diff and error-clue mode; deterministic candidates and tie-breaker; safety gate; `move`, `cast`, `header`, `route`, `enum_map`, `encoding` ops; one live replay and verify; one audit row per heal. Tier 0 (stored fixes, negative cache, single-flight, retirement at 2 losses), tier 1, optional Jev choice and **triage**, tier 2 repair agent (`repair.py`, on by default with `NVIDIA_API_KEY`), sibling propagation (S1), rule mining (S2), injection scenario M10 (S8) |
| MCP gateway and APIs | Front door over stdio and Streamable HTTP (`mcp_server.py`); `Gateway` over one `Registry` per upstream; upstream MCP adapter and loader; OpenAPI 3, Swagger 2.0 and GraphQL sources; `config/mcp_servers.json`; client guides in `docs/mcp-clients.md`. Deferred code exists for gRPC and a Postgres store |
| Spec watcher | `SpecWatcher` polls specs, snapshots changes, calls `Healer.precompute`; runs inside the front door |
| Dashboard | Landing page, live demo (two agents, scenario cards, editable prompt, drift buttons, "broke here" marker, cost chart), patch log with highlighted broken field, metrics, MCP view, report, connections page, guided tour with auto-play, light and dark themes |
| Benchmark | `bench/run.py` for the REST mock and the mock MCP drift server (scripted run recorded in `bench/report.md`), healthy-call overhead, MCP fixtures |
| Demo agent | `demo/mcp_agent.py` (scripted or `--llm`) over the front door with a mid-task rename; `python -m dashboard.demo` terminal demo |
| Local launcher | `start.py` starts the separate REST mock and one FastAPI dashboard/MCP process; AC-81/AC-82 focused tests and same-port HTTP smoke verified; full-suite gate remains blocked by existing failures |

## Remaining

- [ ] **Real-LLM benchmark (T1-10).** `python -m bench.run --agent llm --n 10` has not been run: no token overhead, no tier-2 or T-MOVE figures, AC-16 open. Regenerate `bench/report.md` from it.
- [ ] **Jev.** Jev through OpenRouter returns 401. An opt-in free route through OpenCode (Jev 1.13 Free, AC-48) now works: live M6-N reached tier-2 repair. Follow-up: the dashboard's M6-N correctness check still assumes a refusal.
- [ ] **Postgres store.** `store_pg.py` lacks the newer `FixStore` methods; deferred.
- [ ] **GraphQL and gRPC.** GraphQL M3 is a strict xfail; GraphQL is not benchmarked; gRPC is deferred.
- [ ] **Streaming** and long-running tool responses are not covered.
- [ ] **Dashboard auth.** Routes other than `/api/connections` writes have no auth (writes need `CONNECTIONS_TOKEN` off localhost).
- [ ] **Real-client checks** in Claude Desktop, Cursor and Windsurf (`docs/mcp-clients.md`).
- [ ] Open PR #51 "Updated Metrics" (teammate): review and merge or close.

## History

| Phase or item | PRs |
|---|---|
| Core, registry and spec v3 (phases 0 to 12: healing core, mock, agents, benchmark, dashboard) | #1, #2, #3 |
| Deploy anywhere, baseline fixes | #4, #5 |
| Contracts and ownership, re-plan around an MCP gateway | #6, #7, #12 |
| Old branches landed: S8/M10, S1, S2, X3, X4 precompute, Contract 4 | #15, #16, #17, #18, #19, #20, #22 |
| Spec watcher (T2-7) | #21 |
| AC-18 browser check; overhead and Swagger 2.0; MCP front door; GraphQL, gRPC, Postgres (deferred) | #24, #25, #26 |
| Client guides; dashboard MCP view; mock drift MCP server (T1-6) | #28, #29, #30 |
| Dashboard fixes, docs clean-ups | #23, #27, #31, #32 |
| Upstream MCP gateway (T2-1 to T2-5, T1-1 to T1-4) and review fixes | #33, #34 |
| Tier-2 repair, Jev triage | #35, #36, #45 |
| Connections page, tour, prompt editing, bugfixes | #37, #38, #39, #40 |
| Demo agent (T2-8); watcher in the front door | #41, #42 |
| MCP fixtures, overhead and drift benchmark (T1-7 to T1-9) | #43 |
| Docs rewrite around the gateway | #44 |
| Design system, themes, red-field highlights, whole-app tour, softer greys | #46, #47, #48, #49, #50, #52, #53 |

## Progress log

| Date | Note |
|---|---|
| 2026-10-13 to 14 | Phases 0 to 12 built; scripted benchmark recorded (`bench/report.md`, N = 3) |
| 2026-10-15 | Contracts between modules written; overhead and Swagger 2.0 loader; MCP front door |
| 2026-10-16 | Direction changed to an MCP gateway; upstream gateway, mock drift server, tier-2 repair with Jev triage, connections page, demo agent, MCP benchmark and docs rewrite landed; dashboard design pass |
| 2026-10-16 | Docs decluttered: stale team docs removed, `FLOW.md` added, this plan rewritten |
| 2026-10-16 | Added the unified local launcher; verified startup outside the checkout, HTTP MCP calls, REST M1 recovery visible in the shared dashboard audit, port-conflict safety and SIGTERM cleanup. Ruff passed; full pytest: 835 passed, 10 failed, 14 skipped, 1 xfailed. All 10 failures reproduce on unchanged HEAD (failure-layer checks and MCP drift healing/demo); no healing-core changes made. |
| 2026-10-17 | Combined dashboard and MCP into one FastAPI app/listener; REST mock remains separate. Verified dashboard routes, MCP initialization/list/call, real transport metadata, shared recovery audit and shutdown of both services and their upstream children. Ruff passed; full pytest: 845 passed, the same 10 baseline failures, 14 skipped, 1 xfailed. Real-client UI and container deployment checks remain outstanding. |
