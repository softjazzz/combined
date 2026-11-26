"""注册审批完整HTTP链；仅临时SQLite、持久账号与正常认证。"""

import json
from datetime import timezone

import pytest
import sqlalchemy as sa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.access_control import enforce_default_auth
from app.core.rate_limit import reset_rate_limit_store_for_testing
from app.core.security import create_access_token, get_password_hash
from app.database.models.account_registration import registration_tables
from app.database.models.v36_reports import SysUser, DefectRectification, QCAppeal
from app.routers import account_management, auth, notifications
from app.services import account_management_service, auth_store
from app.services.account_management_service import AccountManagementService
from app.services.account_registration_service import AccountRegistrationService
from app.services.doctor_notification_service import (
    DoctorNotificationService,
    Notification,
)


@pytest.fixture
def registration(monkeypatch):
    engine = sa.create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"qc": None}},
    )
    SysUser.__table__.create(engine)
    users = SysUser.__table__.to_metadata(sa.MetaData())
    requests, events = registration_tables(users)
    requests.create(engine)
    events.create(engine)
    Notification.__table__.create(engine)
    for model in (DefectRectification, QCAppeal):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    secret = "synthetic-registration-only!"
    with sessions.begin() as session:
        for id, role, institute in (
            ("admin", "admin", "A"),
            ("other", "admin", "B"),
            ("global", "admin", None),
            ("qc", "qc_manager", "A"),
        ):
            session.add(
                SysUser(
                    id=id,
                    username=id,
                    email=f"{id}@example.com",
                    display_name=id,
                    password_hash=get_password_hash(secret),
                    institute_id=institute,
                    department="信息科",
                    role=role,
                    roles_json=json.dumps([role]),
                    is_active=True,
                )
            )
    monkeypatch.setattr(auth_store, "SessionLocal", sessions)
    monkeypatch.setattr(auth_store, "users_db", {})
    monkeypatch.setattr(account_management_service, "SessionLocal", sessions)
    service = AccountRegistrationService(sessions)
    monkeypatch.setattr(account_management, "registration_service", service)
    monkeypatch.setattr(
        account_management, "service", AccountManagementService(sessions)
    )
    monkeypatch.setattr(notifications, "service", DoctorNotificationService(sessions))
    app = FastAPI(dependencies=[Depends(enforce_default_auth)])
    for router in (auth.router, account_management.router, notifications.router):
        app.include_router(router)
    client = TestClient(app)
    reset_rate_limit_store_for_testing()
    yield client, sessions, service, requests, events
    engine.dispose()


def application(**changes):
    return (
        dict(
            username="doctor_new",
            email="doctor-new@example.com",
            display_name="申请医生",
            institute_id="A",
            department="内科",
            password="synthetic-applicant-only!",
            role="doctor",
        )
        | changes
    )


def headers(user="admin"):
    return {
        "Authorization": "Bearer "
        + create_access_token({"sub": f"{user}@example.com", "roles": ["admin"]})
    }


def submit(client, **changes):
    response = client.post("/api/v1/auth/register", json=application(**changes))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def review(client, row, **changes):
    data = (
        dict(
            expected_version=row["version"],
            decision="approve",
            comment="核验通过，开通医生账号",
            institute_id="A",
            department="内科",
            roles=["doctor"],
        )
        | changes
    )
    return client.post(
        f"/api/v1/account-management/registrations/{row['user_id']}/review",
        headers=headers(),
        json=data,
    )


def status(client, **changes):
    return client.post(
        "/api/v1/auth/registration-status",
        json={
            "account": application()["username"],
            "password": application()["password"],
        }
        | changes,
    )


