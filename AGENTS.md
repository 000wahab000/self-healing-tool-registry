## Read first

`agent.md`: coding rules and invariants. `FLOW.md`: how the system works end to end. `plan.md`: status and next steps. `product.md`: requirements (FR/AC ids). Single maintainer (Wahab); the earlier machine and team split is history. Reserved AC ranges are historical: new ACs continue from the highest number used in `product.md` (AC-69).

## Contracts between modules

Changing one needs a deliberate PR that updates its tests.

1. **`OperationSpec` (`models.py`).** Every spec loader (OpenAPI 3, Swagger 2.0, upstream MCP, GraphQL, gRPC) returns `dict[str, OperationSpec]` keyed by tool name. Diagnosis and candidate building only read this shape.
2. **`SpecSource` (`models.py`).** An async callable that returns a `LoadedSpec` and raises `httpx.HTTPError` or `ValueError` when the spec is unavailable. `Registry` and `Healer` take one; the default is `openapi_loader.openapi_source(client)`.
3. **`FixStore` (`store.py`).** Any other backend implements it and must pass the same store tests as SQLite. A new table adds its methods to `FixStore` and their tests in the same PR.
4. **`Registry.tools()` and `Registry.call()`.** The MCP server exposes exactly these: `tools/list` comes from `tools()` (the frozen `agent_schema`), `tools/call` goes through `call()`. The MCP server adds no healing logic.
5. **Spec-change hook.** The watcher calls `Healer.precompute(old: LoadedSpec, new: LoadedSpec)`. The watcher records snapshots even when the healer lacks the hook.
6. **New fix operations.** A protocol that needs an operation `ops.py` lacks gets it added there (see `agent.md` section 6), never in an adapter.
7. **Upstream MCP mapping (`adapters/mcp_upstream.py`).** An upstream tool maps to an `OperationSpec` keyed `<server>__<tool>`, built only from its `inputSchema`. A call returns the shared `Outcome`, keeping the JSON-RPC error code and message, the `isError` flag and its content.
8. **Mock drift control (`mock_api/mcp_drift_server.py`).** A documented way to apply, list and reset mutations by name (the same names as the REST mock where one exists). The dashboard, demo and tests only call it.

## Working rules

- Branches are cut from and merged back to `main`, one change per PR.
- Before opening a PR: rebase on `main`, then `pytest -q` and `ruff check .` must both be clean. The repo has no CI, so this local run is the gate. One strict xfail (GraphQL M3) is known.
- Every acceptance criterion gets a `test_ac_XX_*` test (`agent.md` section 5).
- No change may break the invariants in `agent.md` section 2: no invented values, no executed model code, no loops, one audit row per heal, frozen `agent_schema`, no secrets stored, False-Patch Rate 0.
- **Claims:** README, pitch and demo copy use only numbers measured in `bench/report.md`. Do not claim a heal time, "the agent never sees an error" (refusals such as M8 return a structured error by design) or any result that has not been measured.
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
