"""专属临时PG：51→52实际迁移、双owner保护、正常认证和并发审批。"""

import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
import sqlalchemy as sa
from alembic import command
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.access_control import enforce_default_auth
from app.core.security import get_password_hash
from app.database.models.v36_reports import SysUser
from app.routers import account_management, auth, notifications
from app.services import account_management_service, auth_store, user_scope_owner
from app.services.account_management_service import AccountManagementService
from app.services.account_registration_service import AccountRegistrationService
from app.services.doctor_notification_service import DoctorNotificationService
from scripts import bootstrap_pr8_empty_database as bootstrap
from test_report_alembic_upgrade import HELPER, seed_legacy, snapshot

pytest_plugins = ("test_report_migration_compatibility",)
REVISION = "20261025_000052"


@pytest.mark.parametrize("owner", ["sys", "public"])
def test_upgrade_registration_approval_real_login_and_other_owner_protected(
    raw_pg, monkeypatch, owner
):
    bootstrap.initialize(raw_pg.url.database)
    path = f"qc,{owner}," + ("sys," if owner == "public" else "") + "cdm,public,legacy"
    secret = secrets.token_urlsafe(24)
    with raw_pg.begin() as conn:
        seed_legacy(conn)
        public = SysUser.__table__.to_metadata(sa.MetaData(), schema="public")
        public.create(conn)
        target = SysUser.__table__.to_metadata(sa.MetaData(), schema=owner)
        conn.execute(
            target.insert().values(
                id="registration-admin",
                username="registration_admin",
                email="registration-admin@example.com",
                display_name="合成审批管理员",
                institute_id="A",
                department="信息科",
                password_hash=get_password_hash(secret),
                role="admin",
                roles_json='["admin"]',
                is_active=True,
            )
        )
        shadow_owner = "sys" if owner == "public" else "public"
        shadow = SysUser.__table__.to_metadata(sa.MetaData(), schema=shadow_owner)
        conn.execute(
            shadow.insert().values(
                id="shadow-account",
                username="registration_doctor",
                email="shadow@example.com",
                display_name="另一owner哨兵",
                institute_id="OTHER",
                department="其他科",
                role="sync_admin",
                roles_json='["sync_admin"]',
                is_active=True,
            )
        )
        before = snapshot(conn)
    with bootstrap.migration_environment(raw_pg.url) as config:
        monkeypatch.setenv("DB_SEARCH_PATH", path)
        command.upgrade(config, REVISION)
    with raw_pg.connect() as conn:
        migrated = snapshot(conn, before)
        assert {key: migrated[key] for key in before} == before
        assert set(migrated) - set(before) == {
            (owner, "sys_user_registrations"), (owner, "sys_user_registration_events")
        }
        assert (
            conn.exec_driver_sql(
                "SELECT version_num FROM public.alembic_version"
            ).scalar()
            == REVISION
        )
        inspector = sa.inspect(conn)
        for table in ("sys_user_registrations", "sys_user_registration_events"):
            assert inspector.has_table(table, schema=owner)
            assert not inspector.has_table(table, schema=shadow_owner)
            assert {
                fk["referred_schema"]
                for fk in HELPER["_foreign_keys"](inspector, table, owner)
            } == {owner}
    engine = sa.create_engine(
        raw_pg.url, connect_args={"options": f"-csearch_path={path}"}
    )
    sessions = sessionmaker(engine)
    monkeypatch.setattr(user_scope_owner, "DB_SEARCH_PATH", path)
    monkeypatch.setattr(auth_store, "SessionLocal", sessions)
    monkeypatch.setattr(auth_store, "users_db", {})
    monkeypatch.setattr(account_management_service, "SessionLocal", sessions)
    monkeypatch.setattr(
        account_management, "service", AccountManagementService(sessions)
    )
    monkeypatch.setattr(
        account_management, "registration_service", AccountRegistrationService(sessions)
    )
    monkeypatch.setattr(notifications, "service", DoctorNotificationService(sessions))
    app = FastAPI(dependencies=[Depends(enforce_default_auth)])
    for router in (auth.router, account_management.router, notifications.router):
        app.include_router(router)
    http = TestClient(app)

    def login(account):
        return http.post(
            "/api/v1/auth/login", json={"account": account, "password": secret}
        )

    admin = login("registration_admin")
    assert admin.status_code == 200, admin.text
    admin_headers = {"Authorization": "Bearer " + admin.json()["access_token"]}
    payload = dict(
        username="registration_doctor",
        email="registration-doctor@example.com",
        display_name="合成申请医生",
        institute_id="A",
        department="内科",
        password=secret,
    )
    response = http.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    registration = response.json()["data"]
    assert (
        registration["status"] == "pending"
        and login("registration_doctor").status_code == 401
    )
    notice = http.get("/api/v1/notifications", headers=admin_headers).json()["data"]
    assert (
        notice["total"] == 1
        and notice["items"][0]["interaction_target"]["id"] == registration["user_id"]
    )
    decision = dict(
        expected_version=1,
        decision="approve",
        comment="合成管理员核验资料通过",
        institute_id="A",
        department="内科",
        roles=["doctor"],
    )
    url = f"/api/v1/account-management/registrations/{registration['user_id']}/review"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(
                lambda _: http.post(url, headers=admin_headers, json=decision), range(2)
            )
        )
    assert sorted(response.status_code for response in outcomes) == [200, 409], [
        response.text for response in outcomes
    ]
    doctor = login("registration_doctor")
    assert doctor.status_code == 200, doctor.text
    doctor_headers = {"Authorization": "Bearer " + doctor.json()["access_token"]}
    notices = http.get("/api/v1/notifications", headers=doctor_headers).json()["data"]
    assert notices["total"] == notices["unread_count"] == 1
    assert notices["items"][0]["interaction_target"] == {
        "kind": "account_registration_result",
        "id": registration["user_id"],
    }
    assert (
        http.put(
            f"/api/v1/notifications/{notices['items'][0]['id']}/read",
            headers=doctor_headers,
        ).status_code
        == 200
    )
    assert (
        http.get("/api/v1/notifications", headers=doctor_headers).json()["data"][
            "unread_count"
        ]
        == 0
    )
    detail = http.get(
        f"/api/v1/account-management/registrations/{registration['user_id']}",
        headers=admin_headers,
    ).json()["data"]
    assert [event["action"] for event in detail["history"]] == ["submit", "approve"]
    with raw_pg.connect() as conn:
        preserved = {
            key: value
            for key, value in before.items()
            if key not in {(owner, "sys_users"), ("qc", "notifications")}
        }
        actual = snapshot(conn, before)
        assert {key: actual[key] for key in preserved} == preserved
        assert (
            conn.execute(
                sa.select(shadow.c.roles_json).where(shadow.c.id == "shadow-account")
            ).scalar()
            == '["sync_admin"]'
        )
        assert (
            conn.exec_driver_sql(
                f'SELECT count(*) FROM "{owner}".sys_user_registration_events'
            ).scalar()
            == 2
        )
    engine.dispose()
