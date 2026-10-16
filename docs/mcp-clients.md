# Connecting MCP clients to the healer gateway

The healer MCP server (the front door) exposes the registry's tools to any MCP
client. A client that lists `tools` sees the same frozen `agent_schema` the
registry serves, and every call goes through `Registry.call()`, so drift is
healed behind the client without a schema change or a reconnect.

This guide is derived from the setup hand-off in
[`tests/mcp/client-handoff.md`](../tests/mcp/client-handoff.md) and stays
consistent with it. Real-client UI checks are outstanding; the snippets below
are the configurations that server supports, not a claim that every client
release has been tried by hand.

Replace `/ABS/PATH/TO/REPO` with the checkout path on your machine, and the
interpreter path with your platform's:
`/ABS/PATH/TO/REPO/.venv/bin/python` on macOS/Linux, or
`/ABS/PATH/TO/REPO\.venv\Scripts\python.exe` on Windows. Absolute paths let a
client launched from another working directory find the tools file and database.

## 1. Install and start the mock API

From the repository root, install the project and its MCP extra into the
environment you will run the server with:

```sh
python -m pip install -e '.[mcp]'
# Alternative when using uv:
uv pip install -e '.[mcp]'
```

In a separate terminal, start the mock API from the repository root:

```sh
.venv/bin/python -m mock_api
```

When you point the gateway at a different API instead, change `--base-url` and
`--spec-path` accordingly.

## 2. The stdio server command

The stdio server is the absolute virtual-environment Python followed by
`-m healer.mcp_server`. Keep protocol stdout dedicated to MCP: do not wrap the
command in shell output or add stdout logging. Server diagnostics go to stderr.

```sh
.venv/bin/python -m healer.mcp_server \
  --base-url http://127.0.0.1:8000 \
  --spec-path /openapi.json \
  --tools /ABS/PATH/TO/REPO/config/tools.json \
  --db /ABS/PATH/TO/REPO/healer.db
```

### Claude Desktop (stdio)

Add this `healer` entry to Claude Desktop's local `claude_desktop_config.json`
under `mcpServers`:

```json
{
  "mcpServers": {
    "healer": {
      "command": "/ABS/PATH/TO/REPO/.venv/bin/python",
      "args": [
        "-m", "healer.mcp_server",
        "--base-url", "http://127.0.0.1:8000",
        "--spec-path", "/openapi.json",
        "--tools", "/ABS/PATH/TO/REPO/config/tools.json",
        "--db", "/ABS/PATH/TO/REPO/healer.db"
      ]
    }
  }
}
```

Restart Claude Desktop after editing its config. A local stdio process can reach
the local mock. A hosted Claude Connector cannot reach your machine's
`localhost`: for remote use, add a server through Claude's Connectors/custom
connector UI. Do not use an invented `mcpServers.url` field; connector UI and
auth support vary, and a fixed bearer-token header is not claimed to work for
every Claude connector.

### Cursor (stdio)

Add the entry to the project's `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "healer": {
      "command": "/ABS/PATH/TO/REPO/.venv/bin/python",
      "args": [
        "-m", "healer.mcp_server",
        "--base-url", "http://127.0.0.1:8000",
        "--spec-path", "/openapi.json",
        "--tools", "/ABS/PATH/TO/REPO/config/tools.json",
        "--db", "/ABS/PATH/TO/REPO/healer.db"
      ]
    }
  }
}
```

### Windsurf (stdio)

Add the entry to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "healer": {
      "command": "/ABS/PATH/TO/REPO/.venv/bin/python",
      "args": [
        "-m", "healer.mcp_server",
        "--base-url", "http://127.0.0.1:8000",
        "--spec-path", "/openapi.json",
        "--tools", "/ABS/PATH/TO/REPO/config/tools.json",
        "--db", "/ABS/PATH/TO/REPO/healer.db"
      ]
    }
  }
}
```

## 3. Streamable HTTP

Start the mock as above, then run the MCP server in another terminal. HTTP
defaults to `127.0.0.1:8001/mcp`; a bearer token is optional for loopback use.

