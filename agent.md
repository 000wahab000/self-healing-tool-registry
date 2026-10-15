# agent.md: Instructions for AI Coding Agents

You are building **PS 01: Self-Healing Tool Registries Under Runtime API Schema Drift**. Read this file before writing any code.

## 1. Read order and authority

1. `product.md` defines **what** to build: features, requirements (FR-x) and acceptance criteria (AC-x).
2. `technical-approach.md` defines **how**: components, data model, algorithms, stack.
3. `plan.md` defines the **order**: phases and tasks. Work only on the current phase.
4. This file defines the **rules** for writing code in this repo.

When documents conflict, `product.md` wins on requirements and this file wins on coding process. If a conflict blocks you, stop and ask. Do not guess.

## 2. Non-negotiable invariants

Never break these. Any change that would break one is wrong, even if a test passes.

1. **Never invent values.** A patched request may only contain values from the agent's arguments, a config reference, or the current API spec (route names only). There are no defaults, no placeholders, and no model-generated values.
2. **Never execute model-generated code.** Fixes are operation lists interpreted by `ops.py`. A model (Jev or the STRETCH repair LLM) can only select or emit operations that validate against the operations JSON Schema.
3. **Never loop.** Each call gets one heal attempt and each heal gets one replay. A failed fix is never retried. Respect the negative cache and the deadlines.
4. **Never leave a heal unlogged.** Each heal attempt writes exactly one `heal_events` row before the agent receives its result.
5. **Store machine-readable data only.** Use enumerated codes, array paths, `{"ref":...}` value references, canonical JSON and epoch-ms integers. No code may parse English text from the store.
6. **Never change `agent_schema`.** After load, the agent-facing tool schema stays frozen. Only `wire_schema`, `active_fix_id` and `version` change.
7. **No LLM in tiers 0 and 1** except the single Jev Choice call, and only when there are 2 or more candidates.
8. **Keep secrets out of the store, logs, test snapshots and error messages.** Header operations store config keys, never values.
9. **Compute fixes against the base schema.** Never stack one fix on another.
10. **Stay in scope.** Build only what `product.md` lists. STRETCH work (S1–S5) starts only after the plan's phase 11 gate passes.

## 3. Repository layout

```
.
├── agent.md  product.md  technical-approach.md  proposed-solution.md  plan.md
├── pyproject.toml
├── .env.example                 # every env var, no real values
├── config/
│   └── tools.json               # per tool: idempotent, postchecks; global: header_sources
├── src/healer/
│   ├── models.py                # enums + records: ErrorClass, Reason, Outcome, Violation, Op, Fix, AuditEvent
│   ├── canonical.py             # canonical JSON, sha256, path helpers
│   ├── ops.py                   # Op Interpreter (pure)
│   ├── safety.py                # Safety Gate
│   ├── openapi_loader.py        # fetch, $ref resolution, canonicalize, hash
│   ├── registry.py              # ToolDefinition, Registry.call()
│   ├── adapters/rest.py         # request document, send, normalize
│   ├── detect.py                # classification + violations
│   ├── contract.py              # output schema + postchecks
│   ├── fingerprint.py
│   ├── diagnose.py              # spec diff + error-clue mode
│   ├── candidates.py            # Candidate Builder
│   ├── jev.py                   # Jev Client
│   ├── heal.py                  # Heal Controller
│   ├── retry.py                 # E1 policy
│   ├── store.py                 # SQLite + in-memory caches
│   └── metrics.py               # ZTAR, MTTR, Token Overhead from store/results
├── mock_api/                    # FastAPI app, mutations as data, admin endpoints
├── agents/                      # healing_agent.py, baseline_agent.py, shared prompt/tools
├── bench/                       # scenario runner, report writer
├── dashboard/                   # FastAPI + static HTML live demo
├── docs/                        # user guides (MCP client setup)
└── tests/
    ├── unit/
    ├── integration/             # registry + in-process mock API
    └── e2e/                     # real LLM/Jev; skipped unless env vars set
```

Do not add top-level directories without updating this file.

## 4. Stack and conventions

