from __future__ import annotations

import sqlite3
from pathlib import Path

from healer.models import ErrorClass
from healer.store import Store

MOVE = {"op": "move", "from": ["query", "order_id"], "to": ["query", "order_reference"]}
PATCHES = [{"fix_id": 7, "reused": True, "request_ops": [MOVE], "response_ops": []}]


def test_ac_112_call_event_patch_metadata_migrates_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE call_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts_ms INTEGER NOT NULL, agent TEXT NOT NULL, run_id TEXT NOT NULL, "
            "tool TEXT NOT NULL, class TEXT NOT NULL, latency_ms INTEGER NOT NULL)"
        )

    store = Store(str(path))
    assert "patches" in {
        row["name"] for row in store._db.execute("PRAGMA table_info(call_events)")
    }
    store.log_call("mcp", "run", "orders__get_order", ErrorClass.OK, 9, patches=PATCHES)
    assert store.call_events()[0]["patches"] == PATCHES
    store.close()

    reopened = Store(str(path))
    assert reopened.call_events()[0]["patches"] == PATCHES
    reopened.close()


def test_ac_112_call_event_patch_metadata_drops_non_patch_payloads(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "safe.db"))
    try:
        store.log_call(
            "mcp",
            "run",
            "orders__get_order",
            ErrorClass.OK,
            9,
            patches=[{
                **PATCHES[0],
                "arguments": {"order_id": "private-value"},
                "result": {"secret": "not-stored"},
                "headers": {"Authorization": "Bearer secret-value"},
            }],
        )
        stored = store.call_events()[0]["patches"]
        assert stored == PATCHES
        assert "private-value" not in str(stored)
        assert "secret-value" not in str(stored)
    finally:
        store.close()
