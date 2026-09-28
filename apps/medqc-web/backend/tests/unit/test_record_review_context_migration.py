"""迁移 58 审核上下文合同：只用 fake inspector 与 SQLite，不连接真实数据库。"""

from __future__ import annotations

import copy
import importlib.util
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260926_000058_record_review_context.py"
    spec = importlib.util.spec_from_file_location("record_review_context_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _type(kind, length):
    if kind is sa.String:
        return sa.String(length)
    if kind is sa.Text:
        return sa.Text()
    if kind is sa.Integer:
        return sa.Integer()
    return sa.DateTime()


def schema_data(module, *, final):
    columns = module.FINAL_COLUMNS if final else module.BASE_COLUMNS
    checks = module.FINAL_CHECKS if final else module.BASE_CHECKS
    return {
        "exists": True,
        "columns": {
            name: {
                "type": _type(kind, length), "nullable": nullable,
                # PostgreSQL 反射出的服务端默认值带类型转换
                "default": None if default is None else f"'{default}'::character varying",
            }
            for name, (kind, length, nullable, default) in columns.items()
        },
        "pk": {"name": module.PK_NAME, "constrained_columns": ["id"]},
        "uniques": [
            {"name": module.RESULT_UNIQUE_NAME, "column_names": list(module.RESULT_UNIQUE_COLUMNS)},
            {"name": module.REQUEST_UNIQUE_NAME, "column_names": ["request_id"]},
        ],
        "indexes": [
            {"name": module.RESULT_UNIQUE_NAME, "column_names": list(module.RESULT_UNIQUE_COLUMNS),
             "unique": True, "duplicates_constraint": module.RESULT_UNIQUE_NAME},
            {"name": module.CASE_INDEX_NAME, "column_names": list(module.CASE_INDEX_COLUMNS), "unique": False},
        ],
        "checks": dict(checks),
    }


def state(module, *, final):
    return {schema: schema_data(module, final=final) for schema in module.SCHEMAS}


class Inspector:
    def __init__(self, data):
        self.data = data

    def has_table(self, table, schema):
        return self.data[schema]["exists"]

    def get_columns(self, table, schema):
        return [dict(name=name, **copy.copy(value)) for name, value in self.data[schema]["columns"].items()]

    def get_pk_constraint(self, table, schema):
        return self.data[schema]["pk"]

    def get_unique_constraints(self, table, schema):
        return self.data[schema]["uniques"]

    def get_indexes(self, table, schema):
        return self.data[schema]["indexes"]

    def get_check_constraints(self, table, schema):
        return [{"name": name, "sqltext": sql} for name, sql in self.data[schema]["checks"].items()]


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql.startswith("LOCK TABLE"):
            return None
        for schema, count in self.counts.items():
            if f'"{schema}"."qc_record_reviews"' in sql and "review_context <> 'task'" in sql:
                return Scalar(count)
        raise AssertionError(f"unexpected query: {sql}")


OPERATIONS = ("add_column", "alter_column", "create_check_constraint", "drop_constraint", "drop_column")


def fake(monkeypatch, module, data, counts=None):
    calls = []
    bind = Bind(counts)
    monkeypatch.setattr(module.sa, "inspect", lambda _: Inspector(data))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    for operation in OPERATIONS:
        monkeypatch.setattr(
            module.op, operation,
            lambda *args, _operation=operation, **kwargs: calls.append((_operation, args, kwargs)),
        )
    return bind, calls


def test_upgrade_adds_context_and_relaxes_task_fields_in_both_schemas(monkeypatch):
    module = migration()
    assert module.down_revision == "20260926_000057"
    _, calls = fake(monkeypatch, module, state(module, final=False))
    module.upgrade()
    for schema in module.SCHEMAS:
        ops = [(name, args, kwargs) for name, args, kwargs in calls if kwargs["schema"] == schema]
        add = [args for name, args, _ in ops if name == "add_column"]
        assert len(add) == 1
        column = add[0][1]
        assert column.name == "review_context" and not column.nullable
        assert isinstance(column.type, sa.String) and column.type.length == 16
        assert column.server_default.arg == "task"  # 既有行回填为 task
        altered = {args[1]: kwargs["nullable"] for name, args, kwargs in ops if name == "alter_column"}
        assert altered == {"task_id": True, "task_record_id": True, "run_number": True}
        created = {args[0]: args[2] for name, args, _ in ops if name == "create_check_constraint"}
        assert created == module.CONTEXT_CHECKS
    assert [kwargs["schema"] for name, _, kwargs in calls if name == "add_column"] == ["qc", "public"]


def test_upgrade_is_idempotent_when_fully_upgraded(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, state(module, final=True))
    module.upgrade()
    assert calls == []


def test_postgres_reflected_context_checks_match_contract(monkeypatch):
    module = migration()
    data = state(module, final=True)
    for schema in module.SCHEMAS:
        data[schema]["checks"]["ck_qc_record_reviews_context"] = (
            "((review_context)::text = ANY ((ARRAY['task'::character varying, "
            "'workspace'::character varying])::text[]))"
        )
        data[schema]["checks"]["ck_qc_record_reviews_context_fields"] = (
            "((((review_context)::text = 'task'::text) AND (task_id IS NOT NULL) AND "
            "(task_record_id IS NOT NULL) AND (run_number IS NOT NULL)) OR "
            "(((review_context)::text = 'workspace'::text) AND (task_id IS NULL) AND "
            "(task_record_id IS NULL) AND (run_number IS NULL)))"
        )
    _, calls = fake(monkeypatch, module, data)
    module.upgrade()
    assert calls == []


def test_upgrade_rejects_partial_upgrade_across_schemas(monkeypatch):
    module = migration()
    data = state(module, final=False)
    data["qc"] = schema_data(module, final=True)
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError, match="升级状态不一致"):
        module.upgrade()
    assert calls == []


