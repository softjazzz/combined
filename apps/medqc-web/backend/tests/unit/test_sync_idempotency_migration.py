from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260814_000033_sync_trigger_idempotency.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "sync_trigger_idempotency_migration",
        MIGRATION_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sync_idempotency_table_is_owned_by_current_alembic_head(monkeypatch) -> None:
    migration = _load_migration()
    statements: list[str] = []
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda statement: statements.append(str(statement)),
    )

    migration.upgrade()

    sql = "\n".join(statements)
    assert migration.revision == "20260814_000033"
    assert migration.down_revision == "20260812_000032"
    assert migration.TABLE_SCHEMA == "qc"
    assert "CREATE TABLE IF NOT EXISTS qc.sync_trigger_idempotency" in sql
    assert "to_regclass('public.sync_trigger_idempotency')" in sql
    assert "INSERT INTO qc.sync_trigger_idempotency" in sql
    assert "sync_idempotency_schema_contract_mismatch" in sql
    assert "sync_idempotency_primary_key_contract_mismatch" in sql
