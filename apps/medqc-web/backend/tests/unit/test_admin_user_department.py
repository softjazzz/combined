"""管理员维护账号医院＋科室：持久 actor、CAS、选项校验与审计。"""
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
        for user_id, name, institute_id, department in (
            ("doc-1", "张医生", "hospital-a", "心内科"),
            ("doc-2", "李医生", None, None),
            ("admin-1", "管理员", "hospital-a", "信息科"),
        ):
            conn.execute(table.insert().values(
                id=user_id, username=user_id, display_name=name,
                institute_id=institute_id, department=department,
                role="doctor" if user_id.startswith("doc") else "admin",
                is_active=True, created_at=ORIGINAL_VERSION, updated_at=ORIGINAL_VERSION,
            ))
    user = {"id": "admin-1", "roles": ["admin"]}
    options = [
        {"institute_id": "hospital-a", "department": "心内科"},
        {"institute_id": "hospital-a", "department": "信息科"},
        {"institute_id": "hospital-b", "department": "心内科"},
        {"institute_id": "hospital-b", "department": "骨科"},
    ]
    service = AdminUserService(sessions, scope_options_loader=lambda _session: options)
    app = FastAPI()
    app.include_router(admin_users.router)
    app.dependency_overrides[security.get_current_user] = lambda: user
    app.dependency_overrides[admin_users.get_admin_user_service] = lambda: service
    with TestClient(app) as client:
        yield client, sessions, table, user, service
    engine.dispose()


def _scope(sessions, table, user_id):
    with sessions() as session:
        return session.execute(
            sa.select(table.c.institute_id, table.c.department).where(table.c.id == user_id)
        ).one()


def test_list_filters_and_reports_unassigned(env):
    client, sessions, table, *_ = env
    data = client.get("/api/v1/admin/users").json()["data"]
    assert data["total"] == 3
    assert data["departments"] == ["信息科", "心内科"]
    assert next(item for item in data["items"] if item["id"] == "doc-1")["institute_id"] == "hospital-a"
    unassigned = client.get("/api/v1/admin/users", params={"department": "__unassigned__"}).json()["data"]
    assert [item["id"] for item in unassigned["items"]] == ["doc-2"]
    assert unassigned["items"][0]["department"] is None
    by_name = client.get("/api/v1/admin/users", params={"q": "张"}).json()["data"]
    assert [item["id"] for item in by_name["items"]] == ["doc-1"]
    options = client.get("/api/v1/admin/users/scope-options").json()["data"]
    assert options["institutes"] == ["hospital-a", "hospital-b"]
    assert {tuple(item.values()) for item in options["items"]} == {
        ("hospital-a", "信息科"), ("hospital-a", "心内科"),
        ("hospital-b", "心内科"), ("hospital-b", "骨科"),
    }

    with sessions.begin() as session:
        session.execute(
            table.update().where(table.c.id == "doc-1").values(institute_id=None)
        )
    legacy_unassigned = client.get(
        "/api/v1/admin/users", params={"department": "__unassigned__"},
    ).json()["data"]
    assert {item["id"] for item in legacy_unassigned["items"]} == {"doc-1", "doc-2"}


def test_admin_sets_scope_with_cas_and_strictly_advances_version(env, caplog):
    client, sessions, table, _user, _service = env
    url = "/api/v1/admin/users/doc-2/department"
    caplog.set_level("INFO")
    ok = client.put(url, json={
        "institute_id": " hospital-b ", "department": " 骨科 ",
        "expected_updated_at": ORIGINAL_VERSION.isoformat(),
    })
    assert ok.status_code == 200
    body = ok.json()["data"]
    assert body["institute_id"] == "hospital-b"
    assert body["department"] == "骨科"
    assert body["previous_institute_id"] is None
    assert body["previous_department"] is None
    assert body["updated_at"] > ORIGINAL_VERSION.isoformat()
    assert tuple(_scope(sessions, table, "doc-2")) == ("hospital-b", "骨科")
    assert "admin_user_scope_update" in caplog.text
    stale = client.put(url, json={
        "institute_id": "hospital-a", "department": "心内科",
        "expected_updated_at": ORIGINAL_VERSION.isoformat(),
    })
    assert stale.status_code == 409
    assert tuple(_scope(sessions, table, "doc-2")) == ("hospital-b", "骨科")
    cleared = client.put(url, json={
        "institute_id": None, "department": None, "expected_updated_at": body["updated_at"],
    })
    assert cleared.status_code == 200
    assert tuple(_scope(sessions, table, "doc-2")) == (None, None)


