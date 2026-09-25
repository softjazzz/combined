"""Manual defect review migration contract, without touching a real database."""

from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260925_000056_manual_task_defect_review_fields.py"
    spec = importlib.util.spec_from_file_location("task_manual_defect_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state(module, *, deployed=False):
    data = {}
    for schema in module.SCHEMAS:
        columns = {
            "origin": {"type": sa.String(16), "nullable": True, "default": None},
            "status": {"type": sa.String(20), "nullable": False, "default": None},
        }
        checks = {"ck_qc_defects_origin": "origin IN ('auto', 'manual')"}
        if deployed:
            columns[module.REVIEW_COLUMN] = {"type": sa.String(20), "nullable": True, "default": None}
            columns[module.CREATOR_COLUMN] = {"type": sa.String(36), "nullable": True, "default": None}
            checks[module.CHECK_NAME] = module.CHECK_SQL
        data[schema] = {"exists": True, "columns": columns, "checks": checks}
    return data


class Inspector:
    def __init__(self, data):
        self.data = data

    def has_table(self, table, schema):
        return self.data[schema]["exists"]

    def get_columns(self, table, schema):
        return [dict(name=name, **value) for name, value in self.data[schema]["columns"].items()]

    def get_check_constraints(self, table, schema):
        return [{"name": name, "sqltext": sql} for name, sql in self.data[schema]["checks"].items()]


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, populated=None):
        self.populated = populated or {}
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql.startswith("LOCK TABLE"):
            return None
        for schema, populated in self.populated.items():
            if f'"{schema}"."qc_defects"' in sql:
                return Scalar(populated)
        raise AssertionError(f"unexpected query: {sql}")


def fake(monkeypatch, module, data, populated=None):
    calls = []
    bind = Bind(populated)
    monkeypatch.setattr(module.sa, "inspect", lambda _: Inspector(data))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    for operation in ("add_column", "create_check_constraint", "drop_constraint", "drop_column"):
        monkeypatch.setattr(
            module.op, operation,
            lambda *args, _operation=operation, **kwargs: calls.append((_operation, args, kwargs)),
        )
    return bind, calls


def test_upgrade_adds_both_nullable_fields_and_check_in_both_schemas(monkeypatch):
    module = migration()
    bind, calls = fake(monkeypatch, module, state(module))
    module.upgrade()
    assert module.down_revision == "20260925_000055"
    assert len([query for query in bind.queries if query.startswith("LOCK TABLE")]) == 2
    adds = [(args[1].name, kwargs["schema"], args[1]) for name, args, kwargs in calls if name == "add_column"]
    assert {(name, schema) for name, schema, _ in adds} == {
        ("manual_review_status", "qc"), ("manual_created_by", "qc"),
        ("manual_review_status", "public"), ("manual_created_by", "public"),
    }
    assert all(column.nullable and column.server_default is None for _, _, column in adds)
    assert len([name for name, _, _ in calls if name == "create_check_constraint"]) == 2


def test_review_check_keeps_legacy_unknown_but_rejects_invalid_combinations():
    module = migration()
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE defects (origin TEXT, manual_review_status TEXT, "
        f"CONSTRAINT review CHECK ({module.CHECK_SQL}))"
    )
    for row in ((None, None), ("auto", None), ("manual", None),
                ("manual", "pending"), ("manual", "approved"), ("manual", "rejected")):
        connection.execute("INSERT INTO defects VALUES (?, ?)", row)
    for row in ((None, "pending"), ("auto", "pending"),
                ("manual", "unknown"), ("manual", "")):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO defects VALUES (?, ?)", row)
    assert connection.execute("SELECT count(*) FROM defects").fetchone()[0] == 6
    connection.close()


@pytest.mark.parametrize("drift", [
    "missing_table", "missing_origin", "bad_origin", "half_fields",
    "bad_review_type", "bad_check", "schema_mismatch",
])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    module = migration()
    data = state(module)
    selected = data["public"]
    if drift == "missing_table":
        selected["exists"] = False
    elif drift == "missing_origin":
        del selected["columns"]["origin"]
    elif drift == "bad_origin":
        selected["checks"]["ck_qc_defects_origin"] = "origin IN ('auto', 'manual', 'other')"
    elif drift == "half_fields":
        selected["columns"][module.REVIEW_COLUMN] = {"type": sa.String(20), "nullable": True, "default": None}
    elif drift == "bad_review_type":
        data = state(module, deployed=True)
        data["public"]["columns"][module.REVIEW_COLUMN]["type"] = sa.String(40)
    elif drift == "bad_check":
        data = state(module, deployed=True)
        data["public"]["checks"][module.CHECK_NAME] = "manual_review_status IS NOT NULL"
    else:
        data["public"] = state(module, deployed=True)["public"]
    _, calls = fake(monkeypatch, module, data)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []


def test_upgrade_is_idempotent_when_fully_deployed(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, state(module, deployed=True))
    module.upgrade()
    assert calls == []


def test_postgres_reflected_any_array_checks_match_deployed_contract(monkeypatch):
    module = migration()
    data = state(module, deployed=True)
    for schema in module.SCHEMAS:
        data[schema]["checks"]["ck_qc_defects_origin"] = (
            "((origin)::text = ANY ((ARRAY['auto'::character varying, "
            "'manual'::character varying])::text[]))"
        )
        data[schema]["checks"][module.CHECK_NAME] = (
            "((manual_review_status IS NULL) OR "
            "((origin IS NOT NULL) AND ((origin)::text = 'manual'::text) AND "
            "((manual_review_status)::text = ANY "
            "((ARRAY['pending'::character varying, 'approved'::character varying, "
            "'rejected'::character varying])::text[]))))"
        )
    _, calls = fake(monkeypatch, module, data)
    module.upgrade()
    assert calls == []


def test_downgrade_rejects_populated_new_fields_in_either_schema(monkeypatch):
    module = migration()
    bind, calls = fake(
        monkeypatch, module, state(module, deployed=True),
        populated={"qc": False, "public": True},
    )
    with pytest.raises(RuntimeError, match="public.qc_defects.*拒绝丢失数据"):
        module.downgrade()
    assert len([query for query in bind.queries if query.startswith("LOCK TABLE")]) == 2
    assert calls == []


def test_downgrade_empty_fields_drops_only_owned_contract(monkeypatch):
    module = migration()
    _, calls = fake(
        monkeypatch, module, state(module, deployed=True),
        populated={"qc": False, "public": False},
    )
    module.downgrade()
    assert [name for name, _, _ in calls].count("drop_constraint") == 2
    assert [name for name, _, _ in calls].count("drop_column") == 4
