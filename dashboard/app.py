"""Live demo dashboard: two in-process mock APIs, the healing and baseline agents, one page.

Every endpoint is `async def` on purpose: the SQLite store lives on the event-loop thread.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import uuid
from collections.abc import Awaitable, Sequence
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from agents import baseline_agent, common, healing_agent, scripted
from bench.run import CONTROL_STEPS, CONTROL_TASK
from dashboard.connections import router as connections_router
from dashboard.drift_editor import custom_from_schema
from dashboard.explorer import (
    _recording_executor,
    check_data_correctness,
    get_explorer_info,
    run_explore,
)
from dashboard.metrics_view import fix_lifecycle, live_safety, mcp_tool_usage, scorecard
from healer import metrics
from healer.gateway import Gateway, load_apis, load_config
from healer.jev import from_env
from healer.models import AuditEvent, ErrorClass, HealOutcome
from healer.registry import Registry
from healer.repair import from_env as repair_from_env
from healer.store import Store
from mock_api.app import ALIASES, CUSTOM, MUTATIONS, V1_REQUEST
from mock_api.app import create_app as create_mock

LEAD_IN_STEPS = 3  # scripted agents wait this many steps before their first call
HERE = Path(__file__).parent
ROOT = HERE.parent
# A tool-calling turn re-sends the whole conversation to the model and adds a
# completion. Live LLM mode measures the real token figures (AC-16); a scripted
# run makes no model call, so the Metrics tab only *estimates* saved tokens from
# the turns the registry avoided and this clearly-labelled per-turn assumption.
# The estimate is never mixed into a measured figure: `tokens_measured` says which.
EST_TOKENS_PER_TURN = 600
IDLE = {
    "status": "idle",
    "final_text": "",
    "tool_calls": 0,
    "llm_tokens": 0,
    "hit_limit": False,
    "error": None,
}


class StartIn(BaseModel):
    agent: Literal["scripted", "llm"] = "scripted"
    step_delay: float = Field(1.0, ge=0, le=30)


class MutationIn(BaseModel):
    id: str | None
    custom: dict | None = None  # CUSTOM only: a ready drift spec, or just {"tool": ...}
    fake_schema: dict | None = None  # CUSTOM only: edited input schema, diffed into a spec
    header: str | None = None  # CUSTOM only: extra required header


class ExploreIn(BaseModel):
    query: str = ""
    mutation: str | None = None
    agent: Literal["scripted", "llm"] = "scripted"
    custom: dict | None = None  # the drift spec when mutation is CUSTOM


class Dashboard:
    """Both agents run the demo task against their own mock; the store is shared."""

    def __init__(
        self,
        db_path: str | None = None,
        gateway: Registry | Gateway | None = None,
        mcp_port: int = 8001,
        upstream_config_path: str | Path | None = None,
    ) -> None:
        env = os.environ
        self.cfg = {
            "OAUTH_BEARER": env.get("OAUTH_BEARER") or "Bearer test-token",
            "TENANT_ID": env.get("TENANT_ID") or "t-1",
        }
        self.tools = json.loads(
            (ROOT / "config" / "tools.json").read_text(encoding="utf-8")
        )
        db = (
            db_path
            or env.get("DB_PATH")
            or str(Path(tempfile.mkdtemp()) / "dashboard.db")
        )
        self.store = Store(db)
        self.jev = from_env()
        token = self.cfg["OAUTH_BEARER"].removeprefix("Bearer ")
        self.mocks = {"healing": create_mock(token), "baseline": create_mock(token)}
        self.lock = asyncio.Lock()  # start / mutate / reset never interleave
        self.tasks: dict[str, asyncio.Task] = {}
        self.clients: list[httpx.AsyncClient] = []
        self.epoch = 0
        self.mutation: str | None = None
        self.custom: dict | None = None  # the spec behind a CUSTOM mutation
        self.run_scenario: str | None = None
        # The live view starts empty on a fresh server: calls kept in the db from an earlier
        # process have no recorded traces, so they could not open as call cards.
        events = self.store.call_events()
        self.base_event = events[-1]["event_id"] if events else 0
        self.base_heal = 0
        self._audit: list[AuditEvent] = []
        self._audit_last_id = 0
        self._heal_summaries: list[dict] = []
        self.base_call = self.base_event  # Metrics counts calls since the last Reset or restart
        # The measured LLM token pair (baseline, healing) stays for the session, so a
        # later scripted run does not erase a figure an earlier LLM run measured.
        self._llm_tokens: tuple[int, int] | None = None
        self.drifts: list[tuple[int, str | None]] = []  # (ms, mutation) as it went live
        
        self.runs = {a: dict(IDLE) for a in self.mocks}
        self.traces: dict[str, list[dict]] = {a: [] for a in self.mocks}
        self._mcp_info: dict | None = None
        self._v1_schemas: dict | None = None
        self.gateway = gateway
        self.mcp_port = mcp_port
        self.upstream_config_path = upstream_config_path

    def _not_busy(self) -> None:
        """A scenario (and a live-LLM one can take minutes) holds the lock for its whole run.
        Say so at once instead of letting clicks queue up and hang the browser."""
        if self.lock.locked():
            raise ValueError(
                "A scenario is still running on both agents. Wait for it to finish, then try again."
            )

    async def start(self, kind: str, step_delay: float) -> None:
        if kind == "llm" and not os.environ.get("NVIDIA_API_KEY"):
            raise ValueError("llm agents need NVIDIA_API_KEY")
        self._not_busy()
        async with self.lock:
            await self._stop()
            mutation = self.mutation  # a drift picked before Start applies to this run
            custom = self.custom
            scenario = mutation if mutation in CONTROL_STEPS else None
            self._clear()
            http = {
                a: httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=m), base_url="http://mock"
                )
                for a, m in self.mocks.items()
            }
            self.clients = list(http.values())
            healing = Registry(  # repair: the tier-2 LLM agent, when NVIDIA_API_KEY is set
                http["healing"], self.tools, self.cfg, self.store, self.jev, repair=repair_from_env()
            )
            baseline = Registry(http["baseline"], self.tools, self.cfg)  # v1 specs only
            await healing.load()
            await baseline.load()
            # Registries freeze the clean v1 spec first, then the drift goes live.
            if mutation is not None:
                for mock in self.mocks.values():
                    mock.set_mutation(mutation, custom)
                self.mutation = mutation
                self.custom = custom
                self._drift(mutation)
            run_id = uuid.uuid4().hex[:8]
            if kind == "scripted":
                heal_exec, self.traces["healing"] = _recording_executor(
                    healing_agent.executor(healing), self.store, {}, self.mocks["healing"]
                )
                base_exec, self.traces["baseline"] = _recording_executor(
                    baseline_agent.executor(http["baseline"], baseline),
                    self.store,
                    {},
                    self.mocks["baseline"],
                )
                jobs = {
                    "healing": lambda: self._scripted(
                        heal_exec,
                        "healing",
                        False,
                        step_delay,
                        run_id,
                        CONTROL_STEPS.get(scenario, scripted.STEPS),
                    ),
                    "baseline": lambda: self._scripted(
                        base_exec,
                        "baseline",
                        True,
                        step_delay,
                        run_id,
                        CONTROL_STEPS.get(scenario, scripted.STEPS),
                    ),
                }
            else:
                llm = common.make_llm()
                task = CONTROL_TASK.get(scenario, common.TASK)
                heal_exec, self.traces["healing"] = _recording_executor(
                    healing_agent.executor(healing), self.store, {}, self.mocks["healing"]
                )
                base_exec, self.traces["baseline"] = _recording_executor(
                    baseline_agent.executor(http["baseline"], baseline),
                    self.store,
                    {},
                    self.mocks["baseline"],
                )
                heal_graph = create_react_agent(
                    llm,
                    common.make_tools(healing, heal_exec, "healing", self.store, run_id),
                    prompt=common.SYSTEM_PROMPT,
                )
                base_graph = create_react_agent(
                    llm,
                    common.make_tools(baseline, base_exec, "baseline", self.store, run_id),
                    prompt=common.SYSTEM_PROMPT,
                )
                jobs = {
                    "healing": lambda: common.run(heal_graph, task),
                    "baseline": lambda: common.run(base_graph, task),
                }
            self.runs = {a: {**IDLE, "status": "running"} for a in jobs}
            self.run_scenario = scenario  # the page's "cannot affect this run" note
            self.tasks = {
                a: asyncio.create_task(self._finish(a, job, mutation))
                for a, job in jobs.items()
            }

    async def _scripted(
        self,
        execute,
        agent: str,
        retry_same_args: bool,
        step_delay: float,
        run_id: str,
        steps: Sequence[tuple[str, dict]] = scripted.STEPS,
    ):
        # The first call (get_user) would otherwise fire before any mutation can be triggered.
        await asyncio.sleep(LEAD_IN_STEPS * step_delay)
        return await scripted.run(
            execute,
            agent,
            retry_same_args=retry_same_args,
            store=self.store,
            run_id=run_id,
            step_delay=step_delay,
            steps=steps,
        )

    async def _finish(self, agent: str, job, run_mutation: str | None) -> None:
        try:
            run = asdict(await job())
            # Rate what the run saw, not whatever mutation is live now: a control
            # picked after Start cannot affect this task (the page says so too).
            if run_mutation is None and self.mutation in CONTROL_STEPS:
                mut = None
            else:
                mut = self.mutation
            run["data_correct"] = check_data_correctness(
                self.mocks[agent].state(), mut
            )[0]
            self.runs[agent] = {"status": "done", **run}
            self._record_llm_savings()
        # A crashed run is shown on the page as the run's error, not swallowed.
        except Exception as exc:  # noqa: BLE001
            self.runs[agent] = {
                **IDLE,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _record_llm_savings(self) -> None:
        """Once both agents finish an LLM run, remember the measured token pair."""
        if any(r["status"] != "done" for r in self.runs.values()):
            return
        base = int(self.runs["baseline"].get("llm_tokens") or 0)
        heal = int(self.runs["healing"].get("llm_tokens") or 0)
        if base or heal:
            self._llm_tokens = (base, heal)

    async def mutate(self, mid: str | None, custom: dict | None = None) -> None:
        if mid is not None and mid not in MUTATIONS and mid not in ALIASES and mid != CUSTOM:
            raise ValueError(f"unknown mutation {mid!r}")
        self._not_busy()
        async with self.lock:
            for mock in self.mocks.values():
                mock.set_mutation(mid, custom)
            self.mutation = mid
            self.custom = self.mocks["healing"].custom
            self._drift(mid)

    async def drift_schemas(self) -> dict:
        """Each tool's clean v1 input schema, exactly what the agent is given."""
        if self._v1_schemas is None:
            token = self.cfg["OAUTH_BEARER"].removeprefix("Bearer ")
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=create_mock(token)), base_url="http://mock"
            ) as client:
                registry = Registry(client, self.tools, self.cfg, self.store)
                await registry.load()
                self._v1_schemas = {
                    t["name"]: t["parameters"]
                    for t in registry.tools()
                    if t["name"] in V1_REQUEST
                }
        return self._v1_schemas

    async def reset(self) -> None:
        self._not_busy()
        async with self.lock:
            await self._stop()
            self._clear()
            # Only Reset empties the patch log; Start, scenarios and drifts keep adding to it.
            self._refresh_audit()
            self.base_heal += len(self._audit)
            self._audit.clear()
            self._heal_summaries.clear()
            calls = self.store.call_events()
            self.base_call = calls[-1]["event_id"] if calls else 0
            self._llm_tokens = None

    async def explore(
        self,
        query: str,
        mutation: str | None,
        agent: str = "scripted",
        custom: dict | None = None,
    ) -> dict:
        known = (*MUTATIONS, *ALIASES, CUSTOM)
        if mutation is not None and mutation not in known:
            raise ValueError(f"unknown mutation {mutation!r}")
        self._not_busy()
        async with self.lock:
            await self._stop()
            self._clear()
            self._drift(mutation)
            result = await run_explore(
                self.mocks["healing"],
                self.mocks["baseline"],
                self.store,
                self.tools,
                self.cfg,
                self.jev,
                mutation,
                query,
                agent,
                custom,
            )
            # Like a Live run: keep the measured pair for the Metrics tab (calls
            # already reached the call log), never an estimate.
            base = int(result.get("baseline", {}).get("llm_tokens") or 0)
            heal = int(result.get("healing", {}).get("llm_tokens") or 0)
            if agent == "llm" and (base or heal):
                self._llm_tokens = (base, heal)
            return result

    async def mcp_info(self) -> dict:
        """What the MCP front door exposes, read from the same `Registry.tools()`."""
        if self._mcp_info is None:
            if self.gateway is not None:
                tools = self.gateway.tools()
            else:
                # A fresh mock, so the frozen schemas come from the clean v1 spec,
                # never from a mutation the live demo happens to have applied.
                token = self.cfg["OAUTH_BEARER"].removeprefix("Bearer ")
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=create_mock(token)),
                    base_url="http://mock",
                ) as client:
                    registry = Registry(client, self.tools, self.cfg, self.store)
                    await registry.load()
                    tools = registry.tools()
            upstream = Path(
                self.upstream_config_path or ROOT / "config" / "mcp_servers.json"
            )
            self._mcp_info = {
                "front_door": {
                    "name": "healer",
                    "transports": {
                        "stdio": True,
                        "http": {
                            "path": "/mcp",
                            "default_host": "127.0.0.1",
                            "default_port": self.mcp_port,
                        },
                    },
                    "tools": tools,
                },
                "upstream_config_present": upstream.is_file(),
                # names and where they live only; token env names and commands stay out
                "upstream_servers": [
                    {"name": s["name"], "transport": s["transport"], "url": s.get("url")}
                    for s in (load_config(upstream) if upstream.is_file() else [])
                ]
                + [
                    {"name": a["name"], "transport": a["kind"], "url": a.get("base_url")}
                    for a in (load_apis(upstream) if upstream.is_file() else [])
                ],
            }
        return self._mcp_info

    async def wait(self) -> None:
        await asyncio.gather(*self.tasks.values())

    async def aclose(self) -> None:
        async with self.lock:
            await self._stop()
            self.store.close()
            if self.jev:
                await self.jev.aclose()

    async def _stop(self) -> None:
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
        self.tasks = {}
        for client in self.clients:
            await client.aclose()
        self.clients = []

    def _clear(self) -> None:
        self.custom = None
        for mock in self.mocks.values():
            mock.reset()
        self.mutation = None
        self.epoch += 1
        events = self.store.call_events()
        self.base_event = events[-1]["event_id"] if events else 0
        self.runs = {a: dict(IDLE) for a in self.mocks}
        self.traces = {a: [] for a in self.mocks}

    def state(self, after: int = 0) -> dict:
        self._refresh_audit()
        audit = self._audit
        calls_since_reset = self.store.call_events(self.base_event)
        calls = [event for event in calls_since_reset if event["event_id"] > after]
        patch_calls = [
            {
                key: event[key]
                for key in ("event_id", "ts_ms", "agent", "tool", "class", "latency_ms", "patches")
            }
            for event in calls_since_reset
            if event["agent"] == "mcp" and event.get("patches")
        ]
        return {
            "epoch": self.epoch,
            "active_mutation": self.mutation,
            "active_custom": self.custom,
            "run_scenario": self.run_scenario,
            "runs": self.runs,
            # Both agents share one audit log; only the healing side can heal.
            "traces": {
                "healing": self.traces["healing"],
                "baseline": [{**t, "heal_event": None} for t in self.traces["baseline"]],
            },
            "events": calls,
            "patch_calls": patch_calls,
            "heals": self._heal_summaries.copy(),
            "metrics": {
                "mttr": {
                    str(int(t)): v for t, v in metrics.mttr_summary(audit).items()
                },
                "outcomes": metrics.outcome_counts(audit),
                "impact": self._impact(audit),
            },
            "mocks": {
                a: {"mutation": m.mutation, "data": m.state()}
                for a, m in self.mocks.items()
            },
        }

    def _refresh_audit(self) -> None:
        for event_id, event in self.store.audit_events_since(self._audit_last_id):
            summary = self._heal(event)
            self._audit.append(event)
            self._heal_summaries.append(summary)
            self._audit_last_id = event_id

    def _drift(self, mutation: str | None) -> None:
        self.drifts.append((time.time_ns() // 1_000_000, mutation))

    def _heal(self, e: AuditEvent) -> dict:
        fix = self.store.get_fix(e.fix_id) if e.fix_id is not None else None
        # The break that was live when this heal happened, for the "what broke" line.
        drift = next((m for ms, m in reversed(self.drifts) if ms <= e.ts_ms), None)
        try:
            raw = json.loads(e.raw_error) if e.raw_error else None
        except ValueError:
            raw = None
        tool_cfg = self.tools["tools"].get(e.tool, {})
        return {
            "drift": drift,
            "raw_error": raw,
            "write": bool(tool_cfg.get("write")),
            "ts_ms": e.ts_ms,
            "tool": e.tool,
            "class": e.cls,
            "raw_code": e.raw_code,
            "tier": e.tier,
            "path": e.path,
            "outcome": e.outcome,
            "reason": e.reason,
            "mttr_ms": e.mttr_ms,
            "heal_ms": e.heal_ms,
            "jev_tokens": e.jev_tokens,
            "llm_tokens": e.llm_tokens,
            "layers": e.layers,
            "fingerprint": e.fingerprint,
            "fix_id": e.fix_id,
            "fix": {"request_ops": fix.request_ops, "response_ops": fix.response_ops}
            if fix
            else None,
        }

    def _impact(self, audit: list[AuditEvent]) -> dict:
        """What the registry kept away from the agents, since the last Reset.

        Counted from the call log (both agents) and the audit log, so every number
        is measured in this session. The token figure is the one exception: a
        scripted run makes no model call, so it falls back to an explicitly
        labelled estimate (`tokens_measured` is false) until an LLM run measures it.
        """
        calls = self.store.call_events(self.base_call)
        total = {"healing": 0, "baseline": 0}
        errors = {"healing": 0, "baseline": 0}
        retries = {"healing": 0, "baseline": 0}
        last: dict[str, tuple | None] = {"healing": None, "baseline": None}
        last_failed = {"healing": False, "baseline": False}
        for e in calls:
            agent = e["agent"]
            if agent not in total:
                continue
            total[agent] += 1
            failed = e["class"] != ErrorClass.OK.value
            if failed:
                errors[agent] += 1
            # A re-send of the same tool right after a failure is a blind retry.
            key = (e["run_id"], e["tool"])
            if key == last[agent] and last_failed[agent]:
                retries[agent] += 1
            last[agent], last_failed[agent] = key, failed

        turns_saved = max(0, total["baseline"] - total["healing"])
        healer_jev = sum(e.jev_tokens for e in audit)
        healer_llm = sum(e.llm_tokens for e in audit)
        measured = self._llm_tokens  # (baseline, healing) from the last LLM run
        if measured is not None:
            base_tokens, heal_tokens = measured
        else:  # scripted session: no model call, so both bars are an estimate
            base_tokens = total["baseline"] * EST_TOKENS_PER_TURN
            heal_tokens = total["healing"] * EST_TOKENS_PER_TURN
        return {
            "heals": sum(
                1 for e in audit if e.outcome == HealOutcome.RECOVERED
            ),
            "refusals": sum(1 for e in audit if e.outcome == HealOutcome.ABORTED),
            "healing_calls": total["healing"],
            "baseline_calls": total["baseline"],
            "turns_saved": turns_saved,
            "healing_errors": errors["healing"],
            "baseline_errors": errors["baseline"],
            "errors_kept_out": max(0, errors["baseline"] - errors["healing"]),
            "baseline_retries": retries["baseline"],
            "healer_jev_tokens": healer_jev,
            "healer_llm_tokens": healer_llm,
            "healer_tokens": healer_jev + healer_llm,
            "baseline_tokens": base_tokens,
            "healing_tokens": heal_tokens,
            "tokens_saved": max(0, base_tokens - heal_tokens),
            "tokens_measured": measured is not None,
            "tokens_per_turn": EST_TOKENS_PER_TURN,
        }


async def bad_request(call: Awaitable[None]) -> None:
    try:
        await call
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def create_app(
    db_path: str | None = None,
    gateway: Registry | Gateway | None = None,
    mcp_port: int = 8001,
    upstream_config_path: str | Path | None = None,
) -> FastAPI:
    dash = Dashboard(db_path, gateway, mcp_port, upstream_config_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            await dash.aclose()

    app = FastAPI(title="Self-healing demo dashboard", lifespan=lifespan)
    app.state.dash = dash
    app.include_router(connections_router)

    @app.get("/", include_in_schema=False)
    async def landing() -> FileResponse:
        return FileResponse(HERE / "landing.html", headers={"Cache-Control": "no-cache"})

    @app.get("/guide.js", include_in_schema=False)
    async def guide() -> FileResponse:
        return FileResponse(HERE / "guide.js", headers={"Cache-Control": "no-cache"})

    @app.get("/ui.js", include_in_schema=False)
    async def ui() -> FileResponse:
        return FileResponse(HERE / "ui.js", headers={"Cache-Control": "no-cache"})

    @app.get("/theme.css", include_in_schema=False)
    async def theme() -> FileResponse:
        return FileResponse(HERE / "theme.css", headers={"Cache-Control": "no-cache"})

    @app.get("/live", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(HERE / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/panels/{filename:path}", include_in_schema=False)
    async def panel_file(filename: str) -> FileResponse:
        panels_dir = (HERE / "panels").resolve()
        target = (panels_dir / filename).resolve()
        if not target.is_relative_to(panels_dir) or not target.is_file():
            raise HTTPException(404, "Panel file not found")
        media_type = "text/javascript" if target.suffix == ".js" else None
        return FileResponse(
            target,
            media_type=media_type,
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/api/state")
    async def get_state(after: int = 0) -> dict:
        return dash.state(after)

    @app.get("/api/explorer/info")
    async def explorer_info() -> dict:
        return get_explorer_info()

    @app.post("/api/explore")
    async def explore(body: ExploreIn) -> dict:
        try:
            return await dash.explore(
                body.query, body.mutation, body.agent, body.custom
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/mcp")
    async def mcp() -> dict:
        return await dash.mcp_info()

    @app.get("/api/mcp/calls")
    async def mcp_calls() -> dict:
        if dash.gateway is not None:
            tools = dash.gateway.tools()
        else:
            tools = (await dash.mcp_info())["front_door"]["tools"]
        return mcp_tool_usage(tools, dash.store.call_events(), dash.store.audit_events())

    @app.get("/api/report")
    async def report() -> dict:
        try:
            text = (ROOT / "REPORT.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            text = None
        return {"report": text}

    @app.get("/api/metrics/scorecard")
    async def get_scorecard() -> dict:
        return scorecard()

    @app.get("/api/metrics/live")
    async def get_metrics_live() -> dict:
        audit = dash.store.audit_events()[dash.base_heal :]
        return live_safety(audit)

    @app.get("/api/metrics/lifecycle")
    async def get_metrics_lifecycle() -> dict:
        return fix_lifecycle(dash.store)

    @app.post("/api/start")
    async def start(body: StartIn) -> dict:
        await bad_request(dash.start(body.agent, body.step_delay))
        return dash.state()

    @app.get("/api/drift-editor/schemas")
    async def drift_editor_schemas() -> dict:
        return {"tools": await dash.drift_schemas()}

    @app.post("/api/mutation")
    async def mutation(body: MutationIn) -> dict:
        custom = None
        if body.id == CUSTOM:
            custom = body.custom
            if body.fake_schema is not None:
                tool = (body.custom or {}).get("tool")
                actual = (await dash.drift_schemas()).get(tool)
                if actual is None:
                    raise HTTPException(400, f"unknown tool {tool!r}, one of {sorted(V1_REQUEST)}")
                try:
                    custom = custom_from_schema(tool, actual, body.fake_schema, body.header)
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
        await bad_request(dash.mutate(body.id, custom))
        if body.id and all(r["status"] != "running" for r in dash.runs.values()):
            # Nothing is calling the API, so a drift would go unseen: run a quick scripted
            # pass so the break is hit and healed, and the patch log shows it.
            await bad_request(dash.start("scripted", 0.3))
        return dash.state()

    @app.post("/api/reset")
    async def reset() -> dict:
        await dash.reset()
        return dash.state()

    return app
