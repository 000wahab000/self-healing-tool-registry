# ZTAR addendum (give this after `_PREAMBLE.md` for every Z task)

The Z tasks finish and **prove** the 7-layer verification pipeline (`src/healer/verify.py`) and the evaluation discipline behind the Zero-Touch Adaptation Rate. Much of it already exists on `main`. **Step 1 of every Z task is to confirm the gap is still there.** If it is already done, write only the missing test and say so in the PR. Do not rewrite working code.

## Already on main (do not rebuild)

- `src/healer/verify.py`: `Verifier` with `preflight()` and `verify()`, returning per-layer rows `{layer, name, status: pass|fail|skip, detail}` for L1-L7.
- `heal_events.layers` audit field (`store.py`, `models.py`, `heal.py`).
- `bench/oracle.py`: compares what the mock received against `expected_canonical` (CORRECT / WRONG_ACCEPTED / REJECTED). False-Patch Rate is oracle-based.
- Mock mutations M1-M11, W1 (200 but not saved), U1 (cents vs dollars), D1 (side effect before a 5xx), and the request log in `mock_api/app.py`.
- `config/tools.json`: `echo` postchecks, `readback` (only `update_email`), `invariants` (only `update_email`), `idempotency_key` (only `create_ticket`).

## Current layer status

| Layer | Status | Gap a Z task closes |
|---|---|---|
| L1 Provenance | Partial | Enum targets not checked against current-spec values (Z1) |
| L2 Patched request | Partial | Unknown headers; MCP/GraphQL/gRPC requests (Z2) |
| L3 Output schema | Partial | E5 still allows a response cast; must be move/unwrap only; response-source provenance (Z3) |
| L4 Echo | Working | none |
| L5 Read-back | Working for `update_email` only | Other write tools (Z4) |
| L6 Invariants | Partial | U1 not proven through the frozen four-tool registry (Z5) |
| L7 Replay guard | Partial | MCP replay regressions (Z6) |

## Extra hard rules

- Verification is deterministic code. **No LLM call anywhere in the verify path.**
- Never mutate `ToolDefinition.agent_schema`. Patches stay op lists validated against `OPS_SCHEMA`.
- The ops language must not be able to express a literal. Every value in a patched request traces to the agent's args, a config key (`cfg[...]`), or the spec.
- A failed verification leaves the registry untouched (`active_fix`, version and wire op unchanged), writes **exactly one** audit row, and returns a structured refusal with `retry: false`.
- Never store secrets or raw header values in audit rows (keep using `store.sanitize`).
- **Write the failing test first** for every new behaviour. Write "not present" rather than guessing about code you have not read.
- Layer code lives in `src/healer/layers/` once Z0 has merged. A Z task edits only its own layer file there, plus a one-line hook if needed.
- Keep every existing test green; do not loosen an existing assertion to make yours pass.