def test_upgrade_rejects_missing_table(monkeypatch):
    module = migration()
    data = state(module, final=False)
    data["public"] = {"exists": False}
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError, match="迁移 57"):
        module.upgrade()
    assert calls == []


@pytest.mark.parametrize("drift", [
    "context_without_checks", "context_nullable", "context_wrong_default", "task_id_still_not_null",
    "extra_check", "run_number_check_rewritten", "bad_index", "bad_unique", "extra_column",
])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    module = migration()
    data = state(module, final=True)
    target = data["public"]
    if drift == "context_without_checks":
        for name in module.CONTEXT_CHECKS:
            del target["checks"][name]
    elif drift == "context_nullable":
        target["columns"]["review_context"]["nullable"] = True
    elif drift == "context_wrong_default":
        target["columns"]["review_context"]["default"] = "'workspace'::character varying"
    elif drift == "task_id_still_not_null":
        target["columns"]["task_id"]["nullable"] = False
    elif drift == "extra_check":
        target["checks"]["ck_extra"] = "stage IS NOT NULL"
    elif drift == "run_number_check_rewritten":
        target["checks"]["ck_qc_record_reviews_run_number_positive"] = "run_number >= 0"
    elif drift == "bad_index":
        target["indexes"][1]["column_names"] = ["visit_id"]
    elif drift == "bad_unique":
        target["uniques"][0]["column_names"] = ["job_id", "envelope_id"]
    else:
        target["columns"]["extra"] = {"type": sa.Text(), "nullable": True, "default": None}
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []


def test_downgrade_rejects_workspace_rows(monkeypatch):
    module = migration()
    bind, calls = fake(monkeypatch, module, state(module, final=True), counts={"qc": 0, "public": 1})
    with pytest.raises(RuntimeError, match="public.qc_record_reviews.*workspace.*拒绝降级"):
        module.downgrade()
    assert len([query for query in bind.queries if query.startswith("LOCK TABLE")]) == 2
    assert calls == []


