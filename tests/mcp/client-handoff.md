# MCP client hand-off

This is a setup hand-off for P4 to copy into `docs/mcp-clients.md` and verify
with fresh client installations. No client UI has been manually verified yet.

## Install and start the local mock

From the repository root, install the project and its MCP extra into the Python
environment you will use for the server:

```sh
python -m pip install -e '.[mcp]'
# Alternative when using uv:
uv pip install -e '.[mcp]'
```

In a separate terminal, start the mock API from the repository root:

```sh
.venv/bin/python -m mock_api
```

The examples below use `/ABS/PATH/TO/REPO` as the absolute repository path.
Replace it with the checkout path on your machine. The tool config and database
paths are absolute so a client launched from another working directory can
find them. The `get_user` example uses the string argument `user_id: "123"`.

## Stdio clients

The stdio server command is the absolute virtual-environment Python followed by
`-m healer.mcp_server`. Keep protocol stdout dedicated to MCP; do not wrap the
command in shell output or add stdout logging. Server diagnostics go to stderr.

### Claude Desktop

Add this `healer` entry to Claude Desktop's supported local
`claude_desktop_config.json` (`mcpServers`):

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

Restart Claude Desktop after editing its config. A local stdio process can
reach the local mock. A hosted Claude Connector cannot reach your machine's
`localhost`. For remote use, add a server through Claude's Connectors/custom
connector UI; do not use an invented `mcpServers.url` field. Connector UI and
auth support vary, and a fixed bearer-token header is not claimed to work for
all Claude connectors. No connector UI was manually verified for this hand-off.

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

## Streamable HTTP

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

### Remote deployment

Remote binding is not a substitute for a secure deployment. Bind behind a
trusted TLS-terminating reverse proxy, use a non-empty environment-provided
token, and allow only the exact request hostname and required Origin. The
allowed host is the hostname clients send (for example
`registry.example.com`), not the bind address `0.0.0.0`. Origins must be exact;
wildcards are rejected. The proxy must preserve/set the expected `Host` header
and protect the upstream listener. Bearer auth does not encrypt HTTP traffic.

Example server command with placeholders (the proxy terminates TLS):

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

## Opt-in client-config check

The default unit suite does not read an operator-supplied client config or
contact an external endpoint. It does create a temporary stdio config and
launch the repository's offline test harness. The opt-in test is not an LLM
evaluation and makes no paid model calls; it performs only the known
`get_user` request with the string argument `user_id: "123"`. It can launch a
command from the selected config, so point it only at a trusted file. URL-based
configurations contact the configured endpoint.

```sh
RUN_MCP_CLIENT_E2E=1 \
MCP_CLIENT_CONFIG=/ABS/PATH/TO/trusted-client-config.json \
MCP_CLIENT_NAME=healer \
.venv/bin/python -m pytest tests/mcp/test_client_config.py -q
```

`MCP_CLIENT_NAME` is optional and defaults to `healer`. The check supports an
`mcpServers` entry with stdio `command`/`args`/`env`, Cursor HTTP `url`, or
Windsurf HTTP `serverUrl`/`headers`. `test_ac_37_live_client_config` is gated by
`RUN_MCP_CLIENT_E2E=1`; without it, the normal test suite remains offline.
No real-client UI check or live-config run has been completed. The helper's
temporary Python log suppression and child-stderr discard are untested at the
user's request.

## Packaging and follow-up

No named `healer-mcp` command is available. P2 approval is required for this
exact `pyproject.toml` addition:

```toml
[project.scripts]
healer-mcp = "healer.mcp_server:main"
```

P4 owns copying this hand-off to `docs/mcp-clients.md` and manually checking
each client from a fresh configuration. Those checks are still outstanding.
