# Read this before the task file

You are working on **API Healer**: a self-healing tool layer that sits between an LLM agent and upstream APIs (REST/OpenAPI, Swagger 2.0, GraphQL, upstream MCP). When an upstream schema drifts (renamed field, type change, nesting, new required header), it diagnoses the diff, hot-patches the tool call in memory, logs one audit row per heal in SQLite, and refuses rather than invents a value it cannot derive. A FastAPI demo dashboard (`dashboard/`) shows a healing agent and a baseline agent side by side against a mock API (`mock_api/`).

## Before you write code

1. Read `AGENTS.md`, `agent.md` (rules and invariants, especially section 2), and only the files your task names. Do not explore the whole repo.
2. If `graphify-out/graph.json` exists, use `graphify query "<question>"` instead of broad grep.

## Hard rules

- **Edit only the files your task lists under "Owns".** If you believe another file must change, stop and write down why in the PR description instead of editing it.
- Keep the module boundary: new logic goes in the new module the task names, and existing files get only a small call into it.
- Never break the `agent.md` section 2 invariants: no invented values, no executing model-written code, no retry loops, one audit row per heal, frozen `agent_schema`, no secrets stored, False-Patch Rate 0.
- Do not change contracts 1-8 in `AGENTS.md` unless your task explicitly says so.
- Never read, print or paste `.env` contents or API keys.
- Do not claim numbers that are not in `bench/report.md`.
- Match the surrounding code style: type hints, short docstrings that cite FR/AC ids, no new dependencies.

## Tests

- Every task has an acceptance criterion id (AC-xx). Add a test named `test_ac_xx_<short_name>` in the test file the task names.
- Also add a one-line row for the AC to `product.md` after AC-69 (or after the highest AC already present). If another task already used your number, take the next free one and note it in the PR.
- Running from a git worktree: the shared `.venv` imports `src/` from the main checkout, so set the path first:
  - PowerShell: `$env:PYTHONPATH = "$PWD\src;$PWD"`
  - bash: `export PYTHONPATH="$PWD/src:$PWD"`
- Gate before the PR (the repo has no CI): `pytest -q` and `ruff check .` must both be clean. One strict xfail (GraphQL M3) is expected.

## Git

- Branch from `main`: `fix/<task-id>-<slug>` or `feat/<task-id>-<slug>`. Rebase on `main` before the PR.
- One task per PR. In the PR body, list: what changed, the AC id, the test command output summary, and anything you could not verify.
- After the code changes, run `graphify update .`.

## Done means

All "Done when" checks in the task pass, tests and ruff are clean, and you edited no file outside "Owns".
