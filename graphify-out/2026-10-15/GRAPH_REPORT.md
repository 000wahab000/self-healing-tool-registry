# Graph Report - self-healing-tool-registry  (2026-10-15)

## Corpus Check
- 80 files · ~96,050 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 7 file(s) not represented in the graph (top: (none) 5, .example 1, .css 1)

## Summary
- 1297 nodes · 3210 edges · 79 communities (55 shown, 24 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 457 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `15ad9ca9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_heal.py
- test_candidates.py
- test_agents.py
- Healer
- mock_api/app.py
- Store
- test_mock_api.py
- test_dashboard.py
- test_jev.py
- diagnose.py
- test_store.py
- pytest
- report
- dashboard/app.py
- Tier
- candidates.py
- test_bench.py
- test_scenarios.py
- test_openapi_loader.py
- test_explorer.py
- openapi_source
- contract.py
- models.py
- run.py
- fixture
- common.py
- Reason
- run_explore
- Dashboard
- Heal Controller
- safe_refusal
- Four-Person Ownership
- Research Notes
- _coerce_args
- token_overhead
- test_registry.py
- operations
- railway.json
- Self-Healing Tool Registry
- Tool Registry
- Benchmark Metrics
- Deterministic Candidate Tie-Breaker
- Benchmark Report
- send
- Negative Cache
- FastAPI
- Operation Interpreter
- Frozen Agent Schema
- Secret Hygiene
- Proposed Solution
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
- test_ac_34_cli_uses_real_custom_spec_and_closes_resources
- override
- mcp_server.py
- test_agents_live.py
- test_ac_14_mttr_and_heal_ms_reported_per_tier_with_p95_targets
- fixture
- false_patch_rate
- httpx
- test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal
- StepClock
- make_event

## God Nodes (most connected - your core abstractions)
1. `Reason` - 102 edges
2. `ErrorClass` - 71 edges
3. `HealOutcome` - 53 edges
4. `Store` - 44 edges
5. `Side` - 41 edges
6. `Healer` - 37 edges
7. `Tier` - 37 edges
8. `DecisionPath` - 34 edges
9. `Registry` - 32 edges
10. `Outcome` - 30 edges

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

## Communities (79 total, 24 thin omitted)

### Community 0 - "test_heal.py"
Cohesion: 0.13
Nodes (36): DecisionPath, HealOutcome, calls_to(), jev_reply(), m1_fix(), respx side effect: choose the option whose text satisfies `pick`, reading the…, A stored fix for the M1 break on get_user: 422, body.customer_id missing., test_ac_07_m6_d_heals_through_the_tiebreaker_without_jev() (+28 more)

### Community 1 - "test_candidates.py"
Cohesion: 0.09
Nodes (72): _described(), from_violations(), FR-7.6: the index of the one candidate that strictly beats the rest, else None.…, Error-clue mode: no spec, so only flat single-family fixes (technical-approach…, tiebreak(), Side, doc(), obj() (+64 more)

### Community 2 - "test_agents.py"
Cohesion: 0.12
Nodes (35): make_llm(), run(), AIMessage, ChatOpenAI, GenericFakeChatModel, langchain_core_language_models_fake_chat_models, langchain_core_messages, langchain_core_utils_function_calling (+27 more)

### Community 3 - "Healer"
Cohesion: 0.06
Nodes (44): expectation(), once(), What one run of `scenario` owes: a completed task, a safe refusal or a pass-…, FR-15.2: the final mock data state holds only expected writes. Every scenario…, state_ok(), steps_for(), task_done(), Future (+36 more)

### Community 4 - "mock_api/app.py"
Cohesion: 0.06
Nodes (45): fastapi_security, Header, min_length, build(), build_admin(), list_mutations(), mutations(), reset() (+37 more)

### Community 5 - "Store"
Cohesion: 0.06
Nodes (17): Dashboard, Both agents run the demo task against their own mock; the store is shared., fix_text(), main(), print_act(), print_summary(), Terminal demo, the fallback for the pitch: `python -m dashboard.demo`. Scripted…, Run every act from a cold store; `step` is the agents' pause between calls. (+9 more)

### Community 6 - "test_mock_api.py"
Cohesion: 0.11
Nodes (36): api(), client(), deref(), errors(), get_spec(), lookup_args(), operation(), params() (+28 more)

### Community 7 - "test_dashboard.py"
Cohesion: 0.07
Nodes (29): bad_request(), create_app(), explorer_info(), mutation(), start(), FastAPI, get_explorer_info(), calls() (+21 more)

### Community 8 - "test_jev.py"
Cohesion: 0.08
Nodes (36): _amain(), bench(), _pass(), Namespace, One pass of the benchmark: scenarios x agents x n runs, optionally with a…, The main pass (FR-15.1, FR-15.6) and the error-only ablation (FR-15.7)., from_env(), JevChoice (+28 more)

### Community 9 - "diagnose.py"
Cohesion: 0.12
Nodes (35): sha256(), diff(), _diff_leaves(), diff_signature(), _entry(), flatten_request(), flatten_response(), _index() (+27 more)

### Community 10 - "test_store.py"
Cohesion: 0.13
Nodes (30): FixStatus, FR-5.7: the audit blob keeps no secret. Redact, then truncate (so a cut cannot…, sanitize(), clock(), db_path(), FakeClock, make_fix(), open_store() (+22 more)

### Community 11 - "pytest"
Cohesion: 0.08
Nodes (24): pytest, socket, api(), client(), fixture, test_real_http_switch_to_m1(), check(), parametrize (+16 more)

### Community 12 - "report"
Cohesion: 0.18
Nodes (14): _ablation_cell(), _failure_mode(), _outcome(), _pick(), _rate(), mean/p50/p95 with the sample size, the shape FR-15.5 asks for., mean/p50/p95 of `mttr_ms` or `heal_ms` over recovered heals of one tier., Share of runs that met the scenario's own expectation. (+6 more)

### Community 13 - "dashboard/app.py"
Cohesion: 0.23
Nodes (10): ExploreIn, MutationIn, BaseModel, Live demo dashboard: two in-process mock APIs, the healing and baseline agents,…, StartIn, Explorer module: reference metadata, predefined queries, and detailed schema &…, Wrap an Execute so every call, whatever the LLM decides to call, is traced.…, _recording_executor() (+2 more)

### Community 14 - "Tier"
Cohesion: 0.13
Nodes (28): collections, IntEnum, mttr_summary(), outcome_counts(), percentiles(), Any, Benchmark metrics (FR-15.4, FR-15.5) over audit events and benchmark run rows.…, FR-15.5, per scenario and agent: mean/p50/p95 of `llm_tokens` per run and of… (+20 more)

### Community 15 - "candidates.py"
Cohesion: 0.07
Nodes (63): copy, Option, _assign(), build(), _cast(), _clue_fills(), _clue_response_ops(), _dry_run() (+55 more)

### Community 16 - "test_bench.py"
Cohesion: 0.26
Nodes (12): bench, one(), parametrize, Benchmark runner and report tests (FR-15.1 to 15.8; AC-14, AC-15, AC-16, AC-17,…, test_baseline_re_sends_the_same_arguments_until_the_cap(), test_clean_run_completes_for_both_agents(), test_controls_pass_through_with_not_drift(), test_healing_recovers_every_healable_mutation() (+4 more)

### Community 17 - "test_scenarios.py"
Cohesion: 0.13
Nodes (24): assert_first_heal(), call_for(), calls_to(), check_m1(), check_m2(), check_m4(), check_m5(), check_m9() (+16 more)

### Community 18 - "test_openapi_loader.py"
Cohesion: 0.19
Nodes (14): fetch_spec(), AsyncClient, Inline every local `#/...` ref; keywords next to a $ref override the target's., resolve_refs(), walk(), test_fetch_spec_error_status_raises(), test_fetch_spec_returns_resolved_spec_and_raw_hash(), test_flatten_request_of_loaded_operation() (+6 more)

### Community 19 - "test_explorer.py"
Cohesion: 0.08
Nodes (10): client(), offline(), fixture, parametrize, Tests for the Explorer endpoints (/api/explorer/info and /api/explore)., M6-N refuses set_manager (step 3); the agent still opens the ticket (step 4)., The LLM path must never quietly return a canned scripted result., test_explore_controls_pass_business_errors_through() (+2 more)

### Community 20 - "openapi_source"
Cohesion: 0.23
Nodes (10): LoadedSpec, openapi_source(), load(), SpecSource, The default `SpecSource`: the API's OpenAPI 3 document at `path`., _keys(), Step 0 contracts between the two tracks (AGENTS.md): OperationSpec, SpecSource,…, test_injected_spec_source_serves_load_and_heal() (+2 more)

### Community 21 - "contract.py"
Cohesion: 0.12
Nodes (29): hashlib, jsonschema, check(), _passes(), Any, Output-schema validation (E5) and declarative postchecks (E6) on an OK outcome., _schema_violations(), classify() (+21 more)

### Community 22 - "models.py"
Cohesion: 0.12
Nodes (26): collections_abc, dataclasses, Enum, re, sqlite3, dumps(), Canonical JSON, hashing and path helpers for nested dict/list documents., Stable break identity (FR-4): same break, same fingerprint, across runs and… (+18 more)

### Community 23 - "run.py"
Cohesion: 0.14
Nodes (10): agents, argparse, Benchmark runner and report (plan.md phase 10, metrics per phase 12D / FR-15).…, datetime, mcp, subprocess, tempfile, _schema_listing() (+2 more)

### Community 24 - "fixture"
Cohesion: 0.12
Nodes (16): AsyncBaseTransport, client(), jev(), make_registry(), make(), fixture, Request, Response (+8 more)

### Community 25 - "common.py"
Cohesion: 0.09
Nodes (29): build(), executor(), Execute, Baseline agent: same tools, but each call is a bare v1 HTTP request. No…, make_tools(), tool(), Execute, Shared agent pieces: prompt, task, LLM, tool factory and the run loop. (+21 more)

### Community 26 - "Reason"
Cohesion: 0.15
Nodes (32): ErrorClass, Reason, jev_ok(), _event(), StrEnum, test_demo_runs_the_pitch_flow(), test_c2_missing_record_is_not_drift(), test_ac_05_one_audit_event_per_attempt() (+24 more)

### Community 27 - "run_explore"
Cohesion: 0.14
Nodes (14): check_data_correctness(), _heal_summaries(), _llm_bootstrap_error(), Verify mock API state against expected values. `touched` restricts the verdict…, Provider errors arrive as a page of JSON; the UI only needs the headline., Read-only view of every ToolDefinition after the run., Audit events as the explorer renders them, for a whole run., Response for a live-LLM run that could not even reach the provider. Returning… (+6 more)

### Community 28 - "Dashboard"
Cohesion: 0.13
Nodes (15): Side-by-Side Agent Comparison, Dashboard API Client, Dashboard Demo Simulator, Patch Log Renderer, Preset Runner, Benchmark Metrics, Candidate Builder, Dashboard (+7 more)

### Community 29 - "Heal Controller"
Cohesion: 0.13
Nodes (15): API Drift Explainer Landing Page, Machine-Readable Audit Log, Candidate Builder, Deterministic Tie-Breaker, Diagnoser, Break Fingerprint, Heal Controller, Jev Classifier (+7 more)

### Community 30 - "safe_refusal"
Cohesion: 0.20
Nodes (9): RunRow, FR-15.4 ZTAR: over `scenarios` only, the runs where the task completed and the…, FR-15.4 Safe-Refusal Rate: over the runs marked `must_refuse` (M8, and M6-N…, safe_refusal(), ztar(), AC-15: ZTAR 100% over the healable mutations with Jev absent, M6 separate,…, test_ac_15_ztar_safe_refusal_false_patch_and_m6_reported_separately(), test_safe_refusal_needs_the_expected_reason_and_no_invented_value() (+1 more)

### Community 31 - "Four-Person Ownership"
Cohesion: 0.14
Nodes (14): FixStore Contract, Four-Person Ownership, OperationSpec Contract, SpecSource Contract, Benchmark Metrics, MCP Proxy Flow, P1 MCP and Protocols Track, P2 Healing Core and Evidence Track (+6 more)

### Community 32 - "Research Notes"
Cohesion: 0.17
Nodes (12): Research Notes, AgentNoiseBench: Benchmarking Robustness of Tool-Using LLM Agents Under Noisy Condition, Automated Program Repair Based on REST API Specifications Using Large Language Models, CodeUpdateArena: Benchmarking Knowledge Editing on API Updates, Exploratory Analysis of the Structural Evolution of Public REST APIs, How Many Web APIs Evolve Following Semantic Versioning?, Reducing the Impact of Breaking Changes to Web Service Clients During Web API Evolution, Semantic Test Repair for Web Applications (+4 more)

### Community 33 - "_coerce_args"
Cohesion: 0.13
Nodes (17): _coerce_args(), _heal_info(), _json_or_text(), _lossless_coerce(), _parse_tool_result(), Any, Cast a value to the type the frozen v1 schema declares, only if lossless., Fit LLM-supplied arguments to the frozen agent-facing schema. A live model… (+9 more)

### Community 34 - "token_overhead"
Cohesion: 0.22
Nodes (6): FR-15.4 Token Overhead (healing) and wasted tokens (baseline): the mutated…, token_overhead(), AC-16: overhead = mutated total - CLEAN median, baseline waste beside it, the…, test_ac_16_token_overhead_against_clean_median_with_jev_in_its_own_column(), test_token_overhead_is_the_clean_median_difference_without_jev_tokens(), test_token_overhead_without_clean_runs_is_empty()

### Community 35 - "test_registry.py"
Cohesion: 0.21
Nodes (10): calls_to(), fix_for(), parametrize, test_ac_02_invalid_args_no_heal(), test_active_fix_request_ops_are_applied(), test_active_fix_response_ops_reshape_before_contract(), test_fr_3_4_value_rules_are_left_to_the_api(), test_healthy_call() (+2 more)

### Community 36 - "operations"
Cohesion: 0.25
Nodes (8): extract_tool_schemas(), Extract input and output schemas from a resolved OpenAPI spec for each…, OperationSpec, _json_schema(), operations(), _response_schema(), _agent_schema(), test_operations_picks_the_lowest_2xx_json_response()

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

### Community 43 - "send"
Cohesion: 0.50
Nodes (4): AsyncClient, Exception, Response, send()

### Community 44 - "Negative Cache"
Cohesion: 0.67
Nodes (3): Single-Attempt Healing, Negative Cache, Single-Flight Healing

### Community 45 - "FastAPI"
Cohesion: 0.67
Nodes (3): FastAPI, HTTPX, Pydantic

### Community 68 - "test_ac_34_cli_uses_real_custom_spec_and_closes_resources"
Cohesion: 0.15
Nodes (9): test_ac_34_cli_closes_resources_when_custom_spec_startup_fails(), close(), __init__(), tracked_client(), test_ac_34_cli_uses_real_custom_spec_and_closes_resources(), close(), __init__(), tracked_client() (+1 more)

### Community 69 - "override"
Cohesion: 0.19
Nodes (12): override(), Request, Response, Answer requests to `path` with `make(request)` (None passes through); returns…, E4: the API answers 200 with an error body to the v1 request, and works for the…, soft_error_for_old_shape(), test_ac_20_e4_on_idempotent_tool_is_replayed(), test_ac_20_e4_on_non_idempotent_tool_without_key_is_unsafe_replay() (+4 more)

### Community 70 - "mcp_server.py"
Cohesion: 0.10
Nodes (18): dotenv, logging, mcp_server_lowlevel, mcp_types, os, Server, _arguments(), create_server() (+10 more)

### Community 71 - "test_agents_live.py"
Cohesion: 0.31
Nodes (10): completed(), parametrize, Live agent runs: real LLM through NVIDIA NIM, consuming API credits. Skipped…, Run the demo task once; returns (RunResult, mock api, [(tool, class), ...])., New email, manager 456, one ticket, and the lookup itself succeeded., run_live(), test_ac_09_agent_stops_after_retry_false(), test_clean_run_completes() (+2 more)

### Community 73 - "test_ac_14_mttr_and_heal_ms_reported_per_tier_with_p95_targets"
Cohesion: 0.33
Nodes (7): agent_rows(), AC-14: tier-1 MTTR p95 < 4.0 s for M1 to M5 (tier 0 < 0.5 s), heal_ms alongside., AC-17: error loop, calls, tokens and final data are measured per scenario and…, The text from one `##` heading to the next (or the end of the report)., section(), test_ac_14_mttr_and_heal_ms_reported_per_tier_with_p95_targets(), test_ac_17_baseline_outcomes_measured_for_every_scenario_not_asserted()

### Community 75 - "fixture"
Cohesion: 0.33
Nodes (6): main(), main(), out(), fixture, report(), rows()

### Community 76 - "false_patch_rate"
Cohesion: 0.33
Nodes (6): false_patch_rate(), FR-15.4 False-Patch Rate: of the healed runs (a fix passed verification and…, AC-23: M1 to M9 re-run with spec_mode=off, per mutation healed or aborted with…, test_ac_23_error_only_ablation_report_without_a_heal_threshold(), test_false_patch_rate_counts_healed_runs_with_a_wrong_final_state(), test_false_patch_rate_of_nothing_is_empty()

### Community 77 - "httpx"
Cohesion: 0.13
Nodes (17): asyncio, contextlib, httpx, json, create_app(), pathlib, pytest_asyncio, random (+9 more)

### Community 80 - "make_event"
Cohesion: 0.67
Nodes (3): make_event(), test_audit_round_trip(), test_c11_enum_values_are_stored_and_the_old_reason_is_gone()

## Knowledge Gaps
- **63 isolated node(s):** `healer`, `$schema`, `builder`, `dockerfilePath`, `healthcheckPath` (+58 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 393 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ErrorClass` connect `Reason` to `test_heal.py`, `Healer`, `test_registry.py`, `Store`, `override`, `test_dashboard.py`, `test_store.py`, `pytest`, `dashboard/app.py`, `httpx`, `candidates.py`, `Tier`, `make_event`, `contract.py`, `models.py`, `common.py`, `run_explore`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `Reason` connect `Reason` to `test_heal.py`, `test_candidates.py`, `Healer`, `override`, `test_dashboard.py`, `false_patch_rate`, `test_fr_5_3_mttr_runs_from_the_first_failure_and_heal_ms_from_this_heal`, `candidates.py`, `Tier`, `test_scenarios.py`, `make_event`, `models.py`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `FixStore` connect `Store` to `Reason`, `Healer`, `openapi_source`, `models.py`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Are the 89 inferred relationships involving `Reason` (e.g. with `expectation()` and `build()`) actually correct?**
  _`Reason` has 89 INFERRED edges - model-reasoned connections that need verification._
- **Are the 56 inferred relationships involving `ErrorClass` (e.g. with `executor()` and `executor()`) actually correct?**
  _`ErrorClass` has 56 INFERRED edges - model-reasoned connections that need verification._
- **Are the 45 inferred relationships involving `HealOutcome` (e.g. with `_ablation_cell()` and `report()`) actually correct?**
  _`HealOutcome` has 45 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `Store` (e.g. with `_pass()` and `Dashboard`) actually correct?**
  _`Store` has 23 INFERRED edges - model-reasoned connections that need verification._