"""Chaos driver: false GitHub MCP schemas frozen in the healer, real schema behind it.

For every profile in cases.yaml:
  1. shim -> mode=fake, profile=P   (so the healer freezes the FALSE agent schema at startup)
  2. start a fresh healer (fresh db)
  3. shim -> mode=real              (the world "drifts" to the real schema)
  4. control phase: the six calls, written with FAKE arg names, through the healer's MCP
  5. agent phase (agent profiles only): a fresh healer again (steps 1-3), then 2 `claude -p` calls

Everything is joined per call from: the shim log (what was forwarded), the fake upstream log (the
independent oracle: what the upstream accepted), the healer's sqlite audit (tier/outcome/reason/ops).

Offline:  python bench/chaos/github/run.py
Live   :  see REPORT.md ("Live run"); uses --live and a real token env var, never run offline.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPORT_MARKER = "<!-- supplementary-evidence -->"

import profiles as P
import yaml
from jsonschema import Draft202012Validator
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

OUT = HERE / "out"
ROOT = HERE.parents[2]
PORT_HEALER, PORT_SHIM, PORT_UP = 8097, 8099, 8100
MAX_CLAUDE_CALLS = 16
CLAUDE_TIMEOUT_S = 240
procs: list[subprocess.Popen] = []


# ----------------------------------------------------------------------------------------------
# process management
def spawn(name: str, argv: list[str], env_extra: dict[str, str] | None = None) -> subprocess.Popen:
    OUT.mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'src'}{os.pathsep}{ROOT}", **(env_extra or {})}
    log = (OUT / f"{name}.log").open("wb")
    p = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
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
    import socket

    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def supplementary_chaos_report(
    summary: str,
    *,
    mode: str,
    generated_at: str,
    profile_count: int,
    row_count: int,
    claude_calls: int,
) -> str:
    """Render this run's provenance and summary for the supplementary report section."""
    return (
        "\n\n## GitHub MCP chaos run\n\n"
        + f"Mode: {mode}; generated: {generated_at}; profiles: {profile_count}; rows: {row_count}.\n\n"
        + summary
        + f"\n\nclaude calls used: {claude_calls}\n"
    )


def append_chaos_report(
    report_path: Path,
    summary: str,
    *,
    mode: str,
    generated_at: str,
    profile_count: int,
    row_count: int,
    claude_calls: int,
) -> None:
    previous = report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    with report_path.open("a", encoding="utf-8") as report_file:
        if REPORT_MARKER not in previous:
            report_file.write("\n\n" + REPORT_MARKER + "\n")
        report_file.write(
            supplementary_chaos_report(
                summary,
                mode=mode,
                generated_at=generated_at,
                profile_count=profile_count,
                row_count=row_count,
                claude_calls=claude_calls,
            )
        )


def wait_port(port: int, p: subprocess.Popen, timeout: float = 40) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if p.poll() is not None:
            raise RuntimeError(f"{p.chaos_name} exited early (see out/{p.chaos_name}.log)")  # type: ignore[attr-defined]
        if port_open(port):
            return
        time.sleep(0.3)
    raise RuntimeError(f"port {port} did not open")


def control(mode: str | None = None, profile: str | None = None) -> dict:
    body = {k: v for k, v in (("mode", mode), ("profile", profile)) if v}
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT_SHIM}/control",
        data=json.dumps(body).encode() if body else None,
        headers={"content-type": "application/json"},
        method="POST" if body else "GET",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def mcp_ctx(port: int):
    return streamable_http_client(f"http://127.0.0.1:{port}/mcp")


async def list_tools(port: int) -> list[dict]:
    async with mcp_ctx(port) as (r, w, *_):  # noqa: SIM117
        async with ClientSession(r, w) as s:
            await s.initialize()
            return [t.model_dump(by_alias=True, exclude_none=True) for t in (await s.list_tools()).tools]


def start_healer(args: argparse.Namespace) -> subprocess.Popen:
    for ext in ("", "-wal", "-shm"):
        (OUT / f"run.db{ext}").unlink(missing_ok=True)
    py = sys.executable
    p = spawn(
        "healer",
        [py, "-m", "healer.mcp_server", "--transport", "http", "--no-rest", "--host", "127.0.0.1",
         "--port", str(PORT_HEALER), "--no-repair", "--mcp-servers", str(HERE / "chaos.servers.json"),
         "--db", str(OUT / "run.db")],
        # the egress guard refuses loopback unless the exact origin is allow-listed
        {"CONNECTIONS_ALLOWED_ORIGINS": f"http://127.0.0.1:{PORT_SHIM}"},
    )
    wait_port(PORT_HEALER, p)
    return p


