"""真实病历查询不得把同步/书写时间冻结为入院业务时间。"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.services.case_identity import CaseRef
from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot
from app.services.qc_workspace import record_repository as module


ADMISSION = datetime(2026, 2, 2, 10)
DISCHARGE = datetime(2026, 2, 9, 8, 31)
SYNC = datetime(2026, 9, 9, 12)


def _collect(*, entry="query", frontpage=None, admission=None, registration=ADMISSION,
             foreign=None, start=None, end=None):
    engine = create_engine("sqlite:///:memory:")
    for model in (module.MedicalRecordFrontpage, module.AdmissionRecord,
                  module.InpatRegistration, module.DischargeRecord):
        model.__table__.create(bind=engine)
    try:
        with Session(engine) as session:
            identity = dict(institute_id="I", patient_id="P", visit_id="V")
            session.add(module.MedicalRecordFrontpage(
                **identity, admission_datetime=frontpage,
                discharge_datetime=DISCHARGE, update_time=SYNC, mr_datetime=SYNC))
            session.add(module.DischargeRecord(**identity, document_id="D", discharge_time=DISCHARGE))
            session.add(module.AdmissionRecord(
                **identity, admission_datetime=admission,
                update_time=SYNC, record_datetime=SYNC))
            if registration is not None:
                session.add(module.InpatRegistration(
                    **identity, admission_datetime=registration, update_time=SYNC))
            if foreign:
                session.add(module.InpatRegistration(
                    **{**identity, **foreign}, admission_datetime=ADMISSION))
            session.commit()
            repo = module.RecordRepository(session_factory=lambda: session)
            return repo.collect_records(
                scope="all", department=None, doctor=None,
                date_field="admission", start_date=start, end_date=end,
                keyword=None, record_ids=["V"] if entry == "id" else None,
                record_refs=[CaseRef("I", "P", "V")] if entry == "ref" else None)
    finally:
        engine.dispose()


@pytest.mark.parametrize("entry", ["query", "id", "ref"])
def test_registration_business_admission_resolves_frozen_final_horizon(entry):
    rows = _collect(entry=entry)
    assert len(rows) == 1
    assert rows[0]["admission_datetime"] == "2026-02-02 10:00:00"
    frozen = build_record_evaluation_horizon_snapshot(rows, task_frozen_date="2026-09-09")[0]
    assert frozen["resolution_status"] == "resolved"
    assert frozen["evaluation_basis"] == "discharge_datetime"
    assert frozen["evaluation_horizon"] == "2026-02-09"
    assert frozen["discharge_datetime"] == "2026-02-09 08:31:00"


@pytest.mark.parametrize("frontpage,admission,expected", [
    (datetime(2026, 2, 1, 8), datetime(2026, 2, 3, 9), "2026-02-03 09:00:00"),
    (None, datetime(2026, 2, 3, 9), "2026-02-03 09:00:00"),
])
def test_registration_does_not_override_higher_priority_business_sources(frontpage, admission, expected):
    rows = _collect(frontpage=frontpage, admission=admission)
    assert len(rows) == 1
    assert rows[0]["admission_datetime"] == expected


def test_missing_business_admission_does_not_use_update_or_record_time():
    rows = _collect(registration=None)
    assert len(rows) == 1
    assert rows[0]["admission_datetime"] == ""
    assert rows[0]["admission_date"] == ""


@pytest.mark.parametrize("source", ["admission", "registration"])
def test_true_business_admission_after_discharge_remains_time_conflict(source):
    rows = _collect(**{source: datetime(2026, 2, 10, 9)})
    frozen = build_record_evaluation_horizon_snapshot(rows, task_frozen_date="2026-09-09")[0]
    assert frozen["resolution_status"] == "time_conflict"


@pytest.mark.parametrize("foreign", [{"institute_id": "OTHER"}, {"patient_id": "OTHER"}])
def test_registration_from_another_case_with_same_visit_is_not_used(foreign):
    rows = _collect(entry="ref", registration=None, foreign=foreign)
    assert len(rows) == 1
    assert rows[0]["admission_datetime"] == ""


def test_admission_date_filter_uses_registration_business_date():
    rows = _collect(start="2026-02-02", end="2026-02-02")
    assert len(rows) == 1
    assert rows[0]["admission_date"] == "2026-02-02"
    assert _collect(start="2026-09-09", end="2026-09-09") == []


def test_frontpage_time_does_not_create_raw_business_time_conflict():
    rows = _collect(frontpage=datetime(2026, 2, 10, 9))
    frozen = build_record_evaluation_horizon_snapshot(rows, task_frozen_date="2026-09-09")[0]
    assert frozen["resolution_status"] == "resolved"