```sh
.venv/bin/python -m healer.mcp_server \
  --transport http \
  --base-url http://127.0.0.1:8000 \
  --tools /ABS/PATH/TO/REPO/config/tools.json \
  --db /ABS/PATH/TO/REPO/healer.db
```

For token-protected loopback use, set `HEALER_MCP_TOKEN` in the process
environment through a secret manager before launching, then add
`--token-env HEALER_MCP_TOKEN`. Pass the environment variable's **name**, never
its value, on the command line. Do not put token values in these config files,
source control, or logs.

### Cursor (HTTP)

For the local server without an optional token, use Cursor's Streamable HTTP
`url` form in `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "healer": {
      "url": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

### Windsurf (HTTP)

For the local server without an optional token, use Windsurf's `serverUrl` form
in `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "healer": {
      "serverUrl": "http://127.0.0.1:8001/mcp"
    }
  }
}
```

If a local server uses `--token-env`, configure that client's `Authorization`
header using its supported secret mechanism; do not save a real bearer value in
the config snippet. Client config schemas can differ by version.

## 4. Remote deployment

Remote binding is not a substitute for a secure deployment. Bind behind a
trusted TLS-terminating reverse proxy, use a non-empty environment-provided
token, and allow only the exact request hostname and required Origin. The
allowed host is the hostname clients send (for example `registry.example.com`),
not the bind address `0.0.0.0`. Origins must be exact; wildcards are rejected.
The proxy must preserve/set the expected `Host` header and protect the upstream
listener. Bearer auth does not encrypt HTTP traffic.

```sh
.venv/bin/python -m healer.mcp_server \
  --transport http --host 0.0.0.0 --port 8001 \
  --base-url http://127.0.0.1:8000 \
  --tools /ABS/PATH/TO/REPO/config/tools.json \
  --db /ABS/PATH/TO/REPO/healer.db \
  --token-env HEALER_MCP_TOKEN \
  --allowed-host registry.example.com \
  --allowed-origin https://registry.example.com
```

Cursor's remote `url` is `https://registry.example.com/mcp`; Windsurf's remote
`serverUrl` is the same URL. Configure each client's bearer header through an
appropriate secret facility only if that client supports the required auth
mode. Keep one server process and its registry alive behind the proxy: the MCP
sessions share that in-memory registry. Do not assume Claude's hosted connector
accepts this fixed bearer scheme.

## 5. Adding an upstream server

The gateway forwards calls to the upstream servers listed in
`config/mcp_servers.json` (T2-3, owned by T2-PS1). Each entry names the server,
its transport (stdio or Streamable HTTP) and a command or URL. The file stores
only the **name** of the environment variable that holds a token, never the
token value itself. Upstream tools are exposed to clients namespaced as
`<server>__<tool>`, so a tool called `get_user` on a server named `crm` appears
as `crm__get_user`.

The exact field schema of `config/mcp_servers.json` is defined by T2-3. Until it
lands, treat the invariants above (one entry per server, transport, command or
URL, environment-variable name only) as the contract, and keep tokens in the
environment.

## 6. Known limits and outstanding checks

- No named `healer-mcp` console command is available. It needs this exact
  `pyproject.toml` addition, which requires T1-PS1 approval:

  ```toml
  [project.scripts]
  healer-mcp = "healer.mcp_server:main"
  ```

- Real-client UI checks have not been performed. The configurations above match
  the server's accepted options, but no client release was launched and verified
  by hand.
- Optional offline check: the default test suite does not read an
  operator-supplied client config or contact an external endpoint. To run the
  opt-in check against a trusted config, use `RUN_MCP_CLIENT_E2E=1`,
  `MCP_CLIENT_CONFIG` and optional `MCP_CLIENT_NAME` (default `healer`) with
  `tests/mcp/test_client_config.py`. It makes only the known `get_user` request
  with the string argument `user_id: "123"` and no paid model calls. It can
  launch a command from the selected config, so point it only at a trusted file.
