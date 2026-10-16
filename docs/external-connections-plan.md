# External API and tool connections: implementation plan

## Goal and current evidence

Enable users to add independently authenticated REST APIs and upstream MCP servers, discover safe usable tools, and select which enter the registry. Preserve existing configuration and healing behavior. This is a plan, not a claim that these capabilities are implemented.

The gateway loads `servers` and `apis` from `config/mcp_servers.json`, validates entries, builds per-connection clients, and probes MCP tools or API operations (`src/healer/gateway.py:55-64,81-127,162-170,260-304,349-380`). The dashboard connections backend lists, adds, removes and tests entries (`dashboard/connections.py:1-5,94-143`). MCP and API connections open during registry startup; a failure currently aborts startup (`src/healer/mcp_server.py:178-244`). The unified app creates that registry in its lifespan (`dashboard/unified.py:28-54`). There is no config hot reload in this flow.

Important limits: `Registry._agent_schema` exposes body and query parameters but ignores path, cookie and header parameters (`src/healer/registry.py:58-70`). OpenAPI loading currently fetches JSON/local references and recognizes bearer-style security only; API-key and basic schemes are not mapped (`src/healer/openapi_loader.py:44-66`). API connection auth currently comes from `token_env`, as does upstream MCP HTTP auth; this is per-entry, not a global token. Preserve GraphQL's experimental/deferred status: do not extend GraphQL or gRPC loaders/adapters in this work. The product's actual highest acceptance criterion is AC-82; the older `AGENTS.md` note saying AC-69 is stale. Reserve AC-102–AC-111 in `product.md` before implementation.

## Target configuration and decisions

Keep the existing `servers`/`apis` structure and make normalization runtime-only. Legacy `token_env` normalizes to bearer auth; legacy `spec_path` means a same-origin spec source. Do not silently rewrite config. Keep the `OperationSpec` contract unchanged. A connection has a stable name, protocol, base endpoint, selected operations, auth references, and non-secret default headers. An optional provider preset supplies versioned, static suggestions (auth mechanism, defaults, likely spec endpoint); it is not the connection and never contains credentials. Every connection account remains isolated, including two accounts using the same provider.

Support static none, bearer, API-key-in-header, basic and custom header auth using environment-variable *names*. Permit multiple custom secret header references and nonsecret defaults such as version, accept or tenant. Reject conflicting auth modes, including case-insensitive duplicate/conflicting `Authorization` headers. Never put secret values or secret-bearing URLs in config, UI, model schemas, operation specs, logs, store or probe results. Validate env var names; never expose arbitrary process environment to the model. Error redaction must include generated bearer/basic forms and errors rendered into the model prompt (notably `repair.py` consumes outcome data). Config literals are not a reliable secret detector: sensitive values must be references.

Spec retrieval has separate auth settings and a separate client from API calls. New spec URLs default to public/unauthenticated even when the API has credentials; offer explicit same-origin credential reuse only if required. Never inherit credentials across origins. The upstream MCP `tools/list` call uses MCP transport authentication, not REST spec-fetch authentication. Do not let an OpenAPI `servers` value, `$ref`, or model argument choose a new credential target. Initially accept bundled local refs only. Query-credential providers are deferred because URLs can leak through logs; never represent query auth as headers. No OAuth browser flow, token broker, refresh or stored token in this release.

## Security and compatibility gates

Apply exact scheme/host/port origin scoping to credentials and forbid credential-bearing redirects. Require HTTPS before sending credentials externally. Validate API, spec and probe destinations against SSRF: private, loopback, link-local, metadata and reserved addresses, including IPv6; enforce resolved-address checks to address DNS rebinding, or use controlled egress. Permit internal services only through an explicit operator-controlled allowlist. Preserve local mock development through an explicit dev allowance, not a global intranet ban. Reject CRLF, `Host`, hop-by-hop headers and duplicate case-folded header names. Keep dashboard `CONNECTIONS_TOKEN` separate from gateway inbound MCP auth and upstream credentials. Protect remote connection read/edit/test routes; deployment still requires authenticated TLS ingress for the rest of the dashboard—do not claim global dashboard auth.