- **Python and typing:** Python 3.11+. Type hints on every function. `from __future__ import annotations`.
- **Records and enums:** stdlib `dataclasses` for records that cross module boundaries; fix operations stay plain JSON dicts validated by the operations JSON Schema. `StrEnum` for every code (classes, reasons, outcomes, tiers, op names, sides, kinds). Pydantic is used only inside `mock_api/`.
- **Minimal code (ponytail):** smallest complete change. No abstraction, option, wrapper or "for later" code the plan does not require. Stdlib first, then installed dependencies. A shortcut with a known limit gets a `# ponytail:` comment naming the limit.
- **Async:** `httpx.AsyncClient` with explicit timeouts. No requests without a timeout.
- **Paths:** `list[str | int]` with FastAPI location prefixes (`body`, `query`, `header`, `route`). Never use dotted strings.
- **Canonical JSON:** use `canonical.dumps()` only (sorted keys, `(",", ":")` separators, UTF-8). Hash with sha256.
- **Time:** use `time.time_ns() // 1_000_000` for timestamps and `time.perf_counter()` for durations. Inject a clock wherever deadlines are tested.
- **Dependency injection:** pass the store, Jev client, HTTP client and clock into constructors. No hidden globals, and no network calls at import time.
- **Configuration:**
  - secrets in `.env`, loaded at startup and documented in `.env.example`,
  - tool behavior in `config/tools.json`,
  - thresholds and timeouts as named constants in one settings module, matching the values in `product.md`.
- **Lint and format:** `ruff`. Keep functions small. Add comments only where intent is not obvious.
- **Dependencies:** use only the libraries in `technical-approach.md` §2. Ask before adding another.

## 5. Testing rules

- Unit and integration tests run **without network**:
  - the mock API runs in-process via `httpx.ASGITransport`,
  - Jev is mocked with `respx`.
- Every acceptance criterion gets a test named `test_ac_XX_<short_name>`. Each FR you implement gets at least one test.
- E2E tests that use the real LLM or Jev live in `tests/e2e/` and are skipped unless their env vars are set.
- Before marking any task done, run `pytest -q` and `ruff check .`. Both must pass.
- Never weaken, skip or delete a test to make it pass. If a test is wrong, explain why and fix it explicitly.
- Assert on machine-readable fields (class, reason, ops), never on message text.

## 6. Checklists

### Adding a fix operation

1. Add it to the operation enum and the operations JSON Schema, and bump `dsl_version` if the semantics of existing operations change.
2. Implement it in `ops.py` as a pure function. It must not write literal values.
3. Add its provenance rule to `safety.py`.
4. Add the pattern that emits it to `candidates.py`.
5. Add unit tests for apply, invalid input and the safety rejection.
6. Update the operations table in `product.md` §8 and in `technical-approach.md`.

### Adding a mutation scenario

1. Define it as data in `mock_api/` (id, affected operation, spec change, behavior).
2. Add its row to the mutation catalog in `product.md` §7, with the expected class, fix, tier and reason.
3. Add an integration test through the registry and add it to the benchmark scenario list.

### Adding a postcheck type

1. Add it to the postcheck enum and the `config/tools.json` schema.
2. Implement it in `contract.py` as a declarative check. It must not evaluate code from config.
3. Add unit tests for pass and fail.

## 7. Definition of done (per task)

- The code implements the task's FRs and nothing more.
- Tests exist and pass. `ruff` is clean.
- No invariant from §2 is violated.
- New codes are added to the enums, and new config keys to `.env.example` or `config/tools.json`.
- The plan checkbox is ticked. If behavior differs from the docs, flag it and update the docs in the same change, after asking.

## 8. Do not

- Do not call an LLM anywhere in `src/healer/` except `jev.py` (and the STRETCH repair module, once approved).
- Do not catch broad exceptions and continue silently. Map each failure to a reason code and audit it.
- Do not log request bodies or headers at info level. They may contain secrets or PII.
- Do not tune the baseline agent to fail. It uses framework defaults with the same settings as the healing agent.
- Do not start GraphQL or gRPC work before the phase-11 gate.
- Do not commit `.env`, `*.db` or benchmark outputs containing tokens or keys.
