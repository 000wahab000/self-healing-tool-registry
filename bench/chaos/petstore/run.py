"""Petstore v3 + Prism drift chaos. No LLM. Usage: python bench/chaos/petstore/run.py [case_id ...]

Flow per case (see cases.yaml): spec server serves BASE; healer starts and freezes it; spec server and
Prism switch to the DRIFTED spec; one call with ORIGINAL args goes through the healer MCP front door;
the oracle is Prism's own validation + the request Prism received (logged by fixture.py).
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import lib

PROOF = HERE / "proof"
SPECS = PROOF / "specs"
LOGS = PROOF / "logs"
DB = PROOF / "run.db"
FXLOG = PROOF / "prism_requests.jsonl"
RESULTS = PROOF / "results.jsonl"
P_PRISM, P_FIX, P_HEAL = 4010, 4020, 8097
ORIGIN = f"http://127.0.0.1:{P_FIX}"


# ------------------------------------------------------------------ spec mutations
def base_spec() -> dict:
    s = json.loads((HERE / "openapi.orig.json").read_text(encoding="utf-8"))
    s.pop("security", None)
    for item in s["paths"].values():
        for op in item.values():
            if isinstance(op, dict):
                op.pop("security", None)
    s.get("components", {}).pop("securitySchemes", None)
    return s


def pet(s):  return s["components"]["schemas"]["Pet"]
def order(s): return s["components"]["schemas"]["Order"]
def user(s): return s["components"]["schemas"]["User"]
def opx(s, path, method): return s["paths"][path][method]


def rename_prop(schema: dict, old: str, new: str) -> None:
    schema["properties"] = {(new if k == old else k): v for k, v in schema["properties"].items()}
    schema["required"] = [new if r == old else r for r in schema.get("required", [])]


def add_required(schema: dict, name: str, prop: dict) -> None:
    schema["properties"][name] = prop
    schema["required"] = [*schema.get("required", []), name]


def m_D1(s): rename_prop(pet(s), "name", "petName")
def m_D1b(s):
    pin = copy.deepcopy(pet(s))
    rename_prop(pin, "name", "petName")
    s["components"]["schemas"]["PetIn"] = pin
    opx(s, "/pet", "post")["requestBody"]["content"]["application/json"]["schema"] = {"$ref": "#/components/schemas/PetIn"}


def m_D2(s):
    p = opx(s, "/pet/findByStatus", "get")["parameters"][0]
    p.update(name="state", required=True)
def m_D3(s):
    s["paths"]["/pet/{pet_id}"] = s["paths"].pop("/pet/{petId}")
    for o in s["paths"]["/pet/{pet_id}"].values():
        for p in o.get("parameters", []):
            if p["name"] == "petId":
                p["name"] = "pet_id"
def m_D4(s): s["paths"]["/v2/pet/{petId}"] = s["paths"].pop("/pet/{petId}")
def m_D5(s): user(s)["properties"]["phone"] = {"type": "integer", "format": "int64", "example": 12345}
def m_D7(s):
    sch = {"type": "object", "required": ["pet"], "properties": {"pet": {"$ref": "#/components/schemas/Pet"}}}
    opx(s, "/pet", "post")["requestBody"]["content"]["application/json"]["schema"] = sch
def m_D8(s): pass
def m_D9a(s): order(s)["properties"]["status"]["enum"] = ["PLACED", "APPROVED", "DELIVERED"]
def m_D9b(s): order(s)["properties"]["status"]["enum"] = ["ordered", "approved", "delivered"]
def m_D10(s): add_required(order(s), "channel", {"type": "string", "default": "web"})
def m_D11(s): add_required(order(s), "channel", {"type": "string"})
def m_D12(s):
    for p in opx(s, "/pet/{petId}", "delete")["parameters"]:
        if p["name"] == "api_key":
            p.update(name="X-Pet-Key", required=True)
def m_D13(s): s["paths"]["/pet"]["patch"] = s["paths"]["/pet"].pop("put")
def m_D14(s):
    out = copy.deepcopy(pet(s))
    rename_prop(out, "name", "petName")
    s["components"]["schemas"]["PetOut"] = out
    opx(s, "/pet/{petId}", "get")["responses"]["200"]["content"]["application/json"]["schema"] = {"$ref": "#/components/schemas/PetOut"}
def m_D15(s):
    pp = pet(s)
    pp["properties"].pop("name")
    pp["required"] = [r for r in pp["required"] if r != "name"]
    add_required(pp, "first_name", {"type": "string"})
    add_required(pp, "last_name", {"type": "string"})
def m_D16(s): order(s)["properties"]["quantity"]["description"] = "quantity in dozens (was: units)"
def m_D17(s):
    pr = order(s)["properties"]
    pr["id"]["description"], pr["petId"]["description"] = "id of the pet", "id of the order"
    pr["id"]["example"], pr["petId"]["example"] = 198772, 10
def m_D19(s):
    s["info"]["description"] = "Rewritten description."
    for item in s["paths"].values():
        for o in item.values():
            if isinstance(o, dict):
                o["summary"] = "Reworded summary"
                o["description"] = "Reworded description."
def m_NONE(s): pass
def m_B12(s):
    s.setdefault("components", {})["securitySchemes"] = {"api_key": {"type": "apiKey", "name": "api_key", "in": "header"}}
    opx(s, "/pet/{petId}", "get")["security"] = [{"api_key": []}]
def m_D12b(s): s["components"]["securitySchemes"]["api_key"]["name"] = "X-Pet-Key"
def m_D21(s):
    m_D1(s)
    add_required(pet(s), "source", {"type": "string", "default": "api"})


MUT = {k[2:]: v for k, v in globals().items() if k.startswith("m_")}


# ------------------------------------------------------------------ oracle checks (on the request Prism received)
def view(r: dict) -> dict:
    try:
        body = json.loads(r.get("body") or "null")
    except ValueError:
        body = None
    return {"method": r["method"], "path": r["path"], "query": parse_qs(r.get("query") or ""), "body": body,
            "h": {k.lower(): v for k, v in (r.get("headers") or {}).items()}}


PHOTOS = ["http://x/1.png"]


def _pet(b, name_key="name", **extra):
    return (isinstance(b, dict) and b.get(name_key) == "rex" and b.get("id") == 7 and b.get("photoUrls") == PHOTOS
            and b.get("status") in ("available", None) and all(b.get(k) == v for k, v in extra.items()))


def _order(b, **extra):
    return (isinstance(b, dict) and b.get("id") == 9 and b.get("petId") == 7 and b.get("quantity") == 3
            and all(b.get(k) == v for k, v in extra.items()))


CHECK = {
    "D1_body_rename": lambda v: _pet(v["body"], "petName") and "name" not in v["body"],
    "D1b_body_rename_request_only": lambda v: _pet(v["body"], "petName") and "name" not in v["body"],
    "D2_query_rename": lambda v: v["method"] == "GET" and v["path"] == "/pet/findByStatus" and v["query"].get("state") == ["available"],
    "D3_path_param_rename": lambda v: v["path"] == "/pet/7",
    "D4_route_move": lambda v: v["path"] == "/v2/pet/7" and v["method"] == "GET",
    "D5_str_to_int": lambda v: v["body"].get("phone") == 12345 and v["body"].get("username") == "alice",
    "D7_wrap": lambda v: _pet((v["body"] or {}).get("pet")),
    "D8_unwrap": lambda v: _pet(v["body"]) and "pet" not in v["body"],
    "D9a_enum_case": lambda v: _order(v["body"], status="PLACED"),
    "D10_required_default": lambda v: _order(v["body"], status="placed", channel="web"),
    "D12_header_rename": lambda v: v["method"] == "DELETE" and v["path"] == "/pet/7" and v["h"].get("x-pet-key") == "k-123",
    "D13_method_change": lambda v: v["method"] == "PATCH" and v["path"] == "/pet" and _pet(v["body"]) ,
    "A1_array_root_baseline": lambda v: v["path"] == "/pet/findByStatus" and v["query"].get("status") == ["available"],
    "D12b_auth_header_rename": lambda v: v["path"] == "/pet/7" and v["h"].get("x-pet-key") == "k-test-123",
    "D20b_flipflop_request_only": lambda v: _pet(v["body"], "name") and "petName" not in v["body"],
    "D14_response_rename": lambda v: v["path"] == "/pet/7",
    "D16_units_change": lambda v: _order(v["body"], status="placed"),
    "D17_swap_same_type": lambda v: _order(v["body"], status="placed"),
    "D19_description_only": lambda v: v["path"] == "/pet/7",
    "D20_flipflop": lambda v: _pet(v["body"], "name") and "petName" not in v["body"],
    "D21_two_drifts": lambda v: _pet(v["body"], "petName", source="api") and "name" not in v["body"],
}
CHECK_CALL1 = {"D20b_flipflop_request_only": lambda v: _pet(v["body"], "petName") and "name" not in v["body"],"D20_flipflop": lambda v: _pet(v["body"], "petName") and "name" not in v["body"]}


# ------------------------------------------------------------------ process / control helpers
def control(**body) -> dict:
    req = urllib.request.Request(f"{ORIGIN}/__control", data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def start_prism(spec: Path) -> lib.subprocess.Popen:
    p = lib.spawn("prism", ["npx", "-y", "@stoplight/prism-cli@5", "mock", "-p", str(P_PRISM), "-h", "127.0.0.1", "-d",
                            str(spec)], LOGS)
    return p


def stop(p) -> None:
    lib.kill(p)


async def one_call(case: dict, call_no: int, audit: lib.Audit, tool: str, args: dict, check, front) -> dict:
    f0, h0 = lib.line_count(FXLOG), audit.max_heal_id()
    out = await front.call(f"pet__{tool}", args, 60)
    await asyncio.sleep(0.3)
    reqs = [r for r in lib.read_jsonl(FXLOG, f0) if r.get("kind") == "req"]
    heals = audit.heals_after(h0)
    return {"out": out, "reqs": reqs, "heals": heals}


def classify(case: dict, tool: str, call: dict, check) -> dict:
    out, reqs, heals = call["out"], call["reqs"], call["heals"]
    if out["exc"]:
        return {"observed": "hung" if out["exc"].startswith("HUNG") else "crashed", "why": out["exc"]}
    ok2 = [r for r in reqs if r["status"] < 300]
    writes_ok = [r for r in ok2 if r["method"] in ("POST", "PUT", "PATCH", "DELETE")]
    recovered = any(h["outcome"] == "RECOVERED" for h in heals)
    res = out["result"]
    base = {"prism_status": [r["status"] for r in reqs], "dup_write": len(writes_ok) > 1}
    if ok2:
        recv = ok2[-1]
        v = view(recv)
        good = bool(check(v)) if check else False
        if heals and not recovered:
            if recv["method"] == "GET":
                return {**base, "observed": "refused", "why": f"read accepted by Prism but agent got an error ({heals[-1]['outcome']}/{heals[-1]['reason']})"}
            if good:
                return {**base, "observed": "landed_reported_fail",
                        "why": f"Prism accepted the intended request but the agent got an error ({heals[-1]['outcome']}/{heals[-1]['reason']})"}
        if case["id"].startswith("D14"):
            has_name = isinstance(res, dict) and "name" in res and "petName" not in res
            if not heals and not has_name:
                return {**base, "observed": "missed", "why": "response drift undetected: agent result lacks `name`",
                        "received": recv["path"]}
            good = good and has_name
        if not good:
            return {**base, "observed": "wrong", "why": "Prism accepted a request whose values/shape differ from intent",
                    "received": {"method": recv["method"], "path": recv["path"], "query": recv["query"], "body": v["body"],
                                 "headers": {k: x for k, x in v["h"].items() if k.startswith("x-")}}}
        if heals and not recovered:
            return {**base, "observed": "landed_reported_fail",
                    "why": f"Prism accepted the intended request but the agent got an error ({heals[-1]['outcome']}/{heals[-1]['reason']})"}
        return {**base, "observed": "heal_correct" if recovered else "pass_through"}
    if heals and not recovered:
        return {**base, "observed": "refused", "why": f"{heals[-1]['outcome']}/{heals[-1]['reason']}"}
    return {**base, "observed": "missed", "why": f"no accepted request; no audit row; result={lib.short(res, 200)}"}


def verdict(expected: str, observed: str, dup: bool) -> str:
    if observed == "wrong":
        return "FALSE_PATCH"
    if observed in ("crashed", "hung"):
        return observed.upper()
    if observed == "landed_reported_fail":
        return "LANDED_REPORTED_FAIL"
    if dup:
        return "DUP_WRITE"
    ok = {"heal": {"heal_correct"}, "refuse": {"refused"}, "pass_through": {"pass_through"},
          "known_miss": {"pass_through", "missed"}}[expected]
    if observed in ok:
        return "PASS(known miss confirmed)" if expected == "known_miss" else "PASS"
    return {"heal": "MISSED" if observed in ("missed",) else observed.upper(),
            "refuse": "UNEXPECTED_HEAL_VALID" if observed == "heal_correct" else observed.upper(),
            "pass_through": "UNEXPECTED_HEAL" if observed == "heal_correct" else observed.upper(),
            "known_miss": observed.upper()}[expected]


async def run_case(case: dict) -> dict:
    SPECS.mkdir(parents=True, exist_ok=True)
    base = base_spec()
    if case.get("base"):
        MUT[case["base"]](base)
    drift = copy.deepcopy(base)
    if case["mut"] == "D8":
        drift = base_spec()  # the drifted API is the flat original; the base spec wrapped it
    else:
        MUT[case["mut"]](drift)
    bf, df = SPECS / f"{case['id']}.base.json", SPECS / f"{case['id']}.drift.json"
    bf.write_text(json.dumps(base, indent=1), encoding="utf-8")
    df.write_text(json.dumps(drift, indent=1), encoding="utf-8")
    control(spec_file=str(bf))
    healer = prism = None
    t_case = time.time()
    try:
        prism = start_prism(df)  # starts in parallel with the healer; not contacted until the call
        servers = HERE / "servers.json"
        env = {}
        if case.get("auth") == "apikey":
            cfg = json.loads(servers.read_text(encoding="utf-8"))
            cfg["apis"][0]["auth"] = {"type": "api_key", "header": "api_key", "value_env": "API_PET_KEY"}
            servers = PROOF / "servers_apikey.json"
            servers.write_text(json.dumps(cfg, indent=1), encoding="utf-8")
            env = {"API_PET_KEY": "k-test-123"}  # fake test value, never a real key
        healer = lib.start_healer(LOGS, DB, servers, P_HEAL, [ORIGIN], name=f"healer_{case['id']}", env_extra=env)
        audit = lib.Audit(DB)
        async with lib.Front(P_HEAL) as front:
            names = [t["name"] for t in await front.tools()]
            tool = case["tool"]
            if f"pet__{tool}" not in names:
                return {"case": case["id"], "expected": case["expected"], "observed": "crashed",
                        "verdict": "CRASH", "why": f"tool pet__{tool} not exposed at freeze: {names}"}
            control(spec_file=str(df))
            lib.wait_port(P_PRISM, prism, 90)
            time.sleep(1.5)  # noqa: ASYNC251
            calls = []
            c1 = await one_call(case, 1, audit, tool, case["args"], None, front)
            chk1 = CHECK_CALL1.get(case["id"], CHECK.get(case["id"]))
            row1 = classify(case, tool, c1, chk1)
            calls.append((c1, row1))
            if case.get("flipflop"):
                stop(prism)
                lib.wait_closed(P_PRISM)
                control(spec_file=str(bf))
                prism = start_prism(bf)
                lib.wait_port(P_PRISM, prism, 90)
                time.sleep(1.5)  # noqa: ASYNC251
                c2 = await one_call(case, 2, audit, tool, case["args"], None, front)
                row2 = classify(case, tool, c2, CHECK.get(case["id"]))
                calls.append((c2, row2))
                final = row2
                final["call1_observed"] = row1["observed"]
                extra = []
                row_last = row2
                for n in range(3, 6):  # how many more failing calls before the stale fix is gone?
                    if row_last["observed"] in ("pass_through", "heal_correct"):
                        break
                    cx = await one_call(case, n, audit, tool, case["args"], None, front)
                    row_last = classify(case, tool, cx, CHECK.get(case["id"]))
                    calls.append((cx, row_last))
                    extra.append(row_last["observed"])
                final["calls_after_revert"] = [row2["observed"], *extra]
            else:
                final = row1
            heals = [h for c, _ in calls for h in c["heals"]]
            res = {
                "case": case["id"], "tool": tool, "expected": case["expected"], "args": case["args"],
                "observed": final["observed"], "why": final.get("why"),
                "verdict": verdict(case["expected"], final["observed"], final.get("dup_write", False)),
                "call1_observed": final.get("call1_observed"), "calls_after_revert": final.get("calls_after_revert"),
                "prism_status": final.get("prism_status"), "received": final.get("received"),
                "audit": [{k: h.get(k) for k in ("tier", "path", "outcome", "reason", "raw_code", "request_ops", "response_ops", "mttr_ms", "raw_error")} for h in heals],
                "latency_ms": [c["out"]["latency_ms"] for c, _ in calls],
                "agent_result": lib.short(calls[-1][0]["out"]["result"], 500),
                "prism_requests": [{k: r.get(k) for k in ("method", "path", "query", "body", "status", "resp")} for c, _ in calls for r in c["reqs"]],
                "case_s": round(time.time() - t_case, 1),
            }
            # gateway alive?
            h = await front.call("pet__getUserByName", {"username": "alice"}, 30)
            res["gateway_alive_after"] = h["exc"] is None
            return res
    finally:
        for p in (healer, prism):
            if p:
                stop(p)
        lib.wait_closed(P_PRISM)
        lib.wait_closed(P_HEAL)


async def main(only: list[str]) -> None:
    cases = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    cases += yaml.safe_load((HERE / "cases.addendum.yaml").read_text(encoding="utf-8"))["cases"]
    cases += yaml.safe_load((HERE / "cases.addendum2.yaml").read_text(encoding="utf-8"))["cases"]
    if only:
        cases = [c for c in cases if c["id"] in only]
    PROOF.mkdir(exist_ok=True)
    fx = lib.spawn("fixture", [lib.sys.executable, str(HERE.parent / "fixture.py"), "--port", str(P_FIX), "--upstream",
                              f"http://127.0.0.1:{P_PRISM}", "--log", str(FXLOG), "--spec-file", str(HERE / "openapi.orig.json")], LOGS)
    try:
        lib.wait_port(P_FIX, fx)
        for c in cases:
            print(f"== {c['id']} (expect {c['expected']})", flush=True)
            try:
                r = await asyncio.wait_for(run_case(c), 240)
            except Exception as e:  # noqa: BLE001
                r = {"case": c["id"], "expected": c["expected"], "observed": "crashed", "verdict": "CRASH",
                     "why": f"harness/case exception {type(e).__name__}: {e}"[:300]}
            r["run"] = __import__("os").environ.get("RUN_TAG", "main")
            lib.jl(RESULTS, r)
            print(f"   -> {r['observed']} {r['verdict']} {r.get('why') or ''}"[:200], flush=True)
    finally:
        lib.kill_all()


if __name__ == "__main__":
    try:
        asyncio.run(main(sys.argv[1:]))
    finally:
        lib.kill_all()
