"""Batch A P0 回归测试：单库动态 schema、绑定院区 admin 隔离、debug/review 鉴权、演示账号裁剪。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import connection as db_connection
from app.database.models.v36_reports import (
    DefectRectification,
    DefectRectificationEvent,
    QCAppeal,
    QCAppealReview,
    QCRecordReview,
    QCTask,
    QCTaskQCRun,
    QCTaskRecord,
    SysUser,
)
from app.routers import appeals as appeals_router
from app.routers import manual_defect_reviews as manual_defect_reviews_router
from app.routers import notifications as notifications_router
from app.routers import qc_sichuan
from app.routers import remediation as remediation_router
from app.services import case_communication_service
from app.services import defect_rectification_service
from app.services import doctor_notification_service
from app.services import modern_appeal_service
from app.services import qc_result_ready_notification
from app.services import record_review_workflow_service
from app.services import report_institute_scope
from app.services import saved_result_access
from app.services import task_manual_defect_service
from app.services.defect_rectification_service import (
    DefectRectificationService,
    RectificationError,
)
from app.services.modern_appeal_service import ModernAppealService
from app.services.record_review_workflow_service import (
    RecordReviewWorkflowService,
    _ManualSnapshotReadSession,
)


def _request():
    return SimpleNamespace(state=SimpleNamespace(trace_id="trace-batch-a"))


# =============================================================================
# 1. 动态 schema 解析（DB_SCHEMA_MODE=single / split / SQLite）
# =============================================================================


def test_single_schema_mode_models_have_no_hardcoded_qc_schema():
    """子进程模拟 legacy_pg（DB_SCHEMA_MODE=single）导入模型，验证全部为 None schema 且无 qc. 外键前缀。"""
    backend_dir = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DB_SCHEMA_MODE": "single",
        "DB_SEARCH_PATH": "",
        "DATABASE_URL": "sqlite:///:memory:",
    }
    script = (
        "from app.database.models import v36_reports, case_communication\n"
        "from app.services import doctor_notification_service, modern_appeal_service, record_review_workflow_service\n"
        "assert v36_reports.DefectRectification.__table__.schema is None\n"
        "assert v36_reports.DefectRectificationEvent.__table__.schema is None\n"
        "fks = [fk.target_fullname for fk in v36_reports.DefectRectificationEvent.__table__.foreign_keys]\n"
        "assert all(not fk.startswith('qc.') for fk in fks), fks\n"
        "assert case_communication.CaseCommunication.__table__.schema is None\n"
        "comm_fks = [fk.target_fullname for fk in case_communication.CaseCommunication.__table__.foreign_keys]\n"
        "assert comm_fks == ['qc_case_communications.id'], comm_fks\n"
        "assert doctor_notification_service.Notification.__table__.schema is None\n"
        "assert modern_appeal_service.QCAppeal.__table__.schema is None\n"
        "assert modern_appeal_service.QCAppealReview.__table__.schema is None\n"
        "assert record_review_workflow_service.QCRecordReview.__table__.schema is None\n"
        "print('SINGLE_SCHEMA_OK')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(backend_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"stdout={proc.stdout}\nstderr={proc.stderr}"
    assert "SINGLE_SCHEMA_OK" in proc.stdout


def test_runtime_qc_schema_helpers_follow_db_schema_mode(monkeypatch: pytest.MonkeyPatch):
    pg_conn = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    sqlite_conn = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "single")
    assert qc_result_ready_notification._qc_schema(pg_conn) is None
    assert qc_result_ready_notification._qc_schema(sqlite_conn) is None
    assert doctor_notification_service._qc_schema(pg_conn) is None
    assert doctor_notification_service._qc_schema(sqlite_conn) is None
    assert modern_appeal_service._qc_schema() is None
    assert record_review_workflow_service._qc_schema() is None

    pg_session = Mock()
    pg_session.get_bind.return_value.dialect.name = "postgresql"
    assert _ManualSnapshotReadSession(pg_session).options == {}

    monkeypatch.setattr(db_connection, "DB_SCHEMA_MODE", "split")
    assert qc_result_ready_notification._qc_schema(pg_conn) == "qc"
    assert qc_result_ready_notification._qc_schema(sqlite_conn) is None
    assert doctor_notification_service._qc_schema(pg_conn) == "qc"
    assert doctor_notification_service._qc_schema(sqlite_conn) is None
    assert modern_appeal_service._qc_schema() == "qc"
    assert record_review_workflow_service._qc_schema() == "qc"
    assert _ManualSnapshotReadSession(pg_session).options == {
        "schema_translate_map": {None: "qc"}
    }


# =============================================================================
# 2. 9 处绑定院区 admin 跨院区 IDOR 隔离 + super_admin 角色补齐
# =============================================================================


def _seed_sys_users(session):
    users = [
        ("admin-h1", "admin", ["admin"], "H1", "管理科"),
        ("admin-global", "admin", ["admin"], None, "管理科"),
        ("super-h1", "super_admin", ["super_admin"], "H1", "管理科"),
        ("super-global", "super_admin", ["super_admin"], None, "管理科"),
        ("sync-h1", "sync_admin", ["sync_admin"], "H1", "运维科"),
        ("mgr-h1", "qc_manager", ["qc_manager"], "H1", "质控科"),
        ("doc-h1", "doctor", ["doctor"], "H1", "内科"),
        ("doc-h2", "doctor", ["doctor"], "H2", "内科"),
    ]
    for uid, role, roles, inst, dept in users:
        session.add(
            SysUser(
                id=uid,
                username=uid,
                display_name=uid,
                institute_id=inst,
                department=dept,
                role=role,
                roles_json=json.dumps(roles),
                is_active=True,
            )
        )


def test_defect_rectification_bound_admin_isolated_and_super_admin_supported():
    engine = create_engine(
        "sqlite://", execution_options={"schema_translate_map": {"qc": None}}
    )
    for model in (SysUser, DefectRectification, DefectRectificationEvent):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    now = datetime.utcnow()
    with sessions.begin() as s:
        _seed_sys_users(s)
        for idx, inst in enumerate(("H1", "H2"), 1):
            s.add(
                DefectRectification(
                    id=f"rect-{inst}",
                    institute_id=inst,
                    patient_id=f"P{idx}",
                    visit_id=f"V{idx}",
                    scene="running",
                    target_kind="canonical_defect",
                    target_id="LX0609-01-01-01",
                    root_job_id=f"job-{idx}",
                    envelope_id=f"env-{idx}",
                    rule_set_key="luxian_0609_qc_v1",
                    rule_set_version="1",
                    department="内科",
                    creator_id="mgr-h1",
                    assignee_id=f"doc-{inst.lower()}",
                    assignee_name=f"doc-{inst.lower()}",
                    requirement="请尽快按要求补充完整病历记录",
                    status="pending",
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )

    svc = DefectRectificationService(session_factory=sessions)
    # 绑定院区 admin 仅看本院区，访问外院 403
    assert [row["id"] for row in svc.list("admin-h1")["items"]] == ["rect-H1"]
    with pytest.raises(RectificationError) as exc:
        svc.detail("admin-h1", "rect-H2")
    assert exc.value.status == 403
    # 绑定院区 super_admin 同样受本院区隔离且具备管理角色
    assert [row["id"] for row in svc.list("super-h1")["items"]] == ["rect-H1"]
    with pytest.raises(RectificationError) as exc:
        svc.detail("super-h1", "rect-H2")
    assert exc.value.status == 403
    # 未绑定院区 admin / super_admin 与带院区 sync_admin 保留全局视角
    for actor in ("admin-global", "super-global", "sync-h1"):
        ids = {row["id"] for row in svc.list(actor)["items"]}
        assert ids == {"rect-H1", "rect-H2"}
        assert svc.detail(actor, "rect-H2")["id"] == "rect-H2"
    engine.dispose()


def test_modern_appeal_bound_admin_isolated_and_super_admin_supported():
    engine = create_engine(
        "sqlite://", execution_options={"schema_translate_map": {"qc": None}}
    )
    for model in (SysUser, DefectRectification, QCAppeal, QCAppealReview):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    now = datetime.utcnow()
    with sessions.begin() as s:
        _seed_sys_users(s)
        for idx, inst in enumerate(("H1", "H2"), 1):
            s.add(
                modern_appeal_service.QCAppeal(
                    id=f"app-{inst}",
                    qc_result_id=None,
                    record_id=None,
                    appeal_type="defect",
                    defect_item="LX0609-01-01-01",
                    reason="合成申诉原因超过十个字",
                    priority="medium",
                    appellant_id=f"doc-{inst.lower()}",
                    appellant_name=f"doc-{inst.lower()}",
                    appellant_department="内科",
                    case_department="内科",
                    status="pending",
                    target_kind="canonical_defect",
                    target_id="LX0609-01-01-01",
                    institute_id=inst,
                    patient_id=f"P{idx}",
                    visit_id=f"V{idx}",
                    scene="running",
                    root_job_id=f"job-{idx}",
                    envelope_id=f"env-{idx}",
                    rule_set_key="luxian_0609_qc_v1",
                    rule_set_version="1",
                    created_at=now,
                )
            )

    svc = ModernAppealService(session_factory=sessions)
    assert [row["id"] for row in svc.list("admin-h1")["items"]] == ["app-H1"]
    assert [row["id"] for row in svc.list("super-h1")["items"]] == ["app-H1"]
    with pytest.raises(RectificationError) as exc:
        svc.detail("admin-h1", "app-H2")
    assert exc.value.status == 404
    with pytest.raises(RectificationError) as exc:
        svc.detail("super-h1", "app-H2")
    assert exc.value.status == 404
    for actor in ("admin-global", "super-global", "sync-h1"):
        assert {row["id"] for row in svc.list(actor)["items"]} == {"app-H1", "app-H2"}
    engine.dispose()


def test_case_communication_bound_admin_isolated_and_super_admin_supported():
    bound_admin = {"roles": {"admin"}, "institute_id": "H1"}
    unbound_admin = {"roles": {"admin"}, "institute_id": None}
    bound_super = {"roles": {"super_admin"}, "institute_id": "H1"}
    unbound_super = {"roles": {"super_admin"}, "institute_id": None}
    sync_with_inst = {"roles": {"sync_admin", "admin", "super_admin"}, "institute_id": "H1"}

    case_communication_service._manager(bound_admin, "H1")
    with pytest.raises(RectificationError) as exc:
        case_communication_service._manager(bound_admin, "H2")
    assert exc.value.status == 403

    case_communication_service._manager(bound_super, "H1")
    with pytest.raises(RectificationError) as exc:
        case_communication_service._manager(bound_super, "H2")
    assert exc.value.status == 403

    for global_actor in (unbound_admin, unbound_super, sync_with_inst):
        case_communication_service._manager(global_actor, "H2")


def test_record_review_workflow_bound_admin_isolated_and_super_admin_supported():
    engine = create_engine(
        "sqlite://", execution_options={"schema_translate_map": {"qc": None}}
    )
    for model in (SysUser, QCRecordReview):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    now = datetime.utcnow()
    with sessions.begin() as s:
        _seed_sys_users(s)
        for idx, inst in enumerate(("H1", "H2"), 1):
            s.add(
                record_review_workflow_service.QCRecordReview(
                    id=f"rev-{inst}",
                    request_id=f"00000000-0000-0000-0000-00000000000{idx}",
                    institute_id=inst,
                    patient_id=f"P{idx}",
                    visit_id=f"V{idx}",
                    rule_set_key="luxian_0609_qc_v1",
                    rule_set_version="1",
                    job_id=f"job-{idx}",
                    envelope_id=f"env-{idx}",
                    review_context="workspace",
                    scene="running",
                    stage="initial",
                    decision="approved",
                    reviewer_id="mgr-h1",
                    created_at=now,
                    defect_snapshot={"case_department": "内科"},
                )
            )

    svc = RecordReviewWorkflowService(
        sessions=sessions,
        candidates_loader=lambda session, actor: [],
    )
    assert [row["id"] for row in svc.list("admin-h1", state="history")["items"]] == ["rev-H1"]
    assert [row["id"] for row in svc.list("super-h1", state="history")["items"]] == ["rev-H1"]
    with pytest.raises(RectificationError) as exc:
        svc.history("admin-h1", "rev-H2")
    assert exc.value.status == 403
    with pytest.raises(RectificationError) as exc:
        svc.history("super-h1", "rev-H2")
    assert exc.value.status == 403
    for actor in ("admin-global", "super-global", "sync-h1"):
        assert {
            row["id"] for row in svc.list(actor, state="history")["items"]
        } == {"rev-H1", "rev-H2"}
    engine.dispose()


def test_manual_defect_entry_contexts_and_task_service_bound_admin_isolated(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_engine(
        "sqlite://", execution_options={"schema_translate_map": {"qc": None}}
    )
    for model in (SysUser, QCTask, QCTaskRecord, QCTaskQCRun):
        model.__table__.create(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as s:
        _seed_sys_users(s)
        s.add(
            QCTask(
                id="task-1",
                task_number="T-001",
                task_name="抽查任务",
                task_type="one_time",
                scene="running",
                status="in_progress",
                total_records=2,
                completed_records=0,
            )
        )
        for inst, rid, assignee in (
            ("H1", "rec-h1", "admin-h1"),
            ("H2", "rec-h2", "admin-h1"),
            ("H2", "rec-h2-super", "super-h1"),
            ("H2", "rec-h2-sync", "sync-h1"),
        ):
            s.add(
                QCTaskRecord(
                    id=rid,
                    task_id="task-1",
                    record_id=rid,
                    institute_id=inst,
                    patient_id=f"P-{rid}",
                    visit_id=f"V-{rid}",
                    assignee_id=assignee,
                    assignee_name=assignee,
                    status="in_progress",
                )
            )

    monkeypatch.setattr(manual_defect_reviews_router, "SessionLocal", sessions)
    # _entry_contexts: 绑定院区 admin 只见 H1 记录，不见 H2
    ctx = manual_defect_reviews_router._entry_contexts("admin-h1", "all", 1)
    assert [item["task_record_id"] for item in ctx["items"]] == ["rec-h1"]
    # super_admin 绑定 H1 不见 H2
    ctx_super = manual_defect_reviews_router._entry_contexts("super-h1", "all", 1)
    assert ctx_super["items"] == []
    # sync_admin 即使绑定 H1 仍可见 H2
    ctx_sync = manual_defect_reviews_router._entry_contexts("sync-h1", "all", 1)
    assert [item["task_record_id"] for item in ctx_sync["items"]] == ["rec-h2-sync"]

    # task_manual_defect_service._context
    with sessions() as s:
        task_manual_defect_service._context(s, "task-1", "rec-h1", "admin-h1", lock=False)
        with pytest.raises(task_manual_defect_service.TaskManualDefectForbidden):
            task_manual_defect_service._context(s, "task-1", "rec-h2", "admin-h1", lock=False)
        with pytest.raises(task_manual_defect_service.TaskManualDefectForbidden):
            task_manual_defect_service._context(
                s, "task-1", "rec-h2-super", "super-h1", lock=False
            )
        task_manual_defect_service._context(
            s, "task-1", "rec-h2-sync", "sync-h1", lock=False
        )
    engine.dispose()


def test_report_institute_scope_and_remediation_appeals_routers_bound_admin_isolated(
    monkeypatch: pytest.MonkeyPatch,
):
    engine = create_engine("sqlite://")
    SysUser.__table__.create(engine)
    sessions = sessionmaker(engine)
    with sessions.begin() as s:
        _seed_sys_users(s)

    # report_institute_scope
    with sessions() as s:
        assert report_institute_scope.authorized_institute(s, "admin-h1") == "H1"
        assert report_institute_scope.authorized_institute(s, "admin-global") is None
        assert report_institute_scope.authorized_institute(s, "super-h1") == "H1"
        assert report_institute_scope.authorized_institute(s, "super-global") is None
        assert report_institute_scope.authorized_institute(s, "sync-h1") is None
        assert report_institute_scope.authorized_institute(s, "mgr-h1") == "H1"

    # remediation._resolve_actor & appeals._resolve_actor
    monkeypatch.setattr(db_connection, "SessionLocal", sessions)
    for router_mod, roles_set in (
        (remediation_router, remediation_router._MANAGE_ROLES),
        (appeals_router, appeals_router._REVIEW_ROLES),
    ):
        a_h1 = router_mod._resolve_actor({"id": "admin-h1"}, allowed_roles=roles_set)
        assert a_h1["is_global"] is False and a_h1["institute_id"] == "H1"

        a_global = router_mod._resolve_actor({"id": "admin-global"}, allowed_roles=roles_set)
        assert a_global["is_global"] is True and a_global["institute_id"] is None

        s_h1 = router_mod._resolve_actor({"id": "super-h1"}, allowed_roles=roles_set)
        assert s_h1["is_global"] is False and s_h1["institute_id"] == "H1"

        s_global = router_mod._resolve_actor({"id": "super-global"}, allowed_roles=roles_set)
        assert s_global["is_global"] is True and s_global["institute_id"] is None

        sync_h1 = router_mod._resolve_actor({"id": "sync-h1"}, allowed_roles=roles_set)
        assert sync_h1["is_global"] is True and sync_h1["institute_id"] is None
    engine.dispose()


# =============================================================================
# 3 & 4. qc_sichuan /debug & /review 角色+院区校验 + 演示账号拦截与结果裁剪
# =============================================================================


class _BatchJobStub:
    def __init__(self, job: dict[str, Any]):
        self.job = job

    def get_batch_job(self, *, job_id: str, created_by: str):
        if job_id != self.job["id"]:
            return None
        return dict(self.job)

    def update_batch_job_review_report(self, *, job_id: str, created_by: str, review_report: dict[str, Any]):
        updated = dict(self.job)
        updated["summary"] = {**dict(updated.get("summary") or {}), "review_report": review_report}
        return updated

    def export_batch_job_workbook(self, *, job: dict[str, Any]):
        from io import BytesIO

        return BytesIO(b"xlsx")


def _sample_job(institute_id: str = "H1") -> dict[str, Any]:
    return {
        "id": "job-demo-1",
        "draft_id": "sichuan-rule-library",
        "status": "completed",
        "scope": "final",
        "total_records": 2,
        "filters": {
            "rule_set_key": "sc_content_v1",
            "record_refs": [
                {"institute_id": institute_id, "patient_id": "P1", "visit_id": "V1"},
            ],
        },
        "items": [
            {
                "record_ref": "rec_" + "1" * 24,
                "institute_id": institute_id,
                "rule_id": "SC-001",
                "status": "non_compliant",
                "is_confirmed_issue": True,
                "conclusion": "明确缺失签字",
            },
            {
                "record_ref": "rec_" + "2" * 24,
                "institute_id": institute_id,
                "rule_id": "SC-002",
                "status": "uncertain",
                "is_confirmed_issue": False,
                "conclusion": "待核实项",
            },
            {
                "record_ref": "rec_" + "2" * 24,
                "institute_id": institute_id,
                "rule_id": "SC-003",
                "status": "data_gap",
                "is_confirmed_issue": False,
                "conclusion": "资料缺失",
            },
            {
                "record_ref": "rec_" + "2" * 24,
                "institute_id": institute_id,
                "rule_id": "SC-004",
                "status": "no_issue",
                "conclusion": "无问题",
            },
            {
                "record_ref": "rec_" + "2" * 24,
                "institute_id": institute_id,
                "rule_id": "SC-005",
                "status": "ai_suggested_non_compliant",
                "is_confirmed_issue": False,
                "conclusion": "AI建议复核",
            },
        ],
        "failed_records": [{"record_id": "V-err", "error": "internal timeout"}],
        "rule_results": [
            {
                "id": "rr-1",
                "rule_code": "SC-001",
                "status": "completed",
                "debug": {"prompt": "secret"},
                "items": [
                    {"rule_id": "SC-001", "status": "non_compliant"},
                    {"rule_id": "SC-002", "status": "uncertain"},
                ],
            }
        ],
        "summary": {
            "total_records": 2,
            "success_count": 2,
            "failed_count": 0,
            "rule_count": 5,
            "issue_records": 2,
            "uncertain_records": 1,
            "data_quality_gap_count": 1,
            "result_count": 5,
            "status_counts": {
                "non_compliant": 1,
                "uncertain": 1,
                "data_gap": 1,
                "no_issue": 1,
                "ai_suggested_non_compliant": 1,
            },
            "status_breakdown": {"non_compliant": 1, "uncertain": 1, "data_gap": 1},
            "display_status_counts": {"non_compliant": 1, "uncertain": 1},
            "history_issue_summaries": [
                {"rule_id": "SC-001", "status": "non_compliant", "text": "明确缺失签字"},
                {"rule_id": "SC-002", "status": "uncertain", "text": "待核实项"},
            ],
            "review_report": {
                "scope": "luxian_0609_qc_v1",
                "summary": {"total_findings": 1, "p0": 0, "p1": 1, "p2": 0},
                "findings": [{"rule_id": "SC-002", "suggested_status": "not_applicable"}],
            },
            "automatic_failed_rule_retry": {"status": "completed", "max_attempts": 1},
        },
    }


@pytest.mark.asyncio
async def test_debug_endpoint_enforces_role_and_institute_scope(monkeypatch: pytest.MonkeyPatch):
    job = _sample_job(institute_id="H2")
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: _BatchJobStub(job))
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _uid: "H1")

    # 非 trace 角色（qc_manager / doctor）一律 403
    for bad_role in ("qc_manager", "doctor", "qc_staff"):
        with pytest.raises(HTTPException) as exc:
            await qc_sichuan.get_workspace_batch_job_debug(
                _request(),
                "job-demo-1",
                rule_job_id=None,
                item_limit=30,
                current_user={"id": "u-bad", "roles": [bad_role]},
            )
        assert exc.value.status_code == 403

    # 绑定 H1 的 admin 访问 H2 任务 -> 403
    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.get_workspace_batch_job_debug(
            _request(),
            "job-demo-1",
            rule_job_id=None,
            item_limit=30,
            current_user={"id": "admin-h1", "roles": ["admin"], "institute_id": "H1"},
        )
    assert exc.value.status_code == 403

    # 同院区 admin -> 200
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _uid: "H2")
    resp = await qc_sichuan.get_workspace_batch_job_debug(
        _request(),
        "job-demo-1",
        rule_job_id=None,
        item_limit=30,
        current_user={"id": "admin-h2", "roles": ["admin"], "institute_id": "H2"},
    )
    assert resp["success"] is True
    assert resp["data"]["job_id"] == "job-demo-1"


@pytest.mark.asyncio
async def test_review_endpoint_enforces_role_and_institute_scope(monkeypatch: pytest.MonkeyPatch):
    job = _sample_job(institute_id="H2")
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: _BatchJobStub(job))
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _uid: "H1")

    # 非复核角色（doctor / qc_staff / 无角色）-> 403
    for user in (
        {"id": "u-doc", "roles": ["doctor"]},
        {"id": "u-staff", "roles": ["qc_staff"]},
        {"id": "u-empty"},
    ):
        with pytest.raises(HTTPException) as exc:
            await qc_sichuan.review_workspace_batch_job(_request(), "job-demo-1", current_user=user)
        assert exc.value.status_code == 403

    # 跨院区 qc_manager 与绑定院区 admin -> 403
    for user in (
        {"id": "mgr-h1", "roles": ["qc_manager"], "institute_id": "H1"},
        {"id": "admin-h1", "roles": ["admin"], "institute_id": "H1"},
    ):
        with pytest.raises(HTTPException) as exc:
            await qc_sichuan.review_workspace_batch_job(_request(), "job-demo-1", current_user=user)
        assert exc.value.status_code == 403


def test_is_restricted_demo_account_semantics():
    assert qc_sichuan._is_restricted_demo_account({"id": "u1", "roles": ["admin"]}) is False
    assert (
        qc_sichuan._is_restricted_demo_account(
            {"id": "u1", "roles": ["admin"], "is_demo_account": False}
        )
        is False
    )
    assert (
        qc_sichuan._is_restricted_demo_account(
            {"id": "u1", "roles": ["admin"], "is_demo_account": True}
        )
        is True
    )
    assert (
        qc_sichuan._is_restricted_demo_account(
            {"id": "u1", "roles": ["qc_manager"], "is_demo_account": True}
        )
        is True
    )
    for exempt in ("sync_admin", "super_admin", "developer"):
        assert (
            qc_sichuan._is_restricted_demo_account(
                {"id": "u1", "roles": [exempt], "is_demo_account": True}
            )
            is False
        )


@pytest.mark.asyncio
async def test_demo_account_blocked_on_debug_review_export_and_trimmed_on_detail_and_notification(
    monkeypatch: pytest.MonkeyPatch,
):
    job = _sample_job(institute_id="H1")
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: _BatchJobStub(job))
    monkeypatch.setattr(saved_result_access, "saved_result_institute_scope", lambda _uid: None)

    demo_admin = {"id": "demo-admin", "roles": ["admin"], "is_demo_account": True}
    normal_admin = {"id": "real-admin", "roles": ["admin"], "is_demo_account": False}
    demo_sync_admin = {"id": "sync-1", "roles": ["sync_admin"], "is_demo_account": True}

    # 演示账号阻断 /debug, /review, /export
    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.get_workspace_batch_job_debug(
            _request(), "job-demo-1", rule_job_id=None, item_limit=30, current_user=demo_admin
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.review_workspace_batch_job(
            _request(), "job-demo-1", current_user=demo_admin
        )
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        await qc_sichuan.export_workspace_batch_job(
            _request(), "job-demo-1", format="xlsx", current_user=demo_admin
        )
    assert exc.value.status_code == 403

    # sync_admin 即使 is_demo_account=True 仍可访问 /debug
    sync_debug = await qc_sichuan.get_workspace_batch_job_debug(
        _request(), "job-demo-1", rule_job_id=None, item_limit=30, current_user=demo_sync_admin
    )
    assert sync_debug["success"] is True

    # GET /batch-jobs/{job_id}：演示账号仅保留确定问题并剥离 review_report
    demo_detail = await qc_sichuan.get_workspace_batch_job(
        _request(), "job-demo-1", current_user=demo_admin
    )
    data = demo_detail["data"]
    assert [item["rule_id"] for item in data["items"]] == ["SC-001"]
    assert data["failed_records"] == []
    assert "review_report" not in data["summary"]
    assert "automatic_failed_rule_retry" not in data["summary"]
    assert data["summary"]["status_counts"] == {"non_compliant": 1}
    assert data["summary"]["uncertain_records"] == 0
    assert data["summary"]["data_quality_gap_count"] == 0
    assert data["summary"]["result_count"] == 1
    assert data["summary"]["issue_records"] == 1
    assert data["summary"]["total_records"] == 2
    assert [h["rule_id"] for h in data["summary"]["history_issue_summaries"]] == ["SC-001"]
    assert "debug" not in data["rule_results"][0]
    assert [i["rule_id"] for i in data["rule_results"][0]["items"]] == ["SC-001"]

    # 普通 admin 与 sync_admin 保留完整结论与 review_report
    for privileged in (normal_admin, demo_sync_admin):
        full_detail = await qc_sichuan.get_workspace_batch_job(
            _request(), "job-demo-1", current_user=privileged
        )
        assert len(full_detail["data"]["items"]) == 5
        assert "review_report" in full_detail["data"]["summary"]

    # GET /api/v1/notifications/{notification_id}/qc-result：同步裁剪演示账号响应
    monkeypatch.setattr(
        notifications_router.service,
        "result_ready",
        lambda actor_id, notif_id, loader: qc_sichuan._workspace_batch_response_item(
            _sample_job("H1")
        ),
    )
    demo_notif = await notifications_router.get_notification_qc_result(
        "notif-1", _request(), current_user=demo_admin
    )
    notif_data = demo_notif["data"]
    assert [item["rule_id"] for item in notif_data["items"]] == ["SC-001"]
    assert "review_report" not in notif_data["summary"]
    assert notif_data["summary"]["status_counts"] == {"non_compliant": 1}
    assert notif_data["summary"]["uncertain_records"] == 0

    normal_notif = await notifications_router.get_notification_qc_result(
        "notif-1", _request(), current_user=normal_admin
    )
    assert len(normal_notif["data"]["items"]) == 5
    assert "review_report" in normal_notif["data"]["summary"]
