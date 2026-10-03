"""批量逐例 API 使用实际审核与沟通 owner，SQLite 合成结果替代外部资料。"""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.case_communication import CaseCommunication
from app.database.models.qc import (
    Notification, QCDefect, QCDefectHistory, QCRecordReview, QCTask, QCTaskQCRun,
    QCTaskRecord, SysUser,
)
from app.routers import batch_case_actions as batch_router
from app.routers import case_communications as communications_router
from app.routers.qc_sichuan import _hydrate_luxian_canonical_batch_job_or_409
from app.services import record_review_service as reviews
from app.services.case_communication_service import CaseCommunicationService
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services.defect_rectification_service import RectificationError
from app.services.qc_workspace import canonical_result_store as canonical
from tests.unit.test_record_review_service import _envelope_table
from tests.unit.test_record_review_snapshot_report_integration import Environment


@pytest.fixture
def integrated(monkeypatch):
    engine = sa.create_engine("sqlite://", poolclass=StaticPool,
                              connect_args={"check_same_thread": False},
                              execution_options={"schema_translate_map": {"qc": None}})
    for model in (QCTask, QCTaskRecord, QCTaskQCRun, QCRecordReview, QCDefect,
                  QCDefectHistory, SysUser, Notification, CaseCommunication):
        model.__table__.create(engine)
    envelopes = _envelope_table()
    envelopes.create(engine)
    jobs = sa.Table("custom_qc_batch_jobs", sa.MetaData(),
                    sa.Column("id", sa.String, primary_key=True),
                    *[sa.Column(k, sa.String) for k in ("created_by", "scene", "scope")],
                    sa.Column("filters_json", sa.Text))
    jobs.create(engine)
    sessions = sessionmaker(bind=engine)
    workspace = Environment(sessions, envelopes, jobs)
    workspace.add_result()
    workspace.add_result("B")
    with sessions.begin() as session:
        for key, role, institute in (("manager", "qc_manager", "A"),
                                     ("doctor", "doctor", "A"),
                                     ("cross", "qc_manager", "B")):
            session.add(SysUser(id=key, username=key, display_name="合成人员", role=role,
                                institute_id=institute, department="合成科室", is_active=True))
    monkeypatch.setattr(reviews, "SessionLocal", sessions)
    monkeypatch.setattr(reviews, "_default_workspace_factory", lambda: workspace)
    monkeypatch.setattr(reviews, "_envelope_table", lambda: envelopes)
    monkeypatch.setattr(reviews, "_batch_job_table", lambda: jobs)
    monkeypatch.setattr(canonical, "customer_safe_projection_key", lambda: "test-key")
    monkeypatch.setattr(CustomQCWorkspaceService, "__new__", lambda cls: workspace)
    # 最新结果选择适配器不生成状态，场景与三坐标仍由生产解析器核验持久化信封。
    original_reader = workspace.build_latest_single_record_result_dto
    def read_result(**kw):
        identity = {key: kw[key] for key in ("institute_id", "patient_id", "visit_id")}
        dto = original_reader(**identity)
        with sessions() as session:
            payload, _ = canonical.CanonicalResultStore(envelopes).load_selected_with_id(
                session, root_job_id=dto["job_id"], **identity,
                rule_set_key=dto["rule_set_key"], rule_set_version=dto["rule_set_version"],
            )
        return {**dto, "record_ref": payload["record_ref"], "items": payload["items"]}

    workspace.build_latest_single_record_result_dto = read_result

    def department(session, identity):
        if identity not in workspace.current:
            raise RectificationError("合成病例不存在", 404)
        return "合成科室"

    owner = CaseCommunicationService(sessions=sessions, department=department)
    monkeypatch.setattr(batch_router, "service", batch_router.BatchCaseActions(owner))
    monkeypatch.setattr(communications_router, "service", owner)
    app = FastAPI()
    app.include_router(batch_router.router)
    app.include_router(communications_router.router)
    actor = {"id": "manager"}
    app.dependency_overrides[batch_router.get_current_user] = lambda: actor
    yield TestClient(app), sessions, workspace, actor
    engine.dispose()


