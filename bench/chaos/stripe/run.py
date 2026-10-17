"""Stripe-slice chaos (Prism, fake key, no real Stripe). No LLM. Usage: python bench/chaos/stripe/run.py"""

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
RESULTS = PROOF / "results.jsonl"
FXLOG = PROOF / "prism_requests.jsonl"
P_PRISM, P_FIX, P_HEAL = 4011, 4070, 8103
ORIGIN = f"http://127.0.0.1:{P_FIX}"
OLD, NEW = HERE / "slice.v1000.json", HERE / "slice.new.json"
FAKE_KEY = "sk_test_chaos_fake_not_a_real_key"  # loopback Prism only


def control(**body) -> None:
    req = urllib.request.Request(f"{ORIGIN}/__control", data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


async def main() -> None:
    cases = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    PROOF.mkdir(exist_ok=True)
    cfg = PROOF / "servers.json"
    cfg.write_text(json.dumps({"apis": [{
        "name": "stripe", "kind": "openapi", "base_url": ORIGIN, "spec_url": f"{ORIGIN}/__spec.json",
        "selected_operations": "*", "auth": {"type": "bearer", "token_env": "API_STRIPE_TEST_KEY"}}]}), encoding="utf-8")
    fx = lib.spawn("fixture", [lib.sys.executable, str(HERE.parent / "fixture.py"), "--port", str(P_FIX), "--upstream",
                              f"http://127.0.0.1:{P_PRISM}", "--log", str(FXLOG), "--spec-file", str(OLD)], LOGS)
    prism = None
    try:
        lib.wait_port(P_FIX, fx)
        prism = lib.spawn("prism", ["npx", "-y", "@stoplight/prism-cli@5", "mock", "-p", str(P_PRISM), "-h", "127.0.0.1", "-d", str(NEW)], LOGS)
        t0 = time.time()
        try:
            lib.start_healer(LOGS, PROOF / "run.db", cfg, P_HEAL, [ORIGIN], name="healer", timeout=120,
                                      env_extra={"API_STRIPE_TEST_KEY": FAKE_KEY})
        except RuntimeError as e:
            p = next((x for x in lib.procs if getattr(x, "chaos_name", "") == "healer"), None)
            alive = p is not None and p.poll() is None
            for c in cases:
                r = {"case": c["id"], "expected": c["expected"], "observed": "startup_hang" if alive else "startup_abort",
                     "verdict": "HUNG" if alive else "CRASH", "why": f"gateway did not open its port in 120 s ({e}); process alive={alive}; "
                     "cause: healer.openapi_loader.resolve_refs inlines the Stripe slice without memoisation (see loader_probe_output.txt)",
                     "run": "main"}
                lib.jl(RESULTS, r)
                print(f"== {c['id']} -> {r['observed']} {r['verdict']}", flush=True)
            return
        startup_s = round(time.time() - t0, 1)
        audit = lib.Audit(PROOF / "run.db")
        async with lib.Front(P_HEAL) as front:
            names = [t["name"] for t in await front.tools()]
            lib.jl(PROOF / "tools_exposed.jsonl", {"startup_s": startup_s, "tools": names})
            control(spec_file=str(NEW))
            lib.wait_port(P_PRISM, prism, 120)
            time.sleep(1.5)  # noqa: ASYNC251
            for c in cases:
                print(f"== {c['id']} (expect {c['expected']})", flush=True)
                if c["kind"] == "discovery":
                    present = f"stripe__{c['op']}" in names
                    obs = "exposed" if present else "not_exposed"
                    r = {"case": c["id"], "expected": c["expected"], "observed": obs,
                         "verdict": "PASS" if obs == c["expected"] else "FAIL", "tools_exposed": names, "startup_s": startup_s}
                else:
                    f0, h0 = lib.line_count(FXLOG), audit.max_heal_id()
                    if f"stripe__{c['tool']}" not in names:
                        r = {"case": c["id"], "expected": c["expected"], "observed": "tool_not_exposed", "verdict": "FAIL"}
                    else:
                        out = await front.call(f"stripe__{c['tool']}", c["args"], 60)
                        reqs = [x for x in lib.read_jsonl(FXLOG, f0) if x.get("kind") == "req"]
                        heals = audit.heals_after(h0)
                        err = bool(out["is_error"]) or (isinstance(out["result"], dict) and "error" in out["result"])
                        ok = [x for x in reqs if x["status"] < 300]
                        good = bool(ok) and ok[-1]["path"] == "/v1/customers/cus_chaos_1" and not err
                        obs = "pass_through" if (good and not heals) else ("heal" if good else "error")
                        r = {"case": c["id"], "expected": c["expected"], "observed": obs,
                             "verdict": "PASS" if obs == c["expected"] else ("CRASH" if out["exc"] else "FAIL"),
                             "agent_result": lib.short(out["result"], 300),
                             "prism": [{k: x.get(k) for k in ("method", "path", "query", "status")} for x in reqs],
                             "audit": [{k: h.get(k) for k in ("tier", "outcome", "reason")} for h in heals],
                             "latency_ms": out["latency_ms"]}
                r["run"] = "main"
                lib.jl(RESULTS, r)
                print(f"   -> {r['observed']} {r['verdict']}", flush=True)
    finally:
        lib.kill_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        lib.kill_all()
