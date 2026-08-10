from types import SimpleNamespace
from datetime import datetime

import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def test_serialize_record_row_should_include_programmatic_execution_keys():
    service = CustomQCWorkspaceService()
    row = SimpleNamespace(
        institute_id="H1",
        patient_id="P1",
        visit_id="V1",
        name="张三",
        mr_no="MR1",
        inpat_no="IP1",
        discharge_dept_name="普外科",
        admission_dept_name="普外科",
        attending_physician_sign="李医生",
        admission_datetime="2026-04-01 08:00:00",
        discharge_datetime="2026-04-05 09:00:00",
        record_content="病历正文",
        update_time=None,
    )

    item = service._serialize_record_row(row)

    assert item["institute_id"] == "H1"
    assert item["patient_id"] == "P1"
    assert item["medical_text"] == "病历正文"
    assert item["admission_datetime"] == "2026-04-01 08:00:00"
    assert item["discharge_datetime"] == "2026-04-05 09:00:00"


def test_serialize_record_row_should_not_treat_update_time_as_discharge_time():
    service = CustomQCWorkspaceService()
    row = SimpleNamespace(
        institute_id="H1",
        patient_id="P1",
        visit_id="RUN-1",
        name="在院患者",
        mr_no="MR1",
        inpat_no="IP1",
        discharge_dept_name=None,
        admission_dept_name="重症医学科",
        attending_physician_sign="李医生",
        admission_datetime="2026-07-30 08:00:00",
        discharge_datetime=None,
        record_content="在院病历",
        update_time="2026-07-30 10:00:00",
    )

    item = service._serialize_record_row(row)

    assert item["scope"] == "running"
    assert item["status"] == "running"
    assert item["discharge_date"] == ""
    assert item["discharge_datetime"] == ""


def test_hydrate_records_with_medical_text_should_preserve_scope_and_dates(monkeypatch):
    service = CustomQCWorkspaceService()

    class _Row:
        institute_id = "H1"
        patient_id = "P1"
        visit_id = "V1"
        name = "张三"
        department = "普外科"
        attending_physician_sign = "李医生"
        record_content = "补齐病历正文"

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return [_Row()]

    class _Session:
        def query(self, *_args, **_kwargs):
            return _Query()

        def close(self):
            return None

    monkeypatch.setattr("app.services.custom_qc_workspace_service._session", lambda: _Session())

    hydrated = service.hydrate_records_with_medical_text(
        [
            {
                "record_id": "V1",
                "visit_id": "V1",
                "scope": "final",
                "discharge_datetime": "2026-04-05 09:00:00",
                "medical_text": "",
            }
        ]
    )

    assert hydrated[0]["scope"] == "final"
    assert hydrated[0]["discharge_datetime"] == "2026-04-05 09:00:00"
    assert hydrated[0]["medical_text"] == "补齐病历正文"


def test_hydrate_records_should_keep_same_visit_cases_separate(monkeypatch):
    service = CustomQCWorkspaceService()

    def row(institute_id: str, patient_id: str, content: str):
        return SimpleNamespace(
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id="V-SAME",
            name=patient_id,
            department="重症医学科",
            attending_physician_sign="李医生",
            record_content=content,
        )

    class _Query:
        def filter(self, *_args, **_kwargs):
            return self

        def all(self):
            return [row("H1", "P1", "病历一"), row("H2", "P2", "病历二")]

    class _Session:
        def query(self, *_args, **_kwargs):
            return _Query()

        def close(self):
            return None

    monkeypatch.setattr(workspace_module, "_session", lambda: _Session())

    hydrated = service.hydrate_records_with_medical_text(
        [
            {"institute_id": "H1", "patient_id": "P1", "visit_id": "V-SAME"},
            {"institute_id": "H2", "patient_id": "P2", "visit_id": "V-SAME"},
        ]
    )

    assert [item["medical_text"] for item in hydrated] == ["病历一", "病历二"]
    assert len({item["record_key"] for item in hydrated}) == 2