def seed_department_catalog(sessions, monkeypatch):
    from app.services import registration_departments

    monkeypatch.setattr(registration_departments, "clinical_read_schema", lambda: None)
    table = sa.Table(
        "discharge_record", sa.MetaData(),
        sa.Column("institute_id", sa.String), sa.Column("dept_name", sa.String),
        sa.Column("is_deleted", sa.String),
    )
    table.create(sessions.kw["bind"])
    with sessions.begin() as session:
        session.execute(table.insert(), [
            {"institute_id": "A", "dept_name": "内科", "is_deleted": "0"},
            {"institute_id": "A", "dept_name": " 内科 ", "is_deleted": "0"},
            {"institute_id": "B", "dept_name": "内科", "is_deleted": "0"},
            {"institute_id": "A", "dept_name": "已删除科室", "is_deleted": "1"},
            {"institute_id": "A", "dept_name": "-", "is_deleted": "0"},
            {"institute_id": "", "dept_name": "无机构科室", "is_deleted": "0"},
        ])


def test_public_department_catalog_and_no_email_registration_real_login(registration, monkeypatch):
    client, sessions, _, _, _ = registration
    seed_department_catalog(sessions, monkeypatch)
    response = client.get("/api/v1/auth/registration-departments")
    assert response.status_code == 200, response.text
    options = response.json()["data"]["items"]
    assert len(options) == 2
    assert {option["label"] for option in options} == {"内科（A）", "内科（B）"}
    assert all(set(option) == {"key", "name", "label"} for option in options)
    data = application()
    for field in ("email", "institute_id", "department"):
        data.pop(field)
    data["department_key"] = next(option["key"] for option in options if option["label"] == "内科（A）")
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 200, response.text
    row = response.json()["data"]
    assert row["requested_institute_id"] == "A"
    assert row["requested_department"] == "内科"
    assert client.post("/api/v1/auth/login", json={"account": data["username"], "password": data["password"]}).status_code == 401
    assert review(client, row).status_code == 200
    with sessions() as session:
        assert session.scalar(sa.select(SysUser.email).where(SysUser.id == row["user_id"])) is None
    login = client.post("/api/v1/auth/login", json={"account": data["username"], "password": data["password"]})
    assert login.status_code == 200, login.text
    tokens = login.json()["data"]
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert profile.status_code == 200 and profile.json()["data"]["id"] == row["user_id"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 200


def test_department_selection_rejects_stale_key_and_conflicting_institution(registration, monkeypatch):
    client, sessions, _, _, _ = registration
    seed_department_catalog(sessions, monkeypatch)
    data = {"username": "doctor_empty", "display_name": "合成申请", "password": "synthetic-applicant-only!", "department_key": "0" * 64}
    assert client.post("/api/v1/auth/register", json=data).status_code == 409
    assert client.post("/api/v1/auth/register", json=data | {"institute_id": "B"}).status_code == 422
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(SysUser).where(SysUser.username == data["username"])) == 0


def test_no_email_rejected_application_can_resubmit_without_identity_change(registration, monkeypatch):
    client, sessions, _, _, _ = registration
    seed_department_catalog(sessions, monkeypatch)
    options = client.get("/api/v1/auth/registration-departments").json()["data"]["items"]
    data = {"username": "doctor_without_email", "display_name": "合成申请", "password": "synthetic-applicant-only!", "department_key": options[0]["key"]}
    row = client.post("/api/v1/auth/register", json=data).json()["data"]
    assert review(client, row, decision="reject", institute_id=None, department=None, roles=None).status_code == 200
    retry = client.post("/api/v1/auth/register", json=data)
    assert retry.status_code == 200, retry.text
    assert retry.json()["data"]["user_id"] == row["user_id"]


def test_empty_department_catalog_reports_unavailable(registration, monkeypatch):
    from app.services import registration_departments

    client, _, _, _, _ = registration
    monkeypatch.setattr(registration_departments, "clinical_read_schema", lambda: None)
    response = client.get("/api/v1/auth/registration-departments")
    assert response.status_code == 503
    assert "尚无可用科室" in response.json()["detail"]


