# agent.md: Rules for coding agents

The project is a self-healing gateway for upstream MCP servers and OpenAPI, Swagger 2.0 and GraphQL APIs (PS 01). Read this before writing code.

## 1. Read order and authority

1. `product.md`: **what** (FR-x, AC-x). 2. `FLOW.md`: **how it works** and the file map. 3. `plan.md`: status and next steps. 4. This file: **rules** for writing code. 5. `AGENTS.md`: contracts between modules and working rules.

`product.md` wins on requirements; this file wins on coding process. If a conflict blocks you, stop and ask.

## 2. Non-negotiable invariants

Never break these, even if a test passes.

1. **Never invent values.** A patched request may only contain values from the agent's arguments, a config reference, or the current spec (route names only). No defaults, placeholders or model-generated values.
2. **Never execute model-generated code.** Fixes are operation lists interpreted by `ops.py`. A model (Jev or the tier-2 repair LLM) can only select or emit operations that validate against the operations JSON Schema.
3. **Never loop.** One heal attempt per call, one replay per heal. A failed fix is never retried. Respect the negative cache and the deadlines.
4. **Never leave a heal unlogged.** Each heal attempt writes exactly one `heal_events` row before the agent gets its result.
5. **Store machine-readable data only.** Enumerated codes, array paths, `{"ref":...}` value references, canonical JSON, epoch-ms integers. No code parses English text from the store.
6. **Never change `agent_schema`.** After load it stays frozen. Only `wire_schema`, `active_fix_id` and `version` change.
7. **No LLM in tiers 0 and 1** except the single Jev Choice call, and only with 2 or more candidates.
8. **Keep secrets out of the store, logs, test snapshots and error messages.** Header operations store config keys, never values.
9. **Compute fixes against the base schema.** Never stack one fix on another.
10. **Stay in scope.** FR and AC come first in `product.md`, then code. GraphQL and gRPC loaders, `store_pg.py` and their adapters are deferred; do not extend them.

## 3. Layout

Modules and what each does: `FLOW.md` section 7. Do not add top-level directories without updating that map. Top level: `src/healer/`, `mock_api/`, `agents/`, `bench/`, `dashboard/`, `demo/`, `config/`, `docs/`, `tests/` (`unit/`, `integration/`, `e2e/` skipped without env vars, plus per-feature folders).

## 4. Stack and conventions

- **Python and typing:** 3.11+, type hints on every function, `from __future__ import annotations`.
- **Records and enums:** stdlib `dataclasses` across module boundaries; fix operations stay plain JSON dicts validated by the operations schema. `StrEnum` for every code. Pydantic only inside `mock_api/`.
- **Minimal code (ponytail):** smallest complete change; no abstraction or "for later" code. Stdlib first, then installed dependencies; ask before adding one. A shortcut with a known limit gets a `# ponytail:` comment.
- **Async:** `httpx.AsyncClient` with explicit timeouts; no request without one.
- **Paths:** `list[str | int]` with FastAPI location prefixes (`body`, `query`, `header`, `route`). Never dotted strings.
- **Canonical JSON:** `canonical.dumps()` only (sorted keys, `(",", ":")`, UTF-8); hash with sha256.
- **Time:** `time.time_ns() // 1_000_000` for timestamps, `time.perf_counter()` for durations; inject a clock wherever deadlines are tested.
- **Dependency injection:** pass the store, Jev client, HTTP client and clock into constructors. No hidden globals, no network at import time.
- **Configuration:** secrets in `.env` (documented in `.env.example`), tool behavior in `config/tools.json`, thresholds and timeouts as named constants in `settings.py`.
- **Lint:** `ruff`. Small functions; comments only where intent is not obvious.

## 5. Testing rules

- Unit and integration tests run without network: the mock API runs in-process via `httpx.ASGITransport`; Jev is mocked with `respx`.
- Every acceptance criterion gets a test named `test_ac_XX_<short_name>`; each FR gets at least one test.
- E2E tests with a real LLM or Jev live in `tests/e2e/` and are skipped unless their env vars are set.
- Before marking work done run `pytest -q` and `ruff check .`; both must pass.
- Never weaken, skip or delete a test to make it pass. If a test is wrong, say why and fix it explicitly.
- Assert on machine-readable fields (class, reason, ops), never on message text.

## 6. Checklists

**Adding a fix operation:** add it to the operation enum and the operations JSON Schema (bump `dsl_version` if existing semantics change); implement it in `ops.py` as a pure function that writes no literal; add its provenance rule to `safety.py`; add the pattern that emits it to `candidates.py`; unit-test apply, invalid input and safety rejection; update the operations table in `product.md` section 8.

**Adding a mutation scenario:** define it as data in `mock_api/`; add its row to the mutation catalog in `product.md` section 7 (class, fix, tier, reason); add an integration test through the registry and a benchmark scenario.

**Adding a postcheck type:** add it to the postcheck enum and the `config/tools.json` schema; implement it declaratively in `contract.py` (never evaluate config as code); unit-test pass and fail.

## 7. Definition of done

The code implements the task's FRs and nothing more; tests exist and pass; `ruff` is clean; no invariant is violated; new codes are in the enums and new config keys in `.env.example` or `config/tools.json`; docs that describe changed behavior are updated in the same change.

## 8. Do not

- Call an LLM in `src/healer/` except `jev.py` and `repair.py`.
- Catch broad exceptions and continue silently; map each failure to a reason code and audit it.
- Log request bodies or headers at info level (secrets, PII).
- Tune the baseline agent to fail; it uses framework defaults and the healing agent's settings.
- Commit `.env`, `*.db` or benchmark outputs containing tokens or keys.
