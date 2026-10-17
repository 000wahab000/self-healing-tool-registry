# Z6: L7 replay guard for upstream MCP tools

**Depends on Z0.**

## Problem

For REST, a non-idempotent write is replayed after a heal only if the original failure was a pre-execution rejection (400/422 with no side effect) or an idempotency key is configured. Otherwise the call is refused. For **upstream MCP** tools this guard has known regressions. An MCP error does not map to HTTP 400/422, so the "qualifying rejection" test can misfire. A non-idempotent MCP tool could be replayed after it already had a side effect (the D1 pattern).

## Owns

- `src/healer/layers/l7_replay.py`
- `tests/unit/test_ac_89_l7_mcp_replay.py` (new)
- `tests/mcp/`: one integration test file if the drift server supports a side-effect mutation (contract 8: use its documented mutation API, do not modify it)
- `product.md`: AC-89

## Build

1. Read L7 and `safety.py`'s replay rule. Write in the PR exactly what counts as a "qualifying rejection" today.
2. MCP qualifying rejection = JSON-RPC error `-32602` (invalid params), or a tool result with `isError: true` whose content shows an input-validation failure **as classified by the existing detect/diagnose code**. Do not add new message parsing. Any other MCP failure (internal error, timeout, `isError` without validation evidence) is not a qualifying rejection.
3. Idempotent unless proven otherwise? **No.** An MCP tool is non-idempotent unless its config says `"idempotent": true` or the upstream tool annotations say `idempotentHint: true` / `readOnlyHint: true` (read them only if the adapter already keeps them; if not, list it as a follow-up).
4. Non-idempotent MCP tool without a qualifying rejection: refuse with `retry: false`.

## Tests (`test_ac_89_*`)

- MCP non-idempotent tool, `-32602`: replay allowed
- MCP non-idempotent tool, `-32603` / internal or timeout: refused, no replay sent (spy on the adapter)
- MCP tool marked idempotent: replay allowed
- REST rules unchanged (re-run the existing L7 tests)

## Done when

No non-idempotent MCP call is replayed unless the upstream provably rejected it before executing.
