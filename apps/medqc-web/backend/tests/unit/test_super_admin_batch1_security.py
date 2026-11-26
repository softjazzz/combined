"""Super-Admin Batch 1 Security Hardening & RBAC Alignment unit tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import roles as roles_module
from app.core import security as security_module
from app.database import connection as db_conn
from app.database.models.v36_reports import SysUser
from app.routers import debug as debug_router
from app.routers import qc_sample_pools as sample_pools_router


# ---------------------------------------------------------------------------
# 1. roles.effective_roles accepts set / frozenset / Iterable safely
# ---------------------------------------------------------------------------


def test_effective_roles_accepts_iterables_and_rejects_strings_or_mappings():
    for container in (
        ["super_admin"],
        ("super_admin",),
        {"super_admin"},
        frozenset({"super_admin"}),
        (r for r in ["super_admin"]),
    ):
        expanded = roles_module.effective_roles(container)
        assert {"super_admin", "admin", "qc_manager", "developer"} <= set(expanded)
        assert "sync_admin" not in expanded
        assert "doctor" not in expanded

    sync_expanded = roles_module.effective_roles({"sync_admin"})
    assert {"sync_admin", "admin", "qc_manager", "developer", "super_admin"} <= set(sync_expanded)
    assert "doctor" not in sync_expanded

    assert roles_module.effective_roles({"doctor"}) == ["doctor"]
    assert roles_module.effective_roles("super_admin") == []
    assert roles_module.effective_roles(b"super_admin") == []
    assert roles_module.effective_roles({"super_admin": True}) == []
    assert roles_module.effective_roles(None) == []


# ---------------------------------------------------------------------------
# 2. security.is_global_system_admin_principal & fail-closed DB scope check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("roles", "institute_id", "expected"),
    [
        (["sync_admin"], None, True),
        (["sync_admin"], "H-A", True),
        ({"super_admin"}, None, True),
        ({"super_admin"}, "", True),
        ({"super_admin"}, "H-A", True),
        (["admin"], None, True),
        (["admin"], "", True),
        (["admin"], "H-A", False),
        (["qc_manager"], None, False),
        (["qc_manager"], "H-A", False),
        (["doctor"], None, False),
    ],
)
def test_is_global_system_admin_principal_policy(roles, institute_id, expected):
    assert security_module.is_global_system_admin_principal(roles, institute_id) is expected


def test_verify_persistent_global_admin_scope_fails_closed_503_on_unexpected_db_errors(monkeypatch):
    class _BrokenConnectionSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(db_conn, "SessionLocal", lambda: _BrokenConnectionSession())
    with pytest.raises(HTTPException) as exc_info:
        security_module.verify_global_system_admin(
            {"id": "u-admin", "roles": ["admin"], "institute_id": ""}
        )
    assert exc_info.value.status_code == 503

    class _GenericSqlAlchemyErrorSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *args, **kwargs):
            raise SQLAlchemyError("database timeout")

    monkeypatch.setattr(db_conn, "SessionLocal", lambda: _GenericSqlAlchemyErrorSession())
    with pytest.raises(HTTPException) as exc_info:
        security_module.verify_global_system_admin(
            {"id": "u-super", "roles": ["super_admin"], "institute_id": "H-A"}
        )
    assert exc_info.value.status_code == 503


def test_verify_persistent_global_admin_scope_allows_missing_sqlite_table_fallback(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(db_conn, "SessionLocal", sessions)
    try:
        actor = {"id": "u-global-admin", "roles": ["admin"], "institute_id": ""}
        assert security_module.verify_global_system_admin(actor) == actor
    finally:
        engine.dispose()


def test_verify_persistent_global_admin_scope_enforces_persisted_roles_and_active_flag(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    SysUser.__table__.create(engine)
    sessions = sessionmaker(bind=engine)
    with sessions.begin() as session:
        session.add_all(
            [
                SysUser(
                    id="super-bound",
                    username="super-bound",
                    display_name="super-bound",
                    institute_id="H-A",
                    role="super_admin",
                    roles_json=json.dumps(["super_admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="admin-bound",
                    username="admin-bound",
                    display_name="admin-bound",
                    institute_id="H-A",
                    role="admin",
                    roles_json=json.dumps(["admin"]),
                    is_active=True,
                ),
                SysUser(
                    id="super-disabled",
                    username="super-disabled",
                    display_name="super-disabled",
                    institute_id=None,
                    role="super_admin",
                    roles_json=json.dumps(["super_admin"]),
                    is_active=False,
                ),
            ]
        )

    monkeypatch.setattr(db_conn, "SessionLocal", sessions)
    try:
        # super_admin with institute_id is global
        ok_actor = {"id": "super-bound", "roles": ["super_admin"], "institute_id": "H-A"}
        assert security_module.verify_global_system_admin(ok_actor) == ok_actor

        # bound admin trying to omit institute_id in token is blocked (403)
        with pytest.raises(HTTPException) as exc_admin:
            security_module.verify_global_system_admin({"id": "admin-bound", "roles": ["admin"]})
        assert exc_admin.value.status_code == 403

        # disabled super_admin is blocked (403)
        with pytest.raises(HTTPException) as exc_disabled:
            security_module.verify_global_system_admin(
                {"id": "super-disabled", "roles": ["super_admin"]}
            )
        assert exc_disabled.value.status_code == 403
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# 3. debug.py /api/v1/debug/pdf-env role guard
# ---------------------------------------------------------------------------


def test_debug_pdf_env_requires_admin_roles():
    app = FastAPI()
    app.include_router(debug_router.router)
    client = TestClient(app)

    # unauthenticated rejected
    assert client.get("/api/v1/debug/pdf-env").status_code in (401, 403)

    for denied in ("doctor", "qc_manager", "reviewer", "coder"):
        app.dependency_overrides[security_module.get_current_user] = lambda r=denied: {
            "id": f"u-{r}",
            "roles": [r],
        }
        resp = client.get("/api/v1/debug/pdf-env")
        assert resp.status_code == 403, f"expected 403 for {denied}, got {resp.status_code}"

    for allowed in ("admin", "super_admin", "sync_admin"):
        app.dependency_overrides[security_module.get_current_user] = lambda r=allowed: {
            "id": f"u-{r}",
            "roles": [r],
        }
        resp = client.get("/api/v1/debug/pdf-env")
        assert resp.status_code == 200, f"expected 200 for {allowed}, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 4. qc_sample_pools.py sheet2-exact-review/acceptance-package endpoint guard
# ---------------------------------------------------------------------------


def test_sheet2_acceptance_package_endpoint_has_explicit_role_guard(monkeypatch, tmp_path: Path):
    pkg_file = tmp_path / "sheet2_pkg.json"
    pkg_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    monkeypatch.setattr(sample_pools_router, "_SHEET2_EXACT_REVIEW_ACCEPTANCE_JSON", pkg_file)

    # 直接注册路由处理器，验证端点自身依赖（不依赖外层 router 依赖）即可拦截低权限角色
    app = FastAPI()
    app.get("/acceptance-package")(
        sample_pools_router.get_sheet2_exact_review_acceptance_package
    )
    client = TestClient(app)

    assert client.get("/acceptance-package").status_code in (401, 403)

    for denied in ("doctor", "reviewer", "coder"):
        app.dependency_overrides[security_module.get_current_user] = lambda r=denied: {
            "id": f"u-{r}",
            "roles": [r],
        }
        resp = client.get("/acceptance-package")
        assert resp.status_code == 403, f"expected 403 for {denied}, got {resp.status_code}"

    for allowed in ("admin", "qc_manager", "super_admin", "sync_admin"):
        app.dependency_overrides[security_module.get_current_user] = lambda r=allowed: {
            "id": f"u-{r}",
            "roles": [r],
        }
        resp = client.get("/acceptance-package")
        assert resp.status_code == 200, f"expected 200 for {allowed}, got {resp.status_code}"
        assert resp.json()["data"] == {"status": "ok"}
