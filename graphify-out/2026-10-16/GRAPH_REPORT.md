# Graph Report - self-healing-tool-registry  (2026-10-16)

## Corpus Check
- 150 files · ~123,997 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 8 file(s) not represented in the graph (top: (none) 5, .example 1, .css 1)

## Summary
- 2144 nodes · 5303 edges · 109 communities (90 shown, 19 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 699 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b6fdbb0f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_candidates.py
- LoadedSpec
- HealOutcome
- McpDriftServer
- test_jev.py
- diagnose.py
- PostgresStore
- Healer
- swagger2.py
- test_dashboard.py
- test_mock_api.py
- pytest
- Reason
- connections.py
- grpc.py
- canonical.py
- overhead.py
- mock_api/app.py
- test_store.py
- create_app
- BaseModel
- graphql.py
- test_scenarios.py
- test_stdio.py
- graphql_loader.py
- Store
- Outcome
- create_app
- test_explorer.py
- test_http.py
- apply_ops
- Dashboard
- mcp_upstream.py
- FixStore
- test_bench.py
- registry.py
- sanitize
- integration/conftest.py
- report
- Self-Healing Gateway Write-up
- test_agents.py
- run_explore
- FakeClock
- make_tools
- Script
- _coerce_args
- MockApi
- test_admin.py
- test_ac_34_cli_uses_real_custom_spec_and_closes_resources
- test_ac_43_repair_agent.py
- Tier
- test_callback_exception_is_sanitized_and_keeps_secret_out_of_logs
- test_registry.py
- Benchmark pipeline
- test_ac_58_mcp_client_docs.py
- run_live
- build
- FixStatus
- test_ac_68_mcp_view.py
- connect_upstreams
- test_detect.py
- p3/conftest.py
- verify.py
- guide.js
- models.py
- ErrorClass
- _pass
- Gateway
- railway.json
- gateway.py
- One audit row per heal attempt
- Registry
- Heal pipeline
- Spec-change precompute
- ui.js
- detect.py
- Safe fix operations
- Safety gate
- Healer
- Self-healing registry
- send
- StepClock
- OperationSpec loader contract
- Connections configuration page
- Gateway landing page
- F16 Dashboard
- FastAPI
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
- RepairAgent
- build_admin
- test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal
- test_ui_regressions.py
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

## Communities (109 total, 19 thin omitted)

### Community 0 - "test_candidates.py"
Cohesion: 0.06
Nodes (96): Option, _assign(), build(), _cast(), _clue_fills(), _clue_response_ops(), _described(), _dry_run() (+88 more)

### Community 1 - "LoadedSpec"
Cohesion: 0.06
Nodes (37): mcp_source(), source(), ClientSession, OperationSpec, SpecSource, Read the upstream's tools/list. Names starting with `__` are reserved (admin…, to_operation(), load() (+29 more)

### Community 2 - "HealOutcome"
Cohesion: 0.09
Nodes (49): DecisionPath, HealOutcome, StrEnum, calls_to(), jev_reply(), override(), Request, Response (+41 more)

### Community 3 - "McpDriftServer"
Cohesion: 0.06
Nodes (41): _admin_tools(), McpDriftServer, call_tool(), list_tools(), Any, Server, Starlette, Mock drift MCP server implementing Contract 8. (+33 more)

### Community 4 - "test_jev.py"
Cohesion: 0.06
Nodes (51): _arg_types(), _dotted(), _entry(), from_env(), JevChoice, JevUnavailable, Any, Exception (+43 more)

### Community 5 - "diagnose.py"
Cohesion: 0.10
Nodes (39): abstract_signature(), diff(), _diff_leaves(), diff_signature(), _entry(), flatten_request(), flatten_response(), _index() (+31 more)

### Community 6 - "PostgresStore"
Cohesion: 0.11
Nodes (14): PostgresStore, Synchronous FixStore backed by Postgres; active reads always query committed…, pg_store(), fixture, make_fix(), _no_sleep(), test_ac_39_shared_active_fix_and_database_uniqueness(), test_ac_39_two_registries_reuse_m1_fix_at_tier0() (+6 more)

### Community 7 - "Healer"
Cohesion: 0.09
Nodes (29): extract_tool_schemas(), Extract input and output schemas from a resolved OpenAPI spec for each…, Future, _Abort, api_error(), _Heal, Healer, _layer_reason() (+21 more)

### Community 8 - "swagger2.py"
Cohesion: 0.08
Nodes (40): fetch_spec(), _json_schema(), load(), operations(), AsyncClient, OperationSpec, Inline every local `#/...` ref; keywords next to a $ref override the target's., resolve_refs() (+32 more)

### Community 9 - "test_dashboard.py"
Cohesion: 0.07
Nodes (39): itertools, langchain_core_language_models_fake_chat_models, langchain_core_messages, langchain_core_outputs, langchain_core_utils_function_calling, calls(), capturing_llm(), _generate() (+31 more)

### Community 10 - "test_mock_api.py"
Cohesion: 0.10
Nodes (37): api(), client(), deref(), errors(), get_spec(), lookup_args(), operation(), params() (+29 more)

### Community 11 - "pytest"
Cohesion: 0.08
Nodes (34): asyncio, An in-memory MCP client session over a mock drift server (shared by the MCP…, Path, T1-7: record `tools/list` before and after each mutation (AC-52). Writes…, record(), _tools(), contextlib, dotenv (+26 more)

### Community 12 - "Reason"
Cohesion: 0.15
Nodes (30): Reason, test_demo_runs_the_pitch_flow(), test_m8_is_refused_without_inventing_a_value(), (STRETCH, S2) Rule mining: after 3 wins of the same pattern, subsequent…, test_ac_44_rule_mining(), Any, parametrize, run() (+22 more)

### Community 13 - "connections.py"
Cohesion: 0.13
Nodes (24): add_connection(), clean_entry(), config_path(), is_remote(), list_connections(), _load(), page(), Path (+16 more)

### Community 14 - "grpc.py"
Cohesion: 0.07
Nodes (38): FileDescriptorProto, google_protobuf, google_rpc, grpc_reflection_v1alpha, create_server(), _file(), Any, DescriptorPool (+30 more)

### Community 15 - "canonical.py"
Cohesion: 0.11
Nodes (31): hashlib, jsonschema, dumps(), get(), pop(), put(), Any, Path (+23 more)

### Community 16 - "overhead.py"
Cohesion: 0.11
Nodes (19): bench, _main(), measure(), measure_mcp(), percentile(), _print(), Any, AC-28 (FR-21.1): healthy-call overhead of the registry over the raw transport.… (+11 more)

### Community 17 - "mock_api/app.py"
Cohesion: 0.17
Nodes (20): fastapi_exceptions, fastapi_security, CustomerRef, CustomerRefM10, NewTicket, NewTicketPriority, Mock drift API: four operations (plus a dry-run), mutations switchable at…, SetManager (+12 more)

### Community 18 - "test_store.py"
Cohesion: 0.22
Nodes (22): make_event(), make_fix(), open_store(), parametrize, rows(), test_audit_layers_round_trip_and_redaction(), test_audit_round_trip(), test_c11_enum_values_are_stored_and_the_old_reason_is_gone() (+14 more)

### Community 19 - "create_app"
Cohesion: 0.12
Nodes (8): bad_request(), create_app(), explorer_info(), mutation(), start(), FastAPI, get_explorer_info(), test_ac_59_non_local_client_needs_token_even_on_a_local_bind()

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
Cohesion: 0.26
Nodes (9): argparse, ClientSession, session(), _schema_listing(), test_ac_30_list_maps_frozen_registry_tools_and_disables_list_changed(), test_ac_31_get_user_returns_healthy_data(), test_ac_32_heal_keeps_client_schema_stable_without_notification(), test_ac_33_m8_refusal_is_structured_and_does_not_invent_or_write() (+1 more)

### Community 24 - "graphql_loader.py"
Cohesion: 0.08
Nodes (29): copy, create_app(), GraphQLMock, update_email(), FastAPI, Small Strawberry GraphQL mock for protocol-drift tests., User, UserEnvelope (+21 more)

### Community 26 - "Outcome"
Cohesion: 0.14
Nodes (21): Readback, SpecSource, Outcome, Compatibility wrapper; integrations should use preflight/verify_response…, Use ``preflight`` before sending, then ``verify_response`` after replay., Verifier, verify(), _async_value() (+13 more)

### Community 27 - "create_app"
Cohesion: 0.10
Nodes (23): fastapi_testclient, create_app(), MonkeyPatch, TestClient, main(), cfg_file(), client(), fixture (+15 more)

### Community 28 - "test_explorer.py"
Cohesion: 0.08
Nodes (10): client(), offline(), fixture, parametrize, Tests for the Explorer endpoints (/api/explorer/info and /api/explore)., M6-N refuses set_manager (step 3); the agent still opens the ticket (step 4)., The LLM path must never quietly return a canned scripted result., test_explore_controls_pass_business_errors_through() (+2 more)

### Community 29 - "test_http.py"
Cohesion: 0.07
Nodes (29): AsyncExitStack, Llm, _arguments(), create_http_app(), create_server(), main(), Namespace, Server (+21 more)

### Community 30 - "apply_ops"
Cohesion: 0.17
Nodes (23): apply_ops(), cast_op(), parametrize, reason_of(), test_ac_41_enum_map_bijective_and_lossy(), test_ac_42_encoding_sets_content_type(), test_apply_ops_does_not_mutate_input(), test_cast_lossless() (+15 more)

### Community 31 - "Dashboard"
Cohesion: 0.17
Nodes (5): Dashboard, A scenario (and a live-LLM one can take minutes) holds the lock for its whole…, Once both agents finish an LLM run, remember the measured token pair., What the registry kept away from the agents, since the last Reset. Counted from…, Both agents run the demo task against their own mock; the store is shared.

### Community 32 - "mcp_upstream.py"
Cohesion: 0.33
Nodes (6): _payload(), Any, Upstream MCP servers as a protocol (contract 7): tools/list -> OperationSpec,…, Default registry config: a tool is a write unless the upstream says it is read-…, send(), tool_config()

### Community 33 - "FixStore"
Cohesion: 0.12
Nodes (3): Protocol, FixStore, What the registry, the healer and the demo call on a store. SQLite (`Store`)…

### Community 34 - "test_bench.py"
Cohesion: 0.09
Nodes (34): classify_request(), classify_run(), Any, Request-level benchmark oracle, independent of the resulting mock state., Classify one target request; rejected requests are not false patches., Use the target operation's accepted request, including renamed-route attempts., agent_rows(), main() (+26 more)

### Community 35 - "registry.py"
Cohesion: 0.09
Nodes (42): agents, Baseline agent: same tools, but each call is a bare v1 HTTP request. No…, Shared agent pieces: prompt, task, LLM, tool factory and the run loop., RunResult, Healing agent: every tool call goes through the self-healing `Registry`., Scripted agent: the demo task as fixed tool calls. No LLM and no tokens. It…, Benchmark runner and report (plan.md phase 10, metrics per phase 12D / FR-15).…, collections_abc (+34 more)

### Community 36 - "sanitize"
Cohesion: 0.29
Nodes (6): FR-5.7: the audit blob keeps no secret. Redact, then truncate (so a cut cannot…, _safe_layers(), sanitize(), test_ac_24_raw_error_redacted(), test_sanitize_ignores_empty_secret_values(), test_sanitize_truncates_after_redacting()

### Community 37 - "integration/conftest.py"
Cohesion: 0.15
Nodes (17): api(), client(), jev(), make_registry(), make(), AsyncBaseTransport, fixture, Request (+9 more)

### Community 38 - "report"
Cohesion: 0.07
Nodes (35): _ablation_cell(), expectation(), _failure_mode(), mcp_section(), _outcome(), _pick(), _rate(), What one run of `scenario` owes: a completed task, a safe refusal or a pass-… (+27 more)

### Community 39 - "Self-Healing Gateway Write-up"
Cohesion: 0.08
Nodes (40): Coding Agent Rules, Module Contracts and Working Rules, Baseline comparison, False-Patch Rate, Healthy MCP-call overhead, LLM token cost not measured, MCP heal evidence: 12/12, MTTR and internal heal_ms (+32 more)

### Community 40 - "test_agents.py"
Cohesion: 0.08
Nodes (46): make_llm(), run(), ChatOpenAI, main(), ClientSession, Demo agent: one task over two upstream MCP servers, through the healer front…, Run the task once; returns calls, errors seen by the agent and the audit rows., Calls the front door, prints each call, and notes heals read from the shared… (+38 more)

### Community 41 - "run_explore"
Cohesion: 0.14
Nodes (14): check_data_correctness(), _heal_summaries(), _llm_bootstrap_error(), Verify mock API state against expected values. `touched` restricts the verdict…, Provider errors arrive as a page of JSON; the UI only needs the headline., Read-only view of every ToolDefinition after the run., Audit events as the explorer renders them, for a whole run., Response for a live-LLM run that could not even reach the provider. Returning… (+6 more)

### Community 42 - "FakeClock"
Cohesion: 0.20
Nodes (9): clock(), db_path(), FakeClock, _open(), fixture, Path, test_audit_layers_column_migrates_existing_database(), test_candidate_fix_save_and_promote() (+1 more)

### Community 43 - "make_tools"
Cohesion: 0.11
Nodes (19): build(), executor(), Execute, make_tools(), tool(), Execute, One tool per registry spec; both agents differ only in `execute`. Logs each…, build() (+11 more)

### Community 44 - "Script"
Cohesion: 0.19
Nodes (13): hinted(), parametrize, Attempt callable that replays a fixed list of outcomes and records sleeps., Script, test_backoff_sequence_then_gives_up_after_three_retries(), test_budget_shrinks_between_retries(), test_default_jitter_stays_within_bound(), test_jitter_is_added_to_each_backoff() (+5 more)

### Community 45 - "_coerce_args"
Cohesion: 0.13
Nodes (17): _coerce_args(), _heal_info(), _json_or_text(), _lossless_coerce(), _parse_tool_result(), Any, Cast a value to the type the frozen v1 schema declares, only if lossless., Fit LLM-supplied arguments to the frozen agent-facing schema. A live model… (+9 more)

### Community 46 - "MockApi"
Cohesion: 0.18
Nodes (4): check_custom(), MockApi, Validate a custom drift: one tool, any of rename / to_int / wrap / header /…, `custom` is required for, and only used by, the CUSTOM drift.

### Community 47 - "test_admin.py"
Cohesion: 0.13
Nodes (6): socket, api(), client(), fixture, test_real_http_switch_to_m1(), threading

### Community 49 - "test_ac_34_cli_uses_real_custom_spec_and_closes_resources"
Cohesion: 0.15
Nodes (9): test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(), close(), __init__(), tracked_client(), test_ac_34_cli_uses_real_custom_spec_and_closes_resources(), close(), __init__(), tracked_client() (+1 more)

### Community 50 - "test_ac_43_repair_agent.py"
Cohesion: 0.21
Nodes (13): FakeLlm, asyncio, Exception, parametrize, AC-43 and AC-45: the tier-2 repair agent heals a break tier 1 cannot explain,…, Scripted model: returns `answer` and records every prompt it was sent., SlowLlm, test_ac_43_repair_agent_heals_unexplained_drift_and_fix_is_reused() (+5 more)

### Community 51 - "Tier"
Cohesion: 0.09
Nodes (39): collections, IntEnum, Row, false_patch_rate(), mttr_summary(), outcome_counts(), percentiles(), Any (+31 more)

### Community 54 - "test_registry.py"
Cohesion: 0.21
Nodes (10): calls_to(), fix_for(), parametrize, test_ac_02_invalid_args_no_heal(), test_active_fix_request_ops_are_applied(), test_active_fix_response_ops_reshape_before_contract(), test_fr_3_4_value_rules_are_left_to_the_api(), test_healthy_call() (+2 more)

### Community 55 - "Benchmark pipeline"
Cohesion: 0.14
Nodes (14): Mock drift control contract, Benchmark report view, Live stream comparison, Metrics view, Mutation controls, Benchmark pipeline, Dashboard, Mock drift control (+6 more)

### Community 56 - "test_ac_58_mcp_client_docs.py"
Cohesion: 0.24
Nodes (13): io, _json_blocks(), AC-58: docs/mcp-clients.md is a usable client guide derived from the hand-off…, The CLI flags the server actually accepts, read from its argparse help., _server_flags(), test_ac_58_covers_both_transports(), test_ac_58_documented_flags_exist_on_the_server(), test_ac_58_guide_is_derived_from_the_handoff() (+5 more)

### Community 57 - "run_live"
Cohesion: 0.28
Nodes (9): completed(), parametrize, Run the demo task once; returns (RunResult, mock api, [(tool, class), ...])., New email, manager 456, one ticket, and the lookup itself succeeded., run_live(), test_ac_09_agent_stops_after_retry_false(), test_clean_run_completes(), test_m5_baseline_agent_does_not_complete() (+1 more)

### Community 58 - "build"
Cohesion: 0.16
Nodes (9): Header, min_length, build(), manager_ids(), set_manager(), update_email(), validate_manager(), FastAPI (+1 more)

### Community 60 - "FixStatus"
Cohesion: 0.18
Nodes (10): FixStatus, _keys(), Step 0 contracts between the two tracks (AGENTS.md): OperationSpec, SpecSource,…, Contract 4: Registry exposes tools() and passes tools accessor to Healer., Contract 5: P4's watcher calls Healer.precompute(old: LoadedSpec, new:…, test_contract_4_registry_exposes_tools_accessor(), test_contract_5_spec_change_precompute(), test_injected_spec_source_serves_load_and_heal() (+2 more)

### Community 61 - "test_ac_68_mcp_view.py"
Cohesion: 0.19
Nodes (8): app(), client(), _front_door_tools(), offline(), fixture, AC-68: the dashboard MCP view reports the front door's tools (T2-9, no T1-6)., Build a clean registry the way the MCP server does, and read its tools., test_ac_68_endpoint_lists_exactly_the_front_door_tools()

### Community 62 - "connect_upstreams"
Cohesion: 0.07
Nodes (41): BaseException, What the MCP front door exposes, read from the same `Registry.tools()`., _api_client(), api_registry(), _api_source(), api_tool_config(), _check_names(), connect_upstreams() (+33 more)

### Community 63 - "test_detect.py"
Cohesion: 0.29
Nodes (10): parametrize, Response, r(), raw(), raw_status(), req(), test_ac_03_detector_table(), test_data_carries_decoded_body() (+2 more)

### Community 65 - "p3/conftest.py"
Cohesion: 0.31
Nodes (9): api(), client(), make_registry(), make(), fixture, P3-owned fixtures. Mirrors `tests/integration/conftest.py` for the p3 track., Healing registry (store, no Jev, no real sleeping); keyword arguments override., store() (+1 more)

### Community 67 - "verify.py"
Cohesion: 0.27
Nodes (11): _invalid_request(), _invariants_pass(), Any, OperationSpec, Deterministic preflight and post-response verification., _readback_matches(), _row(), _skip_from() (+3 more)

### Community 69 - "guide.js"
Cohesion: 0.44
Nodes (7): close(), go(), onKey(), open(), openTab(), place(), show()

### Community 70 - "models.py"
Cohesion: 0.14
Nodes (28): _arg_violations(), Descriptor, _request_violations(), check(), _passes(), Any, Output-schema validation (E5) and declarative postchecks (E6) on an OK outcome., _schema_violations() (+20 more)

### Community 74 - "ErrorClass"
Cohesion: 0.22
Nodes (13): random, ErrorClass, E1 retry policy (FR-11.1): bounded backoff with jitter. E1 is retried here and…, Run `attempt`, then retry E1 up to len(E1_BACKOFF_S) times while the budget…, with_retries(), check(), parametrize, test_each_missing_property_is_reported_once() (+5 more)

### Community 75 - "_pass"
Cohesion: 0.17
Nodes (12): _amain(), bench(), main(), _pass(), once(), Namespace, One pass of the benchmark: scenarios x agents x n runs, optionally with a…, The main pass (FR-15.1, FR-15.6) and the error-only ablation (FR-15.7). (+4 more)

### Community 76 - "Gateway"
Cohesion: 0.25
Nodes (8): MCP front-door view, Gateway, MCP Front Door, Built MCP gateway and APIs, Deferred GraphQL, gRPC, Postgres, and streaming work, AC-63 namespaced frozen upstream tools, F24 Upstream MCP gateway, System boundaries and deferred protocols

### Community 77 - "railway.json"
Cohesion: 0.25
Nodes (7): build, builder, dockerfilePath, deploy, healthcheckPath, restartPolicyType, $schema

### Community 78 - "gateway.py"
Cohesion: 0.07
Nodes (30): mcp_client_stdio, mcp_client_streamable_http, os, pathlib, re, Many registries behind one frozen tool list: the shape the MCP front door…, JevClient, AsyncClient (+22 more)

### Community 79 - "One audit row per heal attempt"
Cohesion: 0.29
Nodes (7): Audit before returning heal result, Secrets excluded from store and logs, Patch log, One audit row per heal attempt, SQLite fix and audit store, AC-5 exactly one audit event per heal, F5 Store and audit

### Community 80 - "Registry"
Cohesion: 0.29
Nodes (7): Frozen agent_schema invariant, Registry.tools() and Registry.call() contract, Frozen agent_schema, Registry, tools/call, tools/list, Facade and hot-patching

### Community 82 - "Heal pipeline"
Cohesion: 0.33
Nodes (6): One heal and one replay; no retry loop, Contract verification, Spec diagnosis, Heal pipeline, F10 Patch, verify, commit, Healing tiers 0, 1, Jev, and 2

### Community 83 - "Spec-change precompute"
Cohesion: 0.33
Nodes (6): Spec-change hook, Spec-change precompute, Spec watcher, Built spec watcher, AC-55 spec watcher behavior, F18 Spec watcher

### Community 84 - "ui.js"
Cohesion: 0.67
Nodes (5): apply(), init(), read(), toggles(), write()

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

### Community 94 - "send"
Cohesion: 0.50
Nodes (4): AsyncClient, Exception, Response, send()

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

### Community 108 - "test_ac_26_m10.py"
Cohesion: 0.50
Nodes (4): _assert_no_injection_in_requests(), AC-26 (S8 prompt-injection resistance / Mutation M10): Malicious instruction…, test_ac_26_m10_injection_resistance(), test_ac_26_m10_matches_m1_parity()

### Community 120 - "RepairAgent"
Cohesion: 0.09
Nodes (22): mcp_bench(), mcp_state_ok(), Only user 123's email may differ from the seed, and at most the one expected…, The scripted MCP task per drift-server mutation, through a healing gateway and…, Gateway, One healing registry over one upstream server, exposing every tool it lists., upstream_registry(), _json_object() (+14 more)

### Community 121 - "build_admin"
Cohesion: 0.43
Nodes (5): build_admin(), list_mutations(), mutations(), reset(), set_mutation()

### Community 125 - "test_ui_regressions.py"
Cohesion: 0.29
Nodes (6): shutil, subprocess, skipif, Focused browser-logic regressions for the dashboard stepper., test_ac_18_live_control_steps_and_transient_retry_copy(), test_ac_56_stepper_keeps_task_context_and_failure_states()

### Community 127 - "mcp/conftest.py"
Cohesion: 0.33
Nodes (7): pytest_asyncio, api(), mcp_client(), connect(), mcp_registry(), fixture, tools_config()

### Community 131 - "demo.py"
Cohesion: 0.22
Nodes (11): fix_text(), main(), print_act(), print_summary(), Terminal demo, the fallback for the pitch: `python -m dashboard.demo`. Scripted…, Run every act from a cold store; `step` is the agents' pause between calls., task_done(), render_option() (+3 more)

## Knowledge Gaps
- **80 isolated node(s):** `healer`, `$schema`, `builder`, `dockerfilePath`, `healthcheckPath` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 675 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ErrorClass` connect `ErrorClass` to `HealOutcome`, `test_jev.py`, `PostgresStore`, `Healer`, `test_dashboard.py`, `Reason`, `grpc.py`, `canonical.py`, `test_store.py`, `graphql.py`, `test_scenarios.py`, `Store`, `Outcome`, `Dashboard`, `mcp_upstream.py`, `FixStore`, `registry.py`, `run_explore`, `make_tools`, `Script`, `Tier`, `test_registry.py`, `test_detect.py`, `verify.py`, `models.py`, `detect.py`, `test_ac_26_m10.py`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `Registry` connect `Healer` to `HealOutcome`, `PostgresStore`, `pytest`, `overhead.py`, `graphql_loader.py`, `Outcome`, `create_app`, `test_http.py`, `Dashboard`, `FixStore`, `registry.py`, `integration/conftest.py`, `test_agents.py`, `run_explore`, `test_registry.py`, `run_live`, `test_ac_68_mcp_view.py`, `connect_upstreams`, `p3/conftest.py`, `ErrorClass`, `_pass`, `gateway.py`, `test_ac_26_m10.py`, `RepairAgent`, `mcp/conftest.py`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `Store` connect `Store` to `HealOutcome`, `Healer`, `pytest`, `overhead.py`, `test_store.py`, `test_scenarios.py`, `graphql_loader.py`, `create_app`, `test_http.py`, `Dashboard`, `registry.py`, `sanitize`, `integration/conftest.py`, `test_agents.py`, `run_explore`, `FakeClock`, `_coerce_args`, `test_ac_34_cli_uses_real_custom_spec_and_closes_resources`, `Tier`, `test_registry.py`, `run_live`, `FixStatus`, `test_ac_68_mcp_view.py`, `p3/conftest.py`, `ErrorClass`, `_pass`, `test_ac_26_m10.py`, `RepairAgent`, `mcp/conftest.py`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Are the 96 inferred relationships involving `Reason` (e.g. with `expectation()` and `build()`) actually correct?**
  _`Reason` has 96 INFERRED edges - model-reasoned connections that need verification._
- **Are the 86 inferred relationships involving `ErrorClass` (e.g. with `executor()` and `executor()`) actually correct?**
  _`ErrorClass` has 86 INFERRED edges - model-reasoned connections that need verification._
- **Are the 59 inferred relationships involving `HealOutcome` (e.g. with `_ablation_cell()` and `mcp_section()`) actually correct?**
  _`HealOutcome` has 59 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `Store` (e.g. with `measure_mcp()` and `mcp_bench()`) actually correct?**
  _`Store` has 38 INFERRED edges - model-reasoned connections that need verification._