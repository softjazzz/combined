"""工作台病历池查询服务单元测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database.connection import Base
from app.database.models.cdm import AdmissionRecord, MedicalRecordFrontpage, QCResult
from app.services.frontpage_settings import FrontpageExtractionSettings
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
    with Session(engine) as session:
        session.execute(text("""
            CREATE TABLE discharge_record (
                institute_id VARCHAR(100),
                patient_id VARCHAR(100),
                visit_id VARCHAR(100),
                document_id VARCHAR(100),
                dept_name VARCHAR(100),
                discharge_time DATETIME,
                update_time DATETIME
            )
        """))
        session.commit()
    monkeypatch.setattr(
        "app.services.medical_records.query_service.default_workflow_queue_state_service",
        DummyWorkflowQueueStateService(),
    )

    def factory():
        return Session(engine)

    return factory


@pytest.fixture()
def workstation_session_factory_without_discharge_record(monkeypatch):
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


def _insert_discharge_records(session_factory, *rows: dict) -> None:
    with session_factory() as session:
        session.execute(
            text("""
                INSERT INTO discharge_record (
                    institute_id,
                    patient_id,
                    visit_id,
                    document_id,
                    dept_name,
                    discharge_time,
                    update_time
                )
                VALUES (
                    :institute_id,
                    :patient_id,
                    :visit_id,
                    :document_id,
                    :dept_name,
                    :discharge_time,
                    :update_time
                )
            """),
            list(rows),
        )
        session.commit()


def _workstation_settings_loader():
    return SimpleNamespace(), None


def _no_demo_policy(_settings, _real_total_count):
    return False


def test_get_workstation_data_excludes_demo_records_in_production_even_when_enabled(
    workstation_session_factory,
    monkeypatch,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="真实病历",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
    )
    monkeypatch.setattr("app.services.frontpage_settings._is_production_env", lambda: True)

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=lambda: (
            FrontpageExtractionSettings(
                include_demo_records=True,
                auto_hide_demo_when_real_data=False,
            ),
            "file",
        ),
        demo_records_builder=lambda: [
            {
                "id": "DEMO-1",
                "visitId": "DEMO-1",
                "name": "演示病历",
                "department": "内科",
            }
        ],
    )

    assert result["total"] == 1
    assert [record["id"] for record in result["records"]] == ["V1"]


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
            update_time=datetime(2026, 5, 20, 8, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P2",
            visit_id="V2",
            name="出院命中",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 5, 20, 8, 0),
            discharge_datetime=datetime(2026, 5, 25, 8, 0),
            update_time=datetime(2026, 5, 21, 8, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P3",
            visit_id="V3",
            name="未命中",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 5, 18, 8, 0),
            discharge_datetime=datetime(2026, 5, 19, 8, 0),
            update_time=datetime(2026, 5, 25, 8, 0),
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
    updated_result = get_workstation_data(date_field="updated", **common_kwargs)

    assert [record["id"] for record in admission_result["records"]] == ["V1"]
    assert [record["id"] for record in discharge_result["records"]] == ["V2"]
    assert {record["id"] for record in visit_result["records"]} == {"V1", "V2"}
    assert [record["id"] for record in updated_result["records"]] == ["V3"]


def test_get_workstation_data_visit_field_accepts_text_discharge_time(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="字符串出院时间",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            discharge_datetime=None,
            update_time=datetime(2026, 4, 2, 8, 0),
        ),
    )
    _insert_discharge_records(
        workstation_session_factory,
        {
            "institute_id": "I",
            "patient_id": "P1",
            "visit_id": "V1",
            "document_id": "DR1",
            "dept_name": "中医科",
            "discharge_time": "2026-04-05 10:00:00",
            "update_time": datetime(2026, 4, 5, 11, 0),
        },
    )

    result = get_workstation_data(
        start_date=datetime(2026, 4, 1).date(),
        end_date=datetime(2026, 4, 5).date(),
        date_field="visit",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert result["records"][0]["id"] == "V1"
    assert result["records"][0]["department"] == "中医科"
    assert result["records"][0]["dischargeDate"] == "2026-04-05"


def test_get_workstation_data_falls_back_when_discharge_summary_unavailable(
    workstation_session_factory_without_discharge_record,
):
    _insert_workstation_records(
        workstation_session_factory_without_discharge_record,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="无出院记录表",
            admission_dept_name="外一科",
            discharge_dept_name=None,
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            discharge_datetime=datetime(2026, 4, 8, 9, 0),
        ),
    )

    result = get_workstation_data(
        dept="外一科",
        start_date=datetime(2026, 4, 1).date(),
        end_date=datetime(2026, 4, 10).date(),
        date_field="discharge",
        session_factory=workstation_session_factory_without_discharge_record,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert result["records"][0]["id"] == "V1"
    assert result["records"][0]["department"] == "外一科"
    assert result["records"][0]["dischargeDate"] == "2026-04-08"


def test_get_workstation_data_discharge_field_uses_discharge_record_time_and_dept(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="出院记录命中",
            admission_dept_name="内科",
            discharge_dept_name=None,
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            discharge_datetime=None,
        ),
    )
    _insert_discharge_records(
        workstation_session_factory,
        {
            "institute_id": "I",
            "patient_id": "P1",
            "visit_id": "V1",
            "document_id": "DR1",
            "dept_name": "中医科",
            "discharge_time": datetime(2026, 4, 5, 10, 0),
            "update_time": datetime(2026, 4, 5, 11, 0),
        },
    )

    result = get_workstation_data(
        dept="中医科",
        start_date=datetime(2026, 4, 1).date(),
        end_date=datetime(2026, 4, 10).date(),
        date_field="discharge",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert [record["id"] for record in result["records"]] == ["V1"]
    assert result["records"][0]["department"] == "中医科"
    assert result["records"][0]["dischargeDate"] == "2026-04-05"
    assert result["records"][0]["days"] == 4


def test_get_workstation_data_discharge_field_falls_back_to_mr_discharge_datetime(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="首页出院时间命中",
            admission_dept_name="外一科",
            discharge_dept_name=None,
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            discharge_datetime=datetime(2026, 4, 8, 9, 0),
        ),
    )

    result = get_workstation_data(
        dept="外一科",
        start_date=datetime(2026, 4, 1).date(),
        end_date=datetime(2026, 4, 10).date(),
        date_field="discharge",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert [record["id"] for record in result["records"]] == ["V1"]
    assert result["records"][0]["department"] == "外一科"
    assert result["records"][0]["dischargeDate"] == "2026-04-08"


def test_get_workstation_data_multiple_discharge_records_do_not_duplicate_records(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="多条出院记录",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            discharge_datetime=None,
        ),
    )
    _insert_discharge_records(
        workstation_session_factory,
        {
            "institute_id": "I",
            "patient_id": "P1",
            "visit_id": "V1",
            "document_id": "DR1",
            "dept_name": "中医科",
            "discharge_time": datetime(2026, 4, 5, 10, 0),
            "update_time": datetime(2026, 4, 5, 11, 0),
        },
        {
            "institute_id": "I",
            "patient_id": "P1",
            "visit_id": "V1",
            "document_id": "DR2",
            "dept_name": "外一科",
            "discharge_time": datetime(2026, 4, 6, 10, 0),
            "update_time": datetime(2026, 4, 6, 11, 0),
        },
    )

    result = get_workstation_data(
        dept="外一科",
        start_date=datetime(2026, 4, 6).date(),
        end_date=datetime(2026, 4, 6).date(),
        date_field="discharge",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert len(result["records"]) == 1
    assert result["records"][0]["id"] == "V1"
    assert result["records"][0]["department"] == "外一科"
    assert result["records"][0]["dischargeDate"] == "2026-04-06"


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


def test_get_workstation_data_department_stats_prefer_discharge_record_dept(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="甲",
            admission_dept_name="内科",
            discharge_dept_name=None,
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            discharge_datetime=None,
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P2",
            visit_id="V2",
            name="乙",
            admission_dept_name="外一科",
            discharge_dept_name=None,
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            discharge_datetime=datetime(2026, 4, 8, 9, 0),
        ),
    )
    _insert_discharge_records(
        workstation_session_factory,
        {
            "institute_id": "I",
            "patient_id": "P1",
            "visit_id": "V1",
            "document_id": "DR1",
            "dept_name": "中医科",
            "discharge_time": datetime(2026, 4, 5, 10, 0),
            "update_time": datetime(2026, 4, 5, 11, 0),
        },
    )

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    department_totals = {dept["name"]: dept["total"] for dept in result["departments"]}
    assert department_totals["全部科室"] == 2
    assert department_totals["中医科"] == 1
    assert department_totals["外一科"] == 1
    assert "内科" not in department_totals


def test_get_workstation_data_orders_newly_synced_records_first_within_department(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="OLD_ADMISSION",
            name="旧同步但入院较新",
            admission_dept_name="中医科",
            admission_datetime=datetime(2026, 5, 28, 8, 0),
            discharge_datetime=datetime(2026, 5, 29, 8, 0),
            update_time=datetime(2026, 5, 26, 8, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P2",
            visit_id="NEW_SYNC",
            name="新同步但入院较早",
            admission_dept_name="中医科",
            admission_datetime=datetime(2026, 5, 20, 8, 0),
            discharge_datetime=datetime(2026, 5, 21, 8, 0),
            update_time=datetime(2026, 5, 30, 8, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P3",
            visit_id="OLDER_SYNC",
            name="更早同步",
            admission_dept_name="中医科",
            admission_datetime=datetime(2026, 5, 25, 8, 0),
            update_time=datetime(2026, 5, 25, 8, 0),
        ),
    )

    result = get_workstation_data(
        dept="中医科",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert [record["id"] for record in result["records"]] == [
        "NEW_SYNC",
        "OLD_ADMISSION",
        "OLDER_SYNC",
    ]
    assert result["records"][0]["updateTime"] == "2026-05-30 08:00:00"
    assert result["records"][0]["sortTime"] == "2026-05-30 08:00:00"