def test_downgrade_restores_base_contract_when_only_task_rows(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, state(module, final=True), counts={"qc": 0, "public": 0})
    module.downgrade()
    assert [kwargs["schema"] for name, _, kwargs in calls if name == "drop_column"] == ["public", "qc"]
    for schema in module.SCHEMAS:
        ops = [(name, args, kwargs) for name, args, kwargs in calls if kwargs["schema"] == schema]
        assert {args[0] for name, args, _ in ops if name == "drop_constraint"} == set(module.CONTEXT_CHECKS)
        assert {args[1]: kwargs["nullable"] for name, args, kwargs in ops if name == "alter_column"} == {
            "task_id": False, "task_record_id": False, "run_number": False,
        }
        # 先删 CHECK、再收紧 NOT NULL、最后删列
        names = [name for name, _, _ in ops]
        assert names.index("drop_column") == len(names) - 1
        assert max(i for i, n in enumerate(names) if n == "drop_constraint") < names.index("alter_column")


def test_downgrade_is_noop_when_not_upgraded(monkeypatch):
    module = migration()
    bind, calls = fake(monkeypatch, module, state(module, final=False))
    module.downgrade()
    assert calls == [] and bind.queries == []


def test_downgrade_rejects_partial_upgrade(monkeypatch):
    module = migration()
    data = state(module, final=True)
    data["qc"] = schema_data(module, final=False)
    _, calls = fake(monkeypatch, module, data, counts={"qc": 0, "public": 0})
    with pytest.raises(RuntimeError):
        module.downgrade()
    assert calls == []


def test_final_checks_enforce_context_contract_in_sqlite():
    module = migration()
    connection = sqlite3.connect(":memory:")
    checks = ", ".join(f"CONSTRAINT {name} CHECK ({sql})" for name, sql in module.FINAL_CHECKS.items())
    columns = ", ".join(module.FINAL_COLUMNS)
    connection.execute(f"CREATE TABLE t ({columns}, {checks})")
    base = {name: "x" for name in module.FINAL_COLUMNS}
    base.update(run_number=1, stage="initial", decision="approved", reason=None,
                created_at="2026-09-26", review_context="task")
    counter = iter(range(1000))

    def insert(**changes):
        row = {**base, "id": f"id-{next(counter)}", **changes}
        connection.execute(
            f"INSERT INTO t ({columns}) VALUES ({', '.join('?' for _ in row)})", list(row.values()),
        )

    workspace = {"review_context": "workspace", "task_id": None, "task_record_id": None, "run_number": None}
    insert()
    # workspace 行：三字段均为 NULL 时，run_number 正数与非空白 CHECK 按 SQL 语义通过
    insert(**workspace)
    for changes in (
        {"review_context": "other"},
        {"task_id": None},  # task 行缺任务字段
        {"run_number": None},
        {**workspace, "task_id": "task-1"},  # workspace 行带任务字段
        {**workspace, "run_number": 1},
        {**workspace, "visit_id": " "},  # 其他列非空白约束仍生效
        {"run_number": 0},
    ):
        with pytest.raises(sqlite3.IntegrityError):
            insert(**changes)
    assert connection.execute("SELECT count(*) FROM t").fetchone()[0] == 2
    connection.close()


def test_model_matches_final_contract():
    from app.database.models.qc import QCRecordReview

    module = migration()
    scene_path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20260928_000067_record_review_scene.py"
    )
    scene_spec = importlib.util.spec_from_file_location(
        "record_review_scene_migration_for_58", scene_path,
    )
    scene = importlib.util.module_from_spec(scene_spec)
    scene_spec.loader.exec_module(scene)
    table = QCRecordReview.__table__
    assert set(table.c.keys()) == set(module.FINAL_COLUMNS) | {scene.COLUMN}
    for name, (kind, length, nullable, default) in module.FINAL_COLUMNS.items():
        column = table.c[name]
        assert isinstance(column.type, kind) and column.nullable is nullable
        if length is not None:
            assert column.type.length == length
        assert (column.server_default.arg if column.server_default is not None else None) == default
    checks = {
        item.name: module.normalized_check(str(item.sqltext))
        for item in table.constraints if isinstance(item, sa.CheckConstraint)
    }
    assert checks == {
        name: module.normalized_check(sql)
        for name, sql in {**module.FINAL_CHECKS, scene.CHECK: scene.CHECK_SQL}.items()
    }
