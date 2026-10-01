"""迁移81双schema与ORM一致性离线验收，不连接数据库。"""
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.database.models.qc import QCTaskRecord


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261001_000081_task_record_type_snapshot.py"
    spec = importlib.util.spec_from_file_location("task_record_type_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot(**overrides):
    return {"name": "record_type_snapshot", "type": postgresql.JSONB(), "nullable": True, "default": None, **overrides}


class Inspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        assert table == "qc_task_records"
        return schema in self.states

    def get_columns(self, _table, schema):
        return self.states[schema]


class Bind:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.sql = []

    def execute(self, statement):
        sql = str(statement)
        self.sql.append(sql)
        count = next((value for schema, value in self.counts.items() if f'"{schema}"' in sql and "count(*)" in sql), 0)
        class Scalar:
            def scalar_one(self):
                return count
        return Scalar()


def wire(monkeypatch, module, states, counts=None):
    bind = Bind(counts)
    added, dropped = [], []
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(module.sa, "inspect", lambda _: Inspector(states))
    monkeypatch.setattr(module.op, "add_column", lambda *args, **kwargs: added.append((args, kwargs)))
    monkeypatch.setattr(module.op, "drop_column", lambda *args, **kwargs: dropped.append((args, kwargs)))
    return bind, added, dropped


def test_upgrade_sequence_nullable_jsonb_and_orm_contract(monkeypatch):
    module = migration()
    _, added, _ = wire(monkeypatch, module, {schema: [{"name": "department"}] for schema in module.SCHEMAS})
    module.upgrade()
    assert module.revision == "20261001_000081" and module.down_revision == "20261001_000080"
    assert [kwargs["schema"] for _, kwargs in added] == ["qc", "public"]
    orm = QCTaskRecord.__table__.c.record_type_snapshot
    assert orm.nullable and orm.default is None and orm.server_default is None
    assert isinstance(orm.type.dialect_impl(postgresql.dialect()), postgresql.JSONB)
    for args, _ in added:
        column = args[1]
        assert args[0] == QCTaskRecord.__tablename__
        assert column.name == orm.name and isinstance(column.type, postgresql.JSONB)
        assert column.nullable and column.default is None and column.server_default is None


def test_complete_upgrade_is_idempotent(monkeypatch):
    module = migration()
    _, added, _ = wire(monkeypatch, module, {schema: [{"name": "department"}, snapshot()] for schema in module.SCHEMAS})
    module.upgrade()
    assert added == []


@pytest.mark.parametrize("states", [
    {}, {"qc": []},
    {"qc": [{"name": "department"}, snapshot()], "public": [{"name": "department"}]},
    {"qc": [{"name": "department"}, snapshot(type=sa.JSON())]},
    {"qc": [{"name": "department"}, snapshot(nullable=False)]},
    {"qc": [{"name": "department"}, snapshot(default="'{}'")]},
])
def test_invalid_baseline_refuses_before_ddl(monkeypatch, states):
    module = migration()
    _, added, dropped = wire(monkeypatch, module, states)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert added == dropped == []


@pytest.mark.parametrize("populated", ["qc", "public"])
def test_downgrade_locks_both_and_preserves_any_populated_snapshot(monkeypatch, populated):
    module = migration()
    bind, _, dropped = wire(monkeypatch, module, {schema: [{"name": "department"}, snapshot()] for schema in module.SCHEMAS}, {populated: 1})
    with pytest.raises(RuntimeError, match=populated):
        module.downgrade()
    assert len(bind.sql) >= 3
    assert all("LOCK TABLE" in sql for sql in bind.sql[:2])
    assert dropped == []


def test_empty_snapshot_downgrade_drops_only_new_column_in_reverse_order(monkeypatch):
    module = migration()
    bind, _, dropped = wire(monkeypatch, module, {schema: [{"name": "department"}, snapshot()] for schema in module.SCHEMAS})
    module.downgrade()
    assert len(bind.sql) == 4 and all("LOCK TABLE" in sql for sql in bind.sql[:2])
    assert [kwargs["schema"] for _, kwargs in dropped] == ["public", "qc"]
    assert all(args == ("qc_task_records", "record_type_snapshot") for args, _ in dropped)
