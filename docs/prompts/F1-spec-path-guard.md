# F1: Reject off-host spec paths (security, must fix)

## Problem

`src/healer/openapi_loader.py` `operations()` copies each spec `paths` key into `OperationSpec["path"]` as-is. `src/healer/adapters/rest.py` then calls `client.request(method, route["path"], ...)` on an `httpx.AsyncClient` that has `base_url` and the upstream bearer token in its default headers (`src/healer/gateway.py` `_api_client`). httpx ignores `base_url` when the path is an absolute URL, so a spec path such as `https://other.example/collect` or `//other.example/x` sends the request **and the token** to another host.

## Owns

- `src/healer/spec_paths.py` (new)
- `src/healer/openapi_loader.py`: one call in `operations()`
- `src/healer/swagger2.py`: one call where it builds paths (check whether it reuses `operations()`. If it does, no edit is needed)
- `tests/unit/test_ac_70_spec_paths.py` (new)
- `product.md`: one AC row

## Build

1. New module `spec_paths.py` with one public function:
   ```python
   def check_path(path: str) -> str:
       """AC-70: a spec path must be root-relative ('/...'), with no scheme, no '//' prefix and no backslash. Returns it unchanged or raises ValueError."""
   ```
   Reject: anything not starting with `/`; anything starting with `//`; anything containing `://`; any `\`; any control character.
2. In `operations()`, call `check_path(path)` before building the entry. Let the `ValueError` propagate: contract 2 says a `SpecSource` raises `ValueError` when the spec is unusable, so `Registry` and `Healer` already handle it.
3. Do not touch the GraphQL, gRPC or upstream MCP loaders. They do not build URL paths from the spec. Leave a one-line comment in `spec_paths.py` saying any future URL-building loader must call `check_path`.

## Tests (`test_ac_70_*`)

- `/users/{id}` passes unchanged.
- `https://evil.example/x`, `//evil.example/x`, `users`, `/a\\b` each raise `ValueError`.
- A minimal OpenAPI dict with one absolute path makes `operations()` raise `ValueError`.
- End to end: an `httpx.MockTransport` that records hosts. Load a spec with an absolute path through `openapi_source` and assert it raises and no request ever reached a foreign host.

## Done when

No spec can yield an `OperationSpec` whose path leaves `base_url`. Existing tests still pass.
