# External connections

`config/mcp_servers.json` is the source for upstream API/MCP connections. Store
credential environment-variable **names**, never credential values, in that
file. The gateway contract supports per-connection `auth` profiles (`none`,
`bearer`, `api_key`, `basic`) and custom secret headers through
`secret_headers: {"Header-Name": "ENV_NAME"}`; non-secret defaults belong in
`headers`. API/spec auth are separate (`spec_auth`, `spec_url`); API credentials
are not reused for a spec unless `spec_reuse_api_auth` explicitly opts in and
the origins match. MCP transport authentication applies to MCP `tools/list`,
not REST spec retrieval.

| `auth.type` | Reference fields |
|---|---|
| `none` | `{"type":"none"}` |
| `bearer` | `token_env` |
| `api_key` | `header`, `value_env` |
| `basic` | `username_env`, `password_env` |

`selected_operations` contains raw operation IDs; `secret_headers` maps each
header name to an environment-variable name. `spec_auth` uses the same auth
profile shape. `spec_reuse_api_auth` is an explicit same-origin opt-in, never a
cross-origin credential fallback.

Example shape (replace endpoint and environment-variable names for your
deployment; values below are references, not secrets):

```json
{
  "apis": [{
    "name": "example",
    "base_url": "https://api.example.invalid",
    "spec_url": "https://api.example.invalid/openapi.json",
    "selected_operations": ["getRecord"],
    "auth": {"type": "bearer", "token_env": "API_EXAMPLE_TOKEN"},
    "headers": {"Accept": "application/json"},
    "secret_headers": {"X-Client-Key": "API_EXAMPLE_CLIENT_KEY"}
  }]
}
```

**Operation selection.** With no `selected_operations`, only read-only operations
are exposed (REST `GET`/`HEAD`; GraphQL queries, never mutations). Writes need an
explicit list of operation IDs, or the explicit opt-in `"selected_operations": "*"`
(every compatible operation). This applies to OpenAPI, Swagger 2.0 and GraphQL.

**Credential env-var names.** Entries only ever hold env var names. Two rules:
no entry (file or dashboard) may reference one of the healer's own secrets
(`NVIDIA_*`, `OPENROUTER*`, `OPENCODE*`, `JEV_*`, `DASHBOARD*`, `CONNECTIONS_TOKEN`,
`OAUTH_BEARER`, `MCP_TOKEN_ENV`). Entries added or changed through the dashboard
must also use a name starting with `API_`, `MCP_` or `CONN_`; set
`HEALER_CONNECTION_ENV_ALLOW` (comma list; an item ending in `_` is a prefix,
otherwise an exact name) to replace that list. Violations return HTTP 400 naming
the rule, never a value. Names already stored in the config file stay valid when
you edit that connection.

Legacy `token_env` and `spec_path` entries remain runtime-normalized; config is
not rewritten. Use distinct environment names per account, including multiple
accounts at one provider. Presets `github@1` and `notion@1` are hints, not
guarantees; custom connections do not require presets. Consult the active
configuration contract before relying on optional fields.

Saved connection changes and environment-variable rotation activate after a
gateway restart. Until then, tools already loaded into the frozen registry
remain active; restart does not imply live config reload. Keep TLS at the
ingress and keep dashboard authentication separate from gateway inbound MCP
authentication and upstream credentials. Remote dashboard exposure requires
authenticated TLS ingress; `CONNECTIONS_TOKEN` does not authenticate the whole
dashboard. Configure the operator-controlled exact-origin
`CONNECTIONS_ALLOWED_ORIGINS` allowlist only for approved internal-service
egress; it is not dashboard authentication or browser-origin protection. Do not
expose connections management directly to arbitrary internet origins.

Treat discovery as capability-gated, not universal OpenAPI support. Unsupported
media serializers, parameter forms and diagnostics can omit an operation rather
than promise calls will work. GraphQL/gRPC expansion, OAuth refresh/token
storage, query credentials, arbitrary remote `$ref` loading, hot reload,
streaming, universal provider presets, and global dashboard authentication are
not claimed here. HTTP clients disable redirects and use an origin-scoped pinned
transport: each request resolves its host, rejects non-public addresses unless
the exact origin is in `CONNECTIONS_ALLOWED_ORIGINS`, then dials a resolved
numeric address. Credentials require HTTPS unless that exact origin is
operator-allowlisted. Keep the allowlist narrow and use controlled egress as a
second boundary.

Optional discovery-only smoke test (does not call selected operations): put a
connection config with non-empty `selected_operations` in a local file, keep
credential values in the environment/secret manager, then run
`EXTERNAL_SMOKE_CONFIG=/secure/path/connections.json .venv/bin/pytest -q tests/e2e/test_external_smoke.py`.
It probes API specs or HTTP MCP tool lists and verifies selected names only.
Use a disposable/vendor-approved account and a side-effect-free discovery
endpoint; never put real secrets in config files, tests, fixtures, logs,
prompts, or bug reports.
