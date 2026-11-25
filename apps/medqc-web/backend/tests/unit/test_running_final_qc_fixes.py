from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.database.connection import Base
from app.database.models.case_communication import CaseCommunication
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
    QCResult,
)
from app.database.models.v36_reports import DefectRectification, QCAppeal, SysUser
from app.routers import case_communications as comm_router
from app.routers import emr_render
from app.services import case_material_snapshot as case_material
from app.services import clinical_case_catalog as catalog_service
from app.services import clinical_sources
from app.services.case_communication_service import CaseCommunicationService
from app.services.doctor_notification_service import Notification
from app.services.medical_records import query_service
from app.services.workstation import (
    luxian_0609_result_analysis_service as result_analysis_module,
)
from app.services.workstation.luxian_0609_result_analysis_service import (
    Luxian0609ResultAnalysisService,
    clear_luxian_0609_result_analysis_caches,
)


def _no_demo_settings():
    return SimpleNamespace(include_demo_records=False), "test"


def _make_workstation_sqlite_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        execution_options={"schema_translate_map": {"cdm": None, "qc": None}},
    )
    for model in (
        MedicalRecordFrontpage,
        InpatRegistration,
        AdmissionRecord,
        DischargeRecord,
        HospitalizationStatusProjection,
        QCResult,
    ):
        model.__table__.create(engine, checkfirst=True)
    factory = sessionmaker(bind=engine)
    return engine, factory


# =============================================================================
# P0 #1: 历史快照未保留时 fallback_to_current=1 平滑回退 + 严格模式保留 409
# =============================================================================


def test_emr_saved_documents_and_render_fallback_to_current_when_snapshot_missing(
    monkeypatch,
):
    identity = ("泸县人民医院", "P2641480", "2641480")
    live_docs = {
        "layout_version": "bundle_struct_v1",
        "daily_material_status": "complete",
        "primary_material_status": "complete",
        "documents": [
            {
                "id": "adm-1",
                "doc_id": "adm-1",
                "document_id": "adm-1",
                "doc_type": "admission_record",
                "group_key": "admission",
                "execution_domain": "admission",
                "title": "入院记录",
                "content": "患者因胸痛入院，查体平稳。",
            },
            {
                "id": "ord-1",
                "doc_id": "ord-1",
                "document_id": "ord-1",
                "doc_type": "inpat_drug_order",
                "group_key": "orders",
                "execution_domain": "course",
                "title": "阿司匹林肠溶片",
                "order_item": "阿司匹林肠溶片",
                "content": "口服 100mg qd",
            },
        ],
    }

    def fake_saved_source(req: Request, job_id: str):
        req.state.material_root_job_id = job_id
        return clinical_sources.legacy_snapshot()

    monkeypatch.setattr(clinical_sources, "source_for_saved_job", fake_saved_source)
    monkeypatch.setattr(case_material, "load", lambda *_a, **_k: None)
    monkeypatch.setattr(emr_render, "customer_safe_projection_key", lambda: "synthetic-key")
    monkeypatch.setattr(emr_render, "_load_live_cdm_documents", lambda *_a, **_k: None)
    monkeypatch.setattr(
        emr_render,
        "load_current_documents",
        lambda **_kwargs: {
            **live_docs,
            "documents": [dict(doc) for doc in live_docs["documents"]],
        },
    )
    async def _no_annotations(*_a, **_k):
        return [], "no_result"

    monkeypatch.setattr(emr_render, "_load_defect_annotations", _no_annotations)

    app = FastAPI(
        dependencies=[
            Depends(clinical_sources.prepare_request),
            Depends(clinical_sources.bind_request),
        ]
    )
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "qc-1",
        "roles": ["admin", "qc_manager"],
    }

    params = {
        "institute_id": identity[0],
        "patient_id": identity[1],
        "visit_id": identity[2],
        "job_id": "legacy-job-001",
        "view": "summary",
        "document_scope": "clinical",
    }
    with TestClient(app) as client:
        strict_res = client.get("/api/v1/emr/2641480/documents", params=params)
        assert strict_res.status_code == 409
        assert strict_res.json()["detail"] == "historical_material_snapshot_not_retained"

        clinical_res = client.get(
            "/api/v1/emr/2641480/documents",
            params={**params, "fallback_to_current": "1"},
        )
        assert clinical_res.status_code == 200, clinical_res.text
        clinical_data = clinical_res.json()["data"]
        assert clinical_data["material_source_fallback"] is True
        assert (
            clinical_data["material_source_fallback_reason"]
            == "historical_material_snapshot_not_retained"
        )
        assert clinical_data["material_source_view"] == "current"
        assert "最新文书" in clinical_data["material_source_notice"]
        assert [d["document_id"] for d in clinical_data["documents"]] == ["adm-1"]
        assert "content" not in clinical_data["documents"][0]

        orders_res = client.get(
            "/api/v1/emr/2641480/documents",
            params={**params, "document_scope": "orders", "fallback_to_current": "true"},
        )
        assert orders_res.status_code == 200, orders_res.text
        orders_data = orders_res.json()["data"]
        assert orders_data["material_source_fallback"] is True
        assert [d["document_id"] for d in orders_data["documents"]] == ["ord-1"]

        render_res = client.get(
            "/api/v1/emr/2641480/render",
            params={
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
                "job_id": "legacy-job-001",
                "execution_domain": "admission",
                "doc_type": "admission_record",
                "doc_id": "adm-1",
                "fallback_to_current": "1",
            },
        )
        assert render_res.status_code == 200, render_res.text
        render_data = render_res.json()["data"]
        assert render_data["material_source_fallback"] is True
        assert render_data["material_source_view"] == "current"
        assert "患者因胸痛入院" in render_data["content"]

        conflict_res = client.get(
            "/api/v1/emr/2641480/documents",
            params={
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
                "job_id": "legacy-job-001",
                "source_view": "current",
                "view": "full",
                "fallback_to_current": "1",
            },
        )
        assert conflict_res.status_code == 409
        assert (
            conflict_res.json()["detail"]
            == "historical_and_current_material_views_conflict"
        )


