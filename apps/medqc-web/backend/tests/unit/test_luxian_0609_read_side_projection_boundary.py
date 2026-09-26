from pathlib import Path

import pytest

import app.services.custom_qc_workspace_service as workspace_module
from app.services.luxian_0609_rule_catalog import get_luxian_0609_rule
from app.services.custom_qc_workspace_service import (
    LX0609_CUSTOMER_RESULT_CONTRACT_ERROR,
    project_customer_safe_batch_job,
    project_customer_safe_result_item,
)


def _current_long_text_item(conclusion: str, suggestion: str) -> dict:
    rule_id = "LX0609-03-02-01"
    rule = get_luxian_0609_rule(rule_id)
    return {
        "schema_version": "lx0609-customer-result-v2",
        "rule_id": rule_id,
        "rule_version": rule["rule_version"] if rule else "",
        "status": "compliant",
        "result_status": "compliant",
        "display_status": "compliant",
        "is_compliant": True,
        "conclusion": conclusion,
        "suggestion": suggestion,
    }


@pytest.mark.parametrize("deprecated_seal", [False, True])
def test_current_long_multiline_text_survives_detail_reprojection_and_export(
    deprecated_seal: bool,
) -> None:
    conclusion = "已核对的结论内容。" * 60
    suggestion = "\n".join(["请按已核对事实完善病历。"] * 40)
    item = _current_long_text_item(conclusion, suggestion)
    if deprecated_seal:
        # 历史结果附带的废弃签章字段被忽略：不校验、不改变输出、不外传。
        item["customer_text_seal"] = "lx0609-customer-text-v1:" + "f" * 64

    projected = project_customer_safe_result_item(item, hmac_key="unit-test-key")
    assert projected["conclusion"] == conclusion
    assert projected["suggestion"] == suggestion
    assert "customer_text_seal" not in projected
    assert project_customer_safe_result_item(projected, hmac_key="unit-test-key") == projected

    job = {"filters": {"rule_set_key": "luxian_0609_qc_v1"}, "items": [item]}
    detail = project_customer_safe_batch_job(job, hmac_key="unit-test-key")
    assert detail["items"][0]["conclusion"] == conclusion
    assert detail["items"][0]["suggestion"] == suggestion
    _items, rows, _summary = workspace_module._customer_export_rows(
        job, hmac_key="unit-test-key",
    )
    assert rows[0][5:7] == [conclusion, suggestion]


def test_long_text_exemption_is_limited_to_current_lx0609_results() -> None:
    long_text = "已核对的结论内容。" * 60
    projected = project_customer_safe_result_item(
        _current_long_text_item(long_text, long_text), hmac_key="unit-test-key",
    )
    assert projected["conclusion"] == long_text

    # 非 LX0609 规则声明客户 DTO schema 不能获得免裁剪权。
    foreign = {
        "schema_version": "customer-qc-result-v1",
        "rule_id": "CUSTOM-001",
        "status": "non_compliant",
        "result_status": "non_compliant",
        "is_compliant": False,
        "conclusion": long_text,
        "suggestion": long_text,
    }
    foreign_projected = project_customer_safe_result_item(foreign, hmac_key="unit-test-key")
    assert len(foreign_projected["conclusion"]) <= 363
    assert len(foreign_projected["suggestion"]) <= 363


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
                "rule_id": "LX0609-03-01-01",
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
                    "rule_id": "LX0609-03-01-01",
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
                        "rule_id": "LX0609-03-01-01",
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
            "rule_id": "LX0609-03-02-01",
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
                "rule_id": "LX0609-03-01-01",
                "status": "compliant",
                "result_status": "uncertain",
                "display_status": "compliant",
                "is_compliant": True,
            },
            hmac_key="unit-test-key",
        )
