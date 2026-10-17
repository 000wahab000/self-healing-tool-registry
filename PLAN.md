# Plan and implementation status

`AGENTS.md` is the source of truth for requirements, invariants, and architecture. `README.md` is the human/judge entry point; `REPORT.md` is the canonical measured dashboard/benchmark report. This plan distinguishes implemented features from outstanding work and retains historical evidence as historical, not current verification.

## Implemented

- Healing core: `E1`–`E6` and `BUSINESS` classification, stable fingerprints, spec diagnosis and error-clue mode, deterministic candidate construction/tie-breaking, safety checks, DSL operations, bounded heal/replay, verification and audit. Tier 0 stored fixes, negative caching, single-flight, retirement, watcher precomputation, sibling propagation, rule mining, optional Jev choice/triage, and gated tier-2 repair are implemented.
- Mock and benchmark: REST and MCP mutation catalogs, oracle/final-state checks, scripted REST/MCP benchmark, healthy-call overhead, MCP fixtures, and report generation. `bench.run` generates root `REPORT.md`; dashboard `/api/report` serves it, and scorecard/live/lifecycle panels use the metrics view. LLM benchmark/token-overhead results remain unmeasured (see below).
- Gateway: MCP stdio and Streamable HTTP front door; unified gateway with per-upstream registries; OpenAPI 3, Swagger 2.0 and upstream MCP loaders/adapters; GraphQL support is experimental. Configured tools and connections use environment-variable references for secrets.
- Spec watcher and dashboard: background spec snapshots/precompute; dashboard and MCP share the unified web listener; connections page, MCP view/call activity, report, metrics panels, guided demo, and the separate local REST mock.
- Demonstrations and startup: scripted MCP demo agent, terminal demo, and `start.py` launcher with readiness, port-conflict and shutdown handling.
- Documentation consolidation: `doc-cleanup` is integrated with `feat/Patch_log_fix`. The only project documents are root `README.md`, `AGENTS.md`, `REPORT.md`, and `PLAN.md`. Client setup, requirements, safety rules, and historical measurements are consolidated; dependency manifests and raw proof data remain separate non-document artifacts.
- Recent dashboard/audit work: the canonical generated report is root `REPORT.md`; the dashboard report endpoint and scorecard read that report, while benchmark results remain under `bench/`. Incremental audit polling/scorecard/live/lifecycle panels are implemented (AC-76–AC-80). W1 deliberately returns success without persisting the email; its merged drift-schema change makes `update_email` drift from `email` to `email_address` so read-back detects the unsaved write. Separately, `Store.save_fix_and_audit` atomically saves a new fix and its audit event so the event references the assigned `fix_id`. W1 read-back and D1 no-key replay-safety tests pass in the validation below.

## Remaining and known limits

- **Operator restriction:** do not run chaos benchmarks or harnesses here. Preserve the existing results; their presence on `main` was reported by the user, not independently checked in this consolidation.
- [ ] **Release gate:** validation on 2026-10-17 ran `pytest -q -k 'not chaos'`: **965 passed, 1 failed, 15 skipped, 2 deselected, 1 xfailed**. `ruff check .` passed. The deselected tests exercise only the chaos report writer; no chaos benchmark or harness was run. Document inventory, local links/anchors, preserved requirement IDs, unchanged original scorecard, and dashboard scorecard parsing passed their checks. This is not a clean full-suite claim.
- [ ] **Existing AC-59 failure:** `test_ac_59_load_apis_and_legacy_config` expects an empty API list, but the checked-in connection config contains an API. It also failed on original HEAD `4600336`, whose baseline was 961 passed, 3 failed, 15 skipped, 1 xfailed. The other baseline failures (W1 read-back and D1 no-key replay safety) are resolved by the merged changes; the unrelated config/test mismatch remains untouched.
- [ ] **Real-LLM benchmark (T1-10):** `python -m bench.run --agent llm --n 10` has not been run; token overhead, tier-2 and T-MOVE figures and AC-16 evidence remain open. Regenerate `REPORT.md` from measured output when run.
- [ ] **Jev:** OpenRouter route has returned 401. Opt-in OpenCode free route (AC-48) has been used in a live M6-N repair, but dashboard M6-N correctness still assumes refusal. Recheck the route and dashboard outcome behavior before claiming Jev acceptance.
- [ ] **External connections (AC-102–AC-112):** source handoff records targeted evidence for AC-104 isolation/replay, AC-110 redaction and AC-111 invariant/cleanup, but full registry bypass, startup/watcher snapshots, and complete secret-reference wiring still require integration proof. Config/environment changes activate on restart; exact-origin egress allowlisting and separate dashboard auth remain operational constraints. Do not claim the entire lane is closed.
- [ ] **Client validation:** fresh Claude Desktop, Cursor and Windsurf setup/UI checks and opt-in live config check remain outstanding. README setup is a handoff, not evidence of manual client verification.
- [ ] **Deferred/limited capabilities:** `store_pg.py` is unsupported/incomplete; GraphQL M3 is a strict xfail and GraphQL is not benchmarked; gRPC is deferred. Streaming/long-running responses and global dashboard authentication are not supported. Do not infer production readiness.
- [ ] **Broader chaos validation:** the proposed multi-provider run has not been completed. The existing GitHub MCP offline/live experiment is reported in `REPORT.md` § GitHub MCP chaos: offline controls reported 0 false patches/0 crashes after the fix; the live sandbox run reported 0 real false patches and one successful heal. Counts are from one run per profile/mode, not rates; retain its recorded misses, scorer artifact, and environment-specific limitations as reported. The wider proposal targets GitHub REST/Stripe version diffs, httpbin transport faults, Petstore synthetic drifts, and read-only Countries GraphQL, plus agent-context and registry/store/concurrency faults. Before expanding it, pre-register expected outcomes, cite the pre-registration commit, use an independent oracle, and report every case including crashes/timeouts/misses. Enforce Stripe test-mode money safety/write-block proxy, sandbox GitHub scope, offline-first execution, and obtain user approval/credentials; see `AGENTS.md` § Development handoff notes.

