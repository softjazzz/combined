"""日常病程记录时间是独立源字段，迁移不推断或回填时间。"""

from __future__ import annotations

import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def migration():
    path = BACKEND / "alembic/versions/20261029_000056_daily_course_record_datetime.py"
    spec = importlib.util.spec_from_file_location("daily_record_time_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _upgrade_sql(migration, monkeypatch, columns=(), *, exists=True):
    inspector = SimpleNamespace(
        has_table=lambda table, schema: exists,
        get_columns=lambda table, schema: list(columns),
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda _: inspector)
    output = StringIO()
    with Operations.context(MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output},
    )):
        migration.upgrade()
    return output.getvalue()


@pytest.mark.parametrize("mode,schema", [("split", "cdm"), ("single", "public")])
def test_upgrade_only_adds_nullable_no_default_timestamp(migration, monkeypatch, mode, schema):
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    sql = _upgrade_sql(migration, monkeypatch)
    assert f"ALTER TABLE {schema}.daily_course_record ADD COLUMN record_datetime TIMESTAMP WITHOUT TIME ZONE" in sql
    assert sql.count("ALTER TABLE") == 1
    assert not any(word in sql for word in ("NOT NULL", "DEFAULT", "UPDATE ", "DELETE ", "DROP "))


def test_existing_compatible_column_is_not_changed(migration, monkeypatch):
    columns = [{"name": "record_datetime", "type": sa.DateTime(), "nullable": True, "default": None}]
    assert _upgrade_sql(migration, monkeypatch, columns) == ""


@pytest.mark.parametrize("overrides", [
    {"type": sa.Text()},
    {"type": sa.Date()},
    {"type": sa.DateTime(timezone=True)},
    {"nullable": False},
    {"default": "CURRENT_TIMESTAMP"},
])
def test_existing_incompatible_column_is_rejected_without_rewriting(migration, monkeypatch, overrides):
    existing = {"name": "record_datetime", "type": sa.DateTime(), "nullable": True, "default": None}
    existing.update(overrides)
    with pytest.raises(RuntimeError, match="字段合同不符"):
        _upgrade_sql(migration, monkeypatch, [existing])


def test_missing_table_is_not_created(migration, monkeypatch):
    with pytest.raises(RuntimeError, match="缺少迁移目标表"):
        _upgrade_sql(migration, monkeypatch, exists=False)


def test_unknown_schema_mode_is_rejected(migration, monkeypatch):
    monkeypatch.setenv("DB_SCHEMA_MODE", "unknown")
    with pytest.raises(RuntimeError, match="DB_SCHEMA_MODE"):
        migration.upgrade()


def test_downgrade_does_not_delete_source_time(migration):
    with pytest.raises(RuntimeError, match="不支持自动删除"):
        migration.downgrade()


@pytest.mark.parametrize("mode,schema", [("split", "cdm"), ("single", "public")])
def test_additive_migration_preserves_existing_values_in_memory(migration, monkeypatch, mode, schema):
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f"ATTACH DATABASE ':memory:' AS {schema}")
            connection.exec_driver_sql(
                f"CREATE TABLE {schema}.daily_course_record "
                "(document_id TEXT PRIMARY KEY, record_content TEXT, submit_datetime DATETIME)"
            )
            connection.exec_driver_sql(
                f"INSERT INTO {schema}.daily_course_record VALUES (?, ?, ?)",
                ("synthetic-1", "合成测试原文", "2026-10-27 10:00:00"),
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
            assert connection.exec_driver_sql(
                f"SELECT document_id, record_content, submit_datetime, record_datetime "
                f"FROM {schema}.daily_course_record"
            ).one() == ("synthetic-1", "合成测试原文", "2026-10-27 10:00:00", None)
    finally:
        engine.dispose()


def test_orm_and_bootstrap_follow_new_single_head(migration):
    from app.database.models.cdm import DailyCourseRecord
    from scripts.bootstrap_cache_sync_database import TARGET_REVISION

    column = DailyCourseRecord.__table__.c.record_datetime
    assert isinstance(column.type, sa.DateTime) and not column.type.timezone
    assert column.nullable and column.default is None and column.server_default is None
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    assert ScriptDirectory.from_config(config).get_heads() == [migration.revision]
    assert TARGET_REVISION == migration.revision == "20261029_000056"
    assert migration.down_revision == "20261026_000055"


def test_bundle_and_snapshot_keep_record_and_submit_clocks_separate():
    from app.services.bundles import assembly
    from app.services.luxian_0609.source_evidence_reader import _NATIVE_SOURCE_FIELDS

    row = {
        "document_id": "synthetic-daily-1",
        "record_content": "合成测试正文。",
        "record_datetime": "2026-10-26 09:00:00",
        "submit_datetime": "2026-10-27 10:00:00",
        "physician_sign_datetime": "2026-10-28 11:00:00+08:00",
    }
    entry = assembly._inventory_entry(table_name="daily_course_record", row=row)
    assert entry["record_time"] == row["record_datetime"]
    assert entry["submit_time"] == row["submit_datetime"]
    assert entry["display_time"] == row["record_datetime"]
    facts = assembly._build_timeline_facts_from_docs({"daily_course_record": [row]})
    assert {(fact["field"], fact["value"]) for fact in facts} == {
        ("record_datetime", row["record_datetime"]),
        ("submit_datetime", row["submit_datetime"]),
    }
    assert "record_datetime" in _NATIVE_SOURCE_FIELDS["daily_course_record"]
