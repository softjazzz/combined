"""迁移 64 双 schema 与防丢数据合同，不连接数据库。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20260927_000064_task_templates.py"
    spec = importlib.util.spec_from_file_location("task_template_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Inspector:
    def __init__(self, existing):
        self.existing = set(existing)

    def has_table(self, _table, schema):
        return schema in self.existing


class Scalar:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value


class Bind:
    def __init__(self, counts=None):
        self.counts = counts or {}
        self.sql = []

    def execute(self, statement):
        sql = str(statement)
        self.sql.append(sql)
        for schema, count in self.counts.items():
            if f'"{schema}"' in sql and "count(*)" in sql:
                return Scalar(count)
        return Scalar(0)


def test_upgrade_creates_exact_table_and_owner_index_in_both_schemas(monkeypatch):
    module = migration()
    bind = Bind()
    creates = []
    indexes = []
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: Inspector([]))
    monkeypatch.setattr(module.op, "create_table", lambda *args, **kwargs: creates.append((args, kwargs)))
    monkeypatch.setattr(module.op, "create_index", lambda *args, **kwargs: indexes.append((args, kwargs)))

    module.upgrade()

    assert module.revision == "20260927_000064"
    assert module.down_revision == "20260927_000063"
    assert [kwargs["schema"] for _, kwargs in creates] == ["qc", "public"]
    assert all(args[0] == "qc_task_templates" for args, _ in creates)
    assert [kwargs["schema"] for _, kwargs in indexes] == ["qc", "public"]


def test_upgrade_rejects_partial_dual_schema_before_ddl(monkeypatch):
    module = migration()
    monkeypatch.setattr(module, "_validate_existing", lambda *_args: None)
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: Inspector(["qc"]))
    monkeypatch.setattr(module.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(module.op, "create_table", lambda *_args, **_kwargs: pytest.fail("不得执行DDL"))
    with pytest.raises(RuntimeError, match="两套 schema"):
        module.upgrade()


def test_downgrade_refuses_nonempty_user_table(monkeypatch):
    module = migration()
    bind = Bind({"qc": 0, "public": 1})
    monkeypatch.setattr(module, "_validate_existing", lambda *_args: None)
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: Inspector(["qc", "public"]))
    monkeypatch.setattr(module.op, "get_bind", lambda: bind)
    monkeypatch.setattr(module.op, "drop_table", lambda *_args, **_kwargs: pytest.fail("不得删表"))
    monkeypatch.setattr(module.op, "drop_index", lambda *_args, **_kwargs: pytest.fail("不得删索引"))
    with pytest.raises(RuntimeError, match="public.*拒绝降级"):
        module.downgrade()