# ----------------------------------------------------------------------------------------------
# log readers
def read_jsonl(path: Path, start: int = 0) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines[start:] if x.strip()]


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


class Audit:
    """Read-only view of the healer's sqlite db."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _q(self, sql: str, args: tuple = ()) -> list[dict]:
        con = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args)]
        finally:
            con.close()

    def max_heal_id(self) -> int:
        return (self._q("SELECT COALESCE(MAX(event_id),0) m FROM heal_events")[0]["m"])

    def heals_after(self, after_id: int) -> list[dict]:
        rows = self._q(
            "SELECT h.event_id, h.ts_ms, h.tool, h.class, h.raw_code, h.tier, h.path, h.fix_id, h.outcome,"
            " h.reason, h.mttr_ms, h.raw_error, h.layers, f.request_ops, f.response_ops"
            " FROM heal_events h LEFT JOIN fixes f ON f.fix_id = h.fix_id"
            " WHERE h.event_id > ? ORDER BY h.event_id",
            (after_id,),
        )
        for r in rows:
            for k in ("request_ops", "response_ops", "layers"):
                if isinstance(r.get(k), str):
                    try:
                        r[k] = json.loads(r[k])
                    except ValueError:
                        pass
            r["raw_error"] = (r["raw_error"] or "")[:300]
        return rows

    def calls(self) -> list[dict]:
        return self._q("SELECT event_id, ts_ms, tool, class, latency_ms FROM call_events ORDER BY event_id")


# ----------------------------------------------------------------------------------------------
# scoring
def classify(intended: dict, shim: list[dict], up: list[dict], heals: list[dict], result: dict | None, exc: str | None) -> dict:
    """Observed outcome of one registry call."""
    if exc:
        return {"observed": "crashed", "why": exc}
    accepted_up = [u for u in up if u.get("accepted")]
    if accepted_up:
        received = accepted_up[-1]["args"]
    else:
        ok = [s for s in shim if s["status"] == "ok"]
        received = ok[-1]["args_forwarded"] if ok else None
    accepted = received is not None
    recovered = any(h["outcome"] == "RECOVERED" for h in heals)
    if result and result.get("error") == "MCP_TOOL_ERROR":
        return {"observed": "crashed", "why": "MCP_TOOL_ERROR", "received": received}
    if accepted:
        if received != intended:
            return {"observed": "wrong", "why": "upstream accepted different args", "received": received}
        return {"observed": "heal_correct" if heals and recovered else "pass_through", "received": received}
    if heals and not recovered:
        return {"observed": "refused", "received": None}
    if result and isinstance(result, dict) and "error" in result and not heals:
        return {"observed": "missed", "why": f"error without audit row: {result.get('error')}", "received": None}
    return {"observed": "missed", "why": "no accepted upstream call", "received": None}


def verdict(expected: str, observed: str) -> str:
    if observed == "wrong":
        return "FALSE_PATCH"
    if observed == "crashed":
        return "CRASH"
    if expected == "pass_through":
        return "PASS" if observed == "pass_through" else ("UNEXPECTED_HEAL" if observed == "heal_correct" else observed.upper())
    if expected == "heal":
        return "PASS" if observed == "heal_correct" else ("NOT_NEEDED" if observed == "pass_through" else observed.upper())
    if expected == "refuse":
        return "PASS" if observed == "refused" else ("UNSAFE_HEAL_OK" if observed == "heal_correct" else observed.upper())
    return "?"


def relabel(row: dict) -> dict:
    """An agent call the front door rejected before any upstream contact (AGENT_ARG_ERROR) is the
    agent's own mistake against the frozen schema, not a registry outcome: keep it, do not score it."""
    if row.get("kind") == "agent" and "AGENT_ARG_ERROR" in json.dumps(row.get("mcp_result")):
        row.update(observed="agent_arg_error", verdict="AGENT_ERR",
                   why="front door rejected agent args against the frozen schema; no upstream call")
    return row


def short(r: Any, n: int = 300) -> Any:
    s = json.dumps(r, default=str)
    return r if len(s) <= n else s[:n] + "..."


