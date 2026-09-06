from __future__ import annotations

from pathlib import Path

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalizer_owns_executor_customer_display_facts,
    finalizer_requires_public_fact_ref_evidence,
)
from app.services.luxian_0609.transfusion_result_mapping import (
    is_transfusion_customer_rule,
    is_transfusion_public_fact_ref_evidence_rule,
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


def test_transfusion_contract_owner_includes_migrated_041_to_048_and_070() -> None:
    assert all(
        is_transfusion_customer_rule(f"LX0609-{number:03d}")
        and finalizer_owns_executor_customer_display_facts(
            f"LX0609-{number:03d}"
        )
        for number in range(41, 49)
    )
    assert is_transfusion_customer_rule("LX0609-070")
    assert finalizer_owns_executor_customer_display_facts("LX0609-070")
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


def _070_complete_facts() -> dict[str, object]:
    return {
        "verification_kind": "pretransfusion_items_complete",
        "performed_transfusion_confirmed": True,
        "checked_items": [
            "hbsag", "hbsab", "hbeag", "hbeab", "hbcab",
            "hcv", "hiv", "syphilis", "alt",
        ],
        "latest_test_time": "2026-06-02 10:00:00",
        "transfusion_time": "2026-06-04 14:00:00",
        "abo_present": False,
        "rh_present": False,
        "antibody_screen_present": False,
        "transfusion_event_count": 2,
        "checked_transfusion_times": [
            "2026-06-02 14:00:00", "2026-06-04 14:00:00",
        ],
        "event_checks": [
            {
                "transfusion_time": "2026-06-02 14:00:00",
                "latest_valid_test_time": "2026-06-02 10:00:00",
                "missing_items": [],
                "missing_time_items": [],
                "late_items": [],
                "outside_current_stay_items": [],
                "source_document_id": "PRIVATE-070-DOCUMENT",
            },
            {
                "transfusion_time": "2026-06-04 14:00:00",
                "latest_valid_test_time": "2026-06-02 10:00:00",
                "missing_items": [],
                "missing_time_items": [],
                "late_items": [],
                "outside_current_stay_items": [],
            },
        ],
        "admission_time": "2026-06-01 08:00:00",
        "raw_lab_rows": "PRIVATE-070-RAW",
    }


def test_070_mapping_freezes_event_checks_and_strips_private_material() -> None:
    safe = safe_transfusion_customer_display_facts(
        rule_id="LX0609-070", raw=_070_complete_facts()
    )

    assert safe == {
        "verification_kind": "pretransfusion_items_complete",
        "performed_transfusion_confirmed": True,
        "checked_items": [
            "hbsag", "hbsab", "hbeag", "hbeab", "hbcab",
            "hcv", "hiv", "syphilis", "alt",
        ],
        "latest_test_time": "2026-06-02 10:00:00",
        "transfusion_time": "2026-06-04 14:00:00",
        "abo_present": False,
        "rh_present": False,
        "antibody_screen_present": False,
        "transfusion_event_count": 2,
        "checked_transfusion_times": [
            "2026-06-02 14:00:00", "2026-06-04 14:00:00",
        ],
        "event_checks": [
            {
                "transfusion_time": "2026-06-02 14:00:00",
                "latest_valid_test_time": "2026-06-02 10:00:00",
                "missing_items": [],
                "missing_time_items": [],
                "late_items": [],
                "outside_current_stay_items": [],
            },
            {
                "transfusion_time": "2026-06-04 14:00:00",
                "latest_valid_test_time": "2026-06-02 10:00:00",
                "missing_items": [],
                "missing_time_items": [],
                "late_items": [],
                "outside_current_stay_items": [],
            },
        ],
        "admission_time": "2026-06-01 08:00:00",
    }
    assert "PRIVATE-070" not in repr(safe)


def test_070_status_conflict_and_partial_event_facts_downgrade_to_technical_error() -> None:
    result, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-070",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "findings": "must be removed",
            "customer_evidence": [{"source_type": "must-be-cleared"}],
        },
        raw_facts=_070_complete_facts(),
    )

    assert handled is True
    assert (result["status"], result["reason_code"]) == (
        "technical_error",
        "model_invalid_output",
    )
    assert "customer_display_facts" not in result
    assert "customer_evidence" not in result
    assert "findings" not in result


def test_070_missing_facts_preserves_existing_gap_or_not_applicable_status() -> None:
    for status in ("data_gap", "not_applicable"):
        result, handled = finalize_luxian_0609_executor_customer_display_facts(
            result={"rule_id": "LX0609-070", "status": status, "reason_code": "native"},
            raw_facts=None,
        )

        assert handled is True
        assert result["status"] == status
        assert "customer_display_facts" not in result


def test_070_alone_requires_public_fact_ref_evidence() -> None:
    assert is_transfusion_public_fact_ref_evidence_rule("LX0609-070")
    assert finalizer_requires_public_fact_ref_evidence("LX0609-070")
    assert not any(
        finalizer_requires_public_fact_ref_evidence(f"LX0609-{number:03d}")
        for number in range(41, 49)
    )


def test_aggregator_has_no_070_reference() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    ).read_text(encoding="utf-8")

    assert "LX0609-070" not in source
