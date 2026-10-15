# Team kickoff prompts

Paste the prompt for your person into your agent as the first message of a new session. Each prompt starts that person's first item; for later items, change the item ID in the last paragraph. Ownership and rules: `AGENTS.md` ("Four-person ownership"). Work items: `plan.md` ("Phase 13+: four parallel tracks").

Common setup for everyone (once, in your own clone of the repo):

```bash
git pull origin main
```

```bash
python -m venv .venv
```

```bash
pip install -e ".[dev,agents]"
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

## P1: teammate (GPT with oh-my-opencode-slim)

```text
I am P1 on this project. Read AGENTS.md first, then agent.md, then the "Phase 13+: four parallel tracks" section of plan.md, then product.md sections 6, 8, 11 and 15.

My track is P1: the MCP server and protocols. I own only the files listed for P1 in AGENTS.md. Do not edit any other file. If you need a change in a file someone else owns (especially heal.py, models.py or store.py, which P2 owns), stop and write down the exact request for me to send to its owner.

Start with item P1-1, the MCP server over stdio:
1. Read src/healer/registry.py (Registry.tools(), Registry.call(), load()) and src/healer/models.py (HealError, SpecSource). The MCP server wraps these and adds no healing logic.
2. Write the FR and AC for the MCP server into product.md as a new feature section. Use AC-30 onward only. Show me the text before writing any code.
3. Add an optional dependency group "mcp" in pyproject.toml with the official mcp SDK pinned to one major version. Check the current version on PyPI first; do not guess it.
4. Build src/healer/mcp_server.py on the SDK's low-level server so that tools/list returns Registry.tools() exactly: agent_schema as inputSchema, never derived from Python signatures. tools/call goes through Registry.call(). An error dict from the registry becomes a tool result with isError true and the dict as structured content. Never send tools/list_changed, because agent_schema is frozen. Log to stderr only, never stdout. Add a CLI entry point healer-mcp with --base-url, --spec-path, --tools and --db.
5. Write tests in tests/mcp/ using the SDK's client against the in-process mock API (see tests/integration/conftest.py for how the mock is wired; copy what you need into tests/mcp/conftest.py). The tests must show: the tools are listed; get_user works; after api.set_mutation("M1") the same session still gets the right result with no list_changed; M8 returns isError with the refusal reason. Name each AC test test_ac_3X_*.
6. Run python -m pytest -q and ruff check . until both are clean.
7. Create branch p1/p1-1-mcp-stdio, commit, push, and open a PR to main with P2 as reviewer.

Rules that are never broken: the invariants in agent.md section 2. Do not claim any speed or reliability number in code comments, docs or the PR that is not measured in bench/report.md.
```

## P2: Wahab (Claude Code)

```text
I am P2 on this project. Read AGENTS.md and the "Phase 13+: four parallel tracks" section of plan.md.

Start item P2-0, MVP evidence. First run the five opt-in live E2E tests in tests/e2e/test_agents_live.py against gpt-oss-20b on NVIDIA NIM, and tell me before any paid call how many calls and roughly how many tokens the run will use. If the live tests pass, plan the LLM-mode benchmark at N = 10 per agent and scenario, clean runs included, and show me the expected call count before starting it. Report AC-14 and AC-16 as measured, misses included, and record the model and provider in bench/report.md. Branch p2/p2-0-llm-benchmark, one PR.
```

## P3: OpenCode free tier, no plugins

### Pick a model

The repo is private. Use only a free model that OpenCode Zen marks as zero-retention and not used for training. As of 2026-10-15 the Zen docs list these:

- `deepseek-v4.1-flash-free` (try this first)
- `step-5-preview-free`
- `longcat-2.5-preview-free`
- `space-bunny-free`

Do not use `big-pickle`, `exo-free`, `mimo-v2.5-free`, `mimo-v2.6-flash-free` or `muse-spark-1.3-contributor-free`, which may use prompts for training. Do not use the Nemotron free models either: they log usage and are for trial use only. `jev-1.13-free` is a decision model, not a coding model.

Free models are time-limited and change often. Check the current list at https://opencode.ai/docs/zen/ and pick the model in OpenCode with `/models`. If a model fails at tool calls or edits the wrong files, switch to the next one on the list.

### Prompt (one item per session; start a fresh session for each item)

```text
I am P3 on this project. Read AGENTS.md first, then only the "Track P3" table in plan.md.

I own only these files: src/healer/swagger2.py, bench/overhead.py, mock_api/fixtures/, tests/p3/, and checkbox and progress-log edits in plan.md phases 0 to 12. Do not edit, rename, reformat or delete any other file. If something else needs to change, stop and tell me what and why.

Do item P3-1 only: plan hygiene.
1. Read the "Progress log" table at the end of plan.md.
2. For each unticked "- [ ]" box in phases 0 to 12, decide whether the progress log or an existing test shows it is done. Search tests/ for the test it names before deciding.
3. Change "- [ ]" to "- [x]" only for boxes that are clearly done. Leave these unticked: the AC-18 manual check, anything about live or LLM runs, and anything you are unsure about.
4. Change nothing else in plan.md: no rewording, no reformatting.
5. Show me a list of every box you ticked and the evidence for each one (log row or test name). Then stop. Do not commit until I say so.

When I say commit: create branch p3/p3-1-plan-hygiene, commit only plan.md, push, and open a PR to main.
```

For P3-2 and P3-3, use the same prompt with the "Do item ..." part replaced by that item's row from the Track P3 table in `plan.md`, and add these lines:

```text
Write the FR and AC text for product.md first (P3-2 uses AC-28; P3-3 uses AC-50 onward) and show it to me before writing code.
Write the test first, run it and show me that it fails, then write the code until it passes.
Run python -m pytest -q and ruff check . and show me the last lines of both.
```

## P4: Antigravity with Gemini Flash (Gemini Pro via Jio)

Antigravity quota on a Jio-bundled Pro account is shared across the plan and resets on a schedule. Keep one item per conversation and use planning mode, so the agent shows its plan before spending quota on edits.

```text
I am P4 on this project. Read AGENTS.md first, then the "Track P4" table in plan.md, then the README section on running the dashboard.

I own only the files listed for P4 in AGENTS.md. Do not edit any other file. If you need a change elsewhere, stop and tell me.

Do item P4-1, the AC-18 browser check:
1. Install with pip install -e ".[dev,agents]" and start the dashboard with python -m dashboard. Do not put any API key anywhere; the scripted mode needs none.
2. Open http://127.0.0.1:8080 in the browser. Start a scripted run, then trigger M5 with one click.
3. Check three things and record evidence for each: (a) one click triggers the mutation; (b) both the healing and the baseline panes update live; (c) the heal event appears in the patch log within 1 second. For (c), note the time of the click and compare it with the heal event's timestamp from the dashboard's API. Do not judge it by eye.
4. Repeat for M3 or M4, and for M8 (it must show a clean refusal, not a heal).
5. Restart everything and run the full demo twice from a cold start: once normally, once with no Jev settings at all.
6. Take screenshots of each step. Write the results as a table: step, expected, observed, time in ms, pass or fail.
7. Do not change any code in this item. If something fails, describe it and stop.

When done: create branch p4/p4-1-ac18-check, add a row to the plan.md progress log with the results, commit, push, and open a PR to main with the table and screenshots in the description.
```

For later P4 items, use the same first two paragraphs and replace the "Do item" part with that item's row from the Track P4 table in `plan.md`. For P4-2, add: "Write the FR and AC (AC-55 onward) and show them to me before writing code. Inject the clock and the sleep function so tests never wait in real time."
