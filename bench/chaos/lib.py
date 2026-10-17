"""Shared chaos helpers: process control, healer launch, MCP front-door calls, audit reader.

No LLM anywhere: NVIDIA_API_KEY/OPENROUTER*/etc. are stripped from every child env and the healer
always runs with --no-repair. Calls go through the healer's MCP front door with the python client.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[2]
SECRET_ENV = ("NVIDIA", "OPENROUTER", "OPENCODE", "ANTHROPIC", "OPENAI", "JEV_", "MCP_GITHUB")
procs: list[subprocess.Popen] = []


def sha_prefix(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(SECRET_ENV)}
    env["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{ROOT}"
    env["PYTHONUNBUFFERED"] = "1"
    env.update(extra or {})
    return env


def spawn(name: str, argv: list[str], logdir: Path, env_extra: dict[str, str] | None = None,
          cwd: Path | None = None) -> subprocess.Popen:
    logdir.mkdir(parents=True, exist_ok=True)
    log = (logdir / f"{name}.log").open("ab")
    p = subprocess.Popen(argv, cwd=cwd or ROOT, env=child_env(env_extra), stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, shell=(argv[0] == "npx"))
    p.chaos_name = name  # type: ignore[attr-defined]
    procs.append(p)
    return p


def kill(p: subprocess.Popen) -> None:
    if p.poll() is None:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, check=False)
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            pass
    if p in procs:
        procs.remove(p)


def kill_all() -> None:
    while procs:
        kill(procs[0])


def port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_port(port: int, p: subprocess.Popen | None = None, timeout: float = 60) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if p is not None and p.poll() is not None:
            raise RuntimeError(f"{getattr(p, 'chaos_name', '?')} exited early")
        if port_open(port):
            return
        time.sleep(0.25)
    raise RuntimeError(f"port {port} did not open in {timeout}s")


def wait_closed(port: int, timeout: float = 15) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout and port_open(port):
        time.sleep(0.25)


def start_healer(logdir: Path, db: Path, servers_json: Path, port: int, origins: list[str],
                 keep_db: bool = False, name: str = "healer", timeout: float = 60,
                 env_extra: dict[str, str] | None = None) -> subprocess.Popen:
    if not keep_db:
        for ext in ("", "-wal", "-shm"):
            db.with_name(db.name + ext).unlink(missing_ok=True)
    p = spawn(name, [sys.executable, "-m", "healer.mcp_server", "--transport", "http", "--no-rest", "--host",
                     "127.0.0.1", "--port", str(port), "--no-repair", "--mcp-servers", str(servers_json),
                     "--db", str(db)], logdir, {"CONNECTIONS_ALLOWED_ORIGINS": ",".join(origins), **(env_extra or {})})
    wait_port(port, p, timeout)
    return p


def jl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts_ms": int(time.time() * 1000), **row}, default=str) + "\n")


def read_jsonl(path: Path, start: int = 0) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()[start:] if x.strip()]


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


class Audit:
    def __init__(self, path: Path) -> None:
        self.path = path

    def q(self, sql: str, args: tuple = ()) -> list[dict]:
        con = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args)]
        finally:
            con.close()

    def max_heal_id(self) -> int:
        return self.q("SELECT COALESCE(MAX(event_id),0) m FROM heal_events")[0]["m"]

    def heals_after(self, after: int) -> list[dict]:
        rows = self.q(
            "SELECT h.event_id, h.tool, h.class, h.raw_code, h.tier, h.path, h.fix_id, h.outcome, h.reason,"
            " h.mttr_ms, h.raw_error, f.request_ops, f.response_ops FROM heal_events h"
            " LEFT JOIN fixes f ON f.fix_id=h.fix_id WHERE h.event_id > ? ORDER BY h.event_id", (after,))
        for r in rows:
            for k in ("request_ops", "response_ops"):
                if isinstance(r.get(k), str):
                    try:
                        r[k] = json.loads(r[k])
                    except ValueError:
                        pass
            r["raw_error"] = (r["raw_error"] or "")[:300]
        return rows

    def calls_after(self, after: int) -> list[dict]:
        return self.q("SELECT event_id, tool, class, latency_ms FROM call_events WHERE event_id > ?"
                      " ORDER BY event_id", (after,))

    def max_call_id(self) -> int:
        return self.q("SELECT COALESCE(MAX(event_id),0) m FROM call_events")[0]["m"]


def unpack(res: Any) -> dict:
    if res.structured_content is not None:
        out = res.structured_content
    else:
        texts = [c.text for c in res.content if getattr(c, "type", "") == "text"]
        try:
            out = json.loads(texts[0]) if texts else {}
        except (ValueError, IndexError):
            out = {"text": texts}
    return {"is_error": res.is_error, "result": out}


class Front:
    """One MCP client session against the healer front door."""

    def __init__(self, port: int) -> None:
        self.port = port

    async def __aenter__(self):
        self._cm = streamable_http_client(f"http://127.0.0.1:{self.port}/mcp")
        r, w, *_ = await self._cm.__aenter__()
        self.s = ClientSession(r, w)
        await self.s.__aenter__()
        await self.s.initialize()
        return self

    async def __aexit__(self, *a):
        try:
            await self.s.__aexit__(*a)
        finally:
            await self._cm.__aexit__(*a)

    async def tools(self) -> list[dict]:
        return [t.model_dump(by_alias=True, exclude_none=True) for t in (await self.s.list_tools()).tools]

    async def call(self, name: str, args: dict, timeout: float = 90) -> dict:
        t0 = time.time()
        try:
            res = await asyncio.wait_for(self.s.call_tool(name, args), timeout)
            out = unpack(res)
            out["exc"] = None
        except TimeoutError:
            out = {"is_error": None, "result": None, "exc": f"HUNG>{timeout}s"}
        except Exception as e:  # noqa: BLE001
            out = {"is_error": None, "result": None, "exc": f"{type(e).__name__}: {e}"[:300]}
        out["latency_ms"] = int((time.time() - t0) * 1000)
        return out


def short(x: Any, n: int = 400) -> Any:
    s = json.dumps(x, default=str)
    return x if len(s) <= n else s[:n] + "..."
