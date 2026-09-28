"""迁移 67：病历审核场景列双 schema 合同（不连接真实数据库）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


def migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20260928_000067_record_review_scene.py"
    )
    spec = importlib.util.spec_from_file_location("record_review_scene_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Inspector:
    def __init__(self, states, *, reflected=False, extra_index=False):
        self.states = states
        self.reflected = reflected
        self.extra_index = extra_index

    def has_table(self, _table, schema):
        return self.states.get(schema) != "missing_table"

    def get_columns(self, _table, schema):
        columns = [{"name": "created_at", "type": sa.DateTime(), "nullable": False,
                    "default": None}]
        if self.states.get(schema) == "present":
            columns.append({"name": "scene", "type": sa.String(24), "nullable": True,
                            "default": None})
        return columns

    def get_check_constraints(self, _table, schema):
        if self.states.get(schema) != "present":
            return []
        sql = "scene IS NULL OR scene IN ('outpatient_emergency', 'running', 'final')"
        if self.reflected:
            sql = (
                "((scene IS NULL) OR ((scene)::text = ANY "
                "((ARRAY['outpatient_emergency'::character varying, "
                "'running'::character varying, 'final'::character varying])::text[])))"
            )
        return [{"name": "ck_qc_record_reviews_scene", "sqltext": sql}]

    def get_indexes(self, _table, schema):
        if self.states.get(schema) != "present":
            return []
        indexes = [{
            "name": "ix_qc_record_reviews_scene_created",
            "column_names": ["scene", "created_at"],
            "unique": False,
        }]
        if self.extra_index:
            indexes.append({"name": "ix_scene_extra", "column_names": ["scene"], "unique": False})
        return indexes


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, used=0):
        self.used = used
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return Scalar(self.used if "count(*)" in str(statement) else 0)


def _patch_contract(monkeypatch, module, states, **inspector_kwargs):
    bind = Bind()
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.sa, "inspect", lambda _bind: Inspector(states, **inspector_kwargs),
    )
    return bind


def test_upgrade_adds_scene_contract_to_both_schemas(monkeypatch):
    module = migration()
    added, checks, indexes = [], [], []
    _patch_contract(monkeypatch, module, {"qc": "absent", "public": "absent"})
    monkeypatch.setattr(module.op, "add_column", lambda *args, **kwargs: added.append((args, kwargs)))
    monkeypatch.setattr(
        module.op, "create_check_constraint",
        lambda *args, **kwargs: checks.append((args, kwargs)),
    )
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: indexes.append((args, kwargs)))

    module.upgrade()

    assert module.revision == "20260928_000067"
    assert module.down_revision == "20260928_000066"
    assert [kwargs["schema"] for _, kwargs in added] == ["qc", "public"]
    assert [kwargs["schema"] for _, kwargs in checks] == ["qc", "public"]
    assert [kwargs["schema"] for _, kwargs in indexes] == ["qc", "public"]


def test_upgrade_accepts_postgres_reflected_check(monkeypatch):
    module = migration()
    _patch_contract(
        monkeypatch, module, {"qc": "present", "public": "present"}, reflected=True,
    )
    monkeypatch.setattr(module.op, "add_column", lambda *_args, **_kwargs: pytest.fail("不得重复 DDL"))
    module.upgrade()


def test_upgrade_rejects_partial_or_drifted_contract(monkeypatch):
    module = migration()
    _patch_contract(monkeypatch, module, {"qc": "present", "public": "absent"})
    with pytest.raises(RuntimeError, match="部分 schema"):
        module.upgrade()

    module = migration()
    _patch_contract(
        monkeypatch, module, {"qc": "present", "public": "present"}, extra_index=True,
    )
    with pytest.raises(RuntimeError, match="合同漂移"):
        module.upgrade()


def test_downgrade_refuses_used_scene(monkeypatch):
    module = migration()
    bind = Bind(used=1)
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.sa, "inspect",
        lambda _bind: Inspector({"qc": "present", "public": "present"}),
    )
    monkeypatch.setattr(module.op, "drop_column", lambda *_args, **_kwargs: pytest.fail("不得删列"))
    with pytest.raises(RuntimeError, match="拒绝降级"):
        module.downgrade()
