"""工作台病历池查询服务单元测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.connection import Base
from app.database.models.cdm import AdmissionRecord, MedicalRecordFrontpage, QCResult
from app.services.medical_records.query_service import get_workstation_data


class DummyWorkflowQueueStateService:
    def get_state_map(self, **_kwargs):
        return {}

    def backfill_frontpage_generate(self, **_kwargs):
        return None


@pytest.fixture()
def workstation_session_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            MedicalRecordFrontpage.__table__,
            AdmissionRecord.__table__,
            QCResult.__table__,
        ],
    )
    monkeypatch.setattr(
        "app.services.medical_records.query_service.default_workflow_queue_state_service",
        DummyWorkflowQueueStateService(),
    )

    def factory():
        return Session(engine)

    return factory


def _insert_workstation_records(session_factory, *records: MedicalRecordFrontpage) -> None:
    with session_factory() as session:
        session.add_all(records)
        session.commit()


def _workstation_settings_loader():
    return SimpleNamespace(), None


def _no_demo_policy(_settings, _real_total_count):
    return False


def test_get_workstation_data_filters_department_by_coalesced_dept(workstation_session_factory):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="甲",
            admission_dept_name="中医科",
            discharge_dept_name=None,
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P2",
            visit_id="V2",
            name="乙",
            admission_dept_name="普通外科",
            discharge_dept_name="普通外科",
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
    )

    result = get_workstation_data(
        dept="中医科",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert result["records"][0]["id"] == "V1"
    assert result["records"][0]["department"] == "中医科"


def test_get_workstation_data_date_field_filters_admission_discharge_and_visit(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="入院命中",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 5, 25, 8, 0),
            discharge_datetime=datetime(2026, 5, 27, 8, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P2",
            visit_id="V2",
            name="出院命中",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 5, 20, 8, 0),
            discharge_datetime=datetime(2026, 5, 25, 8, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P3",
            visit_id="V3",
            name="未命中",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 5, 18, 8, 0),
            discharge_datetime=datetime(2026, 5, 19, 8, 0),
        ),
    )

    common_kwargs = {
        "start_date": datetime(2026, 5, 25).date(),
        "end_date": datetime(2026, 5, 25).date(),
        "session_factory": workstation_session_factory,
        "settings_loader": _workstation_settings_loader,
        "demo_policy": _no_demo_policy,
    }

    admission_result = get_workstation_data(date_field="admission", **common_kwargs)
    discharge_result = get_workstation_data(date_field="discharge", **common_kwargs)
    visit_result = get_workstation_data(date_field="visit", **common_kwargs)

    assert [record["id"] for record in admission_result["records"]] == ["V1"]
    assert [record["id"] for record in discharge_result["records"]] == ["V2"]
    assert {record["id"] for record in visit_result["records"]} == {"V1", "V2"}


def test_get_workstation_data_department_stats_include_admission_only_dept(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="甲",
            admission_dept_name="中医科",
            discharge_dept_name=None,
            admission_datetime=datetime(2026, 5, 25, 8, 0),
        ),
    )

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    department_totals = {dept["name"]: dept["total"] for dept in result["departments"]}
    assert department_totals["全部科室"] == 1
    assert department_totals["中医科"] == 1