def test_rejects_missing_user_and_bad_or_untrusted_scope(env):
    client, sessions, table, _user, _service = env
    version = ORIGINAL_VERSION.isoformat()
    assert client.put(
        "/api/v1/admin/users/nobody/department",
        json={"institute_id": "hospital-b", "department": "骨科", "expected_updated_at": version},
    ).status_code == 404
    assert client.put(
        "/api/v1/admin/users/doc-1/department",
        json={"institute_id": "hospital-b", "department": "骨科"},
    ).status_code == 422
    assert client.put(
        "/api/v1/admin/users/doc-1/department",
        json={"institute_id": "hospital-b", "department": "骨科", "expected_updated_at": version,
              "roles": ["admin"]},
    ).status_code == 422
    for payload in (
        {"institute_id": "hospital-b", "department": None, "expected_updated_at": version},
        {"institute_id": None, "department": "骨科", "expected_updated_at": version},
        {"institute_id": "hospital-a", "department": "骨科", "expected_updated_at": version},
    ):
        assert client.put("/api/v1/admin/users/doc-1/department", json=payload).status_code == 422
    assert tuple(_scope(sessions, table, "doc-1")) == ("hospital-a", "心内科")


@pytest.mark.parametrize("change", ["revoked", "inactive", "deleted"])
def test_memory_admin_cannot_write_after_persistent_actor_is_invalid(env, change, monkeypatch):
    client, sessions, table, _user, service = env
    calls = []
    original = service.set_scope

    def tracked(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(service, "set_scope", tracked)
    with sessions.begin() as session:
        if change == "revoked":
            session.execute(sa.update(table).where(table.c.id == "admin-1").values(role="qc_manager"))
        elif change == "inactive":
            session.execute(sa.update(table).where(table.c.id == "admin-1").values(is_active=False))
        else:
            session.execute(sa.delete(table).where(table.c.id == "admin-1"))
    response = client.put("/api/v1/admin/users/doc-2/department", json={
        "institute_id": "hospital-b", "department": "骨科",
        "expected_updated_at": ORIGINAL_VERSION.isoformat(),
    })
    assert response.status_code == 403
    assert calls == []
    assert tuple(_scope(sessions, table, "doc-2")) == (None, None)


def test_durable_admin_database_failure_returns_503_without_scope_write(env, monkeypatch):
    client, sessions, table, _user, service = env
    calls = []
    monkeypatch.setattr(
        service, "require_durable_admin",
        lambda _user_id: (_ for _ in ()).throw(admin_users.AdminUserUnavailable("down")),
    )
    monkeypatch.setattr(service, "set_scope", lambda **kwargs: calls.append(kwargs))
    response = client.put("/api/v1/admin/users/doc-2/department", json={
        "institute_id": "hospital-b", "department": "骨科",
        "expected_updated_at": ORIGINAL_VERSION.isoformat(),
    })
    assert response.status_code == 503
    assert calls == []
    assert tuple(_scope(sessions, table, "doc-2")) == (None, None)


def test_scope_options_are_loaded_before_binding_sys_user_owner(env, monkeypatch):
    _client, _sessions, _table, _user, service = env
    bound_sessions = set()
    original_bind = service._bind_owner

    def track_bind(session):
        bound_sessions.add(id(session))
        return original_bind(session)

    def assert_unbound(session):
        assert id(session) not in bound_sessions
        return [{"institute_id": "hospital-b", "department": "骨科"}]

    monkeypatch.setattr(service, "_bind_owner", track_bind)
    monkeypatch.setattr(service, "_scope_options_loader", assert_unbound)
    service.set_scope(
        user_id="doc-2", institute_id="hospital-b", department="骨科",
        expected_updated_at=ORIGINAL_VERSION,
    )
    assert len(bound_sessions) == 1


def test_scope_option_source_failure_returns_503_without_write(env, monkeypatch):
    client, sessions, table, _user, service = env
    monkeypatch.setattr(
        service, "_scope_options_loader",
        lambda _session: (_ for _ in ()).throw(RuntimeError("private source failure")),
    )
    response = client.put("/api/v1/admin/users/doc-2/department", json={
        "institute_id": "hospital-b", "department": "骨科",
        "expected_updated_at": ORIGINAL_VERSION.isoformat(),
    })
    assert response.status_code == 503
    assert "private" not in response.text
    assert tuple(_scope(sessions, table, "doc-2")) == (None, None)
