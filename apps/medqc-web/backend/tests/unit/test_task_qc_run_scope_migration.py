"""运行范围迁移只在假 inspector 中验证，不访问业务库。"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260924_000050_task_qc_run_scope.py"
    spec = importlib.util.spec_from_file_location("task_qc_run_scope_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Inspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        return schema in self.states

    def get_columns(self, table, schema):
        return self.states[schema]["columns"]

    def get_check_constraints(self, table, schema):
        return self.states[schema]["checks"]


class _Bind:
    def __init__(self, assigned=0):
        self.assigned = assigned
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return type("Scalar", (), {"scalar_one": lambda _: self.assigned})()


def _setup(monkeypatch, module, states, *, assigned=0):
    calls = []
    bind = _Bind(assigned)
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(module.sa, "inspect", lambda _: _Inspector(states))
    for name in ("add_column", "create_check_constraint", "drop_constraint", "drop_column"):
        monkeypatch.setattr(module.op, name, lambda *args, _name=name, **kwargs:
                            calls.append((_name, args, kwargs)))
    return bind, calls


def _state(*, scoped=False, check=True, default="'all'::character varying", sql="run_scope IN ('all', 'assigned')"):
    return {
        "columns": ([{"name": "run_scope", "type": sa.String(16), "nullable": False, "default": default}]
                    if scoped else []),
        "checks": ([{"name": "ck_task_qc_runs_scope",
                    "sqltext": sql}]
                   if scoped and check else []),
    }


def test_upgrade_adds_nonnullable_all_default_and_check_to_existing_schemas(monkeypatch):
    module = _migration()
    _, calls = _setup(monkeypatch, module, {"qc": _state(), "public": _state()})
    module.upgrade()
    assert module.down_revision == "20260923_000049"
    assert [kind for kind, _, _ in calls] == ["add_column", "create_check_constraint"] * 2
    for kind, args, kwargs in calls:
        assert kwargs["schema"] in ("qc", "public")
        if kind == "add_column":
            column = args[1]
            assert column.name == "run_scope" and not column.nullable
            assert column.server_default.arg == "all"
        else:
            assert "'assigned'" in args[2]


def test_upgrade_preflights_drift_before_any_ddl(monkeypatch):
    module = _migration()
    states = {"qc": _state(), "public": _state(scoped=True, check=False)}
    _, calls = _setup(monkeypatch, module, states)
    with pytest.raises(RuntimeError, match="合同不完整"):
        module.upgrade()
    assert calls == []


@pytest.mark.parametrize("state", [
    _state(scoped=True, default="'assigned'::character varying"),
    _state(scoped=True, sql="run_scope IN ('all', 'assigned') OR true"),
    _state(scoped=True, sql="run_scope IN ('all', 'assigned', 'other')"),
])
def test_upgrade_refuses_wrong_default_or_weakened_check(monkeypatch, state):
    module = _migration()
    _, calls = _setup(monkeypatch, module, {"qc": _state(), "public": state})
    with pytest.raises(RuntimeError, match="合同不符"):
        module.upgrade()
    assert calls == []


def test_downgrade_refuses_to_erase_assigned_history(monkeypatch):
    module = _migration()
    bind, calls = _setup(monkeypatch, module, {"qc": _state(scoped=True)}, assigned=1)
    with pytest.raises(RuntimeError, match="已有受领人运行历史"):
        module.downgrade()
    assert calls == []
    assert any("LOCK TABLE" in statement for statement in bind.statements)


def test_orm_defaults_legacy_runs_to_all_and_rejects_bad_scope():
    from sqlalchemy.exc import IntegrityError
    from app.database.models.qc import QCTask, QCTaskQCRun

    engine = sa.create_engine("sqlite://")
    QCTask.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="TASK-1", task_name="任务", task_type="one_time",
        ))
        connection.execute(QCTaskQCRun.__table__.insert().values(
            task_id="task-1", run_number=1, job_id="job-1", triggered_by="user-1",
        ))
        assert connection.execute(sa.select(QCTaskQCRun.run_scope)).scalar_one() == "all"
        with pytest.raises(IntegrityError):
            connection.execute(QCTaskQCRun.__table__.insert().values(
                task_id="task-1", run_number=2, job_id="job-2", triggered_by="user-1",
                run_scope="other",
            ))
