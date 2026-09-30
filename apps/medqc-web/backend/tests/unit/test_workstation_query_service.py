"""工作台病历池查询服务单元测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database.connection import Base
from app.database.models.cdm import (
    AdmissionRecord,
    HospitalizationStatusProjection,
    InpatRegistration,
    MedicalRecordFrontpage,
    QCResult,
)
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


def test_discharge_record_columns_keep_first_search_path_schema():
    """同名表跨 schema 时，列类型必须来自 search_path 优先命中的表。"""

    required_columns = {
        "institute_id",
        "patient_id",
        "visit_id",
        "document_id",
        "dept_name",
        "discharge_time",
        "update_time",
    }
    rows = [
        {
            "table_schema": "cdm",
            "column_name": column_name,
            "data_type": "text" if column_name == "discharge_time" else "character varying",
            "udt_name": "text" if column_name == "discharge_time" else "varchar",
        }
        for column_name in required_columns
    ]
    rows.append(
        {
            "table_schema": "public",
            "column_name": "discharge_time",
            "data_type": "timestamp without time zone",
            "udt_name": "timestamp",
        }
    )

    class Result:
        def mappings(self):
            return self

        def all(self):
            return rows

    class SessionStub:
        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, *_args, **_kwargs):
            return Result()

    columns = query_service_module._workstation_discharge_record_columns(SessionStub())

    assert columns is not None
    assert columns["discharge_time"]["table_schema"] == "cdm"
    assert columns["discharge_time"]["data_type"] == "text"


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


_ORIGINAL_LOAD_SCORE_STATES = query_service_module._load_score_states


@pytest.fixture(autouse=True)
def _default_score_states_are_no_standard(monkeypatch):
    """旧工作台单测不建评分标准表，默认得分替身为“未配置评分标准”。"""

    monkeypatch.setattr(
        query_service_module,
        "_load_score_states",
        lambda page_scenes, anchors, **_kwargs: (
            {
                identity: {"status": "no_standard", "score": None, "grade": None, "veto_hit": None,
                           "standard_id": None, "reason_code": None}
                for identity in page_scenes
            },
            {scene: {"status": "no_standard"} for scene in set(page_scenes.values())},
        ),
    )


@pytest.fixture()
def workstation_session_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            MedicalRecordFrontpage.__table__,
            InpatRegistration.__table__,
            AdmissionRecord.__table__,
            HospitalizationStatusProjection.__table__,
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
        session.execute(text("""
            CREATE TABLE visit_index (
                institute_id VARCHAR(100) NOT NULL,
                patient_id VARCHAR(100) NOT NULL,
                visit_id VARCHAR(100) NOT NULL,
                scene_current VARCHAR(32) NOT NULL DEFAULT '',
                updated_at DATETIME,
                PRIMARY KEY (institute_id, patient_id, visit_id)
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
            InpatRegistration.__table__,
            AdmissionRecord.__table__,
            HospitalizationStatusProjection.__table__,
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


def _insert_visit_index_rows(session_factory, *rows: dict) -> None:
    with session_factory() as session:
        session.execute(
            text("""
                INSERT INTO visit_index (
                    institute_id,
                    patient_id,
                    visit_id,
                    scene_current,
                    updated_at
                )
                VALUES (
                    :institute_id,
                    :patient_id,
                    :visit_id,
                    :scene_current,
                    :updated_at
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


def _qc_projection_loader_invalid_envelope(record_refs):
    return {
        (
            str(ref["institute_id"]),
            str(ref["patient_id"]),
            str(ref["visit_id"]),
        ): {
            "status": "technical_error",
            "reason_code": "canonical_result_envelope_invalid",
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


def test_synced_inpatient_without_frontpage_enters_workstation_by_visit_index(
    workstation_session_factory,
):
    with workstation_session_factory() as session:
        session.add(
            InpatRegistration(
                institute_id="H1",
                patient_id="P-RUNNING",
                visit_id="V-RUNNING",
                name="在院患者",
                sex="女",
                age_year="56",
                inpat_no="ZY-001",
                admission_dept_name="重症医学科",
                admission_datetime=datetime(2026, 8, 12, 9, 30),
                discharge_datetime=None,
                update_time=datetime(2026, 8, 13, 8, 0),
            )
        )
        session.commit()
    _insert_visit_index_rows(
        workstation_session_factory,
        {
            "institute_id": "H1",
            "patient_id": "P-RUNNING",
            "visit_id": "V-RUNNING",
            "scene_current": "running",
            "updated_at": datetime(2026, 8, 13, 8, 5),
        },
    )

    result = get_workstation_data(
        hospital_status="inpatient",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert result["qc_summary"]["total_records"] == 1
    assert result["departments"][0]["total"] == 1
    assert result["records"] == [
        {
            **result["records"][0],
            "id": "V-RUNNING",
            "recordKey": '["H1","P-RUNNING","V-RUNNING"]',
            "instituteId": "H1",
            "patientId": "P-RUNNING",
            "name": "在院患者",
            "sex": "女",
            "age": 56,
            "department": "重症医学科",
            "admissionDate": "2026-08-12",
            "dischargeDate": "",
            "cdmFrontpageEmpty": True,
        }
    ]


def test_synced_admission_record_without_frontpage_or_registration_enters_workstation(
    workstation_session_factory,
):
    with workstation_session_factory() as session:
        session.add(
            AdmissionRecord(
                institute_id="H1",
                patient_id="P-ADMISSION",
                visit_id="V-ADMISSION",
                document_id="AR-1",
                name="入院记录患者",
                sex="男",
                age_year="42",
                inpat_no="ZY-002",
                dept_name="神经内科",
                bed_no="08",
                admission_datetime=datetime(2026, 8, 11, 10, 0),
                attending_physician_sign="陈医师",
                update_time=datetime(2026, 8, 13, 9, 0),
            )
        )
        session.commit()
    _insert_visit_index_rows(
        workstation_session_factory,
        {
            "institute_id": "H1",
            "patient_id": "P-ADMISSION",
            "visit_id": "V-ADMISSION",
            "scene_current": "running",
            "updated_at": datetime(2026, 8, 13, 9, 5),
        },
    )

    result = get_workstation_data(
        dept="神经内科",
        doctor="陈医师",
        start_date=datetime(2026, 8, 11).date(),
        end_date=datetime(2026, 8, 11).date(),
        date_field="admission",
        hospital_status="inpatient",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert result["records"][0]["recordKey"] == '["H1","P-ADMISSION","V-ADMISSION"]'
    assert result["records"][0]["name"] == "入院记录患者"
    assert result["records"][0]["department"] == "神经内科"
    assert result["records"][0]["bedNo"] == "08"
    assert result["doctors"] == [
        {"name": "全部主管医师", "total": 1},
        {"name": "陈医师", "total": 1},
    ]


def test_synced_record_without_frontpage_uses_discharge_record_for_final_scope(
    workstation_session_factory,
):
    with workstation_session_factory() as session:
        session.add(
            AdmissionRecord(
                institute_id="H1",
                patient_id="P-FINAL",
                visit_id="V-FINAL",
                document_id="AR-FINAL",
                name="无首页出院患者",
                dept_name="外科",
                admission_datetime=datetime(2026, 8, 1, 8, 0),
            )
        )
        session.commit()
    _insert_discharge_records(
        workstation_session_factory,
        {
            "institute_id": "H1",
            "patient_id": "P-FINAL",
            "visit_id": "V-FINAL",
            "document_id": "DR-FINAL",
            "dept_name": "骨科",
            "discharge_time": datetime(2026, 8, 12, 15, 30),
            "update_time": datetime(2026, 8, 12, 16, 0),
        },
    )
    _insert_visit_index_rows(
        workstation_session_factory,
        {
            "institute_id": "H1",
            "patient_id": "P-FINAL",
            "visit_id": "V-FINAL",
            "scene_current": "final",
            "updated_at": datetime(2026, 8, 12, 16, 5),
        },
    )

    result = get_workstation_data(
        dept="骨科",
        hospital_status="discharged",
        start_date=datetime(2026, 8, 12).date(),
        end_date=datetime(2026, 8, 12).date(),
        date_field="discharge",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert result["records"][0]["dischargeDate"] == "2026-08-12"
    assert result["records"][0]["department"] == "骨科"


def test_pagination_merges_frontpage_and_no_frontpage_records_without_duplicates(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P-MR",
            visit_id="V-MR",
            name="首页患者",
            admission_datetime=datetime(2026, 8, 10, 8, 0),
            update_time=datetime(2026, 8, 10, 9, 0),
        ),
    )
    with workstation_session_factory() as session:
        session.add(
            InpatRegistration(
                institute_id="H1",
                patient_id="P-NO-MR",
                visit_id="V-NO-MR",
                name="无首页患者",
                admission_datetime=datetime(2026, 8, 11, 8, 0),
                update_time=datetime(2026, 8, 11, 9, 0),
            )
        )
        session.commit()
    _insert_visit_index_rows(
        workstation_session_factory,
        {
            "institute_id": "H1",
            "patient_id": "P-NO-MR",
            "visit_id": "V-NO-MR",
            "scene_current": "running",
            "updated_at": datetime(2026, 8, 11, 9, 5),
        },
    )

    common = {
        "page_size": 1,
        "hospital_status": "inpatient",
        "session_factory": workstation_session_factory,
        "settings_loader": _workstation_settings_loader,
        "demo_policy": _no_demo_policy,
    }
    first_page = get_workstation_data(page=1, **common)
    second_page = get_workstation_data(page=2, **common)

    assert first_page["total"] == second_page["total"] == 2
    assert first_page["qc_summary"] == second_page["qc_summary"]
    assert first_page["records"][0]["recordKey"] != second_page["records"][0]["recordKey"]


def test_visit_index_does_not_duplicate_frontpage_or_cross_same_visit_coordinate(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P1",
            visit_id="V-SHARED",
            name="已有首页",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 8, 10, 8, 0),
        ),
    )
    with workstation_session_factory() as session:
        session.add_all(
            [
                InpatRegistration(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="V-SHARED",
                    name="首页对应登记",
                    admission_dept_name="内科",
                ),
                InpatRegistration(
                    institute_id="H2",
                    patient_id="P2",
                    visit_id="V-SHARED",
                    name="另一机构在院患者",
                    admission_dept_name="外科",
                ),
            ]
        )
        session.commit()
    _insert_visit_index_rows(
        workstation_session_factory,
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V-SHARED",
            "scene_current": "running",
            "updated_at": datetime(2026, 8, 13, 10, 0),
        },
        {
            "institute_id": "H2",
            "patient_id": "P2",
            "visit_id": "V-SHARED",
            "scene_current": "running",
            "updated_at": datetime(2026, 8, 13, 10, 0),
        },
    )

    result = get_workstation_data(
        hospital_status="inpatient",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 2
    records_by_key = {row["recordKey"]: row for row in result["records"]}
    assert set(records_by_key) == {
        '["H1","P1","V-SHARED"]',
        '["H2","P2","V-SHARED"]',
    }
    assert records_by_key['["H1","P1","V-SHARED"]']["name"] == "已有首页"
    assert records_by_key['["H2","P2","V-SHARED"]']["name"] == "另一机构在院患者"


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


def test_workstation_qc_projection_preserves_canonical_result_envelope_invalid(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="H1",
            patient_id="P1",
            visit_id="V1",
            name="Envelope状态不一致",
            update_time=datetime(2026, 8, 8, 12, 0),
        ),
    )

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_qc_projection_loader_invalid_envelope,
    )

    assert result["records"][0]["latest_qc_summary"] == {
        "status": "technical_error",
        "reason_code": "canonical_result_envelope_invalid",
    }
    assert result["qc_summary"]["technical_error_records"] == 1


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
    assert result["records"][0]["dischargeDatetime"] == "2026-04-05 10:00:00"
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
    assert result["records"][0]["dischargeDatetime"] == "2026-04-08 09:00:00"


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


def test_get_workstation_data_filters_hospital_status_on_discharge_evidence(
    workstation_session_factory,
):
    """权威出院时间或有效出院文书均结束在院状态。"""
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
            visit_id="V-DISCHARGE-WITHOUT-TIME",
            name="出院文书无时间",
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
            "visit_id": "V-DISCHARGE-WITHOUT-TIME",
            "document_id": "DR-EMPTY",
            "dept_name": "内科",
            "discharge_time": None,
            "update_time": datetime(2026, 4, 3, 13, 0),
        },
    )

    common_kwargs = {
        "page_size": 3,
        "session_factory": workstation_session_factory,
        "settings_loader": _workstation_settings_loader,
        "demo_policy": _no_demo_policy,
    }
    discharged_first_page = get_workstation_data(
        hospital_status="discharged",
        page=1,
        **common_kwargs,
    )
    inpatient = get_workstation_data(hospital_status="inpatient", **common_kwargs)

    assert discharged_first_page["total"] == 3
    assert discharged_first_page["departments"][0]["total"] == 3
    assert discharged_first_page["qc_summary"]["total_records"] == 3
    assert {record["id"] for record in discharged_first_page["records"]} == {
        "V-DISCHARGE-RECORD",
        "V-FRONTPAGE-DISCHARGE",
        "V-DISCHARGE-WITHOUT-TIME",
    }
    assert inpatient["total"] == 0
    assert inpatient["departments"][0]["total"] == 0
    assert inpatient["qc_summary"]["total_records"] == 0
    assert inpatient["records"] == []


def test_discharge_document_without_time_is_final_but_not_in_discharge_date_range(
    workstation_session_factory,
):
    """有效出院记录足以结束在院状态，但更新时间不得冒充出院日期。"""

    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P-DISCHARGE-DOC",
            visit_id="V-DISCHARGE-DOC",
            name="出院时间待补",
            admission_dept_name="普通外科",
            admission_datetime=datetime(2026, 4, 17, 8, 0),
            discharge_datetime=None,
        ),
    )
    _insert_discharge_records(
        workstation_session_factory,
        {
            "institute_id": "I",
            "patient_id": "P-DISCHARGE-DOC",
            "visit_id": "V-DISCHARGE-DOC",
            "document_id": "DR-VALID",
            "dept_name": "普通外科",
            "discharge_time": None,
            "update_time": datetime(2026, 4, 20, 12, 46),
        },
    )

    common_kwargs = {
        "session_factory": workstation_session_factory,
        "settings_loader": _workstation_settings_loader,
        "demo_policy": _no_demo_policy,
    }
    inpatient = get_workstation_data(hospital_status="inpatient", **common_kwargs)
    discharged = get_workstation_data(hospital_status="discharged", **common_kwargs)
    discharge_date_filtered = get_workstation_data(
        hospital_status="discharged",
        start_date=datetime(2026, 4, 20).date(),
        end_date=datetime(2026, 4, 20).date(),
        date_field="discharge",
        **common_kwargs,
    )

    assert inpatient["total"] == 0
    assert discharged["total"] == 1
    assert discharged["records"][0]["id"] == "V-DISCHARGE-DOC"
    assert discharged["records"][0]["dischargeDate"] == ""
    assert discharge_date_filtered["total"] == 0


def test_get_workstation_data_rejects_unknown_hospital_status(workstation_session_factory):
    with pytest.raises(ValueError, match="hospital_status"):
        get_workstation_data(
            hospital_status="pending_discharge",
            session_factory=workstation_session_factory,
            settings_loader=_workstation_settings_loader,
            demo_policy=_no_demo_policy,
        )


def test_get_workstation_data_sorts_inpatients_by_length_of_stay_across_pages(
    workstation_session_factory,
):
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P-RECENT",
            visit_id="V-RECENT",
            name="最近入院",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 4, 10, 8, 0),
            update_time=datetime(2026, 4, 20, 8, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P-MIDDLE",
            visit_id="V-MIDDLE",
            name="中间入院",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 4, 5, 8, 0),
            update_time=datetime(2026, 4, 21, 8, 0),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P-LONGEST",
            visit_id="V-LONGEST",
            name="住院最久",
            admission_dept_name="内科",
            admission_datetime=datetime(2026, 4, 1, 8, 0),
            update_time=datetime(2026, 4, 19, 8, 0),
        ),
    )
    common_kwargs = {
        "hospital_status": "inpatient",
        "inpatient_sort": "longest",
        "page_size": 2,
        "session_factory": workstation_session_factory,
        "settings_loader": _workstation_settings_loader,
        "demo_policy": _no_demo_policy,
    }

    first_page = get_workstation_data(page=1, **common_kwargs)
    second_page = get_workstation_data(page=2, **common_kwargs)

    assert [record["id"] for record in first_page["records"]] == [
        "V-LONGEST",
        "V-MIDDLE",
    ]
    assert [record["id"] for record in second_page["records"]] == ["V-RECENT"]

    recent_first = get_workstation_data(
        **{**common_kwargs, "inpatient_sort": "recent", "page_size": 3}
    )
    assert [record["id"] for record in recent_first["records"]] == [
        "V-RECENT",
        "V-MIDDLE",
        "V-LONGEST",
    ]


def test_get_workstation_data_rejects_unknown_inpatient_sort(workstation_session_factory):
    with pytest.raises(ValueError, match="inpatient_sort"):
        get_workstation_data(
            hospital_status="inpatient",
            inpatient_sort="priority",
            session_factory=workstation_session_factory,
            settings_loader=_workstation_settings_loader,
            demo_policy=_no_demo_policy,
        )


def test_get_workstation_data_today_inpatient_scope_uses_verified_status(
    workstation_session_factory,
):
    """快捷范围只保留今日由轻量状态核验确认仍在院的记录。"""

    # “今日”按医院时区（Asia/Shanghai）与产品同源，避免本机时区跨日时误判。
    from app.services.medical_records.query_service import _hospital_today

    today = datetime.combine(_hospital_today(), datetime.min.time()).replace(hour=9)
    _insert_workstation_records(
        workstation_session_factory,
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P-TODAY",
            visit_id="V-TODAY-INPATIENT",
            name="今日同步在院",
            admission_dept_name="内科",
            admission_datetime=today,
            local_sync_completed_at=today,
        ),
        HospitalizationStatusProjection(
            institute_id="I",
            patient_id="P-TODAY",
            visit_id="V-TODAY-INPATIENT",
            status="inpatient",
            verified_at=today,
            source="inpat_registration",
        ),
        HospitalizationStatusProjection(
            institute_id="I",
            patient_id="P-OLD",
            visit_id="V-OLD-INPATIENT",
            status="inpatient",
            verified_at=today - timedelta(days=1),
            source="inpat_registration",
        ),
        HospitalizationStatusProjection(
            institute_id="I",
            patient_id="P-DISCHARGED",
            visit_id="V-TODAY-DISCHARGED",
            status="discharged",
            verified_at=today,
            source="discharge_record",
            discharge_datetime=today,
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P-OLD",
            visit_id="V-OLD-INPATIENT",
            name="历史同步在院",
            admission_dept_name="内科",
            admission_datetime=today,
            local_sync_completed_at=today - timedelta(days=1),
        ),
        MedicalRecordFrontpage(
            institute_id="I",
            patient_id="P-DISCHARGED",
            visit_id="V-TODAY-DISCHARGED",
            name="今日同步已出院",
            admission_dept_name="内科",
            admission_datetime=today,
            discharge_datetime=today,
            local_sync_completed_at=today,
        ),
    )

    result = get_workstation_data(
        sync_scope="today_inpatient",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
    )

    assert result["total"] == 1
    assert [record["id"] for record in result["records"]] == ["V-TODAY-INPATIENT"]


def test_get_workstation_data_rejects_unknown_sync_scope(workstation_session_factory):
    with pytest.raises(ValueError, match="sync_scope"):
        get_workstation_data(
            sync_scope="last_run",
            session_factory=workstation_session_factory,
            settings_loader=_workstation_settings_loader,
            demo_policy=_no_demo_policy,
        )


# ---------------------------------------------------------------------------
# 病历审核状态挂载（P0-2）：只对本页 ready 摘要原样挂 review_state
# ---------------------------------------------------------------------------


def _anchored_projection_loader(record_refs):
    projections = {}
    for ref in record_refs:
        identity = (str(ref["institute_id"]), str(ref["patient_id"]), str(ref["visit_id"]))
        if identity[2] in {"V1", "V2"}:
            projections[identity] = {
                "status": "ready",
                "completed_at": "2026-08-08T10:00:00",
                "total_rule_count": 1,
                "status_counts": {"compliant": 1},
                "root_job_id": f"job-{identity[2]}",
                "envelope_id": f"env-{identity[2]}",
            }
        else:
            projections[identity] = {"status": "not_run"}
    return projections


def _insert_review_state_records(session_factory):
    _insert_workstation_records(
        session_factory,
        *(
            MedicalRecordFrontpage(
                institute_id="H1", patient_id=f"P{index}", visit_id=f"V{index}",
                name=f"病历{index}", update_time=datetime(2026, 8, 8, 12, 0) - timedelta(hours=index),
            )
            for index in (1, 2, 3)
        ),
    )


def test_workstation_attaches_review_state_to_ready_page_summaries(workstation_session_factory):
    _insert_review_state_records(workstation_session_factory)
    calls = []

    def loader(results):
        calls.append(results)
        return {("H1", "P1", "V1"): "pending_recheck", ("H1", "P2", "V2"): "bogus"}

    result = get_workstation_data(
        page_size=50,
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_anchored_projection_loader,
        review_state_loader=loader,
    )

    summaries = {record["id"]: record["latest_qc_summary"] for record in result["records"]}
    assert summaries["V1"]["review_state"] == "pending_recheck"
    assert summaries["V2"]["review_state"] is None  # 非法取值不透传
    assert summaries["V3"] == {"status": "not_run"}  # 非 ready 不挂
    # 锚点不进入客户可见摘要
    assert all("root_job_id" not in item and "envelope_id" not in item for item in summaries.values())
    assert len(calls) == 1
    assert sorted(calls[0], key=lambda item: item["visit_id"]) == [
        {"institute_id": "H1", "patient_id": "P1", "visit_id": "V1", "job_id": "job-V1",
         "envelope_id": "env-V1", "rule_set_key": "luxian_0609_qc_v1"},
        {"institute_id": "H1", "patient_id": "P2", "visit_id": "V2", "job_id": "job-V2",
         "envelope_id": "env-V2", "rule_set_key": "luxian_0609_qc_v1"},
    ]
    assert result["qc_summary"]["ready_records"] == 2


def test_workstation_review_state_only_for_current_page(workstation_session_factory):
    _insert_review_state_records(workstation_session_factory)
    calls = []

    def loader(results):
        calls.append([item["visit_id"] for item in results])
        return {}

    result = get_workstation_data(
        page=2,
        page_size=1,
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_anchored_projection_loader,
        review_state_loader=loader,
    )

    assert [record["id"] for record in result["records"]] == ["V2"]
    assert calls == [["V2"]]
    assert result["records"][0]["latest_qc_summary"]["review_state"] is None


def test_workstation_review_state_failure_degrades_to_unknown(workstation_session_factory, caplog):
    _insert_review_state_records(workstation_session_factory)

    def broken(_results):
        raise RuntimeError("SELECT secret FROM qc_record_reviews")

    with caplog.at_level("WARNING", logger=query_service_module.__name__):
        result = get_workstation_data(
            session_factory=workstation_session_factory,
            settings_loader=_workstation_settings_loader,
            demo_policy=_no_demo_policy,
            qc_projection_loader=_anchored_projection_loader,
            review_state_loader=broken,
        )

    summaries = {record["id"]: record["latest_qc_summary"] for record in result["records"]}
    assert summaries["V1"]["status"] == "ready" and summaries["V1"]["review_state"] is None
    assert summaries["V2"]["review_state"] is None
    assert result["qc_summary"]["ready_records"] == 2
    assert "RuntimeError" in caplog.text and "secret" not in caplog.text


def test_workstation_default_review_state_loader_uses_review_service(workstation_session_factory, monkeypatch):
    from app.services import record_review_service

    _insert_review_state_records(workstation_session_factory)
    calls = []

    def fake_batch(results):
        calls.append(results)
        return {("H1", "P1", "V1"): "approved"}

    monkeypatch.setattr(record_review_service, "batch_review_states", fake_batch)
    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_anchored_projection_loader,
    )

    summaries = {record["id"]: record["latest_qc_summary"] for record in result["records"]}
    assert summaries["V1"]["review_state"] == "approved"
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# 列表按审核状态筛选（P1-A 合同第 1 节）：先按审核状态过滤完整集合，再分页
# ---------------------------------------------------------------------------

_REVIEW_FILTER_STATES = {
    "V1": "pending_review",
    "V2": "pending_recheck",
    "V3": "approved",
    "V4": "doubtful",
    "V5": "pending_review",
}


def _review_filter_projection_loader(record_refs):
    """V1–V5 ready（带锚点），V6 技术错误，V7 未质控，V-IDX 为就诊索引病例（ready）。"""

    projections = {}
    for ref in record_refs:
        identity = (str(ref["institute_id"]), str(ref["patient_id"]), str(ref["visit_id"]))
        visit_id = identity[2]
        if visit_id in _REVIEW_FILTER_STATES or visit_id == "V-IDX":
            projections[identity] = {
                "status": "ready",
                "completed_at": "2026-08-08T10:00:00",
                "total_rule_count": 2,
                "status_counts": {"compliant": 1, "non_compliant": 1},
                "root_job_id": f"job-{visit_id}",
                "envelope_id": f"env-{visit_id}",
            }
        elif visit_id == "V6":
            projections[identity] = {
                "status": "technical_error",
                "reason_code": "canonical_envelope_invalid",
            }
        else:
            projections[identity] = {"status": "not_run"}
    return projections


def _insert_review_filter_records(session_factory):
    _insert_workstation_records(
        session_factory,
        *(
            MedicalRecordFrontpage(
                institute_id="H1", patient_id=f"P{index}", visit_id=f"V{index}",
                name=f"病历{index}", update_time=datetime(2026, 8, 8, 12, 0) - timedelta(hours=index),
            )
            for index in range(1, 8)
        ),
    )


def _review_filter_loader(calls):
    def loader(results):
        calls.append(sorted(item["visit_id"] for item in results))
        states = {**_REVIEW_FILTER_STATES, "V-IDX": "pending_recheck"}
        return {
            (item["institute_id"], item["patient_id"], item["visit_id"]): states[item["visit_id"]]
            for item in results
            if item["visit_id"] in states
        }

    return loader


def _get_with_review_state(session_factory, review_state, calls, **kwargs):
    return get_workstation_data(
        session_factory=session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_review_filter_projection_loader,
        review_state_loader=_review_filter_loader(calls),
        review_state=review_state,
        **kwargs,
    )


def test_review_state_filter_multi_value_filters_full_set_before_paging(workstation_session_factory):
    _insert_review_filter_records(workstation_session_factory)
    calls = []

    result = _get_with_review_state(
        workstation_session_factory, ["pending_review", "pending_recheck"], calls, page_size=50,
    )

    assert [record["id"] for record in result["records"]] == ["V1", "V2", "V5"]
    assert [record["latest_qc_summary"]["review_state"] for record in result["records"]] == [
        "pending_review", "pending_recheck", "pending_review",
    ]
    assert result["total"] == 3 and result["totalPages"] == 1
    # qc_summary 按过滤后的集合计算
    assert result["qc_summary"]["total_records"] == 3
    assert result["qc_summary"]["ready_records"] == 3
    assert result["qc_summary"]["not_run_records"] == 0
    assert result["qc_summary"]["technical_error_records"] == 0
    assert result["qc_summary"]["status_counts"] == {"compliant": 3, "non_compliant": 3}
    # 只对完整集合中 ready 病例批量读取一次；本页挂载复用同一结果
    assert calls == [["V1", "V2", "V3", "V4", "V5"]]


def test_review_state_filter_paginates_after_filtering(workstation_session_factory):
    _insert_review_filter_records(workstation_session_factory)

    page_two = _get_with_review_state(
        workstation_session_factory, ["pending_review", "pending_recheck"], [], page=2, page_size=2,
    )

    assert [record["id"] for record in page_two["records"]] == ["V5"]
    assert page_two["total"] == 3 and page_two["totalPages"] == 2
    assert page_two["qc_summary"]["total_records"] == 3
    assert page_two["records"][0]["latest_qc_summary"]["review_state"] == "pending_review"


def test_review_state_filter_single_value_and_comma_string(workstation_session_factory):
    _insert_review_filter_records(workstation_session_factory)

    doubtful = _get_with_review_state(workstation_session_factory, ["doubtful"], [])
    assert [record["id"] for record in doubtful["records"]] == ["V4"]

    decided = _get_with_review_state(workstation_session_factory, "approved,doubtful", [])
    assert [record["id"] for record in decided["records"]] == ["V3", "V4"]


def test_review_state_filter_excludes_not_run_and_technical_error(workstation_session_factory):
    _insert_review_filter_records(workstation_session_factory)

    result = _get_with_review_state(
        workstation_session_factory,
        ["pending_review", "pending_recheck", "approved", "doubtful"],
        [],
    )

    ids = [record["id"] for record in result["records"]]
    assert ids == ["V1", "V2", "V3", "V4", "V5"]
    assert result["total"] == 5
    assert result["qc_summary"]["technical_error_records"] == 0
    assert result["qc_summary"]["not_run_records"] == 0


def test_review_state_filter_empty_result_when_no_ready_case(workstation_session_factory):
    _insert_review_filter_records(workstation_session_factory)
    calls = []

    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        review_state_loader=_review_filter_loader(calls),
        review_state=["pending_review"],
    )

    # 默认投影替身全部为 not_run：没有 ready 病例，不读取审核状态，结果为空
    assert result["records"] == [] and result["total"] == 0
    assert result["qc_summary"]["total_records"] == 0
    assert calls == []


def test_review_state_filter_applies_to_visit_index_records(workstation_session_factory):
    _insert_review_filter_records(workstation_session_factory)
    with workstation_session_factory() as session:
        session.add(
            InpatRegistration(
                institute_id="H1", patient_id="P-IDX", visit_id="V-IDX", name="索引病例",
                admission_dept_name="内科", admission_datetime=datetime(2026, 8, 12, 9, 30),
                discharge_datetime=None, update_time=datetime(2026, 8, 13, 8, 0),
            )
        )
        session.commit()
    _insert_visit_index_rows(
        workstation_session_factory,
        {"institute_id": "H1", "patient_id": "P-IDX", "visit_id": "V-IDX",
         "scene_current": "running", "updated_at": datetime(2026, 8, 13, 8, 5)},
    )

    rechecks = _get_with_review_state(workstation_session_factory, ["pending_recheck"], [])
    assert sorted(record["id"] for record in rechecks["records"]) == ["V-IDX", "V2"]
    assert rechecks["total"] == 2 and rechecks["qc_summary"]["total_records"] == 2

    approved = _get_with_review_state(workstation_session_factory, ["approved"], [])
    assert [record["id"] for record in approved["records"]] == ["V3"]


def test_review_state_filter_failure_raises_unavailable(workstation_session_factory, caplog):
    _insert_review_filter_records(workstation_session_factory)

    def broken(_results):
        raise RuntimeError("SELECT secret FROM qc_record_reviews")

    with caplog.at_level("WARNING", logger=query_service_module.__name__):
        with pytest.raises(query_service_module.WorkstationReviewStateUnavailable):
            get_workstation_data(
                session_factory=workstation_session_factory,
                settings_loader=_workstation_settings_loader,
                demo_policy=_no_demo_policy,
                qc_projection_loader=_review_filter_projection_loader,
                review_state_loader=broken,
                review_state=["pending_review"],
            )
    assert "RuntimeError" in caplog.text and "secret" not in caplog.text


@pytest.mark.parametrize("value", [[], ["rejected"], ["pending_review", ""], "pending_review,bogus"])
def test_review_state_filter_rejects_invalid_values(workstation_session_factory, value):
    with pytest.raises(ValueError, match="review_state"):
        get_workstation_data(
            session_factory=workstation_session_factory,
            settings_loader=_workstation_settings_loader,
            demo_policy=_no_demo_policy,
            review_state=value,
        )


def test_without_review_state_parameter_behaviour_unchanged(workstation_session_factory):
    """不带参数：total/qc_summary 覆盖全集，审核状态只按本页读取。"""

    _insert_review_filter_records(workstation_session_factory)
    calls = []

    result = get_workstation_data(
        page_size=3,
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_review_filter_projection_loader,
        review_state_loader=_review_filter_loader(calls),
    )

    assert result["total"] == 7
    assert result["qc_summary"]["total_records"] == 7
    assert result["qc_summary"]["technical_error_records"] == 1
    assert result["qc_summary"]["not_run_records"] == 1
    assert [record["id"] for record in result["records"]] == ["V1", "V2", "V3"]
    assert calls == [["V1", "V2", "V3"]]


# ---------------------------------------------------------------------------
# 列表得分挂载（P2-S 第 5 节）：只对本页 ready 摘要原样挂 score_state
# ---------------------------------------------------------------------------


def test_workstation_attaches_score_state_to_ready_page_summaries(workstation_session_factory):
    _insert_review_state_records(workstation_session_factory)
    calls = []

    def loader(page_scenes, anchors):
        calls.append((dict(page_scenes), dict(anchors)))
        return (
            {
                ("H1", "P1", "V1"): {"status": "scored", "score": 97.0, "grade": "甲", "veto_hit": False,
                                     "standard_id": "std-1", "reason_code": None},
                ("H1", "P2", "V2"): {"status": "bogus"},
            },
            {"running": {"status": "configured", "standard_id": "std-1"}},
        )

    result = get_workstation_data(
        page_size=50,
        hospital_status="inpatient",
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_anchored_projection_loader,
        review_state_loader=lambda anchors: {},
        score_state_loader=loader,
    )

    summaries = {record["id"]: record["latest_qc_summary"] for record in result["records"]}
    assert summaries["V1"]["score_state"]["score"] == 97.0 and summaries["V1"]["score_state"]["grade"] == "甲"
    assert summaries["V2"]["score_state"]["status"] == "unavailable"  # 非法取值不透传
    assert "score_state" not in summaries["V3"]  # 非 ready 不挂
    assert len(calls) == 1
    page_scenes, anchors = calls[0]
    assert page_scenes == {("H1", "P1", "V1"): "running", ("H1", "P2", "V2"): "running"}
    assert anchors[("H1", "P1", "V1")]["envelope_id"] == "env-V1"
    assert result["score_standards"] == {"running": {"status": "configured", "standard_id": "std-1"}}


def test_workstation_score_scene_follows_list_scope(workstation_session_factory):
    _insert_review_state_records(workstation_session_factory)
    scenes = []

    def loader(page_scenes, anchors):
        scenes.append(set(page_scenes.values()))
        return {}, {}

    get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        qc_projection_loader=_anchored_projection_loader,
        review_state_loader=lambda anchors: {},
        score_state_loader=loader,
    )
    # 全部范围：无出院时间的记录按运行场景计分
    assert scenes == [{"running"}]


def test_workstation_score_failure_degrades_to_unavailable(workstation_session_factory, caplog):
    _insert_review_state_records(workstation_session_factory)

    def broken(page_scenes, anchors):
        raise RuntimeError("SELECT secret FROM qc_scoring_standards")

    with caplog.at_level("WARNING", logger=query_service_module.__name__):
        result = get_workstation_data(
            session_factory=workstation_session_factory,
            settings_loader=_workstation_settings_loader,
            demo_policy=_no_demo_policy,
            qc_projection_loader=_anchored_projection_loader,
            review_state_loader=lambda anchors: {},
            score_state_loader=broken,
        )

    summaries = {record["id"]: record["latest_qc_summary"] for record in result["records"]}
    assert summaries["V1"]["status"] == "ready"
    assert summaries["V1"]["score_state"]["status"] == "unavailable"
    assert result["qc_summary"]["ready_records"] == 2
    assert result["score_standards"] == {}
    assert "RuntimeError" in caplog.text and "secret" not in caplog.text


def test_workstation_default_score_loader_uses_scoring_service(workstation_session_factory, monkeypatch):
    from app.services import scoring_service

    _insert_review_state_records(workstation_session_factory)
    # 撤掉默认替身，验证真实默认加载路径
    monkeypatch.setattr(query_service_module, "_load_score_states", _ORIGINAL_LOAD_SCORE_STATES)
    monkeypatch.setattr(
        query_service_module,
        "_load_latest_luxian_0609_qc_summaries",
        lambda record_refs, **_kwargs: _anchored_projection_loader(record_refs),
    )
    calls = []

    def fake_page(page_scenes, anchors, *, session_factory):
        calls.append(session_factory)
        return {identity: {"status": "no_standard"} for identity in page_scenes}, {"running": {"status": "no_standard"}}

    monkeypatch.setattr(scoring_service, "score_workstation_page", fake_page)
    result = get_workstation_data(
        session_factory=workstation_session_factory,
        settings_loader=_workstation_settings_loader,
        demo_policy=_no_demo_policy,
        review_state_loader=lambda anchors: {},
    )
    summaries = {record["id"]: record["latest_qc_summary"] for record in result["records"]}
    assert summaries["V1"]["score_state"]["status"] == "no_standard"
    assert calls == [workstation_session_factory]
