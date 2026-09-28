from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20260928_000066_task_schedules.py"
    )
    spec = importlib.util.spec_from_file_location("task_schedule_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _PresenceInspector:
    def __init__(self, present: dict[tuple[str, str], bool]):
        self.present = present

    def has_table(self, table, schema):
        return self.present.get((schema, table), False)


def test_revision_follows_task_configuration_version() -> None:
    module = migration()
    assert module.revision == "20260928_000066"
    assert module.down_revision == "20260927_000065"


def test_postgres_any_array_enum_check_is_accepted() -> None:
    module = migration()
    sql = (
        "((state)::text = ANY ((ARRAY['active'::character varying, "
        "'paused'::character varying, 'ended'::character varying, "
        "'cancelled'::character varying])::text[]))"
    )
    assert module._check_matches("ck_qc_task_schedules_state", sql)


def test_enum_check_rejects_unexpected_value() -> None:
    module = migration()
    assert not module._check_matches(
        "ck_qc_task_schedule_runs_status",
        "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'unknown')",
    )


def test_schema_state_rejects_only_one_table_in_schema() -> None:
    module = migration()
    inspector = _PresenceInspector({("qc", module.SCHEDULES): True})
    with pytest.raises(RuntimeError, match="部分定时计划表"):
        module._schema_state(inspector)


class _ContractInspector:
    def __init__(self, *, include_unique: bool):
        self.include_unique = include_unique

    def get_columns(self, _table, schema):
        return [{"name": "id", "type": sa.String(36), "nullable": False, "default": None}]

    def get_pk_constraint(self, _table, schema):
        return {"name": "pk_example", "constrained_columns": ["id"]}

    def get_unique_constraints(self, _table, schema):
        if not self.include_unique:
            return []
        return [{"name": "uq_example", "column_names": ["id"]}]

    def get_foreign_keys(self, _table, schema):
        return []

    def get_check_constraints(self, _table, schema):
        return []

    def get_indexes(self, _table, schema):
        return []


def test_existing_table_missing_unique_constraint_fails_closed() -> None:
    module = migration()
    with pytest.raises(RuntimeError, match="唯一约束合同漂移"):
        module._assert_named_contract(
            _ContractInspector(include_unique=False),
            "qc",
            "example",
            columns={"id": (sa.String, 36, False, None)},
            primary_key=("pk_example", ["id"]),
            uniques={"uq_example": ["id"]},
            foreign_keys={},
            checks={},
            indexes={},
        )


def test_existing_table_with_exact_unique_constraint_is_accepted() -> None:
    module = migration()
    module._assert_named_contract(
        _ContractInspector(include_unique=True),
        "qc",
        "example",
        columns={"id": (sa.String, 36, False, None)},
        primary_key=("pk_example", ["id"]),
        uniques={"uq_example": ["id"]},
        foreign_keys={},
        checks={},
        indexes={},
    )


def test_upgrade_creates_both_tables_in_both_schemas(monkeypatch) -> None:
    module = migration()
    inspector = _PresenceInspector({})
    created = []
    monkeypatch.setattr(module.op, "get_bind", lambda: object())
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: inspector)
    monkeypatch.setattr(module.op, "create_table", lambda table, *args, **kwargs: created.append((kwargs["schema"], table)))
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: None)

    module.upgrade()

    assert created == [
        ("qc", module.SCHEDULES),
        ("qc", module.RUNS),
        ("public", module.SCHEDULES),
        ("public", module.RUNS),
    ]
