"""任务病历显式完成来源的隔离迁移测试，不连接业务数据库。"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260925_000055_task_record_completion_source.py"
    spec = importlib.util.spec_from_file_location("task_record_completion_source_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table(*, schema="public", exists=True, deployed=False, view=False):
    columns = {
        "defect_count": {
            "type": sa.Integer(),
            "nullable": deployed or schema == "qc",
            "default": None if deployed or schema == "public" else "0",
        },
    }
    checks = {}
    if deployed:
        columns["completed_run_number"] = {
            "type": sa.Integer(), "nullable": True, "default": None,
        }
        checks["ck_qc_task_records_completed_run_number_positive"] = "completed_run_number > 0"
    return {"exists": exists, "columns": columns, "checks": checks, "view": view}


class _Inspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        if table == "qc_tasks":
            return self.states[schema]["exists"]
        assert table == "qc_task_records"
        return self.states[schema]["exists"]

    def get_columns(self, table, schema):
        if table == "v_qc_task_progress":
            return [
                {"name": name, "type": sa.BigInteger() if name == "total_defects" else sa.Text()}
                for name in _migration().VIEW_COLUMNS
            ]
        return [dict(name=name, **value) for name, value in self.states[schema]["columns"].items()]

    def get_check_constraints(self, table, schema):
        return [dict(name=name, sqltext=sql) for name, sql in self.states[schema]["checks"].items()]

    def get_view_names(self, schema):
        return ["v_qc_task_progress"] if self.states[schema]["view"] else []


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
    for name in (
        "add_column", "alter_column", "create_check_constraint", "drop_constraint", "drop_column",
    ):
        monkeypatch.setattr(
            migration.op, name,
            lambda *args, _name=name, **kwargs: calls.append((_name, args, kwargs)),
        )
    return bind, calls


def test_upgrade_changes_both_schemas_without_touching_existing_values(monkeypatch):
    migration = _migration()
    states = {schema: _table(schema=schema) for schema in migration.SCHEMAS}
    bind, calls = _fakes(monkeypatch, migration, states)
    historical_values = {"legacy-zero": 0, "legacy-three": 3}

    migration.upgrade()

    assert migration.revision == "20260925_000055"
    assert migration.down_revision == "20260924_000054"
    assert historical_values == {"legacy-zero": 0, "legacy-three": 3}
    assert bind.queries == []
    assert [name for name, _, _ in calls] == [
        "add_column", "alter_column", "create_check_constraint",
        "add_column", "alter_column", "create_check_constraint",
    ]
    for schema in migration.SCHEMAS:
        added = next(args[1] for name, args, kwargs in calls if name == "add_column" and kwargs["schema"] == schema)
        assert added.name == "completed_run_number"
        assert isinstance(added.type, sa.Integer)
        assert added.nullable is True
        assert added.default is None and added.server_default is None
        altered = next(kwargs for name, args, kwargs in calls if name == "alter_column" and kwargs["schema"] == schema)
        assert altered["nullable"] is True and altered["server_default"] is None
        check = next(args for name, args, kwargs in calls if name == "create_check_constraint" and kwargs["schema"] == schema)
        assert check == (migration.CHECK_NAME, migration.TABLE, migration.CHECK_SQL)


def test_upgrade_is_idempotent_for_complete_contract(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(monkeypatch, migration, {schema: _table(deployed=True) for schema in migration.SCHEMAS})
    migration.upgrade()
    assert calls == [] and bind.queries == []


def test_upgrade_replaces_existing_view_without_disguising_unknown_count(monkeypatch):
    migration = _migration()
    states = {"qc": _table(schema="qc", view=True), "public": _table(exists=False)}
    bind, calls = _fakes(monkeypatch, migration, states)
    migration.upgrade()
    assert [name for name, _, _ in calls] == ["add_column", "alter_column", "create_check_constraint"]
    assert len(bind.queries) == 1
    assert 'CREATE OR REPLACE VIEW "qc"."v_qc_task_progress"' in bind.queries[0]
    assert "COUNT(r.id) FILTER (WHERE r.status = 'completed' AND r.defect_count IS NULL)" in bind.queries[0]
    assert "SUM(COALESCE(r.defect_count, 0))" not in bind.queries[0]


def test_upgrade_rechecks_view_when_columns_are_already_deployed(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(monkeypatch, migration, {
        "qc": _table(deployed=True, view=True), "public": _table(exists=False),
    })
    migration.upgrade()
    assert calls == []
    assert len(bind.queries) == 1
    assert "r.defect_count IS NULL" in bind.queries[0]


def test_upgrade_refuses_drifted_view_before_table_ddl(monkeypatch):
    migration = _migration()
    states = {"qc": _table(schema="qc", view=True), "public": _table(exists=False)}
    bind, calls = _fakes(monkeypatch, migration, states)
    inspector = _Inspector(states)
    original_columns = inspector.get_columns

    def drifted_columns(table, schema):
        columns = original_columns(table, schema)
        if table == migration.VIEW:
            columns[-1]["type"] = sa.Text()
        return columns

    inspector.get_columns = drifted_columns
    monkeypatch.setattr(migration.sa, "inspect", lambda _: inspector)
    with pytest.raises(RuntimeError, match="列合同漂移"):
        migration.upgrade()
    assert calls == [] and bind.queries == []


@pytest.mark.parametrize("drift", [
    "missing_defect", "qc_wrong_default", "qc_missing_default", "qc_not_null",
    "public_zero_default", "public_nullable", "partial_source", "partial_check",
    "negative_check", "source_default", "wrong_source_type", "wrong_defect_type",
])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    migration = _migration()
    qc = _table(schema="qc")
    public = _table()
    if drift == "missing_defect":
        del qc["columns"]["defect_count"]
    elif drift == "qc_wrong_default":
        qc["columns"]["defect_count"]["default"] = "1"
    elif drift == "qc_missing_default":
        qc["columns"]["defect_count"]["default"] = None
    elif drift == "qc_not_null":
        qc["columns"]["defect_count"]["nullable"] = False
    elif drift == "public_zero_default":
        public["columns"]["defect_count"]["default"] = "0"
    elif drift == "public_nullable":
        public["columns"]["defect_count"]["nullable"] = True
    elif drift == "partial_source":
        qc["columns"][migration.SOURCE_COLUMN] = {"type": sa.Integer(), "nullable": True, "default": None}
    else:
        qc = _table(deployed=True)
        if drift == "partial_check":
            del qc["checks"][migration.CHECK_NAME]
        elif drift == "negative_check":
            qc["checks"][migration.CHECK_NAME] = "completed_run_number >= 0"
        elif drift == "source_default":
            qc["columns"][migration.SOURCE_COLUMN]["default"] = "1"
        elif drift == "wrong_source_type":
            qc["columns"][migration.SOURCE_COLUMN]["type"] = sa.BigInteger()
        elif drift == "wrong_defect_type":
            qc["columns"]["defect_count"]["type"] = sa.SmallInteger()
    _, calls = _fakes(monkeypatch, migration, {"qc": qc, "public": public})
    with pytest.raises(RuntimeError):
        migration.upgrade()
    assert calls == []


def test_upgrade_rejects_mixed_or_missing_schemas(monkeypatch):
    migration = _migration()
    for states in (
        {"qc": _table(schema="qc", deployed=True), "public": _table()},
        {"qc": _table(exists=False), "public": _table(exists=False)},
    ):
        _, calls = _fakes(monkeypatch, migration, states)
        with pytest.raises(RuntimeError):
            migration.upgrade()
        assert calls == []


def test_downgrade_refuses_source_or_unknown_defect_after_locking_all_schemas(monkeypatch):
    migration = _migration()
    states = {schema: _table(deployed=True) for schema in migration.SCHEMAS}
    bind, calls = _fakes(monkeypatch, migration, states, populated={"public": 1})
    with pytest.raises(RuntimeError, match="避免丢失来源或虚构零值"):
        migration.downgrade()
    assert bind.queries[:2] == [
        'LOCK TABLE "qc"."qc_task_records" IN ACCESS EXCLUSIVE MODE',
        'LOCK TABLE "public"."qc_task_records" IN ACCESS EXCLUSIVE MODE',
    ]
    assert calls == []


def test_downgrade_restores_each_schema_baseline_only_for_lossless_state(monkeypatch):
    migration = _migration()
    _, calls = _fakes(monkeypatch, migration, {schema: _table(deployed=True) for schema in migration.SCHEMAS})
    migration.downgrade()
    assert [name for name, _, _ in calls] == [
        "drop_constraint", "drop_column", "alter_column",
        "drop_constraint", "drop_column", "alter_column",
    ]
    assert [kwargs["schema"] for _, _, kwargs in calls] == ["public"] * 3 + ["qc"] * 3
    restored = {kwargs["schema"]: kwargs for name, _, kwargs in calls if name == "alter_column"}
    assert restored["public"]["nullable"] is False
    assert restored["public"]["server_default"] is None
    assert restored["qc"]["nullable"] is True
    assert str(restored["qc"]["server_default"]) == "0"


def test_downgrade_restores_previous_view_only_when_lossless(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(monkeypatch, migration, {
        "qc": _table(deployed=True, view=True), "public": _table(exists=False),
    })
    migration.downgrade()
    assert "SUM(COALESCE(r.defect_count, 0))" in bind.queries[-1]
    assert [name for name, _, _ in calls] == ["drop_constraint", "drop_column", "alter_column"]


def test_view_total_defects_counts_only_completed_and_propagates_unknown():
    migration = _migration()
    sql = migration._total_defects_sql(completed_only=True)
    source = (Path(__file__).resolve().parents[2] / "app/database/sql/qc_views.sql").read_text(encoding="utf-8")
    for clause in (
        "COUNT(r.id) FILTER (WHERE r.status = 'completed') = 0",
        "COUNT(r.id) FILTER (WHERE r.status = 'completed' AND r.defect_count IS NULL) > 0",
        "SUM(r.defect_count) FILTER (WHERE r.status = 'completed')",
    ):
        assert clause in sql and clause in source

    with sqlite3.connect(":memory:") as conn:
        conn.execute("CREATE TABLE records (id INTEGER, status TEXT, defect_count INTEGER)")

        def aggregate():
            return conn.execute(f"SELECT {sql} FROM records r").fetchone()[0]

        assert aggregate() is None
        conn.execute("INSERT INTO records VALUES (1, 'pending', 9)")
        assert aggregate() is None
        conn.execute("INSERT INTO records VALUES (2, 'completed', 0)")
        assert aggregate() == 0
        conn.execute("INSERT INTO records VALUES (3, 'completed', NULL)")
        assert aggregate() is None
        conn.execute("UPDATE records SET defect_count = 2 WHERE id = 3")
        assert aggregate() == 2


def test_orm_and_sqlite_contract_keep_missing_count_unknown_and_run_positive():
    from app.database.models.qc import QCTaskRecord

    migration = _migration()
    table = QCTaskRecord.__table__
    for name in ("defect_count", migration.SOURCE_COLUMN):
        column = table.c[name]
        assert isinstance(column.type, sa.Integer)
        assert column.nullable is True
        assert column.default is None and column.server_default is None
    checks = {check.name: str(check.sqltext) for check in table.constraints if isinstance(check, sa.CheckConstraint)}
    assert checks[migration.CHECK_NAME] == migration.CHECK_SQL
    for dialect in (postgresql.dialect(), sqlite.dialect()):
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert "defect_count INTEGER" in ddl
        assert "completed_run_number INTEGER" in ddl
        assert migration.CHECK_SQL in ddl

    with sqlite3.connect(":memory:") as conn:
        conn.execute(
            "CREATE TABLE task_record (defect_count INTEGER, completed_run_number INTEGER, "
            f"CONSTRAINT {migration.CHECK_NAME} CHECK ({migration.CHECK_SQL}))"
        )
        conn.execute("INSERT INTO task_record DEFAULT VALUES")
        conn.execute("INSERT INTO task_record VALUES (0, 1)")
        for invalid in (0, -1):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO task_record VALUES (NULL, ?)", (invalid,))
        assert conn.execute("SELECT defect_count, completed_run_number FROM task_record").fetchall() == [
            (None, None), (0, 1),
        ]
