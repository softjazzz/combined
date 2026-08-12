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
import app.services.medical_records.query_service as query_service_module
from app.services.medical_records.query_service import get_workstation_data


class DummyWorkflowQueueStateService:
    def get_state_map(self, **_kwargs):
        return {}

    def backfill_frontpage_generate(self, **_kwargs):
        return None


class RunningWorkflowQueueStateService:
    def get_state_map(self, **_kwargs):
        return {
            "V-SHARED": {
                "queue_status": "running",
                "queue_status_source": "runtime",
            }
        }

    def backfill_frontpage_generate(self, **_kwargs):
        return None


@pytest.fixture(autouse=True)
def _default_qc_projection_is_not_run_for_frontpage_only_fixture(monkeypatch):
    """旧工作台单测不建 QC 结果表，显式替身隔离本轮投影依赖。"""

    monkeypatch.setattr(
        query_service_module,
        "_load_latest_luxian_0609_qc_summaries",
        lambda record_refs, **_kwargs: {
            (
                str(ref["institute_id"]),
                str(ref["patient_id"]),
                str(ref["visit_id"]),
            ): {"status": "not_run"}
            for ref in record_refs
        },
    )


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


def _qc_projection_loader_for_test(record_refs):
    """公开病历池入口的受控 Canonical 投影替身。"""

    projections = {}
    for ref in record_refs:
        identity = (
            str(ref["institute_id"]),
            str(ref["patient_id"]),
            str(ref["visit_id"]),
        )
        if identity == ("H1", "P1", "V1"):
            projections[identity] = {
                "status": "ready",
                "completed_at": "2026-08-08T10:00:00",
                "total_rule_count": 2,
                "status_counts": {"compliant": 1, "non_compliant": 1},
            }
        elif identity == ("H2", "P2", "V-SHARED"):
            projections[identity] = {
                "status": "technical_error",
                "reason_code": "record_result_task_generation_conflict",
            }
        else:
            projections[identity] = {"status": "not_run"}
    return projections


def _qc_projection_loader_missing_envelope(record_refs):
    return {
        (
            str(ref["institute_id"]),
            str(ref["patient_id"]),
            str(ref["visit_id"]),
        ): {
            "status": "technical_error",
            "reason_code": "canonical_envelope_missing",
        }
        for ref in record_refs
    }


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


def test_get_workstation_data_keeps_same_visit_id_records_isolated_by_three_coordinate(
    workstation_session_factory,
):
    """同名 visit_id 不能让床位或传统质控状态串到另一机构病历。"""
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P1",
            visit_id="V-SHARED",
            name="机构一患者",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="H2",
            patient_id="P2",
            visit_id="V-SHARED",
            name="机构二患者",
            admission_dept_name="外科",
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
    )
    with workstation_session_factory() as session:
        session.add_all(
            [
                AdmissionRecord(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V-SHARED",
                    bed_no="01",
                ),
                AdmissionRecord(
                    institute_id="H2",
                    patient_id="P2",
                    visit_id="V-SHARED",
                    bed_no="02",
                ),
                QCResult(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V-SHARED",
                    qc_type="form",
                    severity="error",
                    status="open",
                ),
                QCResult(
                    institute_id="H2",
                    patient_id="P2",
                    visit_id="V-SHARED",
                    qc_type="form",
                    severity="info",
                    status="resolved",
                ),
            ]
        )
        session.commit()

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    records_by_key = {record["recordKey"]: record for record in result["records"]}
    assert records_by_key['["H1","P1","V-SHARED"]']["id"] == "V-SHARED"
    assert records_by_key['["H1","P1","V-SHARED"]']["bedNo"] == "01"
    assert records_by_key['["H1","P1","V-SHARED"]']["status"] == "has_defects"
    assert records_by_key['["H2","P2","V-SHARED"]']["id"] == "V-SHARED"
    assert records_by_key['["H2","P2","V-SHARED"]']["bedNo"] == "02"
    assert records_by_key['["H2","P2","V-SHARED"]']["status"] == "completed"


