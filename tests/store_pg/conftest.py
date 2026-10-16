from __future__ import annotations

import os
from uuid import uuid4

import pytest


@pytest.fixture
def pg_store(monkeypatch):
    dsn = os.getenv("PG_DSN")
    if not dsn:
        pytest.skip("set PG_DSN to a disposable Postgres database")
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    from healer.store_pg import PostgresStore

    schema = f"test_store_pg_{uuid4().hex}"
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    test_dsn = make_conninfo(dsn, options=f"-csearch_path={schema}")
    monkeypatch.setenv("PG_DSN", test_dsn)
    try:
        store = PostgresStore(test_dsn)
        try:
            yield store
        finally:
            store.close()
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
