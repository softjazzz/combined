"""同名旧表同时存在时，对真实读取入口做双 schema 回归。"""

from datetime import datetime

import pytest
from sqlalchemy import MetaData, create_engine, insert, select, text
from sqlalchemy.orm import Session

from app.database.models.cdm import (
    AdmissionRecord, Diagnosis, DischargeRecord, InpatRegistration,
    HospitalizationStatusProjection, MedicalRecordFrontpage, MrCost, MrSurgery, QCResult, SeniorCourseRecord,
)
from app.database.repository import SqliteRepository
from app.services.bundles import assembly
from app.services.medical_records import detail_service, export_service


REF = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
MODELS = (MedicalRecordFrontpage, Diagnosis, MrSurgery, MrCost, AdmissionRecord, HospitalizationStatusProjection,
          DischargeRecord, InpatRegistration, SeniorCourseRecord)


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
    for model in MODELS:
        model.__table__.create(engine)
        model.__table__.to_metadata(MetaData(), schema="cdm").create(engine)
    QCResult.__table__.create(engine)
    for schema in ("main", "cdm"):
        with engine.begin() as connection:
            connection.execute(insert(MedicalRecordFrontpage.__table__.to_metadata(MetaData(), schema=schema)),
                               {**REF, "name": "合成病历", "discharge_dept_name": schema + "科",
                                "admission_datetime": datetime(2026, 1, 1)})
            connection.execute(insert(SeniorCourseRecord.__table__.to_metadata(MetaData(), schema=schema)),
                               {**REF, "document_id": "D1", "record_content": schema + "正文"})
            connection.execute(insert(Diagnosis.__table__.to_metadata(MetaData(), schema=schema)),
                               {**REF, "diagnosis_id": "DI1", "diagnosis_no": "1",
                                "diagnosis_type": "出院主要诊断（病理）", "diagnosis_name": schema + "诊断"})
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    yield engine
    engine.dispose()


def repository(engine):
    repo = SqliteRepository.__new__(SqliteRepository)
    repo._session_factory = lambda: Session(engine)
    return repo


def test_repository_reads_cdm_and_keeps_legacy_results_separate(database):
    repo = repository(database)
    assert repo.get_frontpage(**REF)["discharge_dept_name"] == "cdm科"
    assert repo.get_diagnoses(**REF)[0]["diagnosis_name"] == "cdm诊断"
    assert repo.list_departments() == ["cdm科"]
    assert repo.list_patients()["items"][0]["discharge_dept_name"] == "cdm科"
    # 非临床结果的读取不应随着临床来源改成cdm.qc_result。
    assert repo.get_qc_results(**REF) == []


def test_document_columns_and_content_come_from_same_cdm_table(database, monkeypatch):
    with database.begin() as connection:
        connection.execute(text("ALTER TABLE main.senior_course_record ADD COLUMN old_only TEXT"))
    with Session(database) as session:
        assert "old_only" not in detail_service._get_table_columns(session, "senior_course_record")
    monkeypatch.setattr(detail_service, "DOC_TYPES", [("senior_course_record", "上级查房")])
    result = detail_service.get_documents("V1", session_factory=lambda: Session(database))
    assert result["documents"][0]["content"] == "cdm正文"


@pytest.mark.parametrize("service", [detail_service, export_service])
def test_frontpage_sheet_reads_same_clinical_owner(database, service):
    result = service.get_frontpage_sheet("P1", "V1", session_factory=lambda: Session(database))
    assert result["basic"]["discharge_dept_name"] == "cdm科"


@pytest.mark.parametrize(("hospital_name", "expected"), [(None, "泸县人民医院"), ("新区医院", "新区医院")])
def test_frontpage_export_uses_hospital_default_for_missing_name_only(database, monkeypatch, hospital_name, expected):
    monkeypatch.delenv("MEDQC_HOSPITAL_NAME", raising=False)
    if hospital_name is not None:
        monkeypatch.setenv("MEDQC_HOSPITAL_NAME", hospital_name)

    def export():
        return export_service.get_frontpage_sheet("P1", "V1", session_factory=lambda: Session(database))

    assert export()["basic"]["institute_county_desc"] == expected
    table = MedicalRecordFrontpage.__table__.to_metadata(MetaData(), schema="cdm")
    with database.begin() as connection:
        connection.execute(table.update().values(institute_county_desc="原始登记机构"))
    assert export()["basic"]["institute_county_desc"] == "原始登记机构"


def test_table_inspection_uses_cdm_only_for_synced_clinical_tables(database):
    metadata = MetaData()
    MedicalRecordFrontpage.__table__.to_metadata(metadata)
    QCResult.__table__.to_metadata(metadata)
    result = export_service.get_table_data("mr", metadata=metadata, session_factory=lambda: Session(database))
    assert result["items"][0]["discharge_dept_name"] == "cdm科"
    assert export_service.get_table_data("qc_result", metadata=metadata,
                                         session_factory=lambda: Session(database))["total"] == 0


