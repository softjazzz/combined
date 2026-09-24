"""缺陷来源迁移合同测试；不连接或写入业务数据库。"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260924_000052_qc_defect_origin.py"
    spec = importlib.util.spec_from_file_location("qc_defect_origin_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _state(*, exists=True, origin=False, column_type=None, nullable=True, default=None, check=None):
    columns = {}
    if origin:
        columns["origin"] = {
            "type": column_type or sa.String(16), "nullable": nullable, "default": default,
        }
    checks = {}
    if check is not None:
        checks["ck_qc_defects_origin"] = check
    return {"exists": exists, "columns": columns, "checks": checks}


class _Inspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        return self.states[schema]["exists"]

    def get_columns(self, table, schema):
        return [dict(name=name, **value) for name, value in self.states[schema]["columns"].items()]

    def get_check_constraints(self, table, schema):
        return [{"name": name, "sqltext": sql} for name, sql in self.states[schema]["checks"].items()]


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


def _fakes(monkeypatch, migration, states, counts=None):
    bind = _Bind(counts or {schema: 0 for schema in states})
    calls = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration.sa, "inspect", lambda _: _Inspector(states))
    monkeypatch.setattr(
        migration.op, "add_column",
        lambda table, column, *, schema: calls.append(("add", schema, column)),
    )
    monkeypatch.setattr(
        migration.op, "create_check_constraint",
        lambda name, table, expression, *, schema: calls.append(("check", schema, name, expression)),
    )
    monkeypatch.setattr(
        migration.op, "drop_constraint",
        lambda name, table, *, type_, schema: calls.append(("drop_check", schema, name, type_)),
    )
    monkeypatch.setattr(
        migration.op, "drop_column",
        lambda table, column, *, schema: calls.append(("drop", schema, column)),
    )
    return bind, calls


def test_upgrade_adds_nullable_origin_and_check_to_both_existing_schemas(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(monkeypatch, migration, {"qc": _state(), "public": _state()})

    migration.upgrade()

    assert migration.revision == "20260924_000052"
    assert migration.down_revision == "20260924_000051"
    assert [(action, schema) for action, schema, *_ in calls] == [
        ("add", "qc"), ("check", "qc"), ("add", "public"), ("check", "public"),
    ]
    for _, _, column in (call for call in calls if call[0] == "add"):
        assert column.name == "origin"
        assert isinstance(column.type, sa.String)
        assert column.type.length == 16
        assert column.nullable is True
        assert column.default is None
        assert column.server_default is None
    for _, _, name, expression in (call for call in calls if call[0] == "check"):
        assert name == "ck_qc_defects_origin"
        assert expression == "origin IN ('auto', 'manual')"
    assert bind.queries == []


@pytest.mark.parametrize("existing_schema", ["qc", "public"])
def test_upgrade_ignores_absent_schema_and_accepts_fully_deployed_contract(monkeypatch, existing_schema):
    migration = _migration()
    existing = _state(origin=True, check="origin IN ('auto', 'manual')")
    states = {schema: _state(exists=False) for schema in migration.SCHEMAS}
    states[existing_schema] = existing
    _, calls = _fakes(monkeypatch, migration, states)
    migration.upgrade()
    assert calls == []


@pytest.mark.parametrize("existing_schema", ["qc", "public"])
def test_upgrade_adds_only_to_existing_schema(monkeypatch, existing_schema):
    migration = _migration()
    states = {schema: _state(exists=False) for schema in migration.SCHEMAS}
    states[existing_schema] = _state()
    _, calls = _fakes(monkeypatch, migration, states)
    migration.upgrade()
    assert [(action, schema) for action, schema, *_ in calls] == [
        ("add", existing_schema), ("check", existing_schema),
    ]


def test_upgrade_rejects_partial_deployment_before_ddl(monkeypatch):
    migration = _migration()
    _, calls = _fakes(monkeypatch, migration, {
        "qc": _state(origin=True, check="origin IN ('auto', 'manual')"),
        "public": _state(),
    })
    with pytest.raises(RuntimeError, match="部分 schema 已部署"):
        migration.upgrade()
    assert calls == []


@pytest.mark.parametrize("state", [
    _state(origin=True),
    _state(check="origin IN ('auto', 'manual')"),
    _state(origin=True, column_type=sa.String(32), check="origin IN ('auto', 'manual')"),
    _state(origin=True, nullable=False, check="origin IN ('auto', 'manual')"),
    _state(origin=True, default="auto", check="origin IN ('auto', 'manual')"),
    _state(origin=True, check="origin IN ('auto', 'external')"),
    _state(origin=True, check="origin IN ('auto', 'manual') OR origin IS NULL"),
    _state(origin=True, check="origin IN ('auto', 'manual') AND origin IS NULL"),
    _state(origin=True, check="origin IN ('auto', 'manual') = false"),
])
def test_upgrade_rejects_drift_before_ddl(monkeypatch, state):
    migration = _migration()
    _, calls = _fakes(monkeypatch, migration, {"qc": _state(), "public": state})
    with pytest.raises(RuntimeError, match="public.qc_defects"):
        migration.upgrade()
    assert calls == []


def test_upgrade_accepts_postgres_rendered_equivalent_check(monkeypatch):
    migration = _migration()
    postgres_check = (
        "(origin)::text = ANY ((ARRAY['auto'::character varying, "
        "'manual'::character varying])::text[])"
    )
    _, calls = _fakes(monkeypatch, migration, {
        "qc": _state(origin=True, check=postgres_check),
        "public": _state(origin=True, check=postgres_check),
    })

    migration.upgrade()

    assert calls == []


def test_downgrade_rejects_partial_deployment_before_lock_or_ddl(monkeypatch):
    migration = _migration()
    bind, calls = _fakes(monkeypatch, migration, {
        "qc": _state(origin=True, check="origin IN ('auto', 'manual')"),
        "public": _state(),
    })
    with pytest.raises(RuntimeError, match="合同未完整部署"):
        migration.downgrade()
    assert bind.queries == []
    assert calls == []


def test_downgrade_locks_all_tables_and_preserves_populated_origin(monkeypatch):
    migration = _migration()
    complete = _state(origin=True, check="origin IN ('auto', 'manual')")
    bind, calls = _fakes(monkeypatch, migration, {
        "qc": complete, "public": complete,
    }, {"qc": 0, "public": 1})
    with pytest.raises(RuntimeError, match="public.qc_defects.*非 NULL origin"):
        migration.downgrade()
    assert bind.queries[:2] == [
        'LOCK TABLE "qc"."qc_defects" IN ACCESS EXCLUSIVE MODE',
        'LOCK TABLE "public"."qc_defects" IN ACCESS EXCLUSIVE MODE',
    ]
    assert calls == []


def test_downgrade_drops_check_and_column_when_all_origins_null(monkeypatch):
    migration = _migration()
    complete = _state(origin=True, check="origin IN ('auto', 'manual')")
    _, calls = _fakes(monkeypatch, migration, {"qc": complete, "public": complete})
    migration.downgrade()
    assert calls == [
        ("drop_check", "public", "ck_qc_defects_origin", "check"),
        ("drop", "public", "origin"),
        ("drop_check", "qc", "ck_qc_defects_origin", "check"),
        ("drop", "qc", "origin"),
    ]


def test_orm_origin_is_nullable_and_has_no_default():
    from app.database.models.qc import QCDefect

    column = QCDefect.__table__.c.origin
    assert isinstance(column.type, sa.String)
    assert column.type.length == 16
    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None
    for dialect in (postgresql.dialect(), sqlite.dialect()):
        ddl = str(CreateTable(QCDefect.__table__).compile(dialect=dialect))
        assert "origin VARCHAR(16)" in ddl
