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
    transfusion_customer_fact_status_is_valid,
)
from app.services.luxian_0609.native_transfusion_execution import (
    TRANSFUSION_RULE_IDS,
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
        rule_id="LX0609-07-03-01", raw=raw
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
        rule_id="LX0609-11-03-01",
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
            "rule_id": "LX0609-07-01-02",
            "status": "compliant",
            "reason_code": "requirement_satisfied",
            "findings": "must be removed",
        },
        raw_facts={
            "failure_kind": "pretransfusion_assessment_missing",
            "transfusion_order_present": True,
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


def test_044_mapping_keeps_legacy_saved_fact_shape_readable() -> None:
    """历史已保存的 044 三字段事实仍可经过公共安全映射读取。"""

    assert safe_transfusion_customer_display_facts(
        rule_id="LX0609-07-01-02",
        raw={
            "verification_kind": "pretransfusion_assessment_complete",
            "transfusion_order_present": True,
            "checked_fields": [
                "indication",
                "laboratory_indicator",
                "risk_history_or_status",
            ],
            "missing_fields": [],
        },
    ) == {
        "verification_kind": "pretransfusion_assessment_complete",
        "transfusion_order_present": True,
        "checked_fields": [
            "indication",
            "laboratory_indicator",
            "risk_history_or_status",
        ],
        "missing_fields": [],
    }


def test_transfusion_contract_owner_includes_migrated_041_to_048_and_070() -> None:
    assert all(
        is_transfusion_customer_rule(rule_id)
        and finalizer_owns_executor_customer_display_facts(
            rule_id
        )
        for rule_id in TRANSFUSION_RULE_IDS[:-1]
    )
    assert is_transfusion_customer_rule("LX0609-07-01-03")
    assert finalizer_owns_executor_customer_display_facts("LX0609-07-01-03")
    assert not is_transfusion_customer_rule("LX0609-07-04-02")
    assert not finalizer_owns_executor_customer_display_facts("LX0609-07-04-02")


def test_049_conservative_typed_data_gap_is_not_reclassified_by_transfusion_finalizer() -> None:
    """049 仍走保守缺口合同，不能被 041–048 的 facts 迁移误接管。"""

    raw_facts = _customer_display_facts_for_outcome(
        rule_id="LX0609-07-04-02",
        status="data_gap",
        reason_code="billing_linkage_source_unavailable",
    )

    assert raw_facts is not None
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-07-04-02",
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
        rule_id="LX0609-07-01-03", raw=_070_complete_facts()
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
            "rule_id": "LX0609-07-01-03",
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
            result={"rule_id": "LX0609-07-01-03", "status": status, "reason_code": "native"},
            raw_facts=None,
        )

        assert handled is True
        assert result["status"] == status
        assert "customer_display_facts" not in result


def test_070_alone_requires_public_fact_ref_evidence() -> None:
    assert is_transfusion_public_fact_ref_evidence_rule("LX0609-07-01-03")
    assert finalizer_requires_public_fact_ref_evidence("LX0609-07-01-03")
    assert not any(
        finalizer_requires_public_fact_ref_evidence(rule_id)
        for rule_id in TRANSFUSION_RULE_IDS[:-1]
    )


def test_aggregator_has_no_070_reference() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    ).read_text(encoding="utf-8")

    assert "LX0609-07-01-03" not in source


