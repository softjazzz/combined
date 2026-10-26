"""真实账号维护只在临时 SQLite 验证，不读取应用默认数据库。"""

import json
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user, verify_password
from app.database.models.v36_reports import SysUser
from app.routers import account_management as router
from app.routers import auth as auth_router
from app.services import auth_store
from app.services.account_management_service import AccountManagementService


@pytest.fixture
def accounts(monkeypatch):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    SysUser.__table__.create(engine)
    sessions = sessionmaker(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with sessions.begin() as session:
        for id, role, institute in (
            ("admin", "admin", "A"),
            ("qc", "qc_manager", "A"),
            ("doc", "doctor", "A"),
            ("foreign", "admin", "B"),
        ):
            session.add(
                SysUser(
                    id=id,
                    username=id,
                    email=f"{id}@example.com",
                    display_name=id,
                    institute_id=institute,
                    department="内科",
                    role=role,
                    roles_json=json.dumps([role]),
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
    service = AccountManagementService(sessions)
    monkeypatch.setattr(router, "service", service)
    monkeypatch.setattr(auth_store, "SessionLocal", sessions)
    app = FastAPI()
    app.include_router(router.router)
    app.include_router(auth_router.router)
    actor = {"id": "admin", "roles": ["admin"]}
    app.dependency_overrides[get_current_user] = lambda: dict(actor)
    yield service, sessions, TestClient(app), actor
    engine.dispose()


def payload(**changes):
    return (
        dict(
            username="new_doctor",
            email="new-doctor@example.com",
            password="test-only-password!",
            display_name="合成医生",
            institute_id="A",
            department="内科",
            roles=["doctor"],
        )
        | changes
    )


def test_create_persistent_login_and_never_return_hash(accounts):
    _, sessions, client, _ = accounts
    response = client.post("/api/v1/account-management", json=payload())
    assert response.status_code == 200, response.text
    row = response.json()["data"]
    assert "password" not in row and "password_hash" not in row
    with sessions() as session:
        stored = session.get(SysUser, row["id"])
        assert verify_password(payload()["password"], stored.password_hash)
        assert stored.institute_id == "A"
    assert auth_store.find_user_by_account("new_doctor")["id"] == row["id"]
    page = client.get(
        "/api/v1/account-management", params={"keyword": "合成", "role": "doctor"}
    ).json()["data"]
    assert page["total"] == 1 and page["items"][0]["id"] == row["id"]
    assert "password_hash" not in str(page)


def test_real_auth_payload_keeps_persistent_institute_and_active_state(accounts):
    _, sessions, client, _ = accounts
    created = client.post("/api/v1/account-management", json=payload()).json()["data"]
    client.app.dependency_overrides.clear()
    login = client.post("/api/v1/auth/login", json={
        "account": payload()["username"], "password": payload()["password"],
    })
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
    before = client.get("/api/v1/auth/me", headers=headers)
    assert before.status_code == 200
    assert before.json()["data"]["institute_id"] == "A"
    assert before.json()["data"]["is_active"] is True
    with sessions.begin() as session:
        session.get(SysUser, created["id"]).institute_id = "B"
    after = client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 200
    assert after.json()["data"]["institute_id"] == "B"
    assert after.json()["data"]["id"] == before.json()["data"]["id"]
    assert after.json()["data"]["roles"] == before.json()["data"]["roles"]
    with sessions.begin() as session:
        session.get(SysUser, created["id"]).is_active = False
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


@pytest.mark.parametrize("actor_id", ["qc", "doc", "memory-only"])
def test_token_role_does_not_replace_persistent_admin(accounts, actor_id):
    _, _, client, actor = accounts
    actor.update(id=actor_id, roles=["admin"])
    assert client.get("/api/v1/account-management").status_code == 403
    assert client.post("/api/v1/account-management", json=payload()).status_code == 403


def test_bound_admin_cannot_read_create_or_update_foreign_accounts(accounts):
    service, _, client, _ = accounts
    page = service.list("admin")
    assert "foreign" not in [row["id"] for row in page["items"]]
    assert (
        client.post(
            "/api/v1/account-management", json=payload(institute_id="B")
        ).status_code
        == 403
    )
    foreign = service.list("foreign")["items"][0]
    response = client.put("/api/v1/account-management/foreign", json=edit(foreign))
    assert response.status_code == 403


def edit(row, **changes):
    return (
        {
            key: row[key]
            for key in (
                "display_name",
                "institute_id",
                "department",
                "roles",
                "is_active",
            )
        }
        | {
            "expected_updated_at": row["updated_at"],
        }
        | changes
    )


def test_edit_cas_disable_old_token_and_reenable(accounts, monkeypatch):
    service, _, client, _ = accounts
    row = next(row for row in service.list("admin")["items"] if row["id"] == "doc")
    # 模拟曾经被登录缓存过的同 ID 账号，不得因停用而复活。
    monkeypatch.setitem(
        auth_store.users_db,
        "doc@example.com",
        {
            "id": "doc",
            "email": "doc@example.com",
            "username": "doc",
            "roles": ["admin"],
            "display_name": "旧缓存",
            "department": "内科",
            "password_hash": "unused",
        },
    )
    response = client.put(
        "/api/v1/account-management/doc", json=edit(row, is_active=False)
    )
    assert response.status_code == 200, response.text
    assert auth_store.find_user_by_account("doc") is None
    assert auth_store.resolve_user_by_subject("doc@example.com") is None
    assert (
        client.put("/api/v1/account-management/doc", json=edit(row)).status_code == 409
    )
    updated = response.json()["data"]
    assert (
        client.put(
            "/api/v1/account-management/doc",
            json=edit(updated, is_active=True, roles=["qc_staff"]),
        ).status_code
        == 200
    )
    assert auth_store.resolve_user_by_subject("doc@example.com")["roles"] == [
        "qc_staff"
    ]


@pytest.mark.parametrize(
    "changes", [{"is_active": False}, {"roles": ["doctor"]}, {"department": "外科"}]
)
def test_admin_cannot_lock_out_self(accounts, changes):
    service, _, client, _ = accounts
    row = next(row for row in service.list("admin")["items"] if row["id"] == "admin")
    assert (
        client.put(
            "/api/v1/account-management/admin", json=edit(row, **changes)
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"roles": ["super_admin"]},
        {"roles": []},
        {"password": "短口令"},
        {"password": "中" * 30},
        {"username": "unsafe@account"},
        {"institute_id": " "},
    ],
)
def test_invalid_contract_rejected_before_write(accounts, changes):
    _, _, client, _ = accounts
    assert (
        client.post("/api/v1/account-management", json=payload(**changes)).status_code
        == 422
    )


def test_case_insensitive_duplicate_and_unknown_fields(accounts):
    _, _, client, _ = accounts
    assert (
        client.post(
            "/api/v1/account-management", json=payload(username="ADMIN")
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/account-management", json=payload(email="ADMIN@example.com")
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/account-management", json=payload(is_active=True)
        ).status_code
        == 422
    )


def test_database_failure_never_falls_back_to_memory(accounts, monkeypatch):
    monkeypatch.setattr(
        auth_store,
        "_supports_persistent_auth",
        lambda session: (_ for _ in ()).throw(RuntimeError("DB unavailable")),
    )
    with pytest.raises(RuntimeError):
        auth_store.resolve_user_by_subject("admin@medqc.com")


def test_registration_and_self_profile_cannot_grant_scope(accounts):
    _, _, client, actor = accounts
    request = {
        key: value
        for key, value in payload(roles=["doctor"]).items()
        if key not in {"institute_id", "roles"}
    }
    assert (
        client.post(
            "/api/v1/auth/register", json=request | {"role": "admin"}
        ).status_code
        == 422
    )
    actor.update(id="doc", roles=["doctor"], department="内科")
    assert (
        client.put("/api/v1/auth/profile", json={"department": "外科"}).status_code
        == 403
    )


def test_other_product_roles_cannot_be_silently_overwritten(accounts):
    service, sessions, client, _ = accounts
    with sessions.begin() as session:
        session.get(SysUser, "doc").roles_json = '["doctor", "sync_admin"]'
    row = next(row for row in service.list("admin")["items"] if row["id"] == "doc")
    response = client.put(
        "/api/v1/account-management/doc", json=edit(row, roles=["doctor"])
    )
    assert response.status_code == 409 and "原权限系统" in response.text


def test_numeric_employee_account_and_password_spaces_preserved(accounts):
    _, sessions, client, _ = accounts
    secret = "  test-only-password!  "
    response = client.post(
        "/api/v1/account-management", json=payload(username="100001", password=secret)
    )
    assert response.status_code == 200, response.text
    with sessions() as session:
        row = session.get(SysUser, response.json()["data"]["id"])
        assert verify_password(secret, row.password_hash)
        assert not verify_password(secret.strip(), row.password_hash)


def test_validation_log_and_response_never_echo_initial_password(caplog):
    import asyncio
    from fastapi.exceptions import RequestValidationError
    from starlette.requests import Request
    from app.main import create_app

    secret = "test-only-password-that-must-not-be-logged"
    error = RequestValidationError(
        [
            {
                "loc": ("body", "password"),
                "type": "string_too_short",
                "msg": "String too short",
                "input": secret,
            }
        ]
    )
    request = Request(
        {"type": "http", "path": "/api/v1/account-management", "headers": []}
    )
    handler = create_app().exception_handlers[RequestValidationError]
    response = asyncio.run(handler(request, error))
    assert secret not in caplog.text
    assert secret.encode() not in response.body
