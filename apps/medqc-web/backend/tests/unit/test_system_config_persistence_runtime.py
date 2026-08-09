from __future__ import annotations

import logging

import pytest

from app.core import supabase_client
from app.services import config_registry


def test_supabase_adapter_pins_user_llm_configs_to_public_schema():
    client = supabase_client._PgClient(lambda: None)

    query = client.table("user_llm_configs").select("*")
    sql, _params = query._build_select_sql()

    assert 'FROM "public"."user_llm_configs"' in sql


def test_supabase_adapter_logs_only_stable_error_context(caplog):
    class _Session:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("SECRET_SQL SELECT * FROM private_table params={'token': 'SECRET'}")

        def rollback(self):
            return None

        def close(self):
            return None

    query = supabase_client._Query(lambda: _Session(), "public.user_llm_configs").select("*")

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError):
        query.execute()

    assert "database_query_failed method=SELECT table=public.user_llm_configs" in caplog.text
    assert "SECRET_SQL" not in caplog.text
    assert "private_table" not in caplog.text
    assert "token" not in caplog.text


def test_config_registry_pins_runtime_queries_to_qc_schema(monkeypatch):
    statements: list[str] = []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, _params):
            statements.append(str(statement))
            return None

        def commit(self):
            return None

    monkeypatch.setattr(config_registry, "engine", object())
    monkeypatch.setattr(config_registry, "Session", lambda _engine: _Session())

    saved = config_registry.set_config("sync", "sync_tables", [{"name": "mr"}])

    assert saved is True
    assert any("INSERT INTO qc.sync_config_registry" in statement for statement in statements)
    assert all("INSERT INTO sync_config_registry" not in statement for statement in statements)


def test_config_registry_database_error_log_does_not_include_sql_or_parameters(
    monkeypatch,
    caplog,
):
    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, *_args, **_kwargs):
            raise RuntimeError("SECRET_SQL params={'password': 'SECRET'}")

    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setattr(config_registry, "engine", object())
    monkeypatch.setattr(config_registry, "Session", lambda _engine: _Session())

    with caplog.at_level(logging.WARNING):
        config_registry.get_config("sync", "sync_tables")

    assert "config_registry_database_read_failed namespace=sync key=sync_tables" in caplog.text
    assert "SECRET_SQL" not in caplog.text
    assert "password" not in caplog.text
    assert "SECRET" not in caplog.text
