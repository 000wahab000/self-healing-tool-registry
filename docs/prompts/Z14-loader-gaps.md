# Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)

Three small, independent fixes in loaders and the retry path. They are grouped because each is under ~30 lines. **Use one commit per item** so any of them can be reverted alone.

## Owns

- `src/healer/openapi_loader.py`: cycle handling in the `$ref` walker
- `src/healer/candidates.py` or `diagnose.py`: **only** the single check "refuse to patch a field whose schema came from a cut cycle"; if that check needs more than a few lines, stop and report it
- `src/healer/adapters/mcp_upstream.py`: `tools/list` pagination
- `tests/unit/test_retry.py` and any test constructing a retrier: inject jitter
- `tests/unit/test_ac_97_loader_gaps.py` (new)
- `product.md`: AC-97

## Build

1. **Cyclic `$ref`.** The walker (`openapi_loader.py` around lines 20-31) replaces a cycle with `{}`. Instead, replace it with `{"x-healer-cycle": "<ref>"}`, which is still permissive as a schema, so validation behaviour is unchanged. Candidate building must refuse (`LOW_CONFIDENCE` or the closest existing reason) any op whose target or source path passes through a node marked `x-healer-cycle`.
2. **MCP pagination.** `tools/list` returns `nextCursor`; follow it until it is absent. Add a page cap (for example 50 pages, as a named constant) to avoid an endless cursor loop, and raise `ValueError` past the cap (contract 2: a spec source raises `ValueError` when unusable). Keys stay `<server>__<tool>` (contract 7).
3. **Retry jitter.** `retry.py` already has injectable jitter. Find every test that builds a retrier without injecting it (grep the constructor) and inject a deterministic one. Add a guard test: constructing the retrier in tests without jitter raises or warns. If that would need a production change beyond a default, skip the guard and list it.

## Tests (`test_ac_97_*`)

- a self-referencing schema loads; the cycle node is marked; a candidate touching it is refused, and a candidate on a sibling field still heals
- the MCP stub returns 3 pages: all tools are loaded; an endless cursor raises `ValueError` at the cap
- the retry tests are deterministic (run them twice; the same delays are recorded)

## Done when

Cyclic schemas cannot produce a patch, MCP servers with many tools load fully, and the retry tests are deterministic.
