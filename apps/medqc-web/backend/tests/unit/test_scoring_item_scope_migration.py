"""迁移 69 评分条目科室范围合同；只用 fake inspector，不连接数据库。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260928_000069_scoring_item_scope.py"
    spec = importlib.util.spec_from_file_location("scoring_item_scope_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Inspector:
    def __init__(self, states, *, drift=None):
        self.states = states
        self.drift = drift

    def has_table(self, table, schema):
        return True

    def get_columns(self, table, schema):
        columns = [{"name": "id", "type": sa.String(36), "nullable": False, "default": None}]
        if self.states[schema]:
            columns.extend([
                {"name": "department_scope_mode", "type": sa.String(16), "nullable": False, "default": "'all'"},
                {"name": "department_refs_json", "type": sa.Text(), "nullable": False, "default": "'[]'"},
            ])
        if self.drift == "default" and schema == "qc":
            columns[-2]["default"] = "'selected'"
        return columns

    def get_check_constraints(self, table, schema):
        existing = [
            {"name": "ck_qc_scoring_items_group_nonblank", "sqltext": "trim(group_name, ' ') <> ''"},
            {"name": "ck_qc_scoring_items_rule_nonblank", "sqltext": "trim(rule_id, ' ') <> ''"},
            {"name": "ck_qc_scoring_items_deduction_nonnegative", "sqltext": "deduction >= 0"},
        ]
        if not self.states[schema]:
            return existing
        expression = (
            "department_scope_mode = 'all'"
            if self.drift == "check" and schema == "qc"
            else "((department_scope_mode)::text = ANY ((ARRAY['all'::character varying, "
                 "'selected'::character varying])::text[]))"
        )
        return [*existing, {
            "name": "ck_qc_scoring_items_department_scope_mode",
            "sqltext": expression,
        }]


class Result:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, selected=0):
        self.selected = selected
        self.sql = []

    def execute(self, statement):
        self.sql.append(str(statement))
        return Result(self.selected)


def install(monkeypatch, module, states, *, selected=0, drift=None):
    calls = []
    bind = Bind(selected)
    monkeypatch.setattr(module.sa, "inspect", lambda _: Inspector(states, drift=drift))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    for name in ("add_column", "create_check_constraint", "drop_constraint", "drop_column"):
        monkeypatch.setattr(module.op, name, lambda *args, _name=name, **kwargs: calls.append((_name, args, kwargs)))
    return bind, calls


def test_upgrade_adds_explicit_all_columns_to_both_schemas(monkeypatch):
    module = migration()
    assert module.down_revision == "20260928_000068"
    _, calls = install(monkeypatch, module, {"qc": False, "public": False})
    module.upgrade()
    added = [(args[1].name, kwargs["schema"], str(args[1].server_default.arg))
             for name, args, kwargs in calls if name == "add_column"]
    assert added == [
        ("department_scope_mode", "qc", "'all'"), ("department_refs_json", "qc", "'[]'"),
        ("department_scope_mode", "public", "'all'"), ("department_refs_json", "public", "'[]'"),
    ]


def test_upgrade_is_idempotent_and_rejects_partial_schema_deployment(monkeypatch):
    module = migration()
    _, calls = install(monkeypatch, module, {"qc": True, "public": True})
    module.upgrade()
    assert calls == []

    for drift in ("default", "check"):
        _, calls = install(monkeypatch, module, {"qc": True, "public": True}, drift=drift)
        with pytest.raises(RuntimeError, match="漂移|约束"):
            module.upgrade()
        assert calls == []
    _, calls = install(monkeypatch, module, {"qc": True, "public": False})
    with pytest.raises(RuntimeError, match="部分 schema"):
        module.upgrade()
    assert calls == []


def test_downgrade_rejects_selected_rows_and_empty_scope_drops_both_schemas(monkeypatch):
    module = migration()
    _, calls = install(monkeypatch, module, {"qc": True, "public": True}, selected=1)
    with pytest.raises(RuntimeError, match="非全量适用范围"):
        module.downgrade()
    assert calls == []

    bind, calls = install(monkeypatch, module, {"qc": True, "public": True})
    module.downgrade()
    assert len([sql for sql in bind.sql if sql.startswith("LOCK TABLE")]) == 2
    assert [(name, kwargs["schema"]) for name, _args, kwargs in calls if name == "drop_column"] == [
        ("drop_column", "public"), ("drop_column", "public"),
        ("drop_column", "qc"), ("drop_column", "qc"),
    ]
