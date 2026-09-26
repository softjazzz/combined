"""迁移 57 病历审核表合同：只用 fake inspector 与 SQLite，不连接真实数据库。"""

from __future__ import annotations

import copy
import importlib.util
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260926_000057_record_reviews.py"
    spec = importlib.util.spec_from_file_location("record_review_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _type(spec):
    kind, length, _ = spec
    if kind is sa.String:
        return sa.String(length)
    if kind is sa.Text:
        return sa.Text()
    if kind is sa.Integer:
        return sa.Integer()
    return sa.DateTime()


def deployed_schema(module):
    return {
        "exists": True,
        "columns": {
            name: {"type": _type(spec), "nullable": spec[2], "default": None}
            for name, spec in module.COLUMNS.items()
        },
        "pk": {"name": module.PK_NAME, "constrained_columns": ["id"]},
        "uniques": [
            {"name": module.RESULT_UNIQUE_NAME, "column_names": list(module.RESULT_UNIQUE_COLUMNS)},
            {"name": module.REQUEST_UNIQUE_NAME, "column_names": ["request_id"]},
        ],
        "indexes": [
            # PostgreSQL 反射会带出唯一约束支撑索引
            {"name": module.RESULT_UNIQUE_NAME, "column_names": list(module.RESULT_UNIQUE_COLUMNS),
             "unique": True, "duplicates_constraint": module.RESULT_UNIQUE_NAME},
            {"name": module.CASE_INDEX_NAME, "column_names": list(module.CASE_INDEX_COLUMNS), "unique": False},
        ],
        "checks": dict(module.CHECKS),
    }


def state(module, *, deployed):
    return {
        schema: deployed_schema(module) if deployed else {"exists": False}
        for schema in module.SCHEMAS
    }


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
            if f'"{schema}"."qc_record_reviews"' in sql:
                return Scalar(count)
        raise AssertionError(f"unexpected query: {sql}")


def fake(monkeypatch, module, data, counts=None):
    calls = []
    bind = Bind(counts)
    monkeypatch.setattr(module.sa, "inspect", lambda _: Inspector(data))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    for operation in ("create_table", "create_index", "drop_index", "drop_table"):
        monkeypatch.setattr(
            module.op, operation,
            lambda *args, _operation=operation, **kwargs: calls.append((_operation, args, kwargs)),
        )
    return bind, calls


def test_upgrade_creates_table_and_index_in_both_schemas(monkeypatch):
    module = migration()
    assert module.down_revision == "20260925_000056"
    _, calls = fake(monkeypatch, module, state(module, deployed=False))
    module.upgrade()
    creates = [(args, kwargs) for name, args, kwargs in calls if name == "create_table"]
    assert [kwargs["schema"] for _, kwargs in creates] == ["qc", "public"]
    args = creates[0][0]
    columns = {item.name: item for item in args if isinstance(item, sa.Column)}
    assert set(columns) == set(module.COLUMNS)
    assert columns["reason"].nullable and not columns["decision"].nullable
    constraint_names = {item.name for item in args if isinstance(item, sa.Constraint)}
    assert {module.PK_NAME, module.RESULT_UNIQUE_NAME, module.REQUEST_UNIQUE_NAME, *module.CHECKS} <= constraint_names
    unique = next(item for item in args if getattr(item, "name", None) == module.RESULT_UNIQUE_NAME)
    assert [column for column in unique._pending_colargs] == module.RESULT_UNIQUE_COLUMNS
    indexes = [(args, kwargs) for name, args, kwargs in calls if name == "create_index"]
    assert [(args[0], args[2], kwargs["schema"]) for args, kwargs in indexes] == [
        (module.CASE_INDEX_NAME, module.CASE_INDEX_COLUMNS, "qc"),
        (module.CASE_INDEX_NAME, module.CASE_INDEX_COLUMNS, "public"),
    ]


def test_upgrade_is_idempotent_when_fully_deployed(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, state(module, deployed=True))
    module.upgrade()
    assert calls == []


def test_postgres_reflected_checks_match_contract(monkeypatch):
    module = migration()
    data = state(module, deployed=True)
    ws = "' \t\n\r\f\v'::text"
    for schema in module.SCHEMAS:
        checks = data[schema]["checks"]
        checks["ck_qc_record_reviews_stage"] = (
            "((stage)::text = ANY ((ARRAY['initial'::character varying, "
            "'recheck'::character varying])::text[]))"
        )
        checks["ck_qc_record_reviews_doubtful_reason"] = (
            f"(((decision)::text <> 'doubtful'::text) OR ((reason IS NOT NULL) "
            f"AND (btrim(reason, {ws}) <> ''::text)))"
        )
    _, calls = fake(monkeypatch, module, data)
    module.upgrade()
    assert calls == []


def test_upgrade_rejects_partial_deployment(monkeypatch):
    module = migration()
    data = state(module, deployed=False)
    data["qc"] = deployed_schema(module)
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError, match="部署不一致"):
        module.upgrade()
    assert calls == []


