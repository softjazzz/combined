"""病历池住院状态口径统一（P0）与最近质控任务样本验证隔离（P1）回归单测。"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

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
from app.services import clinical_case_catalog
from app.services import custom_qc_workspace_service as workspace_module
from app.services.bundles import assembly
from app.services.case_identity import CaseRef
from app.services.case_scope_service import HospitalizationScopeResult
from app.services.medical_records import hospitalization_status_service as status_service_module
from app.services.medical_records import query_service as query_service_module


def _settings_loader():
    return SimpleNamespace(include_demo_records=False), None


def _no_demo_policy(_settings, _real_count: int) -> bool:
    return False


def _setup_worklist_tables(engine, *, schema: str | None = None) -> None:
    if schema:
        with engine.begin() as conn:
            conn.execute(text(f"ATTACH DATABASE ':memory:' AS {schema}"))
        target_meta = sa.MetaData(schema=schema)
        for model in (
            MedicalRecordFrontpage,
            InpatRegistration,
            AdmissionRecord,
            DischargeRecord,
            HospitalizationStatusProjection,
        ):
            model.__table__.to_metadata(target_meta, schema=schema)
        target_meta.create_all(engine)
        QCResult.__table__.create(engine)
    else:
        Base.metadata.create_all(
            engine,
            tables=[
                MedicalRecordFrontpage.__table__,
                InpatRegistration.__table__,
                AdmissionRecord.__table__,
                DischargeRecord.__table__,
                HospitalizationStatusProjection.__table__,
                QCResult.__table__,
            ],
        )


def _seed_conflicting_worklist_data(session: Session, *, schema: str | None = None) -> None:
    if schema:
        session.connection(execution_options={"schema_translate_map": {None: schema}})

    verified_at = datetime(2026, 4, 15, 9, 0, 0)
    session.add_all(
        [
            # 1) 4 条已有明确出院日期（含未来日期 2026-09-21），但投影表误留存为 inpatient/active
            MedicalRecordFrontpage(
                institute_id="H1",
                patient_id="P-TONG",
                visit_id="V-TONG",
                name="童世先",
                admission_dept_name="呼吸内科",
                discharge_dept_name="呼吸内科",
                admission_datetime=datetime(2026, 9, 10, 8, 0),
                discharge_datetime=datetime(2026, 9, 21, 10, 0),
            ),
            MedicalRecordFrontpage(
                institute_id="H1",
                patient_id="P-CHENG",
                visit_id="V-CHENG",
                name="程思明",
                admission_dept_name="心内科",
                discharge_dept_name="心内科",
                admission_datetime=datetime(2026, 9, 12, 9, 0),
                discharge_datetime=datetime(2026, 9, 21, 11, 0),
            ),
            MedicalRecordFrontpage(
                institute_id="H1",
                patient_id="P-LI",
                visit_id="V-LI",
                name="李良友",
                admission_dept_name="神经内科",
                discharge_dept_name="神经内科",
                admission_datetime=datetime(2026, 9, 15, 8, 30),
                discharge_datetime=None,
            ),
            MedicalRecordFrontpage(
                institute_id="H1",
                patient_id="P-YOU",
                visit_id="V-YOU",
                name="游书高",
                admission_dept_name="消化内科",
                discharge_dept_name="消化内科",
                admission_datetime=datetime(2026, 9, 14, 10, 0),
                discharge_datetime=None,
            ),
            # 2) 2 条真正未出院的在院患者
            MedicalRecordFrontpage(
                institute_id="H1",
                patient_id="P-KONG",
                visit_id="V-KONG",
                name="孔祥斌",
                admission_dept_name="骨科",
                admission_datetime=datetime(2026, 4, 10, 8, 0),
                discharge_datetime=None,
            ),
            MedicalRecordFrontpage(
                institute_id="H1",
                patient_id="P-ZHOU",
                visit_id="V-ZHOU",
                name="周永书",
                admission_dept_name="普外科",
                admission_datetime=datetime(2026, 4, 12, 9, 0),
                discharge_datetime=None,
            ),
            # 3) 1 条无出院证据且投影为 unknown
            MedicalRecordFrontpage(
                institute_id="H1",
                patient_id="P-UNK",
                visit_id="V-UNK",
                name="状态未知患者",
                admission_dept_name="内分泌科",
                admission_datetime=datetime(2026, 4, 1, 8, 0),
                discharge_datetime=None,
            ),
            # 出院记录：李良友有出院时间，游书高仅有有效出院文书无时间
            DischargeRecord(
                institute_id="H1",
                patient_id="P-LI",
                visit_id="V-LI",
                document_id="DR-LI-1",
                dept_name="神经内科",
                discharge_time=datetime(2026, 9, 21, 14, 0),
                update_time=datetime(2026, 9, 21, 14, 30),
            ),
            DischargeRecord(
                institute_id="H1",
                patient_id="P-YOU",
                visit_id="V-YOU",
                document_id="DR-YOU-1",
                dept_name="消化内科",
                discharge_time=None,
                update_time=datetime(2026, 9, 21, 15, 0),
            ),
            # 过期/冲突投影：4 位已出院患者在投影表里仍被标为 inpatient / active
            HospitalizationStatusProjection(
                institute_id="H1",
                patient_id="P-TONG",
                visit_id="V-TONG",
                status="inpatient",
                verified_at=verified_at,
                source="inpat_registration",
            ),
            HospitalizationStatusProjection(
                institute_id="H1",
                patient_id="P-CHENG",
                visit_id="V-CHENG",
                status="active",
                verified_at=verified_at,
                source="source_active_scope",
            ),
            HospitalizationStatusProjection(
                institute_id="H1",
                patient_id="P-LI",
                visit_id="V-LI",
                status="inpatient",
                verified_at=verified_at,
                source="inpat_registration",
            ),
            HospitalizationStatusProjection(
                institute_id="H1",
                patient_id="P-YOU",
                visit_id="V-YOU",
                status="inpatient",
                verified_at=verified_at,
                source="inpat_registration",
            ),
            HospitalizationStatusProjection(
                institute_id="H1",
                patient_id="P-KONG",
                visit_id="V-KONG",
                status="inpatient",
                verified_at=verified_at,
                source="inpat_registration",
            ),
            HospitalizationStatusProjection(
                institute_id="H1",
                patient_id="P-ZHOU",
                visit_id="V-ZHOU",
                status="inpatient",
                verified_at=verified_at,
                source="inpat_registration",
            ),
            HospitalizationStatusProjection(
                institute_id="H1",
                patient_id="P-UNK",
                visit_id="V-UNK",
                status="unknown",
                verified_at=verified_at,
                source="source_scope_unmatched",
            ),
        ]
    )
    session.commit()


@pytest.mark.parametrize("schema_mode", ["single", "split"])
def test_worklist_row_status_matches_filter_when_projection_conflicts_with_discharge(
    monkeypatch, schema_mode: str
):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", schema_mode)
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(
        query_service_module.default_workflow_queue_state_service,
        "get_state_map",
        lambda **_: {},
    )
    monkeypatch.setattr(
        query_service_module.default_workflow_queue_state_service,
        "backfill_frontpage_generate",
        lambda **_: None,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    schema = "cdm" if schema_mode == "split" else None
    try:
        _setup_worklist_tables(engine, schema=schema)
        with Session(engine) as session:
            _seed_conflicting_worklist_data(session, schema=schema)

        common = dict(
            page=1,
            page_size=20,
            session_factory=lambda: Session(engine),
            settings_loader=_settings_loader,
            demo_policy=_no_demo_policy,
            qc_projection_loader=lambda _: {},
        )

        all_res = query_service_module.get_workstation_data(hospital_status="all", **common)
        inpatient_res = query_service_module.get_workstation_data(hospital_status="inpatient", **common)
        discharged_res = query_service_module.get_workstation_data(hospital_status="discharged", **common)
        unknown_res = query_service_module.get_workstation_data(hospital_status="unknown", **common)

        by_id = {rec["id"]: rec for rec in all_res["records"]}
        assert all_res["total"] == 7

        # 1) 列表行状态绝不允许在存在出院日期/出院文书时返回 inpatient/active
        for visit_id in ("V-TONG", "V-CHENG", "V-LI", "V-YOU"):
            assert by_id[visit_id]["hospitalizationStatus"] == "discharged"
            assert by_id[visit_id]["hospitalizationStatusSource"] == "local_discharge_evidence"
            assert by_id[visit_id]["hospitalizationStatusVerifiedAt"] == ""

        assert by_id["V-TONG"]["dischargeDate"] == "2026-09-21"
        assert by_id["V-TONG"]["days"] == 11
        assert by_id["V-CHENG"]["days"] == 9
        assert by_id["V-LI"]["dischargeDate"] == "2026-09-21"
        assert by_id["V-LI"]["days"] == 6
        assert by_id["V-YOU"]["dischargeDate"] == ""

        assert by_id["V-KONG"]["hospitalizationStatus"] == "inpatient"
        assert by_id["V-ZHOU"]["hospitalizationStatus"] == "inpatient"
        assert by_id["V-UNK"]["hospitalizationStatus"] == "unknown"

        # 2) 筛选集合与行展示状态 100% 闭环一致
        assert inpatient_res["total"] == 2
        assert {rec["id"] for rec in inpatient_res["records"]} == {"V-KONG", "V-ZHOU"}
        assert all(rec["hospitalizationStatus"] == "inpatient" for rec in inpatient_res["records"])

        assert discharged_res["total"] == 4
        assert {rec["id"] for rec in discharged_res["records"]} == {
            "V-TONG",
            "V-CHENG",
            "V-LI",
            "V-YOU",
        }
        assert all(rec["hospitalizationStatus"] == "discharged" for rec in discharged_res["records"])

        assert unknown_res["total"] == 1
        assert {rec["id"] for rec in unknown_res["records"]} == {"V-UNK"}
        assert all(rec["hospitalizationStatus"] == "unknown" for rec in unknown_res["records"])
    finally:
        engine.dispose()


def test_worklist_visit_index_row_status_respects_local_discharge_over_stale_projection(monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(
        query_service_module.default_workflow_queue_state_service,
        "get_state_map",
        lambda **_: {},
    )
    monkeypatch.setattr(
        query_service_module.default_workflow_queue_state_service,
        "backfill_frontpage_generate",
        lambda **_: None,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    try:
        _setup_worklist_tables(engine, schema=None)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE visit_index ("
                    "institute_id TEXT, patient_id TEXT, visit_id TEXT)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO visit_index VALUES ('H1', 'P-IDX-OUT', 'V-IDX-OUT'), "
                    "('H1', 'P-IDX-IN', 'V-IDX-IN')"
                )
            )
        verified_at = datetime(2026, 4, 15, 9, 0, 0)
        with Session(engine) as session:
            session.add_all(
                [
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P-IDX-OUT",
                        visit_id="V-IDX-OUT",
                        name="索引已出院",
                        admission_dept_name="呼吸内科",
                        admission_datetime=datetime(2026, 9, 10, 8, 0),
                        discharge_datetime=datetime(2026, 9, 21, 10, 0),
                    ),
                    InpatRegistration(
                        institute_id="H1",
                        patient_id="P-IDX-IN",
                        visit_id="V-IDX-IN",
                        name="索引在院",
                        admission_dept_name="呼吸内科",
                        admission_datetime=datetime(2026, 4, 10, 8, 0),
                        discharge_datetime=None,
                    ),
                    HospitalizationStatusProjection(
                        institute_id="H1",
                        patient_id="P-IDX-OUT",
                        visit_id="V-IDX-OUT",
                        status="inpatient",
                        verified_at=verified_at,
                        source="source_active_scope",
                    ),
                    HospitalizationStatusProjection(
                        institute_id="H1",
                        patient_id="P-IDX-IN",
                        visit_id="V-IDX-IN",
                        status="inpatient",
                        verified_at=verified_at,
                        source="source_active_scope",
                    ),
                ]
            )
            session.commit()

        common = dict(
            page=1,
            page_size=20,
            session_factory=lambda: Session(engine),
            settings_loader=_settings_loader,
            demo_policy=_no_demo_policy,
            qc_projection_loader=lambda _: {},
        )
        all_res = query_service_module.get_workstation_data(hospital_status="all", **common)
        by_id = {rec["id"]: rec for rec in all_res["records"]}
        assert by_id["V-IDX-OUT"]["hospitalizationStatus"] == "discharged"
        assert by_id["V-IDX-IN"]["hospitalizationStatus"] == "inpatient"

        inp = query_service_module.get_workstation_data(hospital_status="inpatient", **common)
        disch = query_service_module.get_workstation_data(hospital_status="discharged", **common)
        assert [rec["id"] for rec in inp["records"]] == ["V-IDX-IN"]
        assert [rec["id"] for rec in disch["records"]] == ["V-IDX-OUT"]
    finally:
        engine.dispose()


def test_reconcile_never_marks_active_when_discharge_evidence_exists():
    verified_at = datetime(2026, 4, 15, 9, 0)
    source_rows = (
        {
            "institute_id": "H1",
            "patient_id": "P-FUTURE-ACTIVE",
            "visit_id": "V-FUTURE-ACTIVE",
            "hospitalization_status": "active",
            "source_table": "inpat_registration",
        },
        {
            "institute_id": "H1",
            "patient_id": "P-DOC-ACTIVE",
            "visit_id": "V-DOC-ACTIVE",
            "hospitalization_status": "active",
            "source_table": "inpat_registration",
        },
        {
            "institute_id": "H1",
            "patient_id": "P-REAL-ACTIVE",
            "visit_id": "V-REAL-ACTIVE",
            "hospitalization_status": "active",
            "source_table": "inpat_registration",
        },
    )
    source_result = HospitalizationScopeResult(
        case_refs=tuple(CaseRef.from_mapping(row) for row in source_rows),
        selected=source_rows,
        all_selected=source_rows,
        sources_used=("inpat_registration",),
        source_status="ready",
        warnings=(),
    )

    projections = status_service_module.reconcile_hospitalization_statuses(
        local_identities={
            ("H1", "P-FUTURE-ACTIVE", "V-FUTURE-ACTIVE"),
            ("H1", "P-DOC-ACTIVE", "V-DOC-ACTIVE"),
            ("H1", "P-REAL-ACTIVE", "V-REAL-ACTIVE"),
        },
        local_discharge_times={
            ("H1", "P-FUTURE-ACTIVE", "V-FUTURE-ACTIVE"): datetime(2026, 9, 21, 10, 0),
        },
        local_discharge_doc_identities={("H1", "P-DOC-ACTIVE", "V-DOC-ACTIVE")},
        source_result=source_result,
        verified_at=verified_at,
    )
    by_visit = {row["visit_id"]: row for row in projections}
    # 即使源库报告 active，只要存在本地未来出院日期，也绝不可写成 inpatient
    assert by_visit["V-FUTURE-ACTIVE"]["status"] == "unknown"
    # 存在有效出院文书（无出院时间）时直接归入 discharged
    assert by_visit["V-DOC-ACTIVE"]["status"] == "discharged"
    assert by_visit["V-REAL-ACTIVE"]["status"] == "inpatient"


def test_independent_cdm_filter_and_display_agree_on_dirty_discharge_value(monkeypatch):
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
            for table_name in ("mr", "admission_record", "discharge_record"):
                conn.execute(
                    text(
                        f"CREATE TABLE cdm.{table_name}("
                        "institute_id TEXT, patient_id TEXT, visit_id TEXT, "
                        "admission_datetime TEXT, discharge_datetime TEXT)"
                    )
                )
            conn.execute(
                text(
                    "INSERT INTO cdm.admission_record VALUES "
                    "('H1', 'P-OK', 'V-OK', '2026-09-10 08:00:00', NULL), "
                    "('H1', 'P-DIRTY', 'V-DIRTY', '2026-09-10 08:00:00', NULL), "
                    "('H1', 'P-OPEN', 'V-OPEN', '2026-09-11 08:00:00', NULL)"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO cdm.discharge_record VALUES "
                    "('H1', 'P-OK', 'V-OK', NULL, '2026-09-21 10:00:00'), "
                    "('H1', 'P-DIRTY', 'V-DIRTY', NULL, 'invalid-date')"
                )
            )
        clinical_case_catalog.catalog.cache_clear()
        monkeypatch.setattr(clinical_connection, "get_engine", lambda: engine)

        discharged = clinical_case_catalog.workstation(
            hospital_status="discharged", qc_projection_loader=lambda _: {}
        )
        unknown = clinical_case_catalog.workstation(
            hospital_status="unknown", qc_projection_loader=lambda _: {}
        )
        inpatient = clinical_case_catalog.workstation(
            hospital_status="inpatient", qc_projection_loader=lambda _: {}
        )

        assert [r["id"] for r in discharged["records"]] == ["V-OK"]
        assert all(r["hospitalizationStatus"] == "discharged" for r in discharged["records"])
        assert {r["id"] for r in unknown["records"]} == {"V-DIRTY", "V-OPEN"}
        assert all(r["hospitalizationStatus"] == "unknown" for r in unknown["records"])
        assert inpatient["total"] == 0
    finally:
        clinical_case_catalog.catalog.cache_clear()
        engine.dispose()


@pytest.fixture
def batch_jobs_store(monkeypatch):
    metadata = sa.MetaData()
    text_cols = (
        "id",
        "draft_id",
        "rule_code",
        "rule_name",
        "scene",
        "scope",
        "status",
        "job_kind",
        "filters_json",
        "created_by",
        "parent_job_id",
        "record_ids_json",
        "summary_json",
        "items_json",
        "failed_records_json",
    )
    table = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        *(sa.Column(name, sa.Text) for name in text_cols),
        *(sa.Column(name, sa.DateTime) for name in ("created_at", "started_at", "finished_at", "updated_at")),
        *(
            sa.Column(name, sa.Integer)
            for name in ("total_records", "success_count", "failed_count", "issue_records", "compliant_records")
        ),
    )
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)

    base_time = datetime(2026, 9, 20, 8, 0, 0)
    rows = [
        # 2 条病历池常规质控任务（较早创建，且带 validation_mode="programmatic" 以防误伤）
        dict(
            id="pool-job-1",
            draft_id="sichuan-rule-library",
            rule_code="SC-BATCH",
            rule_name="泸县0609质控点验证 v1批量任务(10条规则)",
            scene="final",
            scope="all",
            status="completed",
            job_kind="single",
            filters_json=json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_name": "泸县0609质控点验证 v1",
                    "source": "sichuan_rule_workspace",
                    "validation_mode": "programmatic",
                },
                ensure_ascii=False,
            ),
            created_by="u-1",
            parent_job_id=None,
            record_ids_json='["V-1"]',
            summary_json=json.dumps({"total_records": 1, "rule_set_key": "luxian_0609_qc_v1"}),
            items_json="[]",
            failed_records_json="[]",
            created_at=base_time + timedelta(minutes=1),
            total_records=1,
            success_count=1,
            failed_count=0,
            issue_records=0,
            compliant_records=1,
        ),
        dict(
            id="pool-job-2",
            draft_id="sichuan-rule-library",
            rule_code="SC-BATCH",
            rule_name="泸县0609质控点验证 v1批量任务(10条规则)",
            scene="final",
            scope="final",
            status="queued",
            job_kind="single",
            filters_json=json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_name": "泸县0609质控点验证 v1",
                    "source": "sichuan_rule_workspace",
                },
                ensure_ascii=False,
            ),
            created_by="u-1",
            parent_job_id=None,
            record_ids_json='["V-2"]',
            summary_json=json.dumps({"total_records": 2, "rule_set_key": "luxian_0609_qc_v1"}),
            items_json="[]",
            failed_records_json="[]",
            created_at=base_time + timedelta(minutes=2),
            total_records=2,
            success_count=0,
            failed_count=0,
            issue_records=0,
            compliant_records=0,
        ),
        # 3 条更新的客户样本验证任务（同为 luxian_0609_qc_v1，但来自 sample pool）
        dict(
            id="val-job-1",
            draft_id="sichuan-rule-library",
            rule_code="SC-BATCH",
            rule_name="泸县0609质控点验证 v1",
            scene="final",
            scope="final",
            status="queued",
            job_kind="single",
            filters_json=json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_name": "泸县0609质控点验证 v1",
                    "source": "manual_problem_sample_pool",
                    "sample_pool_id": "sample-pool-uuid-1",
                    "validation_mode": "customer",
                },
                ensure_ascii=False,
            ),
            created_by="u-1",
            parent_job_id=None,
            record_ids_json='["V-S1"]',
            summary_json=json.dumps({"total_records": 5, "rule_set_key": "luxian_0609_qc_v1"}),
            items_json="[]",
            failed_records_json="[]",
            created_at=base_time + timedelta(minutes=3),
            total_records=5,
            success_count=0,
            failed_count=0,
            issue_records=0,
            compliant_records=0,
        ),
        dict(
            id="val-job-2",
            draft_id="sichuan-rule-library",
            rule_code="SC-BATCH",
            rule_name="泸县0609质控点验证 v1",
            scene="final",
            scope="final",
            status="queued",
            job_kind="single",
            filters_json=json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_name": "泸县0609质控点验证 v1",
                    "source": "manual_sample_formal_fast_screen_full",
                    "sample_pool_id": "sample-pool-uuid-2",
                    "validation_mode": "formal_fast_screen_full",
                },
                ensure_ascii=False,
            ),
            created_by="u-1",
            parent_job_id=None,
            record_ids_json='["V-S2"]',
            summary_json=json.dumps({"total_records": 8, "rule_set_key": "luxian_0609_qc_v1"}),
            items_json="[]",
            failed_records_json="[]",
            created_at=base_time + timedelta(minutes=4),
            total_records=8,
            success_count=0,
            failed_count=0,
            issue_records=0,
            compliant_records=0,
        ),
        dict(
            id="val-job-3",
            draft_id="sichuan-rule-library",
            rule_code="SC-BATCH",
            rule_name="泸县0609质控点验证 v1",
            scene="final",
            scope="final",
            status="queued",
            job_kind="single",
            filters_json=json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_name": "泸县0609质控点验证 v1",
                    "sample_pool_id": "sample-pool-uuid-3",
                },
                ensure_ascii=False,
            ),
            created_by="u-1",
            parent_job_id=None,
            record_ids_json='["V-S3"]',
            summary_json=json.dumps({"total_records": 3, "rule_set_key": "luxian_0609_qc_v1"}),
            items_json="[]",
            failed_records_json="[]",
            created_at=base_time + timedelta(minutes=5),
            total_records=3,
            success_count=0,
            failed_count=0,
            issue_records=0,
            compliant_records=0,
        ),
    ]
    with engine.begin() as conn:
        conn.execute(table.insert(), rows)

    service = workspace_module.CustomQCWorkspaceService.__new__(
        workspace_module.CustomQCWorkspaceService
    )
    service._batch_job_table = table
    monkeypatch.setattr(workspace_module, "_session", sessionmaker(bind=engine))
    statements: list[str] = []
    sa.event.listen(
        engine,
        "before_cursor_execute",
        lambda conn, cursor, statement, *args: statements.append(statement),
    )
    yield service, statements
    engine.dispose()


def test_workspace_service_exclude_validation_filters_before_pagination_and_keeps_overview_light(
    batch_jobs_store,
):
    service, statements = batch_jobs_store

    # 默认行为向后兼容：返回全部 5 条（含样本验证）
    all_full = service.list_batch_jobs(created_by="u-1", page=1, page_size=2)
    assert all_full.total == 5
    assert [row["id"] for row in all_full.items] == ["val-job-3", "val-job-2"]

    # 开启 exclude_validation=True：在分页前排除 3 条样本验证任务，第 1 页直接返回 2 条病历池任务
    filtered_full = service.list_batch_jobs(
        created_by="u-1", page=1, page_size=2, exclude_validation=True
    )
    assert filtered_full.total == 2
    assert [row["id"] for row in filtered_full.items] == ["pool-job-2", "pool-job-1"]

    # 概览模式同步支持 exclude_validation=True，且绝不读取大 JSON 列
    statements.clear()
    filtered_overview = service.list_batch_job_overviews(
        created_by="u-1", page=1, page_size=2, exclude_validation=True
    )
    assert filtered_overview.total == 2
    assert [row["id"] for row in filtered_overview.items] == ["pool-job-2", "pool-job-1"]
    for sql in statements:
        assert "summary_json" not in sql
        assert "items_json" not in sql
        assert "failed_records_json" not in sql


def test_batch_jobs_endpoint_exposes_safe_origin_fields_and_supports_exclude_validation(
    monkeypatch, batch_jobs_store
):
    service, _ = batch_jobs_store
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda *, readonly=False: service)
    monkeypatch.setattr(qc_sichuan, "_is_workspace_batch_job", lambda job: True)

    app = FastAPI()
    app.include_router(qc_sichuan.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-1", "roles": ["qc_manager"]}
    client = TestClient(app)

    # 1) 默认全量查询：返回 is_sample_validation 与 task_origin，且不泄露 filters/sample_pool_id
    resp_all = client.get("/api/v1/qc/sichuan/workspace/batch-jobs?page=1&page_size=10")
    assert resp_all.status_code == 200
    payload_all = resp_all.json()["data"]
    assert payload_all["total"] == 5
    by_id = {item["id"]: item for item in payload_all["items"]}
    assert by_id["val-job-1"]["is_sample_validation"] is True
    assert by_id["val-job-1"]["task_origin"] == "sample_validation"
    assert by_id["val-job-2"]["is_sample_validation"] is True
    assert by_id["val-job-3"]["is_sample_validation"] is True
    assert by_id["pool-job-1"]["is_sample_validation"] is False
    assert by_id["pool-job-1"]["task_origin"] == "record_pool"
    assert by_id["pool-job-2"]["is_sample_validation"] is False
    assert by_id["pool-job-2"]["task_origin"] == "record_pool"
    assert "sample-pool-uuid" not in json.dumps(payload_all)
    assert "filters" not in by_id["val-job-1"]

    # 2) exclude_validation=true（完整列表）
    resp_filtered = client.get(
        "/api/v1/qc/sichuan/workspace/batch-jobs?page=1&page_size=10&exclude_validation=true"
    )
    assert resp_filtered.status_code == 200
    payload_filtered = resp_filtered.json()["data"]
    assert payload_filtered["total"] == 2
    assert [item["id"] for item in payload_filtered["items"]] == ["pool-job-2", "pool-job-1"]
    assert all(item["is_sample_validation"] is False for item in payload_filtered["items"])
    assert all(item["task_origin"] == "record_pool" for item in payload_filtered["items"])

    # 3) exclude_validation=true（overview 模式）
    resp_overview = client.get(
        "/api/v1/qc/sichuan/workspace/batch-jobs?view=overview&page=1&page_size=10&exclude_validation=true"
    )
    assert resp_overview.status_code == 200
    payload_overview = resp_overview.json()["data"]
    assert payload_overview["total"] == 2
    assert [item["id"] for item in payload_overview["items"]] == ["pool-job-2", "pool-job-1"]
    assert all(item["is_sample_validation"] is False for item in payload_overview["items"])
    assert all(item["task_origin"] == "record_pool" for item in payload_overview["items"])


@pytest.mark.asyncio
async def test_batch_jobs_endpoint_direct_python_call_keeps_default_false(monkeypatch):
    captured = []

    def stub_list_batch_jobs(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(items=[], total=0, page=1, page_size=10)

    monkeypatch.setattr(
        qc_sichuan,
        "_sichuan_workspace_service",
        lambda *, readonly=False: SimpleNamespace(list_batch_jobs=stub_list_batch_jobs),
    )
    await qc_sichuan.list_workspace_batch_jobs(
        Request({"type": "http", "headers": []}),
        status=None,
        scope=None,
        q=None,
        executor_type=None,
        cache_hit=None,
        created_start_date=None,
        created_end_date=None,
        record_id=None,
        view=None,
        page=1,
        page_size=10,
        current_user={"id": "u-1"},
    )
    assert len(captured) == 1
    assert "exclude_validation" not in captured[0]


def test_list_batch_jobs_exclude_validation_only_aggregates_requested_page(
    monkeypatch, batch_jobs_store
):
    service, _ = batch_jobs_store
    aggregated_ids: list[str] = []
    original_aggregate = service._aggregate_parent_job

    def tracked_aggregate(session, job, *, include_items=False):
        aggregated_ids.append(str(job.get("id") or ""))
        return original_aggregate(session, job, include_items=include_items)

    monkeypatch.setattr(service, "_aggregate_parent_job", tracked_aggregate)

    page1 = service.list_batch_jobs(
        created_by="u-1", page=1, page_size=1, exclude_validation=True
    )
    assert page1.total == 2
    assert [item["id"] for item in page1.items] == ["pool-job-2"]
    assert aggregated_ids == ["pool-job-2"]

    aggregated_ids.clear()
    page2 = service.list_batch_jobs(
        created_by="u-1", page=2, page_size=1, exclude_validation=True
    )
    assert page2.total == 2
    assert [item["id"] for item in page2.items] == ["pool-job-1"]
    assert aggregated_ids == ["pool-job-1"]
