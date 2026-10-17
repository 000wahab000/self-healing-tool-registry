# Graph Report - self-healing-tool-registry  (2026-10-17)

## Corpus Check
- 247 files · ~180,720 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 52 file(s) not represented in the graph (top: .jsonl 38, (none) 7, .log 2)

## Summary
- 3129 nodes · 7405 edges · 187 communities (163 shown, 24 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 1028 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a65c9b37`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_candidates.py
- test_spec_watcher.py
- HealOutcome
- McpDriftServer
- test_jev.py
- diagnose.py
- _load_target
- Fix
- start.py
- test_dashboard.py
- test_mock_api.py
- profiles.py
- Reason
- connections.py
- graphql_loader.py
- repair.py
- test_diagnose.py
- mock_api/app.py
- test_store.py
- pytest
- PostgresStore
- github/run.py
- test_scenarios.py
- test_ac_50_mutation_drift.py
- build
- Store
- Verifier
- test_connections.py
- test_explorer.py
- test_http.py
- test_ac_100_drift_editor.py
- Dashboard
- dashboard/app.py
- FixStore
- test_bench.py
- explorer.py
- connection_security.py
- integration/conftest.py
- bench/run.py
- Self-Healing Gateway Write-up
- test_registry_context_closes_resources
- test_ac_81_start.py
- Shim
- baseline_agent.py
- Outcome
- swagger2.py
- build_admin
- grpc_loader.py
- AuditEvent
- test_ac_34_cli_uses_real_custom_spec_and_closes_resources
- test_ac_43_repair_agent.py
- metrics.py
- run_demo
- Gateway
- test_registry.py
- Benchmark pipeline
- test_ac_58_mcp_client_docs.py
- sanitize
- build
- safe_refusal
- graphql.py
- test_ac_68_mcp_view.py
- api_registry
- test_ac_107_graphql_honours_selected_operations
- test_ac_80_lifecycle.py
- p3/conftest.py
- ztar
- .preflight
- openapi_loader.py
- guide.js
- test_stdio.py
- test_agents_live.py
- classify_run
- create_ticket
- ErrorClass
- gateway.py
- Gateway
- railway.json
- models.py
- One audit row per heal attempt
- Registry
- detect.py
- Heal pipeline
- Spec-change precompute
- ui.js
- test_external_egress.py
- test_external_auth.py
- Safe fix operations
- Safety gate
- Healer
- Self-healing registry
- test_agents.py
- demo.py
- Side
- test_verify_layers.py
- StepClock
- create_app
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
- test_ac_52_mcp_fixtures.py
- Dashboard Live Interface
- healer
- JSON Schema
- python-dotenv
- Uvicorn
- .expected_canonical
- tiebreak
- test_ac_77_panel_slot.py
- Process
- test_fingerprint.py
- External API and tool connections: implementation plan
- test_contract.py
- SpecWatcher
- test_ui_regressions.py
- test_prism_specs.py
- Z10: Seeded drift fuzzer for held-out ZTAR
- apply_ops
- F5: A run that calls no tools is not "data-correct" (correctness, must fix)
- V0: A plug-in slot for dashboard panels (foundation for V1-V3)
- G1: Every MCP heal aborts with UNSAFE_PATCH (regression, do first)
- Read this before the task file
- Chaos test plan: external APIs, schema manipulation, crash scenarios
- fix_lifecycle
- Violation
- Z15: ZTAR report with layers, intervals and fuzz (last)
- Z3: L3 / E5 allows only move or unwrap, with response-source provenance
- agents/common.py
- Z6: L7 replay guard for upstream MCP tools
- upstream_registry
- origin
- create_server
- F8: Stop tracking generated graph history (housekeeping)
- RepairUnavailable
- Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)
- Z9: Prove "verify before commit" for every layer (tests only)
- scorecard.js
- test_admin.py
- test_external_discovery.py
- Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)
- Z11: Never heal non-drift (fault-injection matrix + Retry-After date form)
- lifecycle.js
- live_safety.js
- Already on main (do not rebuild)
- Dashboard Panels
- Registry
- PinnedAsyncTransport
- test_ac_81_start_mcp_readiness_validates_jsonrpc_response
- G3: D1 (side effect, then 503) gets retried
- log_jsonl
- verify
- test_external_connections.py
- test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal
- create_server
- LoadedSpec
- connect_upstreams
- re
- mcp_bench
- render
- Z2: L2 validates unknown headers and non-REST patched requests
- _pass
- Stress test summary (2026-10-17)
- F1: Reject off-host spec paths (security, must fix)
- .handle_async_request
- Z1: L1 provenance checks enum targets against the current spec
- test_watcher_resilience.py
- _registry_for
- token_overhead
- Healer
- setup

## God Nodes (most connected - your core abstractions)
1. `ErrorClass` - 130 edges
2. `Reason` - 114 edges
3. `Store` - 91 edges
4. `HealOutcome` - 77 edges
5. `create_app()` - 66 edges
6. `Registry` - 62 edges
7. `Outcome` - 61 edges
8. `Healer` - 57 edges
9. `Side` - 55 edges
10. `Tier` - 52 edges

## Surprising Connections (you probably didn't know these)
- `Owns` --references--> `check_data_correctness()`  [INFERRED]
  docs/prompts/F5-explorer-zero-calls.md → dashboard/explorer.py
- `Tasks` --references--> `check_data_correctness()`  [INFERRED]
  docs/prompts/README.md → dashboard/explorer.py
- `Build` --references--> `fingerprint()`  [INFERRED]
  docs/prompts/V3-fix-lifecycle-panel.md → src/healer/fingerprint.py
- `Problem` --references--> `_api_client()`  [INFERRED]
  docs/prompts/F1-spec-path-guard.md → src/healer/gateway.py
- `Tests (`test_ac_73_*`)` --references--> `api_registry()`  [INFERRED]
  docs/prompts/F4-audit-token-redaction.md → src/healer/gateway.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Benchmark recovery and safety metrics** — bench_report_zero_touch_adaptation_rate, bench_report_safe_refusal_rate, bench_report_false_patch_rate, bench_report_mttr_and_internal_heal_ms, bench_report_baseline_comparison [EXTRACTED 1.00]

## Communities (187 total, 24 thin omitted)

### Community 0 - "test_candidates.py"
Cohesion: 0.16
Nodes (42): doc(), cand(), cast(), e(), header(), move(), mutation_build(), pairing() (+34 more)

### Community 1 - "test_spec_watcher.py"
Cohesion: 0.19
Nodes (16): Clock, AC-55: the spec watcher snapshots changes, idles on unchanged specs, backs off…, Injected clock/sleep pair: sleeping moves time forward with no real wait., A SpecSource that serves a scripted sequence and counts its own calls., Minimal FixStore stand-in: records the snapshots the watcher saves., Recorder, spec(), SpyHealer (+8 more)

### Community 2 - "HealOutcome"
Cohesion: 0.10
Nodes (44): HealOutcome, calls_to(), jev_reply(), override(), Request, Response, respx side effect: choose the option whose text satisfies `pick`, reading the…, Answer requests to `path` with `make(request)` (None passes through); returns… (+36 more)

### Community 3 - "McpDriftServer"
Cohesion: 0.08
Nodes (30): _admin_tools(), create_drift_server(), main(), McpDriftServer, call_tool(), list_tools(), Any, Server (+22 more)

### Community 4 - "test_jev.py"
Cohesion: 0.06
Nodes (48): from_env(), JevChoice, JevClient, JevUnavailable, AsyncClient, Exception, Prefer TypeSafe direct, then OpenRouter, then opt-in OpenCode free Jev., Timeout, transport or HTTP error, or an answer that is not one of our options. (+40 more)

### Community 5 - "diagnose.py"
Cohesion: 0.14
Nodes (20): abstract_signature(), _diff_leaves(), diff_signature(), _entry(), flatten_request(), flatten_response(), _index(), _leaf() (+12 more)

### Community 6 - "_load_target"
Cohesion: 0.25
Nodes (9): _connect(), _load_target(), Path, skipif, _safe_smoke(), _smoke(), test_ac_37_invalid_transport_configs_fail_without_echoing_secrets(), test_ac_37_live_client_config() (+1 more)

### Community 7 - "Fix"
Cohesion: 0.25
Nodes (5): FR-8.6: send the chosen request once to the tool's side-effect-free route. Only…, A response-only fix on E5 reshapes the body already received; nothing is re-…, Fix, _AppliedFix, PatchCallTrace

### Community 8 - "start.py"
Cohesion: 0.18
Nodes (13): signal, _arguments(), _command(), _connect_host(), _display_host(), _env_list(), main(), _preflight() (+5 more)

### Community 9 - "test_dashboard.py"
Cohesion: 0.05
Nodes (51): itertools, langchain_core_language_models_fake_chat_models, langchain_core_outputs, langchain_core_utils_function_calling, pydantic, client(), explore(), impact() (+43 more)

### Community 10 - "test_mock_api.py"
Cohesion: 0.10
Nodes (37): api(), client(), deref(), errors(), get_spec(), lookup_args(), operation(), params() (+29 more)

### Community 11 - "profiles.py"
Cohesion: 0.06
Nodes (45): decoy(), enum_rename(), is_target(), schema(), swap(), get(), int_to_string(), is_int() (+37 more)

### Community 12 - "Reason"
Cohesion: 0.16
Nodes (28): Reason, jev_ok(), test_m8_is_refused_without_inventing_a_value(), Any, parametrize, run(), test_cast_path_not_in_spec_is_unsafe_patch(), test_e5_fix_that_would_re_send_follows_the_replay_rule() (+20 more)

### Community 13 - "connections.py"
Cohesion: 0.05
Nodes (68): add_connection(), clean_entry(), config_path(), is_remote(), list_connections(), _load(), page(), Path (+60 more)

### Community 14 - "graphql_loader.py"
Cohesion: 0.10
Nodes (20): FileDescriptorProto, google_protobuf, create_server(), _file(), Any, DescriptorPool, Small unary gRPC drift fixture with reflection and rich validation errors., Create (but do not start) a grpc.aio server and its descriptor pool. (+12 more)

### Community 15 - "repair.py"
Cohesion: 0.13
Nodes (30): dumps(), get(), pop(), put(), Any, Path, Canonical JSON, hashing and path helpers for nested dict/list documents., sha256() (+22 more)

### Community 16 - "test_diagnose.py"
Cohesion: 0.19
Nodes (22): diff(), _order(), make_op(), obj(), param(), Hand-built operations()-shaped dicts: v1 and every mock-API mutation (contracts…, test_input_is_not_mutated_and_ops_do_not_alias_entries(), entry() (+14 more)

### Community 17 - "mock_api/app.py"
Cohesion: 0.11
Nodes (31): fastapi_exceptions, fastapi_security, drifted(), _custom_model(), CustomerRef, CustomerRefM10, EmailOut, _header_dep() (+23 more)

### Community 18 - "test_store.py"
Cohesion: 0.14
Nodes (32): clock(), db_path(), FakeClock, make_event(), make_fix(), open_store(), _open(), fixture (+24 more)

### Community 19 - "pytest"
Cohesion: 0.14
Nodes (12): fastapi_testclient, pytest, _Gateway, asyncio, MonkeyPatch, Path, test_standalone_status_is_unknown_and_uses_dashboard_config_path(), test_unified_runtime_status_tracks_exact_startup_config() (+4 more)

### Community 20 - "PostgresStore"
Cohesion: 0.09
Nodes (17): FixStatus, PostgresStore, Synchronous FixStore backed by Postgres; active reads always query committed…, pg_store(), fixture, make_fix(), _no_sleep(), test_ac_39_shared_active_fix_and_database_uniqueness() (+9 more)

### Community 21 - "github/run.py"
Cohesion: 0.08
Nodes (44): agent_phase(), Audit, classify(), control(), control_phase(), kill(), kill_all(), line_count() (+36 more)

### Community 22 - "test_scenarios.py"
Cohesion: 0.12
Nodes (26): assert_first_heal(), call_for(), calls_to(), check_m1(), check_m2(), check_m4(), check_m5(), check_m9() (+18 more)

### Community 23 - "test_ac_50_mutation_drift.py"
Cohesion: 0.17
Nodes (19): mcp_shared_exceptions, _dump_tools(), Any, asyncio, parametrize, AC-50 (T-RENAME): get_user renamed to fetch_user; calling get_user returns…, AC-50 (T-REQUIRED): update_email requires 'reason'; old call without 'reason'…, AC-50 (T-ENUM): email_type enum changed to uppercase; lowercase 'work' fails. (+11 more)

### Community 24 - "build"
Cohesion: 0.13
Nodes (23): Open failures, Option, _assign(), build(), _cast(), _clue_fills(), _clue_response_ops(), _evidence() (+15 more)

### Community 25 - "Store"
Cohesion: 0.09
Nodes (7): Row, _fix(), Persist a fix and its success event together, updating caches after commit., Store, Path, test_ac_112_call_event_patch_metadata_drops_non_patch_payloads(), test_ac_112_call_event_patch_metadata_migrates_and_round_trips()

### Community 26 - "Verifier"
Cohesion: 0.11
Nodes (19): Use ``preflight`` before sending, then ``verify_response`` after replay., Verifier, test_l6_invariant_and_l7_unsafe_write_fail_independently(), run(), test_response_layers_reject_bad_base_shape(), run(), parametrize, test_ac_107_l2_checks_path_params_and_accepts_move_to_renamed_param() (+11 more)

### Community 27 - "test_connections.py"
Cohesion: 0.11
Nodes (21): cfg_file(), client(), fixture, MonkeyPatch, parametrize, Path, TestClient, AC-59: the Connections page backend (config validation, routes, probe, API… (+13 more)

### Community 28 - "test_explorer.py"
Cohesion: 0.07
Nodes (14): _coerce_args(), Fit LLM-supplied arguments to the frozen agent-facing schema. A live model…, client(), offline(), fixture, parametrize, Tests for the Explorer endpoints (/api/explorer/info and /api/explore)., M6-N refuses set_manager (step 3); the agent still opens the ticket (step 4). (+6 more)

### Community 29 - "test_http.py"
Cohesion: 0.09
Nodes (23): _arguments(), create_http_app(), main(), Namespace, Starlette, Build registries and keep their backing resources alive until exit., registry_context(), _serve() (+15 more)

### Community 30 - "test_ac_100_drift_editor.py"
Cohesion: 0.11
Nodes (28): _core(), custom_from_schema(), _props(), Turn an edited input schema into the mock's custom drift spec (dashboard-only).…, Diff `fake` against `actual` and return a validated custom drift spec. Pairing…, check_custom(), Validate a custom drift: one tool, any of rename / to_int / wrap / header /…, client() (+20 more)

### Community 31 - "Dashboard"
Cohesion: 0.10
Nodes (13): Dashboard, Path, A scenario (and a live-LLM one can take minutes) holds the lock for its whole…, Once both agents finish an LLM run, remember the measured token pair., Each tool's clean v1 input schema, exactly what the agent is given., What the registry kept away from the agents, since the last Reset. Counted from…, Both agents run the demo task against their own mock; the store is shared., Build (+5 more)

### Community 32 - "dashboard/app.py"
Cohesion: 0.04
Nodes (58): bad_request(), create_app(), explorer_info(), get_metrics_live(), get_scorecard(), mcp_calls(), mutation(), start() (+50 more)

### Community 33 - "FixStore"
Cohesion: 0.09
Nodes (9): Build, Done when, F6: Make the Postgres store fail loudly instead of mid-heal (should fix), Owns, Problem, Protocol, FixStore, What the registry, the healer and the demo call on a store. SQLite (`Store`)… (+1 more)

### Community 34 - "test_bench.py"
Cohesion: 0.12
Nodes (26): agent_rows(), main(), one(), fixture, parametrize, Benchmark runner and report tests (FR-15.1 to 15.8; AC-14, AC-15, AC-16, AC-17,…, AC-15: ZTAR 100% over the healable mutations with Jev absent, M6 separate,…, AC-17: error loop, calls, tokens and final data are measured per scenario and… (+18 more)

### Community 35 - "explorer.py"
Cohesion: 0.08
Nodes (35): check_data_correctness(), extract_tool_schemas(), _heal_info(), _heal_summaries(), _json_or_text(), _llm_bootstrap_error(), _lossless_coerce(), _parse_tool_result() (+27 more)

### Community 36 - "connection_security.py"
Cohesion: 0.17
Nodes (14): ipaddress, IPv4Address, IPv6Address, socket, _allowed_origin(), check_egress(), handle_async_request(), Request (+6 more)

### Community 37 - "integration/conftest.py"
Cohesion: 0.18
Nodes (15): api(), client(), jev(), make_registry(), make(), AsyncBaseTransport, fixture, The in-process mock API, with knobs: per-request delay (lets calls interleave)… (+7 more)

### Community 38 - "bench/run.py"
Cohesion: 0.14
Nodes (26): _ablation_cell(), expectation(), _failure_mode(), mcp_section(), _outcome(), once(), _pick(), _rate() (+18 more)

### Community 39 - "Self-Healing Gateway Write-up"
Cohesion: 0.06
Nodes (46): Coding Agent Rules, Module Contracts and Working Rules, Baseline comparison, False-Patch Rate, Healthy MCP-call overhead, LLM token cost not measured, MCP heal evidence: 12/12, MTTR and internal heal_ms (+38 more)

### Community 40 - "test_registry_context_closes_resources"
Cohesion: 0.21
Nodes (12): MonkeyPatch, parametrize, Path, test_registry_context_closes_resources(), close(), __init__(), test_registry_context_closes_resources_on_startup_failure(), close() (+4 more)

### Community 41 - "test_ac_81_start.py"
Cohesion: 0.23
Nodes (13): Signals, MonkeyPatch, parametrize, setup(), test_ac_81_start_cancel_during_readiness_does_not_spawn_later_services(), test_ac_81_start_commands_environment_and_readiness_order(), interrupt(), test_ac_81_start_deployment_environment_and_cli_precedence() (+5 more)

### Community 42 - "Shim"
Cohesion: 0.19
Nodes (8): main(), Any, Server, Starlette, Shim, lifespan(), call_tool(), list_tools()

### Community 43 - "baseline_agent.py"
Cohesion: 0.13
Nodes (19): agents, build(), executor(), Execute, Baseline agent: same tools, but each call is a bare v1 HTTP request. No…, make_tools(), Execute, One tool per registry spec; both agents differ only in `execute`. Logs each… (+11 more)

### Community 44 - "Outcome"
Cohesion: 0.14
Nodes (18): api_error(), Outcome, Run `attempt`, then retry E1 up to len(E1_BACKOFF_S) times while the budget…, with_retries(), test_ac_110_agent_facing_api_error_redacts_credentials(), hinted(), parametrize, Attempt callable that replays a fixed list of outcomes and records sleeps. (+10 more)

### Community 45 - "swagger2.py"
Cohesion: 0.07
Nodes (41): fetch_spec(), _json_schema(), load(), operations(), AsyncClient, OperationSpec, Inline every local `#/...` ref; keywords next to a $ref override the target's., resolve_refs() (+33 more)

### Community 46 - "build_admin"
Cohesion: 0.15
Nodes (7): build_admin(), list_mutations(), mutations(), reset(), set_mutation(), MockApi, `custom` is required for, and only used by, the CUSTOM drift.

### Community 47 - "grpc_loader.py"
Cohesion: 0.13
Nodes (20): grpc_reflection_v1alpha, grpc_source(), load(), message_class(), operations(), _pool(), Descriptor, DescriptorPool (+12 more)

### Community 48 - "AuditEvent"
Cohesion: 0.14
Nodes (3): AuditEvent, Return ordered rows after the cursor; the id is separate from AuditEvent…, _safe_layers()

### Community 49 - "test_ac_34_cli_uses_real_custom_spec_and_closes_resources"
Cohesion: 0.15
Nodes (9): test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(), close(), __init__(), tracked_client(), test_ac_34_cli_uses_real_custom_spec_and_closes_resources(), close(), __init__(), tracked_client() (+1 more)

### Community 50 - "test_ac_43_repair_agent.py"
Cohesion: 0.21
Nodes (13): FakeLlm, asyncio, Exception, parametrize, AC-43 and AC-45: the tier-2 repair agent heals a break tier 1 cannot explain,…, Scripted model: returns `answer` and records every prompt it was sent., SlowLlm, test_ac_43_repair_agent_heals_unexplained_drift_and_fix_is_reused() (+5 more)

### Community 51 - "metrics.py"
Cohesion: 0.08
Nodes (37): Build, Done when, Owns, Tests (`test_ac_79_*`), V2: Live safety and timing panel (this session's heals), Why, RunRow, false_patch_rate() (+29 more)

### Community 52 - "run_demo"
Cohesion: 0.15
Nodes (12): main(), ClientSession, Run the task once; returns calls, errors seen by the agent and the audit rows., Calls the front door, prints each call, and notes heals read from the shared…, LangGraph ReAct agent whose tools are the front door's tools (same shape as…, run_demo(), run_llm(), wrap() (+4 more)

### Community 53 - "Gateway"
Cohesion: 0.08
Nodes (22): tool(), _main(), measure(), measure_mcp(), registry_call(), percentile(), _print(), Any (+14 more)

### Community 54 - "test_registry.py"
Cohesion: 0.21
Nodes (9): calls_to(), parametrize, test_ac_02_invalid_args_no_heal(), test_active_fix_request_ops_are_applied(), test_active_fix_response_ops_reshape_before_contract(), test_fr_3_4_value_rules_are_left_to_the_api(), test_healthy_call(), test_healthy_create_ticket_sends_idempotency_key() (+1 more)

### Community 55 - "Benchmark pipeline"
Cohesion: 0.15
Nodes (13): Mock drift control contract, Benchmark report view, Live stream comparison, Mutation controls, Benchmark pipeline, Dashboard, Mock drift control, LLM-mode metrics not measured (+5 more)

### Community 56 - "test_ac_58_mcp_client_docs.py"
Cohesion: 0.24
Nodes (13): io, _json_blocks(), AC-58: docs/mcp-clients.md is a usable client guide derived from the hand-off…, The CLI flags the server actually accepts, read from its argparse help., _server_flags(), test_ac_58_covers_both_transports(), test_ac_58_documented_flags_exist_on_the_server(), test_ac_58_guide_is_derived_from_the_handoff() (+5 more)

### Community 57 - "sanitize"
Cohesion: 0.13
Nodes (18): Build, Done when, F4: Redact the real upstream token in the audit log (security, must fix), Owns, Problem, Tests (`test_ac_73_*`), Redact text; truncate only when a caller explicitly supplies a storage limit.…, Redact string leaves while preserving the value's JSON structure and size.… (+10 more)

### Community 58 - "build"
Cohesion: 0.18
Nodes (8): Header, min_length, build(), manager_ids(), update_email(), validate_manager(), FastAPI, require_tenant()

### Community 59 - "safe_refusal"
Cohesion: 0.18
Nodes (9): Build, Done when, Owns, Problems (confirm each on `main` first; line numbers drift), Tests (`test_ac_96_*`), Z13: Heal-path robustness (error typing and bounded memory), FR-15.4 Safe-Refusal Rate: over the runs marked `must_refuse` (M8, and M6-N…, safe_refusal() (+1 more)

### Community 60 - "graphql.py"
Cohesion: 0.07
Nodes (31): create_app(), GraphQLMock, update_email(), FastAPI, Small Strawberry GraphQL mock for protocol-drift tests., User, UserEnvelope, _arg_violations() (+23 more)

### Community 61 - "test_ac_68_mcp_view.py"
Cohesion: 0.19
Nodes (8): app(), client(), _front_door_tools(), offline(), fixture, AC-68: the dashboard MCP view reports the front door's tools (T2-9, no T1-6)., Build a clean registry the way the MCP server does, and read its tools., test_ac_68_endpoint_lists_exactly_the_front_door_tools()

### Community 62 - "api_registry"
Cohesion: 0.10
Nodes (28): BaseException, has_credentials(), _api_client(), api_registry(), api_tool_config(), _check_credential_envs(), credential_envs(), _http_url() (+20 more)

### Community 63 - "test_ac_107_graphql_honours_selected_operations"
Cohesion: 0.67
Nodes (3): test_ac_107_graphql_honours_selected_operations(), names(), source()

### Community 64 - "test_ac_80_lifecycle.py"
Cohesion: 0.21
Nodes (9): app(), client(), offline(), AsyncClient, fixture, AC-80: Fix lifecycle panel (candidates, promoted rules, replays)., test_ac_80_after_scripted_m1_run_twice(), wait_until_finished() (+1 more)

### Community 65 - "p3/conftest.py"
Cohesion: 0.31
Nodes (9): api(), client(), make_registry(), make(), fixture, P3-owned fixtures. Mirrors `tests/integration/conftest.py` for the p3 track., Healing registry (store, no Jev, no real sleeping); keyword arguments override., store() (+1 more)

### Community 66 - "ztar"
Cohesion: 0.20
Nodes (9): Build, Done when, Owns, Tests (`test_ac_95_*`), Why, Z12: Wilson 95% confidence intervals and N=30, FR-15.4 ZTAR: over `scenarios` only, the runs where the task completed and the…, ztar() (+1 more)

### Community 67 - ".preflight"
Cohesion: 0.27
Nodes (11): Build, Owns, _invalid_request(), _invariants_pass(), Any, OperationSpec, _readback_matches(), _row() (+3 more)

### Community 68 - "openapi_loader.py"
Cohesion: 0.15
Nodes (14): _is_bearer(), openapi_source(), SpecSource, Fetch an OpenAPI 3.x spec, inline its local $refs, and index its operations., The default `SpecSource`: the API's OpenAPI 3 document at `path`., _security(), _keys(), Step 0 contracts between the two tracks (AGENTS.md): OperationSpec, SpecSource,… (+6 more)

### Community 69 - "guide.js"
Cohesion: 0.44
Nodes (7): close(), go(), onKey(), open(), openTab(), place(), show()

### Community 70 - "test_stdio.py"
Cohesion: 0.19
Nodes (10): ClientSession, session(), parametrize, _schema_listing(), test_ac_30_list_maps_frozen_registry_tools_and_disables_list_changed(), test_ac_31_get_user_returns_healthy_data(), test_ac_32_heal_keeps_client_schema_stable_without_notification(), test_ac_33_m8_refusal_is_structured_and_does_not_invent_or_write() (+2 more)

### Community 71 - "test_agents_live.py"
Cohesion: 0.31
Nodes (10): completed(), parametrize, Live agent runs: real LLM through NVIDIA NIM, consuming API credits. Skipped…, Run the demo task once; returns (RunResult, mock api, [(tool, class), ...])., New email, manager 456, one ticket, and the lookup itself succeeded., run_live(), test_ac_09_agent_stops_after_retry_false(), test_clean_run_completes() (+2 more)

### Community 72 - "classify_run"
Cohesion: 0.36
Nodes (7): classify_request(), classify_run(), Any, Request-level benchmark oracle, independent of the resulting mock state., Classify one target request; rejected requests are not false patches., Use the target operation's accepted request, including renamed-route attempts., test_m7_accepted_original_body_is_wrong_according_to_request_oracle()

### Community 73 - "create_ticket"
Cohesion: 0.12
Nodes (21): Build, Done when, Owns, Problem, Tests (`test_ac_87_*`), Z4: L5 read-back for every write tool, Build, Done when (+13 more)

### Community 74 - "ErrorClass"
Cohesion: 0.11
Nodes (32): IntEnum, DecisionPath, ErrorClass, Tier, _event(), StrEnum, test_ac_79_live_safety_hand_built_audit(), test_demo_runs_the_pitch_flow() (+24 more)

### Community 75 - "gateway.py"
Cohesion: 0.09
Nodes (39): argparse, asyncio, Shared helpers: JSONL logging and a local-only Streamable-HTTP MCP app., Offline stand-in for the GitHub MCP server (127.0.0.1:8100). APPROXIMATION.…, Drift shim: a Streamable-HTTP MCP proxy between the healer and an upstream MCP…, An in-memory MCP client session over a mock drift server (shared by the MCP…, AC-28 (FR-21.1): healthy-call overhead of the registry over the raw transport.…, T1-7: record `tools/list` before and after each mutation (AC-52). Writes… (+31 more)

### Community 76 - "Gateway"
Cohesion: 0.25
Nodes (8): MCP front-door view, Gateway, MCP Front Door, Built MCP gateway and APIs, Deferred GraphQL, gRPC, Postgres, and streaming work, AC-63 namespaced frozen upstream tools, F24 Upstream MCP gateway, System boundaries and deferred protocols

### Community 77 - "railway.json"
Cohesion: 0.25
Nodes (7): build, builder, dockerfilePath, deploy, healthcheckPath, restartPolicyType, $schema

### Community 78 - "models.py"
Cohesion: 0.08
Nodes (38): base64, collections_abc, contextvars, copy, dataclasses, Enum, inspect, jsonschema (+30 more)

### Community 79 - "One audit row per heal attempt"
Cohesion: 0.29
Nodes (7): Audit before returning heal result, Secrets excluded from store and logs, Patch log, One audit row per heal attempt, SQLite fix and audit store, AC-5 exactly one audit event per heal, F5 Store and audit

### Community 80 - "Registry"
Cohesion: 0.29
Nodes (7): Frozen agent_schema invariant, Registry.tools() and Registry.call() contract, Frozen agent_schema, Registry, tools/call, tools/list, Facade and hot-patching

### Community 81 - "detect.py"
Cohesion: 0.20
Nodes (15): Problem, DestinationUnresolved, DNS could not answer: transient, unlike a destination that was resolved and…, classify(), _error_body(), _is_soft_error(), _kind(), Exception (+7 more)

### Community 82 - "Heal pipeline"
Cohesion: 0.33
Nodes (6): One heal and one replay; no retry loop, Contract verification, Spec diagnosis, Heal pipeline, F10 Patch, verify, commit, Healing tiers 0, 1, Jev, and 2

### Community 83 - "Spec-change precompute"
Cohesion: 0.33
Nodes (6): Spec-change hook, Spec-change precompute, Spec watcher, Built spec watcher, AC-55 spec watcher behavior, F18 Spec watcher

### Community 84 - "ui.js"
Cohesion: 0.67
Nodes (5): apply(), init(), read(), toggles(), write()

### Community 85 - "test_external_egress.py"
Cohesion: 0.16
Nodes (16): _no_sleep_registry_kwargs(), asyncio, MonkeyPatch, parametrize, _registry_for(), test_ac_106_blocked_egress_is_a_structured_non_retryable_error(), test_ac_106_dns_is_resolved_once_and_dial_pins_host_and_sni(), send() (+8 more)

### Community 86 - "test_external_auth.py"
Cohesion: 0.10
Nodes (27): _env(), _header_name(), _header_value(), Validate auth/reference shape without resolving or rewriting config., Resolve operator-held values per connection; never place these in tool config., resolve_headers(), add(), _sensitive_header() (+19 more)

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
Cohesion: 0.24
Nodes (21): run(), build(), call(), call_rows(), FakeLLM, last_tool_result(), llm(), AIMessage (+13 more)

### Community 92 - "demo.py"
Cohesion: 0.36
Nodes (8): fix_text(), main(), print_act(), print_summary(), Terminal demo, the fallback for the pitch: `python -m dashboard.demo`. Scripted…, Run every act from a cold store; `step` is the agents' pause between calls., task_done(), tempfile

### Community 93 - "Side"
Cohesion: 0.27
Nodes (18): from_violations(), Error-clue mode: no spec, so only flat single-family fixes (technical-approach…, Side, parametrize, test_clue_ambiguous_names_give_one_candidate_per_assignment(), test_clue_m1_missing_field_filled_from_name_matching_argument(), test_clue_m2_type_error_becomes_cast(), test_clue_m4_auth_violation_becomes_header() (+10 more)

### Community 94 - "test_verify_layers.py"
Cohesion: 0.29
Nodes (8): Before vs after the fix, _async_value(), _l2(), test_mcp_full_unwrap_drops_the_empty_wrapper_and_passes(), test_mcp_partial_unwrap_fails_request_schema(), test_patched_request_must_match_fresh_spec(), test_w1_readback_mismatch_and_invariant_failure_are_separate_layers(), run()

### Community 96 - "create_app"
Cohesion: 0.27
Nodes (9): create_app(), pytest_asyncio, api(), mcp_client(), connect(), mcp_registry(), fixture, tools_config() (+1 more)

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

### Community 108 - "test_ac_52_mcp_fixtures.py"
Cohesion: 0.22
Nodes (8): Path, record(), _tools(), asyncio, parametrize, AC-52: every recorded MCP drift fixture loads, and its tools differ before and…, test_ac_52_fixture_loads_and_differs(), test_ac_52_fixtures_match_a_fresh_recording()

### Community 119 - ".expected_canonical"
Cohesion: 0.13
Nodes (14): Done when, G2: W1 (200 but not saved) is never caught, Owns, Steps, Room for later (ZTAR), ZTAR lanes, ZTAR series (Z0-Z15), Build (+6 more)

### Community 120 - "tiebreak"
Cohesion: 0.12
Nodes (17): Build, Done when, Owns, Problem, Tests (`test_ac_91_*`), Z8: Evidence ranking, and refusal on a tie, _described(), FR-7.6: the index of the one candidate that strictly beats the rest, else None.… (+9 more)

### Community 121 - "test_ac_77_panel_slot.py"
Cohesion: 0.24
Nodes (5): app(), client(), offline(), fixture, AC-77: A plug-in slot for dashboard panels (V0 foundation).

### Community 122 - "Process"
Cohesion: 0.22
Nodes (7): Popen, _ready(), _stop(), _wait_ready(), Process, test_ac_81_start_stop_kills_group_after_leader_exits(), test_ac_81_start_wait_ready_cancels_immediately()

### Community 123 - "test_fingerprint.py"
Cohesion: 0.35
Nodes (10): hashlib, fingerprint(), outcome(), parametrize, A fresh interpreter (different str hash seed) gets the same fingerprint., test_ac_04_fingerprint_stable(), test_diff_signature_only_counts_for_e6(), test_fingerprint_stable_across_processes() (+2 more)

### Community 124 - "External API and tool connections: implementation plan"
Cohesion: 0.20
Nodes (9): Activation and operator experience, Delivery order (separate PR per phase), Explicit non-goals and references, External API and tool connections: implementation plan, Goal and current evidence, Implementation ownership, Proposed acceptance matrix (reserve IDs in product.md), Security and compatibility gates (+1 more)

### Community 125 - "test_contract.py"
Cohesion: 0.38
Nodes (8): check(), parametrize, test_each_missing_property_is_reported_once(), test_echo_compares_trimmed_casefolded_string_values(), test_non_ok_outcome_is_untouched(), test_postchecks(), test_schema_failure_wins_over_postcheck_and_keeps_data(), test_schema_violation_path_is_the_instance_path()

### Community 126 - "SpecWatcher"
Cohesion: 0.11
Nodes (10): FR-17.11 (X4): Precompute candidate fixes from spec diffs before any failure…, Redact a persisted spec copy without changing the live loaded schema., SpecSource, Contract 5: only the healer that provides precompute is called; snapshots still…, The spec last seen per source (read-only copy)., Poll every due source once. Return the names whose spec changed., SpecWatcher, Task (+2 more)

### Community 127 - "test_ui_regressions.py"
Cohesion: 0.29
Nodes (6): shutil, subprocess, skipif, Focused browser-logic regressions for the dashboard stepper., test_ac_18_live_control_steps_and_transient_retry_copy(), test_ac_56_stepper_keeps_task_context_and_failure_states()

### Community 130 - "test_prism_specs.py"
Cohesion: 0.39
Nodes (7): _published(), asyncio, Path, _spec(), test_prism_api_registry_heals_query_rename_once(), handle(), test_prism_specs_are_self_published_and_expose_only_order_lookup()

### Community 131 - "Z10: Seeded drift fuzzer for held-out ZTAR"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Tests (`test_ac_93_*`), Why, Z10: Seeded drift fuzzer for held-out ZTAR

### Community 132 - "apply_ops"
Cohesion: 0.15
Nodes (26): _dry_run(), Lossless casts and path conflicts are decided by the interpreter itself., apply_ops(), cast_op(), parametrize, reason_of(), test_ac_41_enum_map_bijective_and_lossy(), test_ac_42_encoding_sets_content_type() (+18 more)

### Community 133 - "F5: A run that calls no tools is not "data-correct" (correctness, must fix)"
Cohesion: 0.29
Nodes (6): Build, Done when, F5: A run that calls no tools is not "data-correct" (correctness, must fix), Owns, Problem, Tests (`test_ac_74_*`)

### Community 134 - "V0: A plug-in slot for dashboard panels (foundation for V1-V3)"
Cohesion: 0.17
Nodes (11): mountAll(), mountPanel(), refresh(), register(), Build, Done when, Owns, Room for later (+3 more)

### Community 135 - "G1: Every MCP heal aborts with UNSAFE_PATCH (regression, do first)"
Cohesion: 0.33
Nodes (5): Done when, G1: Every MCP heal aborts with UNSAFE_PATCH (regression, do first), Owns, Problem, Steps

### Community 136 - "Read this before the task file"
Cohesion: 0.29
Nodes (6): Before you write code, Done means, Git, Hard rules, Read this before the task file, Tests

### Community 137 - "Chaos test plan: external APIs, schema manipulation, crash scenarios"
Cohesion: 0.10
Nodes (19): 10. Known limits of this plan, 1. Goal and honesty rules, 2. The test agent, 3. Targets, 4.1 Schema drift (kind A), 4.2 Transport and server crashes, 4.3 Spec and upstream MCP faults, 4.4 Agent context skew (kind B) (+11 more)

### Community 138 - "fix_lifecycle"
Cohesion: 0.18
Nodes (10): get_metrics_lifecycle(), fix_lifecycle(), Fix lifecycle view: rules, candidates, active fixes and replays (AC-80). Read-…, Build, Done when, Owns, Tests (`test_ac_80_*`), V3: Fix lifecycle panel (candidates, promoted rules, spec snapshots) (+2 more)

### Community 139 - "Violation"
Cohesion: 0.14
Nodes (21): google_rpc, classify(), Any, Descriptor, Exception, Unary gRPC adapter and machine-readable status normalization., Send one unary call; classes come from the reflected request descriptor., _request_violations() (+13 more)

### Community 140 - "Z15: ZTAR report with layers, intervals and fuzz (last)"
Cohesion: 0.29
Nodes (6): Build, Done when, Final PR body must include, Owns, Tests (`test_ac_98_*`), Z15: ZTAR report with layers, intervals and fuzz (last)

### Community 141 - "Z3: L3 / E5 allows only move or unwrap, with response-source provenance"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Problem, Tests (`test_ac_86_*`), Z3: L3 / E5 allows only move or unwrap, with response-source provenance

### Community 142 - "agents/common.py"
Cohesion: 0.15
Nodes (13): make_llm(), Shared agent pieces: prompt, task, LLM, tool factory and the run loop., RunResult, Execute, Scripted agent: the demo task as fixed tool calls. No LLM and no tokens. It…, run(), ChatOpenAI, langchain_core_messages (+5 more)

### Community 143 - "Z6: L7 replay guard for upstream MCP tools"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Problem, Tests (`test_ac_89_*`), Z6: L7 replay guard for upstream MCP tools

### Community 144 - "upstream_registry"
Cohesion: 0.14
Nodes (15): Llm, Default registry config: a tool is a write unless the upstream says it is read-…, tool_config(), ClientSession, One healing registry over one upstream server, exposing every tool it lists., upstream_registry(), from_env(), nim_llm() (+7 more)

### Community 145 - "origin"
Cohesion: 0.27
Nodes (9): no_redirect_client(), scope(), no_redirect_httpx2(), scope(), origin(), PinnedHTTPX2Transport, __init__(), AsyncClient (+1 more)

### Community 146 - "create_server"
Cohesion: 0.12
Nodes (14): _call_class(), create_server(), call_tool(), Any, Server, OK without an "error" key; else the result's own class if valid, else BUSINESS., Expose registry tools and calls without adding healing behavior. With a store,…, _drive() (+6 more)

### Community 147 - "F8: Stop tracking generated graph history (housekeeping)"
Cohesion: 0.33
Nodes (5): Build, Done when, F8: Stop tracking generated graph history (housekeeping), Owns, Problem

### Community 148 - "RepairUnavailable"
Cohesion: 0.33
Nodes (5): _json_object(), Exception, The model's proposal and its token count. {"operation": None} means no safe fix., No model, a transport error, or an answer that is not a usable proposal., RepairUnavailable

### Community 149 - "Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)"
Cohesion: 0.33
Nodes (5): Build, Done when, Owns, Tests (`test_ac_97_*`), Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)

### Community 150 - "Z9: Prove "verify before commit" for every layer (tests only)"
Cohesion: 0.33
Nodes (5): Build, Done when, Owns, Why, Z9: Prove "verify before commit" for every layer (tests only)

### Community 151 - "scorecard.js"
Cohesion: 0.80
Nodes (4): el(), median(), render(), statTile()

### Community 152 - "test_admin.py"
Cohesion: 0.13
Nodes (5): api(), client(), fixture, threading, uvicorn

### Community 153 - "test_external_discovery.py"
Cohesion: 0.18
Nodes (18): collections, discover(), _duplicate_params(), _incompatibility(), has_external_ref(), Filter a loaded REST spec to explicitly selected, safely representable…, Select compatible operations; entry selection contains unnamespaced operation…, _scheme_satisfied() (+10 more)

### Community 154 - "Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)"
Cohesion: 0.29
Nodes (6): Done when, Owns, Room for later, Tests (`test_ac_83_*`), Why, Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)

### Community 155 - "Z11: Never heal non-drift (fault-injection matrix + Retry-After date form)"
Cohesion: 0.40
Nodes (4): Build, Done when, Owns, Z11: Never heal non-drift (fault-injection matrix + Retry-After date form)

### Community 156 - "lifecycle.js"
Cohesion: 0.83
Nodes (3): el(), formatOp(), render()

### Community 157 - "live_safety.js"
Cohesion: 1.00
Nodes (3): el(), render(), statTile()

### Community 158 - "Already on main (do not rebuild)"
Cohesion: 0.40
Nodes (4): Already on main (do not rebuild), Current layer status, Extra hard rules, ZTAR addendum (give this after `_PREAMBLE.md` for every Z task)

### Community 160 - "Registry"
Cohesion: 0.13
Nodes (11): SpecSource, _agent_schema(), AsyncClient, SpecSource, Agent-facing data loses only the exact known secrets; the generic patterns…, Header sources sent on every call: a connection's own credentials/headers (the…, Send `base` through `fix` (request ops, response ops), classify, check the…, Apply request fix and resolve approved header refs only in this transient wire… (+3 more)

### Community 161 - "PinnedAsyncTransport"
Cohesion: 0.40
Nodes (3): PinnedAsyncTransport, AsyncBaseTransport, Resolve and validate each target, then dial only the selected numeric address.

### Community 163 - "G3: D1 (side effect, then 503) gets retried"
Cohesion: 0.13
Nodes (13): Problem, Done when, G3: D1 (side effect, then 503) gets retried, Owns, Problem, Steps, Parallel lanes (no shared files), Room for future modules (+5 more)

### Community 164 - "log_jsonl"
Cohesion: 0.67
Nodes (3): log_jsonl(), Any, Path

### Community 165 - "verify"
Cohesion: 0.28
Nodes (8): Readback, Compatibility wrapper; integrations should use preflight/verify_response…, verify(), asyncio_result(), test_non_idempotent_write_requires_safe_rejection_or_actual_key(), test_preflight_validates_patched_document_strictly(), test_spec_unavailable_does_not_claim_l2_pass(), test_verification_has_ordered_seven_machine_readable_results()

### Community 166 - "test_external_connections.py"
Cohesion: 0.30
Nodes (14): _connection_spec(), _empty_spec(), _mcp_session(), _parameter_spec(), asyncio, test_ac_104_two_api_accounts_and_mcp_stay_isolated_through_replay(), handler(), test_ac_107_added_required_secret_header_replays_only_with_approved_value() (+6 more)

### Community 168 - "create_server"
Cohesion: 0.17
Nodes (11): local_http_app(), Server, Starlette, create_server(), call_tool(), main(), Any, Server (+3 more)

### Community 170 - "LoadedSpec"
Cohesion: 0.14
Nodes (19): mcp_source(), source(), ClientSession, OperationSpec, SpecSource, Read the upstream's tools/list. Names starting with `__` are reserved (admin…, to_operation(), _api_source() (+11 more)

### Community 171 - "connect_upstreams"
Cohesion: 0.39
Nodes (8): What the MCP front door exposes, read from the same `Registry.tools()`., _check_names(), connect_upstreams(), load_apis(), load_config(), Path, Open every configured upstream; sessions close when the context exits., _read()

### Community 172 - "re"
Cohesion: 0.20
Nodes (8): re, AsyncClient, Exception, Response, REST adapter: send a request document (contract C1), return the raw result., send(), nav_labels(), test_ac_56_navbar_items_order_active_and_report_stability()

### Community 175 - "mcp_bench"
Cohesion: 0.14
Nodes (12): bench, mcp_bench(), mcp_state_ok(), Only user 123's email may differ from the seed, and at most the one expected…, The scripted MCP task per drift-server mutation, through a healing gateway and…, Step 0: make main green (blocking), AC-28 (FR-21.1): a healthy Registry.call() adds < 10 ms p95 over the raw…, test_ac_28_healthy_overhead() (+4 more)

### Community 176 - "render"
Cohesion: 0.22
Nodes (9): _arg_types(), _dotted(), _entry(), Any, `path: type` for each leaf of the agent's arguments. Values are PII-prone and…, _op_line(), The user message: structure only. Argument values appear only for enum-typed…, render() (+1 more)

### Community 177 - "Z2: L2 validates unknown headers and non-REST patched requests"
Cohesion: 0.25
Nodes (7): Build, Done when, Owns, Problem, Tests (`test_ac_85_*`), Z2: L2 validates unknown headers and non-REST patched requests, _strict()

### Community 180 - "_pass"
Cohesion: 0.25
Nodes (8): _amain(), bench(), main(), _pass(), Namespace, One pass of the benchmark: scenarios x agents x n runs, optionally with a…, The main pass (FR-15.1, FR-15.6) and the error-only ablation (FR-15.7)., out()

### Community 181 - "Stress test summary (2026-10-17)"
Cohesion: 0.33
Nodes (5): 1. Tier-2 repair agent (live LLM), 2. MCP server in Claude Code, 3. Prism drifting external API, 4. Failure cases, Stress test summary (2026-10-17)

### Community 182 - "F1: Reject off-host spec paths (security, must fix)"
Cohesion: 0.29
Nodes (6): Build, Done when, F1: Reject off-host spec paths (security, must fix), Owns, Problem, Tests (`test_ac_70_*`)

### Community 185 - "Z1: L1 provenance checks enum targets against the current spec"
Cohesion: 0.33
Nodes (5): Build, Done when, Problem, Tests (`test_ac_84_*`), Z1: L1 provenance checks enum targets against the current spec

### Community 187 - "test_watcher_resilience.py"
Cohesion: 0.40
Nodes (3): asyncio, The watcher keeps polling after an unexpected error (review fix)., test_watcher_survives_an_unexpected_poll_error()

### Community 188 - "_registry_for"
Cohesion: 0.33
Nodes (5): asyncio, _registry_for(), test_ac_110_plain_config_values_are_not_secrets_for_the_agent(), test_ac_110_watcher_redacts_snapshot_without_mutating_loaded_spec(), source()

### Community 193 - "token_overhead"
Cohesion: 0.11
Nodes (14): Data source, Done when, Owns, Panel, Response shape, Tests (`test_ac_78_*`), V1: Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, Token Overhead), Why (+6 more)

### Community 197 - "Healer"
Cohesion: 0.13
Nodes (18): Future, _Abort, _Heal, Healer, _layer_reason(), Any, Ends the heal with a reason. An OpError from the interpreter ends it the same…, The agent's result: data when recovered, an error dict otherwise. (+10 more)

### Community 198 - "setup"
Cohesion: 0.25
Nodes (8): api(), client(), db_path(), fixture, registry(), store(), fixture, setup()

## Knowledge Gaps
- **226 isolated node(s):** `healer`, `$schema`, `builder`, `dockerfilePath`, `healthcheckPath` (+221 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1044 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ErrorClass` connect `ErrorClass` to `HealOutcome`, `test_jev.py`, `test_dashboard.py`, `Violation`, `Reason`, `agents/common.py`, `repair.py`, `create_server`, `test_store.py`, `PostgresStore`, `github/run.py`, `Store`, `Verifier`, `test_external_discovery.py`, `Dashboard`, `Registry`, `FixStore`, `dashboard/app.py`, `explorer.py`, `verify`, `baseline_agent.py`, `Outcome`, `grpc_loader.py`, `render`, `metrics.py`, `graphql.py`, `.preflight`, `Healer`, `create_ticket`, `gateway.py`, `models.py`, `detect.py`, `test_verify_layers.py`, `test_fingerprint.py`, `test_contract.py`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `Store` connect `Store` to `HealOutcome`, `test_prism_specs.py`, `Fix`, `fix_lifecycle`, `graphql_loader.py`, `repair.py`, `upstream_registry`, `create_server`, `test_store.py`, `PostgresStore`, `test_scenarios.py`, `test_external_discovery.py`, `test_connections.py`, `test_http.py`, `Dashboard`, `dashboard/app.py`, `FixStore`, `explorer.py`, `integration/conftest.py`, `bench/run.py`, `test_external_connections.py`, `test_registry_context_closes_resources`, `mcp_bench`, `AuditEvent`, `test_ac_34_cli_uses_real_custom_spec_and_closes_resources`, `_pass`, `Gateway`, `run_demo`, `test_registry.py`, `sanitize`, `_registry_for`, `test_ac_68_mcp_view.py`, `p3/conftest.py`, `setup`, `test_agents_live.py`, `ErrorClass`, `gateway.py`, `models.py`, `create_app`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `FixStore` connect `FixStore` to `Registry`, `G3: D1 (side effect, then 503) gets retried`, `Healer`, `Fix`, `fix_lifecycle`, `gateway.py`, `connect_upstreams`, `ErrorClass`, `models.py`, `upstream_registry`, `AuditEvent`, `Store`, `SpecWatcher`, `api_registry`, `Dashboard`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Are the 106 inferred relationships involving `ErrorClass` (e.g. with `executor()` and `executor()`) actually correct?**
  _`ErrorClass` has 106 INFERRED edges - model-reasoned connections that need verification._
- **Are the 100 inferred relationships involving `Reason` (e.g. with `expectation()` and `Owns`) actually correct?**
  _`Reason` has 100 INFERRED edges - model-reasoned connections that need verification._
- **Are the 60 inferred relationships involving `Store` (e.g. with `measure_mcp()` and `mcp_bench()`) actually correct?**
  _`Store` has 60 INFERRED edges - model-reasoned connections that need verification._
- **Are the 69 inferred relationships involving `HealOutcome` (e.g. with `_ablation_cell()` and `mcp_section()`) actually correct?**
  _`HealOutcome` has 69 INFERRED edges - model-reasoned connections that need verification._