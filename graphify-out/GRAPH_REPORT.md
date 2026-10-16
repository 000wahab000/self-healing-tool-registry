# Graph Report - self-healing-tool-registry  (2026-10-16)

## Corpus Check
- 152 files · ~124,162 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 5, .example 1, .css 1)

## Summary
- 2147 nodes · 5305 edges · 131 communities (112 shown, 19 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 699 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b6fdbb0f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_candidates.py
- test_spec_watcher.py
- HealOutcome
- McpDriftServer
- test_jev.py
- diagnose.py
- dashboard/app.py
- Healer
- operations
- test_dashboard.py
- test_mock_api.py
- pytest
- Reason
- connections.py
- grpc_loader.py
- repair.py
- overhead.py
- mock_api/app.py
- test_store.py
- models.py
- BaseModel
- graphql.py
- test_scenarios.py
- test_stdio.py
- test_ac_38_registry_graphql_heals_and_keeps_schema_frozen
- Store
- Outcome
- test_connections.py
- test_explorer.py
- test_http.py
- apply_ops
- Dashboard
- api_registry
- FixStore
- test_bench.py
- explorer.py
- sanitize
- integration/conftest.py
- run.py
- Self-Healing Gateway Write-up
- test_agents.py
- run_explore
- FakeClock
- baseline_agent.py
- Script
- swagger2.py
- MockApi
- create_app
- LoadedSpec
- test_ac_34_cli_uses_real_custom_spec_and_closes_resources
- test_ac_43_repair_agent.py
- Tier
- mcp_agent.py
- SpecWatcher
- test_registry.py
- Benchmark pipeline
- test_ac_58_mcp_client_docs.py
- test_agents_live.py
- build
- test_ac_46_repair_triage.py
- test_contracts.py
- test_ac_68_mcp_view.py
- RepairAgent
- test_detect.py
- test_ac_51_reset_and_profiles.py
- p3/conftest.py
- false_patch_rate
- .preflight
- Registry
- guide.js
- Side
- override
- openapi_source
- FakeLLM
- ErrorClass
- test_client_config.py
- Gateway
- railway.json
- gateway.py
- One audit row per heal attempt
- Registry
- JevClient
- Heal pipeline
- Spec-change precompute
- ui.js
- token_overhead
- detect.py
- Safe fix operations
- Safety gate
- Healer
- Self-healing registry
- test_ac_14_mttr_and_heal_ms_reported_per_tier_with_p95_targets
- make_llm
- setup
- send
- StepClock
- Wire
- OperationSpec loader contract
- Connections configuration page
- Gateway landing page
- F16 Dashboard
- FastAPI
- JevUnavailable
- FixStore contract
- SpecSource contract
- demo/__init__.py
- AC-15 ZTAR, Safe-Refusal, and False-Patch Rate targets
- LangChain OpenAI
- test_ac_26_m10.py
- Dashboard Live Interface
- healer
- JSON Schema
- python-dotenv
- Uvicorn
- test_watcher_resilience.py
- Gateway
- build_admin
- render_option
- test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal
- FakeLLM
- test_ui_regressions.py
- test_ac_54_mcp_bench.py
- mcp/conftest.py
- demo.py

## God Nodes (most connected - your core abstractions)
1. `Reason` - 110 edges
2. `ErrorClass` - 108 edges
3. `HealOutcome` - 67 edges
4. `Store` - 67 edges
5. `Outcome` - 57 edges
6. `Side` - 55 edges
7. `Healer` - 49 edges
8. `Registry` - 49 edges
9. `Tier` - 47 edges
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

## Communities (131 total, 19 thin omitted)

### Community 0 - "test_candidates.py"
Cohesion: 0.06
Nodes (96): Option, _assign(), build(), _cast(), _clue_fills(), _clue_response_ops(), _described(), _dry_run() (+88 more)

### Community 1 - "test_spec_watcher.py"
Cohesion: 0.19
Nodes (16): Clock, AC-55: the spec watcher snapshots changes, idles on unchanged specs, backs off…, Injected clock/sleep pair: sleeping moves time forward with no real wait., A SpecSource that serves a scripted sequence and counts its own calls., Minimal FixStore stand-in: records the snapshots the watcher saves., Recorder, spec(), SpyHealer (+8 more)

### Community 2 - "HealOutcome"
Cohesion: 0.12
Nodes (39): DecisionPath, HealOutcome, StrEnum, calls_to(), jev_reply(), respx side effect: choose the option whose text satisfies `pick`, reading the…, test_ac_07_m6_d_heals_through_the_tiebreaker_without_jev(), test_ac_07_m6_n_jev_at_write_threshold_and_confirming_preverify_recovers() (+31 more)

### Community 3 - "McpDriftServer"
Cohesion: 0.08
Nodes (30): mcp_shared_exceptions, _admin_tools(), McpDriftServer, call_tool(), list_tools(), Any, Server, Starlette (+22 more)

### Community 4 - "test_jev.py"
Cohesion: 0.16
Nodes (22): from_env(), Prefer TypeSafe direct, then OpenRouter, then opt-in OpenCode free Jev., render_state(), reply(), _set_manager_op(), test_ac_48_free_failure_is_unavailable(), test_ac_48_free_jev_requires_opt_in_without_keyed_provider(), test_ac_48_free_request_has_no_auth_and_parses_choice() (+14 more)

### Community 5 - "diagnose.py"
Cohesion: 0.06
Nodes (57): create_app(), GraphQLMock, update_email(), FastAPI, Small Strawberry GraphQL mock for protocol-drift tests., User, UserEnvelope, abstract_signature() (+49 more)

### Community 6 - "dashboard/app.py"
Cohesion: 0.14
Nodes (16): collections_abc, ExploreIn, MutationIn, BaseModel, Live demo dashboard: two in-process mock APIs, the healing and baseline agents,…, StartIn, dotenv, os (+8 more)

### Community 7 - "Healer"
Cohesion: 0.07
Nodes (35): Future, _Abort, api_error(), _Heal, Healer, _layer_reason(), Any, SpecSource (+27 more)

### Community 8 - "operations"
Cohesion: 0.12
Nodes (24): fetch_spec(), _json_schema(), load(), operations(), OperationSpec, Inline every local `#/...` ref; keywords next to a $ref override the target's., resolve_refs(), walk() (+16 more)

### Community 9 - "test_dashboard.py"
Cohesion: 0.09
Nodes (31): itertools, langchain_core_language_models_fake_chat_models, langchain_core_messages, langchain_core_outputs, langchain_core_utils_function_calling, calls(), client(), fake_llm() (+23 more)

### Community 10 - "test_mock_api.py"
Cohesion: 0.10
Nodes (37): api(), client(), deref(), errors(), get_spec(), lookup_args(), operation(), params() (+29 more)

### Community 11 - "pytest"
Cohesion: 0.11
Nodes (27): asyncio, An in-memory MCP client session over a mock drift server (shared by the MCP…, Path, T1-7: record `tools/list` before and after each mutation (AC-52). Writes…, record(), _tools(), contextlib, mcp (+19 more)

### Community 12 - "Reason"
Cohesion: 0.16
Nodes (29): Reason, jev_ok(), test_demo_runs_the_pitch_flow(), test_m8_is_refused_without_inventing_a_value(), Any, parametrize, run(), test_cast_path_not_in_spec_is_unsafe_patch() (+21 more)

### Community 13 - "connections.py"
Cohesion: 0.13
Nodes (24): add_connection(), clean_entry(), config_path(), is_remote(), list_connections(), _load(), page(), Path (+16 more)

### Community 14 - "grpc_loader.py"
Cohesion: 0.08
Nodes (30): FileDescriptorProto, google_protobuf, grpc_reflection_v1alpha, create_server(), _file(), Any, DescriptorPool, Small unary gRPC drift fixture with reflection and rich validation errors. (+22 more)

### Community 15 - "repair.py"
Cohesion: 0.10
Nodes (36): hashlib, dumps(), get(), pop(), put(), Any, Path, Canonical JSON, hashing and path helpers for nested dict/list documents. (+28 more)

### Community 16 - "overhead.py"
Cohesion: 0.13
Nodes (18): bench, _main(), measure(), measure_mcp(), percentile(), _print(), Any, AC-28 (FR-21.1): healthy-call overhead of the registry over the raw transport.… (+10 more)

### Community 17 - "mock_api/app.py"
Cohesion: 0.17
Nodes (19): fastapi_exceptions, fastapi_security, CustomerRef, CustomerRefM10, NewTicket, NewTicketPriority, Mock drift API: four operations (plus a dry-run), mutations switchable at…, SetManager (+11 more)

### Community 18 - "test_store.py"
Cohesion: 0.21
Nodes (24): FixStatus, make_event(), make_fix(), open_store(), parametrize, rows(), test_audit_layers_round_trip_and_redaction(), test_audit_round_trip() (+16 more)

### Community 19 - "models.py"
Cohesion: 0.18
Nodes (14): dataclasses, jsonschema, REST adapter: send a request document (contract C1), return the raw result., check(), _passes(), Any, Output-schema validation (E5) and declarative postchecks (E6) on an OK outcome., _schema_violations() (+6 more)

### Community 20 - "BaseModel"
Cohesion: 0.17
Nodes (12): drifted(), _custom_model(), EmailOut, _header_dep(), ManagerOut, MutationIn, BaseModel, Undo the drift on a valid request so the v1 handler can serve it. (+4 more)

### Community 21 - "graphql.py"
Cohesion: 0.19
Nodes (13): classify(), _literal(), AsyncClient, Exception, Response, _query(), GraphQL HTTP transport and machine-readable error normalization., Send using the current schema so response nesting follows the latest… (+5 more)

### Community 22 - "test_scenarios.py"
Cohesion: 0.11
Nodes (28): assert_first_heal(), call_for(), calls_to(), check_m1(), check_m2(), check_m4(), check_m5(), check_m9() (+20 more)

### Community 23 - "test_stdio.py"
Cohesion: 0.19
Nodes (10): ClientSession, session(), parametrize, _schema_listing(), test_ac_30_list_maps_frozen_registry_tools_and_disables_list_changed(), test_ac_31_get_user_returns_healthy_data(), test_ac_32_heal_keeps_client_schema_stable_without_notification(), test_ac_33_m8_refusal_is_structured_and_does_not_invent_or_write() (+2 more)

### Community 24 - "test_ac_38_registry_graphql_heals_and_keeps_schema_frozen"
Cohesion: 0.60
Nodes (5): _protocol_config(), asyncio, parametrize, test_ac_38_registry_graphql_heals_and_keeps_schema_frozen(), test_ac_38_registry_grpc_heals_and_keeps_schema_frozen()

### Community 25 - "Store"
Cohesion: 0.11
Nodes (3): _fix(), Store, test_sqlite_store_implements_fix_store()

### Community 26 - "Outcome"
Cohesion: 0.16
Nodes (20): Readback, Outcome, Compatibility wrapper; integrations should use preflight/verify_response…, Use ``preflight`` before sending, then ``verify_response`` after replay., Verifier, verify(), _async_value(), test_l6_invariant_and_l7_unsafe_write_fail_independently() (+12 more)

### Community 27 - "test_connections.py"
Cohesion: 0.06
Nodes (28): bad_request(), create_app(), explorer_info(), mutation(), start(), FastAPI, get_explorer_info(), fastapi_testclient (+20 more)

### Community 28 - "test_explorer.py"
Cohesion: 0.07
Nodes (14): _coerce_args(), Fit LLM-supplied arguments to the frozen agent-facing schema. A live model…, client(), offline(), fixture, parametrize, Tests for the Explorer endpoints (/api/explorer/info and /api/explore)., M6-N refuses set_manager (step 3); the agent still opens the ticket (step 4). (+6 more)

### Community 29 - "test_http.py"
Cohesion: 0.10
Nodes (21): AsyncExitStack, _arguments(), create_http_app(), main(), Namespace, Starlette, _serve(), _client() (+13 more)

### Community 30 - "apply_ops"
Cohesion: 0.17
Nodes (23): apply_ops(), cast_op(), parametrize, reason_of(), test_ac_41_enum_map_bijective_and_lossy(), test_ac_42_encoding_sets_content_type(), test_apply_ops_does_not_mutate_input(), test_cast_lossless() (+15 more)

### Community 31 - "Dashboard"
Cohesion: 0.17
Nodes (5): Dashboard, A scenario (and a live-LLM one can take minutes) holds the lock for its whole…, Once both agents finish an LLM run, remember the measured token pair., What the registry kept away from the agents, since the last Reset. Counted from…, Both agents run the demo task against their own mock; the store is shared.

### Community 32 - "api_registry"
Cohesion: 0.12
Nodes (20): BaseException, _api_client(), api_registry(), _api_source(), api_tool_config(), namespaced(), _open(), probe() (+12 more)

### Community 33 - "FixStore"
Cohesion: 0.10
Nodes (6): Protocol, Row, AuditEvent, _event(), FixStore, What the registry, the healer and the demo call on a store. SQLite (`Store`)…

### Community 34 - "test_bench.py"
Cohesion: 0.13
Nodes (25): classify_request(), classify_run(), Any, Request-level benchmark oracle, independent of the resulting mock state., Classify one target request; rejected requests are not false patches., Use the target operation's accepted request, including renamed-route attempts., main(), one() (+17 more)

### Community 35 - "explorer.py"
Cohesion: 0.10
Nodes (25): Shared agent pieces: prompt, task, LLM, tool factory and the run loop., RunResult, Execute, Scripted agent: the demo task as fixed tool calls. No LLM and no tokens. It…, run(), _heal_info(), _json_or_text(), _lossless_coerce() (+17 more)

### Community 36 - "sanitize"
Cohesion: 0.29
Nodes (6): FR-5.7: the audit blob keeps no secret. Redact, then truncate (so a cut cannot…, _safe_layers(), sanitize(), test_ac_24_raw_error_redacted(), test_sanitize_ignores_empty_secret_values(), test_sanitize_truncates_after_redacting()

### Community 37 - "integration/conftest.py"
Cohesion: 0.25
Nodes (12): api(), client(), jev(), make_registry(), make(), fixture, Healing registry (store, no Jev, no real sleeping); keyword arguments override., registry() (+4 more)

### Community 38 - "run.py"
Cohesion: 0.10
Nodes (35): _ablation_cell(), _amain(), bench(), expectation(), _failure_mode(), main(), mcp_section(), _outcome() (+27 more)

### Community 39 - "Self-Healing Gateway Write-up"
Cohesion: 0.08
Nodes (40): Coding Agent Rules, Module Contracts and Working Rules, Baseline comparison, False-Patch Rate, Healthy MCP-call overhead, LLM token cost not measured, MCP heal evidence: 12/12, MTTR and internal heal_ms (+32 more)

### Community 40 - "test_agents.py"
Cohesion: 0.33
Nodes (18): run(), build(), call(), call_rows(), last_tool_result(), llm(), AIMessage, parametrize (+10 more)

### Community 41 - "run_explore"
Cohesion: 0.11
Nodes (17): check_data_correctness(), extract_tool_schemas(), _heal_summaries(), _llm_bootstrap_error(), Extract input and output schemas from a resolved OpenAPI spec for each…, Verify mock API state against expected values. `touched` restricts the verdict…, Provider errors arrive as a page of JSON; the UI only needs the headline., Read-only view of every ToolDefinition after the run. (+9 more)

### Community 42 - "FakeClock"
Cohesion: 0.22
Nodes (8): clock(), db_path(), FakeClock, _open(), fixture, Path, test_audit_layers_column_migrates_existing_database(), test_rule_mining_promotes_after_three_wins()

### Community 43 - "baseline_agent.py"
Cohesion: 0.11
Nodes (20): build(), executor(), Execute, Baseline agent: same tools, but each call is a bare v1 HTTP request. No…, make_tools(), tool(), Execute, One tool per registry spec; both agents differ only in `execute`. Logs each… (+12 more)

### Community 44 - "Script"
Cohesion: 0.19
Nodes (13): hinted(), parametrize, Attempt callable that replays a fixed list of outcomes and records sleeps., Script, test_backoff_sequence_then_gives_up_after_three_retries(), test_budget_shrinks_between_retries(), test_default_jitter_stays_within_bound(), test_jitter_is_added_to_each_backoff() (+5 more)

### Community 45 - "swagger2.py"
Cohesion: 0.14
Nodes (16): convert(), _operation(), _param_schema(), Any, Convert a Swagger 2.0 document to the OpenAPI 3 shape `operations()` reads…, Reshape a Swagger 2.0 document into the OpenAPI 3 shape `operations()` reads.…, Deep copy `node`, pointing every local `#/definitions/...` ref at…, Lift a 2.0 non-body parameter's type keywords into the OpenAPI 3 `schema`… (+8 more)

### Community 46 - "MockApi"
Cohesion: 0.18
Nodes (4): check_custom(), MockApi, Validate a custom drift: one tool, any of rename / to_int / wrap / header /…, `custom` is required for, and only used by, the CUSTOM drift.

### Community 47 - "create_app"
Cohesion: 0.12
Nodes (9): create_app(), socket, api(), client(), fixture, test_real_http_switch_to_m1(), test_ac_59_probe_openapi_against_rest_mock(), threading (+1 more)

### Community 48 - "LoadedSpec"
Cohesion: 0.12
Nodes (15): mcp_source(), source(), ClientSession, OperationSpec, SpecSource, Read the upstream's tools/list. Names starting with `__` are reserved (admin…, to_operation(), load() (+7 more)

### Community 49 - "test_ac_34_cli_uses_real_custom_spec_and_closes_resources"
Cohesion: 0.15
Nodes (9): test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(), close(), __init__(), tracked_client(), test_ac_34_cli_uses_real_custom_spec_and_closes_resources(), close(), __init__(), tracked_client() (+1 more)

### Community 50 - "test_ac_43_repair_agent.py"
Cohesion: 0.21
Nodes (13): FakeLlm, asyncio, Exception, parametrize, AC-43 and AC-45: the tier-2 repair agent heals a break tier 1 cannot explain,…, Scripted model: returns `answer` and records every prompt it was sent., SlowLlm, test_ac_43_repair_agent_heals_unexplained_drift_and_fix_is_reused() (+5 more)

### Community 51 - "Tier"
Cohesion: 0.12
Nodes (29): collections, IntEnum, mttr_summary(), outcome_counts(), percentiles(), Any, Benchmark metrics (FR-15.4, FR-15.5) over audit events and benchmark run rows.…, FR-15.5, per scenario and agent: mean/p50/p95 of `llm_tokens` per run and of… (+21 more)

### Community 52 - "mcp_agent.py"
Cohesion: 0.16
Nodes (13): argparse, main(), ClientSession, Demo agent: one task over two upstream MCP servers, through the healer front…, Run the task once; returns calls, errors seen by the agent and the audit rows., Calls the front door, prints each call, and notes heals read from the shared…, run_demo(), run_scripted() (+5 more)

### Community 53 - "SpecWatcher"
Cohesion: 0.16
Nodes (7): SpecSource, Contract 5: only the healer that provides precompute is called; snapshots still…, Poll every due source once. Return the names whose spec changed., SpecWatcher, Task, test_backoff_max_must_cover_the_interval(), test_interval_must_be_positive()

### Community 54 - "test_registry.py"
Cohesion: 0.21
Nodes (10): calls_to(), fix_for(), parametrize, test_ac_02_invalid_args_no_heal(), test_active_fix_request_ops_are_applied(), test_active_fix_response_ops_reshape_before_contract(), test_fr_3_4_value_rules_are_left_to_the_api(), test_healthy_call() (+2 more)

### Community 55 - "Benchmark pipeline"
Cohesion: 0.14
Nodes (14): Mock drift control contract, Benchmark report view, Live stream comparison, Metrics view, Mutation controls, Benchmark pipeline, Dashboard, Mock drift control (+6 more)

### Community 56 - "test_ac_58_mcp_client_docs.py"
Cohesion: 0.24
Nodes (13): io, _json_blocks(), AC-58: docs/mcp-clients.md is a usable client guide derived from the hand-off…, The CLI flags the server actually accepts, read from its argparse help., _server_flags(), test_ac_58_covers_both_transports(), test_ac_58_documented_flags_exist_on_the_server(), test_ac_58_guide_is_derived_from_the_handoff() (+5 more)

### Community 57 - "test_agents_live.py"
Cohesion: 0.24
Nodes (12): agents, sqlite3, completed(), parametrize, Live agent runs: real LLM through NVIDIA NIM, consuming API credits. Skipped…, Run the demo task once; returns (RunResult, mock api, [(tool, class), ...])., New email, manager 456, one ticket, and the lookup itself succeeded., run_live() (+4 more)

### Community 58 - "build"
Cohesion: 0.15
Nodes (10): Header, min_length, build(), manager_ids(), set_manager(), update_email(), validate_manager(), FastAPI (+2 more)

### Community 59 - "test_ac_46_repair_triage.py"
Cohesion: 0.27
Nodes (11): FakeJev, FakeLlm, asyncio, parametrize, AC-46: Jev triages a tier-1 refusal: repair it, or send the error straight to…, Answers only the triage question; records what it was shown., test_ac_46_jev_report_unavailable_or_unsure_sends_the_error(), test_ac_46_jev_says_repair_and_the_agent_heals() (+3 more)

### Community 60 - "test_contracts.py"
Cohesion: 0.40
Nodes (5): _keys(), Step 0 contracts between the two tracks (AGENTS.md): OperationSpec, SpecSource,…, Contract 4: Registry exposes tools() and passes tools accessor to Healer., test_contract_4_registry_exposes_tools_accessor(), test_openapi_operations_match_operation_spec()

### Community 61 - "test_ac_68_mcp_view.py"
Cohesion: 0.19
Nodes (8): app(), client(), _front_door_tools(), offline(), fixture, AC-68: the dashboard MCP view reports the front door's tools (T2-9, no T1-6)., Build a clean registry the way the MCP server does, and read its tools., test_ac_68_endpoint_lists_exactly_the_front_door_tools()

### Community 62 - "RepairAgent"
Cohesion: 0.06
Nodes (44): mcp_bench(), mcp_state_ok(), Only user 123's email may differ from the seed, and at most the one expected…, The scripted MCP task per drift-server mutation, through a healing gateway and…, What the MCP front door exposes, read from the same `Registry.tools()`., Llm, Default registry config: a tool is a write unless the upstream says it is read-…, tool_config() (+36 more)

### Community 63 - "test_detect.py"
Cohesion: 0.29
Nodes (10): parametrize, Response, r(), raw(), raw_status(), req(), test_ac_03_detector_table(), test_data_carries_decoded_body() (+2 more)

### Community 64 - "test_ac_51_reset_and_profiles.py"
Cohesion: 0.26
Nodes (12): _dump_tools(), Any, asyncio, parametrize, AC-51 / Contract 8: admin tools (__admin_apply, __admin_list, __admin_reset)…, AC-51: reset restores tools/list byte for byte after any mutation., AC-51: reset restores in-memory users and tickets to SEED state., AC-51: profile='tickets' lists a different toolset than profile='users'. (+4 more)

### Community 65 - "p3/conftest.py"
Cohesion: 0.31
Nodes (9): api(), client(), make_registry(), make(), fixture, P3-owned fixtures. Mirrors `tests/integration/conftest.py` for the p3 track., Healing registry (store, no Jev, no real sleeping); keyword arguments override., store() (+1 more)

### Community 66 - "false_patch_rate"
Cohesion: 0.18
Nodes (11): RunRow, false_patch_rate(), Count wrong accepted requests when the request-level oracle is available., FR-15.4 ZTAR: over `scenarios` only, the runs where the task completed and the…, ztar(), AC-15: ZTAR 100% over the healable mutations with Jev absent, M6 separate,…, test_ac_15_ztar_safe_refusal_false_patch_and_m6_reported_separately(), test_false_patch_rate_counts_healed_runs_with_a_wrong_final_state() (+3 more)

### Community 67 - ".preflight"
Cohesion: 0.26
Nodes (10): _invalid_request(), _invariants_pass(), Any, OperationSpec, _readback_matches(), _row(), _skip_from(), _spec_constraints() (+2 more)

### Community 68 - "Registry"
Cohesion: 0.21
Nodes (6): create_server(), Server, Expose registry tools and calls without adding healing behavior., Send `base` through `fix` (request ops, response ops), classify, check the…, Registry, main()

### Community 69 - "guide.js"
Cohesion: 0.44
Nodes (7): close(), go(), onKey(), open(), openTab(), place(), show()

### Community 70 - "Side"
Cohesion: 0.11
Nodes (34): google_rpc, _arg_violations(), classify(), Any, Descriptor, Exception, Unary gRPC adapter and machine-readable status normalization., Send one unary call; classes come from the reflected request descriptor. (+26 more)

### Community 71 - "override"
Cohesion: 0.20
Nodes (11): override(), Request, Response, Answer requests to `path` with `make(request)` (None passes through); returns…, E4: the API answers 200 with an error body to the v1 request, and works for the…, soft_error_for_old_shape(), test_ac_20_e4_on_idempotent_tool_is_replayed(), test_ac_24_audit_raw_error_is_redacted() (+3 more)

### Community 72 - "openapi_source"
Cohesion: 0.18
Nodes (9): openapi_source(), AsyncClient, SpecSource, The default `SpecSource`: the API's OpenAPI 3 document at `path`., AsyncClient, SpecSource, Contract 5: P4's watcher calls Healer.precompute(old: LoadedSpec, new:…, test_contract_5_spec_change_precompute() (+1 more)

### Community 73 - "FakeLLM"
Cohesion: 0.20
Nodes (8): capturing_llm(), _generate(), FakeLLM, llm_call(), AIMessage, GenericFakeChatModel, Offline fake that independently chooses the next response per conversation., test_llm_control_run_gets_the_control_task()

### Community 74 - "ErrorClass"
Cohesion: 0.22
Nodes (13): random, ErrorClass, E1 retry policy (FR-11.1): bounded backoff with jitter. E1 is retried here and…, Run `attempt`, then retry E1 up to len(E1_BACKOFF_S) times while the budget…, with_retries(), check(), parametrize, test_each_missing_property_is_reported_once() (+5 more)

### Community 75 - "test_client_config.py"
Cohesion: 0.36
Nodes (9): _connect(), _load_target(), Path, skipif, _safe_smoke(), _smoke(), test_ac_37_invalid_transport_configs_fail_without_echoing_secrets(), test_ac_37_live_client_config() (+1 more)

### Community 76 - "Gateway"
Cohesion: 0.25
Nodes (8): MCP front-door view, Gateway, MCP Front Door, Built MCP gateway and APIs, Deferred GraphQL, gRPC, Postgres, and streaming work, AC-63 namespaced frozen upstream tools, F24 Upstream MCP gateway, System boundaries and deferred protocols

### Community 77 - "railway.json"
Cohesion: 0.25
Nodes (7): build, builder, dockerfilePath, deploy, healthcheckPath, restartPolicyType, $schema

### Community 78 - "gateway.py"
Cohesion: 0.09
Nodes (28): copy, Enum, httpx, inspect, json, logging, mcp_client_streamable_http, pathlib (+20 more)

### Community 79 - "One audit row per heal attempt"
Cohesion: 0.29
Nodes (7): Audit before returning heal result, Secrets excluded from store and logs, Patch log, One audit row per heal attempt, SQLite fix and audit store, AC-5 exactly one audit event per heal, F5 Store and audit

### Community 80 - "Registry"
Cohesion: 0.29
Nodes (7): Frozen agent_schema invariant, Registry.tools() and Registry.call() contract, Frozen agent_schema, Registry, tools/call, tools/list, Facade and hot-patching

### Community 81 - "JevClient"
Cohesion: 0.22
Nodes (5): JevChoice, JevClient, AsyncClient, jev(), fixture

### Community 82 - "Heal pipeline"
Cohesion: 0.33
Nodes (6): One heal and one replay; no retry loop, Contract verification, Spec diagnosis, Heal pipeline, F10 Patch, verify, commit, Healing tiers 0, 1, Jev, and 2

### Community 83 - "Spec-change precompute"
Cohesion: 0.33
Nodes (6): Spec-change hook, Spec-change precompute, Spec watcher, Built spec watcher, AC-55 spec watcher behavior, F18 Spec watcher

### Community 84 - "ui.js"
Cohesion: 0.67
Nodes (5): apply(), init(), read(), toggles(), write()

### Community 85 - "token_overhead"
Cohesion: 0.22
Nodes (6): FR-15.4 Token Overhead (healing) and wasted tokens (baseline): the mutated…, token_overhead(), AC-16: overhead = mutated total - CLEAN median, baseline waste beside it, the…, test_ac_16_token_overhead_against_clean_median_with_jev_in_its_own_column(), test_token_overhead_is_the_clean_median_difference_without_jev_tokens(), test_token_overhead_without_clean_runs_is_empty()

### Community 86 - "detect.py"
Cohesion: 0.29
Nodes (11): classify(), _error_body(), _is_soft_error(), _kind(), Exception, Response, Response classification (technical-approach 5.1, steps 1-5). Schema and…, FR-3.4: a 422 type that says the value is bad becomes a value kind; all others… (+3 more)

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

### Community 91 - "test_ac_14_mttr_and_heal_ms_reported_per_tier_with_p95_targets"
Cohesion: 0.25
Nodes (9): agent_rows(), AC-14: tier-1 MTTR p95 < 4.0 s for M1 to M5 (tier 0 < 0.5 s), heal_ms alongside., AC-17: error loop, calls, tokens and final data are measured per scenario and…, AC-23: M1 to M9 re-run with spec_mode=off, per mutation healed or aborted with…, The text from one `##` heading to the next (or the end of the report)., section(), test_ac_14_mttr_and_heal_ms_reported_per_tier_with_p95_targets(), test_ac_17_baseline_outcomes_measured_for_every_scenario_not_asserted() (+1 more)

### Community 92 - "make_llm"
Cohesion: 0.25
Nodes (7): make_llm(), ChatOpenAI, LangGraph ReAct agent whose tools are the front door's tools (same shape as…, run_llm(), wrap(), test_make_llm_uses_nvidia_key_and_model_override(), test_make_llm_uses_nvidia_nim_defaults()

### Community 93 - "setup"
Cohesion: 0.25
Nodes (8): api(), client(), db_path(), fixture, registry(), store(), fixture, setup()

### Community 94 - "send"
Cohesion: 0.50
Nodes (4): AsyncClient, Exception, Response, send()

### Community 96 - "Wire"
Cohesion: 0.29
Nodes (5): AsyncBaseTransport, Request, Response, The in-process mock API, with knobs: per-request delay (lets calls interleave)…, Wire

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

### Community 102 - "JevUnavailable"
Cohesion: 0.40
Nodes (6): JevUnavailable, Exception, Timeout, transport or HTTP error, or an answer that is not one of our options., parametrize, test_bad_reply_is_unavailable_and_not_retried(), test_transport_error_is_unavailable_and_not_retried()

### Community 108 - "test_ac_26_m10.py"
Cohesion: 0.50
Nodes (4): _assert_no_injection_in_requests(), AC-26 (S8 prompt-injection resistance / Mutation M10): Malicious instruction…, test_ac_26_m10_injection_resistance(), test_ac_26_m10_matches_m1_parity()

### Community 119 - "test_watcher_resilience.py"
Cohesion: 0.40
Nodes (3): asyncio, The watcher keeps polling after an unexpected error (review fix)., test_watcher_survives_an_unexpected_poll_error()

### Community 120 - "Gateway"
Cohesion: 0.25
Nodes (6): Gateway, gateway_factory(), build(), fixture, A Gateway over in-memory upstream drift servers: {"users": drift, "tickets":…, _session()

### Community 121 - "build_admin"
Cohesion: 0.43
Nodes (5): build_admin(), list_mutations(), mutations(), reset(), set_mutation()

### Community 122 - "render_option"
Cohesion: 0.40
Nodes (4): render_option(), Regression tests for the 2026-10-16 code review fixes., test_jev_renders_enum_map_and_encoding_options(), test_render_option_lists_every_op()

### Community 124 - "FakeLLM"
Cohesion: 0.40
Nodes (3): FakeLLM, GenericFakeChatModel, Replays a script of AIMessages; records the tools bound and the messages of…

### Community 125 - "test_ui_regressions.py"
Cohesion: 0.29
Nodes (6): shutil, subprocess, skipif, Focused browser-logic regressions for the dashboard stepper., test_ac_18_live_control_steps_and_transient_retry_copy(), test_ac_56_stepper_keeps_task_context_and_failure_states()

### Community 126 - "test_ac_54_mcp_bench.py"
Cohesion: 0.40
Nodes (4): asyncio, AC-54: MCP drift scenarios in the benchmark: heal, refuse safely, never false-…, test_ac_54_mcp_scenarios(), test_ac_54_report_has_mcp_section()

### Community 127 - "mcp/conftest.py"
Cohesion: 0.33
Nodes (7): pytest_asyncio, api(), mcp_client(), connect(), mcp_registry(), fixture, tools_config()

### Community 131 - "demo.py"
Cohesion: 0.36
Nodes (8): fix_text(), main(), print_act(), print_summary(), Terminal demo, the fallback for the pitch: `python -m dashboard.demo`. Scripted…, Run every act from a cold store; `step` is the agents' pause between calls., task_done(), tempfile

## Knowledge Gaps
- **80 isolated node(s):** `healer`, `$schema`, `builder`, `dockerfilePath`, `healthcheckPath` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 678 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ErrorClass` connect `ErrorClass` to `HealOutcome`, `Healer`, `test_dashboard.py`, `Reason`, `grpc_loader.py`, `repair.py`, `test_store.py`, `models.py`, `graphql.py`, `test_scenarios.py`, `Store`, `Outcome`, `Dashboard`, `FixStore`, `explorer.py`, `run_explore`, `baseline_agent.py`, `Script`, `Tier`, `test_registry.py`, `test_ac_46_repair_triage.py`, `test_detect.py`, `.preflight`, `Registry`, `Side`, `override`, `gateway.py`, `detect.py`, `test_ac_26_m10.py`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `Store` connect `Store` to `HealOutcome`, `Healer`, `overhead.py`, `test_store.py`, `test_scenarios.py`, `test_ac_38_registry_graphql_heals_and_keeps_schema_frozen`, `test_connections.py`, `test_http.py`, `Dashboard`, `FixStore`, `explorer.py`, `sanitize`, `integration/conftest.py`, `run.py`, `run_explore`, `FakeClock`, `test_ac_34_cli_uses_real_custom_spec_and_closes_resources`, `mcp_agent.py`, `test_registry.py`, `test_agents_live.py`, `test_ac_68_mcp_view.py`, `RepairAgent`, `p3/conftest.py`, `Registry`, `ErrorClass`, `gateway.py`, `setup`, `test_ac_26_m10.py`, `Gateway`, `mcp/conftest.py`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `Reason` connect `Reason` to `test_candidates.py`, `FixStore`, `HealOutcome`, `run.py`, `Healer`, `Side`, `override`, `gateway.py`, `repair.py`, `test_store.py`, `models.py`, `Tier`, `test_scenarios.py`, `test_ac_14_mttr_and_heal_ms_reported_per_tier_with_p95_targets`, `apply_ops`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 96 inferred relationships involving `Reason` (e.g. with `expectation()` and `build()`) actually correct?**
  _`Reason` has 96 INFERRED edges - model-reasoned connections that need verification._
- **Are the 86 inferred relationships involving `ErrorClass` (e.g. with `executor()` and `executor()`) actually correct?**
  _`ErrorClass` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `HealOutcome` (e.g. with `_ablation_cell()` and `mcp_section()`) actually correct?**
  _`HealOutcome` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `Store` (e.g. with `measure_mcp()` and `mcp_bench()`) actually correct?**
  _`Store` has 38 INFERRED edges - model-reasoned connections that need verification._