"""Transport-fault chaos. No LLM. Usage: python bench/chaos/faults/run.py [case_id ...]"""

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
FLOG = PROOF / "fault_requests.jsonl"
P_FAULT, P_HEAL = 4030, 8098
ORIGIN = f"http://127.0.0.1:{P_FAULT}"


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(ORIGIN + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def state() -> dict:
    with urllib.request.urlopen(ORIGIN + "/__state", timeout=10) as r:
        return json.loads(r.read())


def servers_json(blocked_url: str | None, name: str) -> Path:
    apis = [{"name": "flt", "kind": "openapi", "base_url": ORIGIN, "spec_path": "/openapi.json",
             "selected_operations": ["getItem", "createItem", "health"]}]
    if blocked_url:
        apis.append({"name": "blk", "kind": "openapi", "base_url": blocked_url, "spec_path": "/openapi.json",
                     "selected_operations": ["getItem"]})
    p = PROOF / f"servers_{name}.json"
    p.write_text(json.dumps({"apis": apis}, indent=1), encoding="utf-8")
    return p


async def run_fault(case: dict, front: lib.Front, audit: lib.Audit) -> dict:
    post("/__mode", case["mode"])
    h0 = audit.max_heal_id()
    lib.line_count(FLOG)
    out = await front.call(f"flt__{case['call']['tool']}", case["call"]["args"], 60)
    st = state()
    health = await front.call("flt__health", {}, 20)
    await asyncio.sleep(0.2)
    heals = audit.heals_after(h0)
    arr = st["arrivals"]
    gap = round(arr[1] - arr[0], 2) if len(arr) > 1 else None
    res = out["result"]
    is_err = bool(out["is_error"]) or (isinstance(res, dict) and "error" in res)
    alive = health["exc"] is None and not health["is_error"]
    exp = case["expected"]
    ok, why = False, ""
    if out["exc"]:
        obs = "hung" if out["exc"].startswith("HUNG") else "crashed"
        why = out["exc"]
    elif not alive:
        obs, why = "crashed", f"gateway health call failed after: {lib.short(health, 200)}"
    elif exp == "retry_success":
        if not is_err and st["seen"] >= 2:
            obs = "retried_success"
            ok = case.get("min_gap_s") is None or (gap is not None and gap >= case["min_gap_s"])
            if not ok:
                obs, why = "retried_too_soon", f"gap {gap}s < required {case['min_gap_s']}s"
            elif heals:
                ok, obs, why = False, "unexpected_heal", "audit row written for a transport fault"
        else:
            obs, why = ("success_no_retry" if not is_err else "error"), f"seen={st['seen']} result={lib.short(res, 200)}"
    elif exp == "structured_error":
        obs = "structured_error" if is_err else "unexpected_success"
        ok = is_err and st["seen"] <= 4 and not any(h["outcome"] == "RECOVERED" for h in heals)
        if is_err and st["seen"] > 4:
            obs, why = "too_many_attempts", f"seen={st['seen']}"
        if heals:
            why += f" audit={[(h['outcome'], h['reason']) for h in heals]}"
    elif exp == "no_replay":
        obs = f"saved_writes={st['saved']}"
        ok = st["saved"] == 1
        why = f"attempts={st['seen']} result={lib.short(res, 160)}"
    elif exp == "bounded":
        ok = out["latency_ms"] < 30000
        obs = "bounded_error" if is_err else "bounded_success"
        why = f"latency {out['latency_ms']} ms, result={lib.short(res, 160)}"
    else:
        obs = "?"
    if ok and exp == "retry_success":
        obs = "retried_success"
    return {"case": case["id"], "expected": exp, "observed": obs, "why": why,
            "verdict": "PASS" if ok else ("CRASH" if obs == "crashed" else "HUNG" if obs == "hung" else "FAIL"),
            "attempts_at_server": st["seen"], "gap_between_attempts_s": gap, "saved_writes": st["saved"],
            "latency_ms": out["latency_ms"], "agent_result": lib.short(res, 400), "is_error": out["is_error"],
            "audit": [{k: h.get(k) for k in ("tier", "outcome", "reason", "raw_code", "class")} for h in heals],
            "gateway_alive_after": alive}


def run_startup(case: dict) -> dict:
    st = case["startup"]
    name = case["id"]
    cfg = servers_json(st.get("base_url") or "http://127.0.0.1:4031", name)
    origins = [ORIGIN] if not st.get("origin_allowlisted", False) else [ORIGIN, st.get("base_url") or "http://127.0.0.1:4031"]
    t0 = time.time()
    p = lib.spawn(f"healer_{name}", [lib.sys.executable, "-m", "healer.mcp_server", "--transport", "http", "--no-rest",
                                     "--host", "127.0.0.1", "--port", "8099", "--no-repair", "--mcp-servers", str(cfg),
                                     "--db", str(PROOF / f"{name}.db")], LOGS,
                  {"CONNECTIONS_ALLOWED_ORIGINS": ",".join(origins)})
    try:
        up = False
        while time.time() - t0 < 30:
            if p.poll() is not None:
                break
            if lib.port_open(8099):
                up = True
                break
            time.sleep(0.3)
        tools: list[str] = []
        if up:
            async def go():
                async with lib.Front(8099) as f:
                    return [t["name"] for t in await f.tools()]
            tools = asyncio.run(go())
        exit_code = p.poll()
        tail = (LOGS / f"healer_{name}.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
        if up and "flt__getItem" in tools and not any(t.startswith("blk__") for t in tools):
            obs, verdict, why = "blocked_api_skipped_gateway_up", "PASS", f"tools={tools}"
        elif up and any(t.startswith("blk__") for t in tools):
            obs, verdict, why = "blocked_api_exposed", "FALSE_PATCH", f"tools={tools}"
        elif not up:
            obs, verdict, why = "startup_abort", "FAIL", f"healer exited code={exit_code}; log tail: {' | '.join(tail)[:300]}"
        else:
            obs, verdict, why = "other", "FAIL", f"tools={tools}"
        return {"case": name, "expected": case["expected"], "observed": obs, "verdict": verdict, "why": why,
                "gateway_alive_after": up, "latency_ms": int((time.time() - t0) * 1000)}
    finally:
        lib.kill(p)


async def main(only: list[str]) -> None:
    cases = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    if only:
        cases = [c for c in cases if c["id"] in only]
    PROOF.mkdir(exist_ok=True)
    fs = lib.spawn("fault_server", [lib.sys.executable, str(HERE / "fault_server.py"), "--port", str(P_FAULT), "--log", str(FLOG)], LOGS)
    try:
        lib.wait_port(P_FAULT, fs)
        healer = lib.start_healer(LOGS, DB, servers_json(None, "main"), P_HEAL, [ORIGIN], name="healer_main")
        audit = lib.Audit(DB)
        try:
            async with lib.Front(P_HEAL) as front:
                for c in cases:
                    if "startup" in c:
                        continue
                    print(f"== {c['id']} (expect {c['expected']})", flush=True)
                    try:
                        r = await asyncio.wait_for(run_fault(c, front, audit), 120)
                    except Exception as e:  # noqa: BLE001
                        r = {"case": c["id"], "expected": c["expected"], "observed": "crashed", "verdict": "CRASH",
                             "why": f"{type(e).__name__}: {e}"[:300]}
                    lib.jl(RESULTS, r)
                    print(f"   -> {r['observed']} {r['verdict']} {r.get('why') or ''}"[:220], flush=True)
        finally:
            lib.kill(healer)
        for c in cases:
            if "startup" in c:
                print(f"== {c['id']} (expect {c['expected']})", flush=True)
                r = run_startup(c)
                lib.jl(RESULTS, r)
                print(f"   -> {r['observed']} {r['verdict']} {r.get('why') or ''}"[:220], flush=True)
    finally:
        lib.kill_all()


if __name__ == "__main__":
    try:
        asyncio.run(main(sys.argv[1:]))
    finally:
        lib.kill_all()
