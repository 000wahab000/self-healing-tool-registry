from __future__ import annotations

import sys
import types

import pytest

from healer.store_pg import PostgresStore


@pytest.mark.parametrize(
    "name",
    [
        "save_fix_and_audit",
        "get_candidate",
        "get_rules",
        "is_rule",
        "promote",
        "record_rule_win",
    ],
)
def test_missing_fix_store_methods_fail_loudly(name: str) -> None:
    store = PostgresStore.__new__(PostgresStore)
    method = getattr(store, name)
    with pytest.raises(
        NotImplementedError,
        match=f"^PostgresStore: {name} not implemented yet, see PLAN\\.md \\(deferred\\)$",
    ):
        if name == "save_fix_and_audit":
            method(None, None)
        elif name == "get_rules":
            method()
        else:
            method(None)


def test_postgres_construction_warns_before_connecting(monkeypatch) -> None:
    psycopg = types.ModuleType("psycopg")
    psycopg.connect = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline"))
    rows = types.ModuleType("psycopg.rows")
    rows.dict_row = object()
    monkeypatch.setitem(sys.modules, "psycopg", psycopg)
    monkeypatch.setitem(sys.modules, "psycopg.rows", rows)

    with (
        pytest.warns(RuntimeWarning, match="incomplete and unsupported"),
        pytest.raises(RuntimeError, match="offline"),
    ):
        PostgresStore("unused")
