"""任务病历科室列迁移（迁移 60）的隔离测试，不连接业务数据库。"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260927_000060_task_record_department.py"
    spec = importlib.util.spec_from_file_location("task_record_department_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(*, exists=True, deployed=False):
    columns = {"completed_run_number": {"type": sa.Integer(), "nullable": True, "default": None}}
    if deployed:
        columns["department"] = {"type": sa.String(100), "nullable": True, "default": None}
    return {"exists": exists, "columns": columns}


class _Inspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        assert table == "qc_task_records"
        return self.states[schema]["exists"]

    def get_columns(self, table, schema):
        return [dict(name=name, **value) for name, value in self.states[schema]["columns"].items()]


class _Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _Bind:
    def __init__(self, populated=None):
        self.populated = populated or {}
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql.startswith("LOCK TABLE"):
            return None
        schema = next(name for name in ("qc", "public") if f'"{name}".' in sql)
        return _Scalar(self.populated.get(schema, 0))


def _fakes(monkeypatch, migration, states, *, populated=None):
    bind = _Bind(populated)
    calls = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration.sa, "inspect", lambda _: _Inspector(states))
    for name in ("add_column", "drop_column"):
        monkeypatch.setattr(
            migration.op, name,
            lambda *args, _name=name, **kwargs: calls.append((_name, args, kwargs)),
        )
    return bind, calls


def test_upgrade_adds_nullable_column_to_both_schemas(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(monkeypatch, migration, {schema: _table() for schema in migration.SCHEMAS})
    migration.upgrade()
    assert migration.revision == "20260927_000060"
    assert migration.down_revision == "20260927_000059"
    assert bind.queries == []
    assert [(name, kwargs["schema"]) for name, _, kwargs in calls] == [
        ("add_column", "qc"), ("add_column", "public"),
    ]
    for _, args, _ in calls:
        assert args[0] == "qc_task_records"
        column = args[1]
        assert column.name == "department"
        assert isinstance(column.type, sa.String) and column.type.length == 100
        assert column.nullable is True
        assert column.default is None and column.server_default is None


def test_upgrade_is_idempotent_for_complete_contract(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(monkeypatch, migration, {s: _table(deployed=True) for s in migration.SCHEMAS})
    migration.upgrade()
    assert calls == [] and bind.queries == []


def test_upgrade_skips_absent_schema_like_migration_55(monkeypatch):
    migration = _migration()
    _, calls = _fakes(monkeypatch, migration, {"qc": _table(), "public": _table(exists=False)})
    migration.upgrade()
    assert [kwargs["schema"] for _, _, kwargs in calls] == ["qc"]


@pytest.mark.parametrize("drift", [
    "wrong_length", "text_type", "not_null", "has_default", "missing_baseline",
])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    migration = _migration()
    qc = _table(deployed=True)
    public = _table(deployed=True)
    column = qc["columns"]["department"]
    if drift == "wrong_length":
        column["type"] = sa.String(64)
    elif drift == "text_type":
        column["type"] = sa.Text()
    elif drift == "not_null":
        column["nullable"] = False
    elif drift == "has_default":
        column["default"] = "''::character varying"
    else:
        qc = _table()
        public = _table()
        del public["columns"]["completed_run_number"]
    _, calls = _fakes(monkeypatch, migration, {"qc": qc, "public": public})
    with pytest.raises(RuntimeError):
        migration.upgrade()
    assert calls == []


def test_upgrade_rejects_mixed_or_missing_schemas(monkeypatch):
    migration = _migration()
    for states in (
        {"qc": _table(deployed=True), "public": _table()},
        {"qc": _table(exists=False), "public": _table(exists=False)},
    ):
        _, calls = _fakes(monkeypatch, migration, states)
        with pytest.raises(RuntimeError):
            migration.upgrade()
        assert calls == []


def test_downgrade_refuses_when_any_schema_has_department_after_locking(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(
        monkeypatch, migration, {s: _table(deployed=True) for s in migration.SCHEMAS},
        populated={"public": 2},
    )
    with pytest.raises(RuntimeError, match="拒绝降级"):
        migration.downgrade()
    assert bind.queries[:2] == [
        'LOCK TABLE "qc"."qc_task_records" IN ACCESS EXCLUSIVE MODE',
        'LOCK TABLE "public"."qc_task_records" IN ACCESS EXCLUSIVE MODE',
    ]
    assert calls == []


def test_downgrade_drops_empty_column_in_reverse_order(monkeypatch):
    migration = _migration()
    _, calls = _fakes(monkeypatch, migration, {s: _table(deployed=True) for s in migration.SCHEMAS})
    migration.downgrade()
    assert [(name, args, kwargs["schema"]) for name, args, kwargs in calls] == [
        ("drop_column", ("qc_task_records", "department"), "public"),
        ("drop_column", ("qc_task_records", "department"), "qc"),
    ]


def test_downgrade_is_noop_when_not_deployed(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(monkeypatch, migration, {s: _table() for s in migration.SCHEMAS})
    migration.downgrade()
    assert calls == [] and bind.queries == []


def test_orm_column_matches_migration_contract():
    from app.database.models.qc import QCTaskRecord

    column = QCTaskRecord.__table__.c.department
    assert isinstance(column.type, sa.String) and column.type.length == 100
    assert column.nullable is True
    assert column.default is None and column.server_default is None
    assert "department VARCHAR(100)" in str(CreateTable(QCTaskRecord.__table__).compile(dialect=postgresql.dialect()))