def test_emr_prefers_frozen_snapshot_even_when_fallback_to_current_enabled(monkeypatch):
    identity = ("泸县人民医院", "P2641480", "2641480")
    frozen = {
        "identity": list(identity),
        "binding": "synthetic-binding",
        "tables": {},
        "documents": {
            "documents": [
                {
                    "id": "frozen-adm",
                    "document_id": "frozen-adm",
                    "doc_type": "admission_record",
                    "group_key": "admission",
                    "execution_domain": "admission",
                    "title": "冻结入院记录",
                    "content": "冻结快照正文",
                }
            ]
        },
    }

    def fake_saved_source(req: Request, job_id: str):
        req.state.material_root_job_id = job_id
        return clinical_sources.legacy_snapshot()

    monkeypatch.setattr(clinical_sources, "source_for_saved_job", fake_saved_source)
    monkeypatch.setattr(case_material, "load", lambda *_a, **_k: frozen)
    monkeypatch.setattr(case_material, "source_binding", lambda *_a: "synthetic-binding")
    monkeypatch.setattr(emr_render, "customer_safe_projection_key", lambda: "synthetic-key")
    monkeypatch.setattr(
        emr_render,
        "load_current_documents",
        lambda **_k: pytest.fail("存在冻结快照时不得回退读取当前文书"),
    )

    app = FastAPI(
        dependencies=[
            Depends(clinical_sources.prepare_request),
            Depends(clinical_sources.bind_request),
        ]
    )
    app.include_router(emr_render.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "qc-1",
        "roles": ["admin", "qc_manager"],
    }

    with TestClient(app) as client:
        res = client.get(
            "/api/v1/emr/2641480/documents",
            params={
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
                "job_id": "new-job-001",
                "view": "summary",
                "document_scope": "clinical",
                "fallback_to_current": "1",
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert not data.get("material_source_fallback")
        assert [d["document_id"] for d in data["documents"]] == ["frozen-adm"]


@pytest.mark.asyncio
async def test_emr_pdf_material_copy_still_rejects_even_with_fallback_flag(monkeypatch):
    from starlette.requests import Request as StarletteRequest
    from app.services import validation_material_source

    monkeypatch.setattr(
        validation_material_source, "_registered_schema", lambda *_: "pdfmat_012345abcdef"
    )

    def saved_source(req, job_id):
        req.state.material_root_job_id = job_id
        return clinical_sources.legacy_snapshot()

    monkeypatch.setattr(clinical_sources, "source_for_saved_job", saved_source)
    monkeypatch.setattr(case_material, "load", lambda *_: None)
    req = StarletteRequest(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/emr/pdfv_V/documents",
            "query_string": (
                b"institute_id=I&patient_id=pdfp_P&visit_id=pdfv_V"
                b"&job_id=PDF-JOB&fallback_to_current=1"
            ),
            "headers": [],
        }
    )
    clinical_sources.prepare_request(req)
    gen = clinical_sources.bind_request(req)
    try:
        with pytest.raises(HTTPException, match="historical_material_snapshot_not_retained"):
            await gen.__anext__()
    finally:
        await gen.aclose()


# =============================================================================
# P0 #2: 病历沟通表缺失时幂等建表避免 503，并支持全/半角括号科室匹配医生
# =============================================================================


def test_case_communications_auto_creates_missing_table_and_normalizes_icu_department(
    monkeypatch,
):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"qc": None}},
    )
    try:
        # 刻意不创建 CaseCommunication 表，模拟 PG split/single 缺表导致的 503
        for model in (Notification, SysUser, DefectRectification, QCAppeal):
            model.__table__.create(engine)
        sessions = sessionmaker(engine)
        with sessions.begin() as session:
            session.add_all(
                [
                    SysUser(
                        id="mgr-1",
                        username="mgr",
                        display_name="质控员",
                        role="qc_manager",
                        institute_id="泸县人民医院",
                        department="质控科",
                        is_active=True,
                    ),
                    SysUser(
                        id="doc-icu",
                        username="doc_icu",
                        display_name="石医生",
                        role="doctor",
                        institute_id="泸县人民医院",
                        department="重症医学科（ICU）",
                        is_active=True,
                    ),
                ]
            )
        frozen_source = {
            "institute_id": "泸县人民医院",
            "patient_id": "0000223003",
            "visit_id": "2641480",
            "scene": "final",
            "root_job_id": "job-2641480",
            "envelope_id": "env-2641480",
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
        }
        svc = CaseCommunicationService(
            sessions=sessions,
            source=lambda _session, _data, *, candidate=False: dict(frozen_source),
            department=lambda _session, _identity: "重症医学科(ICU)",
        )
        monkeypatch.setattr(comm_router, "service", svc)
        app = FastAPI()
        app.include_router(comm_router.router)
        app.dependency_overrides[get_current_user] = lambda: {"id": "mgr-1"}

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/case-communications/candidates",
                json={
                    "institute_id": "泸县人民医院",
                    "patient_id": "0000223003",
                    "visit_id": "2641480",
                    "root_job_id": "job-2641480",
                },
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()["data"]
            assert data["department"] == "重症医学科（ICU）"
            assert data["doctors"] == [{"id": "doc-icu", "name": "石医生"}]
            assert data["items"] == []

            created = client.post(
                "/api/v1/case-communications",
                json={
                    **frozen_source,
                    "recipient_id": "doc-icu",
                    "action": "urge",
                    "content": "请补充病程记录",
                    "request_id": str(uuid4()),
                },
            )
            assert created.status_code == 200, created.text
            assert created.json()["data"]["department"] == "重症医学科（ICU）"

            after = client.post(
                "/api/v1/case-communications/candidates",
                json={
                    "institute_id": "泸县人民医院",
                    "patient_id": "0000223003",
                    "visit_id": "2641480",
                    "root_job_id": "job-2641480",
                },
            )
            assert after.status_code == 200
            assert len(after.json()["data"]["items"]) == 1
    finally:
        engine.dispose()


