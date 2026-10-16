# Self-Healing Gateway for MCP and REST Tools

**An agent calls one MCP server. When an upstream tool or API changes shape underneath it, the gateway repairs the call instead of letting the agent loop on the error.**

Agents call tools that were generated once from a spec or a `tools/list`, and upstreams keep changing. The gateway sits in front of upstream MCP servers and web APIs (OpenAPI 3, Swagger 2.0, GraphQL). On a break it diffs the current schema against the original, builds a fix from a few operations that cannot write an invented value, retries once, checks the answer and writes one audit row. When no safe fix exists it returns a structured refusal (`retry: false`) and the agent skips that one tool.

Built for **PS 01: Self-Healing Tool Registries Under Runtime API Schema Drift**.

```mermaid
flowchart LR
    A[Agent] -->|MCP: stdio or HTTP| F[Front door<br/>python -m healer.mcp_server]
    F --> R[Healing core<br/>detect, diagnose, fix, gate, verify, audit]
    R --> U1[Upstream MCP servers]
    R --> U2[OpenAPI / Swagger 2.0 / GraphQL APIs]
    R --> S[(SQLite: fixes + audit log)]
    W[Spec watcher] -.->|precompute fixes| R
    T2[Tier-2 repair LLM<br/>on by default, ops only] -.->|when tiers 0/1 refuse| R
```

Tier 0 replays a stored fix; tier 1 builds one with code; tier 2 (on by default when `NVIDIA_API_KEY` is set, same model as the agents: `LLM_MODEL`, default gpt-oss-20b on NVIDIA NIM; `--no-repair` turns it off) asks an LLM for DSL operations only, which pass the same safety gate and live verification. Details: [`FLOW.md`](FLOW.md).

## Measured

Scripted mode (fixed calls, no LLM), N = 3, from [`bench/report.md`](bench/report.md): the REST mock completed 21/21 healable runs (baseline 3/21), the MCP drift server completed 12/12 (baseline 0/12), and no healed run ended with wrong data (REST 0/24, MCP 0/12). **LLM-mode numbers (token cost, tier 2) are not measured yet.**

## Quick start

**Needs:** Python 3.11+. No API key is needed for the scripted demo, dashboard and benchmark.

