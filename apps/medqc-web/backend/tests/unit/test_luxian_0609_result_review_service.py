from __future__ import annotations

import json
from typing import Any

from app.services.custom_qc_workspace_service import (
    project_customer_safe_batch_job,
    project_customer_safe_result_item,
)
from app.services.luxian_0609_result_review_service import review_luxian_0609_batch_job


def _job(
    *,
    rule_set_id: str = "luxian_0609_qc_v1",
    items: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    filters = {"rule_set_id": rule_set_id}
    return {
        "id": "job-review-001",
        "rule_code": rule_set_id,
        "rule_name": "泸县0609质控点验证 v1" if rule_set_id == "luxian_0609_qc_v1" else "其他规则集",
        "filters": filters,
        "summary": summary or {"rule_set_id": rule_set_id},
        "items": items or [],
    }


def test_review_service_rejects_non_luxian_job() -> None:
    report = review_luxian_0609_batch_job(_job(rule_set_id="sc_qc_v1"))

    assert report["review_status"] == "skipped"
    assert report["scope"] == "unsupported"
    assert report["summary"] == {"total_findings": 0, "p0": 0, "p1": 0, "p2": 0}
    assert report["findings"] == []


def test_review_service_flags_consultation_without_strong_evidence() -> None:
    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-020",
                    "rule_code": "LX0609-020",
                    "rule_name": "会诊记录：有会诊记录单无请会诊执行记录",
                    "record_id": "2329756",
                    "status": "uncertain",
                    "findings": "病程未记录会诊执行情况。",
                    "evidence_items": [
                        {
                            "source_document": "日常病程记录",
                            "quote": "患者一般情况可，继续目前治疗。",
                        }
                    ],
                }
            ],
        )
    )

    assert report["review_status"] == "completed"
    assert report["summary"]["p1"] == 1
    assert report["findings"][0]["suggested_status"] == "not_applicable"
    assert report["findings"][0]["risk_type"] == "applicability_gate"
    assert report["findings"][0]["auto_applied"] is False


def test_review_service_flags_non_compliant_positive_conclusion() -> None:
    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-003",
                    "rule_code": "LX0609-003",
                    "rule_name": "手术记录：术后24小时内是否完成",
                    "record_id": "2207717",
                    "status": "non_compliant",
                    "findings": "手术记录已在术后43分钟完成，未超过24小时。",
                    "evidence": "手术结束时间：10:00；记录时间：10:43。",
                }
            ],
        )
    )

    finding = report["findings"][0]
    assert finding["severity"] == "P0"
    assert finding["risk_type"] == "status_contradiction"
    assert finding["requires_human_review"] is True


def test_review_service_flags_data_gap_defect_badge() -> None:
    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-013",
                    "rule_code": "LX0609-013",
                    "status": "data_gap",
                    "defect_level": "轻微缺陷",
                    "findings": "缺少病理报告时间。",
                }
            ],
        )
    )

    finding = report["findings"][0]
    assert finding["risk_type"] == "data_gap_display"
    assert finding["severity"] == "P1"
    assert "数据不足" in finding["customer_message"]


def test_review_service_flags_internal_terms_and_weak_evidence() -> None:
    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-017",
                    "rule_code": "LX0609-017",
                    "status": "uncertain",
                    "findings": "待复核。",
                    "evidence": "证据模板：复制类 映射执行规则：CL-275 执行证据：长期",
                }
            ],
        )
    )

    risk_types = {item["risk_type"] for item in report["findings"]}
    assert "presentation" in risk_types
    assert "evidence_quality" in risk_types


def test_review_service_flags_transfusion_without_strong_fact() -> None:
    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-041",
                    "rule_code": "LX0609-041",
                    "status": "data_gap",
                    "findings": "发现相关事件但缺少输血知情同意书。",
                    "evidence": "应包含证据要素：输血申请、输血医嘱、输血记录。",
                }
            ],
        )
    )

    assert report["findings"][0]["risk_type"] == "applicability_gate"
    assert report["findings"][0]["suggested_status"] == "not_applicable"


def test_review_service_flags_chemo_without_order_or_record() -> None:
    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-026",
                    "rule_code": "LX0609-026",
                    "status": "non_compliant",
                    "findings": "恶性肿瘤患者病程未记录化疗。",
                    "evidence": "病理报告：胃腺癌。",
                }
            ],
        )
    )

    assert report["findings"][0]["risk_type"] == "applicability_gate"
    assert report["findings"][0]["suggested_status"] == "not_applicable"