# =============================================================================
# P1 #3: 终末质控顶部 KPI 与「结果分析」Tab 已完成质控份数口径一致
# =============================================================================


def test_workstation_kpi_and_result_analysis_align_ready_and_partial_failed_counts(
    monkeypatch,
):
    clear_luxian_0609_result_analysis_caches()
    records = [
        {
            "institute_id": "H1",
            "patient_id": f"P{idx}",
            "visit_id": f"V{idx}",
            "patient_name": f"患者{idx}",
            "department": "重症医学科(ICU)" if idx % 2 == 0 else "重症医学科（ICU）",
            "attending_physician": "石跃",
        }
        for idx in range(1, 5)
    ]
    refs = [
        {
            "institute_id": rec["institute_id"],
            "patient_id": rec["patient_id"],
            "visit_id": rec["visit_id"],
        }
        for rec in records
    ]
    raw_summaries = {
        ("H1", "P1", "V1"): {
            "status": "ready",
            "completed_at": "2026-10-20T08:00:00+00:00",
            "total_rule_count": 2,
            "status_counts": {"non_compliant": 1, "compliant": 1},
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "non_compliant"},
                {"rule_id": "LX0609-01-02-01", "status": "compliant"},
            ],
        },
        ("H1", "P2", "V2"): {
            "status": "ready",
            "execution_status": "partial_failed",
            "completed_at": "2026-10-21T08:00:00+00:00",
            "total_rule_count": 1,
            "failed_rule_count": 1,
            "failed_rule_ids": ["LX0609-01-02-01"],
            "status_counts": {"non_compliant": 1},
            "items": [
                {"rule_id": "LX0609-01-01-01", "status": "non_compliant"},
            ],
        },
        ("H1", "P3", "V3"): {
            "status": "technical_error",
            "reason_code": "canonical_envelope_missing",
        },
        ("H1", "P4", "V4"): {
            "status": "not_run",
        },
    }

    normalized = query_service._normalize_latest_qc_summary_map(raw_summaries)
    ws_kpi = query_service._build_qc_summary(refs, normalized)
    assert ws_kpi["ready_records"] == 1
    assert ws_kpi["partial_failed_records"] == 1
    assert ws_kpi["technical_error_records"] == 1
    assert ws_kpi["not_run_records"] == 1

    class _StubWorkspace:
        def __init__(self, *, readonly: bool = False):
            self.readonly = readonly

        def _read_luxian_summary_watermark(self, _session):
            return ("wm-align", 1)

        def build_luxian_0609_completed_record_result_summaries(self, **_kwargs):
            return raw_summaries

    class _FakeSession:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def close(self):
            return None

    monkeypatch.setattr(
        result_analysis_module, "CustomQCWorkspaceService", _StubWorkspace
    )
    try:
        svc = Luxian0609ResultAnalysisService(
            record_scope_loader=lambda **_kwargs: records,
            rule_name_loader=lambda: {
                "LX0609-01-01-01": "入院记录时限",
                "LX0609-01-02-01": "首次病程时限",
            },
            session_factory=_FakeSession,
        )
        # 首次调用（写入轻量水印缓存）与二次调用（命中缓存）均须与顶部 KPI 一致
        for _ in range(2):
            analysis = svc.get_analysis(care_phase="discharged")
            assert analysis["kpis"]["scoped_record_total"] == ws_kpi["total_records"]
            assert analysis["kpis"]["ready_record_total"] == ws_kpi["ready_records"] == 1
            assert (
                analysis["kpis"]["partial_failed_record_total"]
                == ws_kpi["partial_failed_records"]
                == 1
            )
            assert (
                analysis["kpis"]["unavailable_result_total"]
                == ws_kpi["technical_error_records"]
                == 1
            )
            # P2 #8：结果分析中的 ICU 全/半角括号也必须归并为一个科室
            rule_01 = next(
                r for r in analysis["rule_distribution"] if r["rule_id"] == "LX0609-01-01-01"
            )
            assert [d["department"] for d in rule_01["department_distribution"]] == [
                "重症医学科（ICU）"
            ]
            assert rule_01["department_distribution"][0]["record_total"] == 2
            assert all(
                item["department"] == "重症医学科（ICU）"
                for item in analysis["record_page"]["items"]
            )
    finally:
        clear_luxian_0609_result_analysis_caches()


