"""Wave 2 (workflow-c) 离线回归单测：覆盖 P1-C1 / P1-C2 / P1-C3 / P1-C4 / P2-C1 / P2-C3。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import json
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database.models.case_communication import CaseCommunication
from app.database.models.v36_reports import (
    DefectRectification as Task,
    DefectRectificationEvent as TaskEvent,
    QCAppeal,
    QCAppealReview,
    QCRecordReview as ReportReview,
    SysUser,
)
from app.routers import defect_rectifications as rectification_router
from app.routers import notifications as notifications_router
from app.services import record_review_service
from app.services import workflow_queue_state_service as wq_mod
from app.services.case_communication_service import CaseCommunicationService
from app.services.defect_rectification_service import (
    DefectRectificationService,
    RectificationError,
)
from app.services.doctor_notification_service import (
    DoctorNotificationService,
    Notification,
    QC_SOURCE,
)
from app.services.feedback_result_source import verify_historical_envelope
from app.services.luxian_0609_rule_catalog import LUXIAN_0609_RULE_SET_KEY
from app.services.modern_appeal_service import ModernAppealService
from app.services.record_review_defect_snapshot_service import validate_snapshot
from app.services.record_review_workflow_service import (
    QCRecordReview,
    RecordReviewWorkflowService,
)
from app.services.workflow_queue_state_service import WorkflowQueueStateService


def _create_queue_schema(engine, *, tri_key_unique: bool = True):
    md = MetaData()
    queue_state = Table(
        "workflow_queue_state",
        md,
        Column("id", String(36), primary_key=True, nullable=False),
        Column("workflow_type", String(32), nullable=False),
        Column("visit_id", String(100), nullable=False),
        Column("patient_id", String(100), nullable=True),
        Column("institute_id", String(100), nullable=True),
        Column("queue_status", String(16), nullable=False),
        Column("queue_status_source", String(16), nullable=False),
        Column("run_id", String(36), nullable=True),
        Column("last_error", Text(), nullable=True),
        Column("last_started_at", DateTime(), nullable=True),
        Column("last_finished_at", DateTime(), nullable=True),
        Column("last_success_at", DateTime(), nullable=True),
        Column("updated_at", DateTime(), nullable=False),
        Column("updated_by", String(100), nullable=False),
    )
    if tri_key_unique:
        Index(
            "ux_queue_state_workflow_tri_key",
            queue_state.c.workflow_type,
            queue_state.c.institute_id,
            queue_state.c.patient_id,
            queue_state.c.visit_id,
            unique=True,
        )
    else:
        Index(
            "ux_queue_state_workflow_visit",
            queue_state.c.workflow_type,
            queue_state.c.visit_id,
            unique=True,
        )

    mr = Table(
        "mr",
        md,
        Column("institute_id", String(100), primary_key=True),
        Column("patient_id", String(100), primary_key=True),
        Column("visit_id", String(100), primary_key=True),
    )
    draft = Table(
        "ai_frontpage_draft",
        md,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("institute_id", String(100), nullable=True),
        Column("patient_id", String(100), nullable=False),
        Column("visit_id", String(100), nullable=False),
        Column("updated_at", DateTime(), nullable=False),
    )
    qc_results = Table(
        "qc_results",
        md,
        Column("id", String(36), primary_key=True),
        Column("record_id", String(100), nullable=False),
        Column("institute_id", String(100), nullable=True),
        Column("patient_id", String(100), nullable=True),
        Column("visit_id", String(100), nullable=True),
        Column("analysis_date", DateTime(), nullable=True),
        Column("created_at", DateTime(), nullable=False),
    )
    md.create_all(engine)
    return queue_state, mr, draft, qc_results


def _doc_payload(content: str = "合成正文"):
    return {
        "documents": [
            {
                "execution_domain": "admission",
                "doc_type": "admission_record",
                "document_id": "doc-1",
                "content": content,
                "sections": [],
            }
        ],
        "domain_projection": {
            "domains": {
                "admission": {"per_source": {"admission_record": {"has_more": False}}}
            }
        },
    }


# ==================== P1-C1 ====================


def test_p1_c1_lazy_default_singleton_does_not_require_db_at_init(monkeypatch):
    monkeypatch.setattr(wq_mod, "SessionLocal", None)
    monkeypatch.setattr(wq_mod, "engine", None)
    monkeypatch.setattr(wq_mod, "_default_workflow_queue_state_service", None)

    svc = WorkflowQueueStateService()
    assert svc is not None
    # 懒代理属性获取不会在未执行 DB 操作时崩溃
    assert callable(wq_mod.default_workflow_queue_state_service.get_state_map)

    with pytest.raises(RuntimeError, match="DATABASE_URL is not configured"):
        wq_mod.default_workflow_queue_state_service.get_state_map(
            workflow_type="coding_qc",
            visit_ids=["V1"],
        )


def test_p1_c1_tri_key_isolation_and_finish_guard():
    engine = create_engine("sqlite:///:memory:")
    try:
        _create_queue_schema(engine, tri_key_unique=True)
        sessions = sessionmaker(engine)
        svc = WorkflowQueueStateService(session_factory=sessions)

        run_h1 = svc.start_run(
            workflow_type="coding_qc",
            institute_id="H1",
            patient_id="P1",
            visit_id="V1",
            user_id="u1",
        )
        run_h2 = svc.start_run(
            workflow_type="coding_qc",
            institute_id="H2",
            patient_id="P1",
            visit_id="V1",
            user_id="u2",
        )

        # 用错机构坐标不得误改其他机构运行态
        assert (
            svc.finish_success(
                workflow_type="coding_qc",
                institute_id="H2",
                patient_id="P1",
                visit_id="V1",
                run_id=run_h1,
            )
            is False
        )
        assert (
            svc.finish_success(
                workflow_type="coding_qc",
                institute_id="H1",
                patient_id="P1",
                visit_id="V1",
                run_id=run_h1,
            )
            is True
        )
        assert (
            svc.finish_failed(
                workflow_type="coding_qc",
                institute_id="H2",
                patient_id="P1",
                visit_id="V1",
                run_id=run_h2,
                error_message="H2 failed",
            )
            is True
        )

        tri_map = svc.get_state_map(
            workflow_type="coding_qc",
            record_refs=[("H1", "P1", "V1"), ("H2", "P1", "V1")],
        )
        assert tri_map[("H1", "P1", "V1")]["queue_status"] == "succeeded"
        assert tri_map[("H2", "P1", "V1")]["queue_status"] == "failed"
        assert tri_map[("H2", "P1", "V1")]["last_error"] == "H2 failed"

        # 兼容单键入参并在指定 institute_id 时严格过滤
        h1_only = svc.get_state_map(
            workflow_type="coding_qc", visit_ids=["V1"], institute_id="H1"
        )
        assert h1_only["V1"]["institute_id"] == "H1"
        assert h1_only["V1"]["queue_status"] == "succeeded"
    finally:
        engine.dispose()


def test_p1_c1_backfill_tri_key_join_runtime_guard_and_stale_reset():
    engine = create_engine("sqlite:///:memory:")
    try:
        queue_state, mr, draft, _ = _create_queue_schema(engine, tri_key_unique=True)
        sessions = sessionmaker(engine)
        now = datetime(2026, 3, 20, 10, 0, 0)
        with engine.begin() as conn:
            conn.execute(
                mr.insert(),
                [
                    {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"},
                    {"institute_id": "H2", "patient_id": "P1", "visit_id": "V1"},
                    {"institute_id": "H3", "patient_id": "P1", "visit_id": "V1"},
                ],
            )
            # 只有 H1 和 H3 有草稿，H2 同 visit_id 无草稿，不能串态成 succeeded
            conn.execute(
                draft.insert(),
                [
                    {
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "updated_at": now,
                    },
                    {
                        "institute_id": "H3",
                        "patient_id": "P1",
                        "visit_id": "V1",
                        "updated_at": now,
                    },
                ],
            )

        svc = WorkflowQueueStateService(session_factory=sessions)
        # 先写入实时态：H1=running，H2=failed，H3=succeeded(含残留 error/run_id)
        svc.start_run(
            workflow_type="frontpage_generate",
            institute_id="H1",
            patient_id="P1",
            visit_id="V1",
        )
        run_h2 = svc.start_run(
            workflow_type="frontpage_generate",
            institute_id="H2",
            patient_id="P1",
            visit_id="V1",
        )
        svc.finish_failed(
            workflow_type="frontpage_generate",
            institute_id="H2",
            patient_id="P1",
            visit_id="V1",
            run_id=run_h2,
            error_message="runtime failure",
        )
        run_h3 = svc.start_run(
            workflow_type="frontpage_generate",
            institute_id="H3",
            patient_id="P1",
            visit_id="V1",
        )
        svc.finish_success(
            workflow_type="frontpage_generate",
            institute_id="H3",
            patient_id="P1",
            visit_id="V1",
            run_id=run_h3,
        )
        with engine.begin() as conn:
            conn.execute(
                sa.update(queue_state)
                .where(queue_state.c.institute_id == "H3")
                .values(last_error="stale_error_leftover")
            )

        svc.backfill_frontpage_generate(
            record_refs=[("H1", "P1", "V1"), ("H2", "P1", "V1"), ("H3", "P1", "V1")]
        )

        states = svc.get_state_map(
            workflow_type="frontpage_generate",
            record_refs=[("H1", "P1", "V1"), ("H2", "P1", "V1"), ("H3", "P1", "V1")],
        )
        # runtime running/failed 受 where 守卫保护不被回填覆盖
        assert states[("H1", "P1", "V1")]["queue_status"] == "running"
        assert states[("H1", "P1", "V1")]["queue_status_source"] == "runtime"
        assert states[("H2", "P1", "V1")]["queue_status"] == "failed"
        assert states[("H2", "P1", "V1")]["queue_status_source"] == "runtime"
        assert states[("H2", "P1", "V1")]["last_error"] == "runtime failure"
        # 安全更新的 H3 应重置残留 run_id 与 last_error
        assert states[("H3", "P1", "V1")]["queue_status"] == "succeeded"
        assert states[("H3", "P1", "V1")]["queue_status_source"] == "backfill"
        assert states[("H3", "P1", "V1")]["run_id"] is None
        assert states[("H3", "P1", "V1")]["last_error"] is None

        # 再验证新建的同 visit_id 无草稿 H4（无 runtime 行）回填为 pending 而非串 H1 的 succeeded
        with engine.begin() as conn:
            conn.execute(
                mr.insert(),
                [{"institute_id": "H4", "patient_id": "P1", "visit_id": "V1"}],
            )
        svc.backfill_frontpage_generate(record_refs=[("H4", "P1", "V1")])
        h4 = svc.get_state_map(
            workflow_type="frontpage_generate", record_refs=[("H4", "P1", "V1")]
        )
        assert h4[("H4", "P1", "V1")]["queue_status"] == "pending"
    finally:
        engine.dispose()


def test_p1_c1_get_state_map_separates_missing_table_from_real_db_failure():
    empty_engine = create_engine("sqlite:///:memory:")
    try:
        svc_missing = WorkflowQueueStateService(session_factory=sessionmaker(empty_engine))
        # 可控缺表返回空 dict
        assert (
            svc_missing.get_state_map(workflow_type="coding_qc", visit_ids=["V1"]) == {}
        )
    finally:
        empty_engine.dispose()

    broken_engine = create_engine("sqlite:///:memory:")
    try:
        _create_queue_schema(broken_engine, tri_key_unique=True)
        sessions = sessionmaker(broken_engine)

        class _BrokenSession:
            def get_bind(self):
                return broken_engine

            def execute(self, *args, **kwargs):
                raise OperationalError("SELECT 1", {}, Exception("connection refused"))

            def close(self):
                pass

        svc_broken = WorkflowQueueStateService(session_factory=_BrokenSession)
        with pytest.raises(OperationalError, match="connection refused"):
            svc_broken.get_state_map(workflow_type="coding_qc", visit_ids=["V1"])
    finally:
        broken_engine.dispose()


def test_p1_c1_legacy_two_column_unique_index_still_supported():
    engine = create_engine("sqlite:///:memory:")
    try:
        _create_queue_schema(engine, tri_key_unique=False)
        svc = WorkflowQueueStateService(session_factory=sessionmaker(engine))
        run_id = svc.start_run(
            workflow_type="coding_qc",
            visit_id="V-LEG",
            patient_id="P-LEG",
            institute_id="H-LEG",
        )
        assert (
            svc.finish_success(
                workflow_type="coding_qc", visit_id="V-LEG", run_id=run_id
            )
            is True
        )
        state_map = svc.get_state_map(workflow_type="coding_qc", visit_ids=["V-LEG"])
        assert state_map["V-LEG"]["queue_status"] == "succeeded"
    finally:
        engine.dispose()


# ==================== P1-C2 ====================


def test_p1_c2_running_doubtful_does_not_leak_into_first_final_review(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", execution_options={"schema_translate_map": {"qc": None}}
    )
    try:
        ReportReview.__table__.create(engine)
        sessions = sessionmaker(engine)

        running_src = dict(
            institute_id="A",
            patient_id="P",
            visit_id="V",
            scene="running",
            root_job_id="J_RUN_1",
            envelope_id="E_RUN_1",
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
            rule_set_version="1",
        )
        final_src = dict(
            institute_id="A",
            patient_id="P",
            visit_id="V",
            scene="final",
            root_job_id="J_FIN_1",
            envelope_id="E_FIN_1",
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
            rule_set_version="1",
        )
        active = {"current": running_src}
        candidates_box = {"items": [deepcopy(running_src) | {"case_department": "内科"}]}

        def snapshot_loader(session, current, captured_at):
            frozen = {
                k: v
                for k, v in current.items()
                if k not in {"root_job_id", "items"}
            } | {"job_id": current["root_job_id"]}
            return validate_snapshot(
                dict(
                    schema_version=1,
                    complete=True,
                    captured_at=captured_at.isoformat() + "+00:00",
                    source=frozen,
                    auto={"count": 1, "items": [{"defect_id": "R1", "rule_id": "R1"}]},
                    manual={"count": 0, "items": []},
                ),
                source=frozen,
            )

        svc = RecordReviewWorkflowService(
            sessions,
            person_loader=lambda s, actor: dict(
                id="staff", name="质控员", roles={"qc_staff"}, institute_id="A", department="内科"
            ),
            source_loader=lambda s, identity, job, env: (
                deepcopy(active["current"])
                | {"items": [{"rule_id": "R1", "is_confirmed_issue": True}]}
            ),
            department_loader=lambda s, identity: "内科",
            snapshot_loader=snapshot_loader,
            candidates_loader=lambda s, actor: deepcopy(candidates_box["items"]),
        )

        # 1. 在院运行审核标为 doubtful
        r1 = svc.submit(
            "staff",
            source=running_src,
            expected_state="pending_review",
            decision="doubtful",
            reason="在院病历需补全记录",
            request_id=str(uuid4()),
        )
        assert r1["stage"] == "initial"
        assert r1["decision"] == "doubtful"

        # 2. 出院后首次终末结果到达：必须仍为 pending_review / initial，不能受 running doubtful 污染
        active["current"] = final_src
        candidates_box["items"] = [
            deepcopy(running_src) | {"case_department": "内科"},
            deepcopy(final_src) | {"case_department": "内科"},
        ]

        cur_final = svc.current("staff", source=final_src)
        assert cur_final["state"] == "pending_review"
        assert cur_final["stage"] == "initial"

        lst_final = svc.list("staff", scene="final")
        assert lst_final["initial_count"] == 1
        assert lst_final["recheck_count"] == 0
        assert lst_final["items"][0]["state"] == "pending_review"
        assert lst_final["items"][0]["stage"] == "initial"

        # 3. 批量状态推导同样按 scene 隔离
        monkeypatch.setattr(record_review_service, "SessionLocal", sessions)
        batch_states = record_review_service.batch_review_states(
            [
                {
                    "institute_id": "A",
                    "patient_id": "P",
                    "visit_id": "V",
                    "job_id": "J_FIN_1",
                    "envelope_id": "E_FIN_1",
                    "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                    "scene": "final",
                }
            ]
        )
        assert batch_states[("A", "P", "V")] == "pending_review"

        # 同在院场景下一轮仍正确推导为 pending_recheck
        batch_running_next = record_review_service.batch_review_states(
            [
                {
                    "institute_id": "A",
                    "patient_id": "P",
                    "visit_id": "V",
                    "job_id": "J_RUN_2",
                    "envelope_id": "E_RUN_2",
                    "rule_set_key": LUXIAN_0609_RULE_SET_KEY,
                    "scene": "running",
                }
            ]
        )
        assert batch_running_next[("A", "P", "V")] == "pending_recheck"

        # 4. 提交首次终末初审：stage 必须为 initial 且落盘完整 defect_snapshot
        f1 = svc.submit(
            "staff",
            source=final_src,
            expected_state="pending_review",
            decision="approved",
            reason="终末初审通过",
            request_id=str(uuid4()),
        )
        assert f1["stage"] == "initial"
        with sessions() as session:
            saved = session.get(QCRecordReview, f1["id"])
            assert saved.scene == "final"
            assert saved.stage == "initial"
            assert saved.defect_snapshot["complete"] is True
            assert saved.defect_snapshot["auto"]["count"] == 1
            assert saved.defect_snapshot["case_department"] == "内科"
    finally:
        engine.dispose()


# ==================== P1-C3 ====================


def test_p1_c3_global_admin_receives_and_views_qc_feedback_without_409_rollback():
    engine = create_engine(
        "sqlite:///:memory:", execution_options={"schema_translate_map": {"qc": None}}
    )
    try:
        for model in (Task, TaskEvent, QCAppeal, QCAppealReview, Notification, SysUser):
            model.__table__.create(engine)
        sessions = sessionmaker(engine)

        source = dict(
            institute_id="A",
            patient_id="P1",
            visit_id="V1",
            scene="running",
            target_kind="canonical_defect",
            target_id="R1",
            root_job_id="J1",
            envelope_id="E1",
            rule_set_key="K",
            rule_set_version="1",
        )
        with sessions.begin() as s:
            # 只有全局 admin (institute_id=None) 与 super_admin (institute_id=None)，机构 A 无本地质控主管
            s.add_all(
                [
                    SysUser(
                        id="gadmin",
                        username="gadmin",
                        display_name="全局管理员",
                        role="admin",
                        institute_id=None,
                        department=None,
                        is_active=True,
                    ),
                    SysUser(
                        id="sadmin",
                        username="sadmin",
                        display_name="超管",
                        role="super_admin",
                        institute_id=None,
                        department=None,
                        is_active=True,
                    ),
                    SysUser(
                        id="bad_mgr",
                        username="bad_mgr",
                        display_name="无机构主管",
                        role="qc_manager",
                        institute_id=None,
                        department=None,
                        is_active=True,
                    ),
                    SysUser(
                        id="doc",
                        username="doc",
                        display_name="医生",
                        role="doctor",
                        institute_id="A",
                        department="内科",
                        is_active=True,
                    ),
                ]
            )
            s.add(
                Task(
                    id="task-global",
                    **source,
                    department="内科",
                    creator_id="gadmin",
                    assignee_id="doc",
                    assignee_name="医生",
                    requirement="全局管理员派发的整改要求不少于十字",
                    status="pending",
                    version=1,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

        notif_svc = DoctorNotificationService(sessions)
        rect_svc = DefectRectificationService(
            sessions,
            document_loader=lambda **identity: _doc_payload(),
        )
        appeal_svc = ModernAppealService(
            sessions,
            source_loader=lambda s, d: dict(source),
            department_loader=lambda s, i: "内科",
        )

        # 1. 医生提交整改：不再 409 回滚，全局 admin 收到并可见 qc_feedback
        submitted = rect_svc.transition(
            "doc",
            "task-global",
            version=1,
            action="submit",
            comment="医生已完成整改并提交说明不少于十字",
        )
        assert submitted["status"] == "submitted"
        gadmin_list = notif_svc.list("gadmin")
        assert gadmin_list["total"] == 1
        assert gadmin_list["unread_count"] == 1
        assert gadmin_list["items"][0]["source_key"] == QC_SOURCE
        assert gadmin_list["items"][0]["title"] == "医生提交了整改"
        assert notif_svc.mark_read("gadmin", gadmin_list["items"][0]["id"]) == 1

        # 无机构 qc_manager 绝不能收到或看到该通知
        assert notif_svc.list("bad_mgr")["total"] == 0

        # 2. 医生发起申诉并撤回：同样路由至全局 admin 且可见
        appeal = appeal_svc.create(
            "doc", rectification_id="task-global", reason="医生申诉理由不少于十个字"
        )
        appeal_svc.transition(
            "doc",
            appeal["id"],
            expected_status="pending",
            action="withdraw",
            comment="医生撤回申诉说明不少于十个字",
        )
        titles = {item["title"] for item in notif_svc.list("gadmin")["items"]}
        assert {"医生提交了整改", "医生提交了申诉", "医生撤回了申诉"} <= titles

        # 3. 若原全局 admin 停用，则兜底路由至全局 super_admin 且 super_admin 可见
        with sessions.begin() as s:
            s.get(SysUser, "gadmin").is_active = False
        appeal2 = appeal_svc.create(
            "doc", rectification_id="task-global", reason="二次申诉理由不少于十个字"
        )
        assert appeal2["status"] == "pending"
        sadmin_list = notif_svc.list("sadmin")
        assert sadmin_list["total"] == 1
        assert sadmin_list["items"][0]["title"] == "医生提交了申诉"
    finally:
        engine.dispose()


# ==================== P1-C4 ====================


def test_p1_c4_stale_appeal_supersede_and_close_stale():
    engine = create_engine(
        "sqlite:///:memory:", execution_options={"schema_translate_map": {"qc": None}}
    )
    try:
        for model in (Task, QCAppeal, QCAppealReview, Notification, SysUser):
            model.__table__.create(engine)
        sessions = sessionmaker(engine)

        source = dict(
            institute_id="A",
            patient_id="P",
            visit_id="V",
            scene="running",
            target_kind="canonical_defect",
            target_id="R1",
            root_job_id="J1",
            envelope_id="E1",
            rule_set_key="K",
            rule_set_version="1",
        )
        with sessions.begin() as s:
            s.add_all(
                [
                    SysUser(
                        id="doc",
                        username="doc",
                        display_name="医生",
                        role="doctor",
                        institute_id="A",
                        department="内科",
                        is_active=True,
                    ),
                    SysUser(
                        id="mgr",
                        username="mgr",
                        display_name="质控主管",
                        role="qc_manager",
                        institute_id="A",
                        department="质控科",
                        is_active=True,
                    ),
                    SysUser(
                        id="admin",
                        username="admin",
                        display_name="管理员",
                        role="admin",
                        institute_id=None,
                        department=None,
                        is_active=True,
                    ),
                    SysUser(
                        id="staff",
                        username="staff",
                        display_name="质控员",
                        role="qc_staff",
                        institute_id="A",
                        department="质控科",
                        is_active=True,
                    ),
                ]
            )
            s.add(
                Task(
                    id="task1",
                    **source,
                    department="内科",
                    creator_id="mgr",
                    assignee_id="doc",
                    assignee_name="医生",
                    requirement="请补充完整病历资料不少于十字",
                    status="pending",
                    version=1,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )

        round_state = {"mode": "current"}

        def dynamic_source(session, data):
            if round_state["mode"] == "current":
                return dict(source)
            if round_state["mode"] == "new_round_diff":
                return {**source, "root_job_id": "J2", "envelope_id": "E2"}
            raise RectificationError("当前保存结果已变化或不可用，请刷新", 409)

        appeals = ModernAppealService(
            sessions,
            source_loader=dynamic_source,
            department_loader=lambda s, i: "内科",
        )
        notifs = DoctorNotificationService(sessions)

        a1 = appeals.create(
            "doc", rectification_id="task1", reason="第一条申诉原因不少于十个字"
        )
        # 当前轮次有效时禁止滥用 supersede / close_stale
        with pytest.raises(RectificationError) as active_err:
            appeals.close_stale("mgr", a1["id"])
        assert active_err.value.status == 409

        # 重跑产生新轮次（diff 形式）：常规 approve 仍 409，但 supersede 可终结
        round_state["mode"] = "new_round_diff"
        with pytest.raises(RectificationError) as review_err:
            appeals.transition(
                "mgr",
                a1["id"],
                expected_status="pending",
                action="approve",
                comment="常规审核应因换轮被拒不少于十字",
            )
        assert review_err.value.status == 409

        # 医生和 qc_staff 无权终结
        for bad_actor in ("doc", "staff"):
            with pytest.raises(RectificationError) as forbidden:
                appeals.close_stale(bad_actor, a1["id"])
            assert forbidden.value.status == 403

        closed1 = appeals.transition(
            "mgr",
            a1["id"],
            expected_status="pending",
            action="supersede",
            comment="质控已重跑产生新轮次，终结旧轮未决申诉",
        )
        assert closed1["status"] == "superseded"
        assert appeals.list("mgr", state="open")["pending_count"] == 0
        assert any(
            item["title"] == "原轮次申诉已因新轮质控终结"
            for item in notifs.list("doc")["items"]
        )

        # 再测 source_loader 抛出 409（真实 current_result 换轮路径）+ 全局 admin close_stale
        round_state["mode"] = "current"
        a2 = appeals.create(
            "doc", rectification_id="task1", reason="第二条申诉原因不少于十个字"
        )
        round_state["mode"] = "new_round_409"
        closed2 = appeals.close_stale("admin", a2["id"])
        assert closed2["status"] == "superseded"
        assert appeals.list("admin", state="open")["pending_count"] == 0
    finally:
        engine.dispose()


def test_p1_c4_case_communication_withdraw_after_new_round_and_historical_envelope(
    monkeypatch,
):
    from app.services import custom_qc_workspace_service

    engine = create_engine(
        "sqlite:///:memory:", execution_options={"schema_translate_map": {"qc": None}}
    )
    try:
        for model in (CaseCommunication, Notification, SysUser, Task, QCAppeal):
            model.__table__.create(engine)
        md = MetaData()
        envelopes = Table(
            "custom_qc_record_result_envelopes",
            md,
            Column("id", String(36), primary_key=True),
            Column("root_job_id", String(36), nullable=False),
            Column("institute_id", String(128), nullable=False),
            Column("patient_id", String(128), nullable=False),
            Column("visit_id", String(128), nullable=False),
        )
        md.create_all(engine)
        monkeypatch.setattr(
            custom_qc_workspace_service,
            "_record_result_envelopes_table",
            lambda: envelopes,
        )

        sessions = sessionmaker(engine)
        with sessions.begin() as s:
            s.add_all(
                [
                    SysUser(
                        id="qc",
                        username="qc",
                        display_name="质控主管",
                        role="qc_manager",
                        institute_id="H1",
                        department="内科",
                        is_active=True,
                    ),
                    SysUser(
                        id="doc",
                        username="doc",
                        display_name="医生",
                        role="doctor",
                        institute_id="H1",
                        department="内科",
                        is_active=True,
                    ),
                ]
            )
            s.execute(
                envelopes.insert(),
                [
                    {
                        "id": "E1",
                        "root_job_id": "J1",
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                    },
                    {
                        "id": "E2",
                        "root_job_id": "J2",
                        "institute_id": "H1",
                        "patient_id": "P1",
                        "visit_id": "V1",
                    },
                ],
            )

        round1 = dict(
            institute_id="H1",
            patient_id="P1",
            visit_id="V1",
            scene="running",
            root_job_id="J1",
            envelope_id="E1",
            rule_set_key="K1",
            rule_set_version="1",
        )
        latest_round = {"active": round1}

        def loader(session, data, *, candidate=False):
            if (
                data["root_job_id"] != latest_round["active"]["root_job_id"]
                or data.get("envelope_id") != latest_round["active"]["envelope_id"]
            ):
                raise RectificationError("当前保存结果已变化或不可用，请刷新", 409)
            return deepcopy(latest_round["active"])

        svc = CaseCommunicationService(
            sessions,
            source=loader,
            department=lambda s, i: "内科",
            envelope_verifier=lambda s, d: verify_historical_envelope(
                s,
                (d["institute_id"], d["patient_id"], d["visit_id"]),
                d["root_job_id"],
                d["envelope_id"],
            ),
        )

        urge = svc.create(
            "qc",
            {
                **round1,
                "action": "urge",
                "recipient_id": "doc",
                "content": "首轮催办请及时修改",
                "request_id": str(uuid4()),
            },
        )

        # 自动质控重跑后最新轮次变为 (J2, E2)
        latest_round["active"] = {**round1, "root_job_id": "J2", "envelope_id": "E2"}

        # 旧轮次发新催办仍必须 409
        with pytest.raises(RectificationError) as new_urge_err:
            svc.create(
                "qc",
                {
                    **round1,
                    "action": "urge",
                    "recipient_id": "doc",
                    "content": "旧轮次新催办应拒绝",
                    "request_id": str(uuid4()),
                },
            )
        assert new_urge_err.value.status == 409

        # 撤回旧轮次催办：只校验原 envelope 与催办归属，不要求原轮次为最新轮次
        withdrawn = svc.create(
            "qc",
            {
                **round1,
                "action": "withdraw",
                "recipient_id": "doc",
                "related_event_id": urge["id"],
                "content": "新轮质控已更新，撤回旧轮催办",
                "request_id": str(uuid4()),
            },
        )
        assert withdrawn["action"] == "withdraw"
        assert withdrawn["related_event_id"] == urge["id"]
        assert svc.detail("doc", urge["id"])["withdrawn"] is True

        # 直接验证 verify_historical_envelope 归属校验
        with sessions() as s:
            assert verify_historical_envelope(s, ("H1", "P1", "V1"), "J1", "E1") == "E1"
            with pytest.raises(RectificationError) as bad_env:
                verify_historical_envelope(s, ("H2", "P1", "V1"), "J1", "E1")
            assert bad_env.value.status == 409
    finally:
        engine.dispose()


# ==================== P2-C1 + P2-C3 ====================


def test_p2_c1_overview_shanghai_day_bounds_covers_00_to_08_cst(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    try:
        for model in (Task, QCAppeal, Notification, SysUser):
            model.__table__.create(engine)
        sessions = sessionmaker(engine)
        with sessions.begin() as s:
            s.add(
                SysUser(
                    id="u1",
                    username="u1",
                    display_name="质控员",
                    role="qc_staff",
                    institute_id="H1",
                    department="内科",
                    is_active=True,
                )
            )
            # 2026-03-23 东八区日界 = [2026-03-22 16:00:00 UTC, 2026-03-23 16:00:00 UTC)
            s.add_all(
                [
                    Notification(
                        id="n-prev",
                        type="system",
                        title="前一天23:59:59",
                        content="应被排除",
                        record_id="R-PREV",
                        severity="info",
                        recipient_id="u1",
                        is_read=False,
                        created_at=datetime(2026, 3, 22, 15, 59, 59),
                    ),
                    Notification(
                        id="n-early-cst",
                        type="system",
                        title="当日00:30:00东八区",
                        content="凌晨00-08跨日窗口应被统计",
                        record_id="R-EARLY",
                        severity="warning",
                        recipient_id="u1",
                        is_read=False,
                        created_at=datetime(2026, 3, 22, 16, 30, 0),
                    ),
                    Notification(
                        id="n-night-cst",
                        type="system",
                        title="当日23:59:59东八区",
                        content="当日末尾应被统计",
                        record_id="R-NIGHT",
                        severity="info",
                        recipient_id="u1",
                        is_read=False,
                        created_at=datetime(2026, 3, 23, 15, 59, 59),
                    ),
                    Notification(
                        id="n-next",
                        type="system",
                        title="次日00:00:00东八区",
                        content="应被排除",
                        record_id="R-NEXT",
                        severity="info",
                        recipient_id="u1",
                        is_read=False,
                        created_at=datetime(2026, 3, 23, 16, 0, 0),
                    ),
                ]
            )

        svc = DoctorNotificationService(sessions)
        monkeypatch.setattr(notifications_router, "service", svc)

        app = FastAPI()
        app.include_router(notifications_router.router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "u1"}
        client = TestClient(app)

        resp = client.get("/api/v1/notifications/overview?date=2026-03-23")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["date"] == "2026-03-23"
        record_ids = {item["record_id"] for item in body["data"]["items"]}
        assert record_ids == {"R-EARLY", "R-NIGHT"}
    finally:
        engine.dispose()


def test_p2_c3_qc_batch_summary_role_guard_and_concurrent_atomic_upsert(
    tmp_path, monkeypatch
):
    db_file = tmp_path / "batch_summary_atomic.sqlite"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"qc": None}},
    )
    try:
        for model in (Task, QCAppeal, Notification, SysUser):
            model.__table__.create(engine)
        sessions = sessionmaker(engine)
        with sessions.begin() as s:
            s.add_all(
                [
                    SysUser(
                        id="doc1",
                        username="doc1",
                        display_name="医生",
                        role="doctor",
                        institute_id="H1",
                        department="内科",
                        is_active=True,
                    ),
                    SysUser(
                        id="staff1",
                        username="staff1",
                        display_name="质控员",
                        role="qc_staff",
                        institute_id="H1",
                        department="质控科",
                        is_active=True,
                    ),
                ]
            )

        svc = DoctorNotificationService(sessions)
        monkeypatch.setattr(notifications_router, "service", svc)

        app = FastAPI()
        app.include_router(notifications_router.router)
        current = {"id": "doc1"}
        app.dependency_overrides[get_current_user] = lambda: dict(current)
        client = TestClient(app)

        payload = {
            "workflow_type": "coding_qc",
            "date": "2026-03-23",
            "total_count": 10,
            "success_count": 9,
            "failed_count": 1,
            "high_risk_count": 2,
        }

        # 医生角色禁止写入批量汇总
        denied = client.post("/api/v1/notifications/qc-batch-summary", json=payload)
        assert denied.status_code == 403

        # 质控人员首次创建 + 二次更新原子 upsert，保留原 created_at
        current["id"] = "staff1"
        r1 = client.post("/api/v1/notifications/qc-batch-summary", json=payload)
        assert r1.status_code == 200
        d1 = r1.json()["data"]
        assert d1["created"] is True and d1["updated"] is False

        with sessions() as s:
            first_created_at = s.get(Notification, d1["id"]).created_at

        r2 = client.post(
            "/api/v1/notifications/qc-batch-summary",
            json={**payload, "total_count": 12, "success_count": 12, "failed_count": 0},
        )
        assert r2.status_code == 200
        d2 = r2.json()["data"]
        assert d2["id"] == d1["id"]
        assert d2["created"] is False and d2["updated"] is True

        # 并发 upsert 绝不重复插入或抛 500
        def _worker(n: int):
            return notifications_router._upsert_qc_batch_summary_owned(
                "staff1",
                workflow_type="coding_qc",
                summary_date="2026-03-23",
                notif_type="coding_qc_batch_summary",
                title="2026-03-23 编码质控批量汇总",
                content=f"并发批次 {n}",
                record_id="batch_summary::coding_qc::2026-03-23",
                severity="info",
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(_worker, range(4)))
        assert all(item["id"] == d1["id"] for item in results)

        with sessions() as s:
            rows = s.scalars(select(Notification)).all()
            assert len(rows) == 1
            assert rows[0].created_at == first_created_at
    finally:
        engine.dispose()


def test_p2_c3_rectification_submit_loads_cdm_outside_lock_and_maps_value_error_to_422(
    monkeypatch,
):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    try:
        Task.__table__.create(engine)
        TaskEvent.__table__.create(engine)
        sessions = sessionmaker(engine)

        people = {
            "qc": {
                "id": "qc",
                "name": "质控员",
                "roles": {"qc_manager"},
                "institute_id": "H1",
                "department": "内科",
            },
            "doc": {
                "id": "doc",
                "name": "医生",
                "roles": {"doctor"},
                "institute_id": "H1",
                "department": "内科",
            },
        }
        data = {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "scene": "running",
            "target_kind": "canonical_defect",
            "target_id": "LX0609-001",
            "root_job_id": "job1",
            "envelope_id": "env1",
            "assignee_id": "doc",
            "requirement": "请补充入院记录并提交整改说明",
        }
        timeline: list[str] = []

        def tracked_loader(**identity):
            timeline.append("load_cdm")
            return _doc_payload("提交后正文")

        svc = DefectRectificationService(
            sessions,
            source_loader=lambda s, req: {
                k: v for k, v in req.items() if k not in {"requirement", "assignee_id"}
            }
            | {"rule_set_key": "LX0609", "rule_set_version": "v1", "_dispatchable": True},
            department_loader=lambda s, i: "内科",
            person_loader=lambda s, uid: deepcopy(people[uid]),
            notification_writer=lambda *args, **kwargs: None,
            document_loader=tracked_loader,
        )

        created = svc.create("qc", data)
        timeline.clear()

        def before_exec(conn, cursor, statement, parameters, context, many):
            upper = statement.strip().upper()
            if upper.startswith("UPDATE"):
                timeline.append("update_task")

        orig_with_for_update = sa.sql.selectable.Select.with_for_update

        def spy_for_update(self, *args, **kwargs):
            timeline.append("select_for_update")
            return orig_with_for_update(self, *args, **kwargs)

        event.listen(engine, "before_cursor_execute", before_exec)
        monkeypatch.setattr(sa.sql.selectable.Select, "with_for_update", spy_for_update)
        try:
            submitted = svc.transition(
                "doc",
                created["id"],
                version=1,
                action="submit",
                comment="已完成整改并提交完整文书说明",
            )
        finally:
            event.remove(engine, "before_cursor_execute", before_exec)

        assert submitted["status"] == "submitted"
        # CDM 文书拉取必须先于 FOR UPDATE 行锁与 UPDATE
        assert timeline.index("load_cdm") < timeline.index("select_for_update")
        assert timeline.index("select_for_update") < timeline.index("update_task")

        # 业务校验 ValueError（例如文书为空/截断）映射为 422 而非 503
        svc.transition(
            "qc",
            created["id"],
            version=2,
            action="reject",
            comment="请重新提交以便验证错误码映射",
        )
        svc.document_loader = lambda **identity: {
            "documents": [],
            "domain_projection": {
                "domains": {
                    "admission": {"per_source": {"admission_record": {"has_more": False}}}
                }
            },
        }
        with pytest.raises(RectificationError) as err:
            svc.transition(
                "doc",
                created["id"],
                version=3,
                action="submit",
                comment="尝试在文书为空时提交整改说明",
            )
        assert err.value.status == 422

        # 经由 FastAPI 路由返回 422 而非 503
        monkeypatch.setattr(rectification_router, "service", svc)
        app = FastAPI()
        app.include_router(rectification_router.router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "doc"}
        client = TestClient(app)
        resp = client.post(
            f"/api/v1/defect-rectifications/{created['id']}/actions",
            json={
                "version": 3,
                "action": "submit",
                "comment": "通过接口提交但文书为空应返回422",
            },
        )
        assert resp.status_code == 422
    finally:
        engine.dispose()
