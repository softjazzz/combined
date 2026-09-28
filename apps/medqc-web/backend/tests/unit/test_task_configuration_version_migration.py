from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260927_000065_task_configuration_version.py"
    spec = importlib.util.spec_from_file_location("task_configuration_version_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Inspector:
    def __init__(self, states, *, default="1", extra_checks=None):
        self.states = states
        self.default = default
        self.extra_checks = list(extra_checks or [])

    def has_table(self, _table, schema):
        return self.states.get(schema) != "missing_table"

    def get_columns(self, _table, schema):
        if self.states.get(schema) != "present":
            return [{"name": "id", "type": sa.String(36), "nullable": False, "default": None}]
        return [
            {"name": "id", "type": sa.String(36), "nullable": False, "default": None},
            {
                "name": "configuration_version",
                "type": sa.Integer(),
                "nullable": False,
                "default": self.default,
            },
        ]

    def get_check_constraints(self, _table, schema):
        if self.states.get(schema) == "present":
            return [{
                "name": "ck_qc_tasks_configuration_version_positive",
                "sqltext": "configuration_version > 0",
            }, *self.extra_checks]
        return []


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, edited=0):
        self.edited = edited

    def execute(self, statement):
        return Scalar(self.edited if "count(*)" in str(statement) else 0)


def test_upgrade_adds_version_and_check_to_both_schemas(monkeypatch):
    module = migration()
    added = []
    checks = []
    monkeypatch.setattr(module.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: Inspector({"qc": "absent", "public": "absent"}))
    monkeypatch.setattr(module.op, "add_column", lambda *args, **kwargs: added.append((args, kwargs)))
    monkeypatch.setattr(module.op, "create_check_constraint", lambda *args, **kwargs: checks.append((args, kwargs)))

    module.upgrade()

    assert module.down_revision == "20260927_000064"
    assert [kwargs["schema"] for _, kwargs in added] == ["qc", "public"]
    assert [kwargs["schema"] for _, kwargs in checks] == ["qc", "public"]


def test_upgrade_rejects_partial_schema_before_ddl(monkeypatch):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: Inspector({"qc": "present", "public": "absent"}))
    monkeypatch.setattr(module.op, "add_column", lambda *_args, **_kwargs: pytest.fail("不得执行DDL"))
    with pytest.raises(RuntimeError, match="部分 schema"):
        module.upgrade()


def test_upgrade_accepts_equivalent_quoted_integer_default(monkeypatch):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(
        module.sa,
        "inspect",
        lambda _bind: Inspector(
            {"qc": "present", "public": "present"},
            default="'1'::integer",
        ),
    )
    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda *_args, **_kwargs: pytest.fail("等价合同不得重复执行DDL"),
    )

    module.upgrade()


def test_upgrade_rejects_extra_check_on_configuration_version(monkeypatch):
    module = migration()
    extra = [{
        "name": "ck_qc_tasks_configuration_version_locked",
        "sqltext": "configuration_version <= 1",
    }]
    monkeypatch.setattr(module.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(
        module.sa,
        "inspect",
        lambda _bind: Inspector(
            {"qc": "present", "public": "present"},
            extra_checks=extra,
        ),
    )
    monkeypatch.setattr(
        module.op,
        "add_column",
        lambda *_args, **_kwargs: pytest.fail("合同漂移时不得执行DDL"),
    )

    with pytest.raises(RuntimeError, match="合同漂移"):
        module.upgrade()


def test_downgrade_refuses_to_drop_edited_versions(monkeypatch):
    module = migration()
    monkeypatch.setattr(module.op, "get_bind", lambda: Bind(edited=1))
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: Inspector({"qc": "present", "public": "present"}))
    monkeypatch.setattr(module.op, "drop_column", lambda *_args, **_kwargs: pytest.fail("不得删列"))
    with pytest.raises(RuntimeError, match="拒绝降级"):
        module.downgrade()
