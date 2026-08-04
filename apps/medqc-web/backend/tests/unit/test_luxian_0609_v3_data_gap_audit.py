from __future__ import annotations

from scripts.audit_luxian_0609_v3_data_gaps import (
    _compare_delivery,
    _evidence_delivery_trace,
    _material_summary,
    _serialize_observations,
    classify_gap,
)


def test_classify_gap_rejects_delivery_projection_difference() -> None:
    cause, layer, confidence, _evidence = classify_gap(
        reason_code="required_field_missing",
        observations={},
        material_summary={},
        required_source_keys=(),
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
        required_source_keys=("daily_course_record",),
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
        required_source_keys=("consultation_record",),
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
        required_source_keys=("surgery_risk_assessment",),
        workspace_envelope_match=True,
    )

    assert (cause, layer, confidence) == (
        "other_with_evidence",
        "source_registry",
        "confirmed",
    )


def test_classify_gap_ignores_empty_horizon_when_rule_does_not_require_it() -> None:
    cause, layer, confidence, _evidence = classify_gap(
        reason_code="linkage_unresolved",
        observations={
            "consultation_record": {"query_state": "available"},
            "evaluation_context.horizon": {"query_state": "empty"},
        },
        material_summary={"consultation_record": {"present": True, "row_count": 1}},
        required_source_keys=("consultation_record",),
        workspace_envelope_match=True,
    )

    assert (cause, layer, confidence) == (
        "event_linkage_failed",
        "native_result_projection",
        "indicated",
    )


def test_serialized_observations_only_include_rule_required_sources() -> None:
    class _Observation:
        def __init__(self, source_key: str, query_state: str) -> None:
            self.source_key = source_key
            self._query_state = query_state

        def to_dict(self) -> dict[str, str]:
            return {"source_key": self.source_key, "query_state": self._query_state}

    class _Snapshot:
        observations = (
            _Observation("consultation_record", "available"),
            _Observation("evaluation_context.horizon", "empty"),
        )

    class _Session:
        snapshot = _Snapshot()

    assert _serialize_observations(_Session(), ("consultation_record",)) == {
        "consultation_record": {
            "source_key": "consultation_record",
            "query_state": "available",
        }
    }


def test_classify_gap_checks_reader_capability_before_native_time_reason() -> None:
    cause, layer, confidence, _evidence = classify_gap(
        reason_code="authoritative_time_missing",
        observations={
            "surgery_risk_assessment": {
                "query_state": "unavailable",
                "reason_code": "SOURCE_READER_NOT_REGISTERED",
            }
        },
        material_summary={"surgery_risk_assessment": {"present": False}},
        required_source_keys=("surgery_risk_assessment",),
        workspace_envelope_match=True,
    )

    assert (cause, layer, confidence) == (
        "other_with_evidence",
        "source_registry",
        "confirmed",
    )


def test_classify_gap_does_not_call_currently_readable_sources_absent() -> None:
    cause, layer, confidence, _evidence = classify_gap(
        reason_code="source_unavailable",
        observations={
            "daily_course_record": {"query_state": "available"},
            "surgery_record": {"query_state": "available"},
            "mr_surgery": {"query_state": "available"},
            "pathology_exam_master": {"query_state": "available"},
            "pathology_exam_report": {"query_state": "available"},
        },
        material_summary={
            "daily_course_record": {"present": True, "row_count": 1},
            "surgery_record": {"present": True, "row_count": 1},
            "mr_surgery": {"present": True, "row_count": 1},
            "pathology_exam_master": {"present": True, "row_count": 1},
            "pathology_exam_report": {"present": True, "row_count": 1},
        },
        required_source_keys=(
            "daily_course_record",
            "surgery_record",
            "mr_surgery",
            "pathology_exam_master",
            "pathology_exam_report",
        ),
        workspace_envelope_match=True,
    )

    assert (cause, layer, confidence) == (
        "other_with_evidence",
        "native_result_projection",
        "unresolved",
    )


def test_evidence_trace_marks_unlocatable_canonical_items_without_claiming_delivery_loss() -> None:
    trace = _evidence_delivery_trace(
        {
            "evidence_items": [
                {"source_document_id": "", "quote": "未定位"},
                {"document_ref": "", "quote": "仍未定位"},
            ]
        },
        {"evidence": []},
    )

    assert trace == {
        "state": "canonical_evidence_unlocatable",
        "canonical_evidence_item_count": 2,
        "canonical_locatable_ref_count": 0,
        "envelope_evidence_count": 0,
        "envelope_source_refs": [],
    }


def test_delivery_comparison_includes_suggestion() -> None:
    matched, differences = _compare_delivery(
        {
            "status": "data_gap",
            "reason_code": "required_field_missing",
            "source_conclusion": "暂无法完成",
            "suggestion": "补资料",
            "data_gap_details": {},
        },
        {
            "status": "data_gap",
            "reason_code": "required_field_missing",
            "conclusion": "暂无法完成",
            "suggestion": "不同建议",
            "data_gap_details": {},
        },
    )

    assert not matched
    assert differences == ["suggestion"]


def test_material_summary_does_not_expect_rows_for_derived_source() -> None:
    class _Materials:
        def has_source(self, _key: str) -> bool:
            raise AssertionError("derived source must not be read from MaterialStore")

    class _Session:
        materials = _Materials()

    assert _material_summary(_Session(), ("inpat_nondrug_order.unstable_order",)) == {
        "inpat_nondrug_order.unstable_order": {
            "present": None,
            "runtime_derived": True,
        }
    }
