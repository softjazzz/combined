from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.luxian_0609_result_schema import CANONICAL_RESULT_STATUSES


def _finalize(result: dict):
    from app.services.luxian_0609.canonical_result_finalizer import (
        finalize_luxian_0609_canonical_result,
    )

    return finalize_luxian_0609_canonical_result(result)


@pytest.mark.parametrize(
    ("extra", "expected_status"),
    [
        ({}, "uncertain"),
        ({"customer_display_facts": {"failure_kind": "document_missing"}}, "non_compliant"),
        ({"criterion_results": [{"criterion_id": "presence", "status": "failed"}]}, "non_compliant"),
        (
            {
                "evidence_items": [
                    {
                        "quote": "未见术前小结",
                        "source_document_id": "document-1",
                    }
                ]
            },
            "non_compliant",
        ),
    ],
)
def test_finalizer_owns_customer_explanation_safety_policy(
    extra: dict,
    expected_status: str,
):
    result = _finalize(
        {
            "rule_id": "LX0609-029",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "reason_code": "requirement_violated",
            "is_compliant": False,
            **extra,
        }
    )

    assert result["status"] == expected_status
    assert result["result_status"] == expected_status
    assert result["is_compliant"] is (False if expected_status == "non_compliant" else None)
    assert result["reason_code"] == (
        "requirement_violated"
        if expected_status == "non_compliant"
        else "customer_explanation_incomplete"
    )


@pytest.mark.parametrize("status", CANONICAL_RESULT_STATUSES)
def test_finalizer_accepts_every_canonical_status_and_preserves_non_defect_reason(
    status: str,
):
    result = _finalize(
        {
            "rule_id": "LX0609-001",
            "status": status,
            "result_status": "stale-value",
            "reason_code": "original_reason",
            "is_compliant": "stale-value",
            "customer_display_facts": (
                {"failure_kind": "late"} if status == "non_compliant" else {}
            ),
        }
    )

    assert result["status"] == status
    assert result["result_status"] == status
    assert result["reason_code"] == "original_reason"
    assert result["is_compliant"] is (
        True
        if status in {"compliant", "not_applicable"}
        else False
        if status == "non_compliant"
        else None
    )


def test_finalizer_rejects_missing_identity_and_unknown_status():
    with pytest.raises(ValueError, match="rule_id"):
        _finalize({"status": "compliant"})

    with pytest.raises(ValueError, match="status"):
        _finalize({"rule_id": "LX0609-001", "status": "future_status"})


def test_location_without_excerpt_is_not_sufficient_customer_explanation():
    result = _finalize(
        {
            "rule_id": "LX0609-029",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
            "customer_evidence": [
                {"source_document_id": "document-1", "source_type": "preoperative_summary"}
            ],
            "evidence_items": [{"source_document_id": "document-1", "quote": ""}],
        }
    )

    assert result["status"] == "uncertain"
    assert result["reason_code"] == "customer_explanation_incomplete"


def test_finalizer_is_idempotent_and_does_not_mutate_nested_input():
    source = {
        "rule_id": "LX0609-029",
        "status": "non_compliant",
        "result_status": "non_compliant",
        "reason_code": "requirement_violated",
        "is_compliant": False,
        "customer_display_facts": {},
        "criterion_results": [],
        "evidence_items": [{"quote": "", "metadata": {"rank": 1}}],
    }
    before = deepcopy(source)

    first = _finalize(source)
    second = _finalize(first)

    assert source == before
    assert first == second
    assert first is not source
    assert first["evidence_items"] is not source["evidence_items"]
    assert first["evidence_items"][0] is not source["evidence_items"][0]


def test_rule_040_keeps_the_controlled_customer_message_when_downgraded():
    result = _finalize(
        {
            "rule_id": "LX0609-040",
            "status": "non_compliant",
            "reason_code": "requirement_violated",
        }
    )

    assert result["status"] == "uncertain"
    assert result["findings"] == "暂无法确认是否需要进行四级手术术前多学科讨论"
    assert "手术级别" in result["evidence"]