def test_collect_records_should_use_inpat_registration_for_active_record_without_frontpage(
    monkeypatch,
):
    service = CustomQCWorkspaceService()
    active_registration = SimpleNamespace(
        institute_id="H1",
        patient_id="P1",
        visit_id="ACTIVE-1",
        name="在院患者",
        mr_no="",
        inpat_no="IP-1",
        admission_dept_name="重症医学科（ICU）",
        discharge_dept_name=None,
        admission_datetime="2026-07-30 08:00:00",
        discharge_datetime=None,
        record_content="在院登记资料",
    )

    class _Query:
        def __init__(self, rows):
            self.rows = rows

        def filter(self, *_args, **_kwargs):
            return self

        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return self.rows

    class _Session:
        def query(self, model, *_args, **_kwargs):
            if model is workspace_module.InpatRegistration:
                return _Query([active_registration])
            return _Query([])

        def close(self):
            return None

    monkeypatch.setattr(workspace_module, "_session", lambda: _Session())
    monkeypatch.setattr(
        service,
        "_build_records_query",
        lambda *_args, **_kwargs: _Query([]),
    )

    records = service.collect_records(
        scope="running",
        department=None,
        doctor=None,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=["ACTIVE-1"],
    )

    assert records == [
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "record_id": "ACTIVE-1",
            "visit_id": "ACTIVE-1",
            "patient_name": "在院患者",
            "mr_no": "",
            "inpat_no": "IP-1",
            "scope": "running",
            "department": "重症医学科（ICU）",
            "doctor": "",
            "admission_date": "2026-07-30",
            "discharge_date": "",
            "admission_datetime": "2026-07-30 08:00:00",
            "discharge_datetime": "",
            "status": "running",
            "medical_text": "在院登记资料",
            "medical_text_length": 6,
        }
    ]
    assert service.count_records(
        scope="running",
        department=None,
        doctor=None,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
        record_ids=["ACTIVE-1"],
    ) == 1


def test_count_records_should_count_distinct_full_case_coordinates(monkeypatch):
    service = CustomQCWorkspaceService()
    selected_columns = []

    class _IdentityQuery:
        def with_entities(self, *columns):
            selected_columns.extend(column.key for column in columns)
            return self

        def distinct(self):
            return self

        def subquery(self):
            return "case_identity_rows"

    class _CountQuery:
        def select_from(self, identity_rows):
            assert identity_rows == "case_identity_rows"
            return self

        def scalar(self):
            return 2

    class _Session:
        def query(self, *_args):
            return _CountQuery()

        def close(self):
            return None

    monkeypatch.setattr(workspace_module, "_session", lambda: _Session())
    monkeypatch.setattr(
        service,
        "_build_records_query",
        lambda *_args, **_kwargs: _IdentityQuery(),
    )

    assert service.count_records(
        scope="all",
        department=None,
        doctor=None,
        date_field="admission",
        start_date=None,
        end_date=None,
        keyword=None,
    ) == 2
    assert selected_columns == ["institute_id", "patient_id", "visit_id"]


def test_collect_records_visit_date_matches_admission_or_discharge_date() -> None:
    engine = create_engine("sqlite:///:memory:")
    for model in (
        workspace_module.MedicalRecordFrontpage,
        workspace_module.AdmissionRecord,
        workspace_module.DischargeRecord,
    ):
        model.__table__.create(bind=engine)

    with Session(engine) as session:
        session.add_all(
            [
                workspace_module.MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P1",
                    visit_id="ADMISSION-HIT",
                    admission_datetime=datetime(2026, 5, 10, 8, 0),
                    discharge_datetime=datetime(2026, 6, 2, 10, 0),
                ),
                workspace_module.MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P2",
                    visit_id="DISCHARGE-HIT",
                    admission_datetime=datetime(2026, 4, 10, 8, 0),
                    discharge_datetime=datetime(2026, 5, 20, 10, 0),
                ),
                workspace_module.MedicalRecordFrontpage(
                    institute_id="H1",
                    patient_id="P3",
                    visit_id="OUTSIDE",
                    admission_datetime=datetime(2026, 4, 1, 8, 0),
                    discharge_datetime=datetime(2026, 6, 1, 10, 0),
                ),
            ]
        )
        session.commit()

        rows = CustomQCWorkspaceService()._build_records_query(
            session,
            scope="all",
            department=None,
            doctor=None,
            date_field="visit",
            start_date="2026-05-01",
            end_date="2026-05-31",
            keyword=None,
        ).all()

    assert {row[0].visit_id for row in rows} == {"ADMISSION-HIT", "DISCHARGE-HIT"}


