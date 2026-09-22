from __future__ import annotations

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.surgery_document_result_mapping import (
    is_surgery_document_public_fact_ref_evidence_rule,
    safe_surgery_document_customer_display_facts,
    surgery_document_customer_fact_status_is_valid,
)


def test_039_customer_facts_exclude_surgeon_identity() -> None:
    safe_facts = safe_surgery_document_customer_display_facts(
        rule_id="LX0609-04-01-02",
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


def test_public_fact_ref_evidence_declaration_is_limited_to_frozen_rules() -> None:
    assert all(
        is_surgery_document_public_fact_ref_evidence_rule(rule_id)
        for rule_id in ("LX0609-11-02-01", "LX0609-04-04-01", "LX0609-04-01-02")
    )
    assert all(
        not is_surgery_document_public_fact_ref_evidence_rule(rule_id)
        for rule_id in ("LX0609-04-01-01", "LX0609-11-02-02", "LX0609-04-04-02", "LX0609-04-04-03")
    )


def test_status_fact_contract_failure_is_isolated_as_technical_error() -> None:
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-04-04-03",
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


def test_037_missing_anesthesia_visit_is_a_deliverable_defect() -> None:
    raw_facts = {
        "failure_kind": "anesthesia_visit_missing",
        "performed_anesthesia_confirmed": True,
        "missing_visit_sources": ["postane_surveil_record"],
    }
    safe_facts = safe_surgery_document_customer_display_facts(
        rule_id="LX0609-04-04-02", raw=raw_facts
    )

    assert surgery_document_customer_fact_status_is_valid(
        rule_id="LX0609-04-04-02",
        status="non_compliant",
        safe_facts=safe_facts,
    )
    assert not surgery_document_customer_fact_status_is_valid(
        rule_id="LX0609-04-04-02",
        status="not_applicable",
        safe_facts=safe_facts,
    )

    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-04-04-02",
            "status": "non_compliant",
            "reason_code": "required_document_missing",
        },
        raw_facts=raw_facts,
    )

    assert handled is True
    assert finalized["status"] == "non_compliant"
    assert finalized["reason_code"] == "required_document_missing"


def test_preop_ambiguous_association_keeps_only_safe_event_coordinates() -> None:
    raw_facts = {
        "verification_kind": "preop_surgery_association_ambiguous",
        "target_document": "presurg_summary",
        "checked_fields": [
            "brief_condition",
            "preop_diagnosis",
            "surgical_indication",
            "planned_procedure",
            "planned_anesthesia",
            "precautions",
            "surgeon_preop_visit",
        ],
        "missing_fields": [],
        "documents": [
            {
                "document_index": 1,
                "event_index": None,
                "association_state": "ambiguous",
                "missing_fields": [],
                "document_id": "must-not-project",
            }
        ],
    }
    assert (
        safe_surgery_document_customer_display_facts(
            rule_id="LX0609-04-01-04", raw=raw_facts
        )
        is None
    )

    raw_facts["documents"][0].pop("document_id")
    safe_facts = safe_surgery_document_customer_display_facts(
        rule_id="LX0609-04-01-04", raw=raw_facts
    )
    assert safe_facts == raw_facts
    assert surgery_document_customer_fact_status_is_valid(
        rule_id="LX0609-04-01-04", status="data_gap", safe_facts=safe_facts
    )