The current gateway initializes `header_sources` as `{}` for upstream and API registries (`gateway.py:219-224,291-296`). Explicitly wire approved configured headers into request validation and replay; relying on `httpx` client defaults alone is insufficient. The effective outbound request must combine connection defaults with safe per-request headers, including secret headers sourced only through approved config references. Validation must account for those effective headers; resolved credentials must not enter model inputs or persisted request documents. Auth headers are never agent-overridable. Do not weaken the existing DSL or trust boundary. Expose required path parameters only after adding route binding support; never invent a path value. If a parameter/media type cannot be safely represented, omit that operation with a machine-readable diagnostic rather than advertising a tool that falsely succeeds. Do not claim full Stripe JSON-body support: form-encoded APIs require a future serializer.

Discovery selects only explicitly allowlisted, compatible operations. Infer only security mechanism and header name declared in the spec; never infer credentials or missing values. Preserve OpenAPI security alternatives versus combined requirements; if unsupported, report it rather than weakening security. External refs, unsupported serialization/media types, missing operation IDs and ambiguous parameters get diagnostics, not false success.

## Delivery order (separate PR per phase)

Dependency order: **A model/validation → B isolated clients/auth → C compatibility-gated discovery → D optional presets → E dashboard lifecycle → F proof/docs**. Each phase is a separate change/PR; no estimates or new runtime dependencies are implied.

1. **A — Requirements, normalization and compatibility.** Add product FRs and AC-102–AC-111, document the supported config, normalize legacy entries without rewriting them, and test legacy same-origin behavior. Add validation for auth profiles, environment references and conflicts. Keep startup fail-fast for invalid configured upstreams initially, but use named safe errors and guarantee resource cleanup. Do not silently change startup semantics; graceful per-connection isolation can be considered later.
2. **B — Isolated authentication and spec fetching.** Add separate API-call and spec-fetch clients with independent credentials and strict origin/redirect policy. Verify effective wire headers and redaction. Add SSRF destination controls, operator allowlisting, and safe behavior for DNS resolution changes. Keep local mock tests supported by explicit operator-controlled dev allowance.
3. **C — Compatibility-gated discovery.** Add selected-operation allowlisting, route/path argument binding and required configured-header handling. Keep frozen `agent_schema` once loaded. Test supported operations end-to-end and ensure unsupported operations produce diagnostics rather than tool definitions. Do not expand `OperationSpec` unless deliberately updating all loaders and contract tests.
4. **D — Small preset catalog, optional.** Only after loader compatibility evidence, seed versioned GitHub and Notion suggestions. Keep custom configuration universal and useful without a preset. Presets are hints, not guarantees; pin preset version/source and verification date, and never scrape arbitrary provider docs. No universal catalog or Google Discovery work.
5. **E — Dashboard setup and lifecycle.** Reuse `dashboard/connections.html` and its existing backend rather than redesigning. Add optional preset/custom selection; separate API and spec endpoints/auth inputs; multiple header env references; and create/edit/test/save/manage flows. Show step-specific status codes, operation/tool counts and unsupported items. A successful spec discovery is not proof API credentials work unless the user separately approves a side-effect-free health probe. Test first, but allow saving a temporarily unavailable service. Preserve secret references on unrelated edits; clearing one must be explicit. Keep stdio configuration file-only and read-only. Names remain stable (no namespace-breaking rename). Use accessible controls and safe `textContent` rendering.
6. **F — Proof and operating documentation.** Prove mixed connections offline first, then provide an opt-in vendor smoke test without real secrets in tests. Document restart activation and operator egress policy. Stop when independent auth, external specs, compatible selected tools and safe failure behavior are demonstrated—not when an arbitrary URL appears to work.

### Implementation ownership

