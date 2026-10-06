import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.ddl.base import AddColumn
from sqlalchemy.dialects import postgresql


PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/20261006_000047_visit_index_sync_fields.py"
)


@pytest.fixture
def migration(monkeypatch):
    spec = importlib.util.spec_from_file_location("visit_index_sync_migration", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    columns = {}
    emitted = []
    state = SimpleNamespace(
        columns=columns, emitted=emitted, table_exists=True, schemas=[]
    )

    def has_table(table, *, schema):
        assert table == "visit_index"
        state.schemas.append(schema)
        return state.table_exists

    inspector = SimpleNamespace(
        has_table=has_table,
        get_columns=lambda table, schema: list(columns.values()),
    )

    def add_column(table, column, *, schema):
        emitted.append(
            str(
                AddColumn(table, column, schema=schema).compile(
                    dialect=postgresql.dialect()
                )
            )
        )
        columns[column.name] = {
            "name": column.name,
            "type": column.type,
            "nullable": column.nullable,
            "default": str(column.server_default.arg)
            if column.server_default
            else None,
        }

    monkeypatch.setattr(
        module,
        "op",
        SimpleNamespace(get_bind=lambda: object(), add_column=add_column),
        raising=False,
    )
    monkeypatch.setattr(sa, "inspect", lambda bind: inspector)
    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    return module, state


def existing(name, *, type_=None, nullable=None, default=None):
    timestamp = name == "latest_mirror_success_time"
    return {
        "name": name,
        "type": type_
        if type_ is not None
        else (sa.DateTime(timezone=False) if timestamp else sa.Integer()),
        "nullable": timestamp if nullable is None else nullable,
        "default": default if default is not None else (None if timestamp else "30"),
    }


NAMES = (
    "latest_mirror_success_time",
    "mirror_delay_base_minutes",
    "sync_interval_minutes",
)


@pytest.mark.parametrize(
    "mode, schema", [("split", "qc"), ("single", "public"), (" SPLIT ", "qc")]
)
def test_upgrade_compiles_exact_three_adds(migration, monkeypatch, mode, schema):
    module, state = migration
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    module.upgrade()
    assert state.schemas == [schema]
    assert state.emitted == [
        f"ALTER TABLE {schema}.visit_index ADD COLUMN latest_mirror_success_time TIMESTAMP WITHOUT TIME ZONE",
        f"ALTER TABLE {schema}.visit_index ADD COLUMN mirror_delay_base_minutes INTEGER DEFAULT 30 NOT NULL",
        f"ALTER TABLE {schema}.visit_index ADD COLUMN sync_interval_minutes INTEGER DEFAULT 30 NOT NULL",
    ]
    assert module.revision == "20261006_000047"
    assert module.down_revision == "20261003_000046"


@pytest.mark.parametrize("present", [NAMES, NAMES[:1], NAMES[1:], NAMES[::2]])
def test_upgrade_existing_all_or_mixed_compatible_is_idempotent(migration, present):
    module, state = migration
    state.columns.update({name: existing(name) for name in present})
    module.upgrade()
    assert len(state.emitted) == 3 - len(present)
    assert all(
        not any(f"ADD COLUMN {name} " in sql for name in present)
        for sql in state.emitted
    )


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("fault", ["type", "nullable", "default"])
def test_upgrade_incompatible_existing_column_fails_before_any_ddl(
    migration, name, fault
):
    module, state = migration
    column = existing(name)
    if fault == "type":
        column["type"] = (
            sa.DateTime(timezone=True) if name == NAMES[0] else sa.BigInteger()
        )
    elif fault == "nullable":
        column["nullable"] = not column["nullable"]
    else:
        column["default"] = "now()" if name == NAMES[0] else "31"
    state.columns[name] = column
    with pytest.raises(RuntimeError, match=name):
        module.upgrade()
    assert state.emitted == []


@pytest.mark.parametrize(
    "default", ["30", "(30)", "'30'::integer", "30::integer", "((30))", "30::int4"]
)
def test_upgrade_accepts_reflected_constant_integer_default(migration, default):
    module, state = migration
    state.columns.update({name: existing(name) for name in NAMES})
    state.columns[NAMES[1]]["default"] = default
    module.upgrade()
    assert state.emitted == []


@pytest.mark.parametrize(
    "default", [None, "30 + 0", "300", "nextval('seq')", "(3)(0)", "'30'::text"]
)
def test_upgrade_rejects_other_defaults_without_ddl(migration, default):
    module, state = migration
    state.columns[NAMES[2]] = existing(NAMES[2])
    state.columns[NAMES[2]]["default"] = default
    with pytest.raises(RuntimeError, match=NAMES[2]):
        module.upgrade()
    assert state.emitted == []


@pytest.mark.parametrize("mode, schema", [("split", "qc"), ("single", "public")])
def test_upgrade_missing_table_fails_without_ddl(migration, monkeypatch, mode, schema):
    module, state = migration
    monkeypatch.setenv("DB_SCHEMA_MODE", mode)
    state.table_exists = False
    with pytest.raises(RuntimeError, match=f"{schema}.visit_index"):
        module.upgrade()
    assert state.emitted == []


def test_upgrade_is_reentrant_after_adding_fields(migration):
    module, state = migration
    module.upgrade()
    first_sql = list(state.emitted)
    module.upgrade()
    assert len(first_sql) == 3
    assert state.emitted == first_sql


def test_upgrade_accepts_postgresql_reflected_types(migration):
    module, state = migration
    state.columns.update({name: existing(name) for name in NAMES})
    state.columns[NAMES[0]]["type"] = postgresql.TIMESTAMP(timezone=False)
    for name in NAMES[1:]:
        state.columns[name]["type"] = postgresql.INTEGER()
    module.upgrade()
    assert state.emitted == []


def test_downgrade_refuses_automatic_deletion(migration):
    module, state = migration
    with pytest.raises(RuntimeError, match="不支持自动降级"):
        module.downgrade()
    assert state.emitted == []
