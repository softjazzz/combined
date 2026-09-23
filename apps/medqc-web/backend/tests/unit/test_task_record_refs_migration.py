"""任务病例三坐标配置迁移合同测试；不连接或写入业务数据库。"""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable


def load_migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260923_000047_task_record_refs.py"
    spec = importlib.util.spec_from_file_location("task_record_refs_migration", path)
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
        return ScalarResult(self.states[schema].get("populated", 0))


class FakeInspector:
    def __init__(self, states):
        self.states = states

    def has_table(self, table, schema):
        return bool(self.states.get(schema, {}).get("exists"))

    def get_columns(self, table, schema):
        return [dict(name=name, **column) for name, column in self.states[schema]["columns"].items()]


def table_state(*, exists=True, record_refs_type=None, nullable=True, default=None, populated=0):
    columns = {"id": {"type": sa.String(36), "nullable": False, "default": None}}
    if record_refs_type is not None:
        columns["record_refs"] = {
            "type": record_refs_type,
            "nullable": nullable,
            "default": default,
        }
    return {"exists": exists, "columns": columns, "populated": populated}


def install_fakes(monkeypatch, migration, states):
    calls = []
    bind = FakeBind(states)
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: FakeInspector(states))

    def add_column(table, column, *, schema):
        calls.append(("add_column", schema, table, column))
        states[schema]["columns"][column.name] = {
            "type": column.type,
            "nullable": column.nullable,
            "default": column.server_default,
        }

    def drop_column(table, name, *, schema):
        calls.append(("drop_column", schema, table, name))
        states[schema]["columns"].pop(name)

    monkeypatch.setattr(migration.op, "add_column", add_column)
    monkeypatch.setattr(migration.op, "drop_column", drop_column)
    return bind, calls


def test_upgrade_adds_nullable_jsonb_to_both_existing_schemas_without_backfill(monkeypatch):
    migration = load_migration()
    states = {"qc": table_state(), "public": table_state()}
    bind, calls = install_fakes(monkeypatch, migration, states)

    migration.upgrade()

    assert migration.revision == "20260923_000047"
    assert migration.down_revision == "20260923_000046"
    assert [(call[0], call[1], call[2]) for call in calls] == [
        ("add_column", "qc", "qc_tasks"),
        ("add_column", "public", "qc_tasks"),
    ]
    for call in calls:
        column = call[3]
        assert column.name == "record_refs"
        assert isinstance(column.type, postgresql.JSONB)
        assert column.nullable is True
        assert column.default is None
        assert column.server_default is None
    assert bind.queries == []


def test_upgrade_skips_missing_table_and_existing_jsonb_column(monkeypatch):
    migration = load_migration()
    states = {
        "qc": table_state(record_refs_type=postgresql.JSONB()),
        "public": table_state(exists=False),
    }
    bind, calls = install_fakes(monkeypatch, migration, states)

    migration.upgrade()

    assert calls == []
    assert bind.queries == []


def test_upgrade_missing_tables_is_noop(monkeypatch):
    migration = load_migration()
    states = {"qc": table_state(exists=False), "public": table_state(exists=False)}
    bind, calls = install_fakes(monkeypatch, migration, states)

    migration.upgrade()

    assert calls == []
    assert bind.queries == []


@pytest.mark.parametrize(
    "nullable, default",
    [(False, None), (True, "'[]'::jsonb"), (False, "'[]'::jsonb")],
)
def test_upgrade_rejects_existing_jsonb_with_incompatible_column_contract(
    monkeypatch, nullable, default
):
    migration = load_migration()
    states = {
        "qc": table_state(),
        "public": table_state(
            record_refs_type=postgresql.JSONB(), nullable=nullable, default=default
        ),
    }
    _, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="public.qc_tasks.record_refs.*可空性或默认值"):
        migration.upgrade()

    assert calls == []
    assert "record_refs" not in states["qc"]["columns"]


@pytest.mark.parametrize("wrong_type", [sa.Text(), postgresql.JSON(), sa.String(200)])
def test_upgrade_rejects_existing_non_jsonb_column_before_any_ddl(monkeypatch, wrong_type):
    migration = load_migration()
    states = {
        "qc": table_state(),
        "public": table_state(record_refs_type=wrong_type),
    }
    _, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="public.qc_tasks.record_refs.*JSONB"):
        migration.upgrade()

    assert calls == []
    assert "record_refs" not in states["qc"]["columns"]


def test_downgrade_rejects_non_null_data_across_schemas_before_any_ddl(monkeypatch):
    migration = load_migration()
    states = {
        "qc": table_state(record_refs_type=postgresql.JSONB(), populated=0),
        "public": table_state(record_refs_type=postgresql.JSONB(), populated=2),
    }
    bind, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="public.qc_tasks.*非 NULL record_refs"):
        migration.downgrade()

    assert calls == []
    assert len(bind.queries) == 4
    assert all("LOCK TABLE" in query for query in bind.queries[:2])
    assert all("record_refs IS NOT NULL" in query for query in bind.queries[2:])
    assert "record_refs" in states["qc"]["columns"]
    assert "record_refs" in states["public"]["columns"]


def test_downgrade_rejects_wrong_column_type_without_query_or_ddl(monkeypatch):
    migration = load_migration()
    states = {
        "qc": table_state(record_refs_type=postgresql.JSONB()),
        "public": table_state(record_refs_type=sa.Text()),
    }
    bind, calls = install_fakes(monkeypatch, migration, states)

    with pytest.raises(RuntimeError, match="public.qc_tasks.record_refs.*JSONB"):
        migration.downgrade()

    assert calls == []
    assert bind.queries == []


def test_downgrade_drops_only_empty_record_refs_after_all_schema_prechecks(monkeypatch):
    migration = load_migration()
    states = {
        "qc": table_state(record_refs_type=postgresql.JSONB()),
        "public": table_state(record_refs_type=postgresql.JSONB()),
    }
    bind, calls = install_fakes(monkeypatch, migration, states)

    migration.downgrade()

    assert bind.queries[:2] == [
        'LOCK TABLE "qc"."qc_tasks" IN ACCESS EXCLUSIVE MODE',
        'LOCK TABLE "public"."qc_tasks" IN ACCESS EXCLUSIVE MODE',
    ]
    assert len(bind.queries) == 4
    assert [(call[0], call[1], call[2], call[3]) for call in calls] == [
        ("drop_column", "public", "qc_tasks", "record_refs"),
        ("drop_column", "qc", "qc_tasks", "record_refs"),
    ]


def test_orm_uses_postgresql_jsonb_and_sqlite_json_with_nullable_history():
    from app.database.models.qc import QCTask

    column = QCTask.__table__.c.record_refs
    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None

    postgresql_ddl = str(CreateTable(QCTask.__table__).compile(dialect=postgresql.dialect()))
    sqlite_ddl = str(CreateTable(QCTask.__table__).compile(dialect=sqlite.dialect()))
    assert "record_refs JSONB" in postgresql_ddl
    assert "record_refs JSON" in sqlite_ddl
    assert "record_refs JSONB" not in sqlite_ddl

    engine = sa.create_engine("sqlite://")
    QCTask.__table__.create(engine)
    refs = [
        {"institute_id": "org-1", "patient_id": "patient-1", "visit_id": "visit-1"}
    ]
    with engine.begin() as connection:
        connection.execute(
            QCTask.__table__.insert().values(
                id="task-1",
                task_number="TASK-1",
                task_name="三坐标配置",
                task_type="one_time",
                record_refs=refs,
            )
        )
        assert connection.execute(
            sa.select(QCTask.__table__.c.record_refs)
        ).scalar_one() == refs
