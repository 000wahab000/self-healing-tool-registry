"""GraphQL chaos: live Countries baseline + local mock drift. No LLM. Usage: python bench/chaos/graphql/run.py [ids]"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lib

PROOF = HERE / "proof"
LOGS = PROOF / "logs"
RESULTS = PROOF / "results.jsonl"
P_LOCAL, P_HEAL = 4060, 8102
LIVE = "https://countries.trevorblades.com"


def oracle(q: str) -> dict:
    r = httpx.post(f"{LIVE}/graphql", json={"query": q}, timeout=20)
    return r.json()


def cfg(kind: str) -> Path:
    if kind == "live":
        api = {"name": "ctry", "kind": "graphql", "base_url": LIVE, "spec_path": "/graphql"}
    else:
        api = {"name": "loc", "kind": "graphql", "base_url": f"http://127.0.0.1:{P_LOCAL}", "spec_path": "/graphql",
               "selected_operations": ["get_user"]}
    p = PROOF / f"servers_{kind}.json"
    p.write_text(json.dumps({"apis": [api]}), encoding="utf-8")
    return p


def set_mutation(name) -> None:
    req = urllib.request.Request(f"http://127.0.0.1:{P_LOCAL}/__mutation", data=json.dumps({"name": name}).encode(), method="POST")
    urllib.request.urlopen(req, timeout=10).read()


def has_value(res, needle) -> bool:
    return needle in json.dumps(res)


async def run_case(c: dict) -> dict:
    kind = c["kind"]
    local = None
    healer = None
    try:
        if kind == "local":
            local = lib.spawn("gql_local", [lib.sys.executable, str(HERE / "gql_local.py"), "--port", str(P_LOCAL)], LOGS)
            lib.wait_port(P_LOCAL, local)
        origins = [f"http://127.0.0.1:{P_LOCAL}"] if kind == "local" else []
        healer = lib.start_healer(LOGS, PROOF / f"{c['id']}.db", cfg(kind), P_HEAL, origins, name=f"healer_{c['id']}")
        audit = lib.Audit(PROOF / f"{c['id']}.db")
        prefix = "ctry__" if kind == "live" else "loc__"
        async with lib.Front(P_HEAL) as front:
            names = [t["name"] for t in await front.tools()]
            if kind == "local":
                set_mutation(c["mutation"])
            h0 = audit.max_heal_id()
            out = await front.call(prefix + c["tool"], c["args"], 60)
            heals = audit.heals_after(h0)
        res = out["result"]
        text = json.dumps(res)
        err = bool(out["is_error"]) or (isinstance(res, dict) and "error" in res)
        exp = c["expected"]
        orc = oracle(c["oracle"]["q"]) if c.get("oracle") else None
        rec = any(h["outcome"] == "RECOVERED" for h in heals)
        if out["exc"]:
            obs = "hung" if out["exc"].startswith("HUNG") else "crashed"
        elif exp == "arg_error":
            obs = "arg_error" if "AGENT_ARG_ERROR" in text else ("error" if err else "unexpected_success")
        elif err:
            obs = "error"
        elif kind == "local":
            obs = ("heal_correct" if rec else "pass_through") if "Ada" in text else "wrong"
        elif exp == "null_result":
            obs = "null_result" if (res in (None, {}) or has_value(res, "null")) else "other"
        else:
            data = orc["data"] if orc else {}
            key = next(iter(data))
            val = data[key]
            if c["oracle"].get("min_count"):
                n = len(res) if isinstance(res, list) else len(next(iter(res.values()), []) if isinstance(res, dict) else [])
                ok = n >= c["oracle"]["min_count"]
            else:
                ok = isinstance(val, dict) and all(has_value(res, str(v)) for v in val.values() if v)
            obs = "success" if ok else "wrong"
        want = {"heal": "heal_correct"}.get(exp, exp)
        if kind == "local" and exp == "success":
            want = "pass_through"
        verdict = "PASS" if obs == want else {"wrong": "FALSE_PATCH", "crashed": "CRASH", "hung": "HUNG"}.get(obs, "FAIL")
        return {"case": c["id"], "expected": exp, "observed": obs, "verdict": verdict, "agent_result": lib.short(res, 400),
                "audit": [{k: h.get(k) for k in ("tier", "outcome", "reason", "raw_code", "class")} for h in heals],
                "latency_ms": out["latency_ms"], "tools_exposed": names if c["id"] in ("G1_country_BR", "L0_local_baseline") else None,
                "oracle": lib.short(orc, 300) if orc else None}
    finally:
        if healer:
            lib.kill(healer)
        if local:
            lib.kill(local)
        lib.wait_closed(P_HEAL)
        lib.wait_closed(P_LOCAL)


async def main(only: list[str]) -> None:
    cases = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    if only:
        cases = [c for c in cases if c["id"] in only]
    PROOF.mkdir(exist_ok=True)
    try:
        for c in cases:
            print(f"== {c['id']} (expect {c['expected']})", flush=True)
            try:
                r = await asyncio.wait_for(run_case(c), 120)
            except Exception as e:  # noqa: BLE001
                r = {"case": c["id"], "expected": c["expected"], "observed": "crashed", "verdict": "CRASH",
                     "why": f"{type(e).__name__}: {e}"[:300]}
            lib.jl(RESULTS, r)
            print(f"   -> {r['observed']} {r['verdict']} {lib.short(r.get('agent_result'), 160)}", flush=True)
    finally:
        lib.kill_all()


if __name__ == "__main__":
    try:
        asyncio.run(main(sys.argv[1:]))
    finally:
        lib.kill_all()
