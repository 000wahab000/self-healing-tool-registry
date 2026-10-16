## Read first

`agent.md` holds the coding rules and the non-negotiable invariants; they apply to every agent and every person. `plan.md` ("Phase 13+: MCP gateway, two teams on four machines") holds the work items and the product direction. The section below says who owns which files while four machines build in parallel.

## Two teams, four machines (phase 13+)

Two people, each running two machines with their own coding agent. Each machine owns one track and its files, so the four agents never edit the same file.

| Machine | Person | Track |
|---|---|---|
| **T1-PS1** | Team 1: Wahab | Healing core for MCP drift (detect, diagnose, heal, ops, store), landing the old P2 branch |
| **T1-PS2** | Team 1: Wahab | Mock drift MCP server, fixtures, benchmark and real-LLM evidence |
| **T2-PS1** | Team 2: teammate | Upstream MCP client and loader, server config, registry dispatch, front-door MCP server |
| **T2-PS2** | Team 2: teammate | Spec watcher, demo agent, dashboard, docs, README and pitch |

Find out which machine you are working for before editing. If the prompt does not say, ask. Kickoff prompts for each machine are in `team-prompts.md`.

### Files each machine owns

Only the owner edits these files. Anyone else asks the owner (issue or PR comment) for a change.

| Owner | Files |
|---|---|
| T1-PS1 | `src/healer/heal.py`, `candidates.py`, `diagnose.py`, `ops.py`, `safety.py`, `detect.py`, `contract.py`, `fingerprint.py`, `jev.py`, `retry.py`, `models.py`, `canonical.py`, `settings.py`, `store.py`; `config/tools.json`; `tests/conftest.py`, `tests/integration/`, `tests/unit/`, `tests/t1ps1/` (new) |
| T1-PS2 | `mock_api/` (including `mcp_drift_server.py` and `fixtures/`), `bench/`, `agents/`, `src/healer/swagger2.py`, `tests/mock_api/`, `tests/agents/`, `tests/bench/`, `tests/e2e/`, `tests/p3/`, `tests/t1ps2/` (new) |
| T2-PS1 | `src/healer/mcp_server.py`, `src/healer/adapters/` (including `mcp_upstream.py`), `src/healer/openapi_loader.py`, `src/healer/registry.py`, `config/mcp_servers.json` (new), deferred protocol files (`graphql_loader.py`, `grpc_loader.py`, `store_pg.py`), `tests/mcp/`, `tests/protocols/`, `tests/t2ps1/` (new) |
| T2-PS2 | `src/healer/spec_watcher.py` (new), `demo/` (new), `dashboard/`, `README.md`, `pitch.md`, `writeup.md`, `docs/`, `tests/dashboard/`, `tests/p4/`, `tests/t2ps2/` (new) |

Shared files: append only, and only in your own subsection.

- `product.md`: each machine writes the FR and AC for its own items before writing code (`agent.md` invariant 10), inside its own `## Track <machine>` section only. Reserved AC numbers: **T2-PS1 AC-30 to AC-39, T1-PS1 AC-40 to AC-49, T1-PS2 AC-50 to AC-54, T2-PS2 AC-55 to AC-59.** AC-28 is P3's healthy-call overhead AC (done); AC-29 stays unassigned.
- `plan.md`: tick your own `T1-*` or `T2-*` boxes, and add progress-log rows only to your own machine's table ("Progress log: T1-PS1" and so on).
- `pyproject.toml`: T2-PS1 adds new optional groups only (`mcp`, `graphql`, `grpc`, `postgres`). Any other change goes through T1-PS1.
- `tests/conftest.py` and `tests/integration/conftest.py`: T1-PS1 owns them. Everyone else adds fixtures in a `conftest.py` inside their own test folder.

### Contracts between the tracks

These interfaces are how the tracks meet. Changing one needs a PR that Wahab and the affected owner approve.

1. **`OperationSpec` (`models.py`).** Every spec loader (OpenAPI 3, Swagger 2.0, upstream MCP, later GraphQL and gRPC) returns `dict[str, OperationSpec]` keyed by tool name. Diagnosis and candidate building only ever read this shape.
2. **`SpecSource` (`models.py`).** An async callable that returns a `LoadedSpec` and raises `httpx.HTTPError` or `ValueError` when the spec is unavailable. `Registry` and `Healer` take one; the default is `openapi_loader.openapi_source(client)`.
3. **`FixStore` (`store.py`).** Any other backend implements it and must pass the same store tests as SQLite. When T1-PS1 adds a table, it adds the methods to `FixStore` and their tests in the same PR.
4. **`Registry.tools()` and `Registry.call()`.** The MCP server exposes exactly these: `tools/list` comes from `tools()` (the frozen `agent_schema`), `tools/call` goes through `call()`. The MCP server adds no healing logic of its own.
5. **Spec-change hook.** T2-PS2's watcher calls `Healer.precompute(old: LoadedSpec, new: LoadedSpec)`. T1-PS1 implements it. The watcher must work (record snapshots) before the healer side exists.
6. **New fix operations.** If a protocol needs an operation `ops.py` lacks, ask T1-PS1.
7. **Upstream MCP mapping (`adapters/mcp_upstream.py`).** An upstream tool maps to an `OperationSpec` keyed `<server>__<tool>`, built only from its `inputSchema`. A call returns the shared `Outcome`, keeping the JSON-RPC error code and message, the `isError` flag and its content. Changes need T1-PS1 and T2-PS1 approval.
8. **Mock drift control (`mock_api/mcp_drift_server.py`).** A documented way to apply, list and reset mutations by name (the same names as the REST mock where one exists). T1-PS2 owns it; the dashboard, demo and tests only call it.

### Working rules

- Branches: `t1-ps1/<item>-<slug>`, `t1-ps2/…`, `t2-ps1/…`, `t2-ps2/…`, one plan item per PR, cut from and merged back to `main`.
- Before opening a PR: rebase on `main`, then `pytest -q` and `ruff check .` must both be clean. The repo has no CI, so this local run is the gate.
- **Review:** Wahab reviews every contract change and every shared-file change. The teammate reviews Team 1 PRs that touch a contract or a Team 2 file.
- Every acceptance criterion gets a `test_ac_XX_*` test (`agent.md` §5).
- No item may break the invariants in `agent.md` §2: no invented values, no executed model code, no loops, one audit row per heal, frozen `agent_schema`, no secrets stored, False-Patch Rate 0.
- **Claims:** README, pitch and demo copy use only numbers measured in `bench/report.md`. Do not claim a heal time, "the agent never sees an error" (refusals such as M8 return a structured error by design) or any other result that has not been measured.
- **Secrets:** never paste `.env` contents or API keys into any agent prompt. Upstream server tokens live in env vars; `config/mcp_servers.json` stores only the variable name.
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
