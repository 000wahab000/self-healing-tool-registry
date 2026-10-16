# F3: Connections routes use the shared auth module (security, must fix)

**Depends on F2 being merged** (`dashboard/auth.py` must exist).

## Problem

`dashboard/connections.py` `is_remote()` decides "local" from `request.client.host in ("127.0.0.1", "::1")` and the absence of forwarding headers. A reverse proxy on the same host that does not add `X-Forwarded-For` makes every public request look local, so anyone can rewrite `config/mcp_servers.json` or make the server probe internal URLs without `CONNECTIONS_TOKEN`.

## Owns

- `dashboard/connections.py`
- `tests/dashboard/test_ac_72_connections_auth.py` (new)
- existing connections tests, only where they assert the old IP-based behaviour
- `product.md`: one AC row

## Build

1. Delete `is_remote()` and the local `require_write()`. Use `dashboard.auth.require_write` for every write and outbound-test route in `connections.py`.
2. Backward compatibility: if `CONNECTIONS_TOKEN` is set and `DASHBOARD_TOKEN` is not, accept `CONNECTIONS_TOKEN` as the token for these routes. Implement this as a small helper inside `connections.py` that calls into `auth.py` and adds no logic of its own to `auth.py`. Add a deprecation comment.
3. Read-only connections routes stay as they are.

## Tests (`test_ac_72_*`)

- In token mode, a request from client `127.0.0.1` with no forwarding header and no token gives 401 or 403 (this is the bug).
- In off mode, a write works.
- `CONNECTIONS_TOKEN`-only configuration still authorizes.
- Grep-style test: `connections.py` no longer references `request.client`.

## Done when

The client address plays no part in any authorization decision anywhere in `dashboard/`.
