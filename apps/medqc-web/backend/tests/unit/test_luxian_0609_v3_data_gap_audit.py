from __future__ import annotations

from scripts.audit_luxian_0609_v3_data_gaps import classify_gap


def test_classify_gap_rejects_delivery_projection_difference() -> None:
    cause, layer, confidence, _evidence = classify_gap(
        reason_code="required_field_missing",
        observations={},
        material_summary={},
        workspace_envelope_match=False,
    )

    assert (cause, layer, confidence) == (
        "technical_error_misclassified",
        "workspace_to_envelope",
        "confirmed",
    )


def test_classify_gap_keeps_required_field_missing_unresolved_without_decision() -> None:
    cause, layer, confidence, _evidence = classify_gap(
        reason_code="required_field_missing",
        observations={"daily_course_record": {"query_state": "available"}},
        material_summary={"daily_course_record": {"present": True, "row_count": 2}},
        workspace_envelope_match=True,
    )

    assert (cause, layer, confidence) == (
        "other_with_evidence",
        "native_result_projection",
        "unresolved",
    )


def test_classify_gap_identifies_snapshot_unavailable_before_native_reason() -> None:
    cause, layer, confidence, _evidence = classify_gap(
        reason_code="linkage_unresolved",
        observations={"consultation_record": {"query_state": "unavailable"}},
        material_summary={"consultation_record": {"present": False}},
        workspace_envelope_match=True,
    )

    assert (cause, layer, confidence) == (
        "source_sync_missing",
        "evidence_snapshot",
        "confirmed",
    )


def test_classify_gap_does_not_call_unregistered_reader_a_sync_failure() -> None:
    cause, layer, confidence, _evidence = classify_gap(
        reason_code="source_unavailable",
        observations={
            "surgery_risk_assessment": {
                "query_state": "unavailable",
                "reason_code": "SOURCE_READER_NOT_REGISTERED",
            }
        },
        material_summary={"surgery_risk_assessment": {"present": False}},
        workspace_envelope_match=True,
    )

    assert (cause, layer, confidence) == (
        "other_with_evidence",
        "source_registry",
        "confirmed",
    )
