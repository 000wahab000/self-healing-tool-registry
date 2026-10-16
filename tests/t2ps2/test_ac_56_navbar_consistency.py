from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES = {name: (ROOT / "dashboard" / name).read_text() for name in ("landing.html", "index.html", "connections.html")}


def nav_labels(source: str) -> list[str]:
    nav = re.search(r'<nav class="tabs"[^>]*>(.*?)</nav>', source, re.DOTALL)
    assert nav
    labels = re.findall(r'<(?:a|button)\b[^>]*>(.*?)</(?:a|button)>', nav.group(1), re.DOTALL)
    return [" ".join(re.sub(r"<span class=\"count\".*?</span>", "", label, flags=re.DOTALL).replace("<", " <").split()) for label in labels]


def test_ac_56_navbar_items_order_active_and_report_stability() -> None:
    expected = ["Home", "Live stream", "Patch log", "Metrics", "MCP", "Report", "Connections"]
    assert [nav_labels(PAGES[name]) for name in PAGES] == [expected] * 3
    assert 'a[aria-current="page"]' in (ROOT / "dashboard/theme.css").read_text()
    theme = (ROOT / "dashboard/theme.css").read_text()
    assert 'nav.tabs button[aria-pressed="true"]' in theme
    assert 'button[aria-selected="true"]' not in theme
    assert 'nav.tabs button:disabled' not in theme
    assert 'a href="/connections" aria-current="page"' in PAGES["connections.html"]
    assert 'id="tab-report"' in PAGES["index.html"] and "disabled" not in re.search(r'<button[^>]*id="tab-report"[^>]*>', PAGES["index.html"]).group()
    assert re.search(r'<p id="report-empty"[^>]*>No benchmark report', PAGES["index.html"])
    assert "python -m bench.run --agent scripted --n 3" in PAGES["index.html"]
    assert '$("report-empty").hidden = Boolean(r.report);' in PAGES["index.html"]
    assert 'location.hash.slice(1)' in PAGES["index.html"]
    assert 'href="/live#heals"' in PAGES["landing.html"]
    assert 'href="/live#heals"' in PAGES["connections.html"]
    assert re.search(r'<button[^>]*data-tab="heals"', PAGES["index.html"])


def test_ac_56_navbar_semantics_and_mobile_layout() -> None:
    assert 'role="tablist"' not in PAGES["index.html"]
    assert 'role="tab"' not in PAGES["index.html"]
    assert 'role="tabpanel"' not in PAGES["index.html"]
    assert 'aria-pressed="true"' in PAGES["index.html"]
    assert 'setAttribute("aria-pressed"' in PAGES["index.html"]
    theme = (ROOT / "dashboard/theme.css").read_text()
    assert "@media (max-width: 760px)" in theme
    assert ".top nav.tabs { order: 3; flex: 1 0 100%; max-width: 100%; }" in theme
