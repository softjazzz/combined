from __future__ import annotations

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.difficult_case_result_mapping import (
    safe_difficult_case_customer_display_facts,
)


_NON_COMPLIANT_FACTS = {
    "verification_kind": "uncertain_diagnosis_discussion_check",
    "admission_time": "2026-08-01 08:00:00",
    "uncertain_record_times": ["2026-08-09 09:00:00"],
    "discussion_count": 0,
}


def test_050_mapping_strips_legacy_private_payload_without_reading_it() -> None:
    raw = {
        **_NON_COMPLIANT_FACTS,
        "raw_text": "PRIVATE_MEDICAL_BODY",
        "source_document_ids": ["PRIVATE-DOC"],
    }

    assert safe_difficult_case_customer_display_facts(
        rule_id="LX0609-03-02-01", raw=raw
    ) == _NON_COMPLIANT_FACTS


def test_050_finalizer_keeps_decision_and_rejects_status_fact_conflict() -> None:
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-03-02-01",
            "status": "non_compliant",
            "reason_code": "required_document_missing",
        },
        raw_facts=_NON_COMPLIANT_FACTS,
    )
    assert handled is True
    assert finalized["status"] == "non_compliant"
    assert finalized["customer_display_facts"] == _NON_COMPLIANT_FACTS

    conflict, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-03-02-01",
            "status": "compliant",
            "reason_code": "requirement_satisfied",
            "findings": "不应保留",
        },
        raw_facts=_NON_COMPLIANT_FACTS,
    )
    assert handled is True
    assert conflict["status"] == "technical_error"
    assert conflict["reason_code"] == "model_invalid_output"
    assert "findings" not in conflict


def test_050_scope_uncertainty_requires_uncertain_status() -> None:
    facts = {
        "verification_kind": "uncertain_diagnosis_scope_unverified",
        "admission_time": "2026-08-01 08:00:00",
        "uncertain_record_times": ["2026-08-09 09:00:00"],
        "discussion_count": 0,
    }
    finalized, _ = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-03-02-01",
            "status": "uncertain",
            "reason_code": "diagnosis_scope_uncertain",
        },
        raw_facts=facts,
    )
    assert finalized["status"] == "uncertain"
    assert finalized["customer_display_facts"] == facts
