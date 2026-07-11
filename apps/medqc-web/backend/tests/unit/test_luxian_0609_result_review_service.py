from __future__ import annotations

import json
from typing import Any

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