def test_044_to_046_mapping_requires_order_facts_and_strips_performed_claim() -> None:
    """已开医嘱是触发事实，不能将其公开为已实际实施输血。"""

    cases = [
        ("LX0609-07-01-02", {
            "verification_kind": "pretransfusion_assessment_complete",
            "checked_fields": ["application_reason", "laboratory_indicator"],
            "missing_fields": [],
        }),
        ("LX0609-07-01-02", {
            "failure_kind": "pretransfusion_assessment_missing",
            "checked_fields": ["application_reason", "laboratory_indicator"],
            "missing_fields": ["application_reason", "laboratory_indicator"],
        }),
        ("LX0609-07-02-01", {
            "verification_kind": "transfusion_course_record_present",
            "checked_sources": ["bloodtrans_record", "daily_course_record"],
            "record_count": 1,
        }),
        ("LX0609-07-02-01", {
            "failure_kind": "transfusion_course_record_missing",
            "checked_sources": ["bloodtrans_record", "daily_course_record"],
            "record_count": 0,
        }),
        ("LX0609-07-02-02", {
            "verification_kind": "transfusion_course_record_complete",
            "checked_fields": ["reason_or_indication", "dose"],
            "missing_fields": [],
            "record_count": 1,
            "incomplete_record_count": 0,
            "missing_field_record_counts": {},
        }),
        ("LX0609-07-02-02", {
            "failure_kind": "transfusion_course_record_incomplete",
            "checked_fields": ["reason_or_indication", "dose"],
            "missing_fields": ["dose"],
            "record_count": 1,
            "incomplete_record_count": 1,
            "missing_field_record_counts": {"dose": 1},
        }),
    ]
    for rule_id, facts in cases:
        expected = {**facts, "transfusion_order_present": True}
        assert safe_transfusion_customer_display_facts(
            rule_id=rule_id,
            raw={**expected, "performed_transfusion_confirmed": True},
        ) == expected
        assert safe_transfusion_customer_display_facts(
            rule_id=rule_id, raw=expected,
        ) == expected
        for order_present in (None, False, 1, "true"):
            legacy = {**facts, "performed_transfusion_confirmed": True}
            if order_present is not None:
                legacy["transfusion_order_present"] = order_present
            assert safe_transfusion_customer_display_facts(
                rule_id=rule_id, raw=legacy,
            ) is None


def test_046_clinical_field_facts_require_matching_terminal_status() -> None:
    """资料不足不能公开为临床字段缺失，合规与缺项事实必须匹配终态。"""

    for kind, expected_status in (
        ("transfusion_course_record_complete", "compliant"),
        ("transfusion_course_record_incomplete", "non_compliant"),
        ("transfusion_requirement_not_documented", "non_compliant"),
    ):
        for status in ("compliant", "non_compliant", "data_gap", "technical_error", "not_applicable"):
            assert transfusion_customer_fact_status_is_valid(
                rule_id="LX0609-07-02-02",
                status=status,
                safe_facts={"verification_kind" if expected_status == "compliant" else "failure_kind": kind},
            ) is (status == expected_status)


def test_046_system_gaps_are_safe_without_clinical_missing_fields() -> None:
    for reason in ("transfusion_course_source_unavailable", "transfusion_course_record_content_unavailable"):
        expected = {
            "failure_kind": "system_data_contract_gap",
            "system_gap_reason": reason,
            "gap_owner": "system_integration",
        }
        raw = {
            **expected,
            "conclusion": "输血病程资料不足，暂无法核对字段。",
            "handling_suggestion": "补齐输血病程资料。",
            "transfusion_order_present": True,
        }
        assert safe_transfusion_customer_display_facts(rule_id="LX0609-07-02-02", raw=raw) == expected
        assert safe_transfusion_customer_display_facts(rule_id="LX0609-07-02-02", raw=expected) == expected
        assert safe_transfusion_customer_display_facts(
            rule_id="LX0609-07-02-02", raw={**raw, "system_gap_reason": "unapproved_reason"},
        ) is None
        result, handled = finalize_luxian_0609_executor_customer_display_facts(
            result={"rule_id": "LX0609-07-02-02", "status": "data_gap", "reason_code": reason},
            raw_facts=raw,
        )
        assert handled is True
        assert result["status"] == "data_gap"
        assert result["customer_display_facts"] == expected


def test_order_trigger_rules_preserve_controlled_no_fact_terminal_states() -> None:
    for rule_id in ("LX0609-07-01-02", "LX0609-07-02-01", "LX0609-07-02-02"):
        for status, reason in (
            ("not_applicable", "transfusion_order_absent"),
            ("data_gap", "transfusion_source_unavailable"),
            ("data_gap", "transfusion_projection_unavailable"),
            ("data_gap", "transfusion_rule_projection_incomplete"),
        ):
            result, handled = finalize_luxian_0609_executor_customer_display_facts(
                result={"rule_id": rule_id, "status": status, "reason_code": reason},
                raw_facts=None,
            )
            assert handled is True
            assert (result["status"], result["reason_code"]) == (status, reason)
            assert "customer_display_facts" not in result
        result, _ = finalize_luxian_0609_executor_customer_display_facts(
            result={"rule_id": rule_id, "status": "compliant", "reason_code": "requirement_satisfied"},
            raw_facts=None,
        )
        assert result["status"] == "technical_error"

    result, _ = finalize_luxian_0609_executor_customer_display_facts(
        result={"rule_id": "LX0609-07-03-01", "status": "not_applicable", "reason_code": "transfusion_order_absent"},
        raw_facts=None,
    )
    assert result["status"] == "technical_error"
