# Graph Report - self-healing-tool-registry  (2026-10-16)

## Corpus Check
- 146 files · ~128,282 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 5, .example 1, .css 1)

## Summary
- 2057 nodes · 5027 edges · 124 communities (96 shown, 28 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 667 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `70f6278f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- HealOutcome
- test_candidates.py
- integration/conftest.py
- SpecWatcher
- mock_api/app.py
- openapi_loader.py
- test_mock_api.py
- test_dashboard.py
- test_jev.py
- test_diagnose.py
- test_store.py
- create_app
- create_app
- grpc.py
- Tier
- build
- test_bench.py
- test_scenarios.py
- test_detect.py
- test_explorer.py
- run_explore
- Healer
- registry.py
- pytest
- test_fingerprint.py
- executor
- overhead.py
- McpDriftServer
- Dashboard
- Heal Controller
- PostgresStore
- Four-Person Ownership
- Research Notes
- Store
- token_overhead
- test_connections.py
- test_client_config.py
- railway.json
- Self-Healing Tool Registry
- Tool Registry
- Benchmark Metrics
- Deterministic Candidate Tie-Breaker
- Benchmark Report
- _coerce_args
- Negative Cache
- FastAPI
- Operation Interpreter
- Frozen Agent Schema
- Secret Hygiene
- Technical Approach
- LangChain OpenAI
- Acceptance-Criteria Tests
- Machine-Readable Store Data
- No LLM in Tiers 0 and 1
- Specification Read Order and Authority
- Self-Healing Tool Registry
- One Audit Row per Heal
- No Model-Generated Code Execution
- Product Landing Page
- healer
- JSON Schema
- python-dotenv
- Uvicorn
- run.py
- ops.py
- Reason
- ErrorClass
- FixStore
- test_registry.py
- connections.py
- build_admin
- test_ops.py
- api_registry
- demo.py
- test_http.py
- Any
- test_explore_llm_surfaces_llm_failure_instead_of_scripted_fallback
- mcp/conftest.py
- LoadedSpec
- models.py
- test_ac_43_repair_agent.py
- RepairAgent
- test_ac_34_cli_uses_real_custom_spec_and_closes_resources
- test_agents.py
- Dashboard
- test_ac_58_mcp_client_docs.py
- test_stdio.py
- Connecting MCP clients to the healer gateway
- gateway.py
- graphql.py
- test_ac_38_registry_graphql_heals_and_keeps_schema_frozen
- p3/conftest.py
- FakeLLM
- test_ac_47_precompute
- false_patch_rate
- FakeClock
- Registry
- FixStatus
- mcp_bench
- test_ac_68_mcp_view.py
- sanitize
- send
- StepClock
- test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal
- test_mutation_buttons_cover_every_scenario_including_m6_m9_and_c3
- test_ac_51_reset_and_profiles.py
- record_mcp_fixtures.py
- detect.py
- _serve
- test_ac_63_mcp_gateway.py
- guide.js
- JevClient
- run_live
- make_tools
- drifted
- RepairUnavailable
- gateway_factory
- extract_tool_schemas
- demo/__init__.py

## God Nodes (most connected - your core abstractions)
1. `Reason` - 111 edges
2. `ErrorClass` - 94 edges
3. `Store` - 66 edges
4. `HealOutcome` - 64 edges
5. `Side` - 55 edges
6. `Registry` - 49 edges
7. `Healer` - 47 edges
8. `Tier` - 47 edges
9. `Outcome` - 43 edges
10. `DecisionPath` - 39 edges

## Surprising Connections (you probably didn't know these)
- `test_fr_6_4_spec_mode_must_be_on_or_off()` --uses--> `Registry`  [INFERRED]
  tests/integration/test_heal.py → src/healer/registry.py
- `Side-by-Side Agent Comparison` --semantically_similar_to--> `Dashboard`  [INFERRED] [semantically similar]
  dashboard/index.html → README.md
- `Single-Attempt Healing` --semantically_similar_to--> `Negative Cache`  [INFERRED] [semantically similar]
  agent.md → plan.md
- `Zero-Retention Model Policy` --semantically_similar_to--> `Secret Hygiene`  [INFERRED] [semantically similar]
  team-prompts.md → AGENTS.md
- `executor()` --uses--> `ErrorClass`  [INFERRED]
  agents/baseline_agent.py → src/healer/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Four Parallel Ownership Tracks** — plan_p1_mcp_protocols_track, plan_p2_healing_core_track, plan_p3_small_isolated_items_track, plan_p4_demo_docs_integration_track [EXTRACTED 1.00]
- **Self-healing request lifecycle** — readme_openapi_spec_diagnosis, readme_candidate_builder, readme_safety_gate, readme_verification_and_postchecks [EXTRACTED 1.00]

## Communities (124 total, 28 thin omitted)

### Community 0 - "HealOutcome"
Cohesion: 0.09
Nodes (50): DecisionPath, HealOutcome, calls_to(), jev_reply(), m1_fix(), override(), Request, Response (+42 more)

### Community 1 - "test_candidates.py"
Cohesion: 0.06
Nodes (98): Option, _assign(), build(), _cast(), _clue_fills(), _clue_response_ops(), _described(), _dry_run() (+90 more)

### Community 2 - "integration/conftest.py"
Cohesion: 0.15
Nodes (17): api(), client(), jev(), make_registry(), make(), AsyncBaseTransport, fixture, Request (+9 more)

### Community 3 - "SpecWatcher"
Cohesion: 0.07
Nodes (27): walk(), SpecSource, The spec last seen per source (read-only copy)., Poll every due source once. Return the names whose spec changed., SpecWatcher, Task, Clock, AC-55: the spec watcher snapshots changes, idles on unchanged specs, backs off… (+19 more)

### Community 4 - "mock_api/app.py"
Cohesion: 0.13
Nodes (26): fastapi_exceptions, fastapi_security, CustomerRef, CustomerRefM10, EmailOut, ManagerOut, MutationIn, NewTicket (+18 more)

### Community 5 - "openapi_loader.py"
Cohesion: 0.06
Nodes (46): copy, re, fetch_spec(), _is_bearer(), _json_schema(), load(), operations(), OperationSpec (+38 more)

### Community 6 - "test_mock_api.py"
Cohesion: 0.11
Nodes (36): api(), client(), deref(), errors(), get_spec(), lookup_args(), operation(), params() (+28 more)

### Community 7 - "test_dashboard.py"
Cohesion: 0.12
Nodes (23): langchain_core_language_models_fake_chat_models, langchain_core_messages, langchain_core_outputs, langchain_core_utils_function_calling, pydantic, calls(), finished(), Dashboard API tests: the app runs in-process, both mocks and the agents are… (+15 more)

### Community 8 - "test_jev.py"
Cohesion: 0.07
Nodes (43): _arg_types(), _dotted(), _entry(), JevChoice, JevUnavailable, Any, Exception, `path: type` for each leaf of the agent's arguments. Values are PII-prone and… (+35 more)

### Community 9 - "test_diagnose.py"
Cohesion: 0.10
Nodes (38): diff(), flatten_request(), flatten_response(), _index(), _leaf(), _leaves(), _order(), A tool that vanished under its name: the one new operation with the same method… (+30 more)

### Community 10 - "test_store.py"
Cohesion: 0.26
Nodes (18): make_fix(), open_store(), parametrize, rows(), test_call_events_returns_rows_after_the_cursor(), test_enum_check_rejects_bad_value(), test_failed_save_keeps_existing_active_fix(), test_fix_round_trip_survives_restart() (+10 more)

### Community 11 - "create_app"
Cohesion: 0.15
Nodes (8): create_app(), socket, api(), client(), fixture, test_real_http_switch_to_m1(), threading, uvicorn

### Community 12 - "create_app"
Cohesion: 0.11
Nodes (10): bad_request(), create_app(), explorer_info(), mutation(), start(), FastAPI, get_explorer_info(), client() (+2 more)

### Community 13 - "grpc.py"
Cohesion: 0.07
Nodes (40): FileDescriptorProto, google_protobuf, google_rpc, grpc_reflection_v1alpha, create_server(), _file(), Any, DescriptorPool (+32 more)

### Community 14 - "Tier"
Cohesion: 0.11
Nodes (30): IntEnum, mttr_summary(), outcome_counts(), percentiles(), Any, Benchmark metrics (FR-15.4, FR-15.5) over audit events and benchmark run rows.…, FR-15.5, per scenario and agent: mean/p50/p95 of `llm_tokens` per run and of…, FR-15.5: count, mean, median (p50) and nearest-rank p95 of one sample. (+22 more)

### Community 15 - "build"
Cohesion: 0.18
Nodes (9): Header, min_length, build(), manager_ids(), set_manager(), update_email(), validate_manager(), FastAPI (+1 more)

### Community 16 - "test_bench.py"
Cohesion: 0.13
Nodes (24): main(), agent_rows(), main(), one(), out(), fixture, parametrize, Benchmark runner and report tests (FR-15.1 to 15.8; AC-14, AC-15, AC-16, AC-17,… (+16 more)

### Community 17 - "test_scenarios.py"
Cohesion: 0.11
Nodes (28): assert_first_heal(), call_for(), calls_to(), check_m1(), check_m2(), check_m4(), check_m5(), check_m9() (+20 more)

### Community 18 - "test_detect.py"
Cohesion: 0.29
Nodes (10): parametrize, Response, r(), raw(), raw_status(), req(), test_ac_03_detector_table(), test_data_carries_decoded_body() (+2 more)

### Community 19 - "test_explorer.py"
Cohesion: 0.09
Nodes (8): client(), offline(), fixture, parametrize, Tests for the Explorer endpoints (/api/explorer/info and /api/explore)., M6-N refuses set_manager (step 3); the agent still opens the ticket (step 4)., test_explore_controls_pass_business_errors_through(), test_explore_refused_tool_is_skipped_and_the_task_continues()

### Community 20 - "run_explore"
Cohesion: 0.14
Nodes (14): check_data_correctness(), _heal_summaries(), _llm_bootstrap_error(), Verify mock API state against expected values. `touched` restricts the verdict…, Provider errors arrive as a page of JSON; the UI only needs the headline., Read-only view of every ToolDefinition after the run., Audit events as the explorer renders them, for a whole run., Response for a live-LLM run that could not even reach the provider. Returning… (+6 more)

### Community 21 - "Healer"
Cohesion: 0.08
Nodes (37): Future, _Abort, api_error(), _Heal, Healer, Any, The agent's result: data when recovered, an error dict otherwise., Gate, optional dry run, verify, commit: the same path for every tier. (+29 more)

### Community 22 - "registry.py"
Cohesion: 0.07
Nodes (45): agents, Baseline agent: same tools, but each call is a bare v1 HTTP request. No…, Shared agent pieces: prompt, task, LLM, tool factory and the run loop., RunResult, Healing agent: every tool call goes through the self-healing `Registry`., Scripted agent: the demo task as fixed tool calls. No LLM and no tokens. It…, collections_abc, ExploreIn (+37 more)

### Community 23 - "pytest"
Cohesion: 0.13
Nodes (24): argparse, asyncio, An in-memory MCP client session over a mock drift server (shared by the MCP…, contextlib, dotenv, mcp, mcp_server_lowlevel, mcp_server_transport_security (+16 more)

### Community 24 - "test_fingerprint.py"
Cohesion: 0.16
Nodes (16): hashlib, shutil, fingerprint(), subprocess, skipif, Focused browser-logic regressions for the dashboard stepper., test_ac_18_live_control_steps_and_transient_retry_copy(), test_ac_56_stepper_keeps_task_context_and_failure_states() (+8 more)

### Community 25 - "executor"
Cohesion: 0.18
Nodes (13): build(), executor(), Execute, build(), executor(), execute(), Execute, Execute (+5 more)

### Community 26 - "overhead.py"
Cohesion: 0.11
Nodes (19): bench, _main(), measure(), measure_mcp(), percentile(), _print(), Any, AC-28 (FR-21.1): healthy-call overhead of the registry over the raw transport.… (+11 more)

### Community 27 - "McpDriftServer"
Cohesion: 0.13
Nodes (11): _admin_tools(), McpDriftServer, call_tool(), list_tools(), Any, Server, Starlette, Mock drift MCP server implementing Contract 8. (+3 more)

### Community 28 - "Dashboard"
Cohesion: 0.13
Nodes (15): Side-by-Side Agent Comparison, Dashboard API Client, Dashboard Demo Simulator, Patch Log Renderer, Preset Runner, Benchmark Metrics, Candidate Builder, Dashboard (+7 more)

### Community 29 - "Heal Controller"
Cohesion: 0.13
Nodes (15): API Drift Explainer Landing Page, Machine-Readable Audit Log, Candidate Builder, Deterministic Tie-Breaker, Diagnoser, Break Fingerprint, Heal Controller, Jev Classifier (+7 more)

### Community 30 - "PostgresStore"
Cohesion: 0.16
Nodes (4): PostgresStore, Synchronous FixStore backed by Postgres; active reads always query committed…, pg_store(), fixture

### Community 31 - "Four-Person Ownership"
Cohesion: 0.14
Nodes (14): FixStore Contract, Four-Person Ownership, OperationSpec Contract, SpecSource Contract, Benchmark Metrics, MCP Proxy Flow, P1 MCP and Protocols Track, P2 Healing Core and Evidence Track (+6 more)

### Community 32 - "Research Notes"
Cohesion: 0.17
Nodes (12): Research Notes, AgentNoiseBench: Benchmarking Robustness of Tool-Using LLM Agents Under Noisy Condition, Automated Program Repair Based on REST API Specifications Using Large Language Models, CodeUpdateArena: Benchmarking Knowledge Editing on API Updates, Exploratory Analysis of the Structural Evolution of Public REST APIs, How Many Web APIs Evolve Following Semantic Versioning?, Reducing the Impact of Breaking Changes to Web Service Clients During Web API Evolution, Semantic Test Repair for Web Applications (+4 more)

### Community 33 - "Store"
Cohesion: 0.11
Nodes (3): Row, _fix(), Store

### Community 34 - "token_overhead"
Cohesion: 0.22
Nodes (6): FR-15.4 Token Overhead (healing) and wasted tokens (baseline): the mutated…, token_overhead(), AC-16: overhead = mutated total - CLEAN median, baseline waste beside it, the…, test_ac_16_token_overhead_against_clean_median_with_jev_in_its_own_column(), test_token_overhead_is_the_clean_median_difference_without_jev_tokens(), test_token_overhead_without_clean_runs_is_empty()

### Community 35 - "test_connections.py"
Cohesion: 0.10
Nodes (22): fastapi_testclient, MonkeyPatch, TestClient, cfg_file(), client(), fixture, parametrize, Path (+14 more)

### Community 36 - "test_client_config.py"
Cohesion: 0.22
Nodes (13): logging, mcp_client_streamable_http, sys, Opt-in client-config check, _connect(), _load_target(), Path, skipif (+5 more)

### Community 37 - "railway.json"
Cohesion: 0.25
Nodes (7): build, builder, dockerfilePath, deploy, healthcheckPath, restartPolicyType, $schema

### Community 38 - "Self-Healing Tool Registry"
Cohesion: 0.29
Nodes (7): Frozen Agent Schema, Safe Operation DSL, Safety Gate, Self-Healing Tool Registry, Verification and Postchecks, Wire Schema, Runtime API Schema Drift

### Community 39 - "Tool Registry"
Cohesion: 0.33
Nodes (6): Baseline Agent, Frozen Agent Schema, Healing Agent, Tool Registry, Wire Schema, Facade Pattern for Frozen Agent Tools

### Community 40 - "Benchmark Metrics"
Cohesion: 0.40
Nodes (5): Scripted Benchmark Results (N=3), Benchmark Metrics, False-Patch Rate, Mock Drift API, Zero-Touch Adaptation Rate (ZTAR)

### Community 41 - "Deterministic Candidate Tie-Breaker"
Cohesion: 0.50
Nodes (4): Compute Fixes Against Base Schema, Deterministic Candidate Tie-Breaker, Ordered Build Phases, Spec v3 Alignment

### Community 42 - "Benchmark Report"
Cohesion: 0.50
Nodes (4): Benchmark Report, 30-Second Pitch, Product Specification, Diagnosis and Patch Logic Write-Up

### Community 43 - "_coerce_args"
Cohesion: 0.13
Nodes (17): _coerce_args(), _heal_info(), _json_or_text(), _lossless_coerce(), _parse_tool_result(), Any, Cast a value to the type the frozen v1 schema declares, only if lossless., Fit LLM-supplied arguments to the frozen agent-facing schema. A live model… (+9 more)

### Community 44 - "Negative Cache"
Cohesion: 0.67
Nodes (3): Single-Attempt Healing, Negative Cache, Single-Flight Healing

### Community 45 - "FastAPI"
Cohesion: 0.67
Nodes (3): FastAPI, HTTPX, Pydantic

### Community 68 - "run.py"
Cohesion: 0.14
Nodes (26): _ablation_cell(), expectation(), _failure_mode(), mcp_section(), _outcome(), once(), _pick(), _rate() (+18 more)

### Community 69 - "ops.py"
Cohesion: 0.14
Nodes (24): get(), pop(), put(), Any, Path, _step(), OpName, _cast() (+16 more)

### Community 70 - "Reason"
Cohesion: 0.18
Nodes (27): Reason, test_m8_is_refused_without_inventing_a_value(), Any, parametrize, run(), test_cast_path_not_in_spec_is_unsafe_patch(), test_e5_fix_that_would_re_send_follows_the_replay_rule(), test_enum_map_destination_not_in_spec_is_unsafe_patch() (+19 more)

### Community 71 - "ErrorClass"
Cohesion: 0.16
Nodes (18): ErrorClass, StrEnum, test_ac_57_llm_run_records_detailed_offline_traces(), test_demo_runs_the_pitch_flow(), test_m5_heal_shows_its_fix_ops_and_the_baseline_hits_the_cap(), _assert_no_injection_in_requests(), test_ac_26_m10_injection_resistance(), test_ac_26_m10_matches_m1_parity() (+10 more)

### Community 72 - "FixStore"
Cohesion: 0.12
Nodes (4): Protocol, FixStore, What the registry, the healer and the demo call on a store. SQLite (`Store`)…, test_sqlite_store_implements_fix_store()

### Community 73 - "test_registry.py"
Cohesion: 0.21
Nodes (10): calls_to(), fix_for(), parametrize, test_ac_02_invalid_args_no_heal(), test_active_fix_request_ops_are_applied(), test_active_fix_response_ops_reshape_before_contract(), test_fr_3_4_value_rules_are_left_to_the_api(), test_healthy_call() (+2 more)

### Community 74 - "connections.py"
Cohesion: 0.13
Nodes (25): add_connection(), clean_entry(), config_path(), is_remote(), list_connections(), _load(), page(), Path (+17 more)

### Community 75 - "build_admin"
Cohesion: 0.15
Nodes (9): build_admin(), list_mutations(), mutations(), reset(), set_mutation(), check_custom(), MockApi, Validate a custom drift: one tool, any of rename / to_int / wrap / header /… (+1 more)

### Community 76 - "test_ops.py"
Cohesion: 0.17
Nodes (23): apply_ops(), cast_op(), parametrize, reason_of(), test_ac_41_enum_map_bijective_and_lossy(), test_ac_42_encoding_sets_content_type(), test_apply_ops_does_not_mutate_input(), test_cast_lossless() (+15 more)

### Community 77 - "api_registry"
Cohesion: 0.12
Nodes (20): BaseException, _api_client(), api_registry(), _api_source(), api_tool_config(), namespaced(), _open(), probe() (+12 more)

### Community 78 - "demo.py"
Cohesion: 0.36
Nodes (8): fix_text(), main(), print_act(), print_summary(), Terminal demo, the fallback for the pitch: `python -m dashboard.demo`. Scripted…, Run every act from a cold store; `step` is the agents' pause between calls., task_done(), itertools

### Community 79 - "test_http.py"
Cohesion: 0.15
Nodes (16): AsyncExitStack, create_http_app(), Starlette, _client(), http_app(), _initialize_body(), fixture, _session() (+8 more)

### Community 80 - "Any"
Cohesion: 0.16
Nodes (18): _dump_tools(), Any, asyncio, parametrize, AC-50 (T-RENAME): get_user renamed to fetch_user; calling get_user returns…, AC-50 (T-REQUIRED): update_email requires 'reason'; old call without 'reason'…, AC-50 (T-ENUM): email_type enum changed to uppercase; lowercase 'work' fails., AC-50 (M8): create_ticket requires priority; call without priority fails. (+10 more)

### Community 82 - "mcp/conftest.py"
Cohesion: 0.33
Nodes (7): pytest_asyncio, api(), mcp_client(), connect(), mcp_registry(), fixture, tools_config()

### Community 83 - "LoadedSpec"
Cohesion: 0.08
Nodes (29): mcp_source(), source(), OperationSpec, SpecSource, Read the upstream's tools/list. Names starting with `__` are reserved (admin…, to_operation(), sha256(), diff_signature() (+21 more)

### Community 84 - "models.py"
Cohesion: 0.12
Nodes (24): jsonschema, _payload(), Any, ClientSession, Upstream MCP servers as a protocol (contract 7): tools/list -> OperationSpec,…, send(), Candidate Builder (FR-7): diff entries or error clues in, candidate fix op…, dumps() (+16 more)

### Community 85 - "test_ac_43_repair_agent.py"
Cohesion: 0.21
Nodes (13): FakeLlm, asyncio, Exception, parametrize, AC-43 and AC-45: the tier-2 repair agent heals a break tier 1 cannot explain,…, Scripted model: returns `answer` and records every prompt it was sent., SlowLlm, test_ac_43_repair_agent_heals_unexplained_drift_and_fix_is_reused() (+5 more)

### Community 86 - "RepairAgent"
Cohesion: 0.15
Nodes (14): Llm, Default registry config: a tool is a write unless the upstream says it is read-…, tool_config(), One healing registry over one upstream server, exposing every tool it lists., upstream_registry(), from_env(), nim_llm(), AsyncClient (+6 more)

### Community 87 - "test_ac_34_cli_uses_real_custom_spec_and_closes_resources"
Cohesion: 0.15
Nodes (9): test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(), close(), __init__(), tracked_client(), test_ac_34_cli_uses_real_custom_spec_and_closes_resources(), close(), __init__(), tracked_client() (+1 more)

### Community 88 - "test_agents.py"
Cohesion: 0.08
Nodes (46): make_llm(), run(), ChatOpenAI, main(), ClientSession, Demo agent: one task over two upstream MCP servers, through the healer front…, Run the task once; returns calls, errors seen by the agent and the audit rows., Calls the front door, prints each call, and notes heals read from the shared… (+38 more)

### Community 90 - "test_ac_58_mcp_client_docs.py"
Cohesion: 0.24
Nodes (13): io, _json_blocks(), AC-58: docs/mcp-clients.md is a usable client guide derived from the hand-off…, The CLI flags the server actually accepts, read from its argparse help., _server_flags(), test_ac_58_covers_both_transports(), test_ac_58_documented_flags_exist_on_the_server(), test_ac_58_guide_is_derived_from_the_handoff() (+5 more)

### Community 91 - "test_stdio.py"
Cohesion: 0.19
Nodes (10): ClientSession, session(), parametrize, _schema_listing(), test_ac_30_list_maps_frozen_registry_tools_and_disables_list_changed(), test_ac_31_get_user_returns_healthy_data(), test_ac_32_heal_keeps_client_schema_stable_without_notification(), test_ac_33_m8_refusal_is_structured_and_does_not_invent_or_write() (+2 more)

### Community 92 - "Connecting MCP clients to the healer gateway"
Cohesion: 0.08
Nodes (23): 1. Install and start the mock API, 2. The stdio server command, 3. Streamable HTTP, 4. Remote deployment, 5. Adding an upstream server, 6. Known limits and outstanding checks, Claude Desktop (stdio), Connecting MCP clients to the healer gateway (+15 more)

### Community 93 - "gateway.py"
Cohesion: 0.26
Nodes (13): What the MCP front door exposes, read from the same `Registry.tools()`., _check_names(), connect_upstreams(), _http_url(), load_apis(), load_config(), Path, Many registries behind one frozen tool list: the shape the MCP front door… (+5 more)

### Community 94 - "graphql.py"
Cohesion: 0.07
Nodes (32): create_app(), GraphQLMock, update_email(), FastAPI, Small Strawberry GraphQL mock for protocol-drift tests., User, UserEnvelope, _arg_violations() (+24 more)

### Community 95 - "test_ac_38_registry_graphql_heals_and_keeps_schema_frozen"
Cohesion: 0.60
Nodes (5): _protocol_config(), asyncio, parametrize, test_ac_38_registry_graphql_heals_and_keeps_schema_frozen(), test_ac_38_registry_grpc_heals_and_keeps_schema_frozen()

### Community 96 - "p3/conftest.py"
Cohesion: 0.31
Nodes (9): api(), client(), make_registry(), make(), fixture, P3-owned fixtures. Mirrors `tests/integration/conftest.py` for the p3 track., Healing registry (store, no Jev, no real sleeping); keyword arguments override., store() (+1 more)

### Community 97 - "FakeLLM"
Cohesion: 0.18
Nodes (9): capturing_llm(), _generate(), fake_llm(), FakeLLM, llm_call(), AIMessage, GenericFakeChatModel, Offline fake that independently chooses the next response per conversation. (+1 more)

### Community 98 - "test_ac_47_precompute"
Cohesion: 0.22
Nodes (8): (FUTURE, X4) Precomputed fix allows the first failing call after a spec change…, Guard verification: Healer.precompute is never called automatically. When no…, (STRETCH, S1) Sibling propagation: a second tool hit by the same rename heals…, (STRETCH, S2) Rule mining: after 3 wins of the same pattern, subsequent…, test_ac_40_sibling_propagation(), test_ac_44_rule_mining(), test_ac_47_precompute(), test_precompute_guarded_when_no_watcher_exists()

### Community 99 - "false_patch_rate"
Cohesion: 0.12
Nodes (17): RunRow, false_patch_rate(), FR-15.4 False-Patch Rate: of the healed runs (a fix passed verification and…, FR-15.4 ZTAR: over `scenarios` only, the runs where the task completed and the…, FR-15.4 Safe-Refusal Rate: over the runs marked `must_refuse` (M8, and M6-N…, safe_refusal(), ztar(), AC-15: ZTAR 100% over the healable mutations with Jev absent, M6 separate,… (+9 more)

### Community 100 - "FakeClock"
Cohesion: 0.22
Nodes (8): clock(), db_path(), FakeClock, _open(), fixture, Path, test_candidate_fix_save_and_promote(), test_rule_mining_promotes_after_three_wins()

### Community 101 - "Registry"
Cohesion: 0.20
Nodes (6): Gateway, create_server(), Server, Expose registry tools and calls without adding healing behavior., Registry, main()

### Community 102 - "FixStatus"
Cohesion: 0.24
Nodes (11): FixStatus, make_fix(), _no_sleep(), test_ac_39_shared_active_fix_and_database_uniqueness(), test_ac_39_two_registries_reuse_m1_fix_at_tier0(), test_pg_concurrent_saves_leave_one_active_fix(), save(), test_pg_fix_active_and_candidate_round_trip_and_retired_read() (+3 more)

### Community 103 - "mcp_bench"
Cohesion: 0.20
Nodes (10): _amain(), bench(), mcp_bench(), mcp_state_ok(), _pass(), Namespace, One pass of the benchmark: scenarios x agents x n runs, optionally with a…, The main pass (FR-15.1, FR-15.6) and the error-only ablation (FR-15.7). (+2 more)

### Community 104 - "test_ac_68_mcp_view.py"
Cohesion: 0.19
Nodes (8): app(), client(), _front_door_tools(), offline(), fixture, AC-68: the dashboard MCP view reports the front door's tools (T2-9, no T1-6)., Build a clean registry the way the MCP server does, and read its tools., test_ac_68_endpoint_lists_exactly_the_front_door_tools()

### Community 105 - "sanitize"
Cohesion: 0.40
Nodes (5): FR-5.7: the audit blob keeps no secret. Redact, then truncate (so a cut cannot…, sanitize(), test_ac_24_raw_error_redacted(), test_sanitize_ignores_empty_secret_values(), test_sanitize_truncates_after_redacting()

### Community 106 - "send"
Cohesion: 0.50
Nodes (4): AsyncClient, Exception, Response, send()

### Community 110 - "test_ac_51_reset_and_profiles.py"
Cohesion: 0.26
Nodes (12): _dump_tools(), Any, asyncio, parametrize, AC-51 / Contract 8: admin tools (__admin_apply, __admin_list, __admin_reset)…, AC-51: reset restores tools/list byte for byte after any mutation., AC-51: reset restores in-memory users and tickets to SEED state., AC-51: profile='tickets' lists a different toolset than profile='users'. (+4 more)

### Community 111 - "record_mcp_fixtures.py"
Cohesion: 0.20
Nodes (9): Path, T1-7: record `tools/list` before and after each mutation (AC-52). Writes…, record(), _tools(), asyncio, parametrize, AC-52: every recorded MCP drift fixture loads, and its tools differ before and…, test_ac_52_fixture_loads_and_differs() (+1 more)

### Community 112 - "detect.py"
Cohesion: 0.29
Nodes (11): classify(), _error_body(), _is_soft_error(), _kind(), Exception, Response, Response classification (technical-approach 5.1, steps 1-5). Schema and…, FR-3.4: a 422 type that says the value is bad becomes a value kind; all others… (+3 more)

### Community 113 - "_serve"
Cohesion: 0.20
Nodes (8): from_env(), JEV_API_KEY (+ JEV_URL, JEV_MODEL) for TypeSafe direct, else Jev via…, _arguments(), main(), Namespace, _serve(), test_ac_35_http_cli_defaults_and_token_environment_validation(), test_from_env_prefers_direct_key_then_openrouter_then_none()

### Community 114 - "test_ac_63_mcp_gateway.py"
Cohesion: 0.31
Nodes (10): asyncio, parametrize, AC-63 to AC-66: upstream MCP servers behind the gateway, healed through the…, test_ac_63_healthy_call_and_unknown_tool(), test_ac_63_tools_are_namespaced_merged_and_hide_admin_tools(), test_ac_64_precompute_prepares_mcp_fix_before_any_failure(), test_ac_64_upstream_drift_heals_with_frozen_schema(), test_ac_65_business_error_is_not_healed() (+2 more)

### Community 115 - "guide.js"
Cohesion: 0.47
Nodes (6): close(), onKey(), open(), openTab(), place(), show()

### Community 116 - "JevClient"
Cohesion: 0.22
Nodes (5): SpecSource, JevClient, AsyncClient, AsyncClient, SpecSource

### Community 117 - "run_live"
Cohesion: 0.28
Nodes (9): completed(), parametrize, Run the demo task once; returns (RunResult, mock api, [(tool, class), ...])., New email, manager 456, one ticket, and the lookup itself succeeded., run_live(), test_ac_09_agent_stops_after_retry_false(), test_clean_run_completes(), test_m5_baseline_agent_does_not_complete() (+1 more)

### Community 118 - "make_tools"
Cohesion: 0.29
Nodes (6): make_tools(), tool(), Execute, One tool per registry spec; both agents differ only in `execute`. Logs each…, registry_call(), StructuredTool

### Community 119 - "drifted"
Cohesion: 0.33
Nodes (5): drifted(), _custom_model(), _header_dep(), Undo the drift on a valid request so the v1 handler can serve it., _to_v1()

### Community 120 - "RepairUnavailable"
Cohesion: 0.33
Nodes (5): _json_object(), Exception, The model's proposal and its token count. {"operation": None} means no safe fix., No model, a transport error, or an answer that is not a usable proposal., RepairUnavailable

### Community 121 - "gateway_factory"
Cohesion: 0.40
Nodes (5): gateway_factory(), build(), fixture, A Gateway over in-memory upstream drift servers: {"users": drift, "tickets":…, _session()

### Community 122 - "extract_tool_schemas"
Cohesion: 0.50
Nodes (3): extract_tool_schemas(), Extract input and output schemas from a resolved OpenAPI spec for each…, _agent_schema()

## Knowledge Gaps
- **79 isolated node(s):** `healer`, `$schema`, `builder`, `dockerfilePath`, `healthcheckPath` (+74 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 661 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **28 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Reason` connect `Reason` to `HealOutcome`, `test_candidates.py`, `test_ac_47_precompute`, `run.py`, `ops.py`, `ErrorClass`, `test_ops.py`, `test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal`, `Tier`, `test_bench.py`, `test_scenarios.py`, `models.py`, `Healer`, `registry.py`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `ErrorClass` connect `ErrorClass` to `HealOutcome`, `test_jev.py`, `test_store.py`, `grpc.py`, `Tier`, `test_scenarios.py`, `test_detect.py`, `run_explore`, `Healer`, `registry.py`, `test_fingerprint.py`, `executor`, `PostgresStore`, `Store`, `ops.py`, `Reason`, `FixStore`, `test_registry.py`, `models.py`, `graphql.py`, `test_ac_47_precompute`, `Registry`, `FixStatus`, `detect.py`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `Dashboard` connect `Dashboard` to `Store`, `Registry`, `test_dashboard.py`, `create_app`, `Tier`, `demo.py`, `test_explorer.py`, `registry.py`, `gateway.py`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 97 inferred relationships involving `Reason` (e.g. with `expectation()` and `build()`) actually correct?**
  _`Reason` has 97 INFERRED edges - model-reasoned connections that need verification._
- **Are the 74 inferred relationships involving `ErrorClass` (e.g. with `executor()` and `executor()`) actually correct?**
  _`ErrorClass` has 74 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `Store` (e.g. with `measure_mcp()` and `mcp_bench()`) actually correct?**
  _`Store` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 56 inferred relationships involving `HealOutcome` (e.g. with `_ablation_cell()` and `mcp_section()`) actually correct?**
  _`HealOutcome` has 56 INFERRED edges - model-reasoned connections that need verification._