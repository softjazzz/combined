"""医生按姓名授权：真实SQL与HTTP反例；仅使用内存合成数据，不访问业务库。"""

import json
from datetime import datetime

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core import access_control
from app.database.models.cdm import (
    AdmissionRecord, Diagnosis, HospitalizationStatusProjection, InpatRegistration,
    MedicalRecordFrontpage as MR, MrCost, MrSurgery, QCResult,
)
from app.database.models.v36_reports import SysUser
from app.routers import auth, emr_render, medical_records, medical_records_alias, qc_sample_pools, records, workstation
from app.services import clinical_read, doctor_case_scope as policy
from app.services.medical_records import export_service, query_service
from app.services.workstation.worklist_service import WorkstationAggregationService


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.connect() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
        connection.execute(text("ATTACH DATABASE ':memory:' AS qc"))
        connection.execute(text("CREATE TABLE qc.sync_config_registry(namespace TEXT,config_key TEXT,payload_json TEXT)"))
        connection.commit()
    SysUser.__table__.create(engine)
    MR.__table__.create(engine)  # public旧表替身，不能成为授权来源。
    for model in (MR, AdmissionRecord, InpatRegistration, HospitalizationStatusProjection, Diagnosis, MrSurgery, MrCost):
        model.__table__.to_metadata(MetaData(), schema="cdm").create(engine)
    QCResult.__table__.create(engine)
    def factory():
        return Session(engine)
    from app.database import connection as owner
    monkeypatch.setattr(owner, "SessionLocal", factory)
    monkeypatch.setattr(policy, "SessionLocal", factory)
    monkeypatch.setattr(query_service, "_session_factory", factory)
    monkeypatch.setattr(export_service, "_session_factory", factory)
    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: "cdm")
    monkeypatch.setattr(query_service, "_load_latest_luxian_0609_qc_summaries", lambda *_args, **_kwargs: {})

    class Queue:
        def get_state_map(self, **kwargs): return {}
        def backfill_frontpage_generate(self, **kwargs): return None

    monkeypatch.setattr(query_service, "default_workflow_queue_state_service", Queue())
    with factory() as session:
        for id_, name, institute, department, role in (
            ("doctor-a", "合成甲", "H-A", "内科", "doctor"),
            ("doctor-b", "合成乙", "H-A", "内科", "doctor"),
            ("doctor-empty", "合成无范围", None, None, "doctor"),
            ("admin", "合成管理员", "H-A", "内科", "admin"),
            ("sync", "合成同步管理员", "H-A", "内科", "sync_admin"),
        ):
            session.add(SysUser(id=id_, username=id_, display_name=name, institute_id=institute,
                                department=department, role=role, roles_json=json.dumps([role]), is_active=True))
        session.add(MR(institute_id="H-A", patient_id="stale", visit_id="stale", name="旧表病历",
                       discharge_dept_name="内科", attending_physician_sign="合成甲"))
        session.commit()
        cases = (
            ("H-A", "P-own", "V-own", "内科", "合成甲", "其他"),
            ("H-A", "P-colleague", "V-colleague", "内科", "合成乙", "合成甲"),
            ("H-A", "P-otherdept", "V-otherdept", "外科", "合成甲", "合成甲"),
            ("H-B", "P-own", "V-own", "内科", "合成甲", "合成甲"),
            ("H-A", "P-multi", "V-multi", "内科", "合成甲 合成乙", "合成甲"),
            ("H-A", "P-own2", "V-own2", "内科", "  合成甲  ", "其他"),
        )
        with engine.begin() as connection:
            connection = connection.execution_options(schema_translate_map={None: "cdm"})
            for institute, patient, visit, dept, attending, resident in cases:
                connection.execute(MR.__table__.insert().values(
                    institute_id=institute, patient_id=patient, visit_id=visit, mr_no="MR-" + patient,
                    name="合成病例-" + patient, discharge_dept_name=dept, admission_dept_name=dept,
                    attending_physician_sign=attending, resident_physician_sign=resident,
                    admission_datetime=datetime(2026, 1, 1), discharge_datetime=datetime(2026, 1, 3),
                ))
    yield factory
    engine.dispose()


def test_scope_uses_persistent_account_exact_attending_name_and_cdm(database):
    scope = policy.resolve_doctor_case_scope("doctor-a")
    assert scope.case_refs == (("H-A", "P-own", "V-own"), ("H-A", "P-own2", "V-own2"))
    assert scope.doctor_name == "合成甲"
    # 同科室其他医生、外科、同号外院、住院医师及多人签名都不构成主治归属。
    assert policy.resolve_doctor_case_scope("admin") is None
    assert policy.resolve_doctor_case_scope("sync") is None


@pytest.mark.parametrize("kind", ["missing", "inactive", "corrupt_roles", "duplicate", "no_name"])
def test_invalid_or_ambiguous_binding_fails_closed(database, kind):
    with database() as session:
        doctor = session.get(SysUser, "doctor-a")
        if kind == "missing":
            doctor.institute_id = None
        if kind == "inactive":
            doctor.is_active = False
        if kind == "corrupt_roles":
            doctor.roles_json = "{broken"
        if kind == "no_name":
            doctor.display_name = " "
        if kind == "duplicate":
            session.add(SysUser(id="duplicate", username="duplicate", display_name="合成甲", institute_id="H-A",
                                department="内科", role="doctor", roles_json='["doctor"]', is_active=True))
        session.commit()
    with pytest.raises(HTTPException) as error:
        policy.resolve_doctor_case_scope("doctor-a")
    assert error.value.status_code == 403


def test_legacy_single_number_rejects_cross_hospital_collision(database):
    scope = policy.resolve_doctor_case_scope("doctor-a")
    with pytest.raises(HTTPException):
        policy.resolve_record_identity(scope, "V-own")
    assert policy.resolve_record_identity(scope, "V-own2")["patient_id"] == "P-own2"


def test_sql_counts_paging_doctor_options_and_summary_share_own_scope(database):
    scope = policy.resolve_doctor_case_scope("doctor-a")
    page = query_service.get_workstation_data(case_scope=scope, page=1, page_size=1)
    assert page["total"] == 2
    assert len(page["records"]) == 1
    assert page["records"][0]["patientId"] in {"P-own", "P-own2"}
    assert {d["name"] for d in page["doctors"]} == {"全部主管医师", "合成甲"}
    assert {d["name"] for d in page["departments"]} == {"全部科室", "内科"}
    simple = query_service.list_medical_records(case_scope=scope, page_size=1)
    assert simple["total"] == 2 and len(simple["items"]) == 1
    assert query_service.get_stats(case_scope=scope)["total_records"] == 2


@pytest.fixture
def client(database, monkeypatch):
    def principal(token):
        with database() as session:
            user = session.get(SysUser, token)
            return {"id": token, "roles": [user.role], "display_name": user.display_name,
                    "department": user.department, "institute_id": user.institute_id, "is_active": True}
    monkeypatch.setattr(access_control, "resolve_current_user_from_token", principal)
    app = FastAPI(dependencies=[Depends(access_control.enforce_default_auth)])
    app.include_router(medical_records.router)
    app.include_router(medical_records_alias.router)
    app.include_router(qc_sample_pools.router)
    app.include_router(emr_render.router)
    app.include_router(records.router)
    app.include_router(workstation.router)
    app.include_router(auth.router)
    return TestClient(app, raise_server_exceptions=True)