def test_workstation_queue_state_remains_pending_when_same_visit_id_is_on_other_page(
    workstation_session_factory,
    monkeypatch,
):
    """visit_id 级旧队列状态不得跨页投影给不同三坐标病历。"""
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P1",
            visit_id="V-SHARED",
            name="机构一患者",
            admission_dept_name="内科",
            update_time=datetime(2026, 5, 26, 9, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="H2",
            patient_id="P2",
            visit_id="V-SHARED",
            name="机构二患者",
            admission_dept_name="外科",
            update_time=datetime(2026, 5, 25, 9, 0),
        ),
    )
    monkeypatch.setattr(
        "app.services.medical_records.query_service.default_workflow_queue_state_service",
        RunningWorkflowQueueStateService(),
    )

    result = get_workstation_data(
        page=1,
        page_size=1,
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 2
    assert len(result["records"]) == 1
    assert result["records"][0]["recordKey"] == '["H1","P1","V-SHARED"]'
    assert result["records"][0]["frontpageGenerateQueueStatus"] == "pending"


def test_workstation_record_key_does_not_collide_when_coordinate_contains_separator(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="A|B",
            patient_id="C",
            visit_id="D",
            name="第一份",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 5, 26, 9, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="A",
            patient_id="B|C",
            visit_id="D",
            name="第二份",
            admission_dept_name="外科",
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
    )

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert {record["recordKey"] for record in result["records"]} == {
        '["A|B","C","D"]',
        '["A","B|C","D"]',
    }


def test_workstation_qc_summary_is_full_scope_and_independent_of_page(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P1",
            visit_id="V1",
            name="第一页病历",
            update_time=datetime(2026, 8, 8, 12, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P2",
            visit_id="V2",
            name="第二页病历",
            update_time=datetime(2026, 8, 8, 11, 0),
        ),
    )

    common_kwargs = {
        "page_size": 1,
        "session_factory": workstation_session_factory,
        "settings_loader": _workstation_settings_loader,
        "demo_policy": _no_demo_policy,
        "qc_projection_loader": _qc_projection_loader_for_test,
    }
    first_page = get_workstation_data(page=1, **common_kwargs)
    second_page = get_workstation_data(page=2, **common_kwargs)

    expected_summary = {
        "total_records": 2,
        "ready_records": 1,
        "not_run_records": 1,
        "technical_error_records": 0,
        "status_counts": {"compliant": 1, "non_compliant": 1},
        "running_state": "unknown",
    }
    assert first_page["qc_summary"] == expected_summary
    assert second_page["qc_summary"] == expected_summary
    assert first_page["records"][0]["latest_qc_summary"]["status"] == "ready"
    assert second_page["records"][0]["latest_qc_summary"] == {"status": "not_run"}


def test_workstation_qc_projection_uses_three_coordinates_and_keeps_source_state_unknown(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P1",
            visit_id="V-SHARED",
            name="无运行结果",
            update_time=datetime(2026, 8, 8, 12, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="H2",
            patient_id="P2",
            visit_id="V-SHARED",
            name="代次冲突",
            update_time=datetime(2026, 8, 8, 11, 0),
        ),
    )

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_qc_projection_loader_for_test,
    )

    records_by_key = {record["recordKey"]: record for record in result["records"]}
    assert records_by_key['["H1","P1","V-SHARED"]']["latest_qc_summary"] == {
        "status": "not_run"
    }
    assert records_by_key['["H2","P2","V-SHARED"]']["latest_qc_summary"] == {
        "status": "technical_error",
        "reason_code": "generation_conflict",
    }
    assert all(
        record["source_state"]
        == {"status": "unknown", "last_sync_at": None, "reason_code": None}
        for record in result["records"]
    )
    assert result["qc_summary"]["technical_error_records"] == 1


def test_workstation_qc_projection_never_falls_back_when_canonical_envelope_is_missing(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P1",
            visit_id="V1",
            name="Envelope缺失",
            update_time=datetime(2026, 8, 8, 12, 0),
        ),
    )

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_qc_projection_loader_missing_envelope,
    )

    assert result["records"][0]["latest_qc_summary"] == {
        "status": "technical_error",
        "reason_code": "canonical_envelope_missing",
    }
    assert result["qc_summary"]["status_counts"] == {}


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