## Verification history (historical)

The 2026-10-16 launcher smoke verified startup outside the checkout, HTTP MCP calls, REST M1 recovery visible in shared dashboard audit, port-conflict safety and SIGTERM cleanup. The 2026-10-17 unified-listener smoke verified dashboard routes, MCP initialize/list/call, transport metadata, shared audit and child shutdown. These are scoped smoke checks, not substitutes for the pending full-suite gate or real-client checks.

External-connection targeted test results and prior 835/845-pass suite runs are historical. Current acceptance IDs, including AC-112, live in `AGENTS.md`; new IDs continue after the highest used ID there, except reserved AC-83–AC-98 (Z0–Z15). Do not resurrect the old AC-82 highest-ID note or reserve AC-102–AC-112 again.

PR #51 (“Updated Metrics”) appears only in the historical delivery record; it is not a current to-do without fresh confirmation.

## Remaining external-connection sequence and evidence

The earlier handoff organized the work as A–F; retain only actionable gaps, not separate phases/ownership docs:

1. **A — Normalize and validate:** runtime-only legacy normalization; isolated auth profiles/env references; no config rewrite; fail-fast startup with safe errors and cleanup.
2. **B — Isolate clients and credentials:** separate API/spec auth; exact-origin scope; HTTPS for external credentials; no credential redirects; SSRF/DNS-rebinding controls and narrow operator allowlists; redact raw and derived credentials from errors, prompts, logs, probes and storage.
3. **C — Capability-gated discovery:** selected compatible operations only; safe path binding and configured headers; diagnostics instead of falsely successful tools; preserve `OperationSpec` and frozen schema contracts.
4. **D — Optional presets:** only versioned/pinned suggestions after compatibility evidence; custom setup works without presets.
5. **E — Connection lifecycle:** authenticated remote read/write/test routes, reference-preserving edits, restart activation and pending-restart/removal messaging; stdio stays file-only. This is not global dashboard authentication.
6. **F — Proof:** offline mixed API/MCP isolation, redaction, safe failure and cleanup tests first; optional discovery-only vendor smoke uses approved disposable accounts and no real secrets in tests.

The 2026-10-17 proposed AC-102–AC-111 evidence matrix is now superseded by product requirements in `AGENTS.md`; AC-112 additionally specifies persisted MCP call metadata without request/response storage. Preserve each criterion there and use the current tests as evidence, not the old proposal table.

## Historical delivery record

Core and gateway phases, tier-2 repair/Jev triage, dashboard connections/tour, MCP demo and fixtures, metrics panels, Swagger 2.0, watcher, unified launcher, and the design pass landed through the historical PR sequence #1–#53. Individual PR assignments and old team ownership are deliberately omitted; this is a single-maintainer project. Treat this list as project history, not proof that every acceptance criterion remains verified.