def test_review_service_flags_mdt_without_level_4_surgery() -> None:
    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-040",
                    "rule_code": "LX0609-040",
                    "status": "non_compliant",
                    "findings": "术前讨论未体现MDT讨论意见。",
                    "evidence": "手术记录：腹腔镜胆囊切除术。",
                }
            ],
        )
    )

    assert report["findings"][0]["risk_type"] == "applicability_gate"
    assert report["findings"][0]["suggested_status"] == "not_applicable"


def test_llm_verifier_receives_only_sanitized_review_context() -> None:
    captured: list[dict[str, Any]] = []

    def fake_llm(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        captured.extend(payloads)
        return [
            {
                "finding_key": payloads[0]["finding_key"],
                "risk_level": "P1",
                "reason": "LLM 认为需人工复核。",
                "customer_message": "建议人工复核。",
                "requires_human_review": True,
            }
        ]

    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-020",
                    "rule_code": "LX0609-020",
                    "status": "uncertain",
                    "findings": "病程未记录会诊执行情况。",
                    "evidence": "执行证据：【日常病程记录】患者一般情况可。",
                    "raw_response": "secret",
                    "prompt": "secret",
                    "embedding": [1, 2, 3],
                    "medical_text": "完整病历全文",
                    "record_content": "完整正文",
                    "documents": [{"content": "完整文书"}],
                    "bundle": {"documents": []},
                    "llm_raw_output": "secret",
                }
            ],
        ),
        llm_verifier=fake_llm,
    )

    dumped = json.dumps(captured, ensure_ascii=False)
    assert captured
    assert "raw_response" not in dumped
    assert "medical_text" not in dumped
    assert "record_content" not in dumped
    assert "documents" not in dumped
    assert "bundle" not in dumped
    assert "完整病历全文" not in dumped
    assert report["llm_review_status"] == "completed"


def test_customer_projector_uses_canonical_status_and_safe_fields_only() -> None:
    projected = project_customer_safe_result_item(
        {
            "result_status": "data_gap",
            "status": "non_compliant",
            "display_status": "confirmed_defect",
            "is_compliant": False,
            "reason_code": "source_unavailable",
            "record_id": "R-001",
            "visit_id": "V-001",
            "patient_id": "P-001",
            "institute_id": "I-001",
            "mr_no": "M-001",
            "patient_name": "张某某",
            "phone": "13800138000",
            "rule_id": "LX0609-033",
            "rule_name": "手术知情同意书",
            "customer_conclusion": "当前受控来源尚不足以形成确定结论。",
            "findings": "原始结论不得回退。",
            "customer_suggestion": "请补充来源后重新评估。",
            "evidence_items": [
                {
                    "source_type": "consent_form",
                    "source_ref": "row-001",
                    "quote": "患者原文不得输出",
                }
            ],
        },
        hmac_key="unit-test-key",
    )

    assert projected["status"] == "data_gap"
    assert projected["is_confirmed_issue"] is False
    assert projected["reason_code"] == "source_unavailable"
    assert projected["record_ref"].startswith("rec_")
    assert projected["conclusion"] == "当前受控数据不足以形成确定结论。"
    assert projected["evidence"] == [
        {
            "source_type": "consent_form",
            "source_ref": projected["evidence"][0]["source_ref"],
        }
    ]
    dumped = json.dumps(projected, ensure_ascii=False)
    for forbidden in (
        "R-001",
        "V-001",
        "P-001",
        "I-001",
        "M-001",
        "张某某",
        "13800138000",
        "原始结论不得回退",
        "患者原文不得输出",
    ):
        assert forbidden not in dumped


def test_customer_projector_keeps_ai_suggestion_separate_from_confirmed_issue() -> None:
    projected = project_customer_safe_result_item(
        {
            "display_status": "ai_suggested_non_compliant",
            "is_compliant": False,
            "reason_code": "Semantic-Low-Confidence",
            "record_id": "R-002",
            "rule_code": "LX0609-021",
            "findings": "不得作为客户结论。",
        },
        hmac_key="unit-test-key",
    )

    assert projected["status"] == "ai_suggested_non_compliant"
    assert projected["is_confirmed_issue"] is False
    assert projected["reason_code"] == "reason_unavailable"
    assert projected["conclusion"] == "AI建议结合病历资料进一步确认。"


def test_customer_projector_never_trusts_unprojected_customer_text() -> None:
    projected = project_customer_safe_result_item(
        {
            "record_id": "R-RAW-TEXT",
            "rule_id": "LX0609-001",
            "status": "non_compliant",
            "customer_conclusion": "患者张三于某日出现高热咳嗽，肺部啰音明显。",
            "customer_suggestion": "请针对张三原始病历立即整改。",
        },
        hmac_key="unit-test-key",
    )

    assert projected["conclusion"] == "发现该质控点对应的明确问题。"
    assert projected["suggestion"] == "请按质控要求补充或修正。"
    dumped = json.dumps(projected, ensure_ascii=False)
    assert "张三" not in dumped
    assert "高热咳嗽" not in dumped


