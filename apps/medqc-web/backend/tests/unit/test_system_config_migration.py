from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260810_000027_system_config_persistence.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("system_config_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_system_config_migration_declares_current_head_and_required_contracts():
    migration = _load_migration()

    assert migration.revision == "20260810_000027"
    assert migration.down_revision == "20260809_000026"
    assert migration.SYNC_CONFIG_SCHEMA == "qc"
    assert migration.LLM_CONFIG_SCHEMA == "public"
    assert {item["name"] for item in migration.DEFAULT_SYNC_TABLES} == {
        "mr",
        "diagnosis",
        "mr_surgery",
        "mr_cost",
        "admission_record",
        "discharge_record",
        "first_course_record",
        "daily_course_record",
    }


def test_system_config_migration_seeds_production_sync_keys():
    migration = _load_migration()

    assert migration.DEFAULT_PG_SOURCE_CONFIG["remote_password_ref"] == "env:REMOTE_DB_PASSWORD"
    assert migration.DEFAULT_PG_SOURCE_CONFIG["remote_schema"] == "public"
    assert migration.DEFAULT_PG_SOURCE_CONFIG["sync_mode"] == "table"


def test_system_config_migration_fixes_owner_and_fails_closed_on_legacy_contract_drift(monkeypatch):
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: statements.append(str(statement)))

    migration.upgrade()

    sql = "\n".join(statements)
    assert "CREATE SCHEMA IF NOT EXISTS qc" in sql
    assert "to_regclass('public.sync_config_registry')" in sql
    assert "INSERT INTO qc.sync_config_registry" in sql
    assert "system_config_schema_contract_mismatch: qc.sync_config_registry" in sql
    assert "system_config_primary_key_contract_mismatch: qc.sync_config_registry" in sql
    assert "system_config_schema_contract_mismatch: public.user_llm_configs" in sql
    assert "system_config_primary_key_contract_mismatch: public.user_llm_configs" in sql
