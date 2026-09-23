"""规则集字段迁移合同测试；不连接或写入业务数据库。"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260923_000048_task_rule_set_key.py"
    spec = importlib.util.spec_from_file_location("task_rule_set_key_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Inspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        return self.states.get(schema, {}).get("exists", False)

    def get_columns(self, table, schema):
        return [dict(name=name, **column) for name, column in self.states[schema]["columns"].items()]


class _Bind:
    def __init__(self, counts):
        self.counts = counts
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql.startswith("LOCK TABLE"):
            return None
        schema = next(schema for schema in self.counts if f'"{schema}".' in sql)
        return SimpleScalar(self.counts[schema])


class SimpleScalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


def _state(*, exists=True, column_type=None, nullable=True, default=None):
    columns = {}
    if column_type is not None:
        columns["rule_set_key"] = {
            "type": column_type, "nullable": nullable, "default": default
        }
    return {"exists": exists, "columns": columns}


def _fakes(monkeypatch, migration, states, counts=None):
    bind = _Bind(counts or {schema: 0 for schema in states})
    calls = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration.sa, "inspect", lambda _: _Inspector(states))
    monkeypatch.setattr(
        migration.op, "add_column",
        lambda table, column, *, schema: calls.append(("add", schema, column)),
    )
    monkeypatch.setattr(
        migration.op, "drop_column",
        lambda table, column, *, schema: calls.append(("drop", schema, column)),
    )
    return bind, calls


def test_upgrade_adds_nullable_varchar_128_to_existing_schemas(monkeypatch):
    migration = _migration()
    states = {"qc": _state(), "public": _state()}
    bind, calls = _fakes(monkeypatch, migration, states)
    migration.upgrade()
    assert migration.revision == "20260923_000048"
    assert migration.down_revision == "20260923_000047"
    assert [(action, schema) for action, schema, _ in calls] == [("add", "qc"), ("add", "public")]
    assert all(isinstance(column.type, sa.String) and column.type.length == 128 and column.nullable for _, _, column in calls)
    assert bind.queries == []


def test_upgrade_rejects_incompatible_existing_column_before_ddl(monkeypatch):
    migration = _migration()
    states = {"qc": _state(), "public": _state(column_type=sa.String(64))}
    _, calls = _fakes(monkeypatch, migration, states)
    with pytest.raises(RuntimeError, match="public.qc_tasks.rule_set_key"):
        migration.upgrade()
    assert calls == []


def test_downgrade_protects_selected_rule_sets(monkeypatch):
    migration = _migration()
    states = {
        "qc": _state(column_type=sa.String(128)),
        "public": _state(column_type=sa.String(128)),
    }
    bind, calls = _fakes(monkeypatch, migration, states, {"qc": 0, "public": 1})
    with pytest.raises(RuntimeError, match="public.qc_tasks.*非 NULL rule_set_key"):
        migration.downgrade()
    assert calls == []
    assert bind.queries[:2] == [
        'LOCK TABLE "qc"."qc_tasks" IN ACCESS EXCLUSIVE MODE',
        'LOCK TABLE "public"."qc_tasks" IN ACCESS EXCLUSIVE MODE',
    ]


def test_orm_column_is_nullable_varchar_128():
    from app.database.models.qc import QCTask

    column = QCTask.__table__.c.rule_set_key
    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None
    for dialect in (postgresql.dialect(), sqlite.dialect()):
        ddl = str(CreateTable(QCTask.__table__).compile(dialect=dialect))
        assert "rule_set_key VARCHAR(128)" in ddl
