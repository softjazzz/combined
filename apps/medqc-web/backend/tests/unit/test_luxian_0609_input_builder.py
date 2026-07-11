from __future__ import annotations

import pytest

from app.services.luxian_0609 import build_luxian_0609_input_profile
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.execution import (
    Luxian0609ExecutionContext,
    attach_luxian_0609_execution_metadata,
)


@pytest.mark.unit
def test_luxian_0609_input_profile_should_describe_available_family_contexts():
    profile = build_luxian_0609_input_profile(
        visit_id="2207717",
        medical_text="完整病历文本",
        evidence_payload={
            "primary_document_text": "入院记录全文",
            "timeline_facts": [],
            "programmatic_timeline": {
                "documents": {
                    "admission_record": [
                        {"content": "入院记录正文", "record_time": "2026-01-01 09:00:00"},
                    ],
                    "daily_course_record": [
                        {"content": "病程记录正文", "record_time": "2026-01-03 09:00:00"},
                    ],
                    "surgery_record": [
                        {"content": "手术记录正文", "record_time": "2026-01-04 11:00:00"},
                    ],
                }
            },
        },
    )

    assert profile["mode"] == "full_text_compat"
    assert profile["visit_id"] == "2207717"
    assert profile["document_count"] == 3
    assert profile["source_table_counts"] == {
        "admission_record": 1,
        "daily_course_record": 1,
        "surgery_record": 1,
    }
    assert "course_quality" in profile["available_family_contexts"]
    assert "surgery_anesthesia" in profile["available_family_contexts"]
    assert profile["family_profiles"]["transfusion"]["ready_for_trimmed_context"] is False


@pytest.mark.unit
def test_luxian_0609_input_profile_should_tolerate_missing_payload():
    profile = build_luxian_0609_input_profile(
        visit_id="",
        medical_text="",
        evidence_payload=None,
    )

    assert profile["evidence_payload_available"] is False
    assert profile["document_count"] == 0
    assert profile["available_family_contexts"] == []


@pytest.mark.unit
def test_luxian_0609_execution_metadata_should_attach_input_profile():
    orchestrated: dict[str, object] = {}

    attach_luxian_0609_execution_metadata(
        orchestrated=orchestrated,
        rule_set_key=LUXIAN_0609_RULE_SET_KEY,
        context=Luxian0609ExecutionContext(
            input_profile={"mode": "full_text_compat", "document_count": 2},
            prepared_rule_count=9,
            executable_rule_count=6,
        ),
    )

    assert orchestrated["luxian_0609_input_profile"] == {
        "mode": "full_text_compat",
        "document_count": 2,
    }
    assert orchestrated["luxian_0609_execution_rule_count"] == 9
    assert orchestrated["luxian_0609_executed_rule_count"] == 6
