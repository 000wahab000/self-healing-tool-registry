# Graph Report - self-healing-tool-registry  (2026-10-16)

## Corpus Check
- 150 files · ~119,816 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 5, .example 1, .css 1)

## Summary
- 2078 nodes · 5111 edges · 119 communities (100 shown, 19 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 664 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Candidates Tests
- Spec Watcher Tests
- Heal Scenario Tests
- MCP Mutation Server
- JEV Tests
- Diagnose Tests
- Connection Manager
- Healing Controller
- Swagger Loader
- Dashboard Tests
- Mock API Tests
- MCP Fixture Recorder
- Safety Tests
- MCP Gateway
- gRPC Loader
- Patch Operations
- Overhead Benchmark
- Mock API Schemas
- Store Tests
- Core Healing Metrics
- Agent Runtime
- Fingerprint Tests
- Scenarios Tests
- MCP Server
- PostgreSQL Store
- SQLite Fix Store
- Ops Tests
- Connection Tests
- Explorer API Tests
- HTTP MCP Tests
- Advanced Healing Setup
- Dashboard State
- OpenAPI Loader
- FixStore Contract
- Bench Tests
- Common Agent
- Spec Diagnosis
- Fixtures
- Benchmark Report Builder
- Project Documentation
- Agent Run Tests
- Explorer Query Logic
- Dashboard API
- MCP Agent Demo
- Retry Tests
- Tool Argument Casting
- Mock API Admin
- Admin Tests
- Safety Metrics
- MCP Lifecycle Tests
- AC 43 Tests
- Client Config MCP Tests
- Contract Validation
- MCP Schema Tests
- Registry Tests
- Dashboard Features
- AC 58 Tests
- Agents Live Tests
- Mock API Operations
- MCP Repair Registry
- Contracts Tests
- AC 68 Tests
- Response Classifier
- Detect Tests
- MCP Clients Guide
- P3 Fixtures
- AC 63 Tests
- AC 52 Tests
- Benchmark Results
- Dashboard Guide
- MCP Benchmark Run
- Dashboard Demo
- MCP Fixtures
- Token Cost Metrics
- Contract Tests
- Benchmark CLI
- MCP Product Roadmap
- Railway Documentation
- Agent Test Fixtures
- Heal Audit Invariants
- Frozen Registry Contract
- Scenario Runner
- Heal Pipeline
- Spec Change Watcher
- Dashboard UI
- Retry Policy
- LLM Repair Proposal
- Safety Invariants
- Safety Design
- Error Classification Flow
- Core Product Requirements
- LLM Tool Tests
- Heal Timing Tests
- Registry Protocols Protocol Tests
- REST Adapter
- Clock Test Fixtures
- MCP Probe Tests
- Loader Contracts
- Connection Setup UI
- Dashboard Landing
- Dashboard Requirements
- Core Dependencies
- LLM Failure Tests
- Store Contract
- Spec Source Contract
- Init Demo
- Benchmark Targets
- LLM Dependencies
- Rule Mining Tests
- Live Dashboard UI
- Pyproject Documentation
- JSON Schema Dependency
- Environment Config Dependency
- ASGI Server Dependency

## God Nodes (most connected - your core abstractions)
1. `Reason` - 111 edges
2. `ErrorClass` - 95 edges
3. `Store` - 66 edges
4. `HealOutcome` - 65 edges
5. `Side` - 55 edges
6. `Registry` - 49 edges
7. `Healer` - 47 edges
8. `Tier` - 47 edges
9. `Outcome` - 43 edges
10. `DecisionPath` - 39 edges

## Surprising Connections (you probably didn't know these)
- `test_fr_6_4_spec_mode_must_be_on_or_off()` --uses--> `Registry`  [INFERRED]
  tests/integration/test_heal.py → src/healer/registry.py
- `executor()` --uses--> `ErrorClass`  [INFERRED]
  agents/baseline_agent.py → src/healer/models.py
- `executor()` --uses--> `ErrorClass`  [INFERRED]
  agents/healing_agent.py → src/healer/models.py
- `execute()` --calls--> `ErrorClass`  [EXTRACTED]
  agents/healing_agent.py → src/healer/models.py
- `run()` --uses--> `ErrorClass`  [INFERRED]
  agents/scripted.py → src/healer/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Benchmark recovery and safety metrics** — bench_report_zero_touch_adaptation_rate, bench_report_safe_refusal_rate, bench_report_false_patch_rate, bench_report_mttr_and_internal_heal_ms, bench_report_baseline_comparison [EXTRACTED 1.00]

## Communities (119 total, 19 thin omitted)

### Community 0 - "Candidates Tests"
Cohesion: 0.06
Nodes (98): Option, _assign(), build(), _cast(), _clue_fills(), _clue_response_ops(), _described(), _dry_run() (+90 more)

### Community 1 - "Spec Watcher Tests"
Cohesion: 0.05
Nodes (42): mcp_source(), source(), ClientSession, OperationSpec, SpecSource, Read the upstream's tools/list. Names starting with `__` are reserved (admin…, to_operation(), load() (+34 more)

### Community 2 - "Heal Scenario Tests"
Cohesion: 0.09
Nodes (50): DecisionPath, HealOutcome, test_ac_26_m10_matches_m1_parity(), calls_to(), jev_reply(), m1_fix(), override(), Request (+42 more)

### Community 3 - "MCP Mutation Server"
Cohesion: 0.06
Nodes (42): mcp_shared_exceptions, _admin_tools(), McpDriftServer, call_tool(), list_tools(), Any, Server, Starlette (+34 more)

### Community 4 - "JEV Tests"
Cohesion: 0.07
Nodes (46): from_env(), JevChoice, JevUnavailable, Exception, Prefer TypeSafe direct, then OpenRouter, then opt-in OpenCode free Jev., Timeout, transport or HTTP error, or an answer that is not one of our options., render_option(), render_state() (+38 more)

### Community 5 - "Diagnose Tests"
Cohesion: 0.07
Nodes (43): GraphQLMock, update_email(), FastAPI, Small Strawberry GraphQL mock for protocol-drift tests., User, UserEnvelope, diff(), flatten_request() (+35 more)

### Community 6 - "Connection Manager"
Cohesion: 0.06
Nodes (47): add_connection(), clean_entry(), config_path(), is_remote(), list_connections(), _load(), page(), Path (+39 more)

### Community 7 - "Healing Controller"
Cohesion: 0.12
Nodes (21): Future, _Abort, _Heal, Healer, Any, SpecSource, The agent's result: data when recovered, an error dict otherwise., Gate, optional dry run, verify, commit: the same path for every tier. (+13 more)

### Community 8 - "Swagger Loader"
Cohesion: 0.07
Nodes (40): fetch_spec(), _json_schema(), load(), operations(), AsyncClient, OperationSpec, Inline every local `#/...` ref; keywords next to a $ref override the target's., resolve_refs() (+32 more)

### Community 9 - "Dashboard Tests"
Cohesion: 0.07
Nodes (38): langchain_core_language_models_fake_chat_models, langchain_core_messages, langchain_core_outputs, langchain_core_utils_function_calling, calls(), capturing_llm(), _generate(), client() (+30 more)

### Community 10 - "Mock API Tests"
Cohesion: 0.11
Nodes (36): api(), client(), deref(), errors(), get_spec(), lookup_args(), operation(), params() (+28 more)

### Community 11 - "MCP Fixture Recorder"
Cohesion: 0.09
Nodes (32): argparse, asyncio, An in-memory MCP client session over a mock drift server (shared by the MCP…, T1-7: record `tools/list` before and after each mutation (AC-52). Writes…, contextlib, mcp, mcp_server_lowlevel, mcp_server_transport_security (+24 more)

### Community 12 - "Safety Tests"
Cohesion: 0.13
Nodes (37): ErrorClass, Reason, jev_ok(), _event(), StrEnum, test_demo_runs_the_pitch_flow(), test_m8_is_refused_without_inventing_a_value(), test_c2_missing_record_is_not_drift() (+29 more)

### Community 13 - "MCP Gateway"
Cohesion: 0.10
Nodes (32): BaseException, What the MCP front door exposes, read from the same `Registry.tools()`., _api_client(), api_registry(), _api_source(), api_tool_config(), _check_names(), connect_upstreams() (+24 more)

### Community 14 - "gRPC Loader"
Cohesion: 0.08
Nodes (30): FileDescriptorProto, google_protobuf, grpc_reflection_v1alpha, create_server(), _file(), Any, DescriptorPool, Small unary gRPC drift fixture with reflection and rich validation errors. (+22 more)

### Community 15 - "Patch Operations"
Cohesion: 0.13
Nodes (29): copy, Candidate Builder (FR-7): diff entries or error clues in, candidate fix op…, get(), pop(), put(), Any, Path, Canonical JSON, hashing and path helpers for nested dict/list documents. (+21 more)

### Community 16 - "Overhead Benchmark"
Cohesion: 0.08
Nodes (26): bench, _main(), measure(), measure_mcp(), percentile(), _print(), Any, AC-28 (FR-21.1): healthy-call overhead of the registry over the raw transport.… (+18 more)

### Community 17 - "Mock API Schemas"
Cohesion: 0.10
Nodes (32): fastapi_exceptions, fastapi_security, drifted(), _custom_model(), CustomerRef, CustomerRefM10, EmailOut, _header_dep() (+24 more)

### Community 18 - "Store Tests"
Cohesion: 0.13
Nodes (31): FR-5.7: the audit blob keeps no secret. Redact, then truncate (so a cut cannot…, sanitize(), clock(), db_path(), FakeClock, make_fix(), open_store(), _open() (+23 more)

### Community 19 - "Core Healing Metrics"
Cohesion: 0.11
Nodes (31): IntEnum, mttr_summary(), outcome_counts(), percentiles(), Any, Benchmark metrics (FR-15.4, FR-15.5) over audit events and benchmark run rows.…, FR-15.5, per scenario and agent: mean/p50/p95 of `llm_tokens` per run and of…, FR-15.5: count, mean, median (p50) and nearest-rank p95 of one sample. (+23 more)

### Community 20 - "Agent Runtime"
Cohesion: 0.12
Nodes (23): agents, Baseline agent: same tools, but each call is a bare v1 HTTP request. No…, Shared agent pieces: prompt, task, LLM, tool factory and the run loop., RunResult, Healing agent: every tool call goes through the self-healing `Registry`., Scripted agent: the demo task as fixed tool calls. No LLM and no tokens. It…, ExploreIn, MutationIn (+15 more)

### Community 21 - "Fingerprint Tests"
Cohesion: 0.13
Nodes (28): google_rpc, hashlib, json, classify(), Any, Descriptor, Exception, Unary gRPC adapter and machine-readable status normalization. (+20 more)

### Community 22 - "Scenarios Tests"
Cohesion: 0.11
Nodes (28): assert_first_heal(), call_for(), calls_to(), check_m1(), check_m2(), check_m4(), check_m5(), check_m9() (+20 more)

### Community 23 - "MCP Server"
Cohesion: 0.09
Nodes (15): Gateway, JevClient, AsyncClient, _arguments(), create_server(), main(), Namespace, Server (+7 more)

### Community 24 - "PostgreSQL Store"
Cohesion: 0.11
Nodes (14): PostgresStore, Synchronous FixStore backed by Postgres; active reads always query committed…, pg_store(), fixture, make_fix(), _no_sleep(), test_ac_39_shared_active_fix_and_database_uniqueness(), test_ac_39_two_registries_reuse_m1_fix_at_tier0() (+6 more)

### Community 25 - "SQLite Fix Store"
Cohesion: 0.11
Nodes (4): Row, _fix(), Store, test_sqlite_store_implements_fix_store()

### Community 26 - "Ops Tests"
Cohesion: 0.17
Nodes (23): apply_ops(), cast_op(), parametrize, reason_of(), test_ac_41_enum_map_bijective_and_lossy(), test_ac_42_encoding_sets_content_type(), test_apply_ops_does_not_mutate_input(), test_cast_lossless() (+15 more)

### Community 27 - "Connection Tests"
Cohesion: 0.13
Nodes (18): fastapi_testclient, MonkeyPatch, TestClient, cfg_file(), client(), fixture, parametrize, Path (+10 more)

### Community 28 - "Explorer API Tests"
Cohesion: 0.09
Nodes (8): client(), offline(), fixture, parametrize, Tests for the Explorer endpoints (/api/explorer/info and /api/explore)., M6-N refuses set_manager (step 3); the agent still opens the ticket (step 4)., test_explore_controls_pass_business_errors_through(), test_explore_refused_tool_is_skipped_and_the_task_continues()

### Community 29 - "HTTP MCP Tests"
Cohesion: 0.15
Nodes (16): AsyncExitStack, create_http_app(), Starlette, _client(), http_app(), _initialize_body(), fixture, _session() (+8 more)

### Community 30 - "Advanced Healing Setup"
Cohesion: 0.15
Nodes (15): collections_abc, Enum, inspect, logging, FixStatus, Enums and records shared across modules. Stdlib only., Spec watcher (T2-7, FR-18): poll each SpecSource, snapshot changes, feed…, _in() (+7 more)

### Community 31 - "Dashboard State"
Cohesion: 0.17
Nodes (5): Dashboard, A scenario (and a live-LLM one can take minutes) holds the lock for its whole…, Once both agents finish an LLM run, remember the measured token pair., What the registry kept away from the agents, since the last Reset. Counted from…, Both agents run the demo task against their own mock; the store is shared.

### Community 32 - "OpenAPI Loader"
Cohesion: 0.13
Nodes (12): httpx, pathlib, re, REST adapter: send a request document (contract C1), return the raw result., Load GraphQL operations from an endpoint's standard introspection result., _is_bearer(), Fetch an OpenAPI 3.x spec, inline its local $refs, and index its operations., _security() (+4 more)

### Community 33 - "FixStore Contract"
Cohesion: 0.10
Nodes (4): Protocol, AuditEvent, FixStore, What the registry, the healer and the demo call on a store. SQLite (`Store`)…

### Community 34 - "Bench Tests"
Cohesion: 0.16
Nodes (20): agent_rows(), main(), one(), fixture, parametrize, Benchmark runner and report tests (FR-15.1 to 15.8; AC-14, AC-15, AC-16, AC-17,…, AC-17: error loop, calls, tokens and final data are measured per scenario and…, The text from one `##` heading to the next (or the end of the report). (+12 more)

### Community 35 - "Common Agent"
Cohesion: 0.11
Nodes (19): build(), executor(), Execute, make_tools(), tool(), Execute, One tool per registry spec; both agents differ only in `execute`. Logs each…, build() (+11 more)

### Community 36 - "Spec Diagnosis"
Cohesion: 0.14
Nodes (17): dumps(), sha256(), abstract_signature(), diff_signature(), Spec diagnosis: flatten operations into leaves and diff them (FR-6.1,…, FR-17.8: abstract structural signature with roles replacing concrete names., _arg_types(), _dotted() (+9 more)

### Community 37 - "Fixtures"
Cohesion: 0.15
Nodes (17): api(), client(), jev(), make_registry(), make(), AsyncBaseTransport, fixture, Request (+9 more)

### Community 38 - "Benchmark Report Builder"
Cohesion: 0.20
Nodes (19): _ablation_cell(), _failure_mode(), mcp_section(), _outcome(), _pick(), _rate(), Benchmark runner and report (plan.md phase 10, metrics per phase 12D / FR-15).…, The "## MCP gateway" report section (T1-8, T1-9). (+11 more)

### Community 39 - "Project Documentation"
Cohesion: 0.19
Nodes (19): Coding Agent Rules, Module Contracts and Working Rules, End-to-End System Flow, Project Pitch, Project Status and Next Steps, Product Requirements Specification, Self-Healing Gateway README, AgentNoiseBench (+11 more)

### Community 40 - "Agent Run Tests"
Cohesion: 0.33
Nodes (18): run(), build(), call(), call_rows(), last_tool_result(), llm(), AIMessage, parametrize (+10 more)

### Community 41 - "Explorer Query Logic"
Cohesion: 0.11
Nodes (17): check_data_correctness(), extract_tool_schemas(), _heal_summaries(), _llm_bootstrap_error(), Extract input and output schemas from a resolved OpenAPI spec for each…, Verify mock API state against expected values. `touched` restricts the verdict…, Provider errors arrive as a page of JSON; the UI only needs the headline., Read-only view of every ToolDefinition after the run. (+9 more)

### Community 42 - "Dashboard API"
Cohesion: 0.12
Nodes (7): bad_request(), create_app(), explorer_info(), mutation(), start(), FastAPI, get_explorer_info()

### Community 43 - "MCP Agent Demo"
Cohesion: 0.17
Nodes (12): main(), ClientSession, Demo agent: one task over two upstream MCP servers, through the healer front…, Run the task once; returns calls, errors seen by the agent and the audit rows., Calls the front door, prints each call, and notes heals read from the shared…, LangGraph ReAct agent whose tools are the front door's tools (same shape as…, run_demo(), run_llm() (+4 more)

### Community 44 - "Retry Tests"
Cohesion: 0.19
Nodes (13): hinted(), parametrize, Attempt callable that replays a fixed list of outcomes and records sleeps., Script, test_backoff_sequence_then_gives_up_after_three_retries(), test_budget_shrinks_between_retries(), test_default_jitter_stays_within_bound(), test_jitter_is_added_to_each_backoff() (+5 more)

### Community 45 - "Tool Argument Casting"
Cohesion: 0.13
Nodes (17): _coerce_args(), _heal_info(), _json_or_text(), _lossless_coerce(), _parse_tool_result(), Any, Cast a value to the type the frozen v1 schema declares, only if lossless., Fit LLM-supplied arguments to the frozen agent-facing schema. A live model… (+9 more)

### Community 46 - "Mock API Admin"
Cohesion: 0.15
Nodes (9): build_admin(), list_mutations(), mutations(), reset(), set_mutation(), check_custom(), MockApi, Validate a custom drift: one tool, any of rename / to_int / wrap / header /… (+1 more)

### Community 47 - "Admin Tests"
Cohesion: 0.15
Nodes (8): create_app(), socket, api(), client(), fixture, test_real_http_switch_to_m1(), threading, uvicorn

### Community 48 - "Safety Metrics"
Cohesion: 0.13
Nodes (15): RunRow, false_patch_rate(), FR-15.4 False-Patch Rate: of the healed runs (a fix passed verification and…, FR-15.4 ZTAR: over `scenarios` only, the runs where the task completed and the…, FR-15.4 Safe-Refusal Rate: over the runs marked `must_refuse` (M8, and M6-N…, safe_refusal(), ztar(), AC-15: ZTAR 100% over the healable mutations with Jev absent, M6 separate,… (+7 more)

### Community 49 - "MCP Lifecycle Tests"
Cohesion: 0.15
Nodes (9): test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(), close(), __init__(), tracked_client(), test_ac_34_cli_uses_real_custom_spec_and_closes_resources(), close(), __init__(), tracked_client() (+1 more)

### Community 50 - "AC 43 Tests"
Cohesion: 0.21
Nodes (13): FakeLlm, asyncio, Exception, parametrize, AC-43 and AC-45: the tier-2 repair agent heals a break tier 1 cannot explain,…, Scripted model: returns `answer` and records every prompt it was sent., SlowLlm, test_ac_43_repair_agent_heals_unexplained_drift_and_fix_is_reused() (+5 more)

### Community 51 - "Client Config MCP Tests"
Cohesion: 0.18
Nodes (14): dotenv, mcp_client_stdio, mcp_client_streamable_http, sys, _connect(), _load_target(), Path, skipif (+6 more)

### Community 52 - "Contract Validation"
Cohesion: 0.20
Nodes (12): dataclasses, jsonschema, check(), _passes(), Any, Output-schema validation (E5) and declarative postchecks (E6) on an OK outcome., _schema_violations(), api_error() (+4 more)

### Community 53 - "MCP Schema Tests"
Cohesion: 0.19
Nodes (10): ClientSession, session(), parametrize, _schema_listing(), test_ac_30_list_maps_frozen_registry_tools_and_disables_list_changed(), test_ac_31_get_user_returns_healthy_data(), test_ac_32_heal_keeps_client_schema_stable_without_notification(), test_ac_33_m8_refusal_is_structured_and_does_not_invent_or_write() (+2 more)

### Community 54 - "Registry Tests"
Cohesion: 0.21
Nodes (10): calls_to(), fix_for(), parametrize, test_ac_02_invalid_args_no_heal(), test_active_fix_request_ops_are_applied(), test_active_fix_response_ops_reshape_before_contract(), test_fr_3_4_value_rules_are_left_to_the_api(), test_healthy_call() (+2 more)

### Community 55 - "Dashboard Features"
Cohesion: 0.14
Nodes (14): Mock drift control contract, Benchmark report view, Live stream comparison, Metrics view, Mutation controls, Benchmark pipeline, Dashboard, Mock drift control (+6 more)

### Community 56 - "AC 58 Tests"
Cohesion: 0.24
Nodes (13): io, _json_blocks(), AC-58: docs/mcp-clients.md is a usable client guide derived from the hand-off…, The CLI flags the server actually accepts, read from its argparse help., _server_flags(), test_ac_58_covers_both_transports(), test_ac_58_documented_flags_exist_on_the_server(), test_ac_58_guide_is_derived_from_the_handoff() (+5 more)

### Community 57 - "Agents Live Tests"
Cohesion: 0.18
Nodes (13): make_llm(), ChatOpenAI, test_make_llm_uses_nvidia_key_and_model_override(), test_make_llm_uses_nvidia_nim_defaults(), completed(), parametrize, Run the demo task once; returns (RunResult, mock api, [(tool, class), ...])., New email, manager 456, one ticket, and the lookup itself succeeded. (+5 more)

### Community 58 - "Mock API Operations"
Cohesion: 0.18
Nodes (9): Header, min_length, build(), manager_ids(), set_manager(), update_email(), validate_manager(), FastAPI (+1 more)

### Community 59 - "MCP Repair Registry"
Cohesion: 0.18
Nodes (11): Llm, Default registry config: a tool is a write unless the upstream says it is read-…, tool_config(), One healing registry over one upstream server, exposing every tool it lists., upstream_registry(), from_env(), nim_llm(), AsyncClient (+3 more)

### Community 60 - "Contracts Tests"
Cohesion: 0.19
Nodes (11): openapi_source(), SpecSource, The default `SpecSource`: the API's OpenAPI 3 document at `path`., _keys(), Step 0 contracts between the two tracks (AGENTS.md): OperationSpec, SpecSource,…, Contract 4: Registry exposes tools() and passes tools accessor to Healer., Contract 5: P4's watcher calls Healer.precompute(old: LoadedSpec, new:…, test_contract_4_registry_exposes_tools_accessor() (+3 more)

### Community 61 - "AC 68 Tests"
Cohesion: 0.19
Nodes (8): app(), client(), _front_door_tools(), offline(), fixture, AC-68: the dashboard MCP view reports the front door's tools (T2-9, no T1-6)., Build a clean registry the way the MCP server does, and read its tools., test_ac_68_endpoint_lists_exactly_the_front_door_tools()

### Community 62 - "Response Classifier"
Cohesion: 0.29
Nodes (11): classify(), _error_body(), _is_soft_error(), _kind(), Exception, Response, Response classification (technical-approach 5.1, steps 1-5). Schema and…, FR-3.4: a 422 type that says the value is bad becomes a value kind; all others… (+3 more)

### Community 63 - "Detect Tests"
Cohesion: 0.29
Nodes (10): parametrize, Response, r(), raw(), raw_status(), req(), test_ac_03_detector_table(), test_data_carries_decoded_body() (+2 more)

### Community 64 - "MCP Clients Guide"
Cohesion: 0.24
Nodes (11): MCP client connection guide, Namespaced upstream tools, Real-client UI checks outstanding, Remote MCP deployment security requirements, Stdio client setup, Streamable HTTP client setup, Upstream MCP server configuration, Client config can launch trusted commands (+3 more)

### Community 65 - "P3 Fixtures"
Cohesion: 0.31
Nodes (9): api(), client(), make_registry(), make(), fixture, P3-owned fixtures. Mirrors `tests/integration/conftest.py` for the p3 track., Healing registry (store, no Jev, no real sleeping); keyword arguments override., store() (+1 more)

### Community 66 - "AC 63 Tests"
Cohesion: 0.31
Nodes (10): asyncio, parametrize, AC-63 to AC-66: upstream MCP servers behind the gateway, healed through the…, test_ac_63_healthy_call_and_unknown_tool(), test_ac_63_tools_are_namespaced_merged_and_hide_admin_tools(), test_ac_64_precompute_prepares_mcp_fix_before_any_failure(), test_ac_64_upstream_drift_heals_with_frozen_schema(), test_ac_65_business_error_is_not_healed() (+2 more)

### Community 67 - "AC 52 Tests"
Cohesion: 0.22
Nodes (8): Path, record(), _tools(), asyncio, parametrize, AC-52: every recorded MCP drift fixture loads, and its tools differ before and…, test_ac_52_fixture_loads_and_differs(), test_ac_52_fixtures_match_a_fresh_recording()

### Community 68 - "Benchmark Results"
Cohesion: 0.27
Nodes (10): Baseline comparison, False-Patch Rate, Healthy MCP-call overhead, LLM token cost not measured, MCP heal evidence: 12/12, MTTR and internal heal_ms, REST heal evidence: 21/21, Safe-Refusal Rate (+2 more)

### Community 69 - "Dashboard Guide"
Cohesion: 0.44
Nodes (7): close(), go(), onKey(), open(), openTab(), place(), show()

### Community 70 - "MCP Benchmark Run"
Cohesion: 0.22
Nodes (8): mcp_bench(), mcp_state_ok(), Only user 123's email may differ from the seed, and at most the one expected…, The scripted MCP task per drift-server mutation, through a healing gateway and…, asyncio, AC-54: MCP drift scenarios in the benchmark: heal, refuse safely, never false-…, test_ac_54_mcp_scenarios(), test_ac_54_report_has_mcp_section()

### Community 71 - "Dashboard Demo"
Cohesion: 0.36
Nodes (8): fix_text(), main(), print_act(), print_summary(), Terminal demo, the fallback for the pitch: `python -m dashboard.demo`. Scripted…, Run every act from a cold store; `step` is the agents' pause between calls., task_done(), itertools

### Community 72 - "MCP Fixtures"
Cohesion: 0.33
Nodes (7): pytest_asyncio, api(), mcp_client(), connect(), mcp_registry(), fixture, tools_config()

### Community 73 - "Token Cost Metrics"
Cohesion: 0.22
Nodes (6): FR-15.4 Token Overhead (healing) and wasted tokens (baseline): the mutated…, token_overhead(), AC-16: overhead = mutated total - CLEAN median, baseline waste beside it, the…, test_ac_16_token_overhead_against_clean_median_with_jev_in_its_own_column(), test_token_overhead_is_the_clean_median_difference_without_jev_tokens(), test_token_overhead_without_clean_runs_is_empty()

### Community 74 - "Contract Tests"
Cohesion: 0.39
Nodes (7): check(), parametrize, test_each_missing_property_is_reported_once(), test_non_ok_outcome_is_untouched(), test_postchecks(), test_schema_failure_wins_over_postcheck_and_keeps_data(), test_schema_violation_path_is_the_instance_path()

### Community 75 - "Benchmark CLI"
Cohesion: 0.25
Nodes (8): _amain(), bench(), main(), _pass(), Namespace, One pass of the benchmark: scenarios x agents x n runs, optionally with a…, The main pass (FR-15.1, FR-15.6) and the error-only ablation (FR-15.7)., out()

### Community 76 - "MCP Product Roadmap"
Cohesion: 0.25
Nodes (8): MCP front-door view, Gateway, MCP Front Door, Built MCP gateway and APIs, Deferred GraphQL, gRPC, Postgres, and streaming work, AC-63 namespaced frozen upstream tools, F24 Upstream MCP gateway, System boundaries and deferred protocols

### Community 77 - "Railway Documentation"
Cohesion: 0.25
Nodes (7): build, builder, dockerfilePath, deploy, healthcheckPath, restartPolicyType, $schema

### Community 78 - "Agent Test Fixtures"
Cohesion: 0.25
Nodes (8): api(), client(), db_path(), fixture, registry(), store(), fixture, setup()

### Community 79 - "Heal Audit Invariants"
Cohesion: 0.29
Nodes (7): Audit before returning heal result, Secrets excluded from store and logs, Patch log, One audit row per heal attempt, SQLite fix and audit store, AC-5 exactly one audit event per heal, F5 Store and audit

### Community 80 - "Frozen Registry Contract"
Cohesion: 0.29
Nodes (7): Frozen agent_schema invariant, Registry.tools() and Registry.call() contract, Frozen agent_schema, Registry, tools/call, tools/list, Facade and hot-patching

### Community 81 - "Scenario Runner"
Cohesion: 0.29
Nodes (7): expectation(), once(), What one run of `scenario` owes: a completed task, a safe refusal or a pass-…, FR-15.2: the final mock data state holds only expected writes. Every scenario…, state_ok(), steps_for(), task_done()

### Community 82 - "Heal Pipeline"
Cohesion: 0.33
Nodes (6): One heal and one replay; no retry loop, Contract verification, Spec diagnosis, Heal pipeline, F10 Patch, verify, commit, Healing tiers 0, 1, Jev, and 2

### Community 83 - "Spec Change Watcher"
Cohesion: 0.33
Nodes (6): Spec-change hook, Spec-change precompute, Spec watcher, Built spec watcher, AC-55 spec watcher behavior, F18 Spec watcher

### Community 84 - "Dashboard UI"
Cohesion: 0.67
Nodes (5): apply(), init(), read(), toggles(), write()

### Community 85 - "Retry Policy"
Cohesion: 0.33
Nodes (4): random, E1 retry policy (FR-11.1): bounded backoff with jitter. E1 is retried here and…, Run `attempt`, then retry E1 up to len(E1_BACKOFF_S) times while the budget…, with_retries()

### Community 86 - "LLM Repair Proposal"
Cohesion: 0.33
Nodes (5): _json_object(), Exception, The model's proposal and its token count. {"operation": None} means no safe fix., No model, a transport error, or an answer that is not a usable proposal., RepairUnavailable

### Community 87 - "Safety Invariants"
Cohesion: 0.40
Nodes (5): No invented values, No executed model-generated code, Deterministic candidate building, Safe fix operations, F7 Candidate builder

### Community 88 - "Safety Design"
Cohesion: 0.40
Nodes (5): Safety invariants, Safety gate, Safety by construction, Base-schema fixes are never stacked, Threats and prevention

### Community 89 - "Error Classification Flow"
Cohesion: 0.40
Nodes (5): Error classes E1–E6 and BUSINESS, Healer, Negative cache, Structured refusal, Structured refusal with retry false

### Community 90 - "Core Product Requirements"
Cohesion: 0.40
Nodes (5): AC-1 registry tools and frozen agent_schema, F1 Tool registry, F3 Drift detection, F9 Safety gate, Self-healing registry

### Community 91 - "LLM Tool Tests"
Cohesion: 0.40
Nodes (3): FakeLLM, GenericFakeChatModel, Replays a script of AIMessages; records the tools bound and the messages of…

### Community 93 - "Registry Protocols Protocol Tests"
Cohesion: 0.60
Nodes (5): _protocol_config(), asyncio, parametrize, test_ac_38_registry_graphql_heals_and_keeps_schema_frozen(), test_ac_38_registry_grpc_heals_and_keeps_schema_frozen()

### Community 94 - "REST Adapter"
Cohesion: 0.50
Nodes (4): AsyncClient, Exception, Response, send()

### Community 96 - "MCP Probe Tests"
Cohesion: 0.50
Nodes (3): test_ac_59_probe_mcp_unreachable(), test_ac_59_probe_reports_short_errors(), handler()

### Community 97 - "Loader Contracts"
Cohesion: 0.67
Nodes (3): OperationSpec contract, Upstream MCP mapping contract, OperationSpec loader contract

### Community 98 - "Connection Setup UI"
Cohesion: 0.67
Nodes (3): Connections configuration page, Environment-variable token-name configuration, MCP, OpenAPI, Swagger and GraphQL connection types

### Community 99 - "Dashboard Landing"
Cohesion: 0.67
Nodes (3): Drift diagnosis and safe patch narrative, Gateway landing page, Interactive mutation demonstration

### Community 100 - "Dashboard Requirements"
Cohesion: 0.67
Nodes (3): AC-18 live dashboard comparison, AC-68 dashboard MCP front-door view, F16 Dashboard

### Community 101 - "Core Dependencies"
Cohesion: 0.67
Nodes (3): FastAPI, HTTPX, Pydantic

## Knowledge Gaps
- **80 isolated node(s):** `healer`, `$schema`, `builder`, `dockerfilePath`, `healthcheckPath` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 657 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ErrorClass` connect `Safety Tests` to `Heal Scenario Tests`, `JEV Tests`, `Connection Manager`, `Healing Controller`, `Dashboard Tests`, `gRPC Loader`, `Patch Operations`, `Store Tests`, `Core Healing Metrics`, `Agent Runtime`, `Fingerprint Tests`, `Scenarios Tests`, `MCP Server`, `PostgreSQL Store`, `SQLite Fix Store`, `Advanced Healing Setup`, `Dashboard State`, `FixStore Contract`, `Common Agent`, `Explorer Query Logic`, `Retry Tests`, `Contract Validation`, `Registry Tests`, `Response Classifier`, `Detect Tests`, `Contract Tests`, `Retry Policy`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **Why does `Reason` connect `Safety Tests` to `Candidates Tests`, `Heal Scenario Tests`, `Healing Controller`, `Rule Mining Tests`, `Patch Operations`, `Safety Metrics`, `Scenario Runner`, `Core Healing Metrics`, `Contract Validation`, `Scenarios Tests`, `Ops Tests`, `Heal Timing Tests`, `Advanced Healing Setup`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `Store` connect `SQLite Fix Store` to `Heal Scenario Tests`, `Healing Controller`, `MCP Fixture Recorder`, `Safety Tests`, `Overhead Benchmark`, `Store Tests`, `Agent Runtime`, `Scenarios Tests`, `MCP Server`, `Connection Tests`, `Advanced Healing Setup`, `Dashboard State`, `FixStore Contract`, `Fixtures`, `Explorer Query Logic`, `MCP Agent Demo`, `Tool Argument Casting`, `MCP Lifecycle Tests`, `Registry Tests`, `Agents Live Tests`, `MCP Repair Registry`, `AC 68 Tests`, `P3 Fixtures`, `MCP Benchmark Run`, `MCP Fixtures`, `Benchmark CLI`, `Agent Test Fixtures`, `Scenario Runner`, `Registry Protocols Protocol Tests`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 97 inferred relationships involving `Reason` (e.g. with `expectation()` and `build()`) actually correct?**
  _`Reason` has 97 INFERRED edges - model-reasoned connections that need verification._
- **Are the 75 inferred relationships involving `ErrorClass` (e.g. with `executor()` and `executor()`) actually correct?**
  _`ErrorClass` has 75 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `Store` (e.g. with `measure_mcp()` and `mcp_bench()`) actually correct?**
  _`Store` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 57 inferred relationships involving `HealOutcome` (e.g. with `_ablation_cell()` and `mcp_section()`) actually correct?**
  _`HealOutcome` has 57 INFERRED edges - model-reasoned connections that need verification._