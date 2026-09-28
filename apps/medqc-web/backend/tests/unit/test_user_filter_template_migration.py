"""迁移 59 用户筛选模板表合同：只用 fake inspector 与 SQLite，不连接真实数据库。"""

from __future__ import annotations

import copy
import importlib.util
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260927_000059_user_filter_templates.py"
    spec = importlib.util.spec_from_file_location("user_filter_template_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _type(spec):
    kind, length, _, _ = spec
    if kind is sa.String:
        return sa.String(length)
    if kind is sa.Text:
        return sa.Text()
    if kind is sa.Boolean:
        return sa.Boolean()
    if kind is sa.Integer:
        return sa.Integer()
    return sa.DateTime()


# PostgreSQL 反射出的服务端默认值形态
_PG_DEFAULTS = {"false": "false", "1": "1"}


def deployed_schema(module):
    return {
        "exists": True,
        "columns": {
            name: {"type": _type(spec), "nullable": spec[2], "default": _PG_DEFAULTS.get(spec[3])}
            for name, spec in module.COLUMNS.items()
        },
        "pk": {"name": module.PK_NAME, "constrained_columns": ["id"]},
        "uniques": [
            {"name": module.NAME_UNIQUE_NAME, "column_names": list(module.NAME_UNIQUE_COLUMNS)},
        ],
        "indexes": [
            # PostgreSQL 反射会带出唯一约束支撑索引
            {"name": module.NAME_UNIQUE_NAME, "column_names": list(module.NAME_UNIQUE_COLUMNS),
             "unique": True, "duplicates_constraint": module.NAME_UNIQUE_NAME},
            # 部分唯一索引：SQLAlchemy 2.0 PG 方言把 WHERE 子句放在 dialect_options
            {"name": module.DEFAULT_INDEX_NAME, "column_names": list(module.DEFAULT_INDEX_COLUMNS),
             "unique": True, "dialect_options": {"postgresql_where": "is_default"}},
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
            if f'"{schema}"."qc_user_filter_templates"' in sql:
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


def test_upgrade_creates_table_and_partial_index_in_both_schemas(monkeypatch):
    module = migration()
    assert module.revision == "20260927_000059"
    assert module.down_revision == "20260926_000058"
    _, calls = fake(monkeypatch, module, state(module, deployed=False))
    module.upgrade()
    creates = [(args, kwargs) for name, args, kwargs in calls if name == "create_table"]
    assert [kwargs["schema"] for _, kwargs in creates] == ["qc", "public"]
    args = creates[0][0]
    columns = {item.name: item for item in args if isinstance(item, sa.Column)}
    assert set(columns) == set(module.COLUMNS)
    assert all(not column.nullable for column in columns.values())
    assert str(columns["is_default"].server_default.arg) == "false"
    assert str(columns["version"].server_default.arg) == "1"
    constraint_names = {item.name for item in args if isinstance(item, sa.Constraint)}
    assert {module.PK_NAME, module.NAME_UNIQUE_NAME, *module.CHECKS} <= constraint_names
    indexes = [(args, kwargs) for name, args, kwargs in calls if name == "create_index"]
    assert [(args[0], args[2], kwargs["schema"], kwargs["unique"]) for args, kwargs in indexes] == [
        (module.DEFAULT_INDEX_NAME, module.DEFAULT_INDEX_COLUMNS, "qc", True),
        (module.DEFAULT_INDEX_NAME, module.DEFAULT_INDEX_COLUMNS, "public", True),
    ]
    assert str(indexes[0][1]["postgresql_where"]) == "is_default"


def test_upgrade_is_idempotent_when_fully_deployed(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, state(module, deployed=True))
    module.upgrade()
    assert calls == []


def test_postgres_reflected_checks_and_defaults_match_contract(monkeypatch):
    """PG 反射形态：IN → = ANY(ARRAY[...])、btrim → TRIM(BOTH ... FROM col)、默认值带括号/类型。"""
    module = migration()
    data = state(module, deployed=True)
    ws = "' \t\n\r\f\v'::text"
    for schema in module.SCHEMAS:
        checks = data[schema]["checks"]
        checks["ck_qc_user_filter_templates_page_key"] = (
            "((page_key)::text = ANY ((ARRAY['v5_records_inpatient'::character varying, "
            "'v5_records_discharged'::character varying])::text[]))"
        )
        checks["ck_qc_user_filter_templates_owner_nonblank"] = (
            f"(TRIM(BOTH {ws} FROM owner_id) <> ''::text)"
        )
        checks["ck_qc_user_filter_templates_name_nonblank"] = f"(btrim((name)::text, {ws}) <> ''::text)"
        checks["ck_qc_user_filter_templates_version_positive"] = "(version > 0)"
        data[schema]["columns"]["version"]["default"] = "(1)"
    _, calls = fake(monkeypatch, module, data)
    module.upgrade()
    assert calls == []


def test_normalized_check_accepts_postgres_reflected_trim_form():
    module = migration()
    declared = module.CHECKS["ck_qc_user_filter_templates_name_nonblank"]
    reflected = "(TRIM(BOTH ' \t\n\r\f\v'::text FROM name) <> ''::text)"
    assert module.normalized_check(declared) == module.normalized_check(reflected)


@pytest.mark.parametrize("reflected", [
    "is_default",
    "(is_default)",
    "(is_default = true)",
    "\"is_default\"",
])
def test_partial_index_predicate_reflected_forms_accepted(monkeypatch, reflected):
    module = migration()
    data = state(module, deployed=True)
    for schema in module.SCHEMAS:
        data[schema]["indexes"][1]["dialect_options"] = {"postgresql_where": reflected}
    _, calls = fake(monkeypatch, module, data)
    module.upgrade()
    assert calls == []


def test_partial_index_predicate_top_level_key_accepted(monkeypatch):
    module = migration()
    data = state(module, deployed=True)
    for schema in module.SCHEMAS:
        index = data[schema]["indexes"][1]
        index.pop("dialect_options")
        index["postgresql_where"] = "is_default"
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
    "extra_column", "missing_column", "nullable_name", "short_owner", "tz_created_at",
    "bool_default_true", "version_no_default", "bigint_version", "bad_pk", "missing_unique",
    "bad_unique", "missing_default_index", "default_index_not_partial",
    "default_index_wrong_predicate", "default_index_not_unique", "default_index_wrong_columns",
    "extra_index", "missing_check", "bad_check",
])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    module = migration()
    data = state(module, deployed=True)
    target = data["public"]
    default_index = target["indexes"][1]
    if drift == "extra_column":
        target["columns"]["extra"] = {"type": sa.Text(), "nullable": True, "default": None}
    elif drift == "missing_column":
        del target["columns"]["filters_json"]
    elif drift == "nullable_name":
        target["columns"]["name"]["nullable"] = True
    elif drift == "short_owner":
        target["columns"]["owner_id"]["type"] = sa.String(36)
    elif drift == "tz_created_at":
        target["columns"]["created_at"]["type"] = sa.DateTime(timezone=True)
    elif drift == "bool_default_true":
        target["columns"]["is_default"]["default"] = "true"
    elif drift == "version_no_default":
        target["columns"]["version"]["default"] = None
    elif drift == "bigint_version":
        target["columns"]["version"]["type"] = sa.BigInteger()
    elif drift == "bad_pk":
        target["pk"] = {"name": module.PK_NAME, "constrained_columns": ["owner_id"]}
    elif drift == "missing_unique":
        target["uniques"] = []
    elif drift == "bad_unique":
        target["uniques"][0]["column_names"] = ["owner_id", "name"]
    elif drift == "missing_default_index":
        target["indexes"] = target["indexes"][:1]
    elif drift == "default_index_not_partial":
        default_index["dialect_options"] = {}
    elif drift == "default_index_wrong_predicate":
        default_index["dialect_options"] = {"postgresql_where": "NOT is_default"}
    elif drift == "default_index_not_unique":
        default_index["unique"] = False
    elif drift == "default_index_wrong_columns":
        default_index["column_names"] = ["owner_id"]
    elif drift == "extra_index":
        target["indexes"].append({"name": "ix_extra", "column_names": ["name"], "unique": False})
    elif drift == "missing_check":
        del target["checks"]["ck_qc_user_filter_templates_version_positive"]
    else:
        target["checks"]["ck_qc_user_filter_templates_page_key"] = "page_key IN ('v5_records_inpatient')"
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []


def test_downgrade_rejects_rows_in_either_schema(monkeypatch):
    module = migration()
    bind, calls = fake(monkeypatch, module, state(module, deployed=True), counts={"qc": 0, "public": 3})
    with pytest.raises(RuntimeError, match="public.qc_user_filter_templates.*拒绝降级"):
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


def test_check_constraints_enforce_contract_in_sqlite():
    module = migration()
    connection = sqlite3.connect(":memory:")
    checks = ", ".join(f"CONSTRAINT {name} CHECK ({sql})" for name, sql in module.CHECKS.items())
    columns = ", ".join(module.COLUMNS)
    connection.execute(f"CREATE TABLE t ({columns}, {checks})")
    base = {
        "id": "t-1", "owner_id": "u-1", "page_key": "v5_records_inpatient", "name": "模板",
        "filters_json": "{}", "is_default": 0, "version": 1,
        "created_at": "2026-09-27", "updated_at": "2026-09-27",
    }

    def insert(**changes):
        row = {**base, **changes}
        connection.execute(
            f"INSERT INTO t ({columns}) VALUES ({', '.join('?' for _ in row)})", list(row.values()),
        )

    insert()
    insert(id="t-2", page_key="v5_records_discharged")
    for changes in (
        {"page_key": "other"}, {"owner_id": " \t"}, {"name": "\n "}, {"version": 0},
    ):
        with pytest.raises(sqlite3.IntegrityError):
            insert(**changes)
    assert connection.execute("SELECT count(*) FROM t").fetchone()[0] == 2
    connection.close()


def test_model_matches_migration_contract():
    from app.database.models.qc import QCUserFilterTemplate

    module = migration()
    outpatient_module_path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20260927_000063_outpatient_filter_templates.py"
    )
    spec = importlib.util.spec_from_file_location("outpatient_filter_template_migration", outpatient_module_path)
    outpatient_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(outpatient_module)
    table = QCUserFilterTemplate.__table__
    assert table.name == module.TABLE
    assert set(table.c.keys()) == set(module.COLUMNS)
    for name, (kind, length, nullable, default) in module.COLUMNS.items():
        column = table.c[name]
        assert isinstance(column.type, kind) and column.nullable is nullable
        if length is not None:
            assert column.type.length == length
        actual_default = None if column.server_default is None else str(column.server_default.arg)
        assert actual_default == default
    checks = {
        item.name: module.normalized_check(str(item.sqltext))
        for item in table.constraints if isinstance(item, sa.CheckConstraint)
    }
    expected_checks = {name: module.normalized_check(sql) for name, sql in module.CHECKS.items()}
    expected_checks[outpatient_module.CHECK_NAME] = module.normalized_check(
        outpatient_module.check_sql(outpatient_module.NEW_PAGE_KEYS)
    )
    assert checks == expected_checks
    uniques = {
        item.name: [column.name for column in item.columns]
        for item in table.constraints if isinstance(item, sa.UniqueConstraint)
    }
    assert uniques == {module.NAME_UNIQUE_NAME: module.NAME_UNIQUE_COLUMNS}
    indexes = {item.name: item for item in table.indexes}
    assert set(indexes) == {module.DEFAULT_INDEX_NAME}
    index = indexes[module.DEFAULT_INDEX_NAME]
    assert [column.name for column in index.columns] == module.DEFAULT_INDEX_COLUMNS
    assert index.unique
    assert str(index.dialect_options["postgresql"]["where"]) == module.DEFAULT_INDEX_PREDICATE


