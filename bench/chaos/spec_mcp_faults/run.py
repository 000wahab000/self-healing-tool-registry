"""Spec / upstream-MCP / restart chaos. No LLM. Usage: python bench/chaos/spec_mcp_faults/run.py [case_id ...]"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lib

PROOF = HERE / "proof"
LOGS = PROOF / "logs"
DB = PROOF / "run.db"
RESULTS = PROOF / "results.jsonl"
APILOG = PROOF / "strict_api_requests.jsonl"
P_API, P_HEAL, P_DRIFT, P_BIZ = 4050, 8100, 8120, 8121
O_API = f"http://127.0.0.1:{P_API}"
PY = lib.sys.executable


def api_control(**body) -> dict:
    req = urllib.request.Request(O_API + "/__control", data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def rest_cfg(name="rest") -> Path:
    p = PROOF / f"servers_{name}.json"
    p.write_text(json.dumps({"apis": [{"name": "wid", "kind": "openapi", "base_url": O_API, "spec_path": "/openapi.json",
                                       "selected_operations": ["searchWidgets", "health"]}]}), encoding="utf-8")
    return p


def mcp_cfg(name: str, url: str, sel: list[str]) -> Path:
    p = PROOF / f"servers_{name}.json"
    p.write_text(json.dumps({"servers": [{"name": name, "transport": "http", "url": url, "selected_operations": sel}]}),
                 encoding="utf-8")
    return p


def start_api(shape="v1", kind="v1"):
    (PROOF).mkdir(exist_ok=True)
    p = lib.spawn("strict_api", [PY, str(HERE / "strict_api.py"), "--port", str(P_API), "--log", str(APILOG),
                                 "--shape", shape, "--spec-kind", kind], LOGS)
    lib.wait_port(P_API, p)
    return p


def is_err(out: dict) -> bool:
    r = out["result"]
    return bool(out["is_error"]) or (isinstance(r, dict) and "error" in r)


def audit_view(heals):
    return [{k: h.get(k) for k in ("tier", "path", "outcome", "reason", "raw_code", "class", "request_ops", "mttr_ms")} for h in heals]


async def wid_call(front, args=None, timeout=60):
    return await front.call("wid__searchWidgets", args or {"q": "hello"}, timeout)


def api_reqs(f0):
    return [r for r in lib.read_jsonl(APILOG, f0) if r.get("kind") == "req"]


async def case_rest(c: dict) -> dict:
    api = start_api()
    healer = None
    try:
        healer = lib.start_healer(LOGS, DB, rest_cfg(), P_HEAL, [O_API], name=f"healer_{c['id']}")
        audit = lib.Audit(DB)
        async with lib.Front(P_HEAL) as front:
            spec = c.get("spec", {})
            ctl = {"shape": "v2", "spec_kind": "cyclic_v2" if spec.get("cyclic") else "v2"}
            if "status" in spec:
                ctl["spec_status"] = spec["status"]
            if "raw" in spec:
                ctl["spec_raw"] = spec["raw"]
            api_control(**ctl)
            h0, f0 = audit.max_heal_id(), lib.line_count(APILOG)
            out = await wid_call(front)
            reqs = api_reqs(f0)
            heals = audit.heals_after(h0)
            health = await front.call("wid__health", {}, 20)
            alive = health["exc"] is None and not health["is_error"]
        ok200 = [r for r in reqs if r["status"] == 200]
        recovered = any(h["outcome"] == "RECOVERED" for h in heals)
        if out["exc"]:
            obs = "hung" if out["exc"].startswith("HUNG") else "crashed"
        elif not alive:
            obs = "crashed"
        elif ok200:
            q = ok200[-1]["query"]
            good = q.get("query") == "hello" and set(q) <= {"query"}
            obs = ("heal_correct" if recovered else "pass_through") if good else "wrong"
        elif heals:
            obs = "refused"
        else:
            obs = "structured_error_no_audit" if is_err(out) else "unexpected"
        exp = c["expected"]
        if obs in ("hung", "crashed", "wrong"):
            v = {"hung": "HUNG", "crashed": "CRASH", "wrong": "FALSE_PATCH"}[obs]
        elif exp == "refuse_or_clue":
            v = "PASS" if obs in ("heal_correct", "refused", "structured_error_no_audit") else "FAIL"
        elif exp == "refuse":
            v = "PASS" if obs in ("refused", "structured_error_no_audit") else "FAIL"
        else:
            v = "FAIL"
        if c.get("max_latency_ms") and out["latency_ms"] > c["max_latency_ms"]:
            v = "FAIL"
        return {"case": c["id"], "expected": exp, "observed": obs, "verdict": v, "latency_ms": out["latency_ms"],
                "has_audit_row": bool(heals), "audit": audit_view(heals), "agent_result": lib.short(out["result"], 400),
                "upstream_requests": [{"query": r["query"], "status": r["status"]} for r in reqs],
                "gateway_alive_after": alive}
    finally:
        if healer:
            lib.kill(healer)
        lib.kill(api)
        lib.wait_closed(P_API)
        lib.wait_closed(P_HEAL)


def spawn_healer_raw(name: str, cfg: Path, port: int, origins: list[str], db: Path | None = None):
    return lib.spawn(f"healer_{name}", [PY, "-m", "healer.mcp_server", "--transport", "http", "--no-rest", "--host", "127.0.0.1",
                                        "--port", str(port), "--no-repair", "--mcp-servers", str(cfg), "--db", str(db or (PROOF / f"{name}.db"))],
                     LOGS, {"CONNECTIONS_ALLOWED_ORIGINS": ",".join(origins)})


async def case_startup(c: dict) -> dict:
    cyc = c["kind"] == "startup_cyclic"
    api = start_api("v1", "cyclic_v1" if cyc else "v1")
    if not cyc:
        api_control(spec_raw=c["spec"]["raw"])
    p = spawn_healer_raw(c["id"], rest_cfg(c["id"]), P_HEAL, [O_API])
    try:
        t0, up = time.time(), False
        while time.time() - t0 < 40:
            if p.poll() is not None:
                break
            if lib.port_open(P_HEAL):
                up = True
                break
            time.sleep(0.3)  # noqa: ASYNC251
        res = {"case": c["id"], "expected": c["expected"], "startup_s": round(time.time() - t0, 1)}
        if not up:
            tail = (LOGS / f"healer_{c['id']}.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
            hung = p.poll() is None
            return {**res, "observed": "startup_hang" if hung else "startup_abort", "verdict": "HUNG" if hung else
                    ("PASS(clear failure)" if not cyc else "FAIL"), "why": f"exit={p.poll()} log tail: {' | '.join(tail)[:300]}",
                    "gateway_alive_after": False}
        async with lib.Front(P_HEAL) as front:
            names = [t["name"] for t in await front.tools()]
            out = await wid_call(front) if "wid__searchWidgets" in names else None
        ok = out is not None and not is_err(out)
        return {**res, "observed": "started_call_ok" if ok else ("started_tool_skipped" if out is None else "started_call_error"),
                "verdict": "PASS" if (ok or not cyc) else "FAIL", "tools": names,
                "agent_result": lib.short(out["result"], 300) if out else None, "gateway_alive_after": True,
                "why": "invalid spec at startup did not prevent startup" if not cyc else ""}
    finally:
        lib.kill(p)
        lib.kill(api)
        lib.wait_closed(P_API)
        lib.wait_closed(P_HEAL)


def start_drift():
    p = lib.spawn("drift_mcp", [PY, "-m", "mock_api.mcp_drift_server", "--profile", "users", "--transport", "http",
                                "--port", str(P_DRIFT)], LOGS)
    lib.wait_port(P_DRIFT, p)
    return p


async def case_mcp(c: dict) -> dict:
    kind = c["kind"]
    procs_ = []
    healer = None
    try:
        if kind in ("mcp_kill", "mcp_drift", "mcp_notfound"):
            drift = start_drift()
            procs_.append(drift)
            cfg = mcp_cfg("users", f"http://127.0.0.1:{P_DRIFT}/mcp", ["get_user", "update_email"])
            origins = [f"http://127.0.0.1:{P_DRIFT}"]
        else:
            biz = lib.spawn("bizmcp", [PY, str(HERE / "bizmcp.py"), "--port", str(P_BIZ), "--log", str(PROOF / "bizmcp_calls.jsonl")], LOGS)
            lib.wait_port(P_BIZ, biz)
            procs_.append(biz)
            cfg = mcp_cfg("biz", f"http://127.0.0.1:{P_BIZ}/mcp", ["lookup", "boom"])
            origins = [f"http://127.0.0.1:{P_BIZ}"]
        healer = lib.start_healer(LOGS, DB, cfg, P_HEAL, origins, name=f"healer_{c['id']}")
        audit = lib.Audit(DB)
        steps: list[dict] = []
        async with lib.Front(P_HEAL) as front:
            res: dict = {"case": c["id"], "expected": c["expected"]}
            if kind == "mcp_kill":
                base = await front.call("users__get_user", {"user_id": "123"}, 30)
                steps.append({"step": "baseline", "ok": not is_err(base), "r": lib.short(base["result"], 150)})
                lib.kill(drift)
                lib.wait_closed(P_DRIFT)
                down = await front.call("users__get_user", {"user_id": "123"}, 60)
                steps.append({"step": "after_kill", "err": is_err(down), "exc": down["exc"], "ms": down["latency_ms"], "r": lib.short(down["result"], 200)})
                listed = await front.tools()
                steps.append({"step": "tools_list_while_down", "n": len(listed)})
                drift2 = start_drift()
                procs_.append(drift2)
                time.sleep(1.0)  # noqa: ASYNC251
                rec = []
                for i in range(3):
                    o = await front.call("users__get_user", {"user_id": "123"}, 40)
                    rec.append({"try": i, "ok": not is_err(o) and not o["exc"], "ms": o["latency_ms"], "exc": o["exc"], "r": lib.short(o["result"], 200)})
                    if rec[-1]["ok"]:
                        break
                    await asyncio.sleep(3)
                steps += [{"step": "after_restart", **x} for x in rec]
                bad = down["exc"] or not is_err(down)
                recovered = rec[-1]["ok"]
                res.update(observed="recovered" if recovered else "not_recovered",
                           verdict=("HUNG" if (down["exc"] or "").startswith("HUNG") else "CRASH" if bad else ("PASS" if recovered else "FAIL")),
                           why=f"recovered_after_try={len(rec)}" if recovered else "calls still failing 3 tries (~9 s) after upstream restart")
            elif kind == "mcp_drift":
                async with lib.Front(P_DRIFT) as adm:
                    a = await adm.call("__admin_apply", {"name": c["mutation"]}, 20)
                steps.append({"step": "admin_apply", "r": lib.short(a["result"], 150)})
                h0 = audit.max_heal_id()
                out = await front.call("users__get_user", {"user_id": "123"}, 60)
                heals = audit.heals_after(h0)
                r = out["result"]
                ok = isinstance(r, dict) and r.get("name") == "Ada" and not out["is_error"]
                rec = any(h["outcome"] == "RECOVERED" for h in heals)
                obs = ("heal_correct" if rec else "pass_through") if ok else ("hung" if (out["exc"] or "").startswith("HUNG") else "crashed" if out["exc"] else "refused" if heals else "structured_error_no_audit")
                if ok and not isinstance(r, dict):
                    obs = "wrong"
                exp = c["expected"]
                good = (obs == "heal_correct") if exp == "heal" else obs in ("heal_correct", "refused", "structured_error_no_audit")
                res.update(observed=obs, verdict="PASS" if good else {"hung": "HUNG", "crashed": "CRASH"}.get(obs, "FAIL"),
                           audit=audit_view(heals), agent_result=lib.short(r, 300), latency_ms=out["latency_ms"])
            elif kind == "mcp_notfound":
                h0 = audit.max_heal_id()
                out = await front.call("users__get_user", {"user_id": "999"}, 60)
                heals = audit.heals_after(h0)
                text = json.dumps(out["result"])
                rec = any(h["outcome"] == "RECOVERED" for h in heals)
                shows = "not found" in text.lower()
                obs = "pass_through" if (is_err(out) and shows and not rec) else "other"
                res.update(observed=obs, verdict="PASS" if obs == "pass_through" else ("FAIL" if not out["exc"] else "CRASH"),
                           audit=audit_view(heals), agent_result=lib.short(out["result"], 300), latency_ms=out["latency_ms"],
                           why=f"audit rows={[(h['outcome']) for h in heals]}" if obs == "pass_through" else f"JSON-RPC -32602 'User not found' triggered {len(heals)} audit row(s); error shown to caller={shows}")
            else:  # mcp_biz
                h0 = audit.max_heal_id()
                call = c["call"]
                out = await front.call(f"biz__{call['tool']}", call["args"], 60)
                heals = audit.heals_after(h0)
                text = json.dumps(out["result"])
                rec = any(h["outcome"] == "RECOVERED" for h in heals)
                again = await front.call("biz__lookup", {"item_id": "fine"}, 20)
                alive = again["exc"] is None and not is_err(again)
                if c["id"].startswith("M4"):
                    good = bool(out["is_error"]) and ("not found" in text.lower() or "not_found" in text.lower()) and not rec
                    obs = "pass_through" if good else "other"
                else:
                    good = is_err(out) and not rec and not out["exc"]
                    obs = "structured_error" if good else "other"
                res.update(observed=obs, verdict="PASS" if (good and alive) else "FAIL", audit=audit_view(heals),
                           agent_result=lib.short(out["result"], 300), is_error=out["is_error"], gateway_alive_after=alive,
                           latency_ms=out["latency_ms"])
        res["steps"] = steps
        return res
    finally:
        if healer:
            lib.kill(healer)
        for p in procs_:
            lib.kill(p)
        for port in (P_HEAL, P_DRIFT, P_BIZ):
            lib.wait_closed(port)


async def case_kill(c: dict) -> dict:
    drift = start_drift()
    healer = None
    steps: list[dict] = []
    try:
        cfg = mcp_cfg("users", f"http://127.0.0.1:{P_DRIFT}/mcp", ["get_user", "update_email"])
        healer = lib.start_healer(LOGS, DB, cfg, P_HEAL, [f"http://127.0.0.1:{P_DRIFT}"], name="healer_M1")
        res: dict = {"case": c["id"], "expected": c["expected"]}
        try:
            async with lib.Front(P_HEAL) as front:
                base = await front.call("users__get_user", {"user_id": "123"}, 30)
                steps.append({"step": "baseline", "ok": not is_err(base)})
                lib.kill(drift)
                lib.wait_closed(P_DRIFT)
                t_kill = time.time()
                down = await front.call("users__get_user", {"user_id": "123"}, 60)
                steps.append({"step": "call_after_kill", "err": is_err(down), "exc": down["exc"], "ms": down["latency_ms"],
                              "r": lib.short(down["result"], 200), "gateway_exit_code": healer.poll()})
                died = None
                for _ in range(20):  # watch the gateway for ~10 s
                    if healer.poll() is not None:
                        died = round(time.time() - t_kill, 1)
                        break
                    await asyncio.sleep(0.5)
                steps.append({"step": "gateway_watch_10s", "gateway_exit_code": healer.poll(), "died_after_s": died})
                if died is None:
                    start_drift()
                    time.sleep(1.0)  # noqa: ASYNC251
                    rec = []
                    for i in range(3):
                        o = await front.call("users__get_user", {"user_id": "123"}, 40)
                        rec.append({"step": "after_restart", "try": i, "ok": not is_err(o) and not o["exc"], "ms": o["latency_ms"], "r": lib.short(o["result"], 200)})
                        if rec[-1]["ok"]:
                            break
                        await asyncio.sleep(3)
                    steps += rec
        except BaseException as e:  # noqa: BLE001
            steps.append({"step": "client_exception", "type": type(e).__name__, "gateway_exit_code": healer.poll()})
        crashed = healer.poll() is not None
        recovered = any(s.get("ok") and s.get("step") == "after_restart" for s in steps)
        res.update(observed="gateway_crashed" if crashed else ("recovered" if recovered else "not_recovered"),
                   verdict="CRASH" if crashed else ("PASS" if recovered else "FAIL"), steps=steps,
                   why=(f"gateway process exited (code {healer.poll()}) after the upstream HTTP MCP died; first call after kill returned a structured E1 error"
                        if crashed else ""))
        return res
    finally:
        if healer:
            lib.kill(healer)
        lib.kill_all()
        for port in (P_HEAL, P_DRIFT):
            lib.wait_closed(port)


async def case_restart(c: dict) -> dict:
    api = start_api()
    healer = None
    try:
        healer = lib.start_healer(LOGS, DB, rest_cfg(), P_HEAL, [O_API], name="healer_R1_a")
        audit = lib.Audit(DB)
        steps = []
        async with lib.Front(P_HEAL) as front:
            api_control(shape="v2", spec_kind="v2")
            h0 = audit.max_heal_id()
            first = await wid_call(front)
            h1 = audit.heals_after(h0)
            steps.append({"step": "first_call_before_restart", "ok": not is_err(first), "audit": audit_view(h1), "r": lib.short(first["result"], 150)})
        lib.kill(healer)
        lib.wait_closed(P_HEAL)
        healer = lib.start_healer(LOGS, DB, rest_cfg(), P_HEAL, [O_API], keep_db=True, name="healer_R1_b")
        async with lib.Front(P_HEAL) as front:
            tools = await front.tools()
            schema = next((t["inputSchema"].get("properties", {}) for t in tools if t["name"] == "wid__searchWidgets"), None)
            steps.append({"step": "frozen_schema_after_restart", "props": list(schema or {})})
            h2 = audit.max_heal_id()
            second = await wid_call(front)
            h3 = audit.heals_after(h2)
            third = await front.call("wid__searchWidgets", {"query": "hello"}, 30)
        ok2 = not is_err(second)
        tier0 = any(h["tier"] == 0 for h in h3)
        steps.append({"step": "old_args_after_restart", "ok": ok2, "audit": audit_view(h3), "r": lib.short(second["result"], 250)})
        steps.append({"step": "new_args_after_restart", "ok": not is_err(third), "r": lib.short(third["result"], 150)})
        if ok2 and tier0:
            obs, v = "tier0_served", "PASS"
        elif ok2:
            obs, v = "served_not_tier0", "FAIL"
        else:
            obs, v = "old_args_rejected_after_restart", "FAIL"
        return {"case": c["id"], "expected": c["expected"], "observed": obs, "verdict": v, "steps": steps,
                "why": "" if v == "PASS" else "old-schema agent call after a gateway restart was not served by the stored fix"}
    finally:
        if healer:
            lib.kill(healer)
        lib.kill(api)
        lib.wait_closed(P_API)
        lib.wait_closed(P_HEAL)


async def case_concurrent(c: dict) -> dict:
    api = start_api()
    healer = None
    try:
        healer = lib.start_healer(LOGS, DB, rest_cfg(), P_HEAL, [O_API], name="healer_R3")
        audit = lib.Audit(DB)
        async with lib.Front(P_HEAL) as front:
            api_control(shape="v2", spec_kind="v2")
            h0, f0 = audit.max_heal_id(), lib.line_count(APILOG)
            outs = await asyncio.gather(*[wid_call(front) for _ in range(c["n"])])
            await asyncio.sleep(0.3)
            heals = audit.heals_after(h0)
            reqs = api_reqs(f0)
        ok_calls = sum(1 for o in outs if not is_err(o) and not o["exc"])
        ok200 = [r for r in reqs if r["status"] == 200 and r["query"].get("query") == "hello"]
        rows = len(heals)
        good = rows == 1 and ok_calls == c["n"] and len(ok200) >= c["n"]
        return {"case": c["id"], "expected": c["expected"], "observed": "single_flight" if good else f"audit_rows={rows},ok_calls={ok_calls}/{c['n']}",
                "verdict": "PASS" if good else ("CRASH" if any(o["exc"] for o in outs) else "FAIL"),
                "audit": audit_view(heals), "upstream_ok_requests": len(ok200), "upstream_rejected": sum(1 for r in reqs if r["status"] != 200),
                "latencies_ms": [o["latency_ms"] for o in outs]}
    finally:
        if healer:
            lib.kill(healer)
        lib.kill(api)
        lib.wait_closed(P_API)
        lib.wait_closed(P_HEAL)


async def main(only: list[str]) -> None:
    cases = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    if only:
        cases = [c for c in cases if c["id"] in only]
    PROOF.mkdir(exist_ok=True)
    try:
        for c in cases:
            print(f"== {c['id']} (expect {c['expected']})", flush=True)
            k = c["kind"]
            fn = {"rest": case_rest, "startup": case_startup, "startup_cyclic": case_startup, "rest_restart": case_restart,
                  "rest_concurrent": case_concurrent, "mcp_kill": case_kill}.get(k, case_mcp)
            try:
                r = await asyncio.wait_for(fn(c), 200)
            except Exception as e:  # noqa: BLE001
                r = {"case": c["id"], "expected": c["expected"], "observed": "crashed", "verdict": "CRASH",
                     "why": f"harness/case exception {type(e).__name__}: {e}"[:300]}
            lib.jl(RESULTS, r)
            print(f"   -> {r['observed']} {r['verdict']} {r.get('why') or ''}"[:220], flush=True)
            lib.kill_all()
    finally:
        lib.kill_all()


if __name__ == "__main__":
    try:
        asyncio.run(main(sys.argv[1:]))
    finally:
        lib.kill_all()
