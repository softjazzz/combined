"""出院文书更新时间不能进入业务出院时间、场景筛选和任务冻结。"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.services.qc_workspace.record_repository import RecordRepository
from app.services.qc_workspace import record_repository as module
from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot


@pytest.fixture
def case_db():
    engine = create_engine("sqlite:///:memory:")
    for model in (module.MedicalRecordFrontpage, module.AdmissionRecord, module.DischargeRecord, module.InpatRegistration):
        model.__table__.create(bind=engine)
    with Session(engine) as session:
        for key in ("UPDATE-ONLY", "DISCHARGE-DATE", "FRONTPAGE-DATE"):
            session.add(module.MedicalRecordFrontpage(
                institute_id="I", patient_id=key, visit_id=key,
                admission_datetime=datetime(2026, 6, 1, 8),
                discharge_datetime=datetime(2026, 6, 5, 9) if key == "FRONTPAGE-DATE" else None,
            ))
            session.add(module.DischargeRecord(
                institute_id="I", patient_id=key, visit_id=key,
                discharge_date=datetime(2026, 6, 7, 10) if key != "UPDATE-ONLY" else None,
                update_time=datetime(2026, 9, 9, 12),
            ))
        session.commit()
        yield session, RecordRepository(session_factory=lambda: session)
    engine.dispose()


def query(case_db, scope="all", date_field="admission", start=None, end=None):
    session, repo = case_db
    return repo._build_records_query(session, scope=scope, department=None, doctor=None,
        date_field=date_field, start_date=start, end_date=end, keyword=None).all()


def test_only_update_time_does_not_create_a_final_case_or_frozen_discharge(case_db):
    _, repo = case_db
    final_ids = {row[0].visit_id for row in query(case_db, "final")}
    assert final_ids == {"DISCHARGE-DATE", "FRONTPAGE-DATE"}
    rows = query(case_db, "running")
    assert [row[0].visit_id for row in rows] == ["UPDATE-ONLY"]
    item = repo._serialize_record_row(rows[0])
    assert item["discharge_datetime"] == ""
    frozen = build_record_evaluation_horizon_snapshot([item], task_frozen_date="2026-09-10")[0]
    assert frozen["evaluation_basis"] == "task_frozen_date"
    assert frozen["evaluation_horizon"] == "2026-09-10"


@pytest.mark.parametrize("date_field", ["discharge", "visit"])
def test_discharge_date_filter_never_matches_document_update_date(case_db, date_field):
    assert query(case_db, date_field=date_field, start="2026-09-09", end="2026-09-09") == []
    assert {row[0].visit_id for row in query(case_db, date_field=date_field, start="2026-06-07", end="2026-06-07")} == {"DISCHARGE-DATE"}


def test_existing_business_date_priority_and_precision_are_preserved(case_db):
    _, repo = case_db
    items = {row[0].visit_id: repo._serialize_record_row(row) for row in query(case_db)}
    assert items["FRONTPAGE-DATE"]["discharge_datetime"] == "2026-06-05 09:00:00"
    assert items["DISCHARGE-DATE"]["discharge_datetime"] == "2026-06-07 00:00:00"
    frozen = build_record_evaluation_horizon_snapshot([items["FRONTPAGE-DATE"]], task_frozen_date="2026-09-10")[0]
    assert frozen["evaluation_basis"] == "discharge_datetime"
    assert frozen["evaluation_horizon"] == "2026-06-05"
