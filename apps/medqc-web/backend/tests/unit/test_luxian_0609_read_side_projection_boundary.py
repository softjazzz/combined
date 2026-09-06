from pathlib import Path

import pytest

from app.services.custom_qc_workspace_service import (
    LX0609_CUSTOMER_RESULT_CONTRACT_ERROR,
    project_customer_safe_batch_job,
    project_customer_safe_result_item,
)


def test_formal_batch_worker_has_no_legacy_consultation_body_evidence_projector() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "app/services/sichuan_workspace_batch_worker.py"
    ).read_text(encoding="utf-8")

    assert "_consultation_evidence_items_for_batch" not in source
    assert "_snippet_near" not in source
    assert "CONSULT-REQUEST" not in source


def test_direct_customer_projection_keeps_bare_legacy_payload_fail_closed() -> None:
    with pytest.raises(ValueError, match=LX0609_CUSTOMER_RESULT_CONTRACT_ERROR):
        project_customer_safe_result_item(
            {
                "rule_id": "LX0609-020",
                "status": "non_compliant",
                "result_status": "non_compliant",
                "is_compliant": False,
                "diagnostic_trace": {"legacy": True},
            },
            hmac_key="unit-test-key",
        )


def test_customer_projection_has_no_historical_status_rewrite() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "app/services/custom_qc_workspace_service.py"
    ).read_text(encoding="utf-8")

    assert "historical_evidence_missing" not in source


def test_historical_batch_detail_isolates_bare_legacy_item_without_failing_the_job() -> None:
    projected = project_customer_safe_batch_job(
        {
            "filters": {"rule_set_id": "luxian_0609_qc_v1"},
            "items": [
                {
                    "record_id": "legacy-record",
                    "rule_id": "LX0609-020",
                    "status": "non_compliant",
                    "result_status": "non_compliant",
                    "is_compliant": False,
                    "diagnostic_trace": {"legacy": True},
                }
            ],
        },
        hmac_key="unit-test-key",
    )

    assert [(item["status"], item["reason_code"]) for item in projected["items"]] == [
        ("technical_error", "canonical_result_envelope_invalid")
    ]
    assert projected["summary"]["result_count"] == 1


def test_batch_detail_keeps_current_canonical_contract_error_fail_closed() -> None:
    with pytest.raises(ValueError, match=LX0609_CUSTOMER_RESULT_CONTRACT_ERROR):
        project_customer_safe_batch_job(
            {
                "filters": {"rule_set_key": "luxian_0609_qc_v1"},
                "items": [
                    {
                        "record_id": "current-record",
                        "rule_id": "LX0609-020",
                        "schema_version": "lx0609-customer-result-v2",
                        "rule_version": "current-version",
                        "status": "non_compliant",
                        "result_status": "non_compliant",
                        "is_compliant": False,
                        "diagnostic_trace": {"legacy": False},
                    }
                ],
            },
            hmac_key="unit-test-key",
        )


def test_current_canonical_projection_preserves_renderer_conclusion_and_suggestion() -> None:
    projected = project_customer_safe_result_item(
        {
            "schema_version": "lx0609-customer-result-v2",
            "rule_id": "LX0609-050",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "display_status": "non_compliant",
            "is_compliant": False,
            "reason_code": "diagnosis_discussion_missing",
            "conclusion": "执行器已生成的客户结论。",
            "suggestion": "执行器已生成的客户建议。",
            "customer_display_facts": {
                "verification_kind": "uncertain_diagnosis_discussion_check",
                "admission_time": "2026-08-01 08:00:00",
                "uncertain_record_times": ["2026-08-09 09:00:00"],
                "discussion_count": 0,
            },
            "customer_evidence": [
                {"source_type": "consultation_record", "source_document_id": "doc-secret"}
            ],
        },
        hmac_key="unit-test-key",
    )

    assert projected["conclusion"] == "执行器已生成的客户结论。"
    assert projected["suggestion"] == "执行器已生成的客户建议。"
    assert projected["status"] == "non_compliant"
    assert projected["evidence"][0]["source_ref"].startswith("src_")
    assert "doc-secret" not in str(projected)


def test_current_canonical_projection_rejects_status_field_mismatch() -> None:
    with pytest.raises(ValueError, match=LX0609_CUSTOMER_RESULT_CONTRACT_ERROR):
        project_customer_safe_result_item(
            {
                "schema_version": "lx0609-customer-result-v2",
                "rule_id": "LX0609-020",
                "status": "compliant",
                "result_status": "uncertain",
                "display_status": "compliant",
                "is_compliant": True,
            },
            hmac_key="unit-test-key",
        )
