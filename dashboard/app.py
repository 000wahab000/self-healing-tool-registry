"""Live demo dashboard: two in-process mock APIs, the healing and baseline agents, one page.

Every endpoint is `async def` on purpose: the SQLite store lives on the event-loop thread.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from collections.abc import Awaitable
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from agents import baseline_agent, common, healing_agent, scripted
from dashboard.explorer import _recording_executor, get_explorer_info, run_explore
from healer import metrics
from healer.jev import from_env
from healer.models import AuditEvent
from healer.registry import Registry
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
        self.base_event = 0  # the view starts after the last start / reset
        self.base_heal = 0
        self.runs = {a: dict(IDLE) for a in self.mocks}
        self.traces: dict[str, list[dict]] = {a: [] for a in self.mocks}

    async def start(self, kind: str, step_delay: float) -> None:
        if kind == "llm" and not os.environ.get("NVIDIA_API_KEY"):
            raise ValueError("llm agents need NVIDIA_API_KEY")
        async with self.lock:
            await self._stop()
            mutation = self.mutation  # a drift picked before Start applies to this run
            self._clear()
            http = {
                a: httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=m), base_url="http://mock"
                )
                for a, m in self.mocks.items()
            }
            self.clients = list(http.values())
            healing = Registry(
                http["healing"], self.tools, self.cfg, self.store, self.jev
            )
            baseline = Registry(http["baseline"], self.tools, self.cfg)  # v1 specs only
            await healing.load()
            await baseline.load()
            # Registries freeze the clean v1 spec first, then the drift goes live.
            if mutation is not None:
                for mock in self.mocks.values():
                    mock.set_mutation(mutation)
                self.mutation = mutation
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
                    ),
                    "baseline": lambda: self._scripted(
                        base_exec,
                        "baseline",
                        True,
                        step_delay,
                        run_id,
                    ),
                }
            else:
                llm = common.make_llm()
                jobs = {
                    "healing": lambda: common.run(
                        healing_agent.build(healing, llm, self.store, run_id),
                        common.TASK,
                    ),
                    "baseline": lambda: common.run(
                        baseline_agent.build(
                            http["baseline"], baseline, llm, self.store, run_id
                        ),
                        common.TASK,
                    ),
                }
            self.runs = {a: {**IDLE, "status": "running"} for a in jobs}
            self.tasks = {
                a: asyncio.create_task(self._finish(a, job)) for a, job in jobs.items()
            }

    async def _scripted(
        self, execute, agent: str, retry_same_args: bool, step_delay: float, run_id: str
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
        )

    async def _finish(self, agent: str, job) -> None:
        try:
            self.runs[agent] = {"status": "done", **asdict(await job())}
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

    async def reset(self) -> None:
        async with self.lock:
            await self._stop()
            self._clear()

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
        self.base_heal = len(self.store.audit_events())
        self.runs = {a: dict(IDLE) for a in self.mocks}
        self.traces = {a: [] for a in self.mocks}

    def state(self, after: int = 0) -> dict:
        audit = self.store.audit_events()[self.base_heal :]
        return {
            "epoch": self.epoch,
            "active_mutation": self.mutation,
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

    def _heal(self, e: AuditEvent) -> dict:
        fix = self.store.get_fix(e.fix_id) if e.fix_id is not None else None
        return {
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

    @app.get("/", include_in_schema=False)
    async def landing() -> FileResponse:
        return FileResponse(HERE / "landing.html", headers={"Cache-Control": "no-cache"})

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
        return dash.state()

    @app.post("/api/reset")
    async def reset() -> dict:
        await dash.reset()
        return dash.state()

    return app
