"""架构治理批次 1 回归测试：全局质控规则权限归一（503 fail-closed）与表结构探测去重。

纯离线测试（SQLite / Mock / AST），覆盖：
1. 停用账号、绑定院区 admin、绑定院区 super_admin、全局 admin/super_admin/sync_admin、
   损坏 roles_json、意外 DB 异常（503 fail-closed）六类核心权限场景；
2. 全部 5 个规则管理路由（semantic_rules / scoring_rules / rule_validation / custom_qc / qc_sichuan）
   统一委托给 app.core.security.require_global_qc_rule_admin 并保留各自错误文案；
3. 共享表结构探测 get_table_columns 的 SQLite 与 PostgreSQL search_path 优先级；
4. 增量 AST 门禁：防止路由重新拷贝 _is_global_admin_sync / _table_columns 或反向依赖整改服务私有函数。
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import roles as roles_module
from app.core import security as security_module
from app.database import connection as db_conn
from app.database import schema_introspection
from app.database.models.v36_reports import SysUser
from app.routers import (
    appeals,
    custom_qc,
    defects,
    qc,
    qc_sichuan,
    remediation,
    reports,
    rule_validation,
    scoring_rules,
    semantic_rules,
)
from app.services import user_scope_owner


BACKEND_APP_DIR = Path(__file__).resolve().parents[2] / "app"
ROUTERS_DIR = BACKEND_APP_DIR / "routers"

GLOBAL_RULE_ROUTERS = [
    ("semantic_rules", semantic_rules, "仅全局管理员允许修改语义规则"),
    ("scoring_rules", scoring_rules, "仅全局管理员允许修改评分规则"),
    ("rule_validation", rule_validation, "仅全局管理员允许执行该操作"),
    ("custom_qc", custom_qc, "仅全局管理员允许发布全局自定义规则"),
    ("qc_sichuan", qc_sichuan, "仅全局管理员允许执行该操作"),
]

TABLE_COLUMN_ROUTERS = [appeals, defects, qc, remediation, reports]


def _seed_sys_users():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    SysUser.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        session.add_all(
            [
                SysUser(
                    id="u-sync-bound",
                    username="u-sync-bound",
                    display_name="u-sync-bound",
                    institute_id="H-A",
                    role="sync_admin",
                    roles_json=json.dumps(["sync_admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-super-global",
                    username="u-super-global",
                    display_name="u-super-global",
                    institute_id=None,
                    role="super_admin",
                    roles_json=json.dumps(["super_admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-admin-global",
                    username="u-admin-global",
                    display_name="u-admin-global",
                    institute_id="",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-super-bound",
                    username="u-super-bound",
                    display_name="u-super-bound",
                    institute_id="H-A",
                    role="super_admin",
                    roles_json=json.dumps(["super_admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-admin-bound",
                    username="u-admin-bound",
                    display_name="u-admin-bound",
                    institute_id="H-A",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="u-super-disabled",
                    username="u-super-disabled",
                    display_name="u-super-disabled",
                    institute_id=None,
                    role="super_admin",
                    roles_json=json.dumps(["super_admin"]),
                    is_active=False,
                ),
                SysUser(
                    id="u-bad-roles-json",
                    username="u-bad-roles-json",
                    display_name="u-bad-roles-json",
                    institute_id=None,
                    role="super_admin",
                    roles_json="{broken-json",
                    is_active=True,
                ),
            ]
        )
    return engine, sessions


# ---------------------------------------------------------------------------
# 1. 全局质控规则权限判定矩阵（绑定院区一律拒绝 + DB 异常 503 fail-closed）
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("roles", "institute_id", "expected"),
    [
        (["sync_admin"], None, True),
        (["sync_admin"], "H-A", True),
        (["super_admin"], None, True),
        (["super_admin"], "", True),
        (["super_admin"], "H-A", False),
        (["admin"], None, True),
        (["admin"], "", True),
        (["admin"], "H-A", False),
        (["qc_manager"], None, False),
        (["doctor"], None, False),
    ],
)
def test_is_global_qc_rule_admin_principal_blocks_bound_super_admin_and_admin(
    roles, institute_id, expected
):
    assert security_module.is_global_qc_rule_admin_principal(roles, institute_id) is expected


@pytest.mark.parametrize(("router_name", "router_mod", "expected_detail"), GLOBAL_RULE_ROUTERS)
def test_all_five_routers_enforce_persistent_policy_matrix(
    monkeypatch, router_name, router_mod, expected_detail
):
    engine, sessions = _seed_sys_users()
    monkeypatch.setattr(db_conn, "SessionLocal", sessions)
    try:
        # 允许：sync_admin（即使带院区）、未绑定院区的 super_admin / admin
        for actor in (
            {"id": "u-sync-bound", "roles": ["sync_admin"], "institute_id": "H-A"},
            {"id": "u-super-global", "roles": ["super_admin"], "institute_id": ""},
            {"id": "u-admin-global", "roles": ["admin"], "institute_id": ""},
        ):
            router_mod._require_global_admin(actor)

        # 拒绝（403 且保留路由各自文案）：停用、绑定院区 super_admin、绑定院区 admin、损坏 roles_json、缺失用户
        for denied_actor in (
            None,
            {"id": "u-super-disabled", "roles": ["super_admin"], "institute_id": ""},
            {"id": "u-super-bound", "roles": ["super_admin"], "institute_id": "H-A"},
            # 即使令牌故意省略 institute_id，也必须以持久账号的院区绑定为准拦截
            {"id": "u-super-bound", "roles": ["super_admin"], "institute_id": ""},
            {"id": "u-admin-bound", "roles": ["admin"], "institute_id": "H-A"},
            {"id": "u-admin-bound", "roles": ["admin"], "institute_id": ""},
            {"id": "u-bad-roles-json", "roles": ["super_admin"], "institute_id": ""},
        ):
            with pytest.raises(HTTPException) as exc_info:
                router_mod._require_global_admin(denied_actor)
            assert exc_info.value.status_code == 403, f"{router_name} should reject {denied_actor}"
            assert exc_info.value.detail == expected_detail
    finally:
        engine.dispose()


@pytest.mark.parametrize(("router_name", "router_mod", "_detail"), GLOBAL_RULE_ROUTERS)
@pytest.mark.parametrize(
    "error_factory",
    [
        lambda: OperationalError("SELECT 1", {}, Exception("connection refused")),
        lambda: SQLAlchemyError("database timeout"),
        lambda: user_scope_owner.UserOwnerUnavailable("账号持久表不存在"),
        lambda: RuntimeError("unexpected pool error"),
    ],
)
def test_all_five_routers_fail_closed_503_on_persistent_read_errors(
    monkeypatch, router_name, router_mod, _detail, error_factory
):
    class _BrokenSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            raise error_factory()

    monkeypatch.setattr(db_conn, "SessionLocal", lambda: _BrokenSession())
    with pytest.raises(HTTPException) as exc_info:
        router_mod._require_global_admin(
            {"id": "u-super-global", "roles": ["super_admin"], "institute_id": ""}
        )
    assert exc_info.value.status_code == 503, f"{router_name} must fail closed with 503"


def test_minimal_sqlite_sys_users_without_institute_column_still_enforces_active(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE sys_users (id TEXT PRIMARY KEY, role TEXT, roles_json TEXT, is_active BOOLEAN)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO sys_users (id, role, roles_json, is_active) VALUES "
                "('u-disabled', 'super_admin', '[\"super_admin\"]', 0),"
                "('u-active', 'admin', '[\"admin\"]', 1)"
            )
        )
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(db_conn, "SessionLocal", sessions)
    try:
        with pytest.raises(HTTPException) as exc_info:
            security_module.require_global_qc_rule_admin(
                {"id": "u-disabled", "roles": ["super_admin"], "institute_id": ""}
            )
        assert exc_info.value.status_code == 403

        actor = {"id": "u-active", "roles": ["admin"], "institute_id": ""}
        assert security_module.require_global_qc_rule_admin(actor) == actor
    finally:
        engine.dispose()


def test_missing_sqlite_table_fallback_still_blocks_bound_super_admin(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(db_conn, "SessionLocal", sessions)
    try:
        with pytest.raises(HTTPException) as exc_info:
            security_module.require_global_qc_rule_admin(
                {"id": "u-bound", "roles": ["super_admin"], "institute_id": "H-A"}
            )
        assert exc_info.value.status_code == 403

        actor = {"id": "u-unbound", "roles": ["super_admin"], "institute_id": ""}
        assert security_module.require_global_qc_rule_admin(actor) == actor
    finally:
        engine.dispose()


def test_persistent_roles_authoritative_in_core_roles():
    assert roles_module.effective_persistent_roles("admin", None) == {"admin"}
    assert "super_admin" in roles_module.effective_persistent_roles("doctor", '["super_admin"]')
    assert roles_module.effective_persistent_roles("super_admin", "{corrupt") == set()


# ---------------------------------------------------------------------------
# 2. 共享表结构探测 get_table_columns（SQLite & PostgreSQL search_path）
# ---------------------------------------------------------------------------


def test_get_table_columns_sqlite_existing_and_missing():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE qc_defects (id TEXT, institute_id TEXT, status TEXT)"))
    sessions = sessionmaker(bind=engine)
    try:
        with sessions() as session:
            assert schema_introspection.get_table_columns(session, "qc_defects") == {
                "id",
                "institute_id",
                "status",
            }
            assert schema_introspection.get_table_columns(session, "nonexistent_table") == set()
    finally:
        engine.dispose()


def test_get_table_columns_postgresql_search_path_and_fallback_order(monkeypatch):
    class _FakeInspector:
        def __init__(self, tables_by_schema):
            self._tables_by_schema = tables_by_schema
            self.checked = []

        def has_table(self, table_name, schema=None):
            self.checked.append((schema, table_name))
            return table_name in self._tables_by_schema.get(schema, {})

        def get_columns(self, table_name, schema=None):
            return [{"name": col} for col in self._tables_by_schema[schema][table_name]]

    fake_session = SimpleNamespace(
        get_bind=lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    )

    # 1) configured_search_path 优先于默认兜底列表
    inspector1 = _FakeInspector(
        {
            "custom_tenant": {"qc_tasks": ["id", "custom_col"]},
            "qc": {"qc_tasks": ["id", "qc_col"]},
        }
    )
    monkeypatch.setattr(schema_introspection, "configured_search_path", lambda: ["custom_tenant", "qc"])
    monkeypatch.setattr(schema_introspection, "sa_inspect", lambda _bind: inspector1)
    assert schema_introspection.get_table_columns(fake_session, "qc_tasks") == {"id", "custom_col"}
    assert inspector1.checked == [("custom_tenant", "qc_tasks")]

    # 2) search_path 未命中时按 qc -> public -> sys -> cdm -> default 顺序回退
    inspector2 = _FakeInspector(
        {
            "sys": {"sys_users": ["id", "institute_id"]},
            None: {"legacy_only": ["id"]},
        }
    )
    monkeypatch.setattr(schema_introspection, "configured_search_path", lambda: ["public"])
    monkeypatch.setattr(schema_introspection, "sa_inspect", lambda _bind: inspector2)
    assert schema_introspection.get_table_columns(fake_session, "sys_users") == {"id", "institute_id"}
    assert inspector2.checked == [("public", "sys_users"), ("qc", "sys_users"), ("sys", "sys_users")]
    assert schema_introspection.get_table_columns(fake_session, "legacy_only") == {"id"}
    assert schema_introspection.get_table_columns(fake_session, "absent") == set()


def test_all_five_routers_bind_to_single_shared_table_columns_helper():
    for router_mod in TABLE_COLUMN_ROUTERS:
        assert router_mod._table_columns is schema_introspection.get_table_columns


# ---------------------------------------------------------------------------
# 3. 增量 AST 门禁：阻止副本回流与反向依赖
# ---------------------------------------------------------------------------


def test_ast_guard_no_router_redefines_global_admin_sync_or_table_columns():
    offenders_admin: list[str] = []
    offenders_table_cols: list[str] = []
    for path in sorted(ROUTERS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_is_global_admin_sync":
                    offenders_admin.append(path.name)
                if node.name == "_table_columns":
                    offenders_table_cols.append(path.name)
    assert offenders_admin == [], f"路由禁止重新定义 _is_global_admin_sync: {offenders_admin}"
    assert offenders_table_cols == [], f"路由禁止重新定义 _table_columns: {offenders_table_cols}"


def test_ast_guard_global_rule_routers_and_core_security_do_not_query_sys_users_or_import_private_service_roles():
    checked_paths = [
        BACKEND_APP_DIR / "core" / "security.py",
        *(ROUTERS_DIR / f"{name}.py" for name, _, _ in GLOBAL_RULE_ROUTERS),
    ]
    for path in checked_paths:
        src = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(src, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
                "defect_rectification_service"
            ):
                imported = {alias.name for alias in node.names}
                assert "_effective_persistent_roles" not in imported, (
                    f"{path.name} 不得从 defect_rectification_service 导入私有 _effective_persistent_roles"
                )
        if path.parent == ROUTERS_DIR:
            assert "FROM {table_ref}" not in src and "sys_users" not in src, (
                f"规则管理路由 {path.name} 不得自行拼装 sys_users 持久查询，请复用 app.core.security"
            )
