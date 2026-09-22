"""仅记录 Alembic 操作，不连接或写入业务数据库。"""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260922_000045_add_task_scene.py"
    spec = importlib.util.spec_from_file_location("task_scene_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mock_operations(monkeypatch, migration, schemas, *, existing=False):
    calls = []
    inspector = SimpleNamespace(
        has_table=lambda table, schema: schema in schemas,
        get_columns=lambda table, schema: [{"name": "id"}] + ([{"name": "scene"}] if existing else []),
        get_check_constraints=lambda table, schema: [{"name": migration.CONSTRAINT}] if existing else [],
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda bind: inspector)
    monkeypatch.setattr(migration.op, "get_bind", lambda: None)
    for name in ("add_column", "create_check_constraint", "drop_constraint", "drop_column", "execute"):
        monkeypatch.setattr(migration.op, name, lambda *args, _name=name, **kwargs: calls.append((_name, args, kwargs)))
    return calls


@pytest.mark.parametrize("schemas", [(), ("qc",), ("public",), ("qc", "public")])
def test_upgrade_targets_existing_explicit_schemas_without_backfill(monkeypatch, schemas):
    migration = load_migration()
    calls = mock_operations(monkeypatch, migration, schemas)
    migration.upgrade()
    assert migration.down_revision == "20260915_000044"
    assert migration.revision == "20260922_000045"
    assert len(calls) == len(schemas) * 2
    for schema in schemas:
        add = next(call for call in calls if call[0] == "add_column" and call[2]["schema"] == schema)
        assert add[1][0] == "qc_tasks"
        column = add[1][1]
        assert column.name == "scene"
        assert column.nullable is True
        assert column.default is None and column.server_default is None
        check = next(call for call in calls if call[0] == "create_check_constraint" and call[2]["schema"] == schema)
        assert check[1] == (migration.CONSTRAINT, "qc_tasks", "scene IS NULL OR scene IN ('running', 'final', 'outpatient')")
    assert not any(call[0] == "execute" for call in calls)


def test_upgrade_does_not_duplicate_existing_contract(monkeypatch):
    migration = load_migration()
    calls = mock_operations(monkeypatch, migration, ("qc", "public"), existing=True)
    migration.upgrade()
    assert calls == []


def test_downgrade_only_removes_scene_contract(monkeypatch):
    migration = load_migration()
    calls = mock_operations(monkeypatch, migration, ("qc", "public"), existing=True)
    migration.downgrade()
    assert [call[0] for call in calls] == ["drop_constraint", "drop_column"] * 2
    assert [call[2]["schema"] for call in calls] == ["public", "public", "qc", "qc"]
    assert all(call[1][0] == "qc_tasks" and call[1][1] == "scene" for call in calls if call[0] == "drop_column")


def test_orm_keeps_scene_nullable_with_same_check():
    from app.database.models.qc import QCTask
    from sqlalchemy import CheckConstraint

    table = QCTask.__table__
    assert table.c.scene.nullable is True
    assert table.c.scene.default is None
    checks = [item for item in table.constraints if isinstance(item, CheckConstraint) and item.name == "ck_qc_tasks_scene"]
    assert len(checks) == 1
    assert str(checks[0].sqltext) == load_migration().SCENE_CHECK
