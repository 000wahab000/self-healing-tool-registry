# Team kickoff prompts

Two teams, four machines. Paste a machine's prompt into its agent as the first message of a new session. Each prompt starts that machine's first item. For each later item, start a new session, paste the same prompt and change the item ID in the "Start with" line. Ownership and contracts: `AGENTS.md` ("Two teams, four machines"). Work items: `plan.md` ("Phase 13+: MCP gateway, two teams on four machines").

| Machine | Person | First item | Then |
|---|---|---|---|
| Team 1, PS1 | Wahab | T1-0 land the old P2 branch | T1-1 to T1-5 |
| Team 1, PS2 | Wahab | T1-6 mock drift MCP server | T1-7 to T1-10 |
| Team 2, PS1 | Teammate | T2-1 upstream MCP client adapter | T2-2 to T2-6 |
| Team 2, PS2 | Teammate | T2-7 spec watcher | T2-8 to T2-11 |

Step 0 in `plan.md` comes first on every machine: merge the open branches into `main`. The `mcp` optional group exists only after P1's branch `p1/p1-1-mcp-stdio` merges.

Common setup on every machine (once, in its own clone of the repo):

```bash
git pull origin main
```

```bash
python -m venv .venv
```

```bash
pip install -e ".[dev,agents,mcp]"
```

Checks before every PR (no CI exists, so these are the gate):

```bash
python -m pytest -q
```

```bash
ruff check .
```

Never paste `.env` contents or API keys into any agent.

---

## Team 1, PS1: healing core (Wahab)

```text
I am Team 1, machine PS1 (T1-PS1) on this project. Read AGENTS.md first, then agent.md, then the "Phase 13+: MCP gateway, two teams on four machines" section of plan.md, then product.md.

Product direction: a self-healing gateway. Agents call our MCP server; the registry forwards each call to an upstream MCP server or a REST API. When an upstream tool's schema drifts, the healer diagnoses it from the old and new tools/list and rewrites the call with deterministic ops. The agent's schema never changes.

My track is the healing core. I own only the files listed for T1-PS1 in AGENTS.md. Do not edit any other file. If I need a change in another machine's file, stop and write the exact request for me to send to its owner.

Start with: T1-0 (land the old P2 branch).
- git fetch origin. Read the single commit on origin/p2/p2-0-llm-benchmark (git show --stat).
- Map every file and hunk to its plan item: S1, S8/M10, X3, S2, X2-E3, X4 precompute.
- For each item, cut a branch t1-ps1/t1-0-<item-slug> from origin/main with only that item's code, tests and plan row. Put the registry.py change and the dashboard/ change on branches of their own, and say in each PR body which machine must approve it (T2-PS1 or T2-PS2).
- Keep Healer.precompute guarded: nothing calls it yet, and it works when no watcher exists. Add a test for that.
- Check every claim in the commit message against a test. List any claim that has no test; do not invent the missing work.
- Do not delete or force-push the original branch.

For later items (T1-1 to T1-5): write the FR and AC in product.md first (my range is AC-40 to AC-49), then the code, then a test_ac_XX_* test for each AC. MCP outcomes come from T2-PS1's adapter (contract 7). Until T1-PS2's fixtures land, test with hand-written tools/list dicts.

Rules for every item: one item per PR on a branch named t1-ps1/<item>-<slug>, cut from main. Rebase on main, then pytest -q and ruff check . must be clean. Keep the agent.md invariants: no invented values, no executed model code, no loops, one audit row per heal, frozen agent_schema, no secrets stored, False-Patch Rate 0. When running tests from a git worktree, set PYTHONPATH to the worktree's src and root first. Never read or print .env. Tick my box in plan.md and add a progress-log row in the same PR. Push and open the PR; do not merge.

Finish with a short report: PR links, ACs covered, tests added, and anything that needs another machine.
```

---

## Team 1, PS2: mock drift server, benchmark and evidence (Wahab)

```text
I am Team 1, machine PS2 (T1-PS2) on this project. Read AGENTS.md first, then agent.md, then the "Phase 13+: MCP gateway, two teams on four machines" section of plan.md, then product.md.

Product direction: a self-healing gateway. Agents call our MCP server; the registry forwards each call to an upstream MCP server or a REST API. When an upstream tool's schema drifts, the healer repairs the call. My track builds the drifting upstream server that everyone tests against, then measures the results.

I own only the files listed for T1-PS2 in AGENTS.md. Do not edit any other file. If I need a change in another machine's file, stop and write the exact request for me to send to its owner.

Start with: T1-6 (mock drift MCP server). Three machines wait on it, so keep it small and land it first.
- Write the FR and AC in product.md first (my range is AC-50 to AC-54).
- mock_api/mcp_drift_server.py on the official mcp SDK (the version pinned in pyproject.toml), over stdio and Streamable HTTP. Its tools mirror the REST mock in mock_api/app.py.
- Mutations, each applied and reset by name: rename tool, rename argument, retype argument, add required argument, change enum, and an M8-style unsafe change that must be refused. Reuse the REST mock's mutation names where one matches.
- The control interface is contract 8 in AGENTS.md. Document it at the top of the file: how to apply, list and reset a mutation.
- The server can start with a different tool set (a flag or argument), so tests can run two upstream servers.
- Tests: each mutation changes tools/list and makes the old call fail; reset restores the original exactly.

Next items in order: T1-7 (recorded tools/list fixtures in mock_api/fixtures/mcp/), T1-8 (healthy-call overhead over MCP in bench/overhead.py), T1-9 (MCP scenarios in bench/run.py and bench/report.md), T1-10 (live gpt-oss-20b runs, N = 10, misses included). Report only measured numbers.

Rules for every item: one item per PR on a branch named t1-ps2/<item>-<slug>, cut from main. Write the FR and AC first and a test_ac_XX_* test for each AC. Rebase on main, then pytest -q and ruff check . must be clean. Keep the agent.md invariants. When running tests from a git worktree, set PYTHONPATH to the worktree's src and root first. Never read or print .env; live runs read the key from the environment. Tick my box in plan.md and add a progress-log row in the same PR. Push and open the PR; do not merge.

Finish with a short report: PR links, ACs covered, tests added, and anything that needs another machine.
```

