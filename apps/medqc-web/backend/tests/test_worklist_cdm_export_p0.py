"""P0-3 / P0-4 / P0-5 focused regression tests for CDM scope/facets, single-DB queries, and Running-QC export."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.access_control import enforce_default_auth
from app.core.security import get_current_user
from app.database import clinical_connection
from app.database.connection import Base
from app.database.models.cdm import (
    AdmissionRecord,
    DischargeRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
    QCResult,
)
from app.routers import qc_sichuan
from app.services import clinical_case_catalog, clinical_read
from app.services.bundles import assembly
from app.services.case_identity import CaseRef
from app.services.doctor_case_scope import DoctorCaseScope
from app.services.medical_records import query_service as query_service_module
from app.services.medical_records.detail_service import InstituteCaseScope
from app.services.qc_workspace.record_repository import RecordRepository


class _DummyQueueService:
    def get_state_map(self, **_kwargs):
        return {}

    def backfill_frontpage_generate(self, **_kwargs):
        return None


def _build_cdm_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
    for model in (InpatRegistration, AdmissionRecord, DischargeRecord):
        model.__table__.to_metadata(MetaData(), schema="cdm").create(engine)
    return engine


# ============================================================================
# P0-3: clinical_case_catalog InstituteCaseScope pushdown + facets + 未分科室
# ============================================================================


def test_cdm_predicates_pushes_institute_id_without_invoking_case_refs(monkeypatch):
    engine = _build_cdm_engine()
    try:
        with Session(engine.execution_options(schema_translate_map={None: "cdm"})) as session:
            session.add_all(
                [
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="本院患者",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 5, 1, 9, 0),
                    ),
                    InpatRegistration(
                        institute_id="H2",
                        patient_id="P2",
                        visit_id="V2",
                        name="外院患者",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 5, 2, 9, 0),
                    ),
                ]
            )
            session.commit()

        monkeypatch.setattr(clinical_connection, "configured", lambda: True)
        monkeypatch.setattr(clinical_connection, "get_engine", lambda: engine)
        clinical_case_catalog.catalog.cache_clear()

        class _ExplodingInstituteScope(InstituteCaseScope):
            @property
            def case_refs(self):
                raise AssertionError("InstituteCaseScope.case_refs must not be invoked in CDM predicates")

        scope = _ExplodingInstituteScope(institute_id="H1")
        source = clinical_case_catalog.catalog(engine, include_frontpage=False)
        clauses = clinical_case_catalog._predicates(source, case_scope=scope)
        compiled = " ".join(str(clause.compile(compile_kwargs={"literal_binds": True})) for clause in clauses)
        assert "institute_id = 'H1'" in compiled
        assert " IN " not in compiled

        for mode in ("deferred", "inline"):
            result = clinical_case_catalog.workstation(
                case_scope=scope,
                qc_summary_mode=mode,
                qc_projection_loader=lambda _refs: {},
            )
            assert result["total"] == 1
            assert [rec["id"] for rec in result["records"]] == ["V1"]
            assert [rec["instituteId"] for rec in result["records"]] == ["H1"]

        # DoctorCaseScope still enforces explicit case_refs tuple predicate
        doc_scope = DoctorCaseScope("H1", "心内科", "张医生", (("H1", "P1", "V1"),))
        doc_clauses = clinical_case_catalog._predicates(source, case_scope=doc_scope)
        doc_compiled = " ".join(str(clause) for clause in doc_clauses)
        assert " IN " in doc_compiled
    finally:
        clinical_case_catalog.catalog.cache_clear()
        engine.dispose()


@pytest.mark.parametrize("mode", ["deferred", "inline"])
def test_cdm_workstation_facets_do_not_collapse_and_unassigned_dept_maps_to_empty(monkeypatch, mode):
    engine = _build_cdm_engine()
    try:
        with Session(engine.execution_options(schema_translate_map={None: "cdm"})) as session:
            session.add_all(
                [
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        name="患者一",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 5, 1, 9, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P2",
                        visit_id="V2",
                        name="患者二",
                        admission_dept_name="外科",
                        admission_datetime=datetime(2026, 5, 2, 9, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P3",
                        visit_id="V3",
                        name="患者三",
                        admission_dept_name=None,
                        admission_datetime=datetime(2026, 5, 3, 9, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P4",
                        visit_id="V4",
                        name="患者四",
                        admission_dept_name="心内科",
                        admission_datetime=datetime(2026, 5, 4, 9, 0),
                    ),
                    AdmissionRecord(
                        institute_id="H1",
                        patient_id="P1",
                        visit_id="V1",
                        document_id="A1",
                        attending_physician_sign="张医生",
                    ),
                    AdmissionRecord(
                        institute_id="H1",
                        patient_id="P2",
                        visit_id="V2",
                        document_id="A2",
                        attending_physician_sign="李医生",
                    ),
                    AdmissionRecord(
                        institute_id="H1",
                        patient_id="P4",
                        visit_id="V4",
                        document_id="A4",
                        attending_physician_sign="王医生",
                    ),
                ]
            )
            session.commit()

        monkeypatch.setattr(clinical_connection, "configured", lambda: True)
        monkeypatch.setattr(clinical_connection, "get_engine", lambda: engine)
        clinical_case_catalog.catalog.cache_clear()

        # Selecting a department must NOT collapse department dropdown options
        by_dept = clinical_case_catalog.workstation(
            dept="心内科",
            qc_summary_mode=mode,
            qc_projection_loader=lambda _refs: {},
        )
        assert by_dept["total"] == 2
        assert {rec["id"] for rec in by_dept["records"]} == {"V1", "V4"}
        dept_facet_map = {item["name"]: item["total"] for item in by_dept["departments"]}
        assert dept_facet_map == {"心内科": 2, "外科": 1, "未分科室": 1}
        doctor_facet_map = {item["name"]: item["total"] for item in by_dept["doctors"]}
        assert doctor_facet_map == {"张医生": 1, "王医生": 1}

        # Selecting a doctor must NOT collapse doctor dropdown options in current dept
        by_dept_and_doctor = clinical_case_catalog.workstation(
            dept="心内科",
            doctor="张医生",
            qc_summary_mode=mode,
            qc_projection_loader=lambda _refs: {},
        )
        assert by_dept_and_doctor["total"] == 1
        assert [rec["id"] for rec in by_dept_and_doctor["records"]] == ["V1"]
        assert {item["name"]: item["total"] for item in by_dept_and_doctor["doctors"]} == {
            "张医生": 1,
            "王医生": 1,
        }
        assert {item["name"]: item["total"] for item in by_dept_and_doctor["departments"]} == {
            "心内科": 1,
        }

        # dept="未分科室" maps to NULL / empty department
        unassigned = clinical_case_catalog.workstation(
            dept="未分科室",
            qc_summary_mode=mode,
            qc_projection_loader=lambda _refs: {},
        )
        assert unassigned["total"] == 1
        assert [rec["id"] for rec in unassigned["records"]] == ["V3"]
        assert {item["name"]: item["total"] for item in unassigned["departments"]} == {
            "心内科": 2,
            "外科": 1,
            "未分科室": 1,
        }
    finally:
        clinical_case_catalog.catalog.cache_clear()
        engine.dispose()


# ============================================================================
# P0-4: single-DB query_service case_scope + visit_index + filters
# ============================================================================


@pytest.fixture()
def single_db_env(monkeypatch):
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)
    monkeypatch.setattr(query_service_module, "clinical_read_schema", lambda: None)
    monkeypatch.setattr(clinical_read, "clinical_read_schema", lambda: None)
    monkeypatch.setattr(query_service_module, "default_workflow_queue_state_service", _DummyQueueService())
    monkeypatch.setattr(
        query_service_module,
        "_load_latest_luxian_0609_qc_summaries",
        lambda refs, **_kwargs: {
            (str(r["institute_id"]), str(r["patient_id"]), str(r["visit_id"])): {"status": "not_run"}
            for r in refs
        },
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            MedicalRecordFrontpage.__table__,
            InpatRegistration.__table__,
            AdmissionRecord.__table__,
            HospitalizationStatusProjection.__table__,
            QCResult.__table__,
        ],
    )
    with Session(engine) as session:
        session.execute(
            text(
                """
                CREATE TABLE discharge_record (
                    institute_id VARCHAR(100),
                    patient_id VARCHAR(100),
                    visit_id VARCHAR(100),
                    document_id VARCHAR(100),
                    dept_name VARCHAR(100),
                    discharge_time DATETIME,
                    update_time DATETIME
                )
                """
            )
        )
        session.execute(
            text(
                """
                CREATE TABLE visit_index (
                    institute_id VARCHAR(100) NOT NULL,
                    patient_id VARCHAR(100) NOT NULL,
                    visit_id VARCHAR(100) NOT NULL,
                    scene_current VARCHAR(32) NOT NULL DEFAULT '',
                    updated_at DATETIME,
                    PRIMARY KEY (institute_id, patient_id, visit_id)
                )
                """
            )
        )
        session.commit()

    def factory():
        return Session(engine)

    monkeypatch.setattr(query_service_module, "_session_factory", factory)
    try:
        yield engine, factory
    finally:
        engine.dispose()


def _insert_visit_index(factory, institute_id: str, patient_id: str, visit_id: str) -> None:
    with factory() as session:
        session.execute(
            text(
                """
                INSERT INTO visit_index (institute_id, patient_id, visit_id, scene_current, updated_at)
                VALUES (:institute_id, :patient_id, :visit_id, 'running', :updated_at)
                """
            ),
            {
                "institute_id": institute_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "updated_at": datetime(2026, 8, 13, 8, 5),
            },
        )
        session.commit()


def test_single_db_non_global_scopes_include_authorized_visit_index_no_frontpage_inpatients(single_db_env):
    _, factory = single_db_env
    with factory() as session:
        session.add_all(
            [
                InpatRegistration(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V-H1-DOC1",
                    name="本院医生一在院患者",
                    admission_dept_name="内科",
                    admission_datetime=datetime(2026, 8, 10, 9, 0),
                ),
                AdmissionRecord(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V-H1-DOC1",
                    document_id="A1",
                    dept_name="内科",
                    attending_physician_sign="王医生",
                    admission_datetime=datetime(2026, 8, 10, 9, 0),
                ),
                InpatRegistration(
                    institute_id="H1",
                    patient_id="P2",
                    visit_id="V-H1-DOC2",
                    name="本院医生二在院患者",
                    admission_dept_name="内科",
                    admission_datetime=datetime(2026, 8, 11, 9, 0),
                ),
                AdmissionRecord(
                    institute_id="H1",
                    patient_id="P2",
                    visit_id="V-H1-DOC2",
                    document_id="A2",
                    dept_name="内科",
                    attending_physician_sign="赵医生",
                    admission_datetime=datetime(2026, 8, 11, 9, 0),
                ),
                InpatRegistration(
                    institute_id="H2",
                    patient_id="P3",
                    visit_id="V-H2-DOC1",
                    name="外院在院患者",
                    admission_dept_name="内科",
                    admission_datetime=datetime(2026, 8, 12, 9, 0),
                ),
                AdmissionRecord(
                    institute_id="H2",
                    patient_id="P3",
                    visit_id="V-H2-DOC1",
                    document_id="A3",
                    dept_name="内科",
                    attending_physician_sign="王医生",
                    admission_datetime=datetime(2026, 8, 12, 9, 0),
                ),
            ]
        )
        session.commit()
    for inst, pat, vis in (
        ("H1", "P1", "V-H1-DOC1"),
        ("H1", "P2", "V-H1-DOC2"),
        ("H2", "P3", "V-H2-DOC1"),
    ):
        _insert_visit_index(factory, inst, pat, vis)

    common = dict(
        session_factory=factory,
        settings_loader=lambda: (SimpleNamespace(), None),
        demo_policy=lambda *_: False,
    )

    # InstituteCaseScope sees H1 no-frontpage inpatients and excludes H2
    mgr_res = query_service_module.get_workstation_data(
        case_scope=InstituteCaseScope("H1"),
        **common,
    )
    assert mgr_res["total"] == 2
    assert {rec["id"] for rec in mgr_res["records"]} == {"V-H1-DOC1", "V-H1-DOC2"}

    # DoctorCaseScope sees ONLY own authorized no-frontpage inpatient
    doc_res = query_service_module.get_workstation_data(
        case_scope=DoctorCaseScope("H1", "内科", "王医生", case_refs=()),
        **common,
    )
    assert doc_res["total"] == 1
    assert [rec["id"] for rec in doc_res["records"]] == ["V-H1-DOC1"]


def test_single_db_dept_unknown_status_today_inpatient_and_visit_id_keyword(single_db_env):
    _, factory = single_db_env
    today_dt = datetime.combine(query_service_module._hospital_today(), datetime.min.time()) + timedelta(hours=8)

    with factory() as session:
        session.add_all(
            [
                MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="VIS_100%Alpha",
                    name="张三",
                    admission_dept_name="内科",
                    admission_datetime=datetime(2026, 8, 1, 9, 0),
                    discharge_datetime=None,
                ),
                MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P2",
                    visit_id="VISX1000Alpha",
                    name="李四",
                    admission_dept_name=None,
                    discharge_dept_name="",
                    admission_datetime=datetime(2026, 8, 2, 9, 0),
                    discharge_datetime=None,
                ),
                MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P3",
                    visit_id="VIS-DISCH",
                    name="王五",
                    admission_dept_name="外科",
                    discharge_dept_name="外科",
                    admission_datetime=datetime(2026, 8, 3, 9, 0),
                    discharge_datetime=datetime(2026, 8, 6, 10, 0),
                ),
                # visit_index record that is locally discharged but still has stale today_inpatient projection
                InpatRegistration(
                    institute_id="H1",
                    patient_id="P4",
                    visit_id="VIS-IDX-DISCH",
                    name="索引已出院",
                    admission_dept_name="内科",
                    admission_datetime=datetime(2026, 8, 4, 9, 0),
                    discharge_datetime=datetime(2026, 8, 7, 10, 0),
                ),
                # visit_index record with unknown projection
                InpatRegistration(
                    institute_id="H1",
                    patient_id="P5",
                    visit_id="VIS-IDX-UNK",
                    name="索引未核验",
                    admission_dept_name="",
                    admission_datetime=datetime(2026, 8, 5, 9, 0),
                    discharge_datetime=None,
                ),
                # Confirmed inpatient projection for P1
                HospitalizationStatusProjection(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="VIS_100%Alpha",
                    status="inpatient",
                    verified_at=today_dt,
                    source="source_active_scope",
                ),
                # Stale today_inpatient projection on locally discharged P4
                HospitalizationStatusProjection(
                    institute_id="H1",
                    patient_id="P4",
                    visit_id="VIS-IDX-DISCH",
                    status="inpatient",
                    verified_at=today_dt,
                    source="source_active_scope",
                ),
                # Explicit unknown projection for P5
                HospitalizationStatusProjection(
                    institute_id="H1",
                    patient_id="P5",
                    visit_id="VIS-IDX-UNK",
                    status="unknown",
                    verified_at=today_dt,
                    source="source_scope_unmatched",
                ),
                QCResult(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="VIS_100%Alpha",
                    qc_type="rule",
                    rule_id="R1",
                    rule_name="规则1",
                    severity="error",
                    status="open",
                ),
                QCResult(
                    institute_id="H1",
                    patient_id="P3",
                    visit_id="VIS-DISCH",
                    qc_type="rule",
                    rule_id="R2",
                    rule_name="规则2",
                    severity="error",
                    status="open",
                ),
            ]
        )
        session.commit()
    _insert_visit_index(factory, "H1", "P4", "VIS-IDX-DISCH")
    _insert_visit_index(factory, "H1", "P5", "VIS-IDX-UNK")

    common = dict(
        session_factory=factory,
        settings_loader=lambda: (SimpleNamespace(), None),
        demo_policy=lambda *_: False,
    )

    # 1. hospital_status="unknown" works without ValueError and matches only unconfirmed records
    unk = query_service_module.get_workstation_data(hospital_status="unknown", **common)
    assert {rec["id"] for rec in unk["records"]} == {"VISX1000Alpha", "VIS-IDX-UNK"}
    assert unk["total"] == 2

    # 2. dept="未分科室" maps to NULL / empty department in both frontpage and visit_index
    unassigned = query_service_module.get_workstation_data(dept="未分科室", **common)
    assert {rec["id"] for rec in unassigned["records"]} == {"VISX1000Alpha", "VIS-IDX-UNK"}
    assert unassigned["total"] == 2

    # 3. sync_scope="today_inpatient" excludes locally discharged visit_index record (P4)
    today_inp = query_service_module.get_workstation_data(sync_scope="today_inpatient", **common)
    assert [rec["id"] for rec in today_inp["records"]] == ["VIS_100%Alpha"]

    # 4. visit_id keyword search is case-insensitive and escapes % / _ wildcards
    kw_res = query_service_module.get_workstation_data(keyword="vis_100%alpha", **common)
    assert [rec["id"] for rec in kw_res["records"]] == ["VIS_100%Alpha"]

    # 5. list_medical_records & get_stats apply dept when case_scope is not None
    scope = InstituteCaseScope("H1")
    listed_internal = query_service_module.list_medical_records(dept="内科", case_scope=scope)
    assert [item["visit_id"] for item in listed_internal["items"]] == ["VIS_100%Alpha"]
    listed_unassigned = query_service_module.list_medical_records(dept="未分科室", case_scope=scope)
    assert [item["visit_id"] for item in listed_unassigned["items"]] == ["VISX1000Alpha"]
    listed_by_visit = query_service_module.list_medical_records(keyword="vis_100%", case_scope=scope)
    assert [item["visit_id"] for item in listed_by_visit["items"]] == ["VIS_100%Alpha"]

    stats_internal = query_service_module.get_stats(dept="内科", case_scope=scope)
    assert stats_internal["total_records"] == 1
    assert stats_internal["total_qc_issues"] == 1
    stats_unassigned = query_service_module.get_stats(dept="未分科室", case_scope=scope)
    assert stats_unassigned["total_records"] == 1
    assert stats_unassigned["total_qc_issues"] == 0


# ============================================================================
# P0-5: Running-QC export (scope="running") resolves verified inpatient records
# ============================================================================


def test_running_qc_export_collect_count_and_endpoint_resolve_verified_inpatient(monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for model in (InpatRegistration, AdmissionRecord, DischargeRecord, HospitalizationStatusProjection):
        model.__table__.create(engine)

    running_ref = CaseRef("H1", "P-RUN", "V-RUN")
    unverified_ref = CaseRef("H1", "P-UNK", "V-UNK")
    stale_ref = CaseRef("H1", "P-STALE", "V-STALE")
    final_ref = CaseRef("H1", "P-FIN", "V-FIN")
    now = datetime.now()

    try:
        with Session(engine) as session:
            session.add_all(
                [
                    InpatRegistration(
                        **running_ref.as_dict(),
                        name="在院患者甲",
                        admission_dept_name="呼吸内科",
                        admission_datetime=now - timedelta(days=3),
                    ),
                    AdmissionRecord(
                        **running_ref.as_dict(),
                        document_id="A-RUN",
                        dept_name="呼吸内科",
                        attending_physician_sign="陈医生",
                        admission_datetime=now - timedelta(days=3),
                    ),
                    HospitalizationStatusProjection(
                        **running_ref.as_dict(),
                        status="inpatient",
                        verified_at=now - timedelta(minutes=10),
                        source="source_active_scope",
                    ),
                    InpatRegistration(
                        **unverified_ref.as_dict(),
                        name="未核验患者",
                        admission_dept_name="呼吸内科",
                        admission_datetime=now - timedelta(days=2),
                    ),
                    InpatRegistration(
                        **stale_ref.as_dict(),
                        name="过期核验患者",
                        admission_dept_name="呼吸内科",
                        admission_datetime=now - timedelta(days=4),
                    ),
                    HospitalizationStatusProjection(
                        **stale_ref.as_dict(),
                        status="inpatient",
                        verified_at=now - timedelta(days=2, seconds=5),
                        source="source_active_scope",
                    ),
                    InpatRegistration(
                        **final_ref.as_dict(),
                        name="出院患者乙",
                        admission_dept_name="呼吸内科",
                        admission_datetime=now - timedelta(days=5),
                        discharge_datetime=now - timedelta(days=1),
                    ),
                ]
            )
            session.commit()

        repository = RecordRepository(session_factory=lambda: Session(engine))

        # 1. Selected running export resolves verified inpatient as scope=="running"
        selected_rows = repository.collect_records(
            scope="running",
            department=None,
            doctor=None,
            date_field="admission",
            start_date=None,
            end_date=None,
            keyword=None,
            record_refs=[running_ref],
        )
        assert len(selected_rows) == 1
        assert selected_rows[0]["visit_id"] == "V-RUN"
        assert selected_rows[0]["scope"] == "running"
        assert selected_rows[0]["qc_scope"] == "running"
        assert selected_rows[0]["qc_scene_reason"] == "verified_inpatient_state"

        # 2. Filtered running export & count return ONLY verified running inpatient
        assert (
            repository.count_records(
                scope="running",
                department="呼吸内科",
                doctor=None,
                date_field="admission",
                start_date=None,
                end_date=None,
                keyword=None,
            )
            == 1
        )
        filtered_rows = repository.collect_records(
            scope="running",
            department="呼吸内科",
            doctor=None,
            date_field="admission",
            start_date=None,
            end_date=None,
            keyword=None,
        )
        assert [row["visit_id"] for row in filtered_rows] == ["V-RUN"]

        # 3. Unverified & stale projections remain unknown (never falsely admitted to running)
        all_rows = {
            row["visit_id"]: row
            for row in repository.collect_records(
                scope="all",
                department=None,
                doctor=None,
                date_field="admission",
                start_date=None,
                end_date=None,
                keyword=None,
            )
        }
        assert all_rows["V-UNK"]["qc_scope"] == "unknown"
        assert all_rows["V-STALE"]["qc_scope"] == "unknown"
        assert all_rows["V-FIN"]["qc_scope"] == "final"

        # 4. End-to-end POST /api/v1/qc/sichuan/workspace/records/export for both selected & filtered
        class _WorkspaceAdapter:
            def __init__(self, repo: RecordRepository):
                self._repo = repo
                self.bulk_refs = []

            def collect_records(self, **kwargs):
                return self._repo.collect_records(**kwargs)

            def count_records(self, **kwargs):
                return self._repo.count_records(**kwargs)

            def build_latest_luxian_0609_record_result_dtos(self, *, record_refs):
                self.bulk_refs.append(record_refs)
                return {}

        adapter = _WorkspaceAdapter(repository)
        monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: adapter)
        monkeypatch.setattr("app.services.saved_result_access.saved_result_institute_scope", lambda _uid: None)

        app = FastAPI()
        app.include_router(qc_sichuan.router)
        app.dependency_overrides[enforce_default_auth] = lambda: None
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "u-admin",
            "email": "admin@hospital.local",
            "roles": ["admin"],
        }

        with TestClient(app) as client:
            selected_resp = client.post(
                "/api/v1/qc/sichuan/workspace/records/export",
                json={
                    "scope": "running",
                    "date_field": "admission",
                    "record_refs": [running_ref.as_dict()],
                },
            )
            assert selected_resp.status_code == 200
            assert selected_resp.content.startswith(b"PK")

            filtered_resp = client.post(
                "/api/v1/qc/sichuan/workspace/records/export",
                json={
                    "scope": "running",
                    "department": "呼吸内科",
                    "date_field": "admission",
                },
            )
            assert filtered_resp.status_code == 200
            assert filtered_resp.content.startswith(b"PK")

        assert adapter.bulk_refs == [
            [running_ref.as_dict()],
            [running_ref.as_dict()],
        ]
    finally:
        engine.dispose()
