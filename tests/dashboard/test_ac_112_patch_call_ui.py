from __future__ import annotations

from pathlib import Path


def test_ac_112_patch_call_ui_keeps_each_request_distinct_and_truthful() -> None:
    page = (Path(__file__).parents[2] / "dashboard" / "index.html").read_text()
    render = page.split("function renderPatchCalls(calls)", 1)[1].split("\nfunction ", 1)[0]
    assert "calls.map((c) => c.event_id)" in render
    assert "[...calls].sort((a, b) => b.ts_ms - a.ts_ms || b.event_id - a.event_id)" in render
    assert '"Existing patch applied"' in render
    assert '"Recovered and patched"' in render
    assert '"Patch attempted"' in render
    assert 'c.class !== "OK" ? "Patch attempted" : hasNewPatch' in render
    assert 'c.patches.some((p) => !p.reused)' in render
    assert 'c.latency_ms + " ms"' in render
    assert "opChip(o, false)" in render and "opChip(o, true)" in render
    assert 'el("td", c.tool' in render  # el() writes user-controlled text through textContent.
    assert "innerHTML" not in render and "mttr" not in render.lower() and "tier" not in render.lower()
    assert "Recovery attempts" in page and "No patched requests yet" in render
    assert 'id="heal-count" title="Recovery attempts" aria-label="Recovery attempts"' in page
