"""专属合成PG：真实账号维护、正常登录及双向消息，不访问现有库。"""

import json
import secrets

import sqlalchemy as sa
from app.core.security import get_password_hash
from app.database.models.v36_reports import SysUser
from app.routers import account_management, modern_appeals
from app.services.account_management_service import AccountManagementService
from app.services.modern_appeal_service import ModernAppealService
from test_report_alembic_upgrade import snapshot
from test_v5_feedback_pg import IDENTITY

pytest_plugins = ("test_v5_feedback_pg",)


def test_real_account_to_doctor_qc_messages_and_disable(
    feedback, monkeypatch, record_property
):
    engine, sessions, _, _, http, actor, job, scene = feedback
    password = secrets.token_urlsafe(24)
    with engine.begin() as conn:
        # bootstrap 的50→51旧库保留历史NOT NULL；现代申诉验收前置是既有84结构。
        # 仅在新建专属合成库显式准备其可空旧主键合同，不改迁移或产品运行时DDL。
        assert conn.exec_driver_sql("SELECT count(*) FROM qc.qc_appeals").scalar() == 0
        conn.exec_driver_sql(
            "ALTER TABLE qc.qc_appeals ALTER COLUMN qc_result_id DROP NOT NULL"
        )
        conn.exec_driver_sql(
            "ALTER TABLE qc.qc_appeals ALTER COLUMN record_id DROP NOT NULL"
        )
        users = SysUser.__table__.to_metadata(sa.MetaData(), schema="sys")
        conn.execute(
            users.insert().values(
                id="account-admin",
                username="account_admin",
                email="account-admin@example.com",
                display_name="合成管理员",
                role="admin",
                roles_json='["admin"]',
                institute_id=IDENTITY["institute_id"],
                department="信息科",
                is_active=True,
                password_hash=get_password_hash(password),
            )
        )
        # 同名旧owner不能被读取或覆盖；正式身份必须始终来自sys。
        shadow = SysUser.__table__.to_metadata(sa.MetaData(), schema="public")
        shadow.create(conn)
        conn.execute(
            shadow.insert().values(
                id="shadow",
                username="two_way_doctor",
                email="shadow@example.com",
                display_name="旧owner哨兵",
                role="admin",
                institute_id="SYN-OTHER",
                department="外科",
                is_active=True,
            )
        )
        before = snapshot(conn)
    monkeypatch.setattr(
        account_management, "service", AccountManagementService(sessions)
    )
    monkeypatch.setattr(modern_appeals, "service", ModernAppealService(sessions))
    http.app.include_router(account_management.router)
    http.app.include_router(modern_appeals.router)

    def login(account, secret):
        response = http.post(
            "/api/v1/auth/login", json={"account": account, "password": secret}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": "Bearer " + response.json()["access_token"]}

    admin_headers = login("account_admin", password)
    url = "/api/v1/account-management"
    actor("qc")
    assert http.get(url).status_code == 403
    created = http.post(
        url,
        headers=admin_headers,
        json={
            "username": "two_way_doctor",
            "email": "two-way-doctor@example.com",
            "password": password,
            "display_name": "合成双向医生",
            "institute_id": IDENTITY["institute_id"],
            "department": "合成内科",
            "roles": ["doctor"],
        },
    )
    assert created.status_code == 200, created.text
    account = created.json()["data"]
    doctor_headers = login("two_way_doctor", password)
    me = http.get("/api/v1/auth/me", headers=doctor_headers).json()["data"]
    assert me["id"] == account["id"] and me["roles"] == ["doctor"]
    assert http.get(url, headers=doctor_headers).status_code == 403
    assert (
        http.put(
            "/api/v1/auth/profile", headers=doctor_headers, json={"department": "外科"}
        ).status_code
        == 403
    )
    actor("qc")
    target = http.get(
        "/api/v1/defect-rectifications/candidates",
        params={**IDENTITY, "expected_job_id": job["id"]},
    ).json()["data"]["targets"][0]
    target.pop("label")
    created = http.post(
        "/api/v1/defect-rectifications",
        json={
            **IDENTITY,
            **target,
            "assignee_id": account["id"],
            "requirement": "合成双向消息验收请核对文书",
        },
    )
    assert created.status_code == 200, created.text
    task = created.json()["data"]
    task_url = "/api/v1/defect-rectifications/" + task["id"]
    for user, version, action in (
        ("doctor", 1, "submit"),
        ("qc", 2, "reject"),
        ("doctor", 3, "submit"),
        ("qc", 4, "approve"),
    ):
        kwargs = {"headers": doctor_headers} if user == "doctor" else {}
        actor("qc")
        result = http.post(
            task_url + "/actions",
            json={
                "version": version,
                "action": action,
                "comment": "合成双向闭环操作意见不少于十字",
            },
            **kwargs,
        )
        assert result.status_code == 200, result.text
    actor("qc")
    notices = http.get("/api/v1/notifications").json()["data"]
    assert notices["total"] == notices["unread_count"] == 2
    assert all(
        row["interaction_target"] == {"kind": "rectification", "id": task["id"]}
        for row in notices["items"]
    )
    for notice in notices["items"]:
        assert http.put(f"/api/v1/notifications/{notice['id']}/read").status_code == 200
    assert http.get("/api/v1/notifications").json()["data"]["unread_count"] == 0
    assert http.get(task_url).json()["data"]["status"] == "approved"
    for action in ("withdraw", "approve"):
        response = http.post(
            "/api/v1/modern-appeals",
            headers=doctor_headers,
            json={"rectification_id": task["id"], "reason": "合成申诉原因不少于十个字"},
        )
        assert response.status_code == 200, response.text
        appeal_id = response.json()["id"]
        response = http.post(
            f"/api/v1/modern-appeals/{appeal_id}/actions",
            json={
                "expected_status": "pending",
                "action": action,
                "comment": "合成审核撤回说明不少于十个字",
            },
            **({"headers": doctor_headers} if action == "withdraw" else {}),
        )
        assert response.status_code == 200, response.text
    messages = http.get("/api/v1/notifications").json()["data"]
    assert messages["total"] == 5 and messages["unread_count"] == 3
    assert {row["title"] for row in messages["items"]} == {
        "医生提交了整改",
        "医生提交了申诉",
        "医生撤回了申诉",
    }
    for notice in messages["items"]:
        kind = notice["interaction_target"]["kind"]
        endpoint = (
            "modern-appeals" if kind == "modern_appeal" else "defect-rectifications"
        )
        assert (
            http.get(
                f"/api/v1/{endpoint}/{notice['interaction_target']['id']}"
            ).status_code
            == 200
        )
    actor("other")
    assert http.get("/api/v1/notifications").json()["data"]["total"] == 0
    assert (
        http.put(f"/api/v1/notifications/{messages['items'][0]['id']}/read").status_code
        == 404
    )
    doctor_messages = http.get("/api/v1/notifications", headers=doctor_headers).json()[
        "data"
    ]
    assert doctor_messages["total"] == 4
    # 登录会更新账号时间戳；管理员先刷新，再按当前版本维护。
    account = next(
        row
        for row in http.get(
            url, headers=admin_headers, params={"keyword": "two_way_doctor"}
        ).json()["data"]["items"]
        if row["id"] == account["id"]
    )
    body = {
        key: account[key]
        for key in ("display_name", "institute_id", "department", "roles")
    }
    response = http.put(
        url + "/" + account["id"],
        headers=admin_headers,
        json=body | {"is_active": False, "expected_updated_at": account["updated_at"]},
    )
    assert response.status_code == 200, response.text
    assert http.get("/api/v1/auth/me", headers=doctor_headers).status_code == 401
    assert http.get("/api/v1/notifications", headers=doctor_headers).status_code == 401
    stale = http.put(
        url + "/" + account["id"],
        headers=admin_headers,
        json=body | {"is_active": True, "expected_updated_at": account["updated_at"]},
    )
    assert stale.status_code == 409
    allowed = {
        ("sys", "sys_users"),
        ("qc", "qc_defect_rectifications"),
        ("qc", "qc_defect_rectification_events"),
        ("qc", "notifications"),
        ("qc", "qc_appeals"),
        ("qc", "qc_appeal_reviews"),
    }
    with engine.connect() as conn:
        after = snapshot(conn)
    assert before.keys() == after.keys()
    for key, old in before.items():
        for field in ("columns", "indexes", "constraints"):
            assert after[key][field] == old[field], (key, field)
        if key not in allowed:
            assert after[key] == old, key
    record_property(
        "two_way_evidence",
        json.dumps(
            {
                "scene": scene,
                "qc_messages": 5,
                "doctor_messages": 4,
                "disabled_token": 401,
                "protected_tables": len(before) - len(allowed),
            }
        ),
    )