@pytest.mark.parametrize("drift", [
    "extra_column", "missing_column", "reason_not_null", "short_identity", "tz_created_at",
    "bad_pk", "missing_request_unique", "bad_result_unique", "missing_index", "bad_index",
    "missing_check", "bad_check",
])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    module = migration()
    data = state(module, deployed=True)
    target = data["public"]
    if drift == "extra_column":
        target["columns"]["extra"] = {"type": sa.Text(), "nullable": True, "default": None}
    elif drift == "missing_column":
        del target["columns"]["envelope_id"]
    elif drift == "reason_not_null":
        target["columns"]["reason"]["nullable"] = False
    elif drift == "short_identity":
        target["columns"]["visit_id"]["type"] = sa.String(100)
    elif drift == "tz_created_at":
        target["columns"]["created_at"]["type"] = sa.DateTime(timezone=True)
    elif drift == "bad_pk":
        target["pk"] = {"name": module.PK_NAME, "constrained_columns": ["request_id"]}
    elif drift == "missing_request_unique":
        target["uniques"] = target["uniques"][:1]
    elif drift == "bad_result_unique":
        target["uniques"][0]["column_names"] = ["job_id", "envelope_id"]
    elif drift == "missing_index":
        target["indexes"] = target["indexes"][:1]
    elif drift == "bad_index":
        target["indexes"][1]["column_names"] = ["institute_id", "patient_id", "visit_id"]
    elif drift == "missing_check":
        del target["checks"]["ck_qc_record_reviews_doubtful_reason"]
    else:
        target["checks"]["ck_qc_record_reviews_decision"] = "decision IN ('approved', 'doubtful', 'x')"
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []


def test_downgrade_rejects_rows_in_either_schema(monkeypatch):
    module = migration()
    bind, calls = fake(monkeypatch, module, state(module, deployed=True), counts={"qc": 0, "public": 2})
    with pytest.raises(RuntimeError, match="public.qc_record_reviews.*拒绝降级"):
        module.downgrade()
    assert len([query for query in bind.queries if query.startswith("LOCK TABLE")]) == 2
    assert calls == []


def test_downgrade_empty_drops_both(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, state(module, deployed=True), counts={"qc": 0, "public": 0})
    module.downgrade()
    assert [(name, kwargs["schema"]) for name, _, kwargs in calls] == [
        ("drop_index", "public"), ("drop_table", "public"),
        ("drop_index", "qc"), ("drop_table", "qc"),
    ]


def test_downgrade_rejects_partial_deployment(monkeypatch):
    module = migration()
    data = state(module, deployed=False)
    data["public"] = deployed_schema(module)
    _, calls = fake(monkeypatch, module, data, counts={"public": 0})
    with pytest.raises(RuntimeError):
        module.downgrade()
    assert calls == []


