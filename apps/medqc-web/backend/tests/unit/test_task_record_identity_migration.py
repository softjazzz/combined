"""病例三坐标迁移合同测试；不连接或写入业务数据库。"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex, CreateTable


def load_migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260923_000046_task_record_case_identity.py"
    spec = importlib.util.spec_from_file_location("task_record_identity_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class FakeBind:
    def __init__(self, states):
        self.states = states
        self.queries = []

    def execute(self, statement):
        sql = str(statement)
        self.queries.append(sql)
        schema = next(name for name in self.states if f'"{name}".' in sql)
        if "institute_id IS NOT NULL OR" in sql:
            key = "populated"
        elif "GROUP BY task_id, institute_id" in sql:
            key = "duplicate_modern"
        elif "GROUP BY task_id, record_id" in sql:
            key = "duplicate_legacy"
        elif "WHERE NOT (institute_id IS NULL" in sql:
            key = "invalid_case"
        else:
            key = "invalid"
        return ScalarResult(self.states[schema].get(key, 0))


class FakeInspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        return bool(self.states.get(schema, {}).get("exists"))

    def get_columns(self, table, schema):
        return [dict(name=name, **attrs) for name, attrs in self.states[schema]["columns"].items()]

    def get_check_constraints(self, table, schema):
        return [{"name": name, "sqltext": expression} for name, expression in self.states[schema]["checks"].items()]

    def get_unique_constraints(self, table, schema):
        return list(self.states[schema]["constraints"])

    def get_indexes(self, table, schema):
        return list(self.states[schema]["indexes"])


def table_state(*, exists=True, identity=False, old_unique="index", invalid=0, populated=0, base_nullable=True):
    columns = {
        "id": {"nullable": False},
        "task_id": {"nullable": base_nullable},
        "record_id": {"nullable": base_nullable},
    }
    if identity:
        columns.update({name: {"nullable": True} for name in ("institute_id", "patient_id", "visit_id")})
    state = {
        "exists": exists,
        "columns": columns,
        "checks": {},
        "constraints": [],
        "indexes": [],
        "invalid": invalid,
        "invalid_case": 0,
        "duplicate_legacy": 0,
        "duplicate_modern": 0,
        "populated": populated,
    }
    if old_unique == "index":
        state["indexes"].append(
            {"name": "legacy_global_idx", "column_names": ["task_id", "record_id"], "unique": True}
        )
    elif old_unique == "constraint":
        state["constraints"].append(
            {"name": "legacy_global_constraint", "column_names": ["record_id", "task_id"]}
        )
    return state


def install_fakes(monkeypatch, migration, states):
    calls = []
    bind = FakeBind(states)
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: FakeInspector(states))

    def add_column(table, column, *, schema):
        calls.append(("add_column", schema, column.name))
        states[schema]["columns"][column.name] = {"nullable": column.nullable}

    def alter_column(table, name, *, schema, nullable, **kwargs):
        calls.append(("alter_column", schema, name, nullable))
        states[schema]["columns"][name]["nullable"] = nullable

    def create_check_constraint(name, table, expression, *, schema):
        calls.append(("create_check_constraint", schema, name))
        states[schema]["checks"][name] = expression

    def create_index(name, table, columns, *, unique, schema, **kwargs):
        calls.append(("create_index", schema, name))
        item = {"name": name, "column_names": list(columns), "unique": unique}
        if "postgresql_where" in kwargs:
            item["dialect_options"] = {"postgresql_where": kwargs["postgresql_where"]}
        states[schema]["indexes"].append(item)

    def drop_constraint(name, table, *, type_, schema):
        calls.append(("drop_constraint", schema, name, type_))
        if type_ == "unique":
            states[schema]["constraints"] = [item for item in states[schema]["constraints"] if item["name"] != name]
        else:
            states[schema]["checks"].pop(name, None)

    def drop_index(name, *, table_name, schema):
        calls.append(("drop_index", schema, name))
        states[schema]["indexes"] = [item for item in states[schema]["indexes"] if item["name"] != name]

    def drop_column(table, name, *, schema):
        calls.append(("drop_column", schema, name))
        states[schema]["columns"].pop(name)

    monkeypatch.setattr(migration.op, "add_column", add_column)
    monkeypatch.setattr(migration.op, "alter_column", alter_column)
    monkeypatch.setattr(migration.op, "create_check_constraint", create_check_constraint)
    monkeypatch.setattr(migration.op, "create_index", create_index)
    monkeypatch.setattr(migration.op, "drop_constraint", drop_constraint)
    monkeypatch.setattr(migration.op, "drop_index", drop_index)
    monkeypatch.setattr(migration.op, "drop_column", drop_column)
    return bind, calls


@pytest.mark.parametrize("old_unique", ["index", "constraint"])
def test_upgrade_adds_nullable_identity_and_replaces_global_unique(monkeypatch, old_unique):
    migration = load_migration()
    states = {"qc": table_state(old_unique=old_unique), "public": table_state(exists=False, old_unique=None)}
    bind, calls = install_fakes(monkeypatch, migration, states)

    migration.upgrade()

    assert migration.revision == "20260923_000046"
    assert migration.down_revision == "20260922_000045"
    assert [call[2] for call in calls if call[0] == "add_column"] == list(migration.IDENTITY_COLUMNS)
    assert all(states["qc"]["columns"][name]["nullable"] for name in migration.IDENTITY_COLUMNS)
    assert states["qc"]["columns"]["task_id"]["nullable"] is True
    assert states["qc"]["columns"]["record_id"]["nullable"] is True
    assert set(states["qc"]["checks"]) == {
        migration.BASE_IDENTITY_CHECK_NAME,
        migration.CASE_IDENTITY_CHECK_NAME,
    }
    index_names = {item["name"] for item in states["qc"]["indexes"]}
    assert index_names == {migration.LEGACY_UNIQUE_INDEX, migration.MODERN_UNIQUE_INDEX}
    assert len(bind.queries) == 4


def test_upgrade_missing_tables_is_noop(monkeypatch):
    migration = load_migration()
    states = {
        "qc": table_state(exists=False, old_unique=None),
        "public": table_state(exists=False, old_unique=None),
    }
    bind, calls = install_fakes(monkeypatch, migration, states)
    migration.upgrade()
    assert calls == []
    assert bind.queries == []


@pytest.mark.parametrize("invalid", [1, 7])
def test_upgrade_fails_closed_for_null_or_blank_legacy_identity(monkeypatch, invalid):
    migration = load_migration()
    states = {"qc": table_state(invalid=invalid), "public": table_state(exists=False, old_unique=None)}
    _, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="未自动回填或删除历史数据"):
        migration.upgrade()

    assert [call[0] for call in calls] == ["add_column", "add_column", "add_column"]


@pytest.mark.parametrize(
    ("state_key", "message"),
    [
        ("invalid_case", "部分填写或空白三坐标"),
        ("duplicate_legacy", "重复 \\(task_id, record_id\\) legacy 身份"),
        ("duplicate_modern", "重复 \\(task_id, institute_id, patient_id, visit_id\\) 身份"),
    ],
)
def test_upgrade_fails_closed_for_invalid_or_duplicate_case_identity(monkeypatch, state_key, message):
    migration = load_migration()
    state = table_state(identity=True, old_unique=None)
    state[state_key] = 1
    states = {"qc": state, "public": table_state(exists=False, old_unique=None)}
    _, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match=message):
        migration.upgrade()

    assert not any(call[0] in {"create_check_constraint", "create_index", "drop_index"} for call in calls)


@pytest.mark.parametrize("check_name", ["BASE_IDENTITY_CHECK_NAME", "CASE_IDENTITY_CHECK_NAME"])
def test_upgrade_rejects_existing_same_name_check_without_guessing_expression(monkeypatch, check_name):
    migration = load_migration()
    state = table_state(identity=True, old_unique=None)
    state["checks"] = {getattr(migration, check_name): "task_id IS NOT NULL"}
    states = {"qc": state, "public": table_state(exists=False, old_unique=None)}
    _, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="拒绝猜测同名 CHECK"):
        migration.upgrade()

    assert calls == []


def test_upgrade_matches_real_dual_schema_topology(monkeypatch):
    migration = load_migration()
    states = {
        "qc": table_state(old_unique=None, base_nullable=True),
        "public": table_state(old_unique="index", base_nullable=False),
    }
    _, calls = install_fakes(monkeypatch, migration, states)

    migration.upgrade()

    assert states["qc"]["columns"]["task_id"]["nullable"] is True
    assert states["qc"]["columns"]["record_id"]["nullable"] is True
    assert states["public"]["columns"]["task_id"]["nullable"] is False
    assert states["public"]["columns"]["record_id"]["nullable"] is False
    assert not any(call[0] == "alter_column" for call in calls)
    for schema in migration.SCHEMAS:
        assert {item["name"] for item in states[schema]["indexes"]} == {
            migration.LEGACY_UNIQUE_INDEX,
            migration.MODERN_UNIQUE_INDEX,
        }


def test_upgrade_rejects_same_name_index_with_wrong_contract(monkeypatch):
    migration = load_migration()
    state = table_state(identity=True, old_unique=None)
    state["indexes"] = [
        {
            "name": migration.LEGACY_UNIQUE_INDEX,
            "column_names": ["task_id", "record_id"],
            "unique": True,
            "dialect_options": {"postgresql_where": "task_id IS NOT NULL"},
        }
    ]
    states = {"qc": state, "public": table_state(exists=False, old_unique=None)}
    _, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="与预期 legacy 唯一合同不一致"):
        migration.upgrade()

    assert not any(call[0] == "drop_index" for call in calls)


def test_sql_contract_rejects_partial_blank_and_duplicate_identities():
    migration = load_migration()
    connection = sqlite3.connect(":memory:")
    case_check = migration.CASE_IDENTITY_CHECK
    base_check = migration.BASE_IDENTITY_CHECK
    connection.executescript(
        f"""
        CREATE TABLE qc_task_records (
          id TEXT PRIMARY KEY,
          task_id TEXT,
          record_id TEXT,
          institute_id TEXT,
          patient_id TEXT,
          visit_id TEXT,
          CONSTRAINT base_identity CHECK ({base_check}),
          CONSTRAINT case_identity CHECK ({case_check})
        );
        CREATE UNIQUE INDEX legacy_unique ON qc_task_records(task_id, record_id)
          WHERE {migration.LEGACY_PREDICATE};
        CREATE UNIQUE INDEX modern_unique
          ON qc_task_records(task_id, institute_id, patient_id, visit_id)
          WHERE {migration.MODERN_PREDICATE};
        """
    )
    insert = "INSERT INTO qc_task_records VALUES (?, ?, ?, ?, ?, ?)"
    connection.execute(insert, ("l1", "t1", "same", None, None, None))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, ("null-task", None, "record", None, None, None))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, ("null-record", "task", None, None, None, None))
    for number, whitespace in enumerate(("", " ", "\t", "\n", "\r", "\f", "\v", "\t\n")):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(insert, (f"base-{number}", whitespace, f"r-{number}", None, None, None))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, ("l2", "t1", "same", None, None, None))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, ("p1", "t1", "partial", "org", None, "visit"))
    for number, whitespace in enumerate(("", " ", "\t", "\n", "\r", "\f", "\v", "\t\n")):
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(insert, (f"blank-{number}", "t1", f"blank-{number}", whitespace, "patient", "visit"))

    connection.execute(insert, ("m1", "t1", "same", "org-a", "patient-a", "visit-1"))
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, ("m2", "t1", "other", "org-a", "patient-a", "visit-1"))
    connection.execute(insert, ("m3", "t1", "other", "org-b", "patient-a", "visit-1"))
    connection.execute(insert, ("m4", "t1", "other", "org-a", "patient-b", "visit-1"))
    assert connection.execute("SELECT count(*) FROM qc_task_records").fetchone()[0] == 4


def test_downgrade_fails_before_ddl_when_case_identity_has_data(monkeypatch):
    migration = load_migration()
    state = table_state(identity=True, old_unique=None, populated=1)
    states = {"qc": state, "public": table_state(exists=False, old_unique=None)}
    _, calls = install_fakes(monkeypatch, migration, states)
    with pytest.raises(RuntimeError, match="避免删除历史病例身份"):
        migration.downgrade()
    assert calls == []


def test_downgrade_rejects_partial_schema_and_preserves_columns(monkeypatch):
    migration = load_migration()
    state = table_state(old_unique=None)
    state["columns"]["institute_id"] = {"nullable": True}
    states = {"qc": state, "public": table_state(exists=False, old_unique=None)}
    _, calls = install_fakes(monkeypatch, migration, states)
    with pytest.raises(RuntimeError, match="三坐标列不完整"):
        migration.downgrade()
    assert calls == []
    assert "institute_id" in state["columns"]


def test_downgrade_validates_all_schemas_before_any_ddl(monkeypatch):
    migration = load_migration()
    public = table_state(identity=True, old_unique=None)
    qc = table_state(identity=True, old_unique=None, populated=1)
    states = {"qc": qc, "public": public}
    _, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="避免删除历史病例身份"):
        migration.downgrade()

    assert calls == []
    assert all(name in public["columns"] for name in migration.IDENTITY_COLUMNS)


@pytest.mark.parametrize("state_key", ["invalid", "duplicate_legacy"])
def test_downgrade_fails_when_old_global_unique_cannot_be_restored(monkeypatch, state_key):
    migration = load_migration()
    state = table_state(identity=True, old_unique=None)
    state[state_key] = 1
    states = {"qc": state, "public": table_state(exists=False, old_unique=None)}
    _, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="无法无损恢复"):
        migration.downgrade()

    assert calls == []


def test_downgrade_legacy_only_restores_global_unique_without_data_loss(monkeypatch):
    migration = load_migration()
    state = table_state(identity=True, old_unique=None)
    state["checks"] = {
        migration.BASE_IDENTITY_CHECK_NAME: migration.BASE_IDENTITY_CHECK,
        migration.CASE_IDENTITY_CHECK_NAME: migration.CASE_IDENTITY_CHECK,
    }
    state["indexes"] = [
        {"name": migration.LEGACY_UNIQUE_INDEX, "column_names": ["task_id", "record_id"], "unique": True},
        {
            "name": migration.MODERN_UNIQUE_INDEX,
            "column_names": ["task_id", *migration.IDENTITY_COLUMNS],
            "unique": True,
        },
    ]
    states = {"qc": state, "public": table_state(exists=False, old_unique=None)}
    _, calls = install_fakes(monkeypatch, migration, states)
    migration.downgrade()

    assert not any(name in state["columns"] for name in migration.IDENTITY_COLUMNS)
    assert state["checks"] == {}
    assert state["indexes"] == [
        {
            "name": migration.RESTORED_GLOBAL_UNIQUE_INDEX,
            "column_names": ["task_id", "record_id"],
            "unique": True,
        }
    ]
    assert [call[2] for call in calls if call[0] == "drop_column"] == ["visit_id", "patient_id", "institute_id"]


def test_orm_matches_nullable_identity_checks_and_partial_indexes():
    from app.database.models.qc import QCTaskRecord

    migration = load_migration()
    table = QCTaskRecord.__table__
    assert all(table.c[name].nullable is True for name in migration.IDENTITY_COLUMNS)
    assert table.c.task_id.nullable is False
    assert table.c.record_id.nullable is False
    checks = {item.name: str(item.sqltext) for item in table.constraints if isinstance(item, CheckConstraint)}
    assert checks[migration.BASE_IDENTITY_CHECK_NAME] == migration.BASE_IDENTITY_CHECK
    assert checks[migration.CASE_IDENTITY_CHECK_NAME] == migration.CASE_IDENTITY_CHECK
    indexes = {item.name: item for item in table.indexes}
    assert migration.RESTORED_GLOBAL_UNIQUE_INDEX not in indexes
    assert tuple(column.name for column in indexes[migration.LEGACY_UNIQUE_INDEX].columns) == (
        "task_id",
        "record_id",
    )
    assert tuple(column.name for column in indexes[migration.MODERN_UNIQUE_INDEX].columns) == (
        "task_id",
        *migration.IDENTITY_COLUMNS,
    )
    assert str(indexes[migration.LEGACY_UNIQUE_INDEX].dialect_options["postgresql"]["where"]) == migration.LEGACY_PREDICATE
    assert str(indexes[migration.MODERN_UNIQUE_INDEX].dialect_options["postgresql"]["where"]) == migration.MODERN_PREDICATE
    assert str(indexes[migration.LEGACY_UNIQUE_INDEX].dialect_options["sqlite"]["where"]) == migration.LEGACY_PREDICATE
    assert str(indexes[migration.MODERN_UNIQUE_INDEX].dialect_options["sqlite"]["where"]) == migration.MODERN_PREDICATE

    postgresql_table_ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert migration.BASE_IDENTITY_CHECK in postgresql_table_ddl
    assert migration.CASE_IDENTITY_CHECK in postgresql_table_ddl
    for name in (migration.LEGACY_UNIQUE_INDEX, migration.MODERN_UNIQUE_INDEX):
        pg_index_ddl = str(CreateIndex(indexes[name]).compile(dialect=postgresql.dialect()))
        sqlite_index_ddl = str(CreateIndex(indexes[name]).compile(dialect=sqlite.dialect()))
        assert " UNIQUE INDEX " in f" {pg_index_ddl} " and " WHERE " in f" {pg_index_ddl} "
        assert " UNIQUE INDEX " in f" {sqlite_index_ddl} " and " WHERE " in f" {sqlite_index_ddl} "
