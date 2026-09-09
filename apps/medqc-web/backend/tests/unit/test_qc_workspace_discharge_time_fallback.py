"""仅有业务出院时间时，各病历入口仍应识别终末场景并冻结精确截止。"""
from datetime import datetime, date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.services.case_identity import CaseRef
from app.services.qc_workspace import record_repository as module
from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot


def records(entry, *, higher=None, discharge_date=None, time=datetime(2026, 2, 9, 8, 31), date_field="admission", start=None, end=None):
    engine = create_engine("sqlite:///:memory:")
    for model in (module.MedicalRecordFrontpage, module.InpatRegistration, module.AdmissionRecord, module.DischargeRecord):
        model.__table__.create(bind=engine)
    with Session(engine) as session:
        identity = dict(institute_id="I", patient_id="P", visit_id="V")
        if entry == "query":
            session.add(module.MedicalRecordFrontpage(**identity, admission_datetime=datetime(2026, 2, 1, 9), discharge_datetime=higher))
        session.add(module.InpatRegistration(**identity, admission_datetime=datetime(2026, 2, 1, 9), discharge_datetime=higher))
        session.add(module.DischargeRecord(**identity, discharge_date=discharge_date, discharge_time=time, update_time=datetime(2026, 9, 9, 12)))
        session.commit()
        repo = module.RecordRepository(session_factory=lambda: session)
        result = repo.collect_records(scope="all", department=None, doctor=None, date_field=date_field, start_date=start, end_date=end, keyword=None,
            record_ids=["V"] if entry == "id" else None,
            record_refs=[CaseRef("I", "P", "V")] if entry == "ref" else None)
    engine.dispose()
    assert len(result) == 1
    return result[0]


@pytest.mark.parametrize("entry", ["query", "id", "ref"])
def test_time_only_enters_final_and_freezes_exact_discharge(entry):
    row = records(entry)
    assert row["scope"] == "final"
    assert row["discharge_datetime"] == "2026-02-09 08:31:00"
    frozen = build_record_evaluation_horizon_snapshot([row], task_frozen_date="2026-09-09")[0]
    assert frozen["evaluation_basis"] == "discharge_datetime"
    assert frozen["discharge_datetime"] == "2026-02-09 08:31:00"
    assert frozen["evaluation_horizon"] == "2026-02-09"


@pytest.mark.parametrize("entry", ["query", "id", "ref"])
def test_time_fallback_does_not_override_existing_higher_date(entry):
    row = records(entry, higher=datetime(2026, 2, 5, 10))
    assert row["discharge_datetime"] == "2026-02-05 10:00:00"
    row = records(entry, discharge_date=date(2026, 2, 7))
    assert row["discharge_date"] == "2026-02-07"


@pytest.mark.parametrize("entry", ["query", "id", "ref"])
def test_without_any_business_discharge_does_not_use_update_time(entry):
    row = records(entry, time=None)
    assert row["scope"] == "running"
    assert not row["discharge_datetime"]


@pytest.mark.parametrize("entry", ["query", "id", "ref"])
def test_time_only_matches_discharge_date_filter(entry):
    row = records(entry, date_field="discharge", start="2026-02-09", end="2026-02-09")
    assert row["scope"] == "final"
    assert row["discharge_datetime"] == "2026-02-09 08:31:00"
