"""Offline regression tests for Wave 1 legacy workflow fixes:
- P0-6: defects.py (manual defect exclusion, RBAC, institute scope, state machine CAS, SQLi)
- P0-7 + P2-C2: appeals.py, remediation.py, qc_views.sql (trace_id response, UUID PK, RBAC, no self-review, CAS, overdue datetime, view filter)
- P1-B2 + P2-A3: tasks.py (creator_id=id, tab=created, institute/creator isolation, re-analyze final status)
- P1-B2 + P1-D1 + P1-D3 + P2-B1: qc.py (role+institute scope, 3-key + cdm.mr_diagnosis + 503 on DB error, pre-send privacy redaction)
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.security import get_current_user
from app.core.supabase_client import _PgClient
from app.database import connection as db_connection
from app.database.models.cdm import (
    Diagnosis,
    MedicalRecordFrontpage,
    MrCost,
    MrSurgery,
)
from app.database.models.qc import (
    QCRemediationHistory,
    QCRemediationTask,
    QCTask as QCTaskLegacy,
    QCTaskRecord as QCTaskRecordLegacy,
)
from app.database.models.v36_reports import (
    QCAppeal,
    QCAppealReview,
    QCDefect,
    QCDefectHistory,
    QCResultBiz,
    SysUser,
)
from app.routers import appeals as appeals_router
from app.routers import defects as defects_router
from app.routers import qc as qc_router
from app.routers import remediation as remediation_router
from app.routers import tasks as tasks_router
from app.services.coding_qc_service import CodingQCEngine
from app.services.luxian_0609.privacy_request_scope import (
    is_luxian_0609_privacy_scope_active,
    protect_current_payload,
)


def _create_test_db(tmp_path: Path):
    db_file = tmp_path / f"legacy_workflow_{uuid.uuid4().hex[:8]}.sqlite"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create tables with full columns (v36_reports + legacy remediation/tasks + cdm)
    for table in (
        SysUser.__table__,
        QCResultBiz.__table__,
        QCDefect.__table__,
        QCDefectHistory.__table__,
        QCAppeal.__table__,
        QCAppealReview.__table__,
        QCRemediationTask.__table__,
        QCRemediationHistory.__table__,
        QCTaskLegacy.__table__,
        QCTaskRecordLegacy.__table__,
        MedicalRecordFrontpage.__table__,
        Diagnosis.__table__,
        MrSurgery.__table__,
        MrCost.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    # Extra tables used by legacy appeals/remediation/coding-qc/tasks
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS medical_records (
                    id VARCHAR(64) PRIMARY KEY,
                    institute_id VARCHAR(128),
                    patient_id VARCHAR(128),
                    visit_id VARCHAR(128)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS mr_diagnosis (
                    diagnosis_id VARCHAR(64) PRIMARY KEY,
                    institute_id VARCHAR(128),
                    patient_id VARCHAR(128),
                    visit_id VARCHAR(128),
                    diagnosis_code VARCHAR(64),
                    diagnosis_name VARCHAR(200),
                    diagnosis_type VARCHAR(64),
                    diagnosis_no VARCHAR(32),
                    diagnosis_main VARCHAR(16),
                    admission_condition VARCHAR(64),
                    is_deleted VARCHAR(8) DEFAULT '0'
                )
                """
            )
        )
        # Apply compatible views from qc_views.sql (including qc_appeals_statistics & v_qc_task_progress)
        views_sql = (
            Path(__file__).resolve().parents[2]
            / "app"
            / "database"
            / "sql"
            / "qc_views.sql"
        ).read_text(encoding="utf-8")
        for stmt in views_sql.split(";"):
            stmt = stmt.strip()
            if not stmt or "::numeric" in stmt or "FILTER (" in stmt:
                continue
            conn.execute(text(stmt))

    # Seed persistent users across two institutes + global admin
    now = datetime.utcnow()
    users = [
        SysUser(
            id="u-admin",
            username="admin_u",
            email="admin_u@example.com",
            display_name="Global Admin",
            institute_id=None,
            department="信息科",
            role="admin",
            roles_json=json.dumps(["admin"]),
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        SysUser(
            id="u-mgr-a",
            username="mgr_a",
            email="mgr_a@example.com",
            display_name="Manager A",
            institute_id="HOSP-A",
            department="质控科",
            role="qc_manager",
            roles_json=json.dumps(["qc_manager"]),
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        SysUser(
            id="u-mgr-a2",
            username="mgr_a2",
            email="mgr_a2@example.com",
            display_name="Manager A2",
            institute_id="HOSP-A",
            department="质控科",
            role="qc_manager",
            roles_json=json.dumps(["qc_manager"]),
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        SysUser(
            id="u-staff-a",
            username="staff_a",
            email="staff_a@example.com",
            display_name="Staff A",
            institute_id="HOSP-A",
            department="质控科",
            role="qc_staff",
            roles_json=json.dumps(["qc_staff"]),
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        SysUser(
            id="u-staff-a2",
            username="staff_a2",
            email="staff_a2@example.com",
            display_name="Staff A2",
            institute_id="HOSP-A",
            department="质控科",
            role="qc_staff",
            roles_json=json.dumps(["qc_staff"]),
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        SysUser(
            id="u-doc-a",
            username="doc_a",
            email="doc_a@example.com",
            display_name="Doctor A",
            institute_id="HOSP-A",
            department="心内科",
            role="doctor",
            roles_json=json.dumps(["doctor"]),
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        SysUser(
            id="u-mgr-b",
            username="mgr_b",
            email="mgr_b@example.com",
            display_name="Manager B",
            institute_id="HOSP-B",
            department="质控科",
            role="qc_manager",
            roles_json=json.dumps(["qc_manager"]),
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
        SysUser(
            id="u-doc-b",
            username="doc_b",
            email="doc_b@example.com",
            display_name="Doctor B",
            institute_id="HOSP-B",
            department="外科",
            role="doctor",
            roles_json=json.dumps(["doctor"]),
            is_active=True,
            created_at=now,
            updated_at=now,
        ),
    ]
    with session_factory() as s:
        s.add_all(users)
        s.commit()

    return engine, session_factory


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine, session_factory = _create_test_db(tmp_path)
    pg_client = _PgClient(session_factory)

    monkeypatch.setattr(db_connection, "engine", engine)
    monkeypatch.setattr(db_connection, "SessionLocal", session_factory)
    monkeypatch.setattr(tasks_router, "get_supabase", lambda: pg_client)
    monkeypatch.setattr(qc_router, "get_supabase", lambda: pg_client)
    monkeypatch.setattr(defects_router, "get_supabase", lambda: pg_client)
    monkeypatch.setattr(appeals_router, "get_supabase", lambda: pg_client)
    monkeypatch.setattr(remediation_router, "get_supabase", lambda: pg_client)

    active_user = {"value": {"id": "u-admin", "roles": ["admin"], "display_name": "Global Admin"}}

    app = FastAPI()
    app.include_router(defects_router.router)
    app.include_router(appeals_router.router)
    app.include_router(remediation_router.router)
    app.include_router(tasks_router.router)
    app.include_router(qc_router.router)
    app.dependency_overrides[get_current_user] = lambda: active_user["value"]

    client = TestClient(app)

    def set_user(uid: str, role: str, name: str = ""):
        active_user["value"] = {
            "id": uid,
            "roles": [role],
            "role": role,
            "display_name": name or uid,
            "email": f"{uid}@example.com",
        }

    try:
        yield {
            "client": client,
            "engine": engine,
            "session_factory": session_factory,
            "set_user": set_user,
        }
    finally:
        engine.dispose()


# =====================================================================
# 1. P0-6: defects.py
# =====================================================================


def test_defects_excludes_manual_defects_across_read_stats_export_and_writes(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]
    now = datetime.utcnow()

    with sf() as s:
        s.add_all(
            [
                QCDefect(
                    id="def-auto-a",
                    record_id="rec-a1",
                    institute_id="HOSP-A",
                    department="心内科",
                    rule_name="自动规则A",
                    description="自动缺陷描述",
                    severity="error",
                    category="core",
                    status="pending",
                    origin="auto",
                    created_at=now,
                    updated_at=now,
                ),
                QCDefect(
                    id="def-null-a",
                    record_id="rec-a2",
                    institute_id="HOSP-A",
                    department="心内科",
                    rule_name="旧规则无origin",
                    description="兼容历史NULL origin",
                    severity="warning",
                    category="other",
                    status="pending",
                    origin=None,
                    created_at=now,
                    updated_at=now,
                ),
                QCDefect(
                    id="def-manual-a",
                    record_id="rec-a3",
                    institute_id="HOSP-A",
                    department="心内科",
                    rule_name="人工复核缺陷",
                    description="现代人工缺陷",
                    severity="error",
                    category="manual",
                    status="pending",
                    origin="manual",
                    manual_review_status="approved",
                    created_at=now,
                    updated_at=now,
                ),
                QCDefect(
                    id="def-auto-b",
                    record_id="rec-b1",
                    institute_id="HOSP-B",
                    department="外科",
                    rule_name="他院自动缺陷",
                    description="B院区缺陷",
                    severity="error",
                    category="core",
                    status="pending",
                    origin="auto",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        s.commit()

    # Manager A sees HOSP-A auto + NULL origin, NEVER manual and NEVER HOSP-B
    set_user("u-mgr-a", "qc_manager", "Manager A")
    list_resp = client.get("/api/v1/qc/defects")
    assert list_resp.status_code == 200
    ids = {item["id"] for item in list_resp.json()["data"]["items"]}
    assert ids == {"def-auto-a", "def-null-a"}

    # Stats also excludes manual & HOSP-B
    stats_resp = client.get("/api/v1/qc/defects/stats")
    assert stats_resp.status_code == 200
    assert stats_resp.json()["data"]["total"] == 2

    # SQL injection payload in keyword cannot bypass manual/institute filter
    sqli_resp = client.get(
        "/api/v1/qc/defects",
        params={"keyword": 'x,id" IS NOT NULL OR 1=1 OR "id.eq.1'},
    )
    assert sqli_resp.status_code == 200
    assert sqli_resp.json()["data"]["items"] == []

    # Export CSV excludes manual & HOSP-B
    exp_resp = client.get("/api/v1/qc/defects/export", params={"format": "csv"})
    assert exp_resp.status_code == 200
    csv_text = exp_resp.content.decode("utf-8-sig")
    assert "自动规则A" in csv_text
    assert "旧规则无origin" in csv_text
    assert "人工复核缺陷" not in csv_text
    assert "他院自动缺陷" not in csv_text

    # Cleanup downloaded file
    downloads_dir = Path(__file__).resolve().parents[2] / "downloads"
    if downloads_dir.exists():
        for f in downloads_dir.glob("缺陷列表_*.csv"):
            try:
                f.unlink()
            except OSError:
                pass

    # All mutation endpoints reject origin='manual' with 409 and never alter status
    assert client.post("/api/v1/qc/defects/def-manual-a/urge", json={"message": "催办"}).status_code == 409
    assert client.post("/api/v1/qc/defects/def-manual-a/cancel-urge", json={"reason": "撤回"}).status_code == 409
    assert (
        client.post(
            "/api/v1/qc/defects/def-manual-a/mark-remediated",
            json={"remediation_note": "已改"},
        ).status_code
        == 409
    )
    assert client.post("/api/v1/qc/defects/def-manual-a/approve", json={"comment": "通过"}).status_code == 409
    assert client.post("/api/v1/qc/defects/def-manual-a/reject", json={"reason": "退回"}).status_code == 409

    batch_resp = client.post(
        "/api/v1/qc/defects/batch-action",
        json={"defect_ids": ["def-manual-a", "def-auto-b"], "action": "urge", "message": "批量催办"},
    )
    assert batch_resp.status_code == 200
    assert batch_resp.json()["data"]["success_count"] == 0
    assert batch_resp.json()["data"]["fail_count"] == 2

    with sf() as s:
        manual = s.execute(text("SELECT status FROM qc_defects WHERE id='def-manual-a'")).scalar_one()
        other_hosp = s.execute(text("SELECT status FROM qc_defects WHERE id='def-auto-b'")).scalar_one()
        assert manual == "pending"
        assert other_hosp == "pending"


def test_defects_rbac_state_machine_cas_and_terminal_protection(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]
    now = datetime.utcnow()

    with sf() as s:
        s.add(
            QCDefect(
                id="def-flow-1",
                record_id="rec-f1",
                institute_id="HOSP-A",
                department="心内科",
                rule_name="流程测试缺陷",
                description="描述",
                severity="error",
                category="core",
                status="pending",
                origin="auto",
                created_at=now,
                updated_at=now,
            )
        )
        s.commit()

    # qc_staff cannot approve, reject, export, or batch approve
    set_user("u-staff-a", "qc_staff", "Staff A")
    assert client.get("/api/v1/qc/defects/export").status_code == 403
    assert client.post("/api/v1/qc/defects/def-flow-1/approve", json={}).status_code == 403
    assert client.post("/api/v1/qc/defects/def-flow-1/reject", json={"reason": "x"}).status_code == 403
    assert (
        client.post(
            "/api/v1/qc/defects/batch-action",
            json={"defect_ids": ["def-flow-1"], "action": "approve"},
        ).status_code
        == 403
    )

    # Illegal transitions blocked: cannot cancel-urge from pending, cannot approve from pending
    assert client.post("/api/v1/qc/defects/def-flow-1/cancel-urge", json={}).status_code == 409
    set_user("u-mgr-a", "qc_manager", "Manager A")
    assert client.post("/api/v1/qc/defects/def-flow-1/approve", json={}).status_code == 409

    # Valid transitions: pending -> urged -> pending -> remediated
    set_user("u-staff-a", "qc_staff", "Staff A")
    assert client.post("/api/v1/qc/defects/def-flow-1/urge", json={"message": "请整改"}).status_code == 200
    assert client.post("/api/v1/qc/defects/def-flow-1/cancel-urge", json={"reason": "撤回"}).status_code == 200
    assert (
        client.post(
            "/api/v1/qc/defects/def-flow-1/mark-remediated",
            json={"remediation_note": "已完善病程记录", "evidence": ["doc1.pdf"]},
        ).status_code
        == 200
    )

    # Cross-institute manager B cannot approve HOSP-A defect
    set_user("u-mgr-b", "qc_manager", "Manager B")
    assert client.post("/api/v1/qc/defects/def-flow-1/approve", json={"comment": "ok"}).status_code == 403

    # Same-institute manager A approves remediated -> approved
    set_user("u-mgr-a", "qc_manager", "Manager A")
    approve_resp = client.post("/api/v1/qc/defects/def-flow-1/approve", json={"comment": "核验通过"})
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["new_status"] == "approved"

    # Terminal state protection: approved cannot be cancelled, rejected, urged, or re-remediated
    assert client.post("/api/v1/qc/defects/def-flow-1/cancel-urge", json={}).status_code == 409
    assert client.post("/api/v1/qc/defects/def-flow-1/reject", json={"reason": "覆写"}).status_code == 409
    assert client.post("/api/v1/qc/defects/def-flow-1/urge", json={"message": "覆写"}).status_code == 409
    assert (
        client.post(
            "/api/v1/qc/defects/def-flow-1/mark-remediated",
            json={"remediation_note": "覆写"},
        ).status_code
        == 409
    )

    with sf() as s:
        row = s.execute(text("SELECT status, approved_by FROM qc_defects WHERE id='def-flow-1'")).mappings().one()
        assert row["status"] == "approved"
        assert row["approved_by"] == "u-mgr-a"
        hist_cnt = s.execute(text("SELECT COUNT(*) FROM qc_defect_history WHERE defect_id='def-flow-1'")).scalar_one()
        assert hist_cnt == 4


# =====================================================================
# 2. P0-7 + P2-C2: appeals.py, remediation.py, qc_views.sql
# =====================================================================


def test_appeals_lifecycle_uuid_rbac_self_review_terminal_cas_and_views(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]
    now = datetime.utcnow()

    qc_res_a = str(uuid.uuid4())
    rec_a = str(uuid.uuid4())
    qc_res_b = str(uuid.uuid4())
    rec_b = str(uuid.uuid4())

    with sf() as s:
        s.add_all(
            [
                QCResultBiz(
                    id=qc_res_a,
                    record_id=rec_a,
                    institute_id="HOSP-A",
                    overall_score=82.0,
                    grade="B",
                    defect_count=1,
                    created_at=now,
                    updated_at=now,
                ),
                QCResultBiz(
                    id=qc_res_b,
                    record_id=rec_b,
                    institute_id="HOSP-B",
                    overall_score=85.0,
                    grade="B",
                    defect_count=1,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        s.execute(
            text("INSERT INTO medical_records (id, institute_id, patient_id, visit_id) VALUES (:id, :inst, :pid, :vid)"),
            [
                {"id": rec_a, "inst": "HOSP-A", "pid": "PA1", "vid": "VA1"},
                {"id": rec_b, "inst": "HOSP-B", "pid": "PB1", "vid": "VB1"},
            ],
        )
        # Also insert a modern appeal row (qc_result_id=NULL, record_id=NULL) to verify view & stats isolation
        s.add(
            QCAppeal(
                id="mod-appeal-1",
                appeal_number="MOD-001",
                qc_result_id=None,
                record_id=None,
                appeal_type="defect",
                reason="现代申诉数据用于验证视图隔离",
                priority="high",
                appellant_id="u-doc-a",
                appellant_name="Doctor A",
                status="pending",
                target_kind="canonical_defect",
                target_id="R001",
                institute_id="HOSP-A",
                patient_id="PA1",
                visit_id="VA1",
                scene="final",
                root_job_id="job-1",
                envelope_id="env-1",
                rule_set_key="luxian_0609_qc_v1",
                rule_set_version="v1",
                case_department="心内科",
                created_at=now,
                updated_at=now,
            )
        )
        s.commit()

    # Doctor A cannot file appeal for HOSP-B
    set_user("u-doc-a", "doctor", "Doctor A")
    cross_create = client.post(
        "/api/v1/appeals",
        json={
            "qc_result_id": qc_res_b,
            "record_id": rec_b,
            "appeal_type": "defect",
            "reason": "跨院申诉测试理由不少于十个字符",
            "priority": "medium",
        },
    )
    assert cross_create.status_code == 403

    # Doctor A creates legacy appeal in HOSP-A -> 200 (no success_response(request=...) 500, UUID PK assigned)
    create_resp = client.post(
        "/api/v1/appeals",
        json={
            "qc_result_id": qc_res_a,
            "record_id": rec_a,
            "appeal_type": "defect",
            "defect_item": "首次病程记录",
            "reason": "患者已按规范补录相关记录请复核",
            "priority": "high",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    body = create_resp.json()
    assert body["success"] is True
    assert body.get("trace_id")
    appeal_id = body["data"]["id"]
    assert uuid.UUID(appeal_id)

    # SQL view qc_appeals_statistics MUST exclude modern appeal row
    with sf() as s:
        view_total = s.execute(text("SELECT COALESCE(SUM(count), 0) FROM qc_appeals_statistics")).scalar_one()
        assert view_total == 1

    # Doctor A cannot self-review
    assert (
        client.post(
            f"/api/v1/appeals/{appeal_id}/review",
            json={"action": "approve", "comment": "自审通过"},
        ).status_code
        == 403
    )

    # qc_staff cannot review
    set_user("u-staff-a", "qc_staff", "Staff A")
    assert (
        client.post(
            f"/api/v1/appeals/{appeal_id}/review",
            json={"action": "approve", "comment": "专员越权审核"},
        ).status_code
        == 403
    )

    # Manager B (HOSP-B) cannot read or review HOSP-A appeal
    set_user("u-mgr-b", "qc_manager", "Manager B")
    assert client.get(f"/api/v1/appeals/{appeal_id}").status_code == 403
    assert (
        client.post(
            f"/api/v1/appeals/{appeal_id}/review",
            json={"action": "approve", "comment": "跨院审核"},
        ).status_code
        == 403
    )

    # Manager A approves HOSP-A appeal -> 200, review record inserted with UUID id
    set_user("u-mgr-a", "qc_manager", "Manager A")
    review_resp = client.post(
        f"/api/v1/appeals/{appeal_id}/review",
        json={"action": "approve", "comment": "核查属实予以通过", "resolution": "撤销扣分"},
    )
    assert review_resp.status_code == 200, review_resp.text
    assert review_resp.json()["data"]["status"] == "approved"

    # Terminal protection: cannot flip approved -> rejected or withdraw
    flip_resp = client.post(
        f"/api/v1/appeals/{appeal_id}/review",
        json={"action": "reject", "comment": "尝试覆写终态"},
    )
    assert flip_resp.status_code == 409

    set_user("u-doc-a", "doctor", "Doctor A")
    assert client.post(f"/api/v1/appeals/{appeal_id}/withdraw", json={"reason": "撤回"}).status_code == 409

    # Verify manager cannot self-review own appeal
    set_user("u-mgr-a", "qc_manager", "Manager A")
    self_create = client.post(
        "/api/v1/appeals",
        json={
            "qc_result_id": qc_res_a,
            "record_id": rec_a,
            "appeal_type": "score",
            "reason": "质控主管自己发起的申诉理由十字符以上",
            "priority": "medium",
        },
    )
    assert self_create.status_code == 200
    self_appeal_id = self_create.json()["data"]["id"]
    assert (
        client.post(
            f"/api/v1/appeals/{self_appeal_id}/review",
            json={"action": "approve", "comment": "自审"},
        ).status_code
        == 403
    )

    # Statistics summary excludes modern appeal and honors date filters
    stats_resp = client.get("/api/v1/appeals/statistics/summary")
    assert stats_resp.status_code == 200
    assert stats_resp.json()["data"]["total"] == 2
    future_stats = client.get(
        "/api/v1/appeals/statistics/summary",
        params={"start_date": (now + timedelta(days=2)).isoformat()},
    )
    assert future_stats.status_code == 200
    assert future_stats.json()["data"]["total"] == 0


def test_remediation_lifecycle_rbac_self_review_cas_and_overdue_datetime(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]
    now = datetime.utcnow()

    qc_res_a = str(uuid.uuid4())
    rec_a = str(uuid.uuid4())
    assignee_doc_a = str(uuid.uuid4())
    mgr_a_uuid = str(uuid.uuid4())

    # Add UUID-formatted users for RemediationTaskCreate UUID4 schema
    with sf() as s:
        s.add_all(
            [
                SysUser(
                    id=assignee_doc_a,
                    username="doc_a_uuid",
                    email="doc_a_uuid@example.com",
                    display_name="Doctor A UUID",
                    institute_id="HOSP-A",
                    department="心内科",
                    role="doctor",
                    roles_json=json.dumps(["doctor"]),
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                SysUser(
                    id=mgr_a_uuid,
                    username="mgr_a_uuid",
                    email="mgr_a_uuid@example.com",
                    display_name="Manager A UUID",
                    institute_id="HOSP-A",
                    department="质控科",
                    role="qc_manager",
                    roles_json=json.dumps(["qc_manager"]),
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                QCResultBiz(
                    id=qc_res_a,
                    record_id=rec_a,
                    institute_id="HOSP-A",
                    overall_score=76.0,
                    grade="C",
                    defect_count=2,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        s.execute(
            text("INSERT INTO medical_records (id, institute_id, patient_id, visit_id) VALUES (:id, :inst, :pid, :vid)"),
            {"id": rec_a, "inst": "HOSP-A", "pid": "PA1", "vid": "VA1"},
        )
        s.commit()

    payload = {
        "qc_result_id": qc_res_a,
        "record_id": rec_a,
        "defect_type": "completeness",
        "defect_description": "入院记录缺少关键体格检查项说明",
        "severity": "high",
        "remediation_requirement": "请补充完整心肺查体记录并签名确认",
        "deadline": (now - timedelta(days=3)).isoformat() + "Z",
        "assignee_id": assignee_doc_a,
        "assignee_name": "Doctor A UUID",
        "assignee_department": "心内科",
    }

    # Doctor cannot create remediation task
    set_user(assignee_doc_a, "doctor", "Doctor A UUID")
    assert client.post("/api/v1/remediation", json=payload).status_code == 403

    # Manager A creates remediation task -> 200 (no success_response(request=...) 500, UUID PK assigned)
    set_user("u-mgr-a", "qc_manager", "Manager A")
    create_resp = client.post("/api/v1/remediation", json=payload)
    assert create_resp.status_code == 200, create_resp.text
    task_id = create_resp.json()["data"]["id"]
    assert uuid.UUID(task_id)

    # P2-C2: overdue endpoint handles PG datetime & aware/naive ISO strings without TypeError
    assert remediation_router._to_utc_naive(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)) == datetime(2026, 1, 1, 12, 0)
    assert remediation_router._to_utc_naive("2026-01-01T12:00:00Z") == datetime(2026, 1, 1, 12, 0)
    assert remediation_router._to_utc_naive(datetime(2026, 1, 1, 12, 0)) == datetime(2026, 1, 1, 12, 0)

    overdue_resp = client.get("/api/v1/remediation/statistics/overdue")
    assert overdue_resp.status_code == 200, overdue_resp.text
    overdue_items = overdue_resp.json()["data"]
    assert len(overdue_items) == 1
    assert overdue_items[0]["task_id"] == task_id
    assert overdue_items[0]["overdue_days"] >= 2

    # Doctor cannot update, close, or review task
    set_user(assignee_doc_a, "doctor", "Doctor A UUID")
    assert client.put(f"/api/v1/remediation/{task_id}", json={"notes": "篡改"}).status_code == 403
    assert client.post(f"/api/v1/remediation/{task_id}/close", json={"reason": "自关"}).status_code == 403

    # Doctor submits remediation -> 200
    sub_resp = client.post(
        f"/api/v1/remediation/{task_id}/submit",
        json={"remediation_description": "已补充完整心肺查体记录并完成主治医师签名", "remediation_evidence": []},
    )
    assert sub_resp.status_code == 200, sub_resp.text
    assert sub_resp.json()["data"]["status"] == "submitted"

    # Doctor cannot self-approve, qc_staff cannot approve, Manager B (other institute) cannot approve
    assert (
        client.post(
            f"/api/v1/remediation/{task_id}/review",
            json={"action": "approve", "review_comment": "医生尝试自批通过十个字符"},
        ).status_code
        == 403
    )
    set_user("u-staff-a", "qc_staff", "Staff A")
    assert (
        client.post(
            f"/api/v1/remediation/{task_id}/review",
            json={"action": "approve", "review_comment": "专员尝试越权验收十个字符"},
        ).status_code
        == 403
    )
    set_user("u-mgr-b", "qc_manager", "Manager B")
    assert (
        client.post(
            f"/api/v1/remediation/{task_id}/review",
            json={"action": "approve", "review_comment": "他院主管尝试验收十个字符"},
        ).status_code
        == 403
    )

    # Manager A approves -> 200
    set_user("u-mgr-a", "qc_manager", "Manager A")
    rev_resp = client.post(
        f"/api/v1/remediation/{task_id}/review",
        json={"action": "approve", "review_comment": "已核对病历内容符合质控规范"},
    )
    assert rev_resp.status_code == 200, rev_resp.text
    assert rev_resp.json()["data"]["status"] == "approved"

    # Terminal protection: cannot close or re-review an approved task
    assert client.post(f"/api/v1/remediation/{task_id}/close", json={"reason": "覆写终态"}).status_code == 409
    assert (
        client.post(
            f"/api/v1/remediation/{task_id}/review",
            json={"action": "reject", "review_comment": "尝试覆写已通过终态十字符"},
        ).status_code
        == 409
    )

    # Anti-self-review for manager assigned to own task
    self_payload = {**payload, "assignee_id": mgr_a_uuid, "assignee_name": "Manager A UUID"}
    self_task_id = client.post("/api/v1/remediation", json=self_payload).json()["data"]["id"]
    set_user(mgr_a_uuid, "qc_manager", "Manager A UUID")
    assert (
        client.post(
            f"/api/v1/remediation/{self_task_id}/submit",
            json={"remediation_description": "主管本人提交自己负责的整改说明十字符以上", "remediation_evidence": []},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/remediation/{self_task_id}/review",
            json={"action": "approve", "review_comment": "尝试自审自批自己负责任务"},
        ).status_code
        == 403
    )
    assert client.post(f"/api/v1/remediation/{self_task_id}/close", json={"reason": "自关"}).status_code == 403


# =====================================================================
# 3. P1-B2 + P2-A3: tasks.py
# =====================================================================


def test_tasks_creator_id_tab_created_isolation_and_reanalyze_status(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]

    # Staff A creates a task -> creator_id must be persisted from actor["id"]
    set_user("u-staff-a", "qc_staff", "Staff A")
    create_resp = client.post(
        "/api/v1/tasks",
        json={
            "task_name": "心内科抽查任务",
            "task_type": "one_time",
            "sampling_method": "all",
            "assign_method": "keep",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    task_data = create_resp.json()["data"]
    task_id = task_data["id"]
    assert task_data["creator_id"] == "u-staff-a"

    # tab="created" returns the task!
    created_list = client.get("/api/v1/tasks", params={"tab": "created"})
    assert created_list.status_code == 200
    assert [t["id"] for t in created_list.json()["data"]["items"]] == [task_id]

    # Another staff (Staff A2) cannot read/update/cancel/re-analyze Staff A's task
    set_user("u-staff-a2", "qc_staff", "Staff A2")
    assert client.get(f"/api/v1/tasks/{task_id}").status_code == 403
    assert client.put(f"/api/v1/tasks/{task_id}", json={"task_name": "越权改名"}).status_code == 403
    assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 403

    # Manager B (HOSP-B) cannot read, list, update, cancel, or delete HOSP-A's task
    set_user("u-mgr-b", "qc_manager", "Manager B")
    assert client.get("/api/v1/tasks").json()["data"]["items"] == []
    assert client.get(f"/api/v1/tasks/{task_id}").status_code == 403
    assert client.get(f"/api/v1/tasks/{task_id}/progress").status_code == 403
    assert client.delete(f"/api/v1/tasks/{task_id}").status_code == 403

    # Seed 2 task records and verify P2-A3: re-analyze finishes as completed (100%), NOT in_progress (0%)
    now = datetime.utcnow()
    with sf() as s:
        s.add_all(
            [
                QCTaskRecordLegacy(
                    id="tr-re-1",
                    task_id=task_id,
                    record_id="rec-re-1",
                    status="pending",
                    created_at=now,
                ),
                QCTaskRecordLegacy(
                    id="tr-re-2",
                    task_id=task_id,
                    record_id="rec-re-2",
                    status="pending",
                    created_at=now,
                ),
            ]
        )
        s.commit()

    set_user("u-staff-a", "qc_staff", "Staff A")
    with patch(
        "app.services.qc_service.QCService.evaluate",
        new=AsyncMock(return_value={"overall_score": 92, "issues": []}),
    ):
        re_resp = client.post(f"/api/v1/tasks/{task_id}/re-analyze")
    assert re_resp.status_code == 200, re_resp.text
    re_data = re_resp.json()["data"]
    assert re_data["status"] == "completed"
    assert re_data["completed_records"] == 2
    assert re_data["progress"] == 100.0

    with sf() as s:
        row = (
            s.execute(text("SELECT status, completed_records, progress FROM qc_tasks WHERE id=:id"), {"id": task_id})
            .mappings()
            .one()
        )
        assert row["status"] == "completed"
        assert row["completed_records"] == 2
        assert float(row["progress"]) == 100.0

    # Completed task cannot be cancelled (409)
    assert client.post(f"/api/v1/tasks/{task_id}/cancel").status_code == 409


# =====================================================================
# 4. P1-B2 + P1-D1 + P1-D3 + P2-B1: qc.py
# =====================================================================


def test_qc_role_and_institute_isolation(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]
    now = datetime.utcnow()

    with sf() as s:
        s.add_all(
            [
                QCResultBiz(
                    id="qcr-a",
                    record_id="rec-iso-a",
                    institute_id="HOSP-A",
                    overall_score=90.0,
                    grade="A",
                    defect_count=0,
                    raw_output="{}",
                    created_at=now,
                    updated_at=now,
                ),
                QCResultBiz(
                    id="qcr-b",
                    record_id="rec-iso-b",
                    institute_id="HOSP-B",
                    overall_score=80.0,
                    grade="B",
                    defect_count=1,
                    raw_output="{}",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        s.commit()

    # Doctor cannot access history, result, analyze, formal-qc, coding-qc
    set_user("u-doc-a", "doctor", "Doctor A")
    assert client.get("/api/v1/qc/history").status_code == 403
    assert client.get("/api/v1/qc/result/rec-iso-a").status_code == 403
    assert client.post("/api/v1/qc/analyze/rec-iso-a", json={}).status_code == 403
    assert client.post("/api/v1/qc/formal-qc/validate", json={"frontpage": {}}).status_code == 403
    assert client.post("/api/v1/qc/coding-qc/check", json={"frontpage": {}, "skip_llm": True}).status_code == 403

    # Manager A sees ONLY HOSP-A history & result; cannot read HOSP-B or run cross-institute QC
    set_user("u-mgr-a", "qc_manager", "Manager A")
    hist = client.get("/api/v1/qc/history")
    assert hist.status_code == 200
    assert [i["id"] for i in hist.json()["data"]["items"]] == ["qcr-a"]

    assert client.get("/api/v1/qc/result/rec-iso-a").status_code == 200
    assert client.get("/api/v1/qc/result/rec-iso-b").status_code == 404

    assert client.post("/api/v1/qc/analyze/rec-iso-b", json={"institute_id": "HOSP-B"}).status_code == 403
    assert (
        client.post(
            "/api/v1/qc/formal-qc/validate",
            json={"institute_id": "HOSP-B", "frontpage": {}},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/qc/coding-qc/check",
            json={"institute_id": "HOSP-B", "frontpage": {}, "skip_llm": True},
        ).status_code
        == 403
    )


def test_coding_qc_three_key_isolation_cdm_schema_and_503_on_db_error(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]

    # Seed two institutes with the SAME visit_id="V-DUP" and same patient_id="P-1"
    with sf() as s:
        s.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id="HOSP-A",
                    patient_id="P-1",
                    visit_id="V-DUP",
                    sex="男",
                    age_year="45",
                ),
                MedicalRecordFrontpage(
                    institute_id="HOSP-B",
                    patient_id="P-1",
                    visit_id="V-DUP",
                    sex="女",
                    age_year="30",
                ),
                MrSurgery(
                    institute_id="HOSP-A",
                    patient_id="P-1",
                    visit_id="V-DUP",
                    surgery_id="S-A",
                    surgery_code="47.09",
                    surgery_name="阑尾切除术",
                    main_surgery_sign="1",
                ),
                MrSurgery(
                    institute_id="HOSP-B",
                    patient_id="P-1",
                    visit_id="V-DUP",
                    surgery_id="S-B",
                    surgery_code="74.1",
                    surgery_name="剖宫产术",
                    main_surgery_sign="1",
                ),
                MrCost(
                    institute_id="HOSP-A",
                    patient_id="P-1",
                    visit_id="V-DUP",
                    pathological_diagnostic_fee="120.0",
                ),
                MrCost(
                    institute_id="HOSP-B",
                    patient_id="P-1",
                    visit_id="V-DUP",
                    pathological_diagnostic_fee="999.0",
                ),
            ]
        )
        # Put diagnoses in mr_diagnosis fallback table to verify mr_diagnosis 3-key + clinical_table_sql
        s.execute(
            text(
                """
                INSERT INTO mr_diagnosis
                    (diagnosis_id, institute_id, patient_id, visit_id, diagnosis_code, diagnosis_name, diagnosis_type, diagnosis_no, diagnosis_main, is_deleted)
                VALUES
                    ('D-A', 'HOSP-A', 'P-1', 'V-DUP', 'K35.8', '急性阑尾炎', '出院主诊断', '1', '1', '0'),
                    ('D-B', 'HOSP-B', 'P-1', 'V-DUP', 'O80', '顺产', '出院主诊断', '1', '1', '0')
                """
            )
        )
        s.commit()

    # 3-key load returns ONLY HOSP-A data (zero cross-institute bleed)
    fp_a = qc_router._load_frontpage_from_pg("P-1", "V-DUP", institute_id="HOSP-A")
    assert fp_a is not None
    assert fp_a["sex"] == "男"
    assert [d["code"] for d in fp_a["diagnoses"]] == ["K35.8"]
    assert [s_item["code"] for s_item in fp_a["surgeries"]] == ["47.09"]
    assert fp_a["fees"]["pathology_diagnostic_fee"] == "120.0"

    # Ambiguous bare visit_id without institute_id fails closed with HTTP 409
    with pytest.raises(Exception) as exc_info:
        qc_router._load_frontpage_from_pg("P-1", "V-DUP", institute_id=None)
    assert getattr(exc_info.value, "status_code", None) == 409

    # Verify split-mode clinical_table_sql produces cdm.mr_diagnosis
    with patch("app.services.clinical_read.clinical_read_schema", return_value="cdm"):
        assert qc_router.clinical_table_sql("mr_diagnosis") == "cdm.mr_diagnosis"

    # P1-D3: DB error in _load_frontpage_from_pg raises HTTP 503 and marks queue failed (NOT "通过" / finish_success!)
    set_user("u-mgr-a", "qc_manager", "Manager A")
    queue_mock = MagicMock()
    queue_mock.start_run.return_value = "run-err-1"

    def _boom_session(*_args, **_kwargs):
        raise RuntimeError("PG connection lost")

    with (
        patch("app.routers.qc.default_workflow_queue_state_service", queue_mock),
        patch("sqlalchemy.orm.Session", side_effect=_boom_session),
    ):
        err_resp = client.post(
            "/api/v1/qc/coding-qc/check",
            json={"institute_id": "HOSP-A", "patient_id": "P-1", "visit_id": "V-DUP", "skip_llm": True},
        )
    assert err_resp.status_code == 503
    queue_mock.finish_failed.assert_called_once()
    queue_mock.finish_success.assert_not_called()


def test_qc_pre_send_privacy_redaction_coding_qc_and_analyze(env):
    client = env["client"]
    set_user = env["set_user"]
    set_user("u-mgr-a", "qc_manager", "Manager A")

    captured_coding = {}

    class _CapturingCodingEngine:
        async def run_all(self, received_frontpage):
            captured_coding["frontpage"] = received_frontpage
            captured_coding["scope_active"] = is_luxian_0609_privacy_scope_active()
            captured_coding["protected_payload"] = protect_current_payload(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "患者姓名：王小虎，身份证：110101199001011234，电话：13800138000",
                        }
                    ]
                }
            )
            return await CodingQCEngine(llm_client=None).run_all(received_frontpage, skip_llm=True)

    queue_mock = MagicMock()
    queue_mock.start_run.return_value = "run-priv-1"
    persist_mock = MagicMock()
    persist_mock.persist_analysis = AsyncMock(return_value={"qc_result_id": "qcr-priv-1"})

    with (
        patch("app.routers.qc._get_coding_qc_engine", return_value=_CapturingCodingEngine()),
        patch("app.routers.qc.default_workflow_queue_state_service", queue_mock),
        patch("app.routers.qc.default_qc_persistence_service", persist_mock),
    ):
        resp = client.post(
            "/api/v1/qc/coding-qc/check",
            json={
                "institute_id": "HOSP-A",
                "frontpage": {
                    "name": "王小虎",
                    "id_card_no": "110101199001011234",
                    "contact_number": "13800138000",
                    "sex": "男",
                    "age": "45",
                    "diagnoses": [{"code": "J18.9", "name": "社区获得性肺炎"}],
                    "surgeries": [],
                    "clinical_summary": "患者姓名：王小虎，身份证：110101199001011234，联系电话：13800138000，现住址：北京市朝阳区建国路88号；因发热咳嗽3天入院。",
                },
                "skip_llm": False,
            },
        )

    assert resp.status_code == 200, resp.text
    assert captured_coding["scope_active"] is True
    sent_fp = captured_coding["frontpage"]
    assert "name" not in sent_fp
    assert "id_card_no" not in sent_fp
    assert "contact_number" not in sent_fp
    summary = sent_fp["clinical_summary"]
    assert "王小虎" not in summary
    assert "110101199001011234" not in summary
    assert "13800138000" not in summary
    assert "建国路88号" not in summary
    assert "因发热咳嗽3天入院" in summary

    protected_msg = captured_coding["protected_payload"]["messages"][0]["content"]
    assert "王小虎" not in protected_msg
    assert "110101199001011234" not in protected_msg
    assert "13800138000" not in protected_msg

    # Also verify /analyze/{record_id} redacts clinical text before service.evaluate
    captured_analyze = {}

    async def _fake_eval(payload):
        captured_analyze["payload"] = payload
        return {
            "id": "an-1",
            "record_id": payload["record_id"],
            "overall_score": 95,
            "overall_grade": "A",
            "issues": [],
        }

    with (
        patch("app.routers.qc.service.evaluate", side_effect=_fake_eval),
        patch("app.routers.qc.default_qc_persistence_service", persist_mock),
    ):
        an_resp = client.post(
            "/api/v1/qc/analyze/rec-priv-1",
            json={
                "content": "患者姓名：李梅，手机号：13912345678，因胸痛入院。",
                "documents": [{"title": "入院记录", "content": "联系人：李明，身份证：110101198802023344"}],
            },
        )

    assert an_resp.status_code == 200, an_resp.text
    assert "李梅" not in captured_analyze["payload"]["content"]
    assert "13912345678" not in captured_analyze["payload"]["content"]
    assert "因胸痛入院" in captured_analyze["payload"]["content"]
    doc_content = captured_analyze["payload"]["documents"][0]["content"]
    assert "110101198802023344" not in doc_content


def test_appeals_withdraw_prevents_review_and_remediation_close_is_terminal(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]
    now = datetime.utcnow()

    qc_res_a = str(uuid.uuid4())
    rec_a = str(uuid.uuid4())
    doc_a_uuid = str(uuid.uuid4())

    with sf() as s:
        s.add_all(
            [
                SysUser(
                    id=doc_a_uuid,
                    username="doc_a_close",
                    email="doc_a_close@example.com",
                    display_name="Doctor A Close",
                    institute_id="HOSP-A",
                    department="心内科",
                    role="doctor",
                    roles_json=json.dumps(["doctor"]),
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                QCResultBiz(
                    id=qc_res_a,
                    record_id=rec_a,
                    institute_id="HOSP-A",
                    overall_score=80.0,
                    grade="B",
                    defect_count=1,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        s.execute(
            text("INSERT INTO medical_records (id, institute_id, patient_id, visit_id) VALUES (:id, :inst, :pid, :vid)"),
            {"id": rec_a, "inst": "HOSP-A", "pid": "PA9", "vid": "VA9"},
        )
        s.commit()

    # Create -> update -> withdraw appeal (all return 200 with trace_id, no 500)
    set_user(doc_a_uuid, "doctor", "Doctor A Close")
    c_resp = client.post(
        "/api/v1/appeals",
        json={
            "qc_result_id": qc_res_a,
            "record_id": rec_a,
            "appeal_type": "defect",
            "reason": "初始申诉理由内容超过十个字符",
            "priority": "low",
        },
    )
    assert c_resp.status_code == 200
    appeal_id = c_resp.json()["data"]["id"]

    u_resp = client.put(
        f"/api/v1/appeals/{appeal_id}",
        json={"reason": "更新后的申诉理由内容超过十个字符", "priority": "high"},
    )
    assert u_resp.status_code == 200
    assert u_resp.json()["data"]["priority"] == "high"

    w_resp = client.post(f"/api/v1/appeals/{appeal_id}/withdraw", json={"reason": "无需申诉"})
    assert w_resp.status_code == 200
    assert w_resp.json()["data"]["status"] == "withdrawn"

    # Withdrawn appeal cannot be reviewed, and no review row is written
    set_user("u-mgr-a", "qc_manager", "Manager A")
    assert (
        client.post(
            f"/api/v1/appeals/{appeal_id}/review",
            json={"action": "approve", "comment": "尝试审核已撤回申诉"},
        ).status_code
        == 409
    )
    with sf() as s:
        rev_cnt = s.execute(
            text("SELECT COUNT(*) FROM qc_appeal_reviews WHERE appeal_id = :aid"),
            {"aid": appeal_id},
        ).scalar_one()
        assert rev_cnt == 0

    # Remediation close -> terminal protection + statistics endpoints work with institute scope
    rem_resp = client.post(
        "/api/v1/remediation",
        json={
            "qc_result_id": qc_res_a,
            "record_id": rec_a,
            "defect_type": "format",
            "defect_description": "首页手术编码格式不规范说明十字符以上",
            "severity": "medium",
            "remediation_requirement": "请核对并更正手术编码说明十字符以上",
            "assignee_id": doc_a_uuid,
            "assignee_name": "Doctor A Close",
            "assignee_department": "心内科",
        },
    )
    assert rem_resp.status_code == 200
    rem_id = rem_resp.json()["data"]["id"]

    close_resp = client.post(f"/api/v1/remediation/{rem_id}/close", json={"reason": "重复任务关闭"})
    assert close_resp.status_code == 200
    assert close_resp.json()["data"]["status"] == "closed"

    # Closed task is terminal: cannot close again or submit
    assert client.post(f"/api/v1/remediation/{rem_id}/close", json={"reason": "二次关闭"}).status_code == 409
    set_user(doc_a_uuid, "doctor", "Doctor A Close")
    assert (
        client.post(
            f"/api/v1/remediation/{rem_id}/submit",
            json={"remediation_description": "尝试提交已关闭任务十字符以上", "remediation_evidence": []},
        ).status_code
        == 409
    )

    # Manager A sees summary & workload; Manager B sees 0
    set_user("u-mgr-a", "qc_manager", "Manager A")
    assert client.get("/api/v1/remediation/statistics/summary").json()["data"]["total"] == 1
    assert len(client.get("/api/v1/remediation/statistics/workload").json()["data"]) == 1

    set_user("u-mgr-b", "qc_manager", "Manager B")
    assert client.get("/api/v1/remediation/statistics/summary").json()["data"]["total"] == 0
    assert client.get("/api/v1/remediation/statistics/workload").json()["data"] == []


def test_tasks_sampling_idempotency_sqli_and_qc_rules_sqli_protection(env):
    client = env["client"]
    sf = env["session_factory"]
    set_user = env["set_user"]

    set_user("u-mgr-a", "qc_manager", "Manager A")
    t_resp = client.post(
        "/api/v1/tasks",
        json={
            "task_name": "抽样幂等测试",
            "task_type": "one_time",
            "sampling_method": "all",
            "assign_method": "keep",
        },
    )
    assert t_resp.status_code == 200
    task_id = t_resp.json()["data"]["id"]

    with patch(
        "app.services.task_sampling_service.TaskSamplingService.sample",
        new=AsyncMock(return_value=[{"id": "rec-s1", "institute_id": "HOSP-A"}, {"id": "rec-s2", "institute_id": "HOSP-B"}]),
    ):
        s1 = client.post(f"/api/v1/tasks/{task_id}/sample")
    assert s1.status_code == 200
    # Cross-institute record rec-s2 filtered out!
    assert s1.json()["data"]["sampled_count"] == 1

    # Second sample call rejected with 409
    with patch(
        "app.services.task_sampling_service.TaskSamplingService.sample",
        new=AsyncMock(return_value=[{"id": "rec-s1", "institute_id": "HOSP-A"}]),
    ):
        s2 = client.post(f"/api/v1/tasks/{task_id}/sample")
    assert s2.status_code == 409

    # Cross-institute assignee rejected with 403
    assert (
        client.post(
            f"/api/v1/tasks/{task_id}/assign",
            json={"assignees": [{"user_id": "u-doc-b", "user_name": "Doctor B"}], "method": "by_ratio"},
        ).status_code
        == 403
    )

    # Keyword SQLi on /api/v1/tasks returns 200 with 0 items
    sqli_tasks = client.get(
        "/api/v1/tasks",
        params={"keyword": 'x,id" IS NOT NULL OR 1=1 OR "id.eq.1'},
    )
    assert sqli_tasks.status_code == 200
    assert sqli_tasks.json()["data"]["items"] == []

    # Keyword SQLi on /api/v1/qc/rules returns 200 without SQLi
    with sf() as s:
        s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS qc_rules (
                    id VARCHAR(64) PRIMARY KEY,
                    rule_code VARCHAR(64),
                    name VARCHAR(200),
                    description TEXT,
                    category VARCHAR(64),
                    severity VARCHAR(32),
                    rule_type VARCHAR(32),
                    applicable_documents TEXT,
                    primary_document_category VARCHAR(64),
                    is_active BOOLEAN DEFAULT 1
                )
                """
            )
        )
        s.execute(
            text(
                "INSERT INTO qc_rules (id, rule_code, name, description, category, is_active) "
                "VALUES ('r1', 'RC001', '规则1', '测试描述', 'core', 1)"
            )
        )
        s.commit()

    sqli_rules = client.get(
        "/api/v1/qc/rules",
        params={"keyword": 'x,id" IS NOT NULL OR 1=1 OR "id.eq.1'},
    )
    assert sqli_rules.status_code == 200
    assert sqli_rules.json()["data"]["items"] == []