def test_adapter_select_and_count_use_cdm_without_changing_other_owners(database):
    from app.core.supabase_client import _Query

    query = _Query(lambda: Session(database), "mr").select("*", count="exact")
    result = query.execute()
    assert result.count == 1 and result.data[0]["discharge_dept_name"] == "cdm科"
    for name in ("qc_result", "sys_users", "public.mr"):
        sql, _ = _Query(lambda: None, name).select("*")._build_select_sql()
        assert '"cdm"' not in sql


def test_single_mode_preserves_legacy_owner(database, monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    assert repository(database).get_frontpage(**REF)["discharge_dept_name"] == "main科"


def test_missing_cdm_rows_do_not_fallback_to_old_public_rows(database):
    table = MedicalRecordFrontpage.__table__.to_metadata(MetaData(), schema="cdm")
    with database.begin() as connection:
        connection.execute(table.delete())
    assert repository(database).get_frontpage(**REF) is None


def test_missing_cdm_table_does_not_fallback_to_old_public_table(database):
    from sqlalchemy.exc import OperationalError

    with database.begin() as connection:
        connection.execute(text("DROP TABLE cdm.mr"))
    with pytest.raises(OperationalError, match="cdm.mr"):
        repository(database).get_frontpage(**REF)


def test_mixed_clinical_and_result_join_preserves_result_owner(database):
    from app.services.clinical_read import clinical_read_model

    with database.begin() as connection:
        connection.execute(insert(QCResult.__table__), {**REF, "qc_type": "content", "severity": "error"})
    clinical = clinical_read_model(MedicalRecordFrontpage)
    with Session(database) as session:
        row = session.execute(select(clinical.discharge_dept_name, QCResult.severity)
                              .join(QCResult, QCResult.visit_id == clinical.visit_id)).one()
        assert tuple(row) == ("cdm科", "error")
        assert not session.connection().get_execution_options().get("schema_translate_map")


def test_rule_primary_diagnosis_helper_reads_cdm(database, monkeypatch):
    from app.services import sichuan_qc_service

    monkeypatch.setattr(sichuan_qc_service, "SessionLocal", lambda: Session(database))
    assert sichuan_qc_service.SichuanQCService._resolve_primary_diagnosis_context(**REF)["diagnosis_name"] == "cdm诊断"


def test_workstation_pool_reads_clinical_owner_and_preserves_existing_result(database, monkeypatch):
    from types import SimpleNamespace
    from app.services.medical_records import query_service

    with database.begin() as connection:
        connection.execute(insert(QCResult.__table__), {**REF, "qc_type": "content", "severity": "error", "status": "open"})
    monkeypatch.setattr(query_service, "default_workflow_queue_state_service",
                        SimpleNamespace(get_state_map=lambda **kwargs: {}))
    result = query_service.get_workstation_data(
        session_factory=lambda: Session(database), settings_loader=lambda: (SimpleNamespace(), None),
        demo_records_builder=lambda: [], demo_policy=lambda *args: False,
        qc_projection_loader=lambda refs: {},
    )
    assert result["total"] == 1
    assert result["records"][0]["department"] == "cdm科"
    assert result["records"][0]["status"] == "has_defects"


@pytest.mark.asyncio
async def test_final_list_real_join_keeps_existing_qc_score(database, monkeypatch):
    import inspect
    from starlette.requests import Request
    from app.database.models.qc import QCDefect, QCResultBiz
    from app.routers import records

    QCResultBiz.__table__.create(database)
    QCDefect.__table__.create(database)
    table = MedicalRecordFrontpage.__table__.to_metadata(MetaData(), schema="cdm")
    with database.begin() as connection:
        connection.execute(table.update().values(discharge_datetime=datetime(2026, 1, 5)))
        connection.execute(insert(QCResultBiz.__table__), {"id": "R1", "record_id": "V1", "overall_score": 95})
    monkeypatch.setattr(records, "SessionLocal", lambda: Session(database))
    # 只测路由内部SQL关联，权限装饰器未修改；不执行质控或生成新结果。
    result = await inspect.unwrap(records.get_final_records)(
        request=Request({"type": "http", "headers": []}), current_user={"id": "test"},
        keyword=None, department=None, qc_status=None, start_date=None, end_date=None, page=1, page_size=10,
    )
    row = result["data"]["items"][0]
    assert result["data"]["total"] == 1
    assert row["department"] == "cdm科"
    assert row["score"] == 95 and row["status"] == "passed"


@pytest.mark.asyncio
async def test_frontpage_input_builders_read_cdm_without_model_calls(database, monkeypatch):
    from app.database import connection
    from app.services.frontpage_extraction_service import FrontPageExtractionService

    monkeypatch.setattr(connection, "engine", database)
    service = FrontPageExtractionService.__new__(FrontPageExtractionService)
    body = await service._get_medical_text("V1", allow_demo_fallback=False)
    assert "cdm正文" in body and "main正文" not in body
    assert "cdm科" in body and "main科" not in body


def test_settlement_sql_supplement_reads_same_clinical_source(database):
    from app.services.settlement_assembly_service import SettlementAssemblyService

    service = SettlementAssemblyService.__new__(SettlementAssemblyService)
    with Session(database) as session:
        result = service._load_sql_data(session, "P1", "V1")
    assert result["mr"]["discharge_dept_name"] == "cdm科"
