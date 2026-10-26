from datetime import datetime

import pytest
from sqlalchemy import MetaData, create_engine, insert, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database.models.cdm import AdmissionRecord, DischargeRecord, InpatRegistration, MedicalRecordFrontpage
from app.services.bundles import assembly
from app.services.qc_workspace.record_repository import RecordRepository


IDENTITY = {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1"}
MODELS = (MedicalRecordFrontpage, AdmissionRecord, InpatRegistration, DischargeRecord)


@pytest.fixture
def database():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("ATTACH DATABASE ':memory:' AS cdm"))
    for model in MODELS:
        model.__table__.create(engine)
        model.__table__.to_metadata(MetaData(), schema="cdm").create(engine)
    yield engine
    engine.dispose()


def seed(engine, *, schema, mr=True, identity=None):
    identity = identity or IDENTITY
    for model in MODELS:
        if model is MedicalRecordFrontpage and not mr:
            continue
        table = model.__table__.to_metadata(MetaData(), schema=schema)
        values = {**identity, "name": "合成病历", "record_content": schema + "正文"}
        if model in (MedicalRecordFrontpage, InpatRegistration, AdmissionRecord):
            values["admission_datetime"] = datetime(2026, 1, 1, 9)
        if model in (MedicalRecordFrontpage, InpatRegistration):
            values["discharge_datetime"] = datetime(2026, 1, 5, 9)
        if model is MedicalRecordFrontpage:
            values["discharge_dept_name"] = schema + "科室"
        elif model in (DischargeRecord, AdmissionRecord):
            values.update(document_id="D1", dept_name=schema + "科室")
        if model is DischargeRecord:
            values.update(discharge_date=datetime(2026, 1, 5).date(),
                          chief_physician_sign_datetime=datetime(2026, 1, 6), v2_schema='{"source":"' + schema + '"}')
        with engine.begin() as connection:
            connection.execute(insert(table), values)


def collect(repository, refs=None):
    return repository.collect_records(scope="all", department=None, doctor=None,
                                      date_field="admission", start_date=None, end_date=None,
                                      keyword=None, record_refs=refs or [IDENTITY])


@pytest.mark.parametrize("has_frontpage", [True, False])
def test_split_uses_same_cdm_owner_for_frontpage_and_explicit_anchors(database, monkeypatch, has_frontpage):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    seed(database, schema="main", mr=has_frontpage)
    seed(database, schema="cdm", mr=has_frontpage)
    # 模拟已升级051的cdm与缺新列的旧public/main影子表同时存在。
    with database.begin() as connection:
        connection.execute(text("ALTER TABLE main.discharge_record DROP COLUMN chief_physician_sign_datetime"))
        connection.execute(text("ALTER TABLE main.discharge_record DROP COLUMN v2_schema"))
    repository = RecordRepository(session_factory=lambda: Session(database))
    rows = collect(repository)
    assert len(rows) == 1
    assert rows[0]["department"] == "cdm科室"
    assert rows[0]["institute_id"] == IDENTITY["institute_id"]
    assert rows[0]["visit_id"] == IDENTITY["visit_id"]


def test_single_mode_keeps_legacy_sqlite_owner(database, monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "single")
    seed(database, schema="main")
    seed(database, schema="cdm")
    rows = collect(RecordRepository(session_factory=lambda: Session(database)))
    assert rows[0]["department"] == "main科室"


def test_split_does_not_fallback_to_public_or_cross_institute(database, monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    seed(database, schema="main", identity=IDENTITY)
    seed(database, schema="cdm", identity={**IDENTITY, "institute_id": "H2"})
    assert collect(RecordRepository(session_factory=lambda: Session(database))) == []


def test_split_list_filters_count_and_hydration_use_same_owner(database, monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    seed(database, schema="main")
    seed(database, schema="cdm")
    repository = RecordRepository(session_factory=lambda: Session(database))
    filters = dict(scope="all", department="cdm科室", doctor=None,
                   date_field="admission", start_date=None, end_date=None, keyword=None)
    assert repository.count_records(**filters) == 1
    listed = repository.list_records(**filters, page=1, page_size=10)
    assert listed.total == 1 and listed.items[0]["department"] == "cdm科室"
    hydrated = repository.hydrate_records_with_medical_text(listed.items)
    assert hydrated[0]["medical_text"] == "cdm正文"
    assert "cdm科室" in repository.get_record_filters(scope="all", department=None)["departments"]


def test_missing_cdm_column_fails_closed_instead_of_reading_public(database, monkeypatch):
    monkeypatch.setattr(assembly, "DB_SCHEMA_MODE", "split")
    seed(database, schema="main", mr=False)
    seed(database, schema="cdm", mr=False)
    with database.begin() as connection:
        connection.execute(text("ALTER TABLE cdm.discharge_record DROP COLUMN v2_schema"))
    with pytest.raises(OperationalError, match="v2_schema"):
        collect(RecordRepository(session_factory=lambda: Session(database)))
