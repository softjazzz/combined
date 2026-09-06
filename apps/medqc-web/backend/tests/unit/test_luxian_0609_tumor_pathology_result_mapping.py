from __future__ import annotations

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.tumor_pathology_result_mapping import (
    safe_tumor_pathology_customer_display_facts,
    tumor_pathology_customer_fact_status_is_valid,
)


def _checked_sources() -> list[dict[str, str]]:
    return [
        {"source": "surgery_record", "state": "present"},
        {"source": "daily_course_record", "state": "present"},
    ]


def _facts(*, rule_id: str, state: str) -> dict[str, object]:
    if rule_id == "LX0609-013":
        return {
            "verification_kind": "pathology_result_documentation_check",
            "pathology_trigger_sources": ["pathology_exam_report"],
            "checked_target_sources": _checked_sources(),
            "requirement_met": state == "met",
        }
    if rule_id == "LX0609-019":
        if state == "missing":
            return {
                "failure_kind": "pathology_sampling_not_documented",
                "pathology_trigger_sources": ["pathology_exam_report"],
                "checked_target_sources": _checked_sources(),
            }
        return {
            "verification_kind": "pathology_sampling_documentation_check",
            "pathology_trigger_sources": ["pathology_exam_report"],
            "checked_target_sources": _checked_sources(),
            "documented_sources": ["surgery_record"],
            "requirement_met": True,
        }
    if rule_id == "LX0609-026":
        field_results = {
            "drug_name": "matched",
            "dose": "matched",
            "route": "matched",
            "time": "matched",
        }
        if state in {"mismatched", "unknown"}:
            field_results["dose"] = state
        return {
            "verification_kind": "chemotherapy_order_course_comparison",
            "order_count": 1,
            "field_results": field_results,
            "missing_order_fields": ["dose"] if state == "missing" else [],
        }
    return {
        "verification_kind": "malignant_discharge_plan_check",
        "malignant_diagnosis_present": True,
        "plan_items": {
            "future_plan": True,
            "tumor_treatment": False,
            "follow_up": True,
        },
        "requirement_met": state == "met",
    }


@pytest.mark.parametrize(
    ("rule_id", "state", "status"),
    [
        ("LX0609-013", "met", "compliant"),
        ("LX0609-013", "not_met", "non_compliant"),
        ("LX0609-019", "documented", "compliant"),
        ("LX0609-019", "missing", "non_compliant"),
        ("LX0609-026", "matched", "compliant"),
        ("LX0609-026", "mismatched", "non_compliant"),
        ("LX0609-026", "unknown", "data_gap"),
        ("LX0609-026", "missing", "data_gap"),
        ("LX0609-027", "met", "compliant"),
        ("LX0609-027", "not_met", "non_compliant"),
    ],
)
def test_tumor_pathology_status_contract_preserves_active_facts(
    rule_id: str, state: str, status: str
) -> None:
    safe_facts = safe_tumor_pathology_customer_display_facts(
        rule_id=rule_id,
        raw=_facts(rule_id=rule_id, state=state),
    )

    assert safe_facts is not None
    assert (
        tumor_pathology_customer_fact_status_is_valid(
            rule_id=rule_id,
            status=status,
            safe_facts=safe_facts,
        )
        is True
    )
    assert (
        tumor_pathology_customer_fact_status_is_valid(
            rule_id=rule_id,
            status="technical_error",
            safe_facts=safe_facts,
        )
        is True
    )


@pytest.mark.parametrize(
    ("rule_id", "state", "incorrect_status"),
    [
        ("LX0609-013", "met", "non_compliant"),
        ("LX0609-013", "not_met", "data_gap"),
        ("LX0609-019", "documented", "non_compliant"),
        ("LX0609-019", "missing", "data_gap"),
        ("LX0609-026", "matched", "data_gap"),
        ("LX0609-026", "mismatched", "compliant"),
        ("LX0609-026", "unknown", "non_compliant"),
        ("LX0609-027", "not_met", "compliant"),
        ("LX0609-027", "not_met", "uncertain"),
    ],
)
def test_tumor_pathology_finalizer_fail_closes_status_fact_conflicts(
    rule_id: str, state: str, incorrect_status: str
) -> None:
    raw_facts = _facts(rule_id=rule_id, state=state)
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": rule_id,
            "status": incorrect_status,
            "reason_code": "untrusted_reason",
            "customer_display_facts": raw_facts,
            "customer_evidence": [{"source_document_id": "must-clear"}],
        },
        raw_facts=raw_facts,
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized


def test_tumor_pathology_finalizer_rejects_invalid_facts_even_for_technical_error() -> (
    None
):
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-013",
            "status": "technical_error",
            "reason_code": "native_failure",
            "customer_display_facts": {"forged": True},
        },
        raw_facts={"forged": True},
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "native_failure"
    assert "customer_display_facts" not in finalized