def test_register_pending_cannot_login_refresh_or_use_old_token(
    registration, monkeypatch
):
    client, sessions, _, _, _ = registration
    row = submit(client)
    assert (
        row["status"] == "pending"
        and "password" not in str(row)
        and "token" not in str(row)
    )
    with sessions() as session:
        user = session.get(SysUser, row["user_id"])
        assert (
            not user.is_active and user.institute_id is None and user.department is None
        )
    monkeypatch.setitem(
        auth_store.users_db,
        application()["email"],
        {"id": row["user_id"], **application(), "roles": ["admin"]},
    )
    token = create_access_token({"sub": application()["email"], "uid": row["user_id"]})
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "account": application()["username"],
                "password": application()["password"],
            },
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer " + token}
        ).status_code
        == 401
    )
    refresh = create_access_token({"sub": application()["email"], "type": "refresh"})
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": refresh}).status_code
        == 401
    )
    assert status(client).json()["data"]["status"] == "pending"
    assert status(client, password="wrong").status_code == 401


def test_admin_approval_login_and_unified_messages_exact_target(registration):
    client, _, _, _, _ = registration
    row = submit(client)
    for actor in ("admin", "global"):
        notice = client.get("/api/v1/notifications", headers=headers(actor)).json()[
            "data"
        ]
        assert notice["unread_count"] == 1
        assert notice["items"][0]["interaction_target"] == {
            "kind": "account_registration",
            "id": row["user_id"],
        }
    page = client.get(
        "/api/v1/account-management/registrations/list", headers=headers()
    ).json()["data"]
    assert page["total"] == 1
    assert "password_hash" not in str(page)
    approved = review(client, row, department="核定内科")
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"
    login = client.post(
        "/api/v1/auth/login",
        json={
            "account": application()["username"],
            "password": application()["password"],
        },
    )
    assert login.status_code == 200, login.text
    doctor = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/api/v1/auth/me", headers=doctor).json()["data"]["roles"] == [
        "doctor"
    ]
    assert (
        client.get(
            "/api/v1/account-management/registrations/list", headers=doctor
        ).status_code
        == 403
    )
    notices = client.get("/api/v1/notifications", headers=doctor).json()["data"]
    assert notices["unread_count"] == 1
    message = notices["items"][0]
    assert message["title"] == "账号已开通"
    assert message["interaction_target"] == {
        "kind": "account_registration_result",
        "id": row["user_id"],
    }
    assert (
        client.put(
            f"/api/v1/notifications/{message['id']}/read", headers=doctor
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/notifications", headers=doctor).json()["data"][
            "unread_count"
        ]
        == 0
    )
    own = client.get("/api/v1/auth/registration", headers=doctor).json()["data"]
    assert own["status"] == "approved" and own["is_active"]
    assert own["institute_id"] == "A" and own["department"] == "核定内科"
    assert own["roles"] == ["doctor"]
    assert status(client).json()["data"]["department"] == "核定内科"
    detail = client.get(
        f"/api/v1/account-management/registrations/{row['user_id']}", headers=headers()
    ).json()["data"]
    assert [event["action"] for event in detail["history"]] == ["submit", "approve"]


def test_reject_and_credential_checked_resubmit_keep_identity_history(registration):
    client, sessions, _, _, _ = registration
    row = submit(client)
    rejected = review(
        client,
        row,
        decision="reject",
        comment="机构信息需核实，请修正后重提",
        institute_id=None,
        department=None,
        roles=None,
    )
    assert rejected.status_code == 200, rejected.text
    assert (
        status(client).json()["data"]["review_comment"]
        == "机构信息需核实，请修正后重提"
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "account": application()["email"],
                "password": application()["password"],
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/register",
            json=application(password="other-synthetic-secret!"),
        ).status_code
        == 409
    )
    resubmitted = submit(client, department="外科")
    assert resubmitted["user_id"] == row["user_id"] and resubmitted["version"] == 3
    assert resubmitted["review_comment"] is None
    assert review(client, row).status_code == 409
    assert review(client, resubmitted).status_code == 200
    detail = client.get(
        f"/api/v1/account-management/registrations/{row['user_id']}", headers=headers()
    ).json()["data"]
    assert [event["action"] for event in detail["history"]] == [
        "submit",
        "reject",
        "submit",
        "approve",
    ]
    with sessions() as session:
        assert (
            session.query(SysUser)
            .filter(SysUser.email == application()["email"])
            .count()
            == 1
        )


