from __future__ import annotations

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.surgery_document_result_mapping import (
    legacy_surgery_document_customer_evidence,
    safe_surgery_document_customer_display_facts,
)


def test_039_customer_facts_exclude_surgeon_identity() -> None:
    safe_facts = safe_surgery_document_customer_display_facts(
        rule_id="LX0609-039",
        raw={
            "failure_kind": "surgeon_not_in_preop_discussion",
            "performed_surgery_confirmed": True,
            "emergency_rescue_exception_absent": True,
            "discussion_state": "present",
            "surgeon_participation_state": "absent",
            "surgeons": ["医务人员A"],
            "discussion_participants": ["医务人员B"],
        },
    )

    assert safe_facts == {
        "failure_kind": "surgeon_not_in_preop_discussion",
        "performed_surgery_confirmed": True,
        "emergency_rescue_exception_absent": True,
        "discussion_state": "present",
        "surgeon_participation_state": "absent",
    }


def test_legacy_direct_evidence_is_strictly_bounded_by_rule_contract() -> None:
    raw = {
        "source_document_id": "document-1",
        "source_document_type": "surgery_record",
    }

    assert legacy_surgery_document_customer_evidence(
        rule_id="LX0609-034", raw=raw, safe_facts={}
    ) == [{"source_type": "anesthesia_record", "source_document_id": "document-1"}]
    assert legacy_surgery_document_customer_evidence(
        rule_id="LX0609-036", raw=raw, safe_facts={}
    ) == [{"source_type": "anesthesia_record", "source_document_id": "document-1"}]
    assert legacy_surgery_document_customer_evidence(
        rule_id="LX0609-039", raw=raw, safe_facts={}
    ) == [{"source_type": "surgery_record", "source_document_id": "document-1"}]
    for rule_id in ("LX0609-029", "LX0609-035", "LX0609-037", "LX0609-038"):
        assert legacy_surgery_document_customer_evidence(
            rule_id=rule_id, raw=raw, safe_facts={}
        ) == []


def test_status_fact_contract_failure_is_isolated_as_technical_error() -> None:
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-038",
            "status": "compliant",
            "reason_code": "requirement_satisfied",
            "findings": ["不应保留"],
        },
        raw_facts={
            "failure_kind": "anesthesia_record_missing",
            "performed_anesthesia_confirmed": True,
            "checked_sources": ["anesthesia_record"],
        },
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert "findings" not in finalized
