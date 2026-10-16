"""Pure metric views for dashboard panels (AC-78, AC-79, AC-80).

No FastAPI imports or framework dependencies. All functions are pure and inspect
only persisted benchmark reports or store/audit rows.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]


def _parse_markdown_table(heading: str, text: str) -> list[dict[str, str]]:
    lines = text.splitlines()
    in_section = False
    table_lines: list[str] = []
    for line in lines:
        if line.startswith("## ") and heading.lower() in line.lower():
            in_section = True
            continue
        elif in_section and line.startswith("## "):
            break
        if in_section and line.strip().startswith("|"):
            table_lines.append(line.strip())

    if len(table_lines) < 3:
        return []

    headers = [c.strip() for c in table_lines[0].split("|")[1:-1]]
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) == len(headers):
            rows.append(dict(zip(headers, cols, strict=False)))
    return rows


def parse_report_markdown(text: str) -> dict[str, Any]:
    """Parse benchmark report markdown into scorecard metric structures."""
    m_ztar = re.search(
        r"Healable mutations.*healing:\s*\d+%\s*\((\d+)/(\d+)\);\s*baseline:\s*\d+%\s*\((\d+)/(\d+)\)",
        text,
    )
    ztar = {
        "healing": (
            {"adapted": int(m_ztar.group(1)), "runs": int(m_ztar.group(2))}
            if m_ztar
            else {"adapted": 0, "runs": 0}
        ),
        "baseline": (
            {"adapted": int(m_ztar.group(3)), "runs": int(m_ztar.group(4))}
            if m_ztar
            else {"adapted": 0, "runs": 0}
        ),
    }

    m_fp = re.search(r"False-Patch Rate:\s*\d+%\s*\((\d+)/(\d+)\)", text)
    false_patch = {
        "false_patches": int(m_fp.group(1)) if m_fp else 0,
        "healed": int(m_fp.group(2)) if m_fp else 0,
    }

    m_sr = re.search(r"Safe-Refusal Rate:\s*\d+%\s*\((\d+)/(\d+)\)", text)
    safe_refusal = {
        "refused": int(m_sr.group(1)) if m_sr else 0,
        "runs": int(m_sr.group(2)) if m_sr else 0,
    }

    scenarios_raw = _parse_markdown_table("Per scenario", text)
    per_scenario: list[dict[str, Any]] = []
    for row in scenarios_raw:
        sc = row.get("Scenario", "")
        if sc == "CLEAN":
            continue
        m_h = re.search(r"\((\d+/\d+)\)", row.get("Healing expected outcome", ""))
        h = m_h.group(1) if m_h else row.get("Healing expected outcome", "")
        m_b = re.search(r"\((\d+/\d+)\)", row.get("Baseline expected outcome", ""))
        b = m_b.group(1) if m_b else row.get("Baseline expected outcome", "")
        fail = row.get("Baseline failure mode", "-")
        refusal = row.get("Refusal reasons", "-")
        per_scenario.append({
            "scenario": sc,
            "healing": h,
            "baseline": b,
            "baseline_failure": None if fail in ("-", "") else fail,
            "refusal_reason": None if refusal in ("-", "") else refusal,
        })

    tokens_raw = _parse_markdown_table("Tokens", text)
    tokens: list[dict[str, Any]] = []
    for row in tokens_raw:
        sc = row.get("Scenario", "")
        if sc == "CLEAN":
            continue
        h_over = row.get("Healing overhead", "-")
        b_waste = row.get("Baseline wasted", "-")
        h_val = int(h_over) if h_over not in ("-", "", "n/a") and (h_over.isdigit() or (h_over.startswith("-") and h_over[1:].isdigit())) else 0
        b_val = int(b_waste) if b_waste not in ("-", "", "n/a") and (b_waste.isdigit() or (b_waste.startswith("-") and b_waste[1:].isdigit())) else 0
        tokens.append({
            "scenario": sc,
            "healing_overhead": h_val,
            "baseline_wasted": b_val,
        })

    return {
        "ztar": ztar,
        "false_patch": false_patch,
        "safe_refusal": safe_refusal,
        "per_scenario": per_scenario,
        "tokens": tokens,
    }


def scorecard(report_path: Path | str | None = None) -> dict[str, Any]:
    """Load benchmark report and return scorecard metrics. Never invent numbers."""
    path = Path(report_path) if report_path is not None else ROOT / "bench" / "report.md"
    if not path.is_file():
        return {
            "available": False,
            "hint": "python -m bench.run --agent scripted --n 3",
        }

    try:
        text = path.read_text(encoding="utf-8")
        parsed = parse_report_markdown(text)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
        return {
            "available": True,
            "source": str(path),
            "generated_at": mtime,
            **parsed,
        }
    except OSError:
        return {
            "available": False,
            "hint": "python -m bench.run --agent scripted --n 3",
        }
