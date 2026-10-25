"""持久SQL账号的超级管理员适配，不信HTTP角色、不写业务库。"""

import pytest

from app.database.models.v36_reports import SysUser
from app.services.defect_rectification_service import _person
from app.services.report_institute_scope import authorized_institute
from app.services.doctor_notification_service import DoctorNotificationService
from test_account_management import accounts as accounts
from test_account_registration import registration as registration, application


def test_persistent_sync_admin_can_read_report_and_manage_other_institute(accounts):
    service, sessions, client, actor = accounts
    with sessions.begin() as session:
        row = session.get(SysUser, "doc")
        row.role = "sync_admin"
        row.roles_json = '["sync_admin"]'
    actor.update(id="doc", roles=["doctor"])
    with sessions() as session:
        assert authorized_institute(session, "doc") is None
        assert {"admin", "qc_manager", "super_admin"} <= _person(session, "doc")["roles"]
    result = client.get("/api/v1/account-management").json()
    assert result["success"]
    assert result["data"]["managed_institute_id"] is None
    assert {row["institute_id"] for row in result["data"]["items"]} == {"A", "B"}
    # 读取及授权展开不回写或覆盖专用角色。
    with sessions() as session:
        assert session.get(SysUser, "doc").roles_json == '["sync_admin"]'


@pytest.mark.parametrize("roles_json,active", [('broken', True), ('{}', True), ('[]', True), ('["sync_admin"]', False)])
def test_invalid_persistent_superuser_does_not_fall_back_to_http_admin(accounts, roles_json, active):
    _, sessions, client, actor = accounts
    with sessions.begin() as session:
        row = session.get(SysUser, "doc")
        row.role = "sync_admin"
        row.roles_json = roles_json
        row.is_active = active
    actor.update(id="doc", roles=["admin", "sync_admin"])
    assert client.get("/api/v1/account-management").status_code == 403


def test_sync_admin_receives_and_can_read_cross_institute_registration(registration):
    client, sessions, service, _, _ = registration
    with sessions.begin() as session:
        for row in session.query(SysUser).all():
            row.is_active = row.id == "admin"
        row = session.get(SysUser, "admin")
        row.role = "sync_admin"
        row.roles_json = '["sync_admin"]'
    response = client.post("/api/v1/auth/register", json=application(institute_id="B"))
    assert response.status_code == 200, response.text
    page = service.list("admin")
    assert page["total"] == 1
    row = page["items"][0]
    assert row["requested_institute_id"] == "B"
    assert service.detail("admin", row["user_id"])["user_id"] == row["user_id"]
    notifications = DoctorNotificationService(sessions)
    page = notifications.list("admin")
    assert page["total"] == 1
    assert page["items"][0]["institute_id"] == "B"
    notifications.mark_read("admin", page["items"][0]["id"])
    assert notifications.list("admin")["unread_count"] == 0
