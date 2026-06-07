from __future__ import annotations

import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.services.clinical_timeline_service import ClinicalTimelineService  # noqa: E402


def test_builds_diagnosis_timeline_from_bundle_documents():
    timeline = ClinicalTimelineService().build_from_bundle({
        "visit_id": "V-001",
        "source_documents": [
            {
                "document_type": "admission_record",
                "document_title": "入院记录",
                "record_time": "2026-04-01 09:00:00",
                "content": "入院诊断：K35.901 急性阑尾炎",
            },
            {
                "document_type": "discharge_record",
                "document_title": "出院记录",
                "record_time": "2026-04-06 10:00:00",
                "content": "出院诊断：K35.901 急性阑尾炎",
            },
        ],
    })

    assert timeline.visit_id == "V-001"
    assert len(timeline.diagnoses) == 1
    diagnosis = timeline.diagnoses[0]
    assert diagnosis.diagnosis_name == "急性阑尾炎"
    assert diagnosis.icd_code == "K35.901"
    assert diagnosis.first_mention_time == "2026-04-01 09:00:00"
    assert diagnosis.status == "confirmed"
    assert len(diagnosis.evidence) == 2


def test_verifies_planned_and_executed_procedure():
    timeline = ClinicalTimelineService().build_from_bundle({
        "visit_id": "V-002",
        "source_documents": [
            {
                "document_type": "presurg_summary",
                "document_title": "术前小结",
                "record_time": "2026-04-01 12:00:00",
                "content": "拟行腹腔镜下阑尾切除术。",
            },
            {
                "document_type": "surgery_record",
                "document_title": "手术记录",
                "record_time": "2026-04-01 15:30:00",
                "content": "手术名称：腹腔镜下阑尾切除术 47.0900，手术经过顺利。",
            },
        ],
    })

    assert len(timeline.procedures) == 1
    procedure = timeline.procedures[0]
    assert procedure.procedure_name == "阑尾切除术"
    assert procedure.icd9_code == "47.0900"
    assert procedure.status == "verified"
    assert procedure.plan_time == "2026-04-01 12:00:00"
    assert procedure.execution_time == "2026-04-01 15:30:00"


def test_marks_planned_only_and_executed_only_procedures():
    timeline = ClinicalTimelineService().build_from_bundle({
        "source_documents": [
            {
                "document_type": "presurg_summary",
                "document_title": "术前小结",
                "record_time": "2026-04-01 12:00:00",
                "content": "拟行胆囊切除术。",
            },
            {
                "document_type": "surgery_record",
                "document_title": "手术记录",
                "record_time": "2026-04-02 09:00:00",
                "content": "手术名称：阑尾切除术。",
            },
        ],
    })

    status_by_name = {item.procedure_name: item.status for item in timeline.procedures}

    assert status_by_name["胆囊切除术"] == "planned_only"
    assert status_by_name["阑尾切除术"] == "executed_only"


def test_empty_bundle_returns_data_quality_flags():
    timeline = ClinicalTimelineService().build_from_bundle({"visit_id": "V-EMPTY"})

    assert timeline.visit_id == "V-EMPTY"
    assert "missing_source_documents" in timeline.data_quality_flags
    assert "no_diagnosis_evidence" in timeline.data_quality_flags
    assert timeline.to_dict()["data_quality_flags"]


def test_compares_timeline_with_frontpage_diagnosis_and_procedure_fields():
    timeline = ClinicalTimelineService().build_from_bundle(
        {
            "visit_id": "V-003",
            "source_documents": [
                {
                    "document_type": "discharge_record",
                    "document_title": "出院记录",
                    "record_time": "2026-04-06 10:00:00",
                    "content": "出院诊断：K35.901 急性阑尾炎\n出院诊断：K65.001 急性腹膜炎",
                },
                {
                    "document_type": "surgery_record",
                    "document_title": "手术记录",
                    "record_time": "2026-04-01 15:30:00",
                    "content": "手术名称：腹腔镜下阑尾切除术 47.0900",
                },
            ],
        },
        frontpage={
            "diagnoses": [
                {"name": "急性阑尾炎"},
                {"name": "胆囊结石"},
            ],
            "surgeries": [],
        },
    )

    issue_keys = {(item.issue_type, item.item_category, item.item_name) for item in timeline.issues}

    assert ("missing_in_frontpage", "diagnosis", "急性腹膜炎") in issue_keys
    assert ("not_supported_by_record", "diagnosis", "胆囊结石") in issue_keys
    assert ("missing_in_frontpage", "procedure", "阑尾切除术") in issue_keys


def test_compares_planned_only_procedure_as_inconsistent():
    timeline = ClinicalTimelineService().build_from_bundle(
        {
            "source_documents": [
                {
                    "document_type": "presurg_summary",
                    "document_title": "术前小结",
                    "record_time": "2026-04-01 12:00:00",
                    "content": "拟行胆囊切除术。",
                },
            ],
        },
        frontpage={"diagnoses": [], "surgeries": []},
    )

    assert any(
        item.issue_type == "inconsistent"
        and item.item_category == "procedure"
        and item.item_name == "胆囊切除术"
        for item in timeline.issues
    )