# =============================================================================
# P2 #7: 运行病历质控缺失 admission_datetime 时从入院登记/入院记录时间兜底回填
# P2 #8: 重症医学科(ICU) 与 重症医学科（ICU）全/半角括号归并及双向筛选
# =============================================================================


def test_workstation_backfills_inpatient_admission_date_and_merges_icu_brackets(
    monkeypatch,
):
    engine, factory = _make_workstation_sqlite_factory()
    try:
        # 模拟本地 PG cdm.admission_record 存在 record_time 列而 admission_datetime 为空
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE admission_record ADD COLUMN record_time DATETIME"))
            conn.execute(
                text(
                    "INSERT INTO admission_record "
                    "(institute_id, patient_id, visit_id, document_id, name, admission_datetime, record_datetime, record_time) "
                    "VALUES ('H1', 'P-KXB', '2313364', 'DOC-1', '孔祥斌', NULL, NULL, '2026-03-29 10:05:55')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO admission_record "
                    "(institute_id, patient_id, visit_id, document_id, name, admission_datetime, record_datetime, record_time) "
                    "VALUES ('H1', 'P-ZYS', '2273484', 'DOC-2', '周永书', NULL, NULL, '2026-03-08 15:37:48')"
                )
            )

        with factory() as session:
            session.add_all(
                [
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P-KXB",
                        visit_id="2313364",
                        name="孔祥斌",
                        admission_dept_name="关节与运动医学科",
                        discharge_dept_name="关节与运动医学科",
                        admission_datetime=None,
                        discharge_datetime=None,
                        update_time=datetime(2026, 4, 19, 10, 4, 54),
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P-ZYS",
                        visit_id="2273484",
                        name="周永书",
                        admission_dept_name="重症医学科(ICU)",
                        discharge_dept_name="重症医学科（ICU）",
                        admission_datetime=None,
                        discharge_datetime=None,
                        update_time=datetime(2026, 3, 10, 0, 1, 35),
                    ),
                    # 出院病例：1 条出院记录写半角括号，1 条写全角括号
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P-ICU-1",
                        visit_id="V-ICU-1",
                        name="患者甲",
                        discharge_dept_name="重症医学科（ICU）",
                        admission_datetime=datetime(2026, 3, 1, 9, 0, 0),
                        discharge_datetime=datetime(2026, 3, 5, 10, 0, 0),
                    ),
                    MedicalRecordFrontpage(
                        institute_id="H1",
                        patient_id="P-ICU-2",
                        visit_id="V-ICU-2",
                        name="患者乙",
                        discharge_dept_name="重症医学科（ICU）",
                        admission_datetime=datetime(2026, 3, 2, 9, 0, 0),
                        discharge_datetime=datetime(2026, 3, 6, 10, 0, 0),
                    ),
                    DischargeRecord(
                        institute_id="H1",
                        patient_id="P-ICU-1",
                        visit_id="V-ICU-1",
                        document_id="DIS-1",
                        dept_name="重症医学科(ICU)",
                        discharge_time=datetime(2026, 3, 5, 10, 0, 0),
                        update_time=datetime(2026, 3, 5, 11, 0, 0),
                    ),
                    DischargeRecord(
                        institute_id="H1",
                        patient_id="P-ICU-2",
                        visit_id="V-ICU-2",
                        document_id="DIS-2",
                        dept_name=" 重症医学科（ICU） ",
                        discharge_time=datetime(2026, 3, 6, 10, 0, 0),
                        update_time=datetime(2026, 3, 6, 11, 0, 0),
                    ),
                ]
            )
            session.commit()

        inpatient = query_service.get_workstation_data(
            hospital_status="inpatient",
            session_factory=factory,
            settings_loader=_no_demo_settings,
            qc_summary_mode="deferred",
        )
        by_id = {rec["id"]: rec for rec in inpatient["records"]}
        assert by_id["2313364"]["admissionDate"] == "2026-03-29"
        assert by_id["2313364"]["admissionDateDisplay"] == "03-29"
        assert by_id["2273484"]["admissionDate"] == "2026-03-08"
        assert by_id["2273484"]["admissionDateDisplay"] == "03-08"

        discharged = query_service.get_workstation_data(
            hospital_status="discharged",
            session_factory=factory,
            settings_loader=_no_demo_settings,
            qc_summary_mode="deferred",
        )
        dept_totals = {d["name"]: d["total"] for d in discharged["departments"]}
        assert dept_totals["重症医学科（ICU）"] == 2
        assert "重症医学科(ICU)" not in dept_totals
        assert {rec["department"] for rec in discharged["records"]} == {
            "重症医学科（ICU）"
        }

        # 无论前端传半角还是全角括号，均能命中底层两种写法的病历
        for query_dept in ("重症医学科(ICU)", "重症医学科（ICU）", " 重症医学科(ICU) "):
            filtered = query_service.get_workstation_data(
                dept=query_dept,
                hospital_status="discharged",
                session_factory=factory,
                settings_loader=_no_demo_settings,
                qc_summary_mode="deferred",
            )
            assert filtered["total"] == 2
            assert {rec["id"] for rec in filtered["records"]} == {"V-ICU-1", "V-ICU-2"}
    finally:
        engine.dispose()


