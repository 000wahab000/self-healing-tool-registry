## Read first

`agent.md` holds the coding rules and the non-negotiable invariants; they apply to every agent and every person. `plan.md` ("Phase 13+: two parallel tracks") holds the work items. This section adds who owns which files while two people build in parallel.

## Two-person ownership (phase 13+)

Two people work in parallel, each with their own coding agent:

- **P1, Protocols and infrastructure** (teammate; GPT with oh-my-opencode-slim). Track items `P1-*` in `plan.md`.
- **P2, Healing core** (Wahab; Claude Code). Track items `P2-*` in `plan.md`.

Find out which person you are working for before editing. If the prompt does not say, ask.

### Files each person owns

Only the owner edits these files. The other person asks the owner (issue or PR comment) for a change.

| P1 owns | P2 owns |
|---|---|
| `src/healer/adapters/` (all adapters, including per-protocol classification into `Outcome`) | `src/healer/heal.py`, `candidates.py`, `diagnose.py`, `ops.py`, `safety.py` |
| `src/healer/openapi_loader.py` and new spec loaders (`swagger2.py`, `graphql_loader.py`, `grpc_loader.py`) | `src/healer/detect.py`, `contract.py`, `fingerprint.py`, `jev.py`, `retry.py` |
| `src/healer/registry.py` (protocol dispatch, `ToolDefinition`) | `src/healer/models.py`, `canonical.py`, `settings.py` |
| New `src/healer/spec_watcher.py` | `src/healer/store.py` (SQLite schema and the `FixStore` protocol) |
| New `src/healer/store_pg.py` (Postgres backend) | `config/tools.json` |
| New mock modules: `mock_api/graphql_app.py`, `mock_api/grpc_server.py`, `mock_api/fixtures/` | `mock_api/app.py` (REST mutations, M10 and new-op scenarios) |
| New tests under `tests/protocols/` and `tests/store_pg/` | `bench/`, `agents/`, `dashboard/` |

Shared files: append only, and only in your own subsection.

- `product.md`: each person writes the FR and AC for their own items before writing code (`agent.md` invariant 10). AC numbers are reserved per person: **P1 uses AC-30 to AC-39, P2 uses AC-40 to AC-49.** AC-28 and AC-29 stay unassigned for MVP close-out.
- `plan.md`: tick your own `P1-*` / `P2-*` boxes and add your own progress-log rows.
- `pyproject.toml`: P1 adds dependencies only as new optional groups (`graphql`, `grpc`, `postgres`). P2 owns the existing groups.
- `tests/conftest.py` and `tests/integration/conftest.py`: P2 owns them; P1 adds fixtures in their own `conftest.py` under `tests/protocols/`.

### Contracts between the tracks

These interfaces are how the tracks meet. Changing one needs a PR that both people approve.

1. **`OperationSpec` (`models.py`).** Every spec loader (OpenAPI 3, Swagger 2.0, GraphQL, gRPC) returns `dict[str, OperationSpec]` keyed by tool name. Diagnosis and candidate building only ever read this shape, so a new protocol heals without changes to P2's files.
2. **`SpecSource` (`models.py`).** An async callable that returns a `LoadedSpec` (raw spec, operations, spec hash) and raises `httpx.HTTPError` or `ValueError` when the spec is unavailable. `Registry` and `Healer` take one; the default is `openapi_loader.openapi_source(client)`. P1 adds new sources; P2 never imports a loader directly.
3. **`FixStore` (`store.py`).** The store methods that the registry and the healer call. P1's Postgres backend implements it and must pass the same store tests as SQLite. When P2 adds a table (rules, proposals), P2 adds its methods to `FixStore` and their tests in the same PR, and P1 then adds them to Postgres.
4. **Spec-change hook (P1-4 to P2-8).** P1's watcher calls `Healer.precompute(old: LoadedSpec, new: LoadedSpec)`. P2 implements it. The watcher must work (record snapshots) before P2's side exists.
5. **New fix operations.** If a protocol needs an operation that `ops.py` lacks (for example a GraphQL selection rename), P1 asks P2; P2 adds it to the operations schema with tests.

### Working rules

- Branches: `p1/<item>-<slug>` and `p2/<item>-<slug>`, one plan item per PR, cut from and merged back to `main`.
- Before opening a PR: rebase on `main`, then `pytest -q` and `ruff check .` must both be clean.
- The other person reviews every PR that touches a contract above or a shared file.
- Every acceptance criterion gets a `test_ac_XX_*` test (`agent.md` §5).
- No item may break the invariants in `agent.md` §2: no invented values, no executed model code, no loops, one audit row per heal, frozen `agent_schema`, no secrets stored, False-Patch Rate 0.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
