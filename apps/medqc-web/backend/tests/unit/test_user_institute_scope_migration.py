"""账号医院迁移只改明确 owner，保留历史账号并拒绝丢失归属。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa


@pytest.fixture
def migration(monkeypatch):
    path = Path(__file__).parents[2] / "alembic/versions/20260930_000076_user_institute_scope.py"
    spec = spec_from_file_location("user_scope_migration_76", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "configured_search_path", lambda: ["qc", "sys", "public"])
    monkeypatch.setattr(module.context, "is_offline_mode", lambda: False)
    return module


class Inspector:
    def __init__(self, *, deployed=False, schemas=("sys", "public")):
        self.schemas = schemas
        self.columns = [{"name": "id"}, {"name": "department"}]
        self.indexes = []
        self.read_schemas = []
        if deployed:
            self.columns.append({
                "name": "institute_id", "type": sa.String(128),
                "nullable": True, "default": None,
            })
            self.indexes.append({
                "name": "ix_sys_users_institute_department",
                "column_names": ["institute_id", "department"], "unique": False,
            })

    def has_table(self, table, schema=None):
        return table == "sys_users" and schema in self.schemas

    def get_schema_names(self):
        return list(self.schemas)

    def get_columns(self, table, schema=None):
        self.read_schemas.append(schema)
        return self.columns

    def get_indexes(self, table, schema=None):
        self.read_schemas.append(schema)
        return self.indexes


def test_upgrade_only_changes_configured_owner_without_backfill(migration, monkeypatch):
    inspector = Inspector()
    added, indexed = [], []
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)
    monkeypatch.setattr(migration.op, "add_column", lambda *args, **kw: added.append((args, kw)))
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kw: indexed.append((args, kw)))
    migration.upgrade()
    assert len(added) == len(indexed) == 1
    assert added[0][1]["schema"] == indexed[0][1]["schema"] == "sys"
    column = added[0][0][1]
    assert column.name == "institute_id" and column.nullable
    assert column.default is None and column.server_default is None
    assert set(inspector.read_schemas) == {"sys"}


def test_completed_upgrade_is_idempotent(migration, monkeypatch):
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: Inspector(deployed=True))
    monkeypatch.setattr(migration.op, "add_column", lambda *_a, **_k: pytest.fail("重复添加列"))
    migration.upgrade()


@pytest.mark.parametrize("drift", ["column_only", "index_only", "length", "nullable", "default", "unique", "order"])
def test_partial_or_drifted_schema_is_rejected(migration, drift):
    inspector = Inspector(deployed=True)
    if drift == "column_only":
        inspector.indexes.clear()
    elif drift == "index_only":
        inspector.columns.pop()
    elif drift == "length":
        inspector.columns[-1]["type"] = sa.String(64)
    elif drift == "nullable":
        inspector.columns[-1]["nullable"] = False
    elif drift == "default":
        inspector.columns[-1]["default"] = "'hospital-a'"
    elif drift == "unique":
        inspector.indexes[0]["unique"] = True
    else:
        inspector.indexes[0]["column_names"].reverse()
    with pytest.raises(RuntimeError, match="漂移"):
        migration._state(inspector, "sys")


def test_ambiguous_owner_without_configuration_is_rejected(migration, monkeypatch):
    monkeypatch.setattr(migration, "configured_search_path", lambda: [])
    with pytest.raises(RuntimeError, match="不唯一"):
        migration._target_schema(Inspector())


def test_single_public_owner_is_supported(migration, monkeypatch):
    monkeypatch.setattr(migration, "configured_search_path", lambda: [])
    assert migration._target_schema(Inspector(schemas=("public",))) == "public"


@pytest.mark.parametrize("count", [0, 1])
def test_downgrade_locks_and_preserves_existing_assignments(migration, monkeypatch, count):
    statements, dropped = [], []

    class Result:
        def scalar_one(self):
            return count

    class Bind:
        def execute(self, statement):
            statements.append(str(statement))
            return Result()

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: Inspector(deployed=True))
    monkeypatch.setattr(migration.op, "drop_index", lambda *args, **kw: dropped.append((args, kw)))
    monkeypatch.setattr(migration.op, "drop_column", lambda *args, **kw: dropped.append((args, kw)))
    if count:
        with pytest.raises(RuntimeError, match="拒绝降级"):
            migration.downgrade()
        assert dropped == []
    else:
        migration.downgrade()
        assert len(dropped) == 2
        assert all(kwargs["schema"] == "sys" for _args, kwargs in dropped)
    assert "ACCESS EXCLUSIVE" in statements[0]
    assert '"sys"."sys_users"' in statements[1]


def test_offline_downgrade_cannot_bypass_nonempty_guard(migration, monkeypatch):
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)
    with pytest.raises(RuntimeError, match="在线核验"):
        migration.downgrade()