# ----------------------------------------------------------------------------------------------
async def control_phase(case: dict, prof: P.Profile, plan: dict, audit: Audit, args: argparse.Namespace) -> list[dict]:
    rows = []
    shim_log, up_log = OUT / "shim_calls.jsonl", OUT / "upstream_calls.jsonl"
    async with mcp_ctx(PORT_HEALER) as (r, w, *_):  # noqa: SIM117
        async with ClientSession(r, w) as s:
            await s.initialize()
            for call in plan["calls"]:
                tool = call["tool"]
                real = {**call["real_args"], **(case.get("control_extra_args") or {})}
                real = subst(real, args)
                fake = prof.to_fake(tool, real)
                s0, u0, h0 = line_count(shim_log), line_count(up_log), audit.max_heal_id()
                t0 = time.time()
                result, exc = None, None
                try:
                    res = await asyncio.wait_for(s.call_tool(f"github__{tool}", fake), 60)
                    result = res.structured_content if res.structured_content is not None else {"text": [c.text for c in res.content if getattr(c, "type", "") == "text"]}
                    is_error = res.is_error
                except Exception as e:  # noqa: BLE001
                    exc, is_error = f"{type(e).__name__}: {e}"[:300], None
                shim = read_jsonl(shim_log, s0)
                up = read_jsonl(up_log, u0)
                heals = audit.heals_after(h0)
                obs = classify(real, shim, up, heals, result, exc)
                exp = case["expect"][call["id"]]
                rows.append(
                    {
                        "kind": "control", "profile": case["id"], "tool": tool, "expected": exp,
                        "agent_args": fake, "intended_real_args": real,
                        "shim_forwarded": [{"args_in": x["args_in"], "args_forwarded": x["args_forwarded"], "status": x["status"], "code": x.get("code"), "message": x.get("message")} for x in shim],
                        "upstream": [{"args": x["args"], "accepted": x["accepted"], "message": x.get("message")} for x in up],
                        "audit": [{k: h.get(k) for k in ("tier", "path", "outcome", "reason", "raw_code", "request_ops", "mttr_ms")} for h in heals],
                        "mcp_is_error": is_error, "mcp_result": short(result), "latency_ms": int((time.time() - t0) * 1000),
                        **obs, "verdict": verdict(exp, obs["observed"]),
                    }
                )
    return rows


def subst(args: dict, a: argparse.Namespace) -> dict:
    """Replace the placeholder octocat/hello-world/1 with --owner/--repo/--issue (live runs)."""
    m = {"octocat": a.owner, "hello-world": a.repo}
    return {k: (m.get(v, v) if isinstance(v, str) else (a.issue if k == "issue_number" else v)) for k, v in args.items()}


def parse_stream(text: str) -> dict:
    tool_uses, results, session, cost, final = [], {}, None, None, None
    for line in text.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("session_id"):
            session = ev["session_id"]
        if ev.get("type") == "assistant":
            for b in ev.get("message", {}).get("content", []):
                if b.get("type") == "tool_use":
                    tool_uses.append({"id": b["id"], "name": b["name"], "input": b["input"]})
        elif ev.get("type") == "user":
            content = ev.get("message", {}).get("content", [])
            if isinstance(content, list):
                for b in content:
                    if b.get("type") == "tool_result":
                        results[b["tool_use_id"]] = b.get("content")
        elif ev.get("type") == "result":
            cost, final = ev.get("total_cost_usd"), ev.get("result")
    return {"tool_uses": tool_uses, "results": results, "session": session, "cost": cost, "final": final}