def test_model_partial_unique_index_allows_one_default_per_owner_page_in_sqlite():
    from app.database.models.qc import QCUserFilterTemplate

    engine = sa.create_engine("sqlite://")
    QCUserFilterTemplate.__table__.create(engine)
    table = QCUserFilterTemplate.__table__
    now = sa.func.current_timestamp()

    def row(template_id, name, is_default, page_key="v5_records_inpatient", owner="u-1"):
        return dict(id=template_id, owner_id=owner, page_key=page_key, name=name,
                    filters_json="{}", is_default=is_default, created_at=now, updated_at=now)

    with engine.begin() as connection:
        connection.execute(table.insert().values(**row("a", "A", True)))
        connection.execute(table.insert().values(**row("b", "B", False)))
        connection.execute(table.insert().values(**row("c", "C", False)))
        connection.execute(table.insert().values(**row("d", "D", True, page_key="v5_records_discharged")))
        connection.execute(table.insert().values(**row(
            "outpatient", "门急诊", True, page_key="v5_records_outpatient_emergency",
        )))
        connection.execute(table.insert().values(**row("e", "A", True, owner="u-2")))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(table.insert().values(**row("f", "F", True)))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as connection:
            connection.execute(table.insert().values(**row("g", "A", False)))
    with engine.connect() as connection:
        versions = connection.execute(sa.select(table.c.version, table.c.is_default).where(table.c.id == "b")).one()
    assert tuple(versions) == (1, False)
    engine.dispose()