def test_get_workstation_data_filters_by_attending_physician_and_returns_department_scoped_doctors(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V1",
            name="甲",
            admission_dept_name="重症医学科",
            attending_physician_sign="张医师",
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P2",
            visit_id="V2",
            name="乙",
            admission_dept_name="重症医学科",
            attending_physician_sign="李医师",
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P3",
            visit_id="V3",
            name="丙",
            admission_dept_name="普通外科",
            attending_physician_sign="王医师",
            admission_datetime=datetime(2026, 5, 25, 9, 0),
        ),
    )

    result = get_workstation_data(
        dept="重症医学科",
        doctor=" 张医师 ",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert result["qc_summary"]["total_records"] == 1
    assert [record["id"] for record in result["records"]] == ["V1"]
    assert result["doctors"] == [
        {"name": "全部主管医师", "total": 2},
        {"name": "张医师", "total": 1},
        {"name": "李医师", "total": 1},
    ]


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


def test_get_workstation_data_filters_hospital_status_on_resolved_discharge_time(
    workstation_session_factory,
):
    """在院/出院筛选必须由权威出院时间决定，且汇总不受分页影响。"""
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P1",
            visit_id="V-DISCHARGE-RECORD",
            name="出院记录时间",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            discharge_datetime=None,
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P2",
            visit_id="V-FRONTPAGE-DISCHARGE",
            name="首页出院时间",
            admission_dept_name="外科",
            admission_datetime=datetime(2026, 4, 2, 8, 0),
            discharge_datetime=datetime(2026, 4, 5, 9, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P3",
            visit_id="V-INPATIENT",
            name="仍在院",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 4, 3, 8, 0),
            discharge_datetime=None,
        ),
    )
    _insert_discharge_records(
        workstation_session_factory,
        {
            "institute_id": "I",
            "patient_id": "P1",
            "visit_id": "V-DISCHARGE-RECORD",
            "document_id": "DR-1",
            "dept_name": "内科",
            "discharge_time": "2026-04-04 12:00:00",
            "update_time": datetime(2026, 4, 4, 13, 0),
        },
        {
            "institute_id": "I",
            "patient_id": "P3",
            "visit_id": "V-INPATIENT",
            "document_id": "DR-EMPTY",
            "dept_name": "内科",
            "discharge_time": None,
            "update_time": datetime(2026, 4, 3, 13, 0),
        },
    )

    common_kwargs = {
        "page_size": 1,
        "session_factory": workstation_session_factory,
        "settings_loader": _workstation_settings_loader,
        "demo_policy": _no_demo_policy,
    }
    discharged_first_page = get_workstation_data(
        hospital_status="discharged",
        page=1,
        **common_kwargs,
    )
    discharged_second_page = get_workstation_data(
        hospital_status="discharged",
        page=2,
        **common_kwargs,
    )
    inpatient = get_workstation_data(hospital_status="inpatient", **common_kwargs)

    assert discharged_first_page["total"] == 2
    assert discharged_first_page["departments"][0]["total"] == 2
    assert discharged_first_page["qc_summary"]["total_records"] == 2
    assert discharged_second_page["qc_summary"] == discharged_first_page["qc_summary"]
    assert {record["id"] for record in [*discharged_first_page["records"], *discharged_second_page["records"]]} == {
        "V-DISCHARGE-RECORD",
        "V-FRONTPAGE-DISCHARGE",
    }
    assert inpatient["total"] == 1
    assert inpatient["departments"][0]["total"] == 1
    assert inpatient["qc_summary"]["total_records"] == 1
    assert [record["id"] for record in inpatient["records"]] == ["V-INPATIENT"]


def test_get_workstation_data_rejects_unknown_hospital_status(workstation_session_factory):
    with pytest.raises(ValueError, match="hospital_status"):
        get_workstation_data(
            hospital_status="pending_discharge",
            session_factory=workstation_session_factory,
            settings_loader=_workstation_settings_loader,
            demo_policy=_no_demo_policy,
        )