def agent_phase(case: dict, prof: P.Profile, plan: dict, audit: Audit, args: argparse.Namespace, budget: dict) -> list[dict]:
    rows, session = [], None
    shim_log, up_log = OUT / "shim_calls.jsonl", OUT / "upstream_calls.jsonl"
    fake_schemas = {t["name"]: t.get("inputSchema") or {} for t in asyncio.run(list_tools(PORT_HEALER))}
    cwd = OUT / "agent_cwd"
    cwd.mkdir(exist_ok=True)
    seen_calls = len(audit.calls())
    for i, task in enumerate(plan["agent_tasks"][:2]):
        if budget["used"] >= MAX_CLAUDE_CALLS:
            rows.append({"kind": "agent", "profile": case["id"], "skipped": "claude call cap reached"})
            break
        budget["used"] += 1
        task = subst_text(task, args)
        cmd = ["claude", "-p", task, "--model", "haiku", "--mcp-config", str(HERE / "mcp-healer.json"),
               "--strict-mcp-config", "--allowedTools", "mcp__healer",
               "--disallowedTools", "Bash,Read,Write,Edit,WebFetch,WebSearch,Task",
               "--output-format", "stream-json", "--verbose", "--max-budget-usd", "0.30"]
        if session:
            cmd += ["--resume", session]
        s0, u0, h0 = line_count(shim_log), line_count(up_log), audit.max_heal_id()
        t0 = time.time()
        try:
            cp = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", timeout=CLAUDE_TIMEOUT_S, check=False)
            out, err, rc = cp.stdout, cp.stderr, cp.returncode
        except subprocess.TimeoutExpired as e:
            out, err, rc = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout", -1
        (OUT / f"agent_{case['id']}_{i}.stream.jsonl").write_text(out, encoding="utf-8")
        st = parse_stream(out)
        session = st["session"] or session
        shim = read_jsonl(shim_log, s0)
        up = read_jsonl(up_log, u0)
        heals = audit.heals_after(h0)
        calls = audit.calls()[seen_calls:]
        seen_calls += len(calls)
        uses = [u for u in st["tool_uses"] if u["name"].startswith("mcp__healer__")]
        if not uses:
            rows.append({"kind": "agent", "profile": case["id"], "task": i, "tool": None, "expected": "n/a", "observed": "no_tool_call", "verdict": "NO_CALL", "rc": rc, "stderr": err[:200], "final": short(st["final"])})
            continue
        for j, u in enumerate(uses):
            tool = u["name"].split("__", 3)[-1]
            ev = calls[j] if j < len(calls) else None
            lo, hi = (ev["ts_ms"] - ev["latency_ms"] - 50, ev["ts_ms"] + 50) if ev else (0, 10**15)
            sh = [x for x in shim if lo <= x["ts_ms"] <= hi and x["tool"] == tool]
            upl = [x for x in up if lo <= x["ts_ms"] <= hi and x["tool"] == tool]
            hl = [h for h in heals if lo <= h["ts_ms"] <= hi and h["tool"].endswith(tool)]
            fake_args = u["input"]
            intended = prof.to_real(tool, fake_args)
            schema_ok = Draft202012Validator(fake_schemas.get(f"github__{tool}", {})).is_valid(fake_args)
            res = st["results"].get(u["id"])
            result = None
            if isinstance(res, list):
                txt = "".join(b.get("text", "") for b in res if isinstance(b, dict))
                try:
                    result = json.loads(txt)
                except ValueError:
                    result = {"text": txt}
            elif isinstance(res, str):
                result = {"text": res}
            if isinstance(result, dict) and "error" not in result and "result" not in result and "text" in result:
                # a plain-text error from the front door (registry error dicts come as JSON)
                pass
            obs = classify(intended, sh, upl, hl, result, None)
            if not schema_ok and obs["observed"] == "missed":
                obs["why"] = "agent args violate the frozen schema (AGENT_ARG_ERROR path)"
            exp = case["expect"].get(tool, "n/a")
            rows.append(relabel(
                {
                    "kind": "agent", "profile": case["id"], "task": i, "tool": tool, "expected": exp,
                    "agent_args": fake_args, "agent_args_match_frozen_schema": schema_ok, "intended_real_args": intended,
                    "shim_forwarded": [{"args_in": x["args_in"], "args_forwarded": x["args_forwarded"], "status": x["status"], "code": x.get("code"), "message": x.get("message")} for x in sh],
                    "upstream": [{"args": x["args"], "accepted": x["accepted"], "message": x.get("message")} for x in upl],
                    "audit": [{k: h.get(k) for k in ("tier", "path", "outcome", "reason", "raw_code", "request_ops", "mttr_ms")} for h in hl],
                    "mcp_result": short(result), "cost_usd": st["cost"], "latency_ms": int((time.time() - t0) * 1000),
                    "agent_final": short(st["final"], 200), **obs, "verdict": verdict(exp, obs["observed"]),
                }
            ))
    return rows


def subst_text(t: str, a: argparse.Namespace) -> str:
    return t.replace("octocat/hello-world", f"{a.owner}/{a.repo}").replace("issue number 1", f"issue number {a.issue}")


# ----------------------------------------------------------------------------------------------
def run_profile(case: dict, plan: dict, args: argparse.Namespace, budget: dict) -> list[dict]:
    prof = P.get(case["id"])
    rows: list[dict] = []
    phases = []
    if not args.agent_only:
        phases.append("control")
    if case.get("agent") and not args.no_agent:
        phases.append("agent")
    for phase in phases:
        print(f"[{case['id']}] {phase}", flush=True)
        control("fake", case["id"])
        healer = start_healer(args)
        try:
            control("real")
            audit = Audit(OUT / "run.db")
            if phase == "control":
                rows += asyncio.run(control_phase(case, prof, plan, audit, args))
            else:
                rows += agent_phase(case, prof, plan, audit, args, budget)
        finally:
            kill(healer)
    return rows