def test_refresh_parent_batch_job_persists_completed_status_after_children_finish(monkeypatch):
    service = CustomQCWorkspaceService()
    executed = []

    class _Result:
        def mappings(self):
            return self

        def first(self):
            return {"id": "parent-1"}

    class _Session:
        def execute(self, statement):
            executed.append(statement)
            return _Result()

        def commit(self):
            return None

        def close(self):
            return None

    parent = {"id": "parent-1", "job_kind": "parent", "summary": {}}
    aggregate = {
        **parent,
        "status": "completed",
        "summary": {"progress": {"step_key": "completed"}},
        "success_count": 7,
        "failed_count": 0,
        "issue_records": 1,
        "compliant_records": 6,
        "total_tokens": 9,
        "total_processing_time": 0.2,
    }
    monkeypatch.setattr(workspace_module, "_session", lambda: _Session())
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda _: parent)
    monkeypatch.setattr(service, "_aggregate_parent_job", lambda *_args, **_kwargs: aggregate)

    service.refresh_parent_batch_job(parent_job_id="parent-1")

    update_statement = next(statement for statement in executed if statement.is_update)
    assert update_statement.compile().params["status"] == "completed"


def test_record_result_envelope_keeps_delivery_facts_evidence_and_model_analysis():
    item = CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "record_id": "R1",
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V1",
            "rule_id": "LX0609-018",
            "status": "non_compliant",
            "findings": "引擎已形成的不合规结论。",
            "criterion_results": [{"key": "chief_complaint_length", "passed": False}],
            "customer_display_facts": {
                "chief_complaint_length": 14,
                "source_document_id": "doc-1",
            },
            "customer_evidence": [{"source_document_id": "doc-1"}],
            "model_analysis": "主诉仅描述症状，无法区分第一诊断。",
            "debug_trace": {"must_not": "persist"},
        }
    )

    assert item["conclusion"] == "引擎已形成的不合规结论。"
    assert item["decision_facts"] == {"chief_complaint_length": 14}
    assert item["customer_display_facts"] == {"chief_complaint_length": 14}
    assert item["criterion_results"] == [{"key": "chief_complaint_length", "passed": False}]
    assert item["record_ref"].startswith("rec_")
    assert item["evidence"][0]["source_ref"].startswith("src_")
    assert "source_document_id" not in item["evidence"][0]
    assert "record_id" not in item
    assert "patient_id" not in item
    assert item["model_analysis"] == "主诉仅描述症状，无法区分第一诊断。"
    assert "debug_trace" not in item


def test_record_result_envelope_normalizes_legacy_semantic_analysis_name():
    item = CustomQCWorkspaceService._envelope_item_from_rule_result(
        {"rule_id": "LX0609-018", "semantic_analysis": "主诉症状无法区分急性下呼吸道感染。"}
    )

    assert item["model_analysis"] == "主诉症状无法区分急性下呼吸道感染。"


def test_record_result_envelope_keeps_llm_analysis_and_actionable_suggestion():
    item = CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": "LX0609-018",
            "status": "non_compliant",
            "medical_analysis": "主诉仅写咳嗽、咳痰，不能区分慢阻肺急性加重与下呼吸道感染。",
            "model_suggestion": "补充急性加重的时间、痰色变化及感染相关症状。",
        }
    )

    assert item["model_analysis"] == "主诉仅写咳嗽、咳痰，不能区分慢阻肺急性加重与下呼吸道感染。"
    assert item["suggestion"] == "补充急性加重的时间、痰色变化及感染相关症状。"


