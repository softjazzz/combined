"""任务运行历史迁移合同；使用假 inspector，不连接业务库。"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260923_000049_task_qc_runs.py"
    spec = importlib.util.spec_from_file_location("task_qc_runs_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_table(*, drift=None):
    columns = {
        "task_id": {"type": sa.String(36), "nullable": False, "default": None},
        "run_number": {"type": sa.Integer(), "nullable": False, "default": None},
        "job_id": {"type": sa.String(36), "nullable": False, "default": None},
        "triggered_by": {"type": sa.String(64), "nullable": False, "default": None},
        "created_at": {"type": sa.DateTime(), "nullable": False, "default": None},
    }
    if drift:
        columns[drift[0]].update(drift[1])
    return {
        "columns": columns,
        "pk": {"name": "pk_task_qc_runs", "constrained_columns": ["task_id", "run_number"]},
        "uniques": [{"name": "uq_task_qc_runs_job", "column_names": ["job_id"]}],
        "fks": [{"name": "fk_task_qc_runs_task", "constrained_columns": ["task_id"],
                 "referred_table": "qc_tasks", "referred_columns": ["id"], "referred_schema": None}],
        "checks": [{"name": "ck_task_qc_runs_positive_number", "sqltext": "(run_number > 0)"}],
    }


class _Inspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        return self.states.get(schema, {}).get("task" if table == "qc_tasks" else "run", False)

    def get_columns(self, table, schema):
        return [dict(name=name, **spec) for name, spec in self.states[schema]["table"]["columns"].items()]

    def get_pk_constraint(self, table, schema):
        return self.states[schema]["table"]["pk"]

    def get_unique_constraints(self, table, schema):
        return self.states[schema]["table"]["uniques"]

    def get_foreign_keys(self, table, schema):
        return self.states[schema]["table"]["fks"]

    def get_check_constraints(self, table, schema):
        return self.states[schema]["table"]["checks"]


class _Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _Bind:
    def __init__(self, counts):
        self.counts = counts
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql.startswith("LOCK TABLE"):
            return None
        schema = next(name for name in self.counts if f'"{name}".' in sql)
        return _Scalar(self.counts[schema])


def _setup(monkeypatch, migration, states, counts=None):
    calls = []
    bind = _Bind(counts or {name: 0 for name in states})
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration.sa, "inspect", lambda _: _Inspector(states))
    monkeypatch.setattr(migration.op, "create_table", lambda *args, **kwargs: calls.append(("create", args, kwargs)))
    monkeypatch.setattr(migration.op, "drop_table", lambda *args, **kwargs: calls.append(("drop", args, kwargs)))
    return bind, calls


def test_upgrade_creates_only_where_task_exists_with_task_fk(monkeypatch):
    migration = _migration()
    states = {"qc": {"task": True}, "public": {"task": False}}
    _, calls = _setup(monkeypatch, migration, states)
    migration.upgrade()
    assert migration.revision == "20260923_000049"
    assert migration.down_revision == "20260923_000048"
    assert len(calls) == 1
    _, args, kwargs = calls[0]
    assert args[0] == "task_qc_runs" and kwargs["schema"] == "qc"
    assert any(isinstance(arg, sa.ForeignKeyConstraint) and
               next(iter(arg.elements)).target_fullname == "qc.qc_tasks.id" for arg in args[1:])
    assert any(isinstance(arg, sa.UniqueConstraint) and arg.name == "uq_task_qc_runs_job" for arg in args[1:])
    assert not any(isinstance(arg, sa.ForeignKeyConstraint) and
                   "custom_qc_batch_jobs" in str(arg) for arg in args[1:])


def test_upgrade_creates_both_schema_tables_with_local_task_references(monkeypatch):
    migration = _migration()
    states = {"qc": {"task": True}, "public": {"task": True}}
    _, calls = _setup(monkeypatch, migration, states)
    migration.upgrade()
    assert [kwargs["schema"] for _, _, kwargs in calls] == ["qc", "public"]
    for _, args, kwargs in calls:
        foreign_key = next(arg for arg in args if isinstance(arg, sa.ForeignKeyConstraint))
        assert next(iter(foreign_key.elements)).target_fullname == f'{kwargs["schema"]}.qc_tasks.id'


def test_upgrade_preflights_both_schemas_before_ddl(monkeypatch):
    migration = _migration()
    states = {"qc": {"task": True}, "public": {"task": True, "run": True,
                                                  "table": _run_table(drift=("job_id", {"nullable": True}))}}
    _, calls = _setup(monkeypatch, migration, states)
    with pytest.raises(RuntimeError, match="public.task_qc_runs 列合同不符"):
        migration.upgrade()
    assert calls == []


def test_upgrade_accepts_matching_existing_table_and_rejects_wrong_fk(monkeypatch):
    migration = _migration()
    states = {"qc": {"task": True, "run": True, "table": _run_table()},
              "public": {"task": True, "run": True, "table": _run_table()}}
    _, calls = _setup(monkeypatch, migration, states)
    migration.upgrade()
    assert calls == []
    states["public"]["table"]["fks"][0]["referred_schema"] = "other"
    with pytest.raises(RuntimeError, match="任务外键合同不符"):
        migration.upgrade()
    assert calls == []


def test_upgrade_rejects_orphan_run_table(monkeypatch):
    migration = _migration()
    states = {"qc": {"task": False, "run": True, "table": _run_table()},
              "public": {"task": False}}
    _, calls = _setup(monkeypatch, migration, states)
    with pytest.raises(RuntimeError, match="qc.task_qc_runs 存在但 qc_tasks 不存在"):
        migration.upgrade()
    assert calls == []


def test_downgrade_protects_history_in_either_schema(monkeypatch):
    migration = _migration()
    states = {"qc": {"task": True, "run": True, "table": _run_table()},
              "public": {"task": True, "run": True, "table": _run_table()}}
    bind, calls = _setup(monkeypatch, migration, states, {"qc": 0, "public": 1})
    with pytest.raises(RuntimeError, match="public.task_qc_runs 已有运行历史"):
        migration.downgrade()
    assert calls == []
    assert bind.queries[:2] == [
        'LOCK TABLE "qc"."task_qc_runs" IN ACCESS EXCLUSIVE MODE',
        'LOCK TABLE "public"."task_qc_runs" IN ACCESS EXCLUSIVE MODE',
    ]


def test_downgrade_drops_empty_tables_in_reverse_order(monkeypatch):
    migration = _migration()
    states = {"qc": {"task": True, "run": True, "table": _run_table()},
              "public": {"task": True, "run": True, "table": _run_table()}}
    _, calls = _setup(monkeypatch, migration, states)
    migration.downgrade()
    assert [(kind, args[0], kwargs["schema"]) for kind, args, kwargs in calls] == [
        ("drop", "task_qc_runs", "public"), ("drop", "task_qc_runs", "qc")]


def test_orm_allows_two_runs_but_rejects_duplicate_job_and_invalid_number():
    from app.database.models.qc import QCTask, QCTaskQCRun

    engine = sa.create_engine("sqlite://")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        QCTask.__table__.create(connection)
        QCTaskQCRun.__table__.create(connection)
        connection.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="TASK-1", task_name="任务", task_type="one_time"))
        connection.execute(QCTaskQCRun.__table__.insert(), [
            {"task_id": "task-1", "run_number": 1, "job_id": "job-1", "triggered_by": "user-1"},
            {"task_id": "task-1", "run_number": 2, "job_id": "job-2", "triggered_by": "user-1"},
        ])
        assert connection.execute(sa.select(sa.func.count()).select_from(QCTaskQCRun.__table__)).scalar_one() == 2
        with pytest.raises(IntegrityError):
            connection.execute(QCTaskQCRun.__table__.insert().values(
                task_id="task-1", run_number=3, job_id="job-1", triggered_by="user-1"))
        with pytest.raises(IntegrityError):
            connection.execute(QCTaskQCRun.__table__.insert().values(
                task_id="task-1", run_number=0, job_id="job-3", triggered_by="user-1"))
