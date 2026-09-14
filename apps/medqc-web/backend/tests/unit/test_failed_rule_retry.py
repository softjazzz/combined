from __future__ import annotations

import pytest

from app.services.case_identity import CaseRef
from app.services.qc_workspace.failed_rule_retry import (
    build_failed_rule_retry_scope,
    merge_failed_rule_retry_results,
)


def _row(rule_id: str, *, status: str | None = None) -> dict:
    row = {
        "institute_id": "hospital-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "record_key": CaseRef("hospital-1", "patient-1", "visit-1").as_key(),
        "rule_id": rule_id,
    }
    if status:
        row["status"] = status
    return row


def test_scope_uses_only_failed_record_rule_pairs() -> None:
    job = {
        "status": "failed",
        "job_kind": "leaf",
        "summary": {"execution_status": "partial_failed"},
        "items": [_row("LX0609-011", status="compliant")],
        "failed_records": [
            _row("LX0609-012"),
            {
                "visit_id": "visit-2",
                "rule_id": "LX0609-040",
            },
        ],
        "filters": {
            "rule_ids": ["LX0609-011", "LX0609-012", "LX0609-040"],
            "record_refs": [
                {
                    "institute_id": "hospital-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                },
                {
                    "institute_id": "hospital-1",
                    "patient_id": "patient-2",
                    "visit_id": "visit-2",
                },
            ],
        },
    }

    result = build_failed_rule_retry_scope(job)

    assert result is not None
    scope, normalized_failures = result
    assert scope["rule_ids"] == ["LX0609-012", "LX0609-040"]
    assert scope["pending_count"] == 2
    assert scope["record_rule_map"] == {
        '["hospital-1","patient-1","visit-1"]': ["LX0609-012"],
        '["hospital-1","patient-2","visit-2"]': ["LX0609-040"],
    }
    assert normalized_failures[1]["patient_id"] == "patient-2"


def test_scope_rejects_ambiguous_legacy_visit_identity() -> None:
    job = {
        "status": "failed",
        "summary": {"execution_status": "partial_failed"},
        "items": [_row("LX0609-011", status="compliant")],
        "failed_records": [{"visit_id": "visit-1", "rule_id": "LX0609-012"}],
        "filters": {
            "record_refs": [
                {"institute_id": "hospital-1", "patient_id": "patient-1", "visit_id": "visit-1"},
                {"institute_id": "hospital-2", "patient_id": "patient-2", "visit_id": "visit-1"},
            ]
        },
    }

    with pytest.raises(ValueError, match="无法唯一定位"):
        build_failed_rule_retry_scope(job)


def test_merge_replaces_only_pending_failure_and_preserves_valid_result() -> None:
    valid = _row("LX0609-011", status="compliant")
    pending = _row("LX0609-012")
    recovered = _row("LX0609-012", status="non_compliant")

    items, failures = merge_failed_rule_retry_results(
        base_items=[valid],
        base_failures=[pending],
        retry_items=[recovered],
        retry_failures=[],
    )

    assert items == [valid, recovered]
    assert failures == []


def test_merge_rejects_out_of_scope_result() -> None:
    with pytest.raises(ValueError, match="范围外"):
        merge_failed_rule_retry_results(
            base_items=[_row("LX0609-011", status="compliant")],
            base_failures=[_row("LX0609-012")],
            retry_items=[_row("LX0609-040", status="compliant")],
            retry_failures=[],
        )


def test_merge_keeps_valid_results_when_retry_still_fails() -> None:
    valid = _row("LX0609-011", status="compliant")
    pending = {**_row("LX0609-012"), "reason_code": "model_invalid_output"}
    retry_failure = {**_row("LX0609-012"), "reason_code": "semantic_output_unknown"}

    items, failures = merge_failed_rule_retry_results(
        base_items=[valid],
        base_failures=[pending],
        retry_items=[],
        retry_failures=[retry_failure],
    )

    assert items == [valid]
    assert failures == [retry_failure]