1. Create a virtual environment and install everything:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   ```

   ```bash
   pip install -e ".[dev,agents,mcp]"
   ```

2. Copy the example settings. The dashboard loads `.env` at startup; put `NVIDIA_API_KEY` there for live agents. Jev is optional (`JEV_API_KEY` / `JEV_URL` / `JEV_MODEL`, or an `OPENROUTER_API_KEY` fallback).

   ```bash
   cp .env.example .env
   ```

3. Start the local stack, or use an individual service command:

   ```bash
   .venv/bin/python start.py
   ```

   Run that relative command from the repository root. From elsewhere, use the
   absolute paths to both `.venv/bin/python` and `start.py`; service paths are
   resolved from the repository root regardless of the caller's working
   directory. On Linux/macOS, this starts the standalone REST mock and the
   unified dashboard+MCP web process in dependency order. The REST mock is at
   http://127.0.0.1:8000; dashboard is at http://127.0.0.1:8080/ and its MCP
   endpoint is http://127.0.0.1:8080/mcp. Stop the stack with Ctrl+C. The
   default database is the shared root `healer.db`; the launcher loads `.env`.
   If either default port is occupied, startup fails without stopping the
   existing process; stop it manually or choose another port. For example:

   ```bash
   .venv/bin/python start.py --mock-port 8100 --port 8180 --db /tmp/opencode/healer.db
   ```

   The unified web process hosts the MCP gateway and watcher, including
   configured upstreams from `config/mcp_servers.json`. Dashboard demo and
   mutation controls use their own in-process mocks; they do not change the
   standalone REST mock or configured upstreams. The shared SQLite audit store
   does not merge dashboard traces with full external MCP client traces. No
   agent, benchmark, or drift scenario is launched automatically.

   To run a service separately:

| I want to… | Command |
|---|---|
| See the live dashboard | `python -m dashboard` → open http://127.0.0.1:8080 |
| Watch a terminal demo (no browser) | `python -m dashboard.demo` |
| Re-run the benchmark | `python -m bench.run --agent scripted --n 3` |
| Serve the gateway over MCP (needs `pip install -e ".[mcp]"`) | `python -m healer.mcp_server`, see [`docs/mcp-clients.md`](docs/mcp-clients.md) |
| Front your own upstreams (MCP servers and APIs) | `python -m healer.mcp_server --mcp-servers config/mcp_servers.json` (tier 2 is on when `NVIDIA_API_KEY` is set; `--no-repair` to turn it off) |
| Run the MCP demo agent (no key; `--llm` for a live agent) | `python -m demo.mcp_agent` |
| Run the mock API alone / the tests | `python -m mock_api` (http://127.0.0.1:8000/docs) / `pytest -q` |

**Dashboard** (`python -m dashboard`): `/` landing page with a guided tour, `/live` demo, patch log, metrics, MCP view, report, and `/connections` to add MCP servers and APIs by URL (tokens by environment-variable name only). Page-by-page flows: [`FLOW.md`](FLOW.md).

**Real LLM agents** use NVIDIA NIM (`https://integrate.api.nvidia.com/v1`), default [`openai/gpt-oss-20b`](https://build.nvidia.com/openai/gpt-oss-20b), temperature 0; `LLM_MODEL` overrides it. The dashboard loads `.env`; benchmark and pytest do not, so export the key in the shell:

```bash
export NVIDIA_API_KEY='<your NIM key>'
RUN_E2E=1 .venv/bin/python -m pytest tests/e2e -q
.venv/bin/python -m bench.run --agent llm --n 10
```

**Deploying the dashboard and MCP gateway:** `Dockerfile` and `Procfile` run
`python start.py`, which starts the REST mock separately and serves dashboard
`/` and MCP `/mcp` on the same listener. Use one worker, no reload, and a
persistent volume for SQLite (`DB_PATH`). Locally the listener defaults to
`127.0.0.1:8080`; a platform-provided `PORT` selects the web port and defaults
the bind host to `0.0.0.0` (override with `HOST`). Configure remote MCP using
environment settings, for example:

```dotenv
MCP_TOKEN_ENV=HEALER_MCP_TOKEN
MCP_ALLOWED_HOSTS=registry.example.com
MCP_ALLOWED_ORIGINS=https://registry.example.com
```

Set the actual `HEALER_MCP_TOKEN` value through the deployment secret manager;
the config contains only its variable name. MCP requires a non-empty token and
an exact allowed host; origin allowlists, when used, are exact too. These guard
MCP only. Dashboard routes such as `/api/start`, `/api/explore`, and
`/api/reset` mutate state and may spend configured model credentials, so expose
the dashboard only behind authenticated TLS ingress. The existing app has no
global dashboard authentication; this is not a production-ready security claim.

## Docs

| Document | What's in it |
|---|---|
| [`FLOW.md`](FLOW.md) | How it works end to end, with diagrams and a file map |
| [`writeup.md`](writeup.md) | Design, safety, evaluation, limits, references |
| [`pitch.md`](pitch.md) | Spoken pitch and Q&A |
| [`docs/mcp-clients.md`](docs/mcp-clients.md) | Connect Claude Desktop, Cursor or Windsurf; add an upstream server |
| [`bench/report.md`](bench/report.md) | Full benchmark tables (the only source of numbers) |
| [`product.md`](product.md) | Requirements and acceptance criteria |
| [`plan.md`](plan.md), [`AGENTS.md`](AGENTS.md), [`agent.md`](agent.md) | Status and next steps, contracts and working rules, coding invariants |
