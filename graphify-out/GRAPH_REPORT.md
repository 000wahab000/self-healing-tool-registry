# Graph Report - self-healing-tool-registry  (2026-10-16)

## Corpus Check
- 198 files · ~142,268 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 9 file(s) not represented in the graph (top: (none) 6, .example 1, .css 1)

## Summary
- 2489 nodes · 5848 edges · 163 communities (141 shown, 22 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 814 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `9250ae3f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_candidates.py
- test_spec_watcher.py
- HealOutcome
- McpDriftServer
- test_jev.py
- test_diagnose.py
- repair.py
- Healer
- operations
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
- contract.py
- PostgresStore
- graphql.py
- test_scenarios.py
- test_stdio.py
- candidates.py
- Store
- Outcome
- test_connections.py
- test_explorer.py
- test_http.py
- apply_ops
- Dashboard
- metrics_view.py
- FixStore
- test_bench.py
- _parse_tool_result
- tiebreak
- integration/conftest.py
- run.py
- Self-Healing Gateway Write-up
- Side
- run_explore
- create_app
- test_agents.py
- Script
- swagger2.py
- build_admin
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
- diagnose.py
- build
- live_safety
- graphql_app.py
- test_ac_68_mcp_view.py
- gateway.py
- test_detect.py
- test_ac_80_lifecycle.py
- p3/conftest.py
- false_patch_rate
- .preflight
- Registry
- guide.js
- Violation
- override
- is_remote
- Already on main (do not rebuild)
- ErrorClass
- test_client_config.py
- Gateway
- railway.json
- models.py
- One audit row per heal attempt
- Registry
- AuditEvent
- Heal pipeline
- Spec-change precompute
- ui.js
- token_overhead
- detect.py
- Safe fix operations
- Safety gate
- Healer
- Self-healing registry
- Z7: One catalog of mutation labels, and an honest denominator
- test_store_pg.py
- _recording_executor
- rest.py
- test_deadline_aborts_and_is_not_negative_cached
- unrecoverable
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
- DecisionPath
- Dashboard Live Interface
- healer
- JSON Schema
- python-dotenv
- Uvicorn
- test_watcher_resilience.py
- mcp_server.py
- test_ac_77_panel_slot.py
- F7: State polls read only new audit rows (should fix, performance)
- test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal
- test_graphql.py
- test_ac_76_audit_since.py
- test_ac_54_mcp_bench.py
- classify_run
- V1: Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, Token Overhead)
- dashboard/app.py
- Z2: L2 validates unknown headers and non-REST patched requests
- check_data_correctness
- registry.js
- F5: A run that calls no tools is not "data-correct" (correctness, must fix)
- Read this before the task file
- V0: A plug-in slot for dashboard panels (foundation for V1-V3)
- V3: Fix lifecycle panel (candidates, promoted rules, spec snapshots)
- Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)
- Z15: ZTAR report with layers, intervals and fuzz (last)
- Z3: L3 / E5 allows only move or unwrap, with response-source provenance
- Z5: L6 invariants catch U1 (wrong units) through the real registry
- Z6: L7 replay guard for upstream MCP tools
- nim_llm
- F1: Reject off-host spec paths (security, must fix)
- F3: Connections routes use the shared auth module (security, must fix)
- F8: Stop tracking generated graph history (housekeeping)
- Z10: Seeded drift fuzzer for held-out ZTAR
- Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)
- Z9: Prove "verify before commit" for every layer (tests only)
- scorecard.js
- Work prompts
- V2: Live safety and timing panel (this session's heals)
- Z11: Never heal non-drift (fault-injection matrix + Retry-After date form)
- test_unsupported_contract.py
- lifecycle.js
- live_safety.js
- page
- Dashboard Panels
- test_explore_llm_surfaces_llm_failure_instead_of_scripted_fallback
- test_failure_layers.py
- test_precompute_guarded_when_no_watcher_exists

## God Nodes (most connected - your core abstractions)
1. `Reason` - 113 edges
2. `ErrorClass` - 110 edges
3. `Store` - 72 edges
4. `HealOutcome` - 71 edges
5. `Outcome` - 57 edges
6. `Side` - 55 edges
7. `Healer` - 51 edges
8. `Registry` - 51 edges
9. `Tier` - 49 edges
10. `FixStore` - 47 edges

## Surprising Connections (you probably didn't know these)
- `Problem` --references--> `is_remote()`  [INFERRED]
  docs/prompts/F3-connections-auth.md → dashboard/connections.py
- `Owns` --references--> `check_data_correctness()`  [INFERRED]
  docs/prompts/F5-explorer-zero-calls.md → dashboard/explorer.py
- `Tasks` --references--> `check_data_correctness()`  [INFERRED]
  docs/prompts/README.md → dashboard/explorer.py
- `Tests (`test_ac_80_*`)` --references--> `fix_lifecycle()`  [INFERRED]
  docs/prompts/V3-fix-lifecycle-panel.md → dashboard/metrics_view.py
- `Build` --references--> `fingerprint()`  [INFERRED]
  docs/prompts/V3-fix-lifecycle-panel.md → src/healer/fingerprint.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Benchmark recovery and safety metrics** — bench_report_zero_touch_adaptation_rate, bench_report_safe_refusal_rate, bench_report_false_patch_rate, bench_report_mttr_and_internal_heal_ms, bench_report_baseline_comparison [EXTRACTED 1.00]

## Communities (163 total, 22 thin omitted)

### Community 0 - "test_candidates.py"
Cohesion: 0.18
Nodes (38): doc(), cand(), cast(), e(), header(), move(), mutation_build(), pairing() (+30 more)

### Community 1 - "test_spec_watcher.py"
Cohesion: 0.14
Nodes (19): walk(), Clock, AC-55: the spec watcher snapshots changes, idles on unchanged specs, backs off…, Injected clock/sleep pair: sleeping moves time forward with no real wait., A SpecSource that serves a scripted sequence and counts its own calls., Minimal FixStore stand-in: records the snapshots the watcher saves., Recorder, spec() (+11 more)

### Community 2 - "HealOutcome"
Cohesion: 0.16
Nodes (24): HealOutcome, calls_to(), jev_reply(), respx side effect: choose the option whose text satisfies `pick`, reading the…, test_ac_07_m6_d_heals_through_the_tiebreaker_without_jev(), test_ac_07_m6_n_jev_at_write_threshold_and_confirming_preverify_recovers(), test_ac_07_m6_n_low_confidence_no_write(), test_ac_07_m6_n_without_preverify_no_write() (+16 more)

### Community 3 - "McpDriftServer"
Cohesion: 0.06
Nodes (42): mcp_shared_exceptions, _admin_tools(), McpDriftServer, call_tool(), list_tools(), Any, Server, Starlette (+34 more)

### Community 4 - "test_jev.py"
Cohesion: 0.06
Nodes (48): from_env(), JevChoice, JevClient, JevUnavailable, AsyncClient, Exception, Prefer TypeSafe direct, then OpenRouter, then opt-in OpenCode free Jev., Timeout, transport or HTTP error, or an answer that is not one of our options. (+40 more)

### Community 5 - "test_diagnose.py"
Cohesion: 0.21
Nodes (21): diff(), make_op(), obj(), param(), Hand-built operations()-shaped dicts: v1 and every mock-API mutation (contracts…, test_input_is_not_mutated_and_ops_do_not_alias_entries(), entry(), leaf() (+13 more)

### Community 6 - "repair.py"
Cohesion: 0.15
Nodes (14): _arg_types(), _dotted(), _entry(), Any, `path: type` for each leaf of the agent's arguments. Values are PII-prone and…, _json_object(), _op_line(), Exception (+6 more)

### Community 7 - "Healer"
Cohesion: 0.13
Nodes (19): Future, _Abort, _Heal, Healer, Any, Ends the heal with a reason. An OpError from the interpreter ends it the same…, The agent's result: data when recovered, an error dict otherwise., Gate, optional dry run, verify, commit: the same path for every tier. (+11 more)

### Community 8 - "operations"
Cohesion: 0.18
Nodes (15): _json_schema(), operations(), OperationSpec, Inline every local `#/...` ref; keywords next to a $ref override the target's., resolve_refs(), _response_schema(), test_fetch_spec_returns_resolved_spec_and_raw_hash(), test_flatten_request_of_loaded_operation() (+7 more)

### Community 9 - "test_dashboard.py"
Cohesion: 0.07
Nodes (40): itertools, langchain_core_language_models_fake_chat_models, langchain_core_outputs, langchain_core_utils_function_calling, pydantic, calls(), capturing_llm(), _generate() (+32 more)

### Community 10 - "test_mock_api.py"
Cohesion: 0.10
Nodes (37): api(), client(), deref(), errors(), get_spec(), lookup_args(), operation(), params() (+29 more)

### Community 11 - "pytest"
Cohesion: 0.12
Nodes (23): asyncio, An in-memory MCP client session over a mock drift server (shared by the MCP…, Path, T1-7: record `tools/list` before and after each mutation (AC-52). Writes…, record(), _tools(), contextlib, mcp (+15 more)

### Community 12 - "Reason"
Cohesion: 0.15
Nodes (31): Reason, (STRETCH, S2) Rule mining: after 3 wins of the same pattern, subsequent…, test_ac_44_rule_mining(), test_ac_05_one_audit_event_per_attempt(), test_ac_09_m8_no_safe_value(), unrecoverable(), Any, parametrize (+23 more)

### Community 13 - "connections.py"
Cohesion: 0.16
Nodes (18): add_connection(), clean_entry(), config_path(), _load(), Path, Connections page backend: add, list, remove and test upstream MCP servers and…, Validate a dashboard-submitted entry (http only) and drop blank optional fields., remove_connection() (+10 more)

### Community 14 - "grpc.py"
Cohesion: 0.07
Nodes (40): FileDescriptorProto, google_protobuf, google_rpc, grpc_reflection_v1alpha, create_server(), _file(), Any, DescriptorPool (+32 more)

### Community 15 - "canonical.py"
Cohesion: 0.11
Nodes (31): dumps(), get(), pop(), put(), Any, Path, Canonical JSON, hashing and path helpers for nested dict/list documents., _step() (+23 more)

### Community 16 - "overhead.py"
Cohesion: 0.14
Nodes (15): _main(), measure(), measure_mcp(), percentile(), _print(), Any, AC-28 (FR-21.1): healthy-call overhead of the registry over the raw transport.…, T1-8: healthy `users__get_user` through Gateway/upstream_registry vs… (+7 more)

### Community 17 - "mock_api/app.py"
Cohesion: 0.11
Nodes (31): fastapi_exceptions, fastapi_security, drifted(), _custom_model(), CustomerRef, CustomerRefM10, EmailOut, _header_dep() (+23 more)

### Community 18 - "test_store.py"
Cohesion: 0.09
Nodes (42): Done when, F4: Redact the real upstream token in the audit log (security, must fix), Owns, Problem, Tests (`test_ac_73_*`), FR-5.7: the audit blob keeps no secret. Redact, then truncate (so a cut cannot…, sanitize(), clock() (+34 more)

### Community 19 - "contract.py"
Cohesion: 0.39
Nodes (7): check(), _passes(), Any, Output-schema validation (E5) and declarative postchecks (E6) on an OK outcome., _schema_violations(), PostcheckType, StrEnum

### Community 20 - "PostgresStore"
Cohesion: 0.10
Nodes (9): Build, Done when, F6: Make the Postgres store fail loudly instead of mid-heal (should fix), Owns, Problem, PostgresStore, Synchronous FixStore backed by Postgres; active reads always query committed…, pg_store() (+1 more)

### Community 21 - "graphql.py"
Cohesion: 0.22
Nodes (12): _arg_violations(), classify(), _literal(), AsyncClient, Exception, Response, _query(), GraphQL HTTP transport and machine-readable error normalization. (+4 more)

### Community 22 - "test_scenarios.py"
Cohesion: 0.12
Nodes (25): assert_first_heal(), call_for(), calls_to(), check_m1(), check_m2(), check_m4(), check_m5(), check_m9() (+17 more)

### Community 23 - "test_stdio.py"
Cohesion: 0.11
Nodes (16): ClientSession, session(), shutil, subprocess, skipif, Focused browser-logic regressions for the dashboard stepper., test_ac_18_live_control_steps_and_transient_retry_copy(), test_ac_56_stepper_keeps_task_context_and_failure_states() (+8 more)

### Community 24 - "candidates.py"
Cohesion: 0.16
Nodes (25): Option, _assign(), build(), _cast(), _clue_fills(), _clue_response_ops(), _dry_run(), _evidence() (+17 more)

### Community 25 - "Store"
Cohesion: 0.11
Nodes (9): Persist a fix and its success event together, updating caches after commit., _safe_layers(), Store, test_sqlite_store_implements_fix_store(), _protocol_config(), asyncio, parametrize, test_ac_38_registry_graphql_heals_and_keeps_schema_frozen() (+1 more)

### Community 26 - "Outcome"
Cohesion: 0.15
Nodes (21): Readback, SpecSource, Outcome, Compatibility wrapper; integrations should use preflight/verify_response…, Use ``preflight`` before sending, then ``verify_response`` after replay., Verifier, verify(), _async_value() (+13 more)

### Community 27 - "test_connections.py"
Cohesion: 0.11
Nodes (21): fastapi_testclient, TestClient, cfg_file(), client(), fixture, MonkeyPatch, parametrize, Path (+13 more)

### Community 28 - "test_explorer.py"
Cohesion: 0.09
Nodes (8): client(), offline(), fixture, parametrize, Tests for the Explorer endpoints (/api/explorer/info and /api/explore)., M6-N refuses set_manager (step 3); the agent still opens the ticket (step 4)., test_explore_controls_pass_business_errors_through(), test_explore_refused_tool_is_skipped_and_the_task_continues()

### Community 29 - "test_http.py"
Cohesion: 0.15
Nodes (16): AsyncExitStack, create_http_app(), Starlette, _client(), http_app(), _initialize_body(), fixture, _session() (+8 more)

### Community 30 - "apply_ops"
Cohesion: 0.17
Nodes (23): apply_ops(), cast_op(), parametrize, reason_of(), test_ac_41_enum_map_bijective_and_lossy(), test_ac_42_encoding_sets_content_type(), test_apply_ops_does_not_mutate_input(), test_cast_lossless() (+15 more)

### Community 31 - "Dashboard"
Cohesion: 0.21
Nodes (4): Dashboard, A scenario (and a live-LLM one can take minutes) holds the lock for its whole…, Once both agents finish an LLM run, remember the measured token pair., Both agents run the demo task against their own mock; the store is shared.

### Community 32 - "metrics_view.py"
Cohesion: 0.13
Nodes (17): get_scorecard(), _parse_markdown_table(), parse_report_markdown(), Any, Path, Pure metric views for dashboard panels (AC-78, AC-79, AC-80). No FastAPI…, Load benchmark report and return scorecard metrics. Never invent numbers., Parse benchmark report markdown into scorecard metric structures. (+9 more)

### Community 33 - "FixStore"
Cohesion: 0.09
Nodes (4): Protocol, _fix(), FixStore, What the registry, the healer and the demo call on a store. SQLite (`Store`)…

### Community 34 - "test_bench.py"
Cohesion: 0.11
Nodes (29): agent_rows(), main(), one(), out(), fixture, parametrize, Benchmark runner and report tests (FR-15.1 to 15.8; AC-14, AC-15, AC-16, AC-17,…, AC-14: tier-1 MTTR p95 < 4.0 s for M1 to M5 (tier 0 < 0.5 s), heal_ms alongside. (+21 more)

### Community 35 - "_parse_tool_result"
Cohesion: 0.29
Nodes (8): _json_or_text(), _lossless_coerce(), _parse_tool_result(), Any, Cast a value to the type the frozen v1 schema declares, only if lossless., Parse a JSON payload; keep the raw text when it is not JSON., Baseline tools answer with raw `HTTP n: body`; healers answer with JSON., test_parse_tool_result_handles_both_agents()

### Community 36 - "tiebreak"
Cohesion: 0.12
Nodes (19): Build, Done when, Owns, Problem, Tests (`test_ac_89_*`), Z8: Evidence ranking, and refusal on a tie, _described(), FR-7.6: the index of the one candidate that strictly beats the rest, else None.… (+11 more)

### Community 37 - "integration/conftest.py"
Cohesion: 0.15
Nodes (17): api(), client(), jev(), make_registry(), make(), AsyncBaseTransport, fixture, Request (+9 more)

### Community 38 - "run.py"
Cohesion: 0.11
Nodes (33): _ablation_cell(), _amain(), bench(), expectation(), _failure_mode(), main(), mcp_section(), mcp_state_ok() (+25 more)

### Community 39 - "Self-Healing Gateway Write-up"
Cohesion: 0.08
Nodes (40): Coding Agent Rules, Module Contracts and Working Rules, Baseline comparison, False-Patch Rate, Healthy MCP-call overhead, LLM token cost not measured, MCP heal evidence: 12/12, MTTR and internal heal_ms (+32 more)

### Community 40 - "Side"
Cohesion: 0.24
Nodes (20): from_violations(), Error-clue mode: no spec, so only flat single-family fixes (technical-approach…, Side, parametrize, test_clue_ambiguous_names_give_one_candidate_per_assignment(), test_clue_m1_missing_field_filled_from_name_matching_argument(), test_clue_m2_type_error_becomes_cast(), test_clue_m4_auth_violation_becomes_header() (+12 more)

### Community 41 - "run_explore"
Cohesion: 0.14
Nodes (14): extract_tool_schemas(), _heal_summaries(), _llm_bootstrap_error(), Extract input and output schemas from a resolved OpenAPI spec for each…, Provider errors arrive as a page of JSON; the UI only needs the headline., Read-only view of every ToolDefinition after the run., Audit events as the explorer renders them, for a whole run., Response for a live-LLM run that could not even reach the provider. Returning… (+6 more)

### Community 42 - "create_app"
Cohesion: 0.12
Nodes (7): bad_request(), create_app(), explorer_info(), mutation(), start(), FastAPI, get_explorer_info()

### Community 43 - "test_agents.py"
Cohesion: 0.05
Nodes (71): agents, build(), executor(), Execute, Baseline agent: same tools, but each call is a bare v1 HTTP request. No…, make_llm(), make_tools(), Execute (+63 more)

### Community 44 - "Script"
Cohesion: 0.19
Nodes (13): hinted(), parametrize, Attempt callable that replays a fixed list of outcomes and records sleeps., Script, test_backoff_sequence_then_gives_up_after_three_retries(), test_budget_shrinks_between_retries(), test_default_jitter_stays_within_bound(), test_jitter_is_added_to_each_backoff() (+5 more)

### Community 45 - "swagger2.py"
Cohesion: 0.13
Nodes (17): convert(), _operation(), _param_schema(), Any, Convert a Swagger 2.0 document to the OpenAPI 3 shape `operations()` reads…, Reshape a Swagger 2.0 document into the OpenAPI 3 shape `operations()` reads.…, Deep copy `node`, pointing every local `#/definitions/...` ref at…, Lift a 2.0 non-body parameter's type keywords into the OpenAPI 3 `schema`… (+9 more)

### Community 46 - "build_admin"
Cohesion: 0.13
Nodes (9): build_admin(), list_mutations(), mutations(), reset(), set_mutation(), check_custom(), MockApi, Validate a custom drift: one tool, any of rename / to_int / wrap / header /… (+1 more)

### Community 47 - "create_app"
Cohesion: 0.10
Nodes (15): create_app(), pytest_asyncio, socket, api(), mcp_client(), connect(), mcp_registry(), fixture (+7 more)

### Community 48 - "LoadedSpec"
Cohesion: 0.10
Nodes (26): mcp_source(), source(), ClientSession, OperationSpec, SpecSource, Read the upstream's tools/list. Names starting with `__` are reserved (admin…, to_operation(), sha256() (+18 more)

### Community 49 - "test_ac_34_cli_uses_real_custom_spec_and_closes_resources"
Cohesion: 0.15
Nodes (9): test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(), close(), __init__(), tracked_client(), test_ac_34_cli_uses_real_custom_spec_and_closes_resources(), close(), __init__(), tracked_client() (+1 more)

### Community 50 - "test_ac_43_repair_agent.py"
Cohesion: 0.21
Nodes (13): FakeLlm, asyncio, Exception, parametrize, AC-43 and AC-45: the tier-2 repair agent heals a break tier 1 cannot explain,…, Scripted model: returns `answer` and records every prompt it was sent., SlowLlm, test_ac_43_repair_agent_heals_unexplained_drift_and_fix_is_reused() (+5 more)

### Community 51 - "Tier"
Cohesion: 0.14
Nodes (26): collections, Build, Why, IntEnum, mttr_summary(), outcome_counts(), percentiles(), Any (+18 more)

### Community 52 - "mcp_agent.py"
Cohesion: 0.14
Nodes (15): argparse, main(), ClientSession, Demo agent: one task over two upstream MCP servers, through the healer front…, Run the task once; returns calls, errors seen by the agent and the audit rows., Calls the front door, prints each call, and notes heals read from the shared…, LangGraph ReAct agent whose tools are the front door's tools (same shape as…, run_demo() (+7 more)

### Community 53 - "SpecWatcher"
Cohesion: 0.13
Nodes (8): Build, FR-17.11 (X4): Precompute candidate fixes from spec diffs before any failure…, SpecSource, Contract 5: only the healer that provides precompute is called; snapshots still…, The spec last seen per source (read-only copy)., Poll every due source once. Return the names whose spec changed., SpecWatcher, Task

### Community 54 - "test_registry.py"
Cohesion: 0.21
Nodes (10): calls_to(), fix_for(), parametrize, test_ac_02_invalid_args_no_heal(), test_active_fix_request_ops_are_applied(), test_active_fix_response_ops_reshape_before_contract(), test_fr_3_4_value_rules_are_left_to_the_api(), test_healthy_call() (+2 more)

### Community 55 - "Benchmark pipeline"
Cohesion: 0.15
Nodes (13): Mock drift control contract, Benchmark report view, Live stream comparison, Mutation controls, Benchmark pipeline, Dashboard, Mock drift control, LLM-mode metrics not measured (+5 more)

### Community 56 - "test_ac_58_mcp_client_docs.py"
Cohesion: 0.16
Nodes (16): io, re, nav_labels(), test_ac_56_navbar_items_order_active_and_report_stability(), _json_blocks(), AC-58: docs/mcp-clients.md is a usable client guide derived from the hand-off…, The CLI flags the server actually accepts, read from its argparse help., _server_flags() (+8 more)

### Community 57 - "diagnose.py"
Cohesion: 0.18
Nodes (18): _diff_leaves(), diff_signature(), _entry(), flatten_request(), flatten_response(), _index(), _leaf(), _leaves() (+10 more)

### Community 58 - "build"
Cohesion: 0.18
Nodes (9): Header, min_length, build(), manager_ids(), set_manager(), update_email(), validate_manager(), FastAPI (+1 more)

### Community 59 - "live_safety"
Cohesion: 0.15
Nodes (12): tool(), registry_call(), get_metrics_live(), live_safety(), Live session safety, timing and refusal metrics (AC-79). Pure function., app(), client(), offline() (+4 more)

### Community 60 - "graphql_app.py"
Cohesion: 0.16
Nodes (9): GraphQLMock, update_email(), FastAPI, Small Strawberry GraphQL mock for protocol-drift tests., User, UserEnvelope, strawberry, strawberry_fastapi (+1 more)

### Community 61 - "test_ac_68_mcp_view.py"
Cohesion: 0.19
Nodes (8): app(), client(), _front_door_tools(), offline(), fixture, AC-68: the dashboard MCP view reports the front door's tools (T2-9, no T1-6)., Build a clean registry the way the MCP server does, and read its tools., test_ac_68_endpoint_lists_exactly_the_front_door_tools()

### Community 62 - "gateway.py"
Cohesion: 0.08
Nodes (43): BaseException, mcp_bench(), The scripted MCP task per drift-server mutation, through a healing gateway and…, What the MCP front door exposes, read from the same `Registry.tools()`., Default registry config: a tool is a write unless the upstream says it is read-…, tool_config(), _api_client(), api_registry() (+35 more)

### Community 63 - "test_detect.py"
Cohesion: 0.29
Nodes (10): parametrize, Response, r(), raw(), raw_status(), req(), test_ac_03_detector_table(), test_data_carries_decoded_body() (+2 more)

### Community 64 - "test_ac_80_lifecycle.py"
Cohesion: 0.16
Nodes (13): get_metrics_lifecycle(), fix_lifecycle(), Fix lifecycle view: rules, candidates, active fixes and replays (AC-80). Read-…, app(), client(), offline(), AsyncClient, fixture (+5 more)

### Community 65 - "p3/conftest.py"
Cohesion: 0.31
Nodes (9): api(), client(), make_registry(), make(), fixture, P3-owned fixtures. Mirrors `tests/integration/conftest.py` for the p3 track., Healing registry (store, no Jev, no real sleeping); keyword arguments override., store() (+1 more)

### Community 66 - "false_patch_rate"
Cohesion: 0.07
Nodes (30): Why, Build, Done when, Owns, Tests (`test_ac_93_*`), Why, Z12: Wilson 95% confidence intervals and N=30, Build (+22 more)

### Community 67 - ".preflight"
Cohesion: 0.15
Nodes (16): Build, Build, Done when, Owns, Problem, Tests (`test_ac_82_*`), Z1: L1 provenance checks enum targets against the current spec, _invalid_request() (+8 more)

### Community 68 - "Registry"
Cohesion: 0.19
Nodes (8): Build, Build, api_error(), AsyncClient, SpecSource, Send `base` through `fix` (request ops, response ops), classify, check the…, Registry, ToolDefinition

### Community 69 - "guide.js"
Cohesion: 0.44
Nodes (7): close(), go(), onKey(), open(), openTab(), place(), show()

### Community 70 - "Violation"
Cohesion: 0.17
Nodes (18): hashlib, _payload(), Any, Upstream MCP servers as a protocol (contract 7): tools/list -> OperationSpec,…, send(), fingerprint(), Stable break identity (FR-4): same break, same fingerprint, across runs and…, Violation (+10 more)

### Community 71 - "override"
Cohesion: 0.16
Nodes (13): override(), Request, Response, Answer requests to `path` with `make(request)` (None passes through); returns…, E4: the API answers 200 with an error body to the v1 request, and works for the…, soft_error_for_old_shape(), test_ac_20_e4_on_idempotent_tool_is_replayed(), test_ac_20_e4_on_non_idempotent_tool_without_key_is_unsafe_replay() (+5 more)

### Community 72 - "is_remote"
Cohesion: 0.20
Nodes (13): is_remote(), list_connections(), Request, Local = the browser runs on this machine and no proxy forwarded the request.…, require_write(), Build, Done when, F2: Shared dashboard auth module, guarding write routes (security, must fix) (+5 more)

### Community 73 - "Already on main (do not rebuild)"
Cohesion: 0.20
Nodes (12): Build, Done when, Owns, Problem, Tests (`test_ac_85_*`), Z4: L5 read-back for every write tool, Already on main (do not rebuild), Current layer status (+4 more)

### Community 74 - "ErrorClass"
Cohesion: 0.20
Nodes (14): random, ErrorClass, E1 retry policy (FR-11.1): bounded backoff with jitter. E1 is retried here and…, Run `attempt`, then retry E1 up to len(E1_BACKOFF_S) times while the budget…, with_retries(), test_demo_runs_the_pitch_flow(), check(), parametrize (+6 more)

### Community 75 - "test_client_config.py"
Cohesion: 0.16
Nodes (15): dotenv, mcp_client_streamable_http, os, sys, _connect(), _load_target(), Path, skipif (+7 more)

### Community 76 - "Gateway"
Cohesion: 0.25
Nodes (8): MCP front-door view, Gateway, MCP Front Door, Built MCP gateway and APIs, Deferred GraphQL, gRPC, Postgres, and streaming work, AC-63 namespaced frozen upstream tools, F24 Upstream MCP gateway, System boundaries and deferred protocols

### Community 77 - "railway.json"
Cohesion: 0.25
Nodes (7): build, builder, dockerfilePath, deploy, healthcheckPath, restartPolicyType, $schema

### Community 78 - "models.py"
Cohesion: 0.08
Nodes (38): collections_abc, Explorer module: reference metadata, predefined queries, and detailed schema &…, dataclasses, Enum, inspect, jsonschema, logging, sqlite3 (+30 more)

### Community 79 - "One audit row per heal attempt"
Cohesion: 0.29
Nodes (7): Audit before returning heal result, Secrets excluded from store and logs, Patch log, One audit row per heal attempt, SQLite fix and audit store, AC-5 exactly one audit event per heal, F5 Store and audit

### Community 80 - "Registry"
Cohesion: 0.29
Nodes (7): Frozen agent_schema invariant, Registry.tools() and Registry.call() contract, Frozen agent_schema, Registry, tools/call, tools/list, Facade and hot-patching

### Community 81 - "AuditEvent"
Cohesion: 0.18
Nodes (4): Row, AuditEvent, _event(), Return ordered rows after the cursor; the id is separate from AuditEvent…

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
Cohesion: 0.26
Nodes (12): Problem, classify(), _error_body(), _is_soft_error(), _kind(), Exception, Response, Response classification (technical-approach 5.1, steps 1-5). Schema and… (+4 more)

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

### Community 91 - "Z7: One catalog of mutation labels, and an honest denominator"
Cohesion: 0.18
Nodes (11): Room for later (ZTAR), ZTAR lanes, ZTAR series (Z0-Z15), Build, Build, Done when, Owns, Problem (+3 more)

### Community 92 - "test_store_pg.py"
Cohesion: 0.26
Nodes (10): make_fix(), _no_sleep(), test_ac_39_shared_active_fix_and_database_uniqueness(), test_ac_39_two_registries_reuse_m1_fix_at_tier0(), test_pg_concurrent_saves_leave_one_active_fix(), save(), test_pg_fix_active_and_candidate_round_trip_and_retired_read(), test_pg_invalid_enum_rolls_back_active_fix_retirement() (+2 more)

### Community 93 - "_recording_executor"
Cohesion: 0.18
Nodes (11): _coerce_args(), _heal_info(), Fit LLM-supplied arguments to the frozen agent-facing schema. A live model…, What actually reached the mock API during one call. Header values are never…, The heal the registry performed during one call, if it performed one., Wrap an Execute so every call, whatever the LLM decides to call, is traced.…, _recording_executor(), recording() (+3 more)

### Community 94 - "rest.py"
Cohesion: 0.33
Nodes (5): AsyncClient, Exception, Response, REST adapter: send a request document (contract C1), return the raw result., send()

### Community 95 - "test_deadline_aborts_and_is_not_negative_cached"
Cohesion: 0.40
Nodes (3): Monotonic clock that jumps `step` seconds on every read., StepClock, test_deadline_aborts_and_is_not_negative_cached()

### Community 96 - "unrecoverable"
Cohesion: 0.20
Nodes (10): m1_fix(), A stored fix for the M1 break on get_user: 422, body.customer_id missing., test_ac_12_negative_cache_known_unfixable(), test_ac_13_jev_unavailable_m6_n_aborts_low_confidence_without_a_write(), test_ac_13_jev_unconfigured_m6_n_aborts_low_confidence_m6_d_still_heals(), test_fr_6_4_spec_mode_off_aborts_a_combined_change(), test_op_error_while_applying_a_fix_becomes_an_abort(), test_stale_stored_fix_records_loss_and_is_negative_cached() (+2 more)

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

### Community 108 - "DecisionPath"
Cohesion: 0.24
Nodes (8): DecisionPath, _assert_no_injection_in_requests(), AC-26 (S8 prompt-injection resistance / Mutation M10): Malicious instruction…, test_ac_26_m10_injection_resistance(), test_ac_26_m10_matches_m1_parity(), test_ac_61_swagger2_fixture_heals_m1(), test_pg_store_audit_snapshots_calls_and_negative_cache(), event()

### Community 119 - "test_watcher_resilience.py"
Cohesion: 0.40
Nodes (3): asyncio, The watcher keeps polling after an unexpected error (review fix)., test_watcher_survives_an_unexpected_poll_error()

### Community 120 - "mcp_server.py"
Cohesion: 0.07
Nodes (22): mcp_server_lowlevel, mcp_server_transport_security, mcp_types, Gateway, _arguments(), create_server(), main(), Namespace (+14 more)

### Community 121 - "test_ac_77_panel_slot.py"
Cohesion: 0.24
Nodes (5): app(), client(), offline(), fixture, AC-77: A plug-in slot for dashboard panels (V0 foundation).

### Community 122 - "F7: State polls read only new audit rows (should fix, performance)"
Cohesion: 0.22
Nodes (7): What the registry kept away from the agents, since the last Reset. Counted from…, Build, Done when, F7: State polls read only new audit rows (should fix, performance), Owns, Problem, Tests (`test_ac_76_*`)

### Community 124 - "test_graphql.py"
Cohesion: 0.33
Nodes (8): create_app(), operations(), OperationSpec, _schema(), _introspection(), test_ac_38_graphql_introspection_maps_argument_and_nested_response(), test_ac_38_graphql_mock_admin_mutation(), test_ac_38_graphql_rejects_custom_scalars()

### Community 125 - "test_ac_76_audit_since.py"
Cohesion: 0.33
Nodes (6): asyncio, MonkeyPatch, Path, test_ac_76_audit_events_since_uses_ordered_event_ids(), test_ac_76_dashboard_caches_incremental_audits_and_reset(), test_ac_76_scripted_state_matches_legacy_render_and_live_reset_counts()

### Community 126 - "test_ac_54_mcp_bench.py"
Cohesion: 0.29
Nodes (5): bench, AC-28 (FR-21.1): a healthy Registry.call() adds < 10 ms p95 over the raw…, test_ac_28_healthy_overhead(), AC-54: MCP drift scenarios in the benchmark: heal, refuse safely, never false-…, test_ac_54_report_has_mcp_section()

### Community 127 - "classify_run"
Cohesion: 0.36
Nodes (7): classify_request(), classify_run(), Any, Request-level benchmark oracle, independent of the resulting mock state., Classify one target request; rejected requests are not false patches., Use the target operation's accepted request, including renamed-route attempts., test_m7_accepted_original_body_is_wrong_according_to_request_oracle()

### Community 130 - "V1: Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, Token Overhead)"
Cohesion: 0.25
Nodes (7): Data source, Done when, Owns, Panel, Response shape, Tests (`test_ac_78_*`), V1: Benchmark scorecard panel (ZTAR, False-Patch, Safe-Refusal, Token Overhead)

### Community 131 - "dashboard/app.py"
Cohesion: 0.12
Nodes (20): copy, ExploreIn, MutationIn, BaseModel, Live demo dashboard: two in-process mock APIs, the healing and baseline agents,…, StartIn, fix_text(), main() (+12 more)

### Community 132 - "Z2: L2 validates unknown headers and non-REST patched requests"
Cohesion: 0.25
Nodes (7): Build, Done when, Owns, Problem, Tests (`test_ac_83_*`), Z2: L2 validates unknown headers and non-REST patched requests, _strict()

### Community 133 - "check_data_correctness"
Cohesion: 0.43
Nodes (6): check_data_correctness(), Verify mock API state against expected values. `touched` restricts the verdict…, test_ac_74_control_mutations_accept_seeded_state_without_calls(), test_ac_74_scoped_completed_run_is_correct(), test_ac_74_zero_calls_checks_full_task(), test_correctness_is_scoped_to_the_tools_actually_called()

### Community 134 - "registry.js"
Cohesion: 0.48
Nodes (4): mountAll(), mountPanel(), refresh(), register()

### Community 135 - "F5: A run that calls no tools is not "data-correct" (correctness, must fix)"
Cohesion: 0.29
Nodes (6): Build, Done when, F5: A run that calls no tools is not "data-correct" (correctness, must fix), Owns, Problem, Tests (`test_ac_74_*`)

### Community 136 - "Read this before the task file"
Cohesion: 0.29
Nodes (6): Before you write code, Done means, Git, Hard rules, Read this before the task file, Tests

### Community 137 - "V0: A plug-in slot for dashboard panels (foundation for V1-V3)"
Cohesion: 0.29
Nodes (6): Done when, Owns, Room for later, Tests (`test_ac_77_*`), V0: A plug-in slot for dashboard panels (foundation for V1-V3), Why

### Community 138 - "V3: Fix lifecycle panel (candidates, promoted rules, spec snapshots)"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Tests (`test_ac_80_*`), V3: Fix lifecycle panel (candidates, promoted rules, spec snapshots), Why

### Community 139 - "Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)"
Cohesion: 0.29
Nodes (6): Done when, Owns, Room for later, Tests (`test_ac_81_*`), Why, Z0: Split verify.py into one module per layer (refactor, foundation for Z1-Z6)

### Community 140 - "Z15: ZTAR report with layers, intervals and fuzz (last)"
Cohesion: 0.29
Nodes (6): Build, Done when, Final PR body must include, Owns, Tests (`test_ac_96_*`), Z15: ZTAR report with layers, intervals and fuzz (last)

### Community 141 - "Z3: L3 / E5 allows only move or unwrap, with response-source provenance"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Problem, Tests (`test_ac_84_*`), Z3: L3 / E5 allows only move or unwrap, with response-source provenance

### Community 142 - "Z5: L6 invariants catch U1 (wrong units) through the real registry"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Problem, Tests (`test_ac_86_*`), Z5: L6 invariants catch U1 (wrong units) through the real registry

### Community 143 - "Z6: L7 replay guard for upstream MCP tools"
Cohesion: 0.29
Nodes (6): Build, Done when, Owns, Problem, Tests (`test_ac_87_*`), Z6: L7 replay guard for upstream MCP tools

### Community 144 - "nim_llm"
Cohesion: 0.29
Nodes (5): Llm, from_env(), nim_llm(), AsyncClient, An OpenAI-compatible chat endpoint (NVIDIA NIM by default).

### Community 145 - "F1: Reject off-host spec paths (security, must fix)"
Cohesion: 0.33
Nodes (5): Done when, F1: Reject off-host spec paths (security, must fix), Owns, Problem, Tests (`test_ac_70_*`)

### Community 146 - "F3: Connections routes use the shared auth module (security, must fix)"
Cohesion: 0.33
Nodes (5): Done when, F3: Connections routes use the shared auth module (security, must fix), Owns, Problem, Tests (`test_ac_72_*`)

### Community 147 - "F8: Stop tracking generated graph history (housekeeping)"
Cohesion: 0.33
Nodes (5): Build, Done when, F8: Stop tracking generated graph history (housekeeping), Owns, Problem

### Community 148 - "Z10: Seeded drift fuzzer for held-out ZTAR"
Cohesion: 0.33
Nodes (5): Done when, Owns, Tests (`test_ac_91_*`), Why, Z10: Seeded drift fuzzer for held-out ZTAR

### Community 149 - "Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)"
Cohesion: 0.33
Nodes (5): Build, Done when, Owns, Tests (`test_ac_95_*`), Z14: Loader gaps (cyclic `$ref`, MCP pagination, retry jitter)

### Community 150 - "Z9: Prove "verify before commit" for every layer (tests only)"
Cohesion: 0.33
Nodes (5): Build, Done when, Owns, Why, Z9: Prove "verify before commit" for every layer (tests only)

### Community 151 - "scorecard.js"
Cohesion: 0.80
Nodes (4): el(), median(), render(), statTile()

### Community 152 - "Work prompts"
Cohesion: 0.40
Nodes (4): Parallel lanes (no shared files), Room for future modules, Tasks, Work prompts

### Community 153 - "V2: Live safety and timing panel (this session's heals)"
Cohesion: 0.40
Nodes (4): Done when, Owns, Tests (`test_ac_79_*`), V2: Live safety and timing panel (this session's heals)

### Community 154 - "Z11: Never heal non-drift (fault-injection matrix + Retry-After date form)"
Cohesion: 0.40
Nodes (4): Build, Done when, Owns, Z11: Never heal non-drift (fault-injection matrix + Retry-After date form)

### Community 155 - "test_unsupported_contract.py"
Cohesion: 0.40
Nodes (4): parametrize, test_missing_fix_store_methods_fail_loudly(), test_postgres_construction_warns_before_connecting(), types

### Community 156 - "lifecycle.js"
Cohesion: 0.83
Nodes (3): el(), formatOp(), render()

### Community 157 - "live_safety.js"
Cohesion: 1.00
Nodes (3): el(), render(), statTile()

### Community 158 - "page"
Cohesion: 0.67
Nodes (3): page(), FileResponse, get

## Knowledge Gaps
- **183 isolated node(s):** `healer`, `$schema`, `builder`, `dockerfilePath`, `healthcheckPath` (+178 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 846 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ErrorClass` connect `ErrorClass` to `HealOutcome`, `test_jev.py`, `Healer`, `test_dashboard.py`, `Reason`, `connections.py`, `grpc.py`, `canonical.py`, `test_store.py`, `contract.py`, `PostgresStore`, `graphql.py`, `test_scenarios.py`, `Store`, `Outcome`, `Dashboard`, `FixStore`, `run_explore`, `test_agents.py`, `Script`, `Tier`, `test_registry.py`, `live_safety`, `test_detect.py`, `.preflight`, `Registry`, `Violation`, `override`, `models.py`, `AuditEvent`, `detect.py`, `test_store_pg.py`, `_recording_executor`, `unrecoverable`, `DecisionPath`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `Store` connect `Store` to `HealOutcome`, `dashboard/app.py`, `Healer`, `overhead.py`, `test_store.py`, `test_scenarios.py`, `test_connections.py`, `Dashboard`, `FixStore`, `integration/conftest.py`, `run.py`, `run_explore`, `test_agents.py`, `create_app`, `test_ac_34_cli_uses_real_custom_spec_and_closes_resources`, `mcp_agent.py`, `test_registry.py`, `test_ac_68_mcp_view.py`, `gateway.py`, `test_ac_80_lifecycle.py`, `p3/conftest.py`, `ErrorClass`, `models.py`, `AuditEvent`, `_recording_executor`, `DecisionPath`, `mcp_server.py`, `test_ac_76_audit_since.py`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `Dashboard` connect `Dashboard` to `HealOutcome`, `dashboard/app.py`, `Registry`, `test_dashboard.py`, `create_app`, `ErrorClass`, `AuditEvent`, `Store`, `F7: State polls read only new audit rows (should fix, performance)`, `test_explorer.py`, `gateway.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 99 inferred relationships involving `Reason` (e.g. with `expectation()` and `Owns`) actually correct?**
  _`Reason` has 99 INFERRED edges - model-reasoned connections that need verification._
- **Are the 88 inferred relationships involving `ErrorClass` (e.g. with `executor()` and `executor()`) actually correct?**
  _`ErrorClass` has 88 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `Store` (e.g. with `measure_mcp()` and `mcp_bench()`) actually correct?**
  _`Store` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 63 inferred relationships involving `HealOutcome` (e.g. with `_ablation_cell()` and `mcp_section()`) actually correct?**
  _`HealOutcome` has 63 INFERRED edges - model-reasoned connections that need verification._