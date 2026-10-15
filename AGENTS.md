## Read first

`agent.md` holds the coding rules and the non-negotiable invariants; they apply to every agent and every person. `plan.md` ("Phase 13+: four parallel tracks") holds the work items. The section below says who owns which files while four people build in parallel.

## Four-person ownership (phase 13+)

Four people work in parallel, each with their own coding agent. P1 and P2 have the strongest setups, so they own the critical and heavy work. P3 and P4 take bounded, well-tested items.

| Person | Setup | Track |
|---|---|---|
| **P1** | Teammate; GPT with oh-my-opencode-slim | MCP server (the product's front door), GraphQL, gRPC, Postgres |
| **P2** | Wahab; Claude Code | Healing core, the real-LLM benchmark, review of every contract change |
| **P3** | OpenCode free tier, no plugins or extra setup | Small isolated items: Swagger 2.0 converter, healthy-call overhead benchmark, plan hygiene |
| **P4** | Antigravity with Gemini Flash (Gemini Pro via Jio) | Browser demo checks, dashboard, docs and pitch, spec watcher, LangGraph migration |

Find out which person you are working for before editing. If the prompt does not say, ask. Kickoff prompts for each person are in `team-prompts.md`.

### Files each person owns

Only the owner edits these files. Anyone else asks the owner (issue or PR comment) for a change.

| Owner | Files |
|---|---|
| P1 | `src/healer/mcp_server.py` (new), `src/healer/adapters/`, `src/healer/openapi_loader.py`, new protocol loaders (`graphql_loader.py`, `grpc_loader.py`), `src/healer/registry.py`, `src/healer/store_pg.py` (new), `mock_api/graphql_app.py`, `mock_api/grpc_server.py`, `tests/mcp/`, `tests/protocols/`, `tests/store_pg/` |
| P2 | `src/healer/heal.py`, `candidates.py`, `diagnose.py`, `ops.py`, `safety.py`, `detect.py`, `contract.py`, `fingerprint.py`, `jev.py`, `retry.py`, `models.py`, `canonical.py`, `settings.py`, `store.py`; `config/tools.json`; `mock_api/app.py`; `bench/` (except `bench/overhead.py`); `agents/` until P2-0 is done |
| P3 | `src/healer/swagger2.py` (new), `mock_api/fixtures/` (new), `bench/overhead.py` (new), `tests/p3/` (new); checkbox and progress-log fixes in `plan.md` phases 0 to 12 |
| P4 | `src/healer/spec_watcher.py` (new), `dashboard/`, `README.md`, `pitch.md`, `writeup.md`, `docs/` (new, MCP client setup guides), `tests/p4/` (new); `agents/` after P2-0 is done |

Shared files: append only, and only in your own subsection.

- `product.md`: each person writes the FR and AC for their own items before writing code (`agent.md` invariant 10). Reserved AC numbers: **P1 AC-30 to AC-39, P2 AC-40 to AC-49, P3 AC-28 and AC-50 to AC-54, P4 AC-55 to AC-59.** AC-29 stays unassigned.
- `plan.md`: tick your own `P1-*` to `P4-*` boxes and add your own progress-log rows.
- `pyproject.toml`: P1 adds new optional groups only (`mcp`, `graphql`, `grpc`, `postgres`). Any other change goes through P2.
- `tests/conftest.py` and `tests/integration/conftest.py`: P2 owns them. Everyone else adds fixtures in a `conftest.py` inside their own test folder.

### Contracts between the tracks

These interfaces are how the tracks meet. Changing one needs a PR that P2 and the affected owner approve.

1. **`OperationSpec` (`models.py`).** Every spec loader (OpenAPI 3, Swagger 2.0, GraphQL, gRPC, upstream MCP) returns `dict[str, OperationSpec]` keyed by tool name. Diagnosis and candidate building only ever read this shape.
2. **`SpecSource` (`models.py`).** An async callable that returns a `LoadedSpec` and raises `httpx.HTTPError` or `ValueError` when the spec is unavailable. `Registry` and `Healer` take one; the default is `openapi_loader.openapi_source(client)`.
3. **`FixStore` (`store.py`).** P1's Postgres backend implements it and must pass the same store tests as SQLite. When P2 adds a table, P2 adds its methods to `FixStore` and their tests in the same PR.
4. **`Registry.tools()` and `Registry.call()`.** The MCP server exposes exactly these: `tools/list` comes from `tools()` (the frozen `agent_schema`), `tools/call` goes through `call()`. The MCP server adds no healing logic of its own.
5. **Spec-change hook.** P4's watcher calls `Healer.precompute(old: LoadedSpec, new: LoadedSpec)`. P2 implements it. The watcher must work (record snapshots) before P2's side exists.
6. **New fix operations.** If a protocol needs an operation `ops.py` lacks, ask P2.

### Working rules

- Branches: `p1/<item>-<slug>` to `p4/<item>-<slug>`, one plan item per PR, cut from and merged back to `main`.
- Before opening a PR: rebase on `main`, then `pytest -q` and `ruff check .` must both be clean. The repo has no CI, so this local run is the gate.
- **Review:** P2 reviews every PR from P3 and P4, and every PR that touches a contract or a shared file. P1 reviews P2's contract changes.
- Every acceptance criterion gets a `test_ac_XX_*` test (`agent.md` §5).
- No item may break the invariants in `agent.md` §2: no invented values, no executed model code, no loops, one audit row per heal, frozen `agent_schema`, no secrets stored, False-Patch Rate 0.
- **Claims:** README, pitch and demo copy use only numbers measured in `bench/report.md`. Do not claim a heal time, "the agent never sees an error" (refusals such as M8 return a structured error by design) or any other result that has not been measured.
- **Secrets:** never paste `.env` contents or API keys into any agent prompt. This matters most for P3: some free OpenCode models keep or train on prompts.
- **Running tests from a git worktree:** the shared `.venv` imports `src/` from the main checkout. Set `PYTHONPATH` to the worktree's `src` and root first.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