IDENTITY = {"institute_id": "A", "patient_id": "P", "visit_id": "V", "scene": "running"}
PATH = "/api/v1/record-reviews/case/batch-item"


def test_actual_api_partial_permission_failure_and_approval_idempotency(integrated):
    client, sessions, workspace, _ = integrated
    assert client.post(f"{PATH}/prepare", json={**IDENTITY, "institute_id": "B"}).status_code == 403
    prepared = client.post(f"{PATH}/prepare", json=IDENTITY)
    assert prepared.status_code == 200
    assert prepared.json()["data"]["source"]["envelope_id"] == "env-A-1"
    payload = {**IDENTITY, "job_id": "job-A-1", "envelope_id": "env-A-1", "request_id": str(uuid4())}
    approved = client.post(f"{PATH}/approve", json=payload)
    assert approved.status_code == 200
    receipt = approved.json()["data"]
    replay = client.post(f"{PATH}/approve", json=payload)
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == receipt["id"]
    assert replay.json()["data"]["idempotent"] is True
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(QCRecordReview)) == 1
        row = session.get(QCRecordReview, receipt["id"])
        assert row.reviewer_id == "manager" and row.defect_snapshot["auto"]["count"] == 1
    workspace.add_result(suffix="2", run=2)
    assert client.post(f"{PATH}/approve", json={**payload, "request_id": str(uuid4())}).status_code == 409
    with sessions.begin() as session:
        session.get(SysUser, "manager").role = "doctor"
    assert client.post(f"{PATH}/approve", json=payload).status_code == 403
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(QCRecordReview)) == 1


def test_actual_urge_api_replay_recipient_permission_and_scene_switch(integrated):
    client, sessions, _, actor = integrated
    prepared = client.post(f"{PATH}/prepare", json=IDENTITY).json()["data"]
    payload = {**prepared["source"], "request_id": str(uuid4()), "action": "urge",
               "content": "合成批量催办", "recipient_id": "doctor"}
    assert client.post("/api/v1/case-communications", json={**payload, "recipient_id": "cross"}).status_code == 403
    assert client.post("/api/v1/case-communications", json={**payload, "scene": "final"}).status_code == 409
    response = client.post("/api/v1/case-communications", json=payload)
    assert response.status_code == 200
    receipt = response.json()["data"]
    assert client.post("/api/v1/case-communications", json=payload).json()["data"]["id"] == receipt["id"]
    actor["id"] = "cross"
    assert client.post("/api/v1/case-communications", json=payload).status_code == 403
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(CaseCommunication)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(Notification)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(QCRecordReview)) == 0


def test_partial_job_success_count_is_verified_against_saved_canonical_cases(integrated):
    _, _, workspace, _ = integrated
    job = workspace.get_batch_job(job_id="job-A-1", created_by="creator")
    job.update(status="failed", success_count=1, total_records=2,
               summary={"execution_status": "partial_failed"})
    job["filters"]["record_refs"].append({"institute_id": "B", "patient_id": "P", "visit_id": "V"})
    hydrated = _hydrate_luxian_canonical_batch_job_or_409(workspace=workspace, job=job)
    assert hydrated["success_count"] == 1
    assert len({item["record_ref"] for item in hydrated["items"]}) == 1
    assert {item["rule_id"] for item in hydrated["items"]} == {"LX0609-001", "LX0609-002"}
    # 成功计数不得冒充未保存病例；生产详情读取器拒绝不一致的计数。
    with pytest.raises(HTTPException) as exc:
        _hydrate_luxian_canonical_batch_job_or_409(workspace=workspace, job={**job, "success_count": 2})
    assert exc.value.status_code == 409