@pytest.mark.parametrize("path", [
    "/api/medical-records/frontpage/H-A/P-colleague/V-colleague",
    "/api/medical-records/diagnoses/H-A/P-colleague/V-colleague",
    "/api/medical-records/record-content/H-A/P-otherdept/V-otherdept",
    "/api/v1/records/V-colleague/qc-detail",
    "/api/v1/emr/V-colleague/documents?source_view=current",
    "/api/medical-records/frontpage-sheet/P-colleague/V-colleague",
    "/api/medical-records/table-data/mr",
    "/api/medical-records/frontpage/H-A/P-own2%20/V-own2",
    "/api/v1/medical-records/V-colleague",
    "/api/v1/records/V-colleague",
    "/api/v1/qc/sample-pools",
])
def test_direct_urls_and_legacy_paths_cannot_bypass_scope(client, path):
    response = client.get(path, headers={"Authorization": "Bearer doctor-a", "X-Role": "admin", "X-Institute-Id": "H-B"})
    assert response.status_code == 403
    assert "P-colleague" not in response.text


def test_workstation_http_enforces_own_scope_and_filter_tampering(client, monkeypatch):
    calls = []

    def load_summaries(refs, **_kwargs):
        calls.append({tuple(ref.values()) for ref in refs})
        return {("H-A", "P-own", "V-own"): {"status": "ready", "status_counts": {"data_gap": 1}}}

    monkeypatch.setattr(query_service, "_load_latest_luxian_0609_qc_summaries", load_summaries)
    headers = {"Authorization": "Bearer doctor-a"}
    url = "/api/medical-records/workstation?page_size=1"
    data = client.get(url, headers=headers).json()
    assert data["total"] == 2 and len(data["records"]) == 1
    deferred = client.get(url + "&qc_summary_mode=deferred", headers=headers).json()
    assert deferred["records"][0]["recordKey"] == data["records"][0]["recordKey"]
    assert "qc_summary" not in deferred and "latest_qc_summary" not in deferred["records"][0]
    assert len(calls) == 1
    summary = client.get(url + "&qc_summary_mode=only", headers=headers).json()
    assert summary == {
        "qc_summary": data["qc_summary"],
        "records": [
            {key: data["records"][0][key] for key in ("recordKey", "latest_qc_summary")}
        ],
    }
    assert calls == [{("H-A", "P-own", "V-own"), ("H-A", "P-own2", "V-own2")}] * 2
    for mode in ("inline", "deferred", "only"):
        for query in ("dept=外科", "doctor=合成乙"):
            assert client.get(url + f"&qc_summary_mode={mode}&" + query, headers=headers).status_code == 403