def test_duplicate_pending_approved_and_identifier_aliases_rejected(registration):
    client, _, _, _, _ = registration
    row = submit(client)
    for changes in (
        {},
        {"username": "DOCTOR_NEW", "email": "different@example.com"},
        {"username": "different", "email": application()["email"].upper()},
    ):
        assert (
            client.post(
                "/api/v1/auth/register", json=application(**changes)
            ).status_code
            == 409
        )
    assert review(client, row).status_code == 200
    assert review(client, row).status_code == 409
    assert client.post("/api/v1/auth/register", json=application()).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"role": "admin"},
        {"role": "qc_staff"},
        {"is_active": True},
        {"roles": ["admin"]},
        {"password": "short"},
        {"password": "中" * 30},
        {"institute_id": " "},
        {"username": "bad@name"},
    ],
)
def test_public_request_cannot_self_enable_or_grant_role(registration, changes):
    client, _, _, _, _ = registration
    assert (
        client.post("/api/v1/auth/register", json=application(**changes)).status_code
        == 422
    )


def test_scope_and_forged_token_roles_do_not_grant_approval(registration):
    client, _, _, _, _ = registration
    row = submit(client)
    path = f"/api/v1/account-management/registrations/{row['user_id']}"
    assert client.get(path, headers=headers("other")).status_code == 403
    assert client.get(path, headers=headers("qc")).status_code == 403
    assert (
        client.get(
            "/api/v1/account-management/registrations/list", headers=headers("other")
        ).json()["data"]["total"]
        == 0
    )
    assert (
        client.get("/api/v1/notifications", headers=headers("other")).json()["data"][
            "total"
        ]
        == 0
    )
    assert review(client, row, institute_id="B").status_code == 403
    assert review(client, row, roles=[]).status_code == 422
    assert review(client, row, comment=" ").status_code == 422


def test_pending_account_cannot_be_enabled_via_management_or_raw_flag(registration):
    client, sessions, _, _, _ = registration
    row = submit(client)
    with sessions() as session:
        user = session.get(SysUser, row["user_id"])
        updated = user.updated_at.replace(tzinfo=timezone.utc).isoformat()
    payload = dict(
        display_name="申请医生",
        institute_id="A",
        department="内科",
        roles=["doctor"],
        is_active=True,
        expected_updated_at=updated,
    )
    assert (
        client.put(
            f"/api/v1/account-management/{row['user_id']}",
            headers=headers(),
            json=payload,
        ).status_code
        == 409
    )
    # 防御旧入口误改启用位：申请未通过仍不能登录或解析旧令牌。
    with sessions.begin() as session:
        session.get(SysUser, row["user_id"]).is_active = True
    assert auth_store.find_user_by_account(application()["email"]) is None
    assert auth_store.resolve_user_by_subject(row["user_id"]) is None


@pytest.mark.parametrize("phase", ["submit", "review"])
def test_notification_failure_rolls_back_account_decision_and_event(
    registration, phase
):
    client, sessions, service, requests, events = registration
    if phase == "review":
        row = submit(client)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic notification failure")

    service.notify = fail
    if phase == "submit":
        with pytest.raises(RuntimeError):
            service.submit(application())
        with sessions() as session:
            assert session.scalar(sa.select(sa.func.count()).select_from(requests)) == 0
            assert (
                session.query(SysUser)
                .filter(SysUser.username == application()["username"])
                .count()
                == 0
            )
    else:
        assert review(client, row).status_code == 503
        with sessions() as session:
            assert not session.get(SysUser, row["user_id"]).is_active
            assert session.scalar(sa.select(requests.c.status)) == "pending"
            assert session.scalar(sa.select(sa.func.count()).select_from(events)) == 1