def test_check_constraints_enforce_contract_in_sqlite():
    module = migration()
    connection = sqlite3.connect(":memory:")
    checks = ", ".join(f"CONSTRAINT {name} CHECK ({sql})" for name, sql in module.CHECKS.items())
    columns = ", ".join(module.COLUMNS)
    connection.execute(f"CREATE TABLE t ({columns}, {checks})")
    base = {name: "x" for name in module.COLUMNS}
    base.update(run_number=1, stage="initial", decision="approved", reason=None, created_at="2026-09-26")

    def insert(**changes):
        row = {**base, **changes}
        connection.execute(
            f"INSERT INTO t ({columns}) VALUES ({', '.join('?' for _ in row)})", list(row.values()),
        )

    insert()
    insert(decision="doubtful", reason="原因", stage="recheck")
    for changes in (
        {"stage": "other"}, {"decision": "rejected"},
        {"decision": "doubtful", "reason": None}, {"decision": "doubtful", "reason": " \t\n"},
        {"visit_id": "  "}, {"envelope_id": "\t"}, {"run_number": 0},
    ):
        with pytest.raises(sqlite3.IntegrityError):
            insert(**changes)
    assert connection.execute("SELECT count(*) FROM t").fetchone()[0] == 2
    connection.close()


def test_model_matches_migration_contract():
    """模型为迁移 57 + 58 的叠加：58 新增 review_context、放开任务三字段可空、追加两条 CHECK。"""
    from app.database.models.qc import QCRecordReview

    module = migration()
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260926_000058_record_review_context.py"
    spec = importlib.util.spec_from_file_location("record_review_context_migration_for_57", path)
    context = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(context)
    table = QCRecordReview.__table__
    assert table.name == module.TABLE
    assert set(table.c.keys()) == set(module.COLUMNS) | {context.CONTEXT_COLUMN}
    for name, (kind, length, nullable) in module.COLUMNS.items():
        column = table.c[name]
        expected_nullable = True if name in context.TASK_FIELDS else nullable
        assert isinstance(column.type, kind) and column.nullable is expected_nullable
        if length is not None:
            assert column.type.length == length
    assert module.CHECKS == context.BASE_CHECKS  # 58 未改写 57 的 CHECK 原文
    checks = {
        item.name: module.normalized_check(str(item.sqltext))
        for item in table.constraints if isinstance(item, sa.CheckConstraint)
    }
    assert checks == {
        name: module.normalized_check(sql)
        for name, sql in {**module.CHECKS, **context.CONTEXT_CHECKS}.items()
    }
    uniques = {
        item.name: [column.name for column in item.columns]
        for item in table.constraints if isinstance(item, sa.UniqueConstraint)
    }
    assert uniques == {
        module.RESULT_UNIQUE_NAME: module.RESULT_UNIQUE_COLUMNS,
        module.REQUEST_UNIQUE_NAME: ["request_id"],
    }
    indexes = {item.name: [column.name for column in item.columns] for item in table.indexes}
    assert indexes == {module.CASE_INDEX_NAME: module.CASE_INDEX_COLUMNS}


@pytest.mark.parametrize("module_name", [
    "20260926_000057_record_reviews",
    "20260926_000058_record_review_context",
])
def test_normalized_check_accepts_postgres_reflected_trim_form(module_name):
    """PostgreSQL 把 btrim(col, ' ') 反射为 TRIM(BOTH ' ' FROM col)；两种写法须归一一致。"""
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(f"reflect_{module_name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    declared = "decision <> 'doubtful' OR (reason IS NOT NULL AND btrim(reason, ' \t\n') <> '')"
    reflected = "((decision)::text <> 'doubtful'::text) OR ((reason IS NOT NULL) AND (TRIM(BOTH ' \t\n' FROM reason) <> ''::text))"
    assert module.normalized_check(declared) == module.normalized_check(reflected)
