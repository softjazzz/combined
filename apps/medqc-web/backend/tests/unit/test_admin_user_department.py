"""管理员维护账号科室：仅 admin 可写、CAS、审计；科室决定医生数据范围。"""
from __future__ import annotations

from datetime import datetime

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import security
from app.database.models.qc import SysUser
from app.routers import admin_users
from app.services.admin_user_service import AdminUserService

ORIGINAL_VERSION = datetime(2026, 9, 30, 8, 0, 0)


@pytest.fixture
def env():
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    SysUser.__table__.to_metadata(sa.MetaData(), schema=None).create(engine)
    sessions = sessionmaker(bind=engine)
    table = sa.Table("sys_users", sa.MetaData(), autoload_with=engine)
    with engine.begin() as conn:
        for user_id, name, department in (
            ("doc-1", "张医生", "心内科"),
            ("doc-2", "李医生", None),
            ("admin-1", "管理员", "信息科"),
        ):
            conn.execute(table.insert().values(
                id=user_id, username=user_id, display_name=name, department=department,
                role="doctor" if user_id.startswith("doc") else "admin",
                is_active=True, created_at=ORIGINAL_VERSION, updated_at=ORIGINAL_VERSION,
            ))
    user = {"id": "admin-1", "roles": ["admin"]}
    app = FastAPI()
    app.include_router(admin_users.router)
    app.dependency_overrides[security.get_current_user] = lambda: user
    app.dependency_overrides[admin_users.get_admin_user_service] = lambda: AdminUserService(sessions)
    with TestClient(app) as client:
        yield client, sessions, table, user
    engine.dispose()


def _department(sessions, table, user_id):
    with sessions() as session:
        return session.execute(sa.select(table.c.department).where(table.c.id == user_id)).scalar()


def test_list_filters_and_reports_unassigned(env):
    client, *_ = env
    data = client.get("/api/v1/admin/users").json()["data"]
    assert data["total"] == 3
    assert data["departments"] == ["信息科", "心内科"]
    unassigned = client.get("/api/v1/admin/users", params={"department": "__unassigned__"}).json()["data"]
    assert [item["id"] for item in unassigned["items"]] == ["doc-2"]
    assert unassigned["items"][0]["department"] is None
    by_name = client.get("/api/v1/admin/users", params={"q": "张"}).json()["data"]
    assert [item["id"] for item in by_name["items"]] == ["doc-1"]


def test_admin_sets_department_with_cas_and_strictly_advances_version(env, caplog):
    client, sessions, table, _user = env
    url = "/api/v1/admin/users/doc-2/department"
    caplog.set_level("INFO")
    ok = client.put(url, json={"department": " 骨科 ", "expected_updated_at": ORIGINAL_VERSION.isoformat()})
    assert ok.status_code == 200
    body = ok.json()["data"]
    assert body["department"] == "骨科"
    assert body["previous_department"] is None
    assert body["updated_at"] > ORIGINAL_VERSION.isoformat()
    assert _department(sessions, table, "doc-2") == "骨科"
    assert "admin_user_department_update" in caplog.text
    stale = client.put(url, json={"department": "外科", "expected_updated_at": ORIGINAL_VERSION.isoformat()})
    assert stale.status_code == 409
    assert _department(sessions, table, "doc-2") == "骨科"
    cleared = client.put(url, json={"department": "  ", "expected_updated_at": body["updated_at"]})
    assert cleared.status_code == 200
    assert _department(sessions, table, "doc-2") is None


def test_rejects_missing_user_bad_payload_and_non_admin(env):
    client, sessions, table, user = env
    version = ORIGINAL_VERSION.isoformat()
    assert client.put(
        "/api/v1/admin/users/nobody/department", json={"department": "骨科", "expected_updated_at": version},
    ).status_code == 404
    assert client.put(
        "/api/v1/admin/users/doc-1/department", json={"department": "骨科"},
    ).status_code == 422
    assert client.put(
        "/api/v1/admin/users/doc-1/department",
        json={"department": "骨科", "expected_updated_at": version, "roles": ["admin"]},
    ).status_code == 422
    user["roles"] = ["qc_manager"]
    assert client.get("/api/v1/admin/users").status_code == 403
    assert client.put(
        "/api/v1/admin/users/doc-1/department", json={"department": "骨科", "expected_updated_at": version},
    ).status_code == 403
    assert _department(sessions, table, "doc-1") == "心内科"
