from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from healer.gateway import probe

CONFIG = os.environ.get("EXTERNAL_SMOKE_CONFIG")


@pytest.mark.skipif(not CONFIG, reason="set EXTERNAL_SMOKE_CONFIG for opt-in discovery smoke")
def test_external_selected_connection_discovery_only() -> None:
    config = json.loads(Path(CONFIG).read_text(encoding="utf-8"))
    entries = [
        entry
        for entry in [*config.get("apis", []), *config.get("servers", [])]
        if entry.get("selected_operations")
        and ("kind" in entry or entry.get("transport") == "http")
    ]
    assert entries, "smoke config needs one HTTP connection with selected_operations"

    for entry in entries:
        result = asyncio.run(probe(entry))
        assert result["ok"], result.get("error")
        prefix = f"{entry['name']}__"
        discovered = set(result["tools"])
        expected = {f"{prefix}{name}" for name in entry["selected_operations"]}
        assert expected <= discovered
