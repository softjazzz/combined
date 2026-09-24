"""现代质控身份迁移的隔离合同测试，不连接数据库。"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260924_000053_qc_identity_source.py"
    spec = importlib.util.spec_from_file_location("qc_identity_source_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _state(module, *, modern=False):
    states = {}
    for schema in module.SCHEMAS:
        for table in module.TABLES:
            columns = {}
            if (schema, table) in module.PRESERVED_COORDINATES:
                columns = {
                    "institute_id": {"type": sa.Text(), "nullable": True, "default": "'LX001'::text"},
                    "patient_id": {"type": sa.Text(), "nullable": True, "default": None},
                    "visit_id": {"type": sa.Text(), "nullable": True, "default": None},
                }
            checks = {}
            indexes = {}
            if modern:
                columns.update({
                    "identity_version": {"type": sa.SmallInteger(), "nullable": True, "default": None},
                    "source_key": {"type": sa.String(64), "nullable": True, "default": None},
                })
                for name in module.COORDINATES:
                    columns.setdefault(name, {"type": sa.Text(), "nullable": True, "default": None})
                checks[module._check_name(table)] = module._check_sql()
                indexes[module._index_name(table)] = {
                    "column_names": ["source_key", *module.COORDINATES, *module.INDEX_SUFFIX[table]],
                    "unique": False, "dialect_options": {"postgresql_where": "(identity_version = 1)"},
                }
            states[(schema, table)] = {"exists": True, "columns": columns, "checks": checks, "indexes": indexes}
    return states


class _Inspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        return self.states[(schema, table)]["exists"]

    def get_columns(self, table, schema):
        return [dict(name=name, **value) for name, value in self.states[(schema, table)]["columns"].items()]

    def get_check_constraints(self, table, schema):
        return [
            {"name": name, "sqltext": expression}
            for name, expression in self.states[(schema, table)]["checks"].items()
        ]

    def get_indexes(self, table, schema):
        return [dict(name=name, **value) for name, value in self.states[(schema, table)]["indexes"].items()]


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
        key = next(key for key in self.populated if f'"{key[0]}"."{key[1]}"' in sql)
        return _Scalar(self.populated[key])


def _fake(monkeypatch, module, states, populated=None):
    calls = []
    bind = _Bind(populated or {key: 0 for key in states})
    monkeypatch.setattr(module.sa, "inspect", lambda _: _Inspector(states))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    for operation in ("add_column", "create_check_constraint", "create_index", "drop_index", "drop_constraint", "drop_column"):
        monkeypatch.setattr(
            module.op, operation,
            lambda *args, _operation=operation, **kwargs: calls.append((_operation, args, kwargs)),
        )
    return bind, calls


def test_upgrade_preserves_legacy_partial_identity_and_adds_only_missing_columns(monkeypatch):
    module = _migration()
    states = _state(module)
    bind, calls = _fake(monkeypatch, module, states)
    module.upgrade()
    assert module.down_revision == "20260924_000052"
    assert bind.queries == []
    added = [(args[0], args[1].name, kw["schema"], args[1]) for op, args, kw in calls if op == "add_column"]
    assert len(added) == 27
    assert [(table, name) for table, name, schema, _ in added if (schema, table) == ("qc", "qc_results")] == [
        ("qc_results", "identity_version"), ("qc_results", "source_key"),
    ]
    assert all(column.nullable and column.server_default is None for _, _, _, column in added)
    indexes = [(args, kw) for op, args, kw in calls if op == "create_index"]
    assert len(indexes) == 6
    assert all(str(kw["postgresql_where"]) == "identity_version = 1" for _, kw in indexes)
    assert len([op for op, _, _ in calls if op == "create_check_constraint"]) == 6


def test_modern_check_rejects_blank_and_partial_rows_but_allows_legacy():
    module = _migration()
    expression = module._check_sql()
    assert "identity_version IS NULL AND source_key IS NULL" in expression
    assert "identity_version IS NOT NULL AND identity_version = 1" in expression
    assert "identity_version = 1" in expression
    for name in ("source_key", *module.COORDINATES):
        assert f"{name} IS NOT NULL AND btrim({name}, {module.TRIM_CHARS_SQL}) <> ''" in expression
    check = sa.CheckConstraint(expression)
    assert str(check.sqltext.compile(dialect=postgresql.dialect())) == expression
    conn = sqlite3.connect(":memory:")
    conn.create_function("chr", 1, chr)
    conn.create_function("btrim", 2, lambda value, chars: value.strip(chars) if value is not None else None)
    conn.execute(
        "CREATE TABLE sample (identity_version SMALLINT, source_key TEXT, "
        "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
        f"CONSTRAINT modern_identity CHECK ({expression}))"
    )
    conn.execute("INSERT INTO sample (institute_id) VALUES ('LX001')")
    conn.execute(
        "INSERT INTO sample VALUES (?, ?, ?, ?, ?)",
        (1, "settlement_qc", "LX001", "P01", "V01"),
    )
    for invalid in (
        (None, "settlement_qc", "LX001", "P01", "V01"),
        (1, None, "LX001", "P01", "V01"),
        (1, " ", "LX001", "P01", "V01"),
        (1, "\r\n\t", "LX001", "P01", "V01"),
        (1, "settlement_qc", "LX001", "P01", None),
        (1, "settlement_qc", "LX001", "\t", "V01"),
        (1, "settlement_qc", "LX001", "\v\f", "V01"),
        (2, "settlement_qc", "LX001", "P01", "V01"),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO sample VALUES (?, ?, ?, ?, ?)", invalid)
    assert conn.execute("SELECT count(*) FROM sample").fetchone()[0] == 2
    conn.close()


def test_upgrade_accepts_fully_deployed_contract(monkeypatch):
    module = _migration()
    states = _state(module, modern=True)
    _, calls = _fake(monkeypatch, module, states)
    module.upgrade()
    assert calls == []


def test_check_reflection_accepts_extra_operand_parentheses_but_rejects_changed_grouping():
    module = _migration()
    expected = module._check_sql()
    reflected = expected.replace(
        "identity_version IS NULL", "(identity_version IS NULL)",
    ).replace(
        f"btrim(source_key, {module.TRIM_CHARS_SQL})",
        f"btrim((source_key)::text, ({module.TRIM_CHARS_SQL}))",
    )
    assert module._has_expected_check(reflected)
    changed = expected.replace(
        "(identity_version IS NULL AND source_key IS NULL) OR ",
        "((identity_version IS NULL AND source_key IS NULL) OR ",
    ) + ") AND visit_id IS NOT NULL"
    assert not module._has_expected_check(changed)
    assert not module._has_expected_check(expected + " OR identity_version = 1")
    assert not module._has_expected_check(
        expected.replace("chr(9)", "chr(8)", 1)
    )
    assert not module._has_expected_check(
        expected.replace(f"btrim(source_key, {module.TRIM_CHARS_SQL})", "btrim(source_key)")
    )


@pytest.mark.parametrize("drift", ["missing_table", "partial_schema", "partial_table", "bad_type", "bad_check", "bad_index", "unexpected_baseline"])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    module = _migration()
    states = _state(module)
    key = ("public", "notifications")
    if drift == "missing_table":
        states[key]["exists"] = False
    elif drift == "partial_schema":
        deployed = _state(module, modern=True)
        for table in module.TABLES:
            states[("qc", table)] = deployed[("qc", table)]
    elif drift == "partial_table":
        states[key]["columns"]["identity_version"] = {
            "type": sa.SmallInteger(), "nullable": True, "default": None,
        }
    elif drift == "bad_type":
        states = _state(module, modern=True)
        states[key]["columns"]["source_key"]["type"] = sa.String(32)
    elif drift == "bad_check":
        states = _state(module, modern=True)
        states[key]["checks"][module._check_name("notifications")] = "identity_version IS NULL OR source_key IS NOT NULL"
    elif drift == "bad_index":
        states = _state(module, modern=True)
        states[key]["indexes"][module._index_name("notifications")]["column_names"] = ["visit_id"]
    else:
        states[key]["columns"]["visit_id"] = {"type": sa.Text(), "nullable": True, "default": None}
    bind, calls = _fake(monkeypatch, module, states)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []
    assert bind.queries == []


def test_downgrade_locks_all_tables_and_rejects_populated_new_columns(monkeypatch):
    module = _migration()
    states = _state(module, modern=True)
    populated = {key: 0 for key in states}
    populated[("public", "qc_defects")] = 1
    bind, calls = _fake(monkeypatch, module, states, populated)
    with pytest.raises(RuntimeError, match="public.qc_defects.*拒绝降级"):
        module.downgrade()
    assert len([sql for sql in bind.queries if sql.startswith("LOCK TABLE")]) == 6
    assert calls == []
    qc_results_query = next(sql for sql in bind.queries if 'FROM "qc"."qc_results"' in sql)
    assert '"institute_id" IS NOT NULL' not in qc_results_query
    assert '"patient_id" IS NOT NULL' not in qc_results_query
    assert '"visit_id" IS NOT NULL' not in qc_results_query


def test_downgrade_removes_only_migration_owned_columns(monkeypatch):
    module = _migration()
    states = _state(module, modern=True)
    _, calls = _fake(monkeypatch, module, states)
    module.downgrade()
    dropped = [(args[0], args[1], kw["schema"]) for op, args, kw in calls if op == "drop_column"]
    assert len(dropped) == 27
    assert not any(schema == "qc" and table == "qc_results" and name in module.COORDINATES for table, name, schema in dropped)
    assert len([op for op, _, _ in calls if op == "drop_constraint"]) == 6
    assert len([op for op, _, _ in calls if op == "drop_index"]) == 6
