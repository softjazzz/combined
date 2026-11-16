"""普通质控从原始住院身份准入；缺首页表/列不得影响收集。"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database import clinical_connection
from app.services.bundles import assembly
from app.services.case_identity import CaseRef
from app.services.qc_workspace.record_repository import (
    AdmissionRecord, DischargeRecord, InpatRegistration, RecordRepository,
)


REF = CaseRef("ORG_A", "P", "V")
FILTERS = dict(scope="all", department=None, doctor=None, date_field="admission",
               start_date=None, end_date=None, keyword=None)


@pytest.fixture
def raw_source(monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(clinical_connection, "configured", lambda: False)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: None)
    engine = create_engine("sqlite:///:memory:")
    for model in (InpatRegistration, AdmissionRecord, DischargeRecord):
        model.__table__.create(engine)
    with Session(engine) as session:
        session.add(InpatRegistration(**REF.as_dict(), name="原始登记",
            admission_datetime=datetime(2026, 1, 2, 9), admission_dept_name="内科"))
        session.add(AdmissionRecord(**REF.as_dict(), document_id="A",
            admission_datetime=datetime(2026, 1, 1, 8), record_content="原始入院正文"))
        session.commit()
    yield engine
    engine.dispose()


@pytest.mark.parametrize("mr_shape", ["absent", "missing_columns"])
@pytest.mark.parametrize("entry", ["refs", "ids", "filtered", "list", "count", "filters", "hydrate"])
def test_ordinary_entry_never_reads_frontpage(raw_source, mr_shape, entry):
    if mr_shape == "missing_columns":
        with raw_source.begin() as connection:
            connection.execute(text("CREATE TABLE mr (visit_id TEXT)"))
    statements = []
    event.listen(raw_source, "before_cursor_execute",
                 lambda conn, cursor, statement, params, ctx, many: statements.append(statement))
    repository = RecordRepository(session_factory=lambda: Session(raw_source))
    if entry == "list":
        result = repository.list_records(**FILTERS, page=1, page_size=10, institute_id="ORG_A")
        assert result.total == 1
        rows = result.items
    elif entry == "count":
        assert repository.count_records(**FILTERS) == 1
        rows = []
    elif entry == "filters":
        assert repository.get_record_filters(scope="all", department=None)["departments"] == ["内科"]
        rows = []
    elif entry == "hydrate":
        rows = repository.hydrate_records_with_medical_text([REF.as_dict()])
        assert rows[0]["medical_text"] == "原始入院正文"
    else:
        args = {"record_refs": [REF]} if entry == "refs" else {"record_ids": ["V"]} if entry == "ids" else {}
        rows = repository.collect_records(**FILTERS, **args)
    if rows:
        assert CaseRef.from_mapping(rows[0]) == REF
        assert rows[0].get("admission_datetime", "2026-01-01 08:00:00") == "2026-01-01 08:00:00"
    assert not any(" mr" in statement.lower() or "mr." in statement.lower() for statement in statements)


def test_explicit_identity_and_institute_filter_cannot_cross_case(raw_source):
    repository = RecordRepository(session_factory=lambda: Session(raw_source))
    assert repository.collect_records(**FILTERS, record_refs=[REF], institute_id="ORG_B") == []
    assert repository.collect_records(**FILTERS, record_refs=[CaseRef("ORG_B", "P", "V")]) == []
    with Session(raw_source) as session:
        session.add(InpatRegistration(institute_id="ORG_B", patient_id="OTHER", visit_id="V"))
        session.commit()
    with pytest.raises(ValueError, match="ambiguous"):
        repository.collect_records(**FILTERS, record_ids=["V"])
    assert len(repository.collect_records(**FILTERS, record_refs=[REF])) == 1


def test_raw_source_sql_error_is_not_reclassified_as_missing_frontpage(raw_source):
    with raw_source.begin() as connection:
        connection.execute(text("ALTER TABLE admission_record RENAME COLUMN record_content TO unavailable_content"))
    with pytest.raises(OperationalError, match="record_content"):
        RecordRepository(session_factory=lambda: Session(raw_source)).collect_records(**FILTERS, record_refs=[REF])


@pytest.fixture
def independent_source(raw_source, monkeypatch):
    from app.services import clinical_case_catalog
    with raw_source.begin() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
    for model in (InpatRegistration, AdmissionRecord, DischargeRecord):
        from sqlalchemy import MetaData
        model.__table__.to_metadata(MetaData(), schema="cdm").create(raw_source)
    with Session(raw_source.execution_options(schema_translate_map={None: "cdm"})) as session:
        session.add(InpatRegistration(**REF.as_dict(), name="独立来源",
            admission_datetime=datetime(2026, 1, 1, 8)))
        session.commit()
    monkeypatch.setattr(clinical_connection, "configured", lambda: True)
    monkeypatch.setattr(clinical_connection, "get_engine", lambda: raw_source)
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    try:
        yield raw_source
    finally:
        clinical_case_catalog.catalog.cache_clear()


def test_independent_source_catalog_and_collection_do_not_require_mr(independent_source):
    from app.services import clinical_case_catalog
    repository = RecordRepository(session_factory=lambda: pytest.fail("禁止回退业务源"))
    try:
        assert clinical_case_catalog.resolve_identity("V", institute_id="ORG_A") == REF.as_dict()
        rows = repository.collect_records(**FILTERS)
        assert len(rows) == 1 and rows[0]["patient_name"] == "独立来源"
        assert repository.count_records(**FILTERS) == 1
        assert repository.list_records(**FILTERS, page=1, page_size=10).total == 1
    finally:
        clinical_case_catalog.catalog.cache_clear()


@pytest.mark.parametrize("filter_value", [{"department": "出院科"}, {"doctor": "原始医生"}])
def test_independent_filter_uses_same_raw_fields_as_explicit_refs(independent_source, filter_value):
    with Session(independent_source.execution_options(schema_translate_map={None: "cdm"})) as session:
        session.query(InpatRegistration).update({"admission_dept_name": "入院科"})
        session.add(AdmissionRecord(**REF.as_dict(), document_id="A", attending_physician_sign="原始医生"))
        session.add(DischargeRecord(**REF.as_dict(), document_id="D", dept_name="出院科"))
        session.commit()
    repository = RecordRepository(session_factory=lambda: pytest.fail("禁止回退业务源"))
    filters = {**FILTERS, **filter_value}
    explicit = repository.collect_records(**filters, record_refs=[REF])
    assert len(explicit) == 1
    assert repository.collect_records(**filters) == explicit


def test_missing_raw_business_time_remains_unknown_scene(raw_source):
    with Session(raw_source) as session:
        session.query(InpatRegistration).update({"admission_datetime": None})
        session.query(AdmissionRecord).update({"admission_datetime": None})
        session.commit()
    row = RecordRepository(session_factory=lambda: Session(raw_source)).collect_records(**FILTERS, record_refs=[REF])[0]
    assert row["qc_scope"] == "unknown"


def test_count_and_pagination_do_not_hydrate_unselected_medical_text(raw_source):
    with Session(raw_source) as session:
        session.add_all(InpatRegistration(institute_id="ORG_A", patient_id=f"P{n}", visit_id=f"V{n}",
            admission_datetime=datetime(2026, 1, 1), record_content="合成大正文" * 100) for n in range(40))
        session.commit()
    statements = []
    loaded_bodies = []
    event.listen(raw_source, "before_cursor_execute",
        lambda conn, cursor, statement, params, ctx, many: statements.append(statement))
    def loaded(instance, context):
        if "record_content" in instance.__dict__:
            loaded_bodies.append(CaseRef.from_mapping(instance.__dict__))
    event.listen(InpatRegistration, "load", loaded)
    repository = RecordRepository(session_factory=lambda: Session(raw_source))
    try:
        assert repository.count_records(**FILTERS) == 41
        assert not any("record_content" in statement for statement in statements)
        result = repository.list_records(**FILTERS, page=2, page_size=3)
        assert result.total == 41 and len(result.items) == 3
        assert set(loaded_bodies) == {CaseRef.from_mapping(item) for item in result.items}
        assert len(loaded_bodies) == 3
        statements.clear()
        repository.hydrate_records_with_medical_text(result.items)
        assert len([statement for statement in statements if statement.lstrip().startswith("SELECT")]) == 3
    finally:
        event.remove(InpatRegistration, "load", loaded)


def test_frontpage_only_identity_is_available_only_to_explicit_display(independent_source):
    from sqlalchemy import MetaData
    from app.services import clinical_case_catalog
    from app.services.data_pipeline_settings import PipelineError
    from app.services.qc_workspace.record_repository import MedicalRecordFrontpage
    MedicalRecordFrontpage.__table__.to_metadata(MetaData(), schema="cdm").create(independent_source)
    with Session(independent_source.execution_options(schema_translate_map={None: "cdm"})) as session:
        session.add(MedicalRecordFrontpage(institute_id="ORG_A", patient_id="ONLY_MR", visit_id="ONLY_MR", mr_no="M123"))
        session.commit()
    with pytest.raises(PipelineError, match="ambiguous_or_missing"):
        clinical_case_catalog.resolve_identity("M123")
    assert clinical_case_catalog.resolve_identity("M123", include_frontpage=True)["visit_id"] == "ONLY_MR"


@pytest.mark.asyncio
async def test_create_route_collects_real_raw_repository_without_frontpage(raw_source, monkeypatch):
    from types import SimpleNamespace
    from tests.unit.test_qc_sichuan_batch_throughput import _WorkspaceStub, _ServiceStub, _luxian_native_settings
    from app.routers import qc_sichuan
    from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
    with Session(raw_source) as session:
        session.query(InpatRegistration).update({"discharge_datetime": datetime(2026, 1, 3)})
        session.commit()
    repository = RecordRepository(session_factory=lambda: Session(raw_source))
    owner = CustomQCWorkspaceService.__new__(CustomQCWorkspaceService)
    monkeypatch.setattr(owner, "_record_repository", lambda: repository)
    workspace = _WorkspaceStub()
    workspace.collect_records = owner.collect_records
    workspace.collect_records_for_admission = owner.collect_records_for_admission
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)
    monkeypatch.setattr(qc_sichuan, "get_settings", _luxian_native_settings)
    monkeypatch.setattr(qc_sichuan, "submit_detached_task", lambda *_args: None)
    response = await qc_sichuan.create_workspace_batch_job(
        request=SimpleNamespace(state=SimpleNamespace()),
        payload=qc_sichuan.SichuanWorkspaceBatchJobCreateRequest(
            rule_set_key=qc_sichuan.LUXIAN_0609_RULE_SET_KEY, scope="final", record_refs=[REF.as_dict()]),
        qc_service=_ServiceStub(), current_user={"id": "tester"},
    )
    assert response["success"] is True
    assert workspace.created_job["record_refs"] == [REF]
