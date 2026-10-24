"""PG 前置门禁的离线反例；不连接 PostgreSQL，不创建合成账号。"""

from contextlib import nullcontext
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from app.database.models.qc import QCDefect, QCDefectHistory, SysUser
from app.services import user_scope_owner as owners
from scripts import manual_review_pg_preflight as gate


class Schema:
    def __init__(self, schemas=("sys", "public")):
        self.tables = {}
        for schema, model in [(s, SysUser) for s in schemas] + [("qc", QCDefect), ("qc", QCDefectHistory)]:
            self.tables[schema, model.__tablename__] = [
                {"name": col.name, "type": col.type, "nullable": col.nullable, "default": None}
                for col in model.__table__.columns
            ]
        self.missing_index = False
        self.missing_unique = False
        self.bad_check = False

    def has_table(self, name, schema):
        return (schema, name) in self.tables

    def get_schema_names(self):
        return sorted({key[0] for key in self.tables})

    def get_columns(self, name, schema):
        return self.tables[schema, name]

    def get_pk_constraint(self, name, schema):
        return {"constrained_columns": ["id"]}

    def get_indexes(self, name, schema):
        return [] if self.missing_index else [{"name": "ix_sys_users_institute_department",
                                               "column_names": ["institute_id", "department"], "unique": False}]

    def get_unique_constraints(self, name, schema):
        return [] if self.missing_unique else [{"column_names": ["username"]}]

    def get_check_constraints(self, name, schema):
        return [] if self.bad_check else [{"name": c.name, "sqltext": c.sqltext}
                                         for c in QCDefect.__table__.constraints if isinstance(c, sa.CheckConstraint)]


def test_revision_57_without_institute_is_rejected_before_writing():
    schema = Schema()
    schema.tables["sys", "sys_users"] = [c for c in schema.tables["sys", "sys_users"] if c["name"] != "institute_id"]
    with pytest.raises(gate.PreflightRejected, match="institute_id"):
        gate.validate_schema(schema, "sys")


@pytest.mark.parametrize("owner", [None, "legacy", ""])
def test_unknown_owner_rejected(owner):
    with pytest.raises(gate.PreflightRejected, match="owner"):
        gate.validate_schema(Schema(), owner)


@pytest.mark.parametrize("path,expected", [("qc,sys,public", "sys"), ("qc,public,sys", "public")])
def test_dual_tables_use_configured_real_owner(monkeypatch, path, expected):
    schema = Schema()
    monkeypatch.setattr(owners, "DB_SEARCH_PATH", path)
    monkeypatch.setattr(owners.sa, "inspect", lambda _: schema)
    session = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    owner = owners.resolve_user_owner_schema(session)
    assert owner == expected
    gate.validate_schema(schema, owner)
    # 不能因为另一张同名表完整就放行实际 owner 的缺列。
    schema.tables[owner, "sys_users"] = [c for c in schema.tables[owner, "sys_users"] if c["name"] != "institute_id"]
    with pytest.raises(gate.PreflightRejected, match=f"{owner}.sys_users.*institute_id"):
        gate.validate_schema(schema, owner)


def test_ambiguous_owner_fails_closed(monkeypatch):
    monkeypatch.setattr(owners, "DB_SEARCH_PATH", "")
    monkeypatch.setattr(owners.sa, "inspect", lambda _: Schema())
    session = SimpleNamespace(get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")))
    with pytest.raises(owners.UserOwnerUnavailable):
        owners.resolve_user_owner_schema(session)


@pytest.mark.parametrize("fault,reason", [("missing_index", "索引"), ("missing_unique", "唯一"), ("bad_check", "合同漂移")])
def test_required_constraints_checked(fault, reason):
    schema = Schema()
    setattr(schema, fault, True)
    with pytest.raises(gate.PreflightRejected, match=reason):
        gate.validate_schema(schema, "sys")


def test_readonly_preflight_precedes_fixture_writes(monkeypatch):
    statements = []
    conn = SimpleNamespace(begin=lambda: nullcontext(), execute=lambda sql: execute(str(sql)))

    def execute(sql):
        statements.append(sql)
        return SimpleNamespace(scalar_one=lambda: gate.TARGET_DB if "current_database" in sql else "qc")

    monkeypatch.setattr(gate, "Session", lambda **_: nullcontext(object()))
    monkeypatch.setattr(gate, "resolve_user_owner_schema", lambda _: "sys")
    monkeypatch.setattr(gate.sa, "inspect", lambda _: Schema())
    engine = SimpleNamespace(connect=lambda: nullcontext(conn))
    assert gate.preflight(engine) == "sys"
    assert statements == ["SET TRANSACTION READ ONLY", "SELECT current_database()", "SELECT current_schema()"]


def test_complete_schema_allowed_without_revision_string_ordering():
    gate.validate_schema(Schema(), "public")


@pytest.mark.parametrize("field,value,reason", [("nullable", False, "机构列合同"),
                                               ("type", sa.String(64), "机构列合同")])
def test_institute_column_drift_rejected(field, value, reason):
    schema = Schema()
    next(c for c in schema.tables["sys", "sys_users"] if c["name"] == "institute_id")[field] = value
    with pytest.raises(gate.PreflightRejected, match=reason):
        gate.validate_schema(schema, "sys")


def test_current_model_scene_column_required_even_on_new_revision():
    schema = Schema()
    schema.tables["qc", "qc_defects"] = [c for c in schema.tables["qc", "qc_defects"] if c["name"] != "scene"]
    with pytest.raises(gate.PreflightRejected, match="qc.qc_defects.*scene"):
        gate.validate_schema(schema, "sys")


def test_wrong_database_stops_before_owner_resolution(monkeypatch):
    statements = []

    def execute(sql):
        statements.append(str(sql))
        return SimpleNamespace(scalar_one=lambda: "not-the-authorized-isolated-db")

    conn = SimpleNamespace(begin=lambda: nullcontext(), execute=execute)
    monkeypatch.setattr(gate, "resolve_user_owner_schema", lambda _: pytest.fail("must not resolve or write fixtures"))
    with pytest.raises(gate.PreflightRejected, match="隔离库"):
        gate.preflight(SimpleNamespace(connect=lambda: nullcontext(conn)))
    assert statements == ["SET TRANSACTION READ ONLY", "SELECT current_database()"]
