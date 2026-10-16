# G1: Every MCP heal aborts with UNSAFE_PATCH (regression, do first)

## Problem

Since "Part 1 of ZTAR" (#63), every healable MCP drift is refused. Running `run.mcp_bench(1)` on `main` gives:

```
MCP-M1        ABORTED UNSAFE_PATCH
MCP-M2        ABORTED UNSAFE_PATCH
MCP-T-RENAME  ABORTED UNSAFE_PATCH
MCP-T-ENUM    ABORTED UNSAFE_PATCH
MCP-T-REQUIRED ABORTED NO_SAFE_VALUE   (expected)
MCP-M8        ABORTED NO_SAFE_VALUE    (expected)
```

The audit `layers` field is `None` for these rows, so the refusal happens **before** or **outside** the `Verifier`, most likely in `Verifier.preflight` (the L7 replay rule: an MCP tool with no `idempotent` config is treated as a non-idempotent write) or in `safety.py`. Failing test: `tests/t1ps2/test_ac_54_mcp_bench.py::test_ac_54_mcp_scenarios`.

## Owns

- `src/healer/verify.py` and/or `src/healer/safety.py`: the smallest change that fixes the classification
- `src/healer/heal.py`: only if the `layers` rows are not written for preflight refusals (they must be, so the audit shows which layer refused)
- `tests/unit/test_g1_mcp_preflight.py` (new)

Do **not** edit `tests/t1ps2/test_ac_54_mcp_bench.py`. It is the spec.

## Steps

1. Reproduce:
   ```python
   import asyncio; from bench import run
   rows = asyncio.run(run.mcp_bench(1))
   print([(r["scenario"], [(h["outcome"], h.get("reason"), h.get("layers")) for h in r["heals"]]) for r in rows if r["agent"] == "healing"])
   ```
2. Find exactly where `UNSAFE_PATCH` is raised for MCP-M1 (add a temporary breakpoint or log, and remove it after). Write the file:line and the condition in the PR.
3. Fix the rule, not the test:
   - If L7 treats the MCP tool as non-idempotent only because config is missing, read idempotency from what the MCP adapter already knows (the tool's `annotations.readOnlyHint` / `idempotentHint` if kept), else from the error class: a JSON-RPC `-32602` invalid-params rejection is a pre-execution rejection and therefore replay-safe. Never treat "unknown" as safe for anything else.
   - If L2 rejects because MCP has no request schema, it must `skip` (protocol_schema), not fail.
4. Make sure a preflight refusal still writes `layers` (no more `None`).

## Done when

- `test_ac_54_mcp_scenarios` passes
- MCP-T-REQUIRED and MCP-M8 still refuse with `NO_SAFE_VALUE`
- the new unit test pins the rule: MCP + `-32602` gives replay allowed; MCP + internal error gives refused
- `pytest -q` and `ruff check .` show no new failures
