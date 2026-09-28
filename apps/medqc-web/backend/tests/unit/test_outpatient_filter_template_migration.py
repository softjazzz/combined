"""迁移 63 门急诊筛选模板 page_key 约束合同（fake inspector，不连接数据库）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def migration():
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/20260927_000063_outpatient_filter_templates.py"
    )
    spec = importlib.util.spec_from_file_location("outpatient_filter_template_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Inspector:
    def __init__(self, module, states):
        self.module = module
        self.states = states

    def has_table(self, _table, schema):
        return self.states[schema] != "missing"

    def get_check_constraints(self, _table, schema):
        state = self.states[schema]
        if state == "old":
            sql = self.module.check_sql(self.module.OLD_PAGE_KEYS)
        elif state == "new":
            sql = self.module.check_sql(self.module.NEW_PAGE_KEYS)
        else:
            sql = "page_key IN ('drifted')"
        return [{"name": self.module.CHECK_NAME, "sqltext": sql}]


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.queries = []

    def execute(self, statement, params):
        sql = str(statement)
        self.queries.append((sql, params))
        schema = next(schema for schema in ("qc", "public") if f'"{schema}"' in sql)
        return Scalar(self.counts.get(schema, 0))


def fake(monkeypatch, module, states, counts=None):
    calls = []
    bind = Bind(counts)
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: Inspector(module, states))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(
        module.op,
        "drop_constraint",
        lambda *args, **kwargs: calls.append(("drop", args, kwargs)),
    )
    monkeypatch.setattr(
        module.op,
        "create_check_constraint",
        lambda *args, **kwargs: calls.append(("create", args, kwargs)),
    )
    return bind, calls


def test_upgrade_replaces_old_check_in_both_schemas(monkeypatch):
    module = migration()
    assert module.revision == "20260927_000063"
    assert module.down_revision == "20260927_000062"
    _, calls = fake(monkeypatch, module, {"qc": "old", "public": "old"})

    module.upgrade()

    assert [(action, kwargs["schema"]) for action, _, kwargs in calls] == [
        ("drop", "qc"), ("create", "qc"),
        ("drop", "public"), ("create", "public"),
    ]
    creates = [args for action, args, _ in calls if action == "create"]
    assert all(module.OUTPATIENT_PAGE_KEY in args[2] for args in creates)


def test_upgrade_is_idempotent_when_both_schemas_are_new(monkeypatch):
    module = migration()
    _, calls = fake(monkeypatch, module, {"qc": "new", "public": "new"})
    module.upgrade()
    assert calls == []


@pytest.mark.parametrize("states", [
    {"qc": "old", "public": "new"},
    {"qc": "old", "public": "missing"},
    {"qc": "old", "public": "drift"},
])
def test_upgrade_rejects_mixed_missing_or_drifted_state_before_ddl(monkeypatch, states):
    module = migration()
    _, calls = fake(monkeypatch, module, states)
    with pytest.raises(RuntimeError):
        module.upgrade()
    assert calls == []


def test_postgres_reflected_any_form_is_accepted():
    module = migration()
    reflected = (
        "((page_key)::text = ANY ((ARRAY['v5_records_inpatient'::character varying, "
        "'v5_records_discharged'::character varying, "
        "'v5_records_outpatient_emergency'::character varying])::text[]))"
    )
    assert module.normalized_check(reflected) == module.normalized_check(
        module.check_sql(module.NEW_PAGE_KEYS)
    )


def test_downgrade_rejects_existing_outpatient_templates(monkeypatch):
    module = migration()
    bind, calls = fake(
        monkeypatch,
        module,
        {"qc": "new", "public": "new"},
        counts={"qc": 0, "public": 2},
    )
    with pytest.raises(RuntimeError, match="public.*拒绝降级"):
        module.downgrade()
    assert len(bind.queries) == 2
    assert calls == []


def test_downgrade_without_outpatient_templates_restores_old_check(monkeypatch):
    module = migration()
    _, calls = fake(
        monkeypatch,
        module,
        {"qc": "new", "public": "new"},
        counts={"qc": 0, "public": 0},
    )
    module.downgrade()
    creates = [(args, kwargs) for action, args, kwargs in calls if action == "create"]
    assert [kwargs["schema"] for _, kwargs in creates] == ["qc", "public"]
    assert all(module.OUTPATIENT_PAGE_KEY not in args[2] for args, _ in creates)