def test_independent_cdm_catalog_normalizes_and_filters_bracket_departments(monkeypatch):
    from app.database import clinical_connection

    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
            for name in ("mr", "admission_record", "discharge_record"):
                conn.execute(
                    text(
                        f"CREATE TABLE cdm.{name} ("
                        "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                        "name TEXT, dept_name TEXT, admission_datetime TEXT, discharge_time TEXT)"
                    )
                )
            conn.execute(
                text(
                    "INSERT INTO cdm.admission_record VALUES "
                    "('H1','P1','V1','甲','重症医学科(ICU)','2026-03-01 08:00:00',NULL),"
                    "('H1','P2','V2','乙','重症医学科（ICU）','2026-03-02 08:00:00',NULL)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO cdm.discharge_record VALUES "
                    "('H1','P1','V1','甲','重症医学科(ICU)',NULL,'2026-03-05 10:00:00'),"
                    "('H1','P2','V2','乙','重症医学科（ICU）',NULL,'2026-03-06 10:00:00')"
                )
            )
        monkeypatch.setattr(clinical_connection, "get_engine", lambda: engine)
        catalog_service.catalog.cache_clear()

        all_dis = catalog_service.workstation(
            hospital_status="discharged",
            qc_projection_loader=lambda _: {},
        )
        assert all_dis["departments"] == [
            {"name": "重症医学科（ICU）", "total": 2, "warningCount": 0}
        ]
        assert {r["department"] for r in all_dis["records"]} == {"重症医学科（ICU）"}

        half_filtered = catalog_service.workstation(
            dept="重症医学科(ICU)",
            hospital_status="discharged",
            qc_projection_loader=lambda _: {},
        )
        full_filtered = catalog_service.workstation(
            dept="重症医学科（ICU）",
            hospital_status="discharged",
            qc_projection_loader=lambda _: {},
        )
        assert half_filtered["total"] == 2
        assert full_filtered["total"] == 2
    finally:
        catalog_service.catalog.cache_clear()
        engine.dispose()
