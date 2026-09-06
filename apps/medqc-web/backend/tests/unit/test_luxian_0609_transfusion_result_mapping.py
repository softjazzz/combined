from __future__ import annotations

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalizer_owns_executor_customer_display_facts,
)
from app.services.luxian_0609.transfusion_result_mapping import (
    is_transfusion_customer_rule,
    safe_transfusion_customer_display_facts,
)
from app.services.luxian_0609.native_transfusion_execution import (
    _customer_display_facts_for_outcome,
)


def test_transfusion_mapping_strips_internal_document_references() -> None:
    raw = {
        "verification_kind": "posttransfusion_evaluation_complete",
        "performed_transfusion_confirmed": True,
        "threshold_hours": 24,
        "checked_sources": ["bloodtrans_record", "daily_course_record"],
        "source_document_refs": [
            {"source_type": "bloodtrans_record", "source_document_id": "BLOOD-1"}
        ],
        "transfusion_end_time": "2026-09-06 10:00:00",
        "evaluation_time": "2026-09-06 11:00:00",
        "elapsed_hours": 1.0,
    }

    assert safe_transfusion_customer_display_facts(
        rule_id="LX0609-047", raw=raw
    ) == {
        "verification_kind": "posttransfusion_evaluation_complete",
        "performed_transfusion_confirmed": True,
        "threshold_hours": 24,
        "checked_sources": ["bloodtrans_record", "daily_course_record"],
        "transfusion_end_time": "2026-09-06 10:00:00",
        "evaluation_time": "2026-09-06 11:00:00",
        "elapsed_hours": 1.0,
    }


def test_transfusion_mapping_rejects_invalid_system_gap_contract() -> None:
    assert safe_transfusion_customer_display_facts(
        rule_id="LX0609-041",
        raw={
            "failure_kind": "system_data_contract_gap",
            "system_gap_reason": "wrong_reason",
            "gap_owner": "system_integration",
            "conclusion": "资料未接入",
            "handling_suggestion": "补齐资料",
        },
    ) is None


def test_transfusion_fact_status_conflict_is_isolated_technical_error() -> None:
    result, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-044",
            "status": "compliant",
            "reason_code": "requirement_satisfied",
            "findings": "must be removed",
        },
        raw_facts={
            "failure_kind": "pretransfusion_assessment_missing",
            "performed_transfusion_confirmed": True,
            "checked_fields": [
                "indication",
                "laboratory_indicator",
                "risk_history_or_status",
            ],
            "missing_fields": ["indication"],
        },
    )

    assert handled is True
    assert result["status"] == "technical_error"
    assert result["reason_code"] == "model_invalid_output"
    assert "findings" not in result
    assert "customer_display_facts" not in result


def test_transfusion_contract_owner_includes_migrated_041_to_048_only() -> None:
    assert all(
        is_transfusion_customer_rule(f"LX0609-{number:03d}")
        and finalizer_owns_executor_customer_display_facts(
            f"LX0609-{number:03d}"
        )
        for number in range(41, 49)
    )
    assert not is_transfusion_customer_rule("LX0609-049")
    assert not finalizer_owns_executor_customer_display_facts("LX0609-049")


def test_049_conservative_typed_data_gap_is_not_reclassified_by_transfusion_finalizer() -> None:
    """049 仍走保守缺口合同，不能被 041–048 的 facts 迁移误接管。"""

    raw_facts = _customer_display_facts_for_outcome(
        rule_id="LX0609-049",
        status="data_gap",
        reason_code="billing_linkage_source_unavailable",
    )

    assert raw_facts is not None
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-049",
            "status": "data_gap",
            "reason_code": "billing_linkage_source_unavailable",
        },
        raw_facts=raw_facts,
    )

    assert handled is False
    assert finalized["status"] == "data_gap"
    assert finalized["reason_code"] == "billing_linkage_source_unavailable"
