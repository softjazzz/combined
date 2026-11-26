"""Batch1 整改待办与消息中心后端修复单测（P0 #1 / P1 #4a / P2 #8）。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database.models.account_registration import registration_tables
from app.database.models.v36_reports import DefectRectification as Task
from app.database.models.v36_reports import QCAppeal
from app.database.models.v36_reports import QCRecordReview as ReportReview
from app.database.models.v36_reports import SysUser
from app.routers import notifications as notifications_router
from app.routers import record_reviews as record_reviews_router
from app.services import custom_qc_workspace_service, report_case_scope
from app.services.account_registration_service import (
    SOURCE as REG_SOURCE,
    publish_registration_notification,
)
from app.services.defect_rectification_service import RectificationError
from app.services.doctor_notification_service import (
    DoctorNotificationService,
    Notification,
    SOURCE as FEEDBACK_SOURCE,
    sanitize_legacy_notification_text,
)
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.record_review_workflow_service import (
    RecordReviewWorkflowService,
    _candidate_sources,
)


def _create_batch_jobs_table(engine):
    md = MetaData()
    table = Table(
        "qc_batch_jobs",
        md,
        Column("id", String(64), primary_key=True),
        Column("scene", String(32)),
        Column("scope", String(32)),
        Column("filters_json", Text),
    )
    md.create_all(engine)
    return table


# =============================================================================
# P0 #1: 病历审核候选加载对单病历历史保存结果缺失/无效容错，未分类错误仍 503
# =============================================================================


def test_candidate_sources_skips_known_historical_artifact_errors_and_keeps_ready_records(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    try:
        ReportReview.__table__.create(engine)
        jobs_table = _create_batch_jobs_table(engine)
        sessions = sessionmaker(engine)
        with sessions.begin() as session:
            session.execute(
                jobs_table.insert().values(
                    id="job-ready-1",
                    scene="final",
                    scope="final",
                    filters_json=json.dumps({"query_scope": "final"}),
                )
            )
            session.execute(
                jobs_table.insert().values(
                    id="job-ready-2",
                    scene="running",
                    scope="running",
                    filters_json=json.dumps({"query_scope": "running"}),
                )
            )

        records = [
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "department": "内科",
            },
            {
                "institute_id": "H1",
                "patient_id": "P2",
                "visit_id": "V2",
                "department": "外科",
            },
            {
                "institute_id": "H1",
                "patient_id": "P3",
                "visit_id": "V3",
                "department": "骨科",
            },
            {
                "institute_id": "H1",
                "patient_id": "P4",
                "visit_id": "V4",
                "department": "儿科",
            },
            {
                "institute_id": "H1",
                "patient_id": "P5",
                "visit_id": "V5",
                "department": "心内科",
            },
            {
                "institute_id": "H1",
                "patient_id": "P6",
                "visit_id": "V6",
                "department": "呼吸科",
            },
        ]
        summaries = {
            ("H1", "P1", "V1"): {
                "status": "ready",
                "root_job_id": "job-ready-1",
                "envelope_id": "env-1",
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": "1",
            },
            ("H1", "P2", "V2"): {
                "status": "ready",
                "root_job_id": "job-ready-2",
                "envelope_id": "env-2",
                "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                "rule_set_version": "1",
            },
            ("H1", "P3", "V3"): {
                "status": "technical_error",
                "reason_code": "canonical_envelope_missing",
            },
            ("H1", "P4", "V4"): {
                "status": "technical_error",
                "reason_code": "canonical_result_envelope_invalid",
            },
            ("H1", "P5", "V5"): {
                "status": "technical_error",
                "reason_code": "generation_conflict",
            },
            ("H1", "P6", "V6"): {"status": "not_run"},
        }

        monkeypatch.setattr(
            report_case_scope,
            "load_current_workstation_records",
            lambda **kwargs: records,
        )
        monkeypatch.setattr(
            custom_qc_workspace_service,
            "CustomQCWorkspaceService",
            lambda **kwargs: SimpleNamespace(
                build_luxian_0609_completed_record_result_summaries=lambda **kw: summaries
            ),
        )
        monkeypatch.setattr(
            custom_qc_workspace_service,
            "_batch_jobs_table",
            lambda readonly=True: jobs_table,
        )

        actor = {
            "id": "admin-h1",
            "name": "管理员",
            "roles": {"admin", "qc_manager"},
            "institute_id": "H1",
            "department": "信息科",
        }
        with sessions() as session:
            sources = _candidate_sources(session, actor)

        assert {(row["visit_id"], row["scene"], row["case_department"]) for row in sources} == {
            ("V1", "final", "内科"),
            ("V2", "running", "外科"),
        }

        service = RecordReviewWorkflowService(
            sessions=sessions,
            person_loader=lambda session, actor_id: deepcopy(actor),
        )
        app = FastAPI()
        app.include_router(record_reviews_router.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-h1",
            "role": "admin",
        }
        monkeypatch.setattr(record_reviews_router, "service", service)
        with TestClient(app) as client:
            resp_open = client.get("/api/v1/record-reviews", params={"state": "open"})
            assert resp_open.status_code == 200, resp_open.text
            open_data = resp_open.json()
            assert open_data["total"] == 2
            assert open_data["pending_count"] == 2
            assert open_data["initial_count"] == 2
            assert open_data["recheck_count"] == 0

            resp_hist = client.get("/api/v1/record-reviews", params={"state": "history"})
            assert resp_hist.status_code == 200, resp_hist.text
            hist_data = resp_hist.json()
            assert hist_data["total"] == 0
            assert hist_data["pending_count"] == 2
    finally:
        engine.dispose()


def test_candidate_sources_returns_empty_when_all_records_not_run_or_skippable(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_engine("sqlite:///:memory:")
    try:
        sessions = sessionmaker(engine)
        records = [
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "department": "内科",
            }
        ]
        monkeypatch.setattr(
            report_case_scope,
            "load_current_workstation_records",
            lambda **kwargs: records,
        )
        monkeypatch.setattr(
            custom_qc_workspace_service,
            "CustomQCWorkspaceService",
            lambda **kwargs: SimpleNamespace(
                build_luxian_0609_completed_record_result_summaries=lambda **kw: {
                    ("H1", "P1", "V1"): {
                        "status": "technical_error",
                        "reason_code": "canonical_envelope_missing",
                    }
                }
            ),
        )
        actor = {"id": "admin-h1", "roles": {"admin"}, "institute_id": "H1"}
        with sessions() as session:
            assert _candidate_sources(session, actor) == []
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "bad_summary",
    [
        {"status": "technical_error"},
        {"status": "technical_error", "reason_code": "database_timeout"},
        {"status": "unexpected_failure"},
    ],
)
def test_candidate_sources_still_fails_closed_503_on_unknown_technical_error(
    monkeypatch: pytest.MonkeyPatch, bad_summary: dict
):
    engine = create_engine("sqlite:///:memory:")
    try:
        sessions = sessionmaker(engine)
        records = [
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "V1",
                "department": "内科",
            }
        ]
        monkeypatch.setattr(
            report_case_scope,
            "load_current_workstation_records",
            lambda **kwargs: records,
        )
        monkeypatch.setattr(
            custom_qc_workspace_service,
            "CustomQCWorkspaceService",
            lambda **kwargs: SimpleNamespace(
                build_luxian_0609_completed_record_result_summaries=lambda **kw: {
                    ("H1", "P1", "V1"): bad_summary
                }
            ),
        )
        actor = {"id": "admin-h1", "roles": {"admin"}, "institute_id": "H1"}
        with sessions() as session, pytest.raises(RectificationError) as exc:
            _candidate_sources(session, actor)
        assert exc.value.status == 503
    finally:
        engine.dispose()


# =============================================================================
# P1 #4a + P2 #8: 账号注册归类/筛选对齐 + 历史 analysis/UUID 读取投影清洗
# =============================================================================


@pytest.fixture
def notification_setup():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    for model in (SysUser, Task, QCAppeal, Notification):
        model.__table__.create(engine)
    users_copy = SysUser.__table__.to_metadata(MetaData())
    registrations, _ = registration_tables(users_copy)
    registrations.create(engine)
    sessions = sessionmaker(engine)
    now = datetime.utcnow()

    people = {
        "admin": {
            "id": "admin",
            "name": "院区管理员",
            "roles": {"admin", "qc_manager"},
            "institute_id": "H1",
            "department": "信息科",
        },
        "applicant": {
            "id": "applicant",
            "name": "新申请医生",
            "roles": {"doctor"},
            "institute_id": "H1",
            "department": "内科",
        },
    }

    with sessions.begin() as session:
        for person in people.values():
            roles = sorted(person["roles"])
            session.add(
                SysUser(
                    id=person["id"],
                    username=person["id"],
                    display_name=person["name"],
                    institute_id=person["institute_id"],
                    department=person["department"],
                    role=roles[0],
                    roles_json=json.dumps(roles),
                    is_active=True,
                )
            )
        session.execute(
            registrations.insert().values(
                user_id="applicant",
                status="pending",
                requested_institute_id="H1",
                requested_department="内科",
                version=1,
                review_comment=None,
                submitted_at=now,
                updated_at=now,
            )
        )
        # 1) 账号注册待审批通知（库内原始 type='system', source_key='v5_account_registration'）
        publish_registration_notification(
            session,
            row={
                "user_id": "applicant",
                "status": "pending",
                "requested_institute_id": "H1",
                "version": 1,
                "review_comment": None,
            },
            event_id="evt-reg-1",
            sender_id="applicant",
            recipients=["admin"],
            pending=True,
        )
        # 2) 账号开通结果通知（申请人视角）
        publish_registration_notification(
            session,
            row={
                "user_id": "applicant",
                "status": "approved",
                "requested_institute_id": "H1",
                "version": 2,
                "review_comment": "已开通",
            },
            event_id="evt-reg-2",
            sender_id="admin",
            recipients=["applicant"],
            pending=False,
        )
        # 3) 真正的系统通知（related_type=None 与 related_type='qc_result'）
        session.add_all(
            [
                Notification(
                    id="sys-real-1",
                    type="system",
                    title="系统通知",
                    content="本月质控评分规则已更新",
                    recipient_id="admin",
                    related_type=None,
                    source_key=None,
                    is_read=False,
                    created_at=now - timedelta(minutes=1),
                ),
                Notification(
                    id="sys-qc-1",
                    type="system",
                    title="质控发现新缺陷",
                    content="病历 2248248 质控完成，发现 2 条缺陷",
                    recipient_id="admin",
                    related_type="qc_result",
                    source_key=None,
                    is_read=False,
                    created_at=now - timedelta(minutes=2),
                ),
                # 4) 历史脏文案：analysis + 36位 UUID
                Notification(
                    id="legacy-analysis-uuid",
                    type="analysis_qc",
                    title="analysis发现问题",
                    content="病历 8deec54a-744d-4f1e-95bc-71c685520fd8 analysis完成，当前有 1 条待处理问题。",
                    record_id="8deec54a-744d-4f1e-95bc-71c685520fd8",
                    recipient_id="admin",
                    related_type="qc_result",
                    source_key=None,
                    is_read=False,
                    created_at=now - timedelta(minutes=3),
                ),
                # 5) 历史脏文案：带有效 visit_id
                Notification(
                    id="legacy-analysis-with-visit",
                    type="analysis_qc",
                    title="analysis发现问题",
                    content="病历 8deec54a-744d-4f1e-95bc-71c685520fd8 analysis完成，本次发现 2 条问题。",
                    record_id="8deec54a-744d-4f1e-95bc-71c685520fd8",
                    visit_id="2298532",
                    recipient_id="admin",
                    related_type="qc_result",
                    source_key=None,
                    is_read=False,
                    created_at=now - timedelta(minutes=4),
                ),
                # 6) 历史别名类型（remediation_assigned / appeal_created / task_assigned / defect_urge）
                Notification(
                    id="legacy-rem-1",
                    type="remediation_assigned",
                    title="整改任务分配",
                    content="骨科病历整改任务已创建",
                    recipient_id="admin",
                    source_key=None,
                    is_read=False,
                    created_at=now - timedelta(minutes=5),
                ),
                Notification(
                    id="legacy-app-1",
                    type="appeal_created",
                    title="新申诉提交",
                    content="临床科室提交了缺陷申诉",
                    recipient_id="admin",
                    source_key=None,
                    is_read=False,
                    created_at=now - timedelta(minutes=6),
                ),
                Notification(
                    id="legacy-task-1",
                    type="task_assigned",
                    title="质控任务分配",
                    content="1月终末质控任务已分配",
                    recipient_id="admin",
                    source_key=None,
                    is_read=False,
                    created_at=now - timedelta(minutes=7),
                ),
                Notification(
                    id="legacy-urge-1",
                    type="defect_urge",
                    title="缺陷催办",
                    content="心内科病历质控缺陷待整改",
                    recipient_id="admin",
                    source_key=None,
                    is_read=False,
                    created_at=now - timedelta(minutes=8),
                ),
            ]
        )

    service = DoctorNotificationService(
        session_factory=sessions,
        person_loader=lambda session, actor_id: deepcopy(people[actor_id]),
    )
    yield service, sessions
    engine.dispose()


def test_account_registration_type_filter_and_serialized_type(
    notification_setup, monkeypatch: pytest.MonkeyPatch
):
    service, _ = notification_setup

    # 1. 管理员按 type=account_registration 筛选可精准命中待审批单，且序列化 type 为 account_registration
    reg_page = service.list("admin", type="account_registration")
    assert reg_page["total"] == 1
    assert len(reg_page["items"]) == 1
    reg_item = reg_page["items"][0]
    assert reg_item["type"] == "account_registration"
    assert reg_item["title"] == "账号注册待审批"
    assert reg_item["source_key"] == REG_SOURCE
    assert reg_item["interaction_target"] == {
        "kind": "account_registration",
        "id": "applicant",
    }

    # 2. 申请人按 type=account_registration 筛选同样命中审批结果通知
    applicant_reg = service.list("applicant", type="account_registration")
    assert applicant_reg["total"] == 1
    assert applicant_reg["items"][0]["type"] == "account_registration"
    assert applicant_reg["items"][0]["interaction_target"] == {
        "kind": "account_registration_result",
        "id": "applicant",
    }

    # 3. 按 type=system 筛选仅命中真正的系统通知，不再把账号注册待审批混入「系统通知」
    sys_page = service.list("admin", type="system")
    assert {item["id"] for item in sys_page["items"]} == {"sys-real-1", "sys-qc-1"}
    assert all(item["type"] == "system" for item in sys_page["items"])

    # 4. 其余历史别名业务类型筛选与规范化口径一致
    rem_page = service.list("admin", type="remediation")
    assert [item["id"] for item in rem_page["items"]] == ["legacy-rem-1"]
    assert rem_page["items"][0]["type"] == "remediation"

    app_page = service.list("admin", type="appeal_result")
    assert [item["id"] for item in app_page["items"]] == ["legacy-app-1"]
    assert app_page["items"][0]["type"] == "appeal_result"

    task_page = service.list("admin", type="task_assign")
    assert [item["id"] for item in task_page["items"]] == ["legacy-task-1"]
    assert task_page["items"][0]["type"] == "task_assign"

    urge_page = service.list("admin", type="defect_urge")
    assert [item["id"] for item in urge_page["items"]] == ["legacy-urge-1"]
    assert urge_page["items"][0]["type"] == "defect_urge"

    # 5. API 路由 GET /api/v1/notifications?type=account_registration 返回一致
    app = FastAPI()
    app.include_router(notifications_router.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "admin", "role": "admin"}
    monkeypatch.setattr(notifications_router, "service", service)
    with TestClient(app) as client:
        resp = client.get(
            "/api/v1/notifications", params={"type": "account_registration"}
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["total"] == 1
        assert data["items"][0]["type"] == "account_registration"
        assert data["items"][0]["title"] == "账号注册待审批"


def test_legacy_analysis_and_uuid_sanitized_in_read_projection_only(notification_setup):
    service, sessions = notification_setup

    all_items = {item["id"]: item for item in service.list("admin")["items"]}
    item_no_visit = all_items["legacy-analysis-uuid"]
    assert item_no_visit["title"] == "病历分析发现问题"
    assert item_no_visit["content"] == "该病历分析完成，当前有 1 条待处理问题。"
    assert "analysis" not in item_no_visit["title"].lower()
    assert "analysis" not in item_no_visit["content"].lower()
    assert "8deec54a-744d-4f1e-95bc-71c685520fd8" not in item_no_visit["content"]

    item_with_visit = all_items["legacy-analysis-with-visit"]
    assert item_with_visit["title"] == "病历分析发现问题"
    assert item_with_visit["content"] == "病历 2298532 分析完成，本次发现 2 条问题。"

    # overview_rows 同样走读取投影清洗
    now = datetime.utcnow()
    overview = {
        item["id"]: item
        for item in service.overview_rows(
            "admin", now - timedelta(hours=1), now + timedelta(hours=1)
        )
    }
    assert overview["legacy-analysis-uuid"]["title"] == "病历分析发现问题"
    assert overview["legacy-analysis-uuid"]["content"] == "该病历分析完成，当前有 1 条待处理问题。"

    # 验证数据库原记录未被改写
    with sessions() as session:
        raw = session.scalar(
            select(Notification).where(Notification.id == "legacy-analysis-uuid")
        )
        assert raw.title == "analysis发现问题"
        assert "8deec54a-744d-4f1e-95bc-71c685520fd8" in raw.content
        assert "analysis完成" in raw.content


def test_sanitize_legacy_notification_text_edge_cases():
    assert (
        sanitize_legacy_notification_text(
            "analysis发现问题 · 病历 8deec54a-744d-4f1e-95bc-71c685520fd8 analysis完成，当前有 1 条待处理问题"
        )
        == "病历分析发现问题 · 该病历分析完成，当前有 1 条待处理问题"
    )
    assert (
        sanitize_legacy_notification_text("病历 test-1 analysis完成，当前有 4 条待处理问题。")
        == "病历 test-1 病历分析完成，当前有 4 条待处理问题。"
    )
    assert (
        sanitize_legacy_notification_text("病历 2321104 编码质控完成，当前有 7 条待处理问题。")
        == "病历 2321104 编码质控完成，当前有 7 条待处理问题。"
    )
    assert sanitize_legacy_notification_text(None) is None
    assert sanitize_legacy_notification_text("") == ""
