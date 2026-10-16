from __future__ import annotations

import inspect

from healer.store import FixStore
from healer.store_pg import PostgresStore


def test_ac_75_postgres_matches_fix_store_contract() -> None:
    for name, protocol_method in FixStore.__dict__.items():
        if name.startswith("_") or not inspect.isfunction(protocol_method):
            continue
        postgres_method = getattr(PostgresStore, name, None)
        assert postgres_method is not None
        assert name in PostgresStore.__dict__
        assert inspect.signature(postgres_method) == inspect.signature(protocol_method)
