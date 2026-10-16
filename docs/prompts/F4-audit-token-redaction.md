# F4: Redact the real upstream token in the audit log (security, must fix)

## Problem

`src/healer/heal.py` `_event()` stores `raw_error=sanitize(canonical.dumps(blob), self._cfg.values())`. `sanitize()` (`src/healer/store.py:39`) redacts the given secret values plus `Bearer ...`, header-shaped values and JWTs. The upstream API token, though, lives only in the httpx client headers built by `gateway._token_headers(api, env)`. It is never passed into the secrets list. If an upstream error body echoes the bare token, for example `{"received": "abc123opaque"}`, the token is written to SQLite. This breaks the "no secrets stored" invariant.

## Owns

- `src/healer/gateway.py`: pass the token values down
- `src/healer/registry.py` / `src/healer/heal.py`: only the plumbing that accepts an extra `secrets: Iterable[str]` and adds it to the `sanitize()` call. No other logic change.
- `tests/unit/test_ac_73_audit_redaction.py` (new)
- `product.md`: one AC row

## Build

1. Find how `cfg` reaches `Healer` (`Registry(..., cfg, ...)`). Add an optional keyword `secrets: tuple[str, ...] = ()` to `Registry` and `Healer` (default empty, so every existing caller still works).
2. In `gateway.api_registry`, collect the header values from `_token_headers(api, env)`. Pass both the full value (`Bearer xyz`) and the bare token (`xyz`) as `secrets`. Do the same for upstream MCP servers if their adapter holds a token (check `adapters/mcp_upstream.py`; if it does not, write that down in the PR and skip it).
3. In `_event`, call `sanitize(..., (*self._cfg.values(), *self._secrets))`.
4. Do not change `sanitize()` itself and do not change the audit schema.

## Tests (`test_ac_73_*`)

- Unit: `sanitize('{"received":"tok_abc123"}', ["tok_abc123"])` contains no `tok_abc123`.
- Integration: a mock transport returns 400 with body `{"received": "<token>"}` using a dummy token from env. Run one call through `api_registry`, then assert no `store.audit_events()` row's `raw_error` contains the token.
- Existing callers that pass no `secrets` still construct fine.

## Done when

A token configured for an upstream can never appear in `heal_events.raw_error`.