---

## Team 2, PS1: MCP client, loader and front door (teammate)

```text
I am Team 2, machine PS1 (T2-PS1) on this project. Read AGENTS.md first, then agent.md, then the "Phase 13+: MCP gateway, two teams on four machines" section of plan.md, then product.md sections 6, 8, 11 and 15, then tests/mcp/client-handoff.md.

Product direction: a self-healing gateway. Agents call our MCP server (src/healer/mcp_server.py); the registry forwards each call to an upstream MCP server or a REST API. When an upstream tool's schema drifts, the healer (T1-PS1) repairs the call. My track is the plumbing: connecting to upstream MCP servers, loading their tools, routing calls and serving the merged tool list.

I own only the files listed for T2-PS1 in AGENTS.md. Do not edit any other file. If I need a change in another machine's file (especially models.py, heal.py or store.py, which T1-PS1 owns), stop and write the exact request for me to send to its owner.

Start with: T2-1 (upstream MCP client adapter).
- Write the FR and AC in product.md first (my range is AC-30 to AC-39).
- src/healer/adapters/mcp_upstream.py: one client session per upstream server, over stdio or Streamable HTTP, using the official mcp SDK.
- A tool call returns the same Outcome model the REST adapter returns. Keep the JSON-RPC error code and message, the isError flag and its content, so T1-PS1 can classify them. This mapping is contract 7 in AGENTS.md; send its exact shape to T1-PS1 before building on it.
- Tests: success, an isError result, a JSON-RPC invalid-params error, an unknown-tool error and a transport failure each give the right Outcome. If T1-PS2's mock drift server is not merged yet, test against a minimal in-process server in tests/t2ps1/.

Next items in order: T2-2 (mcp_upstream_source: tools/list to OperationSpec, keyed <server>__<tool>), T2-3 (config/mcp_servers.json with env var names only, no secrets), T2-4 (registry dispatch by protocol; tools() stays frozen), T2-5 (front door over stdio and HTTP serving REST and MCP tools, never emitting tools/list_changed). T2-6 (GraphQL, gRPC, Postgres) is deferred.

Rules for every item: one item per PR on a branch named t2-ps1/<item>-<slug>, cut from main. Write the FR and AC first and a test_ac_XX_* test for each AC. Rebase on main, then pytest -q and ruff check . must be clean. The MCP server adds no healing logic of its own (contract 4). Keep the agent.md invariants. Logs go to stderr only. Never read or print .env. Tick my box in plan.md and add a progress-log row in the same PR. Push and open the PR; do not merge.

Finish with a short report: PR links, ACs covered, tests added, and anything that needs another machine.
```

---

## Team 2, PS2: watcher, demo, dashboard and docs (teammate)

```text
I am Team 2, machine PS2 (T2-PS2) on this project. Read AGENTS.md first, then agent.md, then the "Phase 13+: MCP gateway, two teams on four machines" section of plan.md, then product.md.

Product direction: a self-healing gateway. Agents call our MCP server; the registry forwards each call to an upstream MCP server or a REST API. When an upstream tool's schema drifts, the healer repairs the call. My track makes it visible: a watcher that spots drift early, a demo agent, the dashboard and the docs.

I own only the files listed for T2-PS2 in AGENTS.md. Do not edit any other file. If I need a change in another machine's file, stop and write the exact request for me to send to its owner.

Start with: T2-7 (spec watcher).
- Write the FR and AC in product.md first (my range is AC-55 to AC-59).
- src/healer/spec_watcher.py: poll a list of SpecSource callables on an interval (OpenAPI now, upstream MCP once T2-PS1 lands it). Hash each LoadedSpec and save a snapshot when it changes.
- Call Healer.precompute(old, new) only when the healer has it (contract 5). Guard the call so the watcher works without it.
- Inject the clock and sleep so tests run instantly. Use bounded backoff when a source fails. Never block a tool call.
- Tests: a change is snapshotted within one interval; an unchanged spec causes no extra work; a failing source backs off and recovers.

Next items in order: T2-8 (demo/mcp_agent.py: an agent that connects only to our front door, uses tools from 2+ mock upstream servers, and finishes a task after a mid-task rename), T2-9 (dashboard MCP view and mutation buttons through contract 8), T2-10 (docs/mcp-clients.md from tests/mcp/client-handoff.md), T2-11 (README, pitch and writeup around the gateway, every number from bench/report.md). T2-8 and T2-9 wait for T2-5 and T1-6.

Rules for every item: one item per PR on a branch named t2-ps2/<item>-<slug>, cut from main. Write the FR and AC first and a test_ac_XX_* test for each AC. Rebase on main, then pytest -q and ruff check . must be clean. Keep the agent.md invariants. Docs and pitch use only numbers measured in bench/report.md; never claim "the agent never sees an error". Check dashboard changes in the browser and attach screenshots to the PR. Never read or print .env. Tick my box in plan.md and add a progress-log row in the same PR. Push and open the PR; do not merge.

Finish with a short report: PR links, ACs covered, tests added, and anything that needs another machine.
```