| Area | Primary touchpoints | Validation owner |
|---|---|---|
| Config, auth and discovery | `src/healer/gateway.py`, `openapi_loader.py`, `swagger2.py`; preserve existing loader contracts | Backend implementer: normalization, isolation and compatibility tests |
| Request construction and healing | `src/healer/registry.py`, `adapters/rest.py`, header-source wiring in `heal.py`/`candidates.py` only where necessary | Backend implementer: effective-header, path-binding and replay tests |
| Secret redaction | `src/healer/store.py`, `heal.py`, `repair.py` and connection probe errors | Security test owner: secret-echo and derived-credential tests |
| Lifecycle and management | `src/healer/mcp_server.py`, `dashboard/unified.py`, `dashboard/connections.py` | Integration test owner: restart semantics, authorization and cleanup |
| Setup experience | `dashboard/connections.html` using the existing visual system | Designer: accessible form, edit flow and pending-restart browser checks |
| Requirements and hand-off | `product.md`, `FLOW.md`, `plan.md`, `.env.example`, connection examples and user guide | Integrator: acceptance coverage and final repository gates |

## Activation and operator experience

Use restart activation for the first release: no hot reload, MCP `list_changed`, or mutation of a frozen schema. After save/update/remove, show “pending restart”; the currently loaded tools remain active until restart. Removing a saved connection must warn that its loaded registry remains active until restart. Do not show runtime-active status without comparing saved configuration to a loaded fingerprint. Env rotation also requires restart. Connection-test endpoints need not share the same activation state as discovery: make this explicit in the UI. Preserve existing `CONNECTIONS_TOKEN` checks for remote writes/tests and add equivalent protection for any new remote read/edit endpoints. Do not confuse these controls with MCP transport authentication.

## Proposed acceptance matrix (reserve IDs in product.md)

| AC | Acceptance evidence | Suggested ownership |
|---|---|---|
| AC-102 | Legacy entries normalize; same-origin legacy auth works; config is not silently rewritten. | `gateway.py`; `tests/t2ps2/test_connections.py` |
| AC-103 | Supported auth profiles, missing env refs and case-insensitive conflicts validate; no secret values leak. | gateway/auth tests; dashboard tests |
| AC-104 | Two APIs plus MCP, and two accounts for one provider, remain isolated through calls and replay. | `gateway.py`, registry tests |
| AC-105 | Remote spec auth is independent; no cross-origin credential inheritance or credential redirect. | spec/client tests |
| AC-106 | SSRF, DNS rebinding, redirects and unsafe/duplicate headers are rejected safely. | focused security tests |
| AC-107 | Compatible discovery exposes selected tools, binds path params, and diagnoses unsupported operations. | loader/registry tests |
| AC-108 | Presets are versioned/pinned; custom connections work without a preset. | preset unit tests |
| AC-109 | CRUD, safe test results and pending-restart/removal warnings work; stdio stays file-only. | dashboard routes and `connections.html`; `tests/dashboard/test_ac_82_single_port.py` |
| AC-110 | Raw and derived credentials are redacted from errors, repair prompts, logs, probes and store. | focused redaction tests |
| AC-111 | Healing invariants remain: frozen schemas, no invented values/model code, one replay and one audit row per heal, cleanup on failure. | `tests/t2ps1/test_ac_63_mcp_gateway.py`, `tests/mcp/test_stdio.py`, registry integration tests |

Use `test_ac_XX_*` names and offline `httpx.MockTransport`/`ASGITransport` plus the existing MCP harness. Never use real secrets. Do not test new features by weakening existing tests. The existing full-suite baseline in `plan.md` reports 845 passed, 10 pre-existing failures, 14 skipped and 1 xfailed (2026-10-17); re-baseline before work and report baseline separately, never silently treat it as a clean release gate. The later implementation PR must run `pytest -q` and `ruff check .`; graphify update is required after code changes. This document-only plan does not run those checks.

## Explicit non-goals and references

First-release non-goals: interactive OAuth/token storage/refresh; query auth; YAML or remote-ref crawling; arbitrary documentation scraping; complete OpenAPI serialization; Google Discovery; new GraphQL/gRPC work; streaming; hot reload; and a universal provider catalog. OAuth broker integration (for example Nango or Composio) is a separate decision only after a real use case.

Research references (patterns to evaluate, not features already present here): [Nango API configuration](https://nango.dev/docs/integrations/api-configuration), [Composio proxy execution](https://docs.composio.dev/docs/extending-sessions/proxy-execute), [Pipedream API proxy](https://pipedream.com/docs/connect/api-proxy), and [IBM MCP Context Forge multi-auth headers](https://github.com/IBM/mcp-context-forge/blob/main/docs/docs/using/multi-auth-headers.md).
