# Static orders API drift demo

Prism 5.14.2 HTTP behavior and registry query-rename recovery were checked
locally. Antigravity UI behavior and two-machine networking have not been
verified.

This is a static Prism mock, not an order database: it always returns the same
illustrative `ORD-1001` response and keeps no state. The dashboard's built-in
mutation buttons control a different mock and do not change these files.
The `/openapi.json` route is explicitly mocked by each spec's embedded example;
it is not a Prism built-in. When editing a spec, keep that inline example in
sync with the outer document; the published copy omits its own
`/openapi.json` response example to avoid recursive embedding.

## Machine A: API mock

From the repository root, allow inbound TCP/4010 from the private demo network
only, then start v1:

```sh
npx --yes @stoplight/prism-cli@5.14.2 mock -h 0.0.0.0 -p 4010 demo/prism/openapi-v1.json
```

Do not add Prism's `--errors` option: invalid requests can become 500 responses
instead of the healable 422 response. This uses Prism's static mode (no `-d`).
From Machine B, replace `PRISM_LAN_IP` below with Machine A's private LAN IP:

```sh
curl -sS http://PRISM_LAN_IP:4010/openapi.json | python -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])'
curl -i 'http://PRISM_LAN_IP:4010/orders?order_id=ORD-1001'
curl -i 'http://PRISM_LAN_IP:4010/orders?order_reference=ORD-1001'
```

The first command prints `1.0.0`; v1 accepts `order_id` and returns the
illustrative order, while `order_reference` is rejected with 422.

## Machine B: gateway and MCP client

Merge this entry into the existing `config/mcp_servers.json` `apis` array; do
not replace other entries:

```json
{
  "name": "orders",
  "kind": "openapi",
  "base_url": "http://PRISM_LAN_IP:4010",
  "spec_url": "http://PRISM_LAN_IP:4010/openapi.json",
  "selected_operations": ["get_order"],
  "auth": {"type": "none"}
}
```

For this private-LAN HTTP endpoint, set and persist the exact origin before
starting the gateway (substitute the same IP):

```sh
export CONNECTIONS_ALLOWED_ORIGINS=http://PRISM_LAN_IP:4010
```

This allowlist authorizes private-address egress; keep it limited to the exact
origin and the private demo network. See
[`../../docs/external-connections.md`](../../docs/external-connections.md) for
the connection security and configuration contract.

Start the local dashboard/gateway entry point:

```sh
.venv/bin/python start.py --port 8080
```

If the gateway is already running, add the API entry above and restart it once
while Prism is serving v1, before the initial Antigravity connection. In
Antigravity, open **Manage MCP servers > View raw config** and merge this entry
into its existing `mcpServers` object (do not overwrite other servers):

```json
{
  "mcpServers": {
    "healer": {
      "serverUrl": "http://127.0.0.1:8080/mcp"
    }
  }
}
```

Use the UI's raw config view; no particular config-file path is assumed.
Connect/reload the healer while Prism serves v1. Ask it to look up `ORD-1001`
using `orders__get_order`/the order lookup tool.

## Change the contract

On Machine A, stop Prism and restart it on the same address and port with v2:

```sh
npx --yes @stoplight/prism-cli@5.14.2 mock -h 0.0.0.0 -p 4010 demo/prism/openapi-v2.json
```

Check the version and both parameter names from Machine B:

```sh
curl -sS http://PRISM_LAN_IP:4010/openapi.json | python -c 'import json,sys; s=json.load(sys.stdin); print(s["info"]["version"], s["paths"]["/orders"]["get"]["parameters"][0]["name"])'
curl -i 'http://PRISM_LAN_IP:4010/orders?order_id=ORD-1001'
curl -i 'http://PRISM_LAN_IP:4010/orders?order_reference=ORD-1001'
```

The version/name should be `2.0.0 order_reference`; the old query is rejected
with 422 and the renamed query succeeds. Without restarting the gateway or
reconnecting/reloading MCP, repeat the same unchanged `ORD-1001` lookup prompt.
The gateway can discover the changed spec and heal the query name while its
agent-facing tool schema remains frozen. No exact healing-time claim is made.

## Reset

Stop Prism, restart it with `openapi-v1.json`, then restart the gateway and
reconnect/reload the MCP client to establish a fresh v1 baseline. Restrict the
mock listener with the host firewall to the private demo network; do not expose
it to the public internet.