def test_customer_projector_is_idempotent_for_safe_identity_and_decision() -> None:
    first = project_customer_safe_result_item(
        {
            "record_id": "R-IDEMPOTENT",
            "rule_id": "LX0609-028",
            "result_status": "data_gap",
            "reason_code": "actual_interval_unavailable",
            "customer_conclusion": "实际用药时间证据不足。",
            "evidence_items": [
                {"source_type": "medical_order", "source_ref": "order-row-1"}
            ],
        },
        hmac_key="unit-test-key",
    )
    second = project_customer_safe_result_item(first, hmac_key="unit-test-key")

    assert second["record_ref"] == first["record_ref"]
    assert second["status"] == first["status"]
    assert second["reason_code"] == first["reason_code"]
    assert second["conclusion"] == first["conclusion"]
    assert second["evidence"] == first["evidence"]


def test_review_report_and_llm_payload_never_expose_record_identity_or_raw_body() -> None:
    captured: list[dict[str, Any]] = []

    def fake_llm(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        captured.extend(payloads)
        return []

    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-020",
                    "status": "uncertain",
                    "record_id": "R-003",
                    "visit_id": "V-003",
                    "patient_id": "P-003",
                    "institute_id": "I-003",
                    "patient_name": "李某某",
                    "findings": "原始会诊正文",
                    "evidence_items": [
                        {
                            "source_document": "日常病程记录",
                            "quote": "患者一般情况可，继续目前治疗。",
                        }
                    ],
                }
            ]
        ),
        llm_verifier=fake_llm,
    )

    dumped = json.dumps({"report": report, "payload": captured}, ensure_ascii=False)
    for forbidden in ("R-003", "V-003", "P-003", "I-003", "李某某", "原始会诊正文", "患者一般情况可"):
        assert forbidden not in dumped
    assert report["findings"][0]["record_ref"].startswith("rec_")


def test_review_uses_same_canonical_status_and_reason_as_customer_projector() -> None:
    item = {
        "rule_id": "LX0609-013",
        "result_status": "data_gap",
        "status": "non_compliant",
        "display_status": "confirmed_defect",
        "is_compliant": False,
        "reason_code": "source_unavailable",
        "record_id": "R-STATUS",
        "defect_level": "一般缺陷",
    }
    projected = project_customer_safe_result_item(item, hmac_key="unit-test-key")
    report = review_luxian_0609_batch_job(_job(items=[item]))

    assert projected["status"] == "data_gap"
    assert projected["reason_code"] == "source_unavailable"
    assert report["findings"][0]["original_status"] == projected["status"]
    assert report["findings"][0]["original_reason_code"] == projected["reason_code"]


def test_review_uses_same_unique_source_rows_as_customer_projection() -> None:
    duplicated = {
        "rule_id": "LX0609-020",
        "status": "data_gap",
        "reason_code": "source_incomplete",
        "record_id": "R-DUPLICATED",
        "findings": "未发现会诊文书。",
    }
    report = review_luxian_0609_batch_job(
        _job(
            items=[duplicated],
            summary={"rule_results": [{"items": [dict(duplicated)]}]},
        )
    )

    assert [finding["risk_type"] for finding in report["findings"]] == [
        "applicability_gate",
        "evidence_quality",
    ]


def test_review_accepts_already_projected_batch_job() -> None:
    projected = project_customer_safe_batch_job(
        _job(
            items=[
                {
                    "record_id": "R-PROJECTED",
                    "rule_id": "LX0609-020",
                    "status": "data_gap",
                    "reason_code": "source_incomplete",
                }
            ]
        ),
        hmac_key="unit-test-key",
    )

    report = review_luxian_0609_batch_job(projected)

    assert report["scope"] == "luxian_0609_qc_v1"
    assert report["review_status"] == "completed"


def test_review_provider_exception_is_reduced_to_safe_error_code() -> None:
    def failing_llm(_payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise RuntimeError("patient=张某某 visit=V-SECRET")

    report = review_luxian_0609_batch_job(
        _job(
            items=[
                {
                    "rule_id": "LX0609-013",
                    "status": "data_gap",
                    "record_id": "R-ERROR",
                    "defect_level": "一般缺陷",
                }
            ]
        ),
        llm_verifier=failing_llm,
    )

    dumped = json.dumps(report, ensure_ascii=False)
    assert report["llm_review_status"] == "failed"
    assert report["findings"][0]["llm_error_code"] == "review_provider_failed"
    assert "张某某" not in dumped
    assert "V-SECRET" not in dumped
