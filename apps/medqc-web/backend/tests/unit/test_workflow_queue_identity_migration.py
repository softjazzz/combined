"""现代队列身份迁移的隔离合同测试，不连接数据库。"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260924_000054_workflow_queue_identity.py"
    spec = importlib.util.spec_from_file_location("workflow_queue_identity_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _state(module, *, modern=False, exists=True):
    columns = {
        name: {"type": kind, "nullable": nullable, "default": None}
        for name, (kind, nullable) in module.BASELINE_COLUMNS.items()
    }
    checks = {name: "" for name in module.BASELINE_CHECKS}
    indexes = {
        "ix_queue_state_workflow_status_updated": {
            "column_names": ["workflow_type", "queue_status", None], "unique": False,
        },
        "ix_queue_state_visit": {"column_names": ["visit_id"], "unique": False},
    }
    if modern:
        columns.update({
            "identity_version": {"type": sa.SmallInteger(), "nullable": True, "default": None},
            "source_key": {"type": sa.String(64), "nullable": True, "default": None},
        })
        checks[module.MODERN_CHECK] = module._check_sql()
        indexes[module.LEGACY_INDEX] = {
            "column_names": list(module.LEGACY_INDEX_COLUMNS), "unique": True,
            "dialect_options": {"postgresql_where": f"({module.LEGACY_INDEX_PREDICATE})"},
        }
        indexes[module.MODERN_INDEX] = {
            "column_names": list(module.MODERN_INDEX_COLUMNS), "unique": True,
            "dialect_options": {"postgresql_where": f"({module.MODERN_INDEX_PREDICATE})"},
        }
    else:
        indexes[module.BASELINE_INDEX] = {
            "column_names": list(module.LEGACY_INDEX_COLUMNS), "unique": True,
            "dialect_options": {"postgresql_where": None},
        }
    return {"exists": exists, "columns": columns, "checks": checks, "indexes": indexes}


class _Inspector:
    def __init__(self, state):
        self.state = state

    def has_table(self, table, schema):
        assert (schema, table) == ("qc", "workflow_queue_state")
        return self.state["exists"]

    def get_columns(self, table, schema):
        return [dict(name=name, **value) for name, value in self.state["columns"].items()]

    def get_check_constraints(self, table, schema):
        return [{"name": name, "sqltext": expression} for name, expression in self.state["checks"].items()]

    def get_indexes(self, table, schema):
        return [dict(name=name, **value) for name, value in self.state["indexes"].items()]


class _Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class _Bind:
    def __init__(self, modern_rows=0):
        self.modern_rows = modern_rows
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        if sql.startswith("LOCK TABLE"):
            return None
        assert 'FROM "qc"."workflow_queue_state"' in sql
        assert '"identity_version" IS NOT NULL OR "source_key" IS NOT NULL' in sql
        return _Scalar(self.modern_rows)


def _fake(monkeypatch, module, state, *, modern_rows=0):
    calls = []
    bind = _Bind(modern_rows)
    monkeypatch.setattr(module.sa, "inspect", lambda _: _Inspector(state))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    for operation in (
        "add_column", "create_check_constraint", "create_index",
        "drop_index", "drop_constraint", "drop_column",
    ):
        monkeypatch.setattr(
            module.op, operation,
            lambda *args, _operation=operation, **kwargs: calls.append((_operation, args, kwargs)),
        )
    return bind, calls


def _sqlite(module):
    conn = sqlite3.connect(":memory:")
    conn.create_function("chr", 1, chr)
    conn.create_function(
        "btrim", 2,
        lambda value, chars: value.strip(chars) if value is not None else None,
    )
    conn.execute(
        "CREATE TABLE workflow_queue_state ("
        "id TEXT NOT NULL, workflow_type TEXT NOT NULL, visit_id TEXT NOT NULL, "
        "patient_id TEXT, institute_id TEXT, identity_version SMALLINT, source_key TEXT, "
        f"CONSTRAINT {module.MODERN_CHECK} CHECK ({module._check_sql()}))"
    )
    conn.execute(
        f"CREATE UNIQUE INDEX {module.LEGACY_INDEX} ON workflow_queue_state "
        f"({', '.join(module.LEGACY_INDEX_COLUMNS)}) WHERE {module.LEGACY_INDEX_PREDICATE}"
    )
    conn.execute(
        f"CREATE UNIQUE INDEX {module.MODERN_INDEX} ON workflow_queue_state "
        f"({', '.join(module.MODERN_INDEX_COLUMNS)}) WHERE {module.MODERN_INDEX_PREDICATE}"
    )
    return conn


def _insert(conn, *, identity_version, source_key, institute_id, patient_id, visit_id, workflow_type="coding_qc"):
    conn.execute(
        "INSERT INTO workflow_queue_state "
        "(id, workflow_type, visit_id, patient_id, institute_id, identity_version, source_key) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            f"row-{conn.total_changes + 1}", workflow_type, visit_id,
            patient_id, institute_id, identity_version, source_key,
        ),
    )


def test_revision_chain_follows_identity_source_migration():
    module = _migration()
    assert module.revision == "20260924_000054"
    assert module.down_revision == "20260924_000053"
    assert module.SCHEMA == "qc"
    assert module.TABLE == "workflow_queue_state"
    assert module.MODERN_INDEX_COLUMNS == (
        "workflow_type", "source_key", "institute_id", "patient_id", "visit_id",
    )
    assert module.LEGACY_INDEX_PREDICATE == "identity_version IS NULL"
    assert module.MODERN_INDEX_PREDICATE == "identity_version = 1"


def test_upgrade_swaps_unique_index_and_adds_only_modern_columns(monkeypatch):
    module = _migration()
    bind, calls = _fake(monkeypatch, module, _state(module))
    module.upgrade()

    # 不回填历史、不执行任何 DML。
    assert bind.queries == []
    assert [operation for operation, _, _ in calls] == [
        "add_column", "add_column", "create_check_constraint",
        "create_index", "create_index", "drop_index",
    ]

    added = [args[1] for operation, args, _ in calls if operation == "add_column"]
    assert [column.name for column in added] == ["identity_version", "source_key"]
    assert all(column.nullable and column.server_default is None for column in added)
    assert isinstance(added[0].type, sa.SmallInteger)
    assert isinstance(added[1].type, sa.String) and added[1].type.length == 64

    checks = [args for operation, args, _ in calls if operation == "create_check_constraint"]
    assert checks == [(module.MODERN_CHECK, module.TABLE, module._check_sql())]

    indexes = [call for call in calls if call[0] == "create_index"]
    assert [call[1][0] for call in indexes] == [module.LEGACY_INDEX, module.MODERN_INDEX]
    assert indexes[0][1][1] == module.TABLE
    assert indexes[0][1][2] == list(module.LEGACY_INDEX_COLUMNS)
    assert indexes[1][1][2] == list(module.MODERN_INDEX_COLUMNS)
    for _, _, kwargs in indexes:
        assert kwargs["unique"] is True
        assert kwargs["schema"] == "qc"
    assert [str(kwargs["postgresql_where"]) for _, _, kwargs in indexes] == [
        module.LEGACY_INDEX_PREDICATE, module.MODERN_INDEX_PREDICATE,
    ]
    assert [args for operation, args, _ in calls if operation == "drop_index"] == [(module.BASELINE_INDEX,)]


def test_upgrade_accepts_fully_deployed_contract(monkeypatch):
    module = _migration()
    bind, calls = _fake(monkeypatch, module, _state(module, modern=True))
    module.upgrade()
    assert calls == []
    assert bind.queries == []


def test_modern_check_allows_legacy_rows_and_rejects_blank_or_partial_identity():
    module = _migration()
    expression = module._check_sql()
    assert "identity_version IS NULL AND source_key IS NULL" in expression
    assert "identity_version IS NOT NULL AND identity_version = 1" in expression
    for name in module.IDENTITY_COLUMNS:
        assert f"{name} IS NOT NULL AND btrim({name}, {module.TRIM_CHARS_SQL}) <> ''" in expression
    check = sa.CheckConstraint(expression)
    assert str(check.sqltext.compile(dialect=postgresql.dialect())) == expression

    conn = _sqlite(module)
    _insert(conn, identity_version=None, source_key=None, institute_id="LX001", patient_id="P01", visit_id="V01")
    _insert(conn, identity_version=None, source_key=None, institute_id=None, patient_id=None, visit_id="V02")
    for invalid in (
        dict(identity_version=None, source_key="saved", institute_id="LX001", patient_id="P01", visit_id="V03"),
        dict(identity_version=1, source_key=None, institute_id="LX001", patient_id="P01", visit_id="V03"),
        dict(identity_version=1, source_key=" ", institute_id="LX001", patient_id="P01", visit_id="V03"),
        dict(identity_version=1, source_key="\r\n\t", institute_id="LX001", patient_id="P01", visit_id="V03"),
        dict(identity_version=1, source_key="saved", institute_id=None, patient_id="P01", visit_id="V03"),
        dict(identity_version=1, source_key="saved", institute_id="LX001", patient_id="\t", visit_id="V03"),
        dict(identity_version=1, source_key="saved", institute_id="\v\f", patient_id="P01", visit_id="V03"),
        dict(identity_version=1, source_key="saved", institute_id="LX001", patient_id="P01", visit_id="  "),
        dict(identity_version=2, source_key="saved", institute_id="LX001", patient_id="P01", visit_id="V03"),
    ):
        with pytest.raises(sqlite3.IntegrityError):
            _insert(conn, **invalid)
    assert conn.execute("SELECT count(*) FROM workflow_queue_state").fetchone()[0] == 2
    conn.close()


def test_partial_unique_indexes_let_same_visit_queue_per_case_and_source():
    module = _migration()
    conn = _sqlite(module)
    legacy = dict(identity_version=None, source_key=None, institute_id="LX001", patient_id="P01", visit_id="V01")
    saved = dict(identity_version=1, source_key="saved", institute_id="LX001", patient_id="P01", visit_id="V01")
    generated = dict(identity_version=1, source_key="generated", institute_id="LX001", patient_id="P01", visit_id="V01")
    other_case = dict(identity_version=1, source_key="saved", institute_id="LX001", patient_id="P02", visit_id="V01")

    # 历史行与同一 visit 的现代行互不挤占。
    _insert(conn, **legacy)
    _insert(conn, **saved)
    _insert(conn, **generated)
    _insert(conn, **other_case)
    _insert(conn, workflow_type="frontpage_qc", **saved)

    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, **saved)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, **legacy)
    assert conn.execute("SELECT count(*) FROM workflow_queue_state").fetchone()[0] == 5
    conn.close()


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
    assert not module._has_expected_check(expected.replace("chr(9)", "chr(8)", 1))
    assert not module._has_expected_check(
        expected.replace(f"btrim(source_key, {module.TRIM_CHARS_SQL})", "btrim(source_key)")
    )


@pytest.mark.parametrize(
    "drift",
    [
        "missing_table", "extra_column", "baseline_column_drift", "baseline_narrowed_column",
        "missing_baseline_check", "missing_untouched_index", "missing_baseline_unique_index",
        "baseline_unique_not_unique", "partial_modern_columns", "modern_column_width",
        "modern_column_nullable", "bad_check", "legacy_index_columns", "legacy_index_predicate",
        "missing_modern_index", "modern_index_predicate", "baseline_index_still_present",
    ],
)
def test_upgrade_rejects_drift_before_ddl(monkeypatch, drift):
    module = _migration()
    deployed = {
        "extra_column", "modern_column_width", "modern_column_nullable", "bad_check",
        "legacy_index_columns", "legacy_index_predicate", "missing_modern_index",
        "modern_index_predicate", "baseline_index_still_present",
    }
    state = _state(module, modern=drift in deployed)
    if drift == "missing_table":
        state["exists"] = False
    elif drift == "extra_column":
        state["columns"]["unexpected_note"] = {"type": sa.Text(), "nullable": True, "default": None}
    elif drift == "baseline_column_drift":
        state["columns"]["visit_id"] = {"type": sa.String(64), "nullable": False, "default": None}
    elif drift == "baseline_narrowed_column":
        state["columns"]["institute_id"] = {"type": sa.Text(), "nullable": True, "default": None}
    elif drift == "missing_baseline_check":
        del state["checks"]["ck_workflow_queue_state_workflow"]
    elif drift == "missing_untouched_index":
        del state["indexes"]["ix_queue_state_visit"]
    elif drift == "missing_baseline_unique_index":
        del state["indexes"][module.BASELINE_INDEX]
    elif drift == "baseline_unique_not_unique":
        state["indexes"][module.BASELINE_INDEX]["unique"] = False
    elif drift == "partial_modern_columns":
        state["columns"]["identity_version"] = {"type": sa.SmallInteger(), "nullable": True, "default": None}
    elif drift == "modern_column_width":
        state["columns"]["source_key"]["type"] = sa.String(32)
    elif drift == "modern_column_nullable":
        state["columns"]["identity_version"]["nullable"] = False
    elif drift == "bad_check":
        state["checks"][module.MODERN_CHECK] = "identity_version IS NULL OR source_key IS NOT NULL"
    elif drift == "legacy_index_columns":
        state["indexes"][module.LEGACY_INDEX]["column_names"] = ["visit_id"]
    elif drift == "legacy_index_predicate":
        state["indexes"][module.LEGACY_INDEX]["dialect_options"]["postgresql_where"] = "identity_version = 1"
    elif drift == "missing_modern_index":
        del state["indexes"][module.MODERN_INDEX]
    elif drift == "modern_index_predicate":
        state["indexes"][module.MODERN_INDEX]["dialect_options"]["postgresql_where"] = None
    elif drift == "baseline_index_still_present":
        state["indexes"][module.BASELINE_INDEX] = {
            "column_names": list(module.LEGACY_INDEX_COLUMNS), "unique": True,
            "dialect_options": {"postgresql_where": None},
        }
    bind, calls = _fake(monkeypatch, module, state)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []
    assert bind.queries == []


def test_downgrade_refuses_when_contract_not_deployed(monkeypatch):
    module = _migration()
    bind, calls = _fake(monkeypatch, module, _state(module))
    with pytest.raises(RuntimeError, match="拒绝降级"):
        module.downgrade()
    assert calls == []
    assert bind.queries == []


def test_downgrade_refuses_to_drop_columns_when_modern_rows_exist(monkeypatch):
    module = _migration()
    bind, calls = _fake(monkeypatch, module, _state(module, modern=True), modern_rows=7)
    with pytest.raises(RuntimeError, match="7 行现代身份数据.*拒绝降级"):
        module.downgrade()
    assert len([sql for sql in bind.queries if sql.startswith("LOCK TABLE")]) == 1
    assert calls == []


def test_downgrade_restores_global_unique_index_and_drops_modern_artifacts(monkeypatch):
    module = _migration()
    bind, calls = _fake(monkeypatch, module, _state(module, modern=True))
    module.downgrade()
    assert len(bind.queries) == 2
    assert [operation for operation, _, _ in calls] == [
        "create_index", "drop_index", "drop_index", "drop_constraint", "drop_column", "drop_column",
    ]
    assert calls[0][1] == (module.BASELINE_INDEX, module.TABLE, list(module.LEGACY_INDEX_COLUMNS))
    assert calls[0][2] == {"unique": True, "schema": "qc"}
    assert [call[1][0] for call in calls if call[0] == "drop_index"] == [module.MODERN_INDEX, module.LEGACY_INDEX]
    assert [call[1][1] for call in calls if call[0] == "drop_column"] == ["source_key", "identity_version"]


def test_postgresql_ddl_compiles_for_check_and_partial_indexes():
    module = _migration()
    dialect = postgresql.dialect()
    check = sa.CheckConstraint(module._check_sql())
    assert str(check.sqltext.compile(dialect=dialect)) == module._check_sql()

    table = sa.Table(
        module.TABLE, sa.MetaData(schema=module.SCHEMA),
        sa.Column("workflow_type", sa.String(32), nullable=False),
        sa.Column("visit_id", sa.String(100), nullable=False),
        sa.Column("patient_id", sa.String(100), nullable=True),
        sa.Column("institute_id", sa.String(100), nullable=True),
        sa.Column("source_key", sa.String(64), nullable=True),
        sa.Column("identity_version", sa.SmallInteger(), nullable=True),
    )

    def ddl(name, columns, predicate=None):
        index = sa.Index(
            name, *[table.c[column] for column in columns], unique=True,
            **({"postgresql_where": sa.text(predicate)} if predicate else {}),
        )
        return " ".join(str(sa.schema.CreateIndex(index).compile(dialect=dialect)).split())

    modern = ddl(module.MODERN_INDEX, module.MODERN_INDEX_COLUMNS, module.MODERN_INDEX_PREDICATE)
    assert modern.startswith(
        f"CREATE UNIQUE INDEX {module.MODERN_INDEX} ON {module.SCHEMA}.{module.TABLE} "
        f"({', '.join(module.MODERN_INDEX_COLUMNS)})"
    )
    assert modern.endswith(f"WHERE {module.MODERN_INDEX_PREDICATE}")

    legacy = ddl(module.LEGACY_INDEX, module.LEGACY_INDEX_COLUMNS, module.LEGACY_INDEX_PREDICATE)
    assert legacy.endswith(f"WHERE {module.LEGACY_INDEX_PREDICATE}")

    restored = ddl(module.BASELINE_INDEX, module.LEGACY_INDEX_COLUMNS)
    assert restored == (
        f"CREATE UNIQUE INDEX {module.BASELINE_INDEX} ON {module.SCHEMA}.{module.TABLE} "
        "(workflow_type, visit_id)"
    )
