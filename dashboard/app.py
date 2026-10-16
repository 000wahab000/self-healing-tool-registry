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
from dashboard.explorer import (
    _recording_executor,
    check_data_correctness,
    get_explorer_info,
    run_explore,
)
from healer import metrics
from healer.gateway import load_apis, load_config
from healer.jev import from_env
from healer.models import AuditEvent
from healer.registry import Registry
from healer.repair import from_env as repair_from_env
from healer.store import Store
from mock_api.app import ALIASES, CUSTOM, MUTATIONS
from mock_api.app import create_app as create_mock

LEAD_IN_STEPS = 3  # scripted agents wait this many steps before their first call
HERE = Path(__file__).parent
ROOT = HERE.parent
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


class ExploreIn(BaseModel):
    query: str = ""
    mutation: str | None = None
    agent: Literal["scripted", "llm"] = "scripted"
    custom: dict | None = None  # the drift spec when mutation is CUSTOM


class Dashboard:
    """Both agents run the demo task against their own mock; the store is shared."""

    def __init__(self, db_path: str | None = None) -> None:
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
        self.run_scenario: str | None = None
        # The live view starts empty on a fresh server: calls kept in the db from an earlier
        # process have no recorded traces, so they could not open as call cards.
        events = self.store.call_events()
        self.base_event = events[-1]["event_id"] if events else 0
        self.base_heal = 0
        self.drifts: list[tuple[int, str | None]] = []  # (ms, mutation) as it went live
        self.runs = {a: dict(IDLE) for a in self.mocks}
        self.traces: dict[str, list[dict]] = {a: [] for a in self.mocks}
        self._mcp_info: dict | None = None

    async def start(self, kind: str, step_delay: float) -> None:
        if kind == "llm" and not os.environ.get("NVIDIA_API_KEY"):
            raise ValueError("llm agents need NVIDIA_API_KEY")
        async with self.lock:
            await self._stop()
            mutation = self.mutation  # a drift picked before Start applies to this run
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
                    mock.set_mutation(mutation)
                self.mutation = mutation
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
        # A crashed run is shown on the page as the run's error, not swallowed.
        except Exception as exc:  # noqa: BLE001
            self.runs[agent] = {
                **IDLE,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    async def mutate(self, mid: str | None) -> None:
        if mid is not None and mid not in MUTATIONS and mid not in ALIASES:
            raise ValueError(f"unknown mutation {mid!r}")
        async with self.lock:
            for mock in self.mocks.values():
                mock.set_mutation(mid)
            self.mutation = mid
            self._drift(mid)

    async def reset(self) -> None:
        async with self.lock:
            await self._stop()
            self._clear()
            # Only Reset empties the patch log; Start, scenarios and drifts keep adding to it.
            self.base_heal = len(self.store.audit_events())

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
        async with self.lock:
            await self._stop()
            self._clear()
            self._drift(mutation)
            return await run_explore(
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

    async def mcp_info(self) -> dict:
        """What the MCP front door exposes, read from the same `Registry.tools()`."""
        if self._mcp_info is None:
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
            upstream = ROOT / "config" / "mcp_servers.json"
            self._mcp_info = {
                "front_door": {
                    "name": "healer",
                    "transports": {
                        "stdio": True,
                        "http": {
                            "path": "/mcp",
                            "default_host": "127.0.0.1",
                            "default_port": 8001,
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
        for mock in self.mocks.values():
            mock.reset()
        self.mutation = None
        self.epoch += 1
        events = self.store.call_events()
        self.base_event = events[-1]["event_id"] if events else 0
        self.runs = {a: dict(IDLE) for a in self.mocks}
        self.traces = {a: [] for a in self.mocks}

    def state(self, after: int = 0) -> dict:
        audit = self.store.audit_events()[self.base_heal :]
        return {
            "epoch": self.epoch,
            "active_mutation": self.mutation,
            "run_scenario": self.run_scenario,
            "runs": self.runs,
            # Both agents share one audit log; only the healing side can heal.
            "traces": {
                "healing": self.traces["healing"],
                "baseline": [{**t, "heal_event": None} for t in self.traces["baseline"]],
            },
            "events": self.store.call_events(max(after, self.base_event)),
            "heals": [self._heal(e) for e in audit],
            "metrics": {
                "mttr": {
                    str(int(t)): v for t, v in metrics.mttr_summary(audit).items()
                },
                "outcomes": metrics.outcome_counts(audit),
            },
            "mocks": {
                a: {"mutation": m.mutation, "data": m.state()}
                for a, m in self.mocks.items()
            },
        }

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
            "fingerprint": e.fingerprint,
            "fix_id": e.fix_id,
            "fix": {"request_ops": fix.request_ops, "response_ops": fix.response_ops}
            if fix
            else None,
        }


async def bad_request(call: Awaitable[None]) -> None:
    try:
        await call
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def create_app(db_path: str | None = None) -> FastAPI:
    dash = Dashboard(db_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
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

    @app.get("/api/report")
    async def report() -> dict:
        try:
            text = (ROOT / "bench" / "report.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            text = None
        return {"report": text}

    @app.post("/api/start")
    async def start(body: StartIn) -> dict:
        await bad_request(dash.start(body.agent, body.step_delay))
        return dash.state()

    @app.post("/api/mutation")
    async def mutation(body: MutationIn) -> dict:
        await bad_request(dash.mutate(body.id))
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