def test_missing_admin_or_schema_fails_closed_without_memory_creation(registration):
    client, sessions, _, requests, _ = registration
    with sessions.begin() as session:
        for id in ("admin", "global"):
            session.get(SysUser, id).is_active = False
    assert client.post("/api/v1/auth/register", json=application()).status_code == 409
    requests.drop(sessions.kw["bind"])
    assert (
        client.post(
            "/api/v1/auth/register", json=application(institute_id="B")
        ).status_code
        == 503
    )
    assert application()["email"] not in auth_store.users_db


def test_status_is_not_a_business_login_and_is_rate_limited(registration):
    client, _, _, _, _ = registration
    submit(client)
    for _ in range(10):
        response = status(client)
        assert response.status_code == 200
        assert "token" not in str(response.json()) and "password" not in str(
            response.json()
        )
    assert status(client).status_code == 429
    assert client.get("/api/v1/notifications").status_code == 401


def test_recipients_include_super_admin_and_exclude_unapproved_admins(registration):
    from datetime import datetime

    client, sessions, _, requests, _ = registration
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with sessions.begin() as session:
        # 停用原有本机构与全局普通管理员，仅保留：
        # 1) 绑定到其他机构 HQ 的 super_admin（应接收全部机构注册通知）
        # 2) 本机构 A 但注册状态为 pending 的未核准管理员（必须被排除）
        for uid in ("admin", "global"):
            session.get(SysUser, uid).is_active = False
        session.add(
            SysUser(
                id="super_hq",
                username="super_hq",
                email="super_hq@example.com",
                display_name="总部超管",
                password_hash=get_password_hash("synthetic-registration-only!"),
                institute_id="HQ",
                department="信息科",
                role="super_admin",
                roles_json='["super_admin"]',
                is_active=True,
            )
        )
        session.add(
            SysUser(
                id="unapproved_admin",
                username="unapproved_admin",
                email="unapproved-admin@example.com",
                display_name="未审管理员",
                password_hash=get_password_hash("synthetic-registration-only!"),
                institute_id="A",
                department="信息科",
                role="admin",
                roles_json='["admin"]',
                is_active=True,
            )
        )
        session.execute(
            requests.insert().values(
                user_id="unapproved_admin",
                status="pending",
                requested_institute_id="A",
                requested_department="信息科",
                version=1,
                submitted_at=now,
                updated_at=now,
            )
        )

    row = submit(client)
    with sessions() as session:
        recipients = {
            n.recipient_id
            for n in session.query(Notification)
            .filter(Notification.related_id == row["user_id"])
            .all()
        }
    assert recipients == {"super_hq"}
    assert "unapproved_admin" not in recipients
    queue = client.get(
        "/api/v1/account-management/registrations/list", headers=headers("super_hq")
    ).json()["data"]
    assert row["user_id"] in {item["user_id"] for item in queue["items"]}

    # 若连 super_hq 也停用，仅剩未审管理员时必须拒绝提交（409）
    with sessions.begin() as session:
        session.get(SysUser, "super_hq").is_active = False
    assert (
        client.post(
            "/api/v1/auth/register",
            json=application(
                username="doctor_no_recipient", email="no-rec@example.com"
            ),
        ).status_code
        == 409
    )


def test_pending_registration_cannot_reset_password(registration):
    client, _, _, _, _ = registration
    row = submit(client)
    res = client.post(
        f"/api/v1/account-management/{row['user_id']}/reset-password",
        headers=headers("admin"),
        json={"password": "synthetic-new-password!"},
    )
    assert res.status_code == 409
