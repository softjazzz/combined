"""迁移71扫码会话表的合成合同。"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


def _migration():
    path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260928_000071_qr_login_sessions.py"
    )
    spec = spec_from_file_location("qr_login_migration_71", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Inspector:
    def __init__(self, tables):
        self.tables = set(tables)

    def has_table(self, table, schema=None):
        return (schema, table) in self.tables


def test_upgrade_creates_only_authoritative_sys_table(monkeypatch):
    migration = _migration()
    inspector = Inspector({("sys", "sys_users")})
    created = []
    indexes = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda table, *parts, **kwargs: created.append((table, parts, kwargs)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table, columns, **kwargs: indexes.append((name, table, columns, kwargs)),
    )

    migration.upgrade()

    assert len(created) == 1
    assert created[0][0] == migration.TABLE
    assert created[0][2]["schema"] == "sys"
    assert {item[0] for item in indexes} == set(migration.INDEXES)
    foreign_keys = [part for part in created[0][1] if part.__class__.__name__ == "ForeignKeyConstraint"]
    assert len(foreign_keys) == 1
    assert foreign_keys[0].elements[0]._colspec == "sys.sys_users.id"


def test_ambiguous_or_missing_authoritative_user_schema_fails_closed():
    migration = _migration()
    with pytest.raises(RuntimeError):
        migration._target_schema(Inspector(set()))
    with pytest.raises(RuntimeError):
        migration._target_schema(
            Inspector({("sys", "sys_users"), ("public", "sys_users")})
        )


def test_postgres_any_reflection_matches_status_in_contract():
    migration = _migration()
    reflected = (
        "status = ANY (ARRAY['pending'::character varying, "
        "'approved'::character varying, 'rejected'::character varying, "
        "'cancelled'::character varying, 'expired'::character varying, "
        "'consumed'::character varying])"
    )
    assert migration._normalized(reflected) == migration._normalized(
        migration.CHECKS["ck_sys_qr_login_sessions_status"]
    )


def test_downgrade_refuses_nonempty_session_table(monkeypatch):
    migration = _migration()
    inspector = Inspector({("sys", "sys_users"), ("sys", migration.TABLE)})
    monkeypatch.setattr(migration, "_validate_existing", lambda *_args: None)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: inspector)

    class Result:
        @staticmethod
        def scalar_one():
            return 1

    class Bind:
        @staticmethod
        def execute(*_args, **_kwargs):
            return Result()

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    with pytest.raises(RuntimeError, match="拒绝降级"):
        migration.downgrade()