def summarize(rows: list[dict]) -> str:
    from collections import Counter, defaultdict

    by = defaultdict(list)
    for r in rows:
        if r.get("tool") or r.get("verdict") == "NO_CALL":
            by[(r["profile"], r["kind"])].append(r)
    lines = ["| profile | kind | calls | verdicts | observed |", "|---|---|---|---|---|"]
    for (prof, kind), rs in by.items():
        v = Counter(r["verdict"] for r in rs)
        o = Counter(r["observed"] for r in rs)
        lines.append(f"| {prof} | {kind} | {len(rs)} | {dict(v)} | {dict(o)} |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="GitHub MCP schema-drift chaos driver")
    ap.add_argument("--profiles", help="comma list; default all in cases.yaml")
    ap.add_argument("--no-agent", action="store_true", help="control phase only (no claude calls)")
    ap.add_argument("--agent-only", action="store_true")
    ap.add_argument("--live", action="store_true", help="real GitHub upstream (needs --token-env); not for offline runs")
    ap.add_argument("--upstream-url", default="https://api.githubcopilot.com/mcp/")
    ap.add_argument("--token-env", default="MCP_GITHUB_TOKEN")
    ap.add_argument("--owner", default="octocat")
    ap.add_argument("--repo", default="hello-world")
    ap.add_argument("--issue", type=int, default=1)
    ap.add_argument("--results", default=str(OUT / "results.jsonl"))
    ap.add_argument("--rescore", action="store_true", help="re-apply relabel() to an existing results file; no processes, no claude calls")
    args = ap.parse_args()
    if args.rescore:
        rows = [relabel(json.loads(x)) for x in Path(args.results).read_text(encoding="utf-8").splitlines() if x.strip()]
        Path(args.results).write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), encoding="utf-8")
        print(summarize(rows))
        return

    plan = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))
    chosen = set(args.profiles.split(",")) if args.profiles else None
    cases = [c for c in plan["profiles"] if chosen is None or c["id"] in chosen]
    for port in (PORT_HEALER, PORT_SHIM) + (() if args.live else (PORT_UP,)):
        if port_open(port):
            sys.exit(f"port {port} already in use; stop whatever holds it first")
    OUT.mkdir(exist_ok=True)
    for f in ("shim_calls.jsonl", "upstream_calls.jsonl"):
        (OUT / f).unlink(missing_ok=True)
    cases_sha = hashlib.sha256((HERE / "cases.yaml").read_bytes()).hexdigest()[:16]
    py = sys.executable
    all_rows: list[dict] = []
    budget = {"used": 0}
    try:
        if args.live:
            shim_argv = [py, str(HERE / "shim.py"), "--upstream-url", args.upstream_url, "--token-env", args.token_env]
        else:
            up = spawn("fake_upstream", [py, str(HERE / "fake_upstream.py"), "--port", str(PORT_UP)])
            wait_port(PORT_UP, up)
            shim_argv = [py, str(HERE / "shim.py"), "--upstream-url", f"http://127.0.0.1:{PORT_UP}/mcp"]
        shim = spawn("shim", shim_argv, {"CONNECTIONS_ALLOWED_ORIGINS": ""})
        wait_port(PORT_SHIM, shim)
        control("real")
        P.load_real_schemas(asyncio.run(list_tools(PORT_SHIM)))
        with open(args.results, "w", encoding="utf-8") as f:
            f.write(json.dumps({"kind": "meta", "cases_sha256_16": cases_sha, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "live": args.live}) + "\n")
            for case in cases:
                try:
                    rows = run_profile(case, plan, args, budget)
                except Exception as e:  # noqa: BLE001
                    rows = [{"kind": "harness_error", "profile": case["id"], "error": f"{type(e).__name__}: {e}"[:500]}]
                    print("  harness error:", rows[0]["error"], flush=True)
                f.writelines(json.dumps(r, default=str) + "\n" for r in rows)
                f.flush()
                all_rows += rows
        summary = summarize(all_rows)
        append_chaos_report(
            HERE.parents[2] / "REPORT.md",
            summary,
            mode="live" if args.live else "offline",
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
            profile_count=len(cases),
            row_count=len(all_rows),
            claude_calls=budget["used"],
        )
        print(summary)
        print("claude calls used:", budget["used"])
    finally:
        kill_all()


if __name__ == "__main__":
    main()
