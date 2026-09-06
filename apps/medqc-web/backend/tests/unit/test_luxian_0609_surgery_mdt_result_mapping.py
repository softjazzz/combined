from __future__ import annotations

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.surgery_mdt_result_mapping import (
    legacy_surgery_mdt_customer_evidence,
    safe_surgery_mdt_customer_display_facts,
)


_MISSING_FACTS = {
    "performed_surgery_confirmed": True,
    "procedure_kind": "surgery",
    "effective_surgery_level": "四级",
    "surgery_level_source": "structured_field",
    "mdt_discussion_state": "missing",
}


def test_mdt_facts_remove_internal_ids_and_preserve_the_public_contract() -> None:
    raw = {
        **_MISSING_FACTS,
        "source_document_refs": [
            {"source_type": "mr_surgery", "source_document_id": "SURGERY-040"}
        ],
        "source_document_id": "SURGERY-040",
    }

    assert safe_surgery_mdt_customer_display_facts(
        rule_id="LX0609-040", raw=raw
    ) == _MISSING_FACTS


def test_mdt_legacy_direct_evidence_only_accepts_explicit_surgery_trigger() -> None:
    raw = {
        **_MISSING_FACTS,
        "source_document_refs": [
            {"source_type": "mr_surgery", "source_document_id": "SURGERY-040"}
        ],
    }
    assert legacy_surgery_mdt_customer_evidence(
        rule_id="LX0609-040", raw=raw, safe_facts=_MISSING_FACTS
    ) == [{"source_type": "mr_surgery", "source_document_id": "SURGERY-040"}]

    raw["source_document_refs"] = [
        {"source_type": "presurg_discussion", "source_document_id": "DISCUSSION-040"}
    ]
    assert legacy_surgery_mdt_customer_evidence(
        rule_id="LX0609-040", raw=raw, safe_facts=_MISSING_FACTS
    ) == []


def test_mdt_status_and_safe_facts_conflict_becomes_technical_error() -> None:
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-040",
            "status": "compliant",
            "reason_code": "requirement_satisfied",
            "findings": "不应保留",
        },
        raw_facts=_MISSING_FACTS,
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert "findings" not in finalized