def test_record_result_envelope_keeps_compliant_facts_criteria_and_evidence():
    item = CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": "LX0609-001",
            "status": "compliant",
            "detail": "入院记录在入院后 2 小时内完成。",
            "actual": "记录时间：2026-07-07 16:10",
            "standard": "应在入院后 24 小时内完成。",
            "criterion_results": [{"criterion_id": "within_24_hours", "status": "passed"}],
            "decision_facts": {"elapsed_hours": 2},
            "evidence_refs": [{"source_ref": "src_admission_1"}],
        }
    )

    assert item["detail"] == "入院记录在入院后 2 小时内完成。"
    assert item["actual"] == "记录时间：2026-07-07 16:10"
    assert item["standard"] == "应在入院后 24 小时内完成。"
    assert item["criterion_results"] == [{"criterion_id": "within_24_hours", "status": "passed"}]
    assert item["customer_display_facts"] == {"elapsed_hours": 2}
    assert item["evidence"][0]["source_ref"].startswith("src_")
    assert item["evidence"][0]["source_ref"] != "src_admission_1"


def test_record_result_envelope_normalizes_text_evidence_to_empty_array():
    item = CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": "LX0609-003",
            "status": "not_applicable",
            "findings": "本次不适用。",
            "evidence": "完整适用性证据未触发本质控点。",
        }
    )

    assert item["evidence"] == []


def test_record_result_envelope_keeps_data_gap_source_and_field_facts():
    item = CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": "LX0609-011",
            "status": "data_gap",
            "reason_code": "required_source_unavailable",
            "reason": "影像报告已检出，但对应病程记录来源未返回。",
            "missing_sources": ["daily_course_record"],
            "missing_fields": ["report_time"],
            "source_availability": {"daily_course_record": "unavailable"},
        }
    )

    assert item["detail"] == "影像报告已检出，但对应病程记录来源未返回。"
    assert item["data_gap_details"] == {
        "reason_code": "required_source_unavailable",
        "missing_sources": ["daily_course_record"],
        "missing_fields": ["report_time"],
        "source_availability": {"daily_course_record": "unavailable"},
    }


def test_record_result_envelope_preserves_data_gap_customer_message():
    item = CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": "LX0609-011",
            "status": "data_gap",
            "reason_code": "required_field_missing",
            "customer_message": "缺少检查报告时间，暂时无法完成本项质控。",
            "data_gap_details": {
                "reason_label": "关键字段缺失",
                "customer_message": "缺少检查报告时间，暂时无法完成本项质控。",
            },
        }
    )

    assert item["customer_message"] == "缺少检查报告时间，暂时无法完成本项质控。"
    assert item["data_gap_details"]["reason_label"] == "关键字段缺失"


def test_record_result_envelope_preserves_finalized_state_fields_verbatim():
    item = CustomQCWorkspaceService._envelope_item_from_rule_result(
        {
            "rule_id": "LX0609-029",
            "status": "uncertain",
            "result_status": "uncertain",
            "reason_code": "customer_explanation_incomplete",
            "is_compliant": None,
            "evidence": [],
        }
    )

    assert "is_compliant" in item
    assert {
        key: item.get(key)
        for key in ("status", "result_status", "reason_code", "is_compliant")
    } == {
        "status": "uncertain",
        "result_status": "uncertain",
        "reason_code": "customer_explanation_incomplete",
        "is_compliant": None,
    }


def test_record_result_envelopes_are_grouped_by_full_case_coordinate():
    service = CustomQCWorkspaceService()
    executed = []

    class _Session:
        def execute(self, statement):
            executed.append(statement)
            return None

    items = [
        {
            "institute_id": "H1",
            "patient_id": "P1",
            "visit_id": "V-SAME",
            "record_id": "V-SAME",
            "rule_id": "LX0609-001",
            "rule_code": "LX0609-001",
            "status": "compliant",
        },
        {
            "institute_id": "H2",
            "patient_id": "P2",
            "visit_id": "V-SAME",
            "record_id": "V-SAME",
            "rule_id": "LX0609-001",
            "rule_code": "LX0609-001",
            "status": "non_compliant",
        },
    ]

    service._write_record_result_envelopes(
        _Session(),
        job_row={
            "id": "job-1",
            "created_by": "tester",
            "filters_json": '{"rule_set_key":"luxian_0609_qc_v1"}',
        },
        items=items,
        now=datetime(2026, 8, 9, 18, 0, 0),
    )

    insert_params = [statement.compile().params for statement in executed if statement.is_insert]
    assert len(insert_params) == 2
    assert {
        (params["institute_id"], params["patient_id"], params["visit_id"])
        for params in insert_params
    } == {("H1", "P1", "V-SAME"), ("H2", "P2", "V-SAME")}
