# Graph Report - self-healing-tool-registry  (2026-10-17)

## Corpus Check
- 212 files · ~151,497 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 6, .example 1, .css 1)

## Summary
- 2649 nodes · 6255 edges · 171 communities (148 shown, 23 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 860 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `87276cdb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_candidates.py
- SpecWatcher
- HealOutcome
- McpDriftServer
- test_jev.py
- diagnose.py
- session
- Healer
- start.py
- test_dashboard.py
- test_mock_api.py
- mcp_drift_server.py
- Reason
- connections.py
- grpc.py
- repair.py
- test_diagnose.py
- mock_api/app.py
- test_store.py
- create_app
- PostgresStore
- openapi_source
- test_scenarios.py
- test_callback_exception_is_sanitized_and_keeps_secret_out_of_logs
- candidates.py
- Store
- Outcome
- test_connections.py
- test_explorer.py
- test_http.py
- test_ac_50_mutation_drift.py
- Dashboard
- test_ac_78_scorecard.py
- FixStore
- test_bench.py
- _coerce_args
- connection_security.py
- integration/conftest.py
- report
- Self-Healing Gateway Write-up
- test_registry_context_closes_resources
- run_explore
- create_app
- mcp_bench
- Script
- operations
- MockApi
- swagger2.py
- LoadedSpec
- test_ac_34_cli_uses_real_custom_spec_and_closes_resources
- test_ac_43_repair_agent.py
- Tier
- mcp_agent.py
- measure_mcp
- test_registry.py
- Benchmark pipeline
- test_ac_58_mcp_client_docs.py
- sanitize
- build
- live_safety
- graphql_app.py
- test_ac_68_mcp_view.py
- gateway.py
- test_detect.py
- test_ac_80_lifecycle.py
- p3/conftest.py
- token_overhead
- .preflight
- Registry
- guide.js
- false_patch_rate
- run_live
- _pass
- Already on main (do not rebuild)
- ErrorClass
- test_client_config.py
- Gateway
- railway.json
- dashboard/app.py
- One audit row per heal attempt
- Registry
- classify
- Heal pipeline
- Spec-change precompute
- ui.js
- test_ac_51_reset_and_profiles.py
- graphql.py
- Safe fix operations
- Safety gate
- Healer
- Self-healing registry
- test_agents.py
- demo.py
- Side
- send
- StepClock
- mcp/conftest.py
- OperationSpec loader contract
- Connections configuration page
- Gateway landing page
- F16 Dashboard
- FastAPI
- test_ac_63_mcp_gateway.py
- FixStore contract
- SpecSource contract
- demo/__init__.py
- AC-15 ZTAR, Safe-Refusal, and False-Patch Rate targets
- LangChain OpenAI
- Gateway
- Dashboard Live Interface
- healer
- JSON Schema
- python-dotenv
- Uvicorn
- Z7: One catalog of mutation labels, and an honest denominator
- tiebreak
- test_ac_77_panel_slot.py
- F7: State polls read only new audit rows (should fix, performance)
- Violation
- External API and tool connections: implementation plan
- test_ac_76_audit_since.py
- safe_refusal
- FixStatus
- V1: Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, Token Overhead)
- models.py
- apply_ops
- check_data_correctness
- V0: A plug-in slot for dashboard panels (foundation for V1-V3)
- F5: A run that calls no tools is not "data-correct" (correctness, must fix)
- Read this before the task file
- override
- V3: Fix lifecycle panel (candidates, promoted rules, spec snapshots)
- pytest
- Z15: ZTAR report with layers, intervals and fuzz (last)
- Z3: L3 / E5 allows only move or unwrap, with response-source provenance
- test_graphql.py
- Z6: L7 replay guard for upstream MCP tools
- RepairAgent
- jev.py
- test_ui_regressions.py
- F8: Stop tracking generated graph history (housekeeping)
- copy
- Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)
- Z9: Prove "verify before commit" for every layer (tests only)
- scorecard.js
- contract.py
- fixture
- Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)
- Z10: Seeded drift fuzzer for held-out ZTAR
- lifecycle.js
- live_safety.js
- build_admin
- Dashboard Panels
- V2: Live safety and timing panel (this session's heals)
- test_ac_26_m10.py
- BaseModel
- test_failure_layers.py
- Z5: L6 invariants catch U1 (wrong units) through the real registry
- drifted
- test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal
- mcp_server.py
- FakeLLM
- send
- test_ac_56_navbar_consistency.py

## God Nodes (most connected - your core abstractions)
1. `Reason` - 114 edges
2. `ErrorClass` - 113 edges
3. `Store` - 75 edges
4. `HealOutcome` - 72 edges
5. `Outcome` - 60 edges
6. `Side` - 55 edges
7. `Healer` - 53 edges
8. `Registry` - 52 edges
9. `Tier` - 50 edges
10. `create_app()` - 49 edges

## Surprising Connections (you probably didn't know these)
- `Owns` --references--> `check_data_correctness()`  [INFERRED]
  docs/prompts/F5-explorer-zero-calls.md → dashboard/explorer.py
- `Build` --references--> `fingerprint()`  [INFERRED]
  docs/prompts/V3-fix-lifecycle-panel.md → src/healer/fingerprint.py
- `Problem` --references--> `_api_client()`  [INFERRED]
  docs/prompts/F1-spec-path-guard.md → src/healer/gateway.py
- `Tests (`test_ac_73_*`)` --references--> `api_registry()`  [INFERRED]
  docs/prompts/F4-audit-token-redaction.md → src/healer/gateway.py
- `Owns` --references--> `Reason`  [INFERRED]
  docs/prompts/Z13-heal-robustness.md → src/healer/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Benchmark recovery and safety metrics** — bench_report_zero_touch_adaptation_rate, bench_report_safe_refusal_rate, bench_report_false_patch_rate, bench_report_mttr_and_internal_heal_ms, bench_report_baseline_comparison [EXTRACTED 1.00]

## Communities (171 total, 23 thin omitted)

### Community 0 - "test_candidates.py"
Cohesion: 0.18
Nodes (37): doc(), cand(), cast(), e(), header(), move(), mutation_build(), run() (+29 more)

### Community 1 - "SpecWatcher"
Cohesion: 0.07
Nodes (27): SpecSource, Contract 5: only the healer that provides precompute is called; snapshots still…, The spec last seen per source (read-only copy)., Poll every due source once. Return the names whose spec changed., SpecWatcher, Task, Clock, AC-55: the spec watcher snapshots changes, idles on unchanged specs, backs off… (+19 more)

### Community 2 - "HealOutcome"
Cohesion: 0.12
Nodes (39): DecisionPath, HealOutcome, calls_to(), jev_reply(), m1_fix(), respx side effect: choose the option whose text satisfies `pick`, reading the…, A stored fix for the M1 break on get_user: 422, body.customer_id missing., test_ac_07_m6_d_heals_through_the_tiebreaker_without_jev() (+31 more)

### Community 3 - "McpDriftServer"
Cohesion: 0.13
Nodes (11): _admin_tools(), McpDriftServer, call_tool(), list_tools(), Any, Server, Starlette, Mock drift MCP server implementing Contract 8. (+3 more)

### Community 4 - "test_jev.py"
Cohesion: 0.06
Nodes (47): from_env(), JevChoice, JevClient, JevUnavailable, AsyncClient, Exception, Prefer TypeSafe direct, then OpenRouter, then opt-in OpenCode free Jev., Timeout, transport or HTTP error, or an answer that is not one of our options. (+39 more)

### Community 5 - "diagnose.py"
Cohesion: 0.15
Nodes (18): abstract_signature(), _diff_leaves(), _entry(), flatten_request(), _index(), _leaf(), _leaves(), _order() (+10 more)

### Community 6 - "session"
Cohesion: 0.12
Nodes (17): ClientSession, session(), Path, T1-7: record `tools/list` before and after each mutation (AC-52). Writes…, record(), _tools(), _schema_listing(), test_ac_30_list_maps_frozen_registry_tools_and_disables_list_changed() (+9 more)

### Community 7 - "Healer"
Cohesion: 0.13
Nodes (20): Future, _Abort, _Heal, Healer, _layer_reason(), Any, Ends the heal with a reason. An OpError from the interpreter ends it the same…, The agent's result: data when recovered, an error dict otherwise. (+12 more)

### Community 8 - "start.py"
Cohesion: 0.05
Nodes (40): Popen, signal, Signals, socket, _arguments(), _command(), _connect_host(), _display_host() (+32 more)

### Community 9 - "test_dashboard.py"
Cohesion: 0.08
Nodes (36): langchain_core_outputs, calls(), capturing_llm(), _generate(), client(), fake_llm(), FakeLLM, finished() (+28 more)

### Community 10 - "test_mock_api.py"
Cohesion: 0.10
Nodes (37): api(), client(), deref(), errors(), get_spec(), lookup_args(), operation(), params() (+29 more)

### Community 11 - "mcp_drift_server.py"
Cohesion: 0.17
Nodes (15): An in-memory MCP client session over a mock drift server (shared by the MCP…, mcp, mcp_server_lowlevel, mcp_server_transport_security, mcp_shared_memory, mcp_types, create_drift_server(), main() (+7 more)

### Community 12 - "Reason"
Cohesion: 0.16
Nodes (29): Reason, jev_ok(), (STRETCH, S2) Rule mining: after 3 wins of the same pattern, subsequent…, test_ac_44_rule_mining(), Any, parametrize, run(), test_cast_path_not_in_spec_is_unsafe_patch() (+21 more)

### Community 13 - "connections.py"
Cohesion: 0.08
Nodes (37): add_connection(), clean_entry(), config_path(), is_remote(), list_connections(), _load(), page(), Path (+29 more)

### Community 14 - "grpc.py"
Cohesion: 0.06
Nodes (45): FileDescriptorProto, google_protobuf, google_rpc, grpc_reflection_v1alpha, create_server(), _file(), Any, DescriptorPool (+37 more)

### Community 15 - "repair.py"
Cohesion: 0.10
Nodes (35): jsonschema, dumps(), get(), pop(), put(), Any, Path, Canonical JSON, hashing and path helpers for nested dict/list documents. (+27 more)

### Community 16 - "test_diagnose.py"
Cohesion: 0.22
Nodes (21): diff(), flatten_response(), make_op(), obj(), param(), Hand-built operations()-shaped dicts: v1 and every mock-API mutation (contracts…, entry(), leaf() (+13 more)

### Community 17 - "mock_api/app.py"
Cohesion: 0.13
Nodes (26): fastapi_exceptions, fastapi_security, CustomerRef, CustomerRefM10, EmailOut, ManagerOut, MutationIn, NewTicket (+18 more)

### Community 18 - "test_store.py"
Cohesion: 0.12
Nodes (35): clock(), db_path(), FakeClock, make_event(), make_fix(), open_store(), _open(), fixture (+27 more)

### Community 19 - "create_app"
Cohesion: 0.13
Nodes (25): _arguments(), create_app(), _env_list(), main(), FastAPI, Namespace, SimpleNamespace, arguments() (+17 more)

### Community 20 - "PostgresStore"
Cohesion: 0.08
Nodes (13): Build, Done when, F6: Make the Postgres store fail loudly instead of mid-heal (should fix), Owns, Problem, PostgresStore, Synchronous FixStore backed by Postgres; active reads always query committed…, pg_store() (+5 more)

### Community 21 - "openapi_source"
Cohesion: 0.25
Nodes (7): openapi_source(), AsyncClient, SpecSource, The default `SpecSource`: the API's OpenAPI 3 document at `path`., Contract 5: P4's watcher calls Healer.precompute(old: LoadedSpec, new:…, test_contract_5_spec_change_precompute(), test_injected_spec_source_serves_load_and_heal()

### Community 22 - "test_scenarios.py"
Cohesion: 0.11
Nodes (28): assert_first_heal(), call_for(), calls_to(), check_m1(), check_m2(), check_m4(), check_m5(), check_m9() (+20 more)

### Community 24 - "candidates.py"
Cohesion: 0.15
Nodes (26): Option, _assign(), build(), _cast(), _clue_fills(), _clue_response_ops(), _dry_run(), _evidence() (+18 more)

### Community 25 - "Store"
Cohesion: 0.09
Nodes (5): _fix(), Persist a fix and its success event together, updating caches after commit., _safe_layers(), Store, test_sqlite_store_implements_fix_store()

### Community 26 - "Outcome"
Cohesion: 0.11
Nodes (24): Readback, SpecSource, Outcome, Run `attempt`, then retry E1 up to len(E1_BACKOFF_S) times while the budget…, with_retries(), Compatibility wrapper; integrations should use preflight/verify_response…, Use ``preflight`` before sending, then ``verify_response`` after replay., Verifier (+16 more)

### Community 27 - "test_connections.py"
Cohesion: 0.10
Nodes (22): fastapi_testclient, TestClient, cfg_file(), client(), fixture, MonkeyPatch, parametrize, Path (+14 more)

### Community 28 - "test_explorer.py"
Cohesion: 0.08
Nodes (10): client(), offline(), fixture, parametrize, Tests for the Explorer endpoints (/api/explorer/info and /api/explore)., M6-N refuses set_manager (step 3); the agent still opens the ticket (step 4)., The LLM path must never quietly return a canned scripted result., test_explore_controls_pass_business_errors_through() (+2 more)

### Community 29 - "test_http.py"
Cohesion: 0.08
Nodes (26): AsyncExitStack, _arguments(), create_http_app(), create_server(), main(), Namespace, Server, Starlette (+18 more)

### Community 30 - "test_ac_50_mutation_drift.py"
Cohesion: 0.17
Nodes (19): mcp_shared_exceptions, _dump_tools(), Any, asyncio, parametrize, AC-50 (T-RENAME): get_user renamed to fetch_user; calling get_user returns…, AC-50 (T-REQUIRED): update_email requires 'reason'; old call without 'reason'…, AC-50 (T-ENUM): email_type enum changed to uppercase; lowercase 'work' fails. (+11 more)

### Community 31 - "Dashboard"
Cohesion: 0.21
Nodes (4): Dashboard, A scenario (and a live-LLM one can take minutes) holds the lock for its whole…, Once both agents finish an LLM run, remember the measured token pair., Both agents run the demo task against their own mock; the store is shared.

### Community 32 - "test_ac_78_scorecard.py"
Cohesion: 0.14
Nodes (15): get_scorecard(), _parse_markdown_table(), parse_report_markdown(), Any, Path, Load benchmark report and return scorecard metrics. Never invent numbers., Parse benchmark report markdown into scorecard metric structures., scorecard() (+7 more)

### Community 33 - "FixStore"
Cohesion: 0.09
Nodes (7): Protocol, Row, AuditEvent, _event(), FixStore, What the registry, the healer and the demo call on a store. SQLite (`Store`)…, Return ordered rows after the cursor; the id is separate from AuditEvent…

### Community 34 - "test_bench.py"
Cohesion: 0.16
Nodes (19): main(), main(), one(), out(), fixture, parametrize, Benchmark runner and report tests (FR-15.1 to 15.8; AC-14, AC-15, AC-16, AC-17,…, report() (+11 more)

### Community 35 - "_coerce_args"
Cohesion: 0.13
Nodes (17): _coerce_args(), _heal_info(), _json_or_text(), _lossless_coerce(), _parse_tool_result(), Any, Cast a value to the type the frozen v1 schema declares, only if lossless., Fit LLM-supplied arguments to the frozen agent-facing schema. A live model… (+9 more)

### Community 36 - "connection_security.py"
Cohesion: 0.13
Nodes (17): ipaddress, _env(), _header_name(), Runtime-only connection auth and egress policy., Resolve operator-held values per connection; never place these in tool config., Validate auth/reference shape without resolving or rewriting config., resolve_headers(), add() (+9 more)

### Community 37 - "integration/conftest.py"
Cohesion: 0.15
Nodes (17): api(), client(), jev(), make_registry(), make(), AsyncBaseTransport, fixture, Request (+9 more)

### Community 38 - "report"
Cohesion: 0.20
Nodes (16): _ablation_cell(), _failure_mode(), mcp_section(), _outcome(), _pick(), _rate(), The "## MCP gateway" report section (T1-8, T1-9)., mean/p50/p95 with the sample size, the shape FR-15.5 asks for. (+8 more)

### Community 39 - "Self-Healing Gateway Write-up"
Cohesion: 0.07
Nodes (41): Coding Agent Rules, Module Contracts and Working Rules, Baseline comparison, False-Patch Rate, Healthy MCP-call overhead, LLM token cost not measured, MCP heal evidence: 12/12, MTTR and internal heal_ms (+33 more)

### Community 40 - "test_registry_context_closes_resources"
Cohesion: 0.21
Nodes (12): MonkeyPatch, parametrize, Path, test_registry_context_closes_resources(), close(), __init__(), test_registry_context_closes_resources_on_startup_failure(), close() (+4 more)

### Community 41 - "run_explore"
Cohesion: 0.18
Nodes (11): _heal_summaries(), _llm_bootstrap_error(), Provider errors arrive as a page of JSON; the UI only needs the headline., Read-only view of every ToolDefinition after the run., Audit events as the explorer renders them, for a whole run., Response for a live-LLM run that could not even reach the provider. Returning…, Run both agents synchronously, capturing full per-call traces, schemas, and…, _registry() (+3 more)

### Community 42 - "create_app"
Cohesion: 0.11
Nodes (8): bad_request(), create_app(), explorer_info(), get_metrics_lifecycle(), mutation(), start(), FastAPI, get_explorer_info()

### Community 43 - "mcp_bench"
Cohesion: 0.11
Nodes (21): build(), executor(), Execute, make_tools(), Execute, One tool per registry spec; both agents differ only in `execute`. Logs each…, build(), executor() (+13 more)

### Community 44 - "Script"
Cohesion: 0.25
Nodes (13): hinted(), parametrize, Attempt callable that replays a fixed list of outcomes and records sleeps., Script, test_backoff_sequence_then_gives_up_after_three_retries(), test_budget_shrinks_between_retries(), test_default_jitter_stays_within_bound(), test_jitter_is_added_to_each_backoff() (+5 more)

### Community 45 - "operations"
Cohesion: 0.15
Nodes (19): fetch_spec(), _json_schema(), load(), operations(), OperationSpec, Inline every local `#/...` ref; keywords next to a $ref override the target's., resolve_refs(), walk() (+11 more)

### Community 46 - "MockApi"
Cohesion: 0.20
Nodes (4): check_custom(), MockApi, Validate a custom drift: one tool, any of rename / to_int / wrap / header /…, `custom` is required for, and only used by, the CUSTOM drift.

### Community 47 - "swagger2.py"
Cohesion: 0.17
Nodes (15): convert(), _operation(), _param_schema(), Any, Convert a Swagger 2.0 document to the OpenAPI 3 shape `operations()` reads…, Reshape a Swagger 2.0 document into the OpenAPI 3 shape `operations()` reads.…, Deep copy `node`, pointing every local `#/definitions/...` ref at…, Lift a 2.0 non-body parameter's type keywords into the OpenAPI 3 `schema`… (+7 more)

### Community 48 - "LoadedSpec"
Cohesion: 0.09
Nodes (31): mcp_source(), source(), OperationSpec, SpecSource, Read the upstream's tools/list. Names starting with `__` are reserved (admin…, to_operation(), sha256(), discover() (+23 more)

### Community 49 - "test_ac_34_cli_uses_real_custom_spec_and_closes_resources"
Cohesion: 0.15
Nodes (9): test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(), close(), __init__(), tracked_client(), test_ac_34_cli_uses_real_custom_spec_and_closes_resources(), close(), __init__(), tracked_client() (+1 more)

### Community 50 - "test_ac_43_repair_agent.py"
Cohesion: 0.21
Nodes (13): FakeLlm, asyncio, Exception, parametrize, AC-43 and AC-45: the tier-2 repair agent heals a break tier 1 cannot explain,…, Scripted model: returns `answer` and records every prompt it was sent., SlowLlm, test_ac_43_repair_agent_heals_unexplained_drift_and_fix_is_reused() (+5 more)

### Community 51 - "Tier"
Cohesion: 0.14
Nodes (26): Build, Why, IntEnum, mttr_summary(), outcome_counts(), percentiles(), Any, Benchmark metrics (FR-15.4, FR-15.5) over audit events and benchmark run rows.… (+18 more)

### Community 52 - "mcp_agent.py"
Cohesion: 0.16
Nodes (13): main(), ClientSession, Demo agent: one task over two upstream MCP servers, through the healer front…, Run the task once; returns calls, errors seen by the agent and the audit rows., Calls the front door, prints each call, and notes heals read from the shared…, LangGraph ReAct agent whose tools are the front door's tools (same shape as…, run_demo(), run_llm() (+5 more)

### Community 53 - "measure_mcp"
Cohesion: 0.15
Nodes (12): tool(), _main(), measure(), measure_mcp(), registry_call(), percentile(), _print(), Any (+4 more)

### Community 54 - "test_registry.py"
Cohesion: 0.21
Nodes (10): calls_to(), fix_for(), parametrize, test_ac_02_invalid_args_no_heal(), test_active_fix_request_ops_are_applied(), test_active_fix_response_ops_reshape_before_contract(), test_fr_3_4_value_rules_are_left_to_the_api(), test_healthy_call() (+2 more)

### Community 55 - "Benchmark pipeline"
Cohesion: 0.15
Nodes (13): Mock drift control contract, Benchmark report view, Live stream comparison, Mutation controls, Benchmark pipeline, Dashboard, Mock drift control, LLM-mode metrics not measured (+5 more)

### Community 56 - "test_ac_58_mcp_client_docs.py"
Cohesion: 0.24
Nodes (13): io, _json_blocks(), AC-58: docs/mcp-clients.md is a usable client guide derived from the hand-off…, The CLI flags the server actually accepts, read from its argparse help., _server_flags(), test_ac_58_covers_both_transports(), test_ac_58_documented_flags_exist_on_the_server(), test_ac_58_guide_is_derived_from_the_handoff() (+5 more)

### Community 57 - "sanitize"
Cohesion: 0.20
Nodes (10): Build, Done when, F4: Redact the real upstream token in the audit log (security, must fix), Owns, Problem, Tests (`test_ac_73_*`), FR-17.11 (X4): Precompute candidate fixes from spec diffs before any failure…, FR-5.7: the audit blob keeps no secret. Redact, then truncate (so a cut cannot… (+2 more)

### Community 58 - "build"
Cohesion: 0.18
Nodes (8): Header, min_length, build(), manager_ids(), update_email(), validate_manager(), FastAPI, require_tenant()

### Community 59 - "live_safety"
Cohesion: 0.19
Nodes (9): get_metrics_live(), live_safety(), Live session safety, timing and refusal metrics (AC-79). Pure function., app(), client(), offline(), fixture, AC-79: Live safety and timing panel (session heals). (+1 more)

### Community 60 - "graphql_app.py"
Cohesion: 0.16
Nodes (9): GraphQLMock, update_email(), FastAPI, Small Strawberry GraphQL mock for protocol-drift tests., User, UserEnvelope, strawberry, strawberry_fastapi (+1 more)

### Community 61 - "test_ac_68_mcp_view.py"
Cohesion: 0.19
Nodes (8): app(), client(), _front_door_tools(), offline(), fixture, AC-68: the dashboard MCP view reports the front door's tools (T2-9, no T1-6)., Build a clean registry the way the MCP server does, and read its tools., test_ac_68_endpoint_lists_exactly_the_front_door_tools()

### Community 62 - "gateway.py"
Cohesion: 0.12
Nodes (32): BaseException, What the MCP front door exposes, read from the same `Registry.tools()`., check_egress(), no_redirect_client(), origin(), AsyncClient, Reject unsafe destinations. Injected test transports bypass DNS only., _api_client() (+24 more)

### Community 63 - "test_detect.py"
Cohesion: 0.29
Nodes (10): parametrize, Response, r(), raw(), raw_status(), req(), test_ac_03_detector_table(), test_data_carries_decoded_body() (+2 more)

### Community 64 - "test_ac_80_lifecycle.py"
Cohesion: 0.16
Nodes (13): fix_lifecycle(), Fix lifecycle view: rules, candidates, active fixes and replays (AC-80). Read-…, Tests (`test_ac_80_*`), app(), client(), offline(), AsyncClient, fixture (+5 more)

### Community 65 - "p3/conftest.py"
Cohesion: 0.31
Nodes (9): api(), client(), make_registry(), make(), fixture, P3-owned fixtures. Mirrors `tests/integration/conftest.py` for the p3 track., Healing registry (store, no Jev, no real sleeping); keyword arguments override., store() (+1 more)

### Community 66 - "token_overhead"
Cohesion: 0.09
Nodes (20): Why, Build, Done when, Owns, Tests (`test_ac_93_*`), Why, Z12: Wilson 95% confidence intervals and N=30, RunRow (+12 more)

### Community 67 - ".preflight"
Cohesion: 0.15
Nodes (16): Build, Build, Done when, Owns, Problem, Tests (`test_ac_82_*`), Z1: L1 provenance checks enum targets against the current spec, _invalid_request() (+8 more)

### Community 68 - "Registry"
Cohesion: 0.11
Nodes (14): extract_tool_schemas(), Extract input and output schemas from a resolved OpenAPI spec for each…, Build, Done when, F1: Reject off-host spec paths (security, must fix), Owns, Problem, Tests (`test_ac_70_*`) (+6 more)

### Community 69 - "guide.js"
Cohesion: 0.44
Nodes (7): close(), go(), onKey(), open(), openTab(), place(), show()

### Community 70 - "false_patch_rate"
Cohesion: 0.14
Nodes (16): false_patch_rate(), Count wrong accepted requests when the request-level oracle is available., agent_rows(), AC-14: tier-1 MTTR p95 < 4.0 s for M1 to M5 (tier 0 < 0.5 s), heal_ms alongside., AC-15: ZTAR 100% over the healable mutations with Jev absent, M6 separate,…, AC-17: error loop, calls, tokens and final data are measured per scenario and…, AC-23: M1 to M9 re-run with spec_mode=off, per mutation healed or aborted with…, The text from one `##` heading to the next (or the end of the report). (+8 more)

### Community 71 - "run_live"
Cohesion: 0.18
Nodes (13): make_llm(), ChatOpenAI, test_make_llm_uses_nvidia_key_and_model_override(), test_make_llm_uses_nvidia_nim_defaults(), completed(), parametrize, Run the demo task once; returns (RunResult, mock api, [(tool, class), ...])., New email, manager 456, one ticket, and the lookup itself succeeded. (+5 more)

### Community 72 - "_pass"
Cohesion: 0.11
Nodes (20): classify_request(), classify_run(), Any, Request-level benchmark oracle, independent of the resulting mock state., Classify one target request; rejected requests are not false patches., Use the target operation's accepted request, including renamed-route attempts., _amain(), bench() (+12 more)

### Community 73 - "Already on main (do not rebuild)"
Cohesion: 0.19
Nodes (14): Build, Done when, Owns, Problem, Tests (`test_ac_85_*`), Z4: L5 read-back for every write tool, Problem, Already on main (do not rebuild) (+6 more)

### Community 74 - "ErrorClass"
Cohesion: 0.17
Nodes (18): ErrorClass, StrEnum, test_ac_79_live_safety_hand_built_audit(), test_demo_runs_the_pitch_flow(), (FUTURE, X4) Precomputed fix allows the first failing call after a spec change…, (STRETCH, S1) Sibling propagation: a second tool hit by the same rename heals…, test_ac_40_sibling_propagation(), test_ac_47_precompute() (+10 more)

### Community 75 - "test_client_config.py"
Cohesion: 0.27
Nodes (11): mcp_client_stdio, mcp_client_streamable_http, _connect(), _load_target(), Path, skipif, _safe_smoke(), _smoke() (+3 more)

### Community 76 - "Gateway"
Cohesion: 0.25
Nodes (8): MCP front-door view, Gateway, MCP Front Door, Built MCP gateway and APIs, Deferred GraphQL, gRPC, Postgres, and streaming work, AC-63 namespaced frozen upstream tools, F24 Upstream MCP gateway, System boundaries and deferred protocols

### Community 77 - "railway.json"
Cohesion: 0.25
Nodes (7): build, builder, dockerfilePath, deploy, healthcheckPath, restartPolicyType, $schema

### Community 78 - "dashboard/app.py"
Cohesion: 0.10
Nodes (36): agents, Baseline agent: same tools, but each call is a bare v1 HTTP request. No…, Shared agent pieces: prompt, task, LLM, tool factory and the run loop., RunResult, Healing agent: every tool call goes through the self-healing `Registry`., Scripted agent: the demo task as fixed tool calls. No LLM and no tokens. It…, argparse, asyncio (+28 more)

### Community 79 - "One audit row per heal attempt"
Cohesion: 0.29
Nodes (7): Audit before returning heal result, Secrets excluded from store and logs, Patch log, One audit row per heal attempt, SQLite fix and audit store, AC-5 exactly one audit event per heal, F5 Store and audit

### Community 80 - "Registry"
Cohesion: 0.29
Nodes (7): Frozen agent_schema invariant, Registry.tools() and Registry.call() contract, Frozen agent_schema, Registry, tools/call, tools/list, Facade and hot-patching

### Community 81 - "classify"
Cohesion: 0.15
Nodes (15): Build, Done when, Owns, Problem, Z11: Never heal non-drift (fault-injection matrix + Retry-After date form), classify(), _error_body(), _is_soft_error() (+7 more)

### Community 82 - "Heal pipeline"
Cohesion: 0.33
Nodes (6): One heal and one replay; no retry loop, Contract verification, Spec diagnosis, Heal pipeline, F10 Patch, verify, commit, Healing tiers 0, 1, Jev, and 2

### Community 83 - "Spec-change precompute"
Cohesion: 0.33
Nodes (6): Spec-change hook, Spec-change precompute, Spec watcher, Built spec watcher, AC-55 spec watcher behavior, F18 Spec watcher

### Community 84 - "ui.js"
Cohesion: 0.67
Nodes (5): apply(), init(), read(), toggles(), write()

### Community 85 - "test_ac_51_reset_and_profiles.py"
Cohesion: 0.26
Nodes (12): _dump_tools(), Any, asyncio, parametrize, AC-51 / Contract 8: admin tools (__admin_apply, __admin_list, __admin_reset)…, AC-51: reset restores tools/list byte for byte after any mutation., AC-51: reset restores in-memory users and tickets to SEED state., AC-51: profile='tickets' lists a different toolset than profile='users'. (+4 more)

### Community 86 - "graphql.py"
Cohesion: 0.22
Nodes (12): _arg_violations(), classify(), _literal(), AsyncClient, Exception, Response, _query(), GraphQL HTTP transport and machine-readable error normalization. (+4 more)

### Community 87 - "Safe fix operations"
Cohesion: 0.40
Nodes (5): No invented values, No executed model-generated code, Deterministic candidate building, Safe fix operations, F7 Candidate builder

### Community 88 - "Safety gate"
Cohesion: 0.40
Nodes (5): Safety invariants, Safety gate, Safety by construction, Base-schema fixes are never stacked, Threats and prevention

### Community 89 - "Healer"
Cohesion: 0.40
Nodes (5): Error classes E1–E6 and BUSINESS, Healer, Negative cache, Structured refusal, Structured refusal with retry false

### Community 90 - "Self-healing registry"
Cohesion: 0.40
Nodes (5): AC-1 registry tools and frozen agent_schema, F1 Tool registry, F3 Drift detection, F9 Safety gate, Self-healing registry

### Community 91 - "test_agents.py"
Cohesion: 0.22
Nodes (23): run(), itertools, langchain_core_language_models_fake_chat_models, langchain_core_messages, langchain_core_utils_function_calling, pydantic, build(), call() (+15 more)

### Community 92 - "demo.py"
Cohesion: 0.43
Nodes (7): fix_text(), main(), print_act(), print_summary(), Terminal demo, the fallback for the pitch: `python -m dashboard.demo`. Scripted…, Run every act from a cold store; `step` is the agents' pause between calls., task_done()

### Community 93 - "Side"
Cohesion: 0.24
Nodes (20): from_violations(), Error-clue mode: no spec, so only flat single-family fixes (technical-approach…, Side, parametrize, test_clue_ambiguous_names_give_one_candidate_per_assignment(), test_clue_m1_missing_field_filled_from_name_matching_argument(), test_clue_m2_type_error_becomes_cast(), test_clue_m4_auth_violation_becomes_header() (+12 more)

### Community 94 - "send"
Cohesion: 0.50
Nodes (4): AsyncClient, Exception, Response, send()

### Community 96 - "mcp/conftest.py"
Cohesion: 0.33
Nodes (7): pytest_asyncio, api(), mcp_client(), connect(), mcp_registry(), fixture, tools_config()

### Community 97 - "OperationSpec loader contract"
Cohesion: 0.67
Nodes (3): OperationSpec contract, Upstream MCP mapping contract, OperationSpec loader contract

### Community 98 - "Connections configuration page"
Cohesion: 0.67
Nodes (3): Connections configuration page, Environment-variable token-name configuration, MCP, OpenAPI, Swagger and GraphQL connection types

### Community 99 - "Gateway landing page"
Cohesion: 0.67
Nodes (3): Drift diagnosis and safe patch narrative, Gateway landing page, Interactive mutation demonstration

### Community 100 - "F16 Dashboard"
Cohesion: 0.67
Nodes (3): AC-18 live dashboard comparison, AC-68 dashboard MCP front-door view, F16 Dashboard

### Community 101 - "FastAPI"
Cohesion: 0.67
Nodes (3): FastAPI, HTTPX, Pydantic

### Community 102 - "test_ac_63_mcp_gateway.py"
Cohesion: 0.31
Nodes (10): asyncio, parametrize, AC-63 to AC-66: upstream MCP servers behind the gateway, healed through the…, test_ac_63_healthy_call_and_unknown_tool(), test_ac_63_tools_are_namespaced_merged_and_hide_admin_tools(), test_ac_64_precompute_prepares_mcp_fix_before_any_failure(), test_ac_64_upstream_drift_heals_with_frozen_schema(), test_ac_65_business_error_is_not_healed() (+2 more)

### Community 108 - "Gateway"
Cohesion: 0.20
Nodes (7): Path, Gateway, gateway_factory(), build(), fixture, A Gateway over in-memory upstream drift servers: {"users": drift, "tickets":…, _session()

### Community 119 - "Z7: One catalog of mutation labels, and an honest denominator"
Cohesion: 0.20
Nodes (10): Room for later (ZTAR), ZTAR lanes, ZTAR series (Z0-Z15), Build, Done when, Owns, Problem, Room for later (+2 more)

### Community 120 - "tiebreak"
Cohesion: 0.12
Nodes (20): Build, Done when, Owns, Problem, Tests (`test_ac_89_*`), Z8: Evidence ranking, and refusal on a tie, _described(), FR-7.6: the index of the one candidate that strictly beats the rest, else None.… (+12 more)

### Community 121 - "test_ac_77_panel_slot.py"
Cohesion: 0.24
Nodes (5): app(), client(), offline(), fixture, AC-77: A plug-in slot for dashboard panels (V0 foundation).

### Community 122 - "F7: State polls read only new audit rows (should fix, performance)"
Cohesion: 0.22
Nodes (7): What the registry kept away from the agents, since the last Reset. Counted from…, Build, Done when, F7: State polls read only new audit rows (should fix, performance), Owns, Problem, Tests (`test_ac_76_*`)

### Community 123 - "Violation"
Cohesion: 0.36
Nodes (11): hashlib, fingerprint(), Violation, outcome(), parametrize, A fresh interpreter (different str hash seed) gets the same fingerprint., test_ac_04_fingerprint_stable(), test_diff_signature_only_counts_for_e6() (+3 more)

### Community 124 - "External API and tool connections: implementation plan"
Cohesion: 0.20
Nodes (9): Activation and operator experience, Delivery order (separate PR per phase), Explicit non-goals and references, External API and tool connections: implementation plan, Goal and current evidence, Implementation ownership, Proposed acceptance matrix (reserve IDs in product.md), Security and compatibility gates (+1 more)

### Community 125 - "test_ac_76_audit_since.py"
Cohesion: 0.33
Nodes (7): event(), asyncio, MonkeyPatch, Path, test_ac_76_audit_events_since_uses_ordered_event_ids(), test_ac_76_dashboard_caches_incremental_audits_and_reset(), test_ac_76_scripted_state_matches_legacy_render_and_live_reset_counts()

### Community 126 - "safe_refusal"
Cohesion: 0.12
Nodes (13): Build, Done when, Owns, Problems (confirm each on `main` first; line numbers drift), Tests (`test_ac_94_*`), Z13: Heal-path robustness (error typing and bounded memory), FR-15.4 Safe-Refusal Rate: over the runs marked `must_refuse` (M8, and M6-N…, safe_refusal() (+5 more)

### Community 127 - "FixStatus"
Cohesion: 0.24
Nodes (11): FixStatus, make_fix(), _no_sleep(), test_ac_39_shared_active_fix_and_database_uniqueness(), test_ac_39_two_registries_reuse_m1_fix_at_tier0(), test_pg_concurrent_saves_leave_one_active_fix(), save(), test_pg_fix_active_and_candidate_round_trip_and_retired_read() (+3 more)

### Community 130 - "V1: Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, Token Overhead)"
Cohesion: 0.25
Nodes (7): Data source, Done when, Owns, Panel, Response shape, Tests (`test_ac_78_*`), V1: Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, Token Overhead)

### Community 131 - "models.py"
Cohesion: 0.07
Nodes (27): base64, Pure metric views for dashboard panels (AC-78, AC-79, AC-80). No FastAPI…, datetime, Enum, re, sqlite3, Upstream MCP servers as a protocol (contract 7): tools/list -> OperationSpec,…, REST adapter: send a request document (contract C1), return the raw result. (+19 more)

### Community 132 - "apply_ops"
Cohesion: 0.11
Nodes (30): Build, Done when, Owns, Problem, Tests (`test_ac_83_*`), Z2: L2 validates unknown headers and non-REST patched requests, apply_ops(), _strict() (+22 more)

### Community 133 - "check_data_correctness"
Cohesion: 0.21
Nodes (10): check_data_correctness(), Verify mock API state against expected values. `touched` restricts the verdict…, Parallel lanes (no shared files), Room for future modules, Tasks, Work prompts, test_ac_74_control_mutations_accept_seeded_state_without_calls(), test_ac_74_scoped_completed_run_is_correct() (+2 more)

### Community 134 - "V0: A plug-in slot for dashboard panels (foundation for V1-V3)"
Cohesion: 0.17
Nodes (11): mountAll(), mountPanel(), refresh(), register(), Build, Done when, Owns, Room for later (+3 more)

### Community 135 - "F5: A run that calls no tools is not "data-correct" (correctness, must fix)"
Cohesion: 0.29
Nodes (6): Build, Done when, F5: A run that calls no tools is not "data-correct" (correctness, must fix), Owns, Problem, Tests (`test_ac_74_*`)

### Community 136 - "Read this before the task file"
Cohesion: 0.29
Nodes (6): Before you write code, Done means, Git, Hard rules, Read this before the task file, Tests

### Community 137 - "override"
Cohesion: 0.20
Nodes (11): override(), Request, Response, Answer requests to `path` with `make(request)` (None passes through); returns…, E4: the API answers 200 with an error body to the v1 request, and works for the…, soft_error_for_old_shape(), test_ac_20_e4_on_idempotent_tool_is_replayed(), test_ac_24_audit_raw_error_is_redacted() (+3 more)

### Community 138 - "V3: Fix lifecycle panel (candidates, promoted rules, spec snapshots)"
Cohesion: 0.33
Nodes (5): Build, Done when, Owns, V3: Fix lifecycle panel (candidates, promoted rules, spec snapshots), Why

### Community 139 - "pytest"
Cohesion: 0.20
Nodes (8): bench, math, pytest, AC-28 (FR-21.1): a healthy Registry.call() adds < 10 ms p95 over the raw…, test_ac_28_healthy_overhead(), asyncio, AC-53: the MCP healthy-call overhead bench runs and returns finite numbers., test_ac_53_mcp_overhead_runs_and_returns_numbers()

### Community 140 - "Z15: ZTAR report with layers, intervals and fuzz (last)"
Cohesion: 0.29
Nodes (6): Build, Done when, Final PR body must include, Owns, Tests (`test_ac_96_*`), Z15: ZTAR report with layers, intervals and fuzz (last)

### Community 141 - "Z3: L3 / E5 allows only move or unwrap, with response-source provenance"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Problem, Tests (`test_ac_84_*`), Z3: L3 / E5 allows only move or unwrap, with response-source provenance

### Community 142 - "test_graphql.py"
Cohesion: 0.25
Nodes (10): create_app(), operations(), OperationSpec, _schema(), _introspection(), asyncio, test_ac_38_graphql_does_not_send_nested_input_values(), test_ac_38_graphql_introspection_maps_argument_and_nested_response() (+2 more)

### Community 143 - "Z6: L7 replay guard for upstream MCP tools"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Problem, Tests (`test_ac_87_*`), Z6: L7 replay guard for upstream MCP tools

### Community 144 - "RepairAgent"
Cohesion: 0.10
Nodes (20): Llm, Default registry config: a tool is a write unless the upstream says it is read-…, tool_config(), ClientSession, One healing registry over one upstream server, exposing every tool it lists., upstream_registry(), from_env(), _json_object() (+12 more)

### Community 145 - "jev.py"
Cohesion: 0.28
Nodes (8): dataclasses, _arg_types(), _dotted(), _entry(), Any, Jev Client (FR-8): one Choice call that selects a candidate index. Jev never…, `path: type` for each leaf of the agent's arguments. Values are PII-prone and…, string

### Community 146 - "test_ui_regressions.py"
Cohesion: 0.29
Nodes (6): shutil, subprocess, skipif, Focused browser-logic regressions for the dashboard stepper., test_ac_18_live_control_steps_and_transient_retry_copy(), test_ac_56_stepper_keeps_task_context_and_failure_states()

### Community 147 - "F8: Stop tracking generated graph history (housekeeping)"
Cohesion: 0.33
Nodes (5): Build, Done when, F8: Stop tracking generated graph history (housekeeping), Owns, Problem

### Community 148 - "copy"
Cohesion: 0.33
Nodes (6): collections, copy, _incompatibility(), has_external_ref(), Filter a loaded REST spec to explicitly selected, safely representable…, _scheme_satisfied()

### Community 149 - "Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)"
Cohesion: 0.33
Nodes (5): Build, Done when, Owns, Tests (`test_ac_95_*`), Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)

### Community 150 - "Z9: Prove "verify before commit" for every layer (tests only)"
Cohesion: 0.33
Nodes (5): Build, Done when, Owns, Why, Z9: Prove "verify before commit" for every layer (tests only)

### Community 151 - "scorecard.js"
Cohesion: 0.80
Nodes (4): el(), median(), render(), statTile()

### Community 152 - "contract.py"
Cohesion: 0.48
Nodes (6): check(), _passes(), Any, Output-schema validation (E5) and declarative postchecks (E6) on an OK outcome., _schema_violations(), PostcheckType

### Community 153 - "fixture"
Cohesion: 0.33
Nodes (6): api(), client(), db_path(), fixture, registry(), store()

### Community 154 - "Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)"
Cohesion: 0.29
Nodes (6): Done when, Owns, Room for later, Tests (`test_ac_81_*`), Why, Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)

### Community 155 - "Z10: Seeded drift fuzzer for held-out ZTAR"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Tests (`test_ac_91_*`), Why, Z10: Seeded drift fuzzer for held-out ZTAR

### Community 156 - "lifecycle.js"
Cohesion: 0.83
Nodes (3): el(), formatOp(), render()

### Community 157 - "live_safety.js"
Cohesion: 1.00
Nodes (3): el(), render(), statTile()

### Community 158 - "build_admin"
Cohesion: 0.43
Nodes (5): build_admin(), list_mutations(), mutations(), reset(), set_mutation()

### Community 160 - "V2: Live safety and timing panel (this session's heals)"
Cohesion: 0.40
Nodes (4): Done when, Owns, Tests (`test_ac_79_*`), V2: Live safety and timing panel (this session's heals)

### Community 161 - "test_ac_26_m10.py"
Cohesion: 0.50
Nodes (4): _assert_no_injection_in_requests(), AC-26 (S8 prompt-injection resistance / Mutation M10): Malicious instruction…, test_ac_26_m10_injection_resistance(), test_ac_26_m10_matches_m1_parity()

### Community 162 - "BaseModel"
Cohesion: 0.50
Nodes (4): ExploreIn, MutationIn, BaseModel, StartIn

### Community 164 - "Z5: L6 invariants catch U1 (wrong units) through the real registry"
Cohesion: 0.33
Nodes (5): Build, Done when, Owns, Tests (`test_ac_86_*`), Z5: L6 invariants catch U1 (wrong units) through the real registry

### Community 165 - "drifted"
Cohesion: 0.33
Nodes (5): drifted(), _custom_model(), _header_dep(), Undo the drift on a valid request so the v1 handler can serve it., _to_v1()

### Community 168 - "mcp_server.py"
Cohesion: 0.10
Nodes (16): collections_abc, dotenv, inspect, logging, random, Load GraphQL operations from an endpoint's standard introspection result., MCP stdio transport for a frozen :class:`healer.registry.Registry`., E1 retry policy (FR-11.1): bounded backoff with jitter. E1 is retried here and… (+8 more)

### Community 169 - "FakeLLM"
Cohesion: 0.40
Nodes (3): FakeLLM, GenericFakeChatModel, Replays a script of AIMessages; records the tools bound and the messages of…

### Community 170 - "send"
Cohesion: 0.50
Nodes (4): _payload(), Any, ClientSession, send()

## Knowledge Gaps
- **191 isolated node(s):** `healer`, `$schema`, `builder`, `dockerfilePath`, `healthcheckPath` (+186 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 890 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Store` connect `Store` to `HealOutcome`, `models.py`, `Healer`, `grpc.py`, `RepairAgent`, `test_store.py`, `test_scenarios.py`, `fixture`, `test_connections.py`, `test_http.py`, `Dashboard`, `FixStore`, `test_ac_26_m10.py`, `_coerce_args`, `integration/conftest.py`, `mcp_server.py`, `run_explore`, `test_registry_context_closes_resources`, `mcp_bench`, `test_ac_34_cli_uses_real_custom_spec_and_closes_resources`, `mcp_agent.py`, `measure_mcp`, `test_registry.py`, `test_ac_68_mcp_view.py`, `test_ac_80_lifecycle.py`, `p3/conftest.py`, `run_live`, `_pass`, `ErrorClass`, `dashboard/app.py`, `mcp/conftest.py`, `Gateway`, `test_ac_76_audit_since.py`, `FixStatus`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `ErrorClass` connect `ErrorClass` to `HealOutcome`, `models.py`, `test_jev.py`, `Healer`, `test_dashboard.py`, `override`, `Reason`, `grpc.py`, `repair.py`, `test_graphql.py`, `test_store.py`, `PostgresStore`, `test_scenarios.py`, `contract.py`, `Store`, `Outcome`, `Dashboard`, `FixStore`, `test_ac_26_m10.py`, `mcp_server.py`, `run_explore`, `send`, `mcp_bench`, `Script`, `Tier`, `test_registry.py`, `test_detect.py`, `.preflight`, `Registry`, `dashboard/app.py`, `classify`, `graphql.py`, `Violation`, `test_ac_76_audit_since.py`, `FixStatus`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `Reason` connect `Reason` to `test_candidates.py`, `HealOutcome`, `models.py`, `apply_ops`, `Healer`, `test_dashboard.py`, `override`, `repair.py`, `test_store.py`, `test_scenarios.py`, `candidates.py`, `FixStore`, `Tier`, `false_patch_rate`, `_pass`, `ErrorClass`, `Side`, `tiebreak`, `safe_refusal`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 100 inferred relationships involving `Reason` (e.g. with `expectation()` and `Owns`) actually correct?**
  _`Reason` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 91 inferred relationships involving `ErrorClass` (e.g. with `executor()` and `executor()`) actually correct?**
  _`ErrorClass` has 91 INFERRED edges - model-reasoned connections that need verification._
- **Are the 44 inferred relationships involving `Store` (e.g. with `measure_mcp()` and `mcp_bench()`) actually correct?**
  _`Store` has 44 INFERRED edges - model-reasoned connections that need verification._
- **Are the 64 inferred relationships involving `HealOutcome` (e.g. with `_ablation_cell()` and `mcp_section()`) actually correct?**
  _`HealOutcome` has 64 INFERRED edges - model-reasoned connections that need verification._