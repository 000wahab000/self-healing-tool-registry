# Z2: L2 validates unknown headers and non-REST patched requests

**Depends on Z0.**

## Problem

L2 validates the REST body and query of the patched request against the freshly fetched spec. Two gaps remain:
1. **Headers:** a patched request can carry a header the current spec does not declare, and L2 does not flag it.
2. **Other protocols:** for MCP, GraphQL and gRPC, L2 returns `skip / protocol_schema`, so a patched request there is never schema-checked.

## Owns

- `src/healer/layers/l2_request.py`
- `tests/unit/test_ac_83_l2_request.py` (new)
- `product.md`: AC-83

Do not edit the adapters or loaders. L2 reads the `OperationSpec` they already produce (contract 1). If an adapter does not put enough into `OperationSpec` (for example a GraphQL variables schema), stop for that protocol, keep `skip` with a precise detail, and list it in the PR.

## Build

1. **Headers.** Allowed header names = the spec's `in: header` params + security scheme headers + the `header_sources` keys in `config/tools.json` + `Idempotency-Key` when the tool config enables it. Compare case-insensitively. Any other header on the patched doc fails L2 with `detail="unknown_header:<name>"`. Never put header **values** in `detail`.
2. **MCP upstream:** `OperationSpec` keyed `<server>__<tool>` is built from `inputSchema` (contract 7). Validate the patched arguments with the same strict-schema helper (`_strict`) used for REST bodies.
3. **GraphQL / gRPC:** do the same if their `OperationSpec.body_schema` is populated; otherwise keep `skip` with `detail="protocol_schema:<protocol>:no_schema"`.

## Tests (`test_ac_83_*`)

- REST: a declared header passes; an undeclared `X-Debug` fails with `unknown_header:x-debug`, and the value never appears in the row.
- `X-Tenant-Id` from `header_sources` passes (the M5 path).
- MCP: patched args missing a required field fail L2; valid args pass.
- GraphQL/gRPC: assert pass/fail if a schema exists, or the exact skip detail if it does not.
- Integration: the existing M5 and MCP heal tests stay green.

## Done when

No patched request leaves with an undeclared header, and every protocol that exposes a schema is validated at L2.
