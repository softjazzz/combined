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


def test_customer_projection_rejects_bare_legacy_non_compliant_payload() -> None:
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
            "filters": {"rule_set_key": "luxian_0609_qc_v1"},
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


def test_batch_detail_keeps_versioned_canonical_contract_error_fail_closed() -> None:
    with pytest.raises(ValueError, match=LX0609_CUSTOMER_RESULT_CONTRACT_ERROR):
        project_customer_safe_batch_job(
            {
                "filters": {"rule_set_key": "luxian_0609_qc_v1"},
                "items": [
                    {
                        "record_id": "current-record",
                        "rule_id": "LX0609-020",
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
