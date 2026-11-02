"""Caché 同步 POC 库的正式初始化入口验收。"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa

from scripts import bootstrap_cache_sync_database as bootstrap

pytest_plugins = ("test_report_migration_compatibility",)


def _prepare_owner(engine: sa.Engine) -> None:
    database = engine.url.database
    user = engine.url.username
    assert database and user
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='medqc_owner') THEN "
            "CREATE ROLE medqc_owner NOLOGIN; END IF; END $$"
        )
        connection.exec_driver_sql(f'GRANT medqc_owner TO "{user}"')
        connection.exec_driver_sql(
            f'GRANT CREATE ON DATABASE "{database}" TO medqc_owner'
        )
        connection.exec_driver_sql("GRANT CREATE, USAGE ON SCHEMA public TO medqc_owner")


def _prepare_poc_database(engine: sa.Engine) -> None:
    _prepare_owner(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE SCHEMA cache_raw AUTHORIZATION medqc_owner")
        connection.exec_driver_sql("CREATE SCHEMA cdm AUTHORIZATION medqc_owner")
        connection.exec_driver_sql("CREATE SCHEMA sync_ops AUTHORIZATION medqc_owner")
        connection.exec_driver_sql("SET ROLE medqc_owner")
        connection.exec_driver_sql(
            "CREATE TABLE cache_raw.source_record "
            "(source_key text PRIMARY KEY, payload jsonb NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO cache_raw.source_record VALUES "
            "('synthetic-1', '{\"visit_id\":\"v1\"}'::jsonb),"
            "('synthetic-2', '{\"visit_id\":\"v2\"}'::jsonb)"
        )
        for table in (
            "source_interface",
            "sync_batch",
            "source_schema",
            "sync_checkpoint",
            "bootstrap_marker",
        ):
            connection.exec_driver_sql(
                f"CREATE TABLE sync_ops.{table} (id text PRIMARY KEY, value text)"
            )
            connection.exec_driver_sql(
                f"INSERT INTO sync_ops.{table} VALUES ('keep', '{table}')"
            )


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    engine: sa.Engine,
    tmp_path: Path,
) -> None:
    pgpass = tmp_path / "pgpass"
    pgpass.write_text("placeholder\n", encoding="utf-8")
    pgpass.chmod(0o600)
    monkeypatch.setenv(
        "MEDQC_BOOTSTRAP_DATABASE_URL",
        engine.url.render_as_string(hide_password=False),
    )
    monkeypatch.setenv("PGPASSFILE", str(pgpass))
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REMOTE_DB_URL", raising=False)


def test_empty_database_upgrades_to_release_head(
    raw_pg: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _prepare_owner(raw_pg)
    _configure(monkeypatch, raw_pg, tmp_path)

    assert bootstrap.initialize(
        raw_pg.url.database,
        owner_role="medqc_owner",
    )[-1] == "20261026_000055"

    with raw_pg.connect() as connection:
        inspector = sa.inspect(connection)
        assert connection.exec_driver_sql(
            "SELECT version_num FROM public.alembic_version"
        ).scalar_one() == "20261026_000055"
        assert len(inspector.get_columns("mr", schema="cdm")) == 78
        assert inspector.get_pk_constraint("mr", schema="cdm")[
            "constrained_columns"
        ] == ["institute_id", "patient_id", "visit_id"]
        assert not inspector.has_table("mr", schema="public")


def test_poc_database_upgrades_to_release_head_without_changing_raw_data(
    raw_pg: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _prepare_poc_database(raw_pg)
    _configure(monkeypatch, raw_pg, tmp_path)

    assert bootstrap.main(
        [
            "--database",
            raw_pg.url.database,
            "--owner-role",
            "medqc_owner",
            "--apply",
        ]
    ) == 0

    with raw_pg.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT version_num FROM public.alembic_version"
        ).scalar_one() == "20261026_000055"
        assert connection.exec_driver_sql(
            "SELECT jsonb_agg(payload ORDER BY source_key) "
            "FROM cache_raw.source_record"
        ).scalar_one() == [{"visit_id": "v1"}, {"visit_id": "v2"}]
        for table in bootstrap.SYNC_OPS_TABLES:
            assert connection.exec_driver_sql(
                f"SELECT value FROM sync_ops.{table} WHERE id='keep'"
            ).scalar_one() == table
        inspector = sa.inspect(connection)
        assert len(inspector.get_columns("mr", schema="cdm")) == 78
        assert inspector.get_pk_constraint("mr", schema="cdm")[
            "constrained_columns"
        ] == ["institute_id", "patient_id", "visit_id"]
        assert not inspector.has_table("mr", schema="public")
        assert connection.exec_driver_sql(
            "SELECT pg_get_userbyid(c.relowner) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='cdm' AND c.relname='mr'"
        ).scalar_one() == "medqc_owner"

    # 重复执行只读核验已完成状态，不再发 DDL/DML。
    assert bootstrap.initialize(
        raw_pg.url.database,
        owner_role="medqc_owner",
    ) == []


def test_unapproved_poc_object_is_rejected_before_alembic(
    raw_pg: sa.Engine,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _prepare_poc_database(raw_pg)
    with raw_pg.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE cache_raw.unapproved (id integer)")
    _configure(monkeypatch, raw_pg, tmp_path)

    with pytest.raises(RuntimeError, match="未授权对象"):
        bootstrap.initialize(raw_pg.url.database, owner_role="medqc_owner")

    with raw_pg.connect() as connection:
        assert not sa.inspect(connection).has_table("alembic_version", schema="public")


def test_bootstrap_url_must_not_contain_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "MEDQC_BOOTSTRAP_DATABASE_URL",
        "postgresql+psycopg2://postgres:secret@127.0.0.1:5432/medqc_cache_poc",
    )
    with pytest.raises(RuntimeError, match="不得包含口令"):
        bootstrap.resolve_url("medqc_cache_poc")


def test_bootstrap_refuses_remote_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "MEDQC_BOOTSTRAP_DATABASE_URL",
        "postgresql+psycopg2://postgres@192.168.140.177:5432/medqc_cache_poc",
    )
    with pytest.raises(RuntimeError, match="127.0.0.1"):
        bootstrap.resolve_url("medqc_cache_poc")


def test_bootstrap_requires_explicit_pgpassfile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MEDQC_BOOTSTRAP_DATABASE_URL",
        "postgresql+psycopg2://postgres@127.0.0.1:5432/medqc_cache_poc",
    )
    monkeypatch.delenv("PGPASSFILE", raising=False)
    monkeypatch.delenv("PGPASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="PGPASSFILE"):
        bootstrap.initialize("medqc_cache_poc")
