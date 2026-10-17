"""Build bench/chaos/<suite>/REPORT.md tables + SUMMARY.md from each suite's proof/results.jsonl. No LLM.

Usage: python bench/chaos/make_reports.py     (last row per case wins; earlier rows stay in the jsonl)
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITES = ["petstore", "faults", "spec_mcp_faults", "graphql", "stripe"]


def last_rows(suite: str) -> list[dict]:
    rows: dict[str, dict] = {}
    for line in (HERE / suite / "proof" / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        rows[r["case"]] = r
    return list(rows.values())


def label(r: dict) -> str:
    """One of: healed / refused / pass-through / missed / wrong (false patch) / crashed / hung / other."""
    v, o = r.get("verdict", ""), r.get("observed", "")
    if v == "FALSE_PATCH":
        return "wrong (false patch)"
    if v in ("CRASH", "CRASHED"):
        return "crashed"
    if v == "HUNG":
        return "hung"
    if o in ("heal_correct", "retried_success", "recovered", "tier0_served", "single_flight"):
        return "healed / recovered"
    if o in ("refused", "structured_error", "arg_error", "bounded_error", "blocked_api_skipped_gateway_up",
             "structured_error_no_audit"):
        return "refused / structured error"
    if o in ("pass_through", "exposed", "not_exposed", "success", "null_result", "bounded_success", "started_call_ok"):
        return "pass-through"
    if str(o).startswith("saved_writes"):
        return "refused / structured error (write not replayed)"
    if o in ("startup_abort", "startup_hang"):
        return "startup abort (whole gateway down)" if o == "startup_abort" else "hung"
    if v == "LANDED_REPORTED_FAIL":
        return "missed (write landed, error reported)"
    return "missed / other"


def note(r: dict) -> str:
    bits = []
    if r.get("why"):
        bits.append(str(r["why"]))
    a = r.get("audit")
    if a:
        bits.append("audit: " + ", ".join(f"T{x.get('tier')}/{x.get('outcome')}" + (f"/{x['reason']}" if x.get("reason") else "") for x in a[:3]))
    ar = r.get("agent_result")
    if isinstance(ar, str):
        try:
            ar = json.loads(ar)
        except ValueError:
            ar = None
    if isinstance(ar, dict) and ar.get("error") and r.get("verdict") not in ("PASS",):
        bits.append(f"agent saw: {ar['error']}/{ar.get('reason') or ar.get('status') or ''}")
    if r.get("call1_observed"):
        bits.append(f"call 1: {r['call1_observed']}")
    if r.get("calls_after_revert"):
        bits.append("calls after revert: " + ", ".join(r["calls_after_revert"]))
    if r.get("latency_ms") not in (None, []):
        bits.append(f"latency {r['latency_ms']} ms")
    if r.get("attempts_at_server") is not None:
        bits.append(f"server attempts {r['attempts_at_server']}, gap {r.get('gap_between_attempts_s')} s")
    s = "; ".join(bits).replace("|", "/").replace("\n", " ")
    return s[:330]


def table(suite: str) -> str:
    out = ["| Case | Expected | Observed | Verdict | Category | Note |", "|---|---|---|---|---|---|"]
    for r in last_rows(suite):
        out.append(f"| {r['case']} | {r.get('expected')} | {r.get('observed')} | {r.get('verdict')} | {label(r)} | {note(r)} |")
    return "\n".join(out)


def totals(suite: str) -> Counter:
    c: Counter = Counter()
    for r in last_rows(suite):
        c["cases"] += 1
        v = r.get("verdict", "")
        if v == "PASS" or v.startswith("PASS("):
            c["pass"] += 1
        elif v == "FALSE_PATCH":
            c["false_patch"] += 1
        elif v in ("CRASH", "CRASHED"):
            c["crash"] += 1
        elif v == "HUNG":
            c["hung"] += 1
        elif v == "LANDED_REPORTED_FAIL":
            c["landed_reported_fail"] += 1
        elif v in ("REFUSED", "MISSED", "NOT_NEEDED") or r.get("observed") in ("refused", "missed"):
            c["miss_safe"] += 1
        else:
            c["other_fail"] += 1
    return c


def summary_md(parts, tot) -> str:
    import report_text as T
    out = ["# Chaos suites summary (no LLM, offline except where stated)", "", T.COMMON, "",
           "Run date 2026-10-17, branch test/chaos-suite, nothing committed. Per-suite detail, oracle logs and raw rows are in `bench/chaos/<suite>/REPORT.md` and `proof/`.",
           "", "## Suites run / skipped", "",
           "| Suite | Status | Cases | Pre-registration (cases.yaml sha256 prefix) |", "|---|---|---|---|",
           f"| petstore | run | {parts[0][1]['cases']} | 4b7c267f754d94d9 (+ addenda 0d6ff67284e9f3a8, 10562414b6536c8d) |",
           f"| faults | run (F10 and call-time private-DNS not run) | {parts[1][1]['cases']} | 046823628e67ab85 |",
           f"| spec_mcp_faults | run (S4 spec-changes-during-heal not run) | {parts[2][1]['cases']} | eb69799f84c56c30 |",
           f"| graphql | run (live baseline + project-mock drift) | {parts[3][1]['cases']} | c41a2a32b5bcc50a |",
           f"| stripe | run, but the gateway hung on startup so no call was possible | {parts[4][1]['cases']} | eabe8d7bea302f2a |",
           "", ("Skipped for cost/need: Docker targets (stripe-mock, go-httpbin/T4 httpbin), GitHub REST version diffs (T2), live Stripe, agent-driven (`claude -p`) runs. "
           "Existing GitHub MCP suite (`bench/chaos/github`) was not re-run."), ""]
    for name, t in parts:
        out += [f"## {name}", "", table_short(name), "",
                (f"Totals: {t['cases']} cases, {t.get('pass', 0)} as expected, {t.get('false_patch', 0)} false patches, {t.get('crash', 0)} crashed, {t.get('hung', 0)} hung, "
                f"{t.get('landed_reported_fail', 0)} write-landed-but-error-reported, {t.get('miss_safe', 0)} safe misses/refusals where a heal was expected, {t.get('other_fail', 0)} other deviations."), ""]
    out += ["## Grand totals", "",
            f"- Cases: {tot['cases']}; as expected: {tot['pass']}",
            f"- **False patches: {tot['false_patch']}** (an accepted request with a changed or dropped value). The one apparent case, D13, is a valid heal (see petstore report).",
            f"- Crashes: {tot['crash']} (B1 gateway process death; B2 front-door error twice, gateway stayed up). Hangs: {tot['hung']} (stripe, B6).",
            f"- Write landed but agent told it failed: {tot['landed_reported_fail']} (B8).",
            f"- Safe misses (refused where a heal was expected): {tot['miss_safe']}.",
            f"- Other deviations from the pre-registered expectation: {tot['other_fail']} (graphql 8; faults 3: F2b, F11a, F11b; spec_mcp 1: R1; petstore 2: D13 valid unexpected heal, D20 whose first call did not heal).",
            "", T.BUGS]
    return "\n".join(out) + "\n"


def table_short(suite: str) -> str:
    out = ["| Case | Expected | Observed | Verdict |", "|---|---|---|---|"]
    out += [f"| {r['case']} | {r.get('expected')} | {r.get('observed')} | {r.get('verdict')} |" for r in last_rows(suite)]
    return "\n".join(out)


if __name__ == "__main__":
    import report_text as T
    tot = Counter()
    parts = []
    for s in SUITES:
        t = totals(s)
        tot.update(t)
        (HERE / s / "proof" / "table.md").write_text(table(s) + "\n", encoding="utf-8")
        parts.append((s, t))
        (HERE / s / "REPORT.md").write_text(T.HEAD[s] + "\n" + T.COMMON + "\n\n## Every case\n\n" + table(s) + "\n", encoding="utf-8")
    (HERE / "SUMMARY.md").write_text(summary_md(parts, tot), encoding="utf-8")
    print(json.dumps({s: dict(t) for s, t in parts}, indent=1))
    print(dict(tot))