def test_emr_explicit_identity_permits_own_shared_visit_but_rejects_foreign_identity(client, monkeypatch):
    monkeypatch.setattr(emr_render, "load_current_documents", lambda **identity: {
        "documents": [{"content": "合成正文", "document_id": "safe", **identity}], "documents_tree": [],
    })
    monkeypatch.setattr(emr_render, "_project_customer_safe_source_refs", lambda data: data)
    headers = {"Authorization": "Bearer doctor-a"}
    url = "/api/v1/emr/V-own/documents?source_view=current&institute_id=H-A&patient_id=P-own&visit_id=V-own"
    response = client.get(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["documents"][0]["institute_id"] == "H-A"
    assert client.get(url.replace("H-A", "H-B"), headers=headers).status_code == 403


def test_doctor_cannot_change_matching_name_or_department_via_self_profile(client):
    headers = {"Authorization": "Bearer doctor-a"}
    for change in ({"display_name": "合成乙"}, {"department": "外科"}):
        response = client.put("/api/v1/auth/profile", json=change, headers=headers)
        assert response.status_code == 403


def test_manager_routes_keep_existing_owner_and_no_doctor_scope(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(query_service, "get_repository", lambda: type("Repository", (), {
        "list_patients": lambda _, **kwargs: captured.update(kwargs) or {"items": [], "total": 42},
    })())
    response = client.get("/api/medical-records/list", headers={"Authorization": "Bearer sync"})
    assert response.status_code == 200 and response.json()["total"] == 42


def test_unmatched_name_returns_empty_without_department_or_demo_fallback(database):
    with database() as session:
        session.get(SysUser, "doctor-a").display_name = "合成未匹配医师"
        session.commit()
    scope = policy.resolve_doctor_case_scope("doctor-a")
    assert not scope.case_refs
    data = query_service.get_workstation_data(case_scope=scope, demo_policy=lambda *_: True)
    assert data["total"] == 0 and not data["records"]


def test_qc_detail_uses_authorized_identity_and_never_legacy_unscoped_results(client, monkeypatch):
    captured = {}
    def documents(record_id, *, authorized_identity):
        captured.update(authorized_identity)
        return {"documents": [{"doc_type": "admission_record", "content": "合成正文"}], "documents_tree": []}
    monkeypatch.setattr(records, "_load_bundle_payload_for_record", documents)
    monkeypatch.setattr(records, "_load_luxian_0609_review_items_from_canonical", lambda *_, **_kw: {
        "review_items": [{"rule_id": "LX0609-01-02-02", "status": "compliant"}], "state": "ready",
    })
    def forbidden(*args, **kwargs):
        raise AssertionError("不能读取旧缓存或未核定身份的结果")
    monkeypatch.setattr(records, "get_supabase", forbidden)
    monkeypatch.setattr(records, "_load_review_items_from_latest_batch", forbidden)
    response = client.get("/api/v1/records/V-own2/qc-detail", headers={"Authorization": "Bearer doctor-a"})
    assert response.status_code == 200
    assert captured == {"institute_id": "H-A", "patient_id": "P-own2", "visit_id": "V-own2"}
    assert response.json()["data"]["review_items"][0]["status"] == "compliant"
    monkeypatch.setattr(records, "_load_luxian_0609_review_items_from_canonical", lambda *_, **_kw: {
        "review_items": [], "state": "technical_error",
    })
    response = client.get("/api/v1/records/V-own2/qc-detail", headers={"Authorization": "Bearer doctor-a"})
    assert response.json()["data"]["review_result_state"] == "technical_error"


def test_home_passes_only_owned_case_refs_to_result_reader(client, database, monkeypatch):
    service = WorkstationAggregationService(session_factory=database)
    captured = []
    def summaries(refs):
        captured.extend(refs)
        return {}
    monkeypatch.setattr(service, "_load_luxian_0609_summaries", summaries)
    monkeypatch.setattr(workstation, "default_workstation_aggregation_service", service)
    response = client.get("/api/v1/workstation/qc-home", headers={"Authorization": "Bearer doctor-a"})
    assert response.status_code == 200
    assert {(r["institute_id"], r["patient_id"], r["visit_id"]) for r in captured} == {
        ("H-A", "P-own", "V-own"), ("H-A", "P-own2", "V-own2"),
    }
    assert "P-colleague" not in response.text and "H-B" not in response.text


def test_sheet_export_filters_all_clinical_components_by_authorized_institute(client, database):
    with database() as session:
        connection = session.connection().execution_options(schema_translate_map={None: "cdm"})
        for institute, suffix in (("H-A", "本人"), ("H-B", "外院")):
            identity = {"institute_id": institute, "patient_id": "P-own2", "visit_id": "V-own2"}
            connection.execute(Diagnosis.__table__.insert(), [
                {**identity, "diagnosis_id": "1", "diagnosis_type": "出院诊断", "diagnosis_name": suffix + "诊断", "diagnosis_code": "A01"},
                {**identity, "diagnosis_id": "2", "diagnosis_type": "病理诊断", "diagnosis_name": suffix + "病理", "diagnosis_code": "M01"},
            ])
            connection.execute(MrSurgery.__table__.insert().values(**identity, surgery_id="1", surgery_name=suffix + "手术"))
            connection.execute(MrCost.__table__.insert().values(**identity))
        session.commit()
    response = client.get("/api/medical-records/frontpage-sheet/P-own2/V-own2", headers={"Authorization": "Bearer doctor-a"})
    assert response.status_code == 200
    assert "本人" in response.text
    assert "外院" not in response.text
