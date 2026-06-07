from __future__ import annotations

import json
import os
import sys
from pathlib import Path


BACKEND_PATH = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))
os.environ.setdefault("JWT_SECRET", "test-secret")

from app.routers import icd_search  # noqa: E402
from app.services.qc_agent.schemas import SuggestRecordICDCodesInput  # noqa: E402
from app.services.qc_agent.tools import suggest_record_icd_codes  # noqa: E402


SENSITIVE_TEXT = "完整病历正文不允许返回"
SENSITIVE_KEYS = {
    "medical_text",
    "documents",
    "bundle",
    "record_content",
    "internal_data",
    "raw_response",
    "embedding",
    "vector",
    "structured_context",
}


class FixtureWorkspace:
    def __init__(self, case: dict) -> None:
        self.case = case
        self.persist_called = False

    def collect_records(self, *, record_ids=None, **_kwargs):
        if record_ids and self.case["visit_id"] not in record_ids:
            return []
        return [
            {
                **self.case["record_summary"],
                "visit_id": self.case["visit_id"],
                "patient_id": self.case["patient_id"],
            }
        ]

    def hydrate_records_with_medical_text(self, records):
        record = records[0]
        return [
            {
                **record,
                "medical_text": SENSITIVE_TEXT,
                "structured_context": self.case["structured_context"],
                "documents": [{"content": SENSITIVE_TEXT}],
                "bundle": {"raw": SENSITIVE_TEXT},
            }
        ]

    def load_or_assemble_scene_bundle(self, *_args, **_kwargs):
        self.persist_called = True
        raise AssertionError("编码建议不应写入或组装正式业务数据")

    def upsert_scene_bundle(self, *_args, **_kwargs):
        self.persist_called = True
        raise AssertionError("编码建议不应持久化")


def _load_case() -> dict:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "icd_coding_cases.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    return cases[0]


def _seed_local_icd(monkeypatch) -> None:
    icd_search._initialized = True
    icd_search._icd10_data = [
        {"code": "E11.900", "name": "2型糖尿病", "name_lower": "2型糖尿病", "code_lower": "e11.900"},
        {"code": "I10.x01", "name": "高血压", "name_lower": "高血压", "code_lower": "i10.x01"},
    ]
    icd_search._icd10_clinical_data = [
        {"code": "E11.900x001", "name": "2型糖尿病", "name_lower": "2型糖尿病", "code_lower": "e11.900x001"},
        {"code": "I10.x00x001", "name": "高血压", "name_lower": "高血压", "code_lower": "i10.x00x001"},
    ]
    icd_search._icd9cm3_data = [
        {
            "code": "51.2301",
            "name": "腹腔镜胆囊切除术",
            "name_lower": "腹腔镜胆囊切除术",
            "code_lower": "51.2301",
        }
    ]
    icd_search._code_mapping = {
        "clinical_to_insurance": {
            "E11.900x001": {"code": "E11.900", "name": "2型糖尿病", "diff": True},
            "I10.x00x001": {"code": "I10.x01", "name": "高血压", "diff": True},
        },
        "insurance_to_clinical": {
            "E11.900": {"code": "E11.900x001", "name": "2型糖尿病", "diff": True},
            "I10.x01": {"code": "I10.x00x001", "name": "高血压", "diff": True},
        },
    }
    monkeypatch.setattr(icd_search, "_load_data", lambda: None)


def _assert_no_sensitive_output(value) -> None:
    text = str(value)
    assert SENSITIVE_TEXT not in text
    for key in SENSITIVE_KEYS:
        assert key not in text


def test_record_coding_suggestions_use_fixture_sources_and_stable_candidates(monkeypatch):
    case = _load_case()
    _seed_local_icd(monkeypatch)

    observation = suggest_record_icd_codes(
        SuggestRecordICDCodesInput(
            visit_id=case["visit_id"],
            patient_id=case["patient_id"],
            include_procedures=True,
            limit_per_item=3,
        ),
        workspace=FixtureWorkspace(case),  # type: ignore[arg-type]
    )

    assert observation.status == "success"
    public = observation.public_data
    assert public["record_summary"]["visit_id"] == case["visit_id"]
    assert public["record_summary"]["patient_name"] == "李明"

    diagnosis_candidates = public["diagnosis_candidates"]
    procedure_candidates = public["procedure_candidates"]
    assert [item["name"] for item in diagnosis_candidates] == ["2型糖尿病", "高血压"]
    assert [item["source"] for item in diagnosis_candidates] == ["病案首页", "诊断表"]
    assert procedure_candidates[0]["name"] == "腹腔镜胆囊切除术"
    assert procedure_candidates[0]["source"] == "手术表"

    expected = case["expected"]
    assert diagnosis_candidates[0]["candidates"][0]["code"] == expected["main_diagnosis_code"]
    assert diagnosis_candidates[1]["candidates"][0]["code"] == expected["other_diagnosis_code"]
    assert procedure_candidates[0]["candidates"][0]["code"] == expected["procedure_code"]
    assert all(item["low_confidence"] is False for item in diagnosis_candidates + procedure_candidates)
    _assert_no_sensitive_output(public)
