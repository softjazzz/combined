from __future__ import annotations

import json
from typing import Any

from app.services.custom_qc_workspace_service import (
    _row_to_batch_job,
    flatten_customer_safe_result_items,
    iter_unique_customer_result_source_items,
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


def test_serialized_batch_result_roundtrip_keeps_rule_facts_and_one_record_binding() -> None:
    """模拟任务 JSON 落库后的回读；不得丢失事实或将结果绑定到其他病历。"""

    persisted_row = {
        "id": "persisted-job-001",
        "draft_id": "draft-001",
        "rule_code": "LX0609",
        "rule_name": "泸县0609质控点验证 v1",
        "scene": "final",
        "scope": "final",
        "status": "completed",
        "filters_json": json.dumps({"rule_set_id": "luxian_0609_qc_v1"}),
        "record_ids_json": json.dumps(["VISIT-ONE"]),
        "summary_json": json.dumps({"rule_count": 49, "progress": {"step_key": "completed"}}),
        "items_json": json.dumps([
            {
                "institute_id": "H1",
                "patient_id": "P1",
                "visit_id": "VISIT-ONE",
                "record_id": "VISIT-ONE",
                "rule_id": "LX0609-025",
                "status": "non_compliant",
                "customer_display_facts": {
                    "failure_kind": "implant_information_incomplete",
                    "missing_fields": ["implant_specification", "implant_material"],
                    "source_document_id": "surgery-document-one",
                    "raw_surgery_text": "PRIVATE_SURGERY_TEXT_MUST_NOT_LEAK",
                },
                "customer_evidence": [
                    {"source_type": "surgery_record", "source_document_id": "surgery-document-one"}
                ],
            }
        ]),
        "failed_records_json": json.dumps([]),
        "child_job_ids_json": json.dumps([]),
        "child_summary_json": json.dumps({}),
        "error_message": None,
        "created_by": "tester",
        "created_at": None,
        "started_at": None,
        "finished_at": None,
        "updated_at": None,
        "total_records": 1,
        "success_count": 1,
        "failed_count": 0,
        "issue_records": 1,
        "compliant_records": 0,
        "total_tokens": 0,
        "total_processing_time": 0,
        "job_kind": "leaf",
        "parent_job_id": None,
        "family_key": None,
        "family_name": None,
    }

    readback = _row_to_batch_job(persisted_row)
    safe = project_customer_safe_batch_job(readback, hmac_key="unit-test-key")
    item = safe["items"][0]

    assert safe["record_focus"] == {"record_ref": item["record_ref"]}
    # 客户 DTO 不回传原始 visit_id；单病历授权依赖与结果同源的 record_ref。
    assert "record_ids" not in safe
    assert item["status"] == "non_compliant"
    assert item["customer_display_facts"] == {
        "failure_kind": "implant_information_incomplete",
        "source_label": "手术记录",
        "missing_fields": ["implant_specification", "implant_material"],
    }
    assert item["evidence"] == [{
        "source_type": "surgery_record",
        "source_ref": "src_" + __import__("hmac").new(
            b"unit-test-key",
            b"src:surgery-document-one",
            __import__("hashlib").sha256,
        ).hexdigest()[:24],
    }]
    assert "PRIVATE_SURGERY_TEXT_MUST_NOT_LEAK" not in json.dumps(safe, ensure_ascii=False)
    assert "VISIT-ONE" not in json.dumps(safe, ensure_ascii=False)


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

    assert projected["status"] == "uncertain"
    assert projected["is_confirmed_issue"] is False
    assert projected["reason_code"] == "customer_explanation_incomplete"
    assert projected["conclusion"] == "现有证据无法形成确定结论。"
    assert projected["suggestion"] == "建议结合病历资料进一步确认。"
    dumped = json.dumps(projected, ensure_ascii=False)
    assert "张三" not in dumped
    assert "高热咳嗽" not in dumped


def test_customer_projector_preserves_shared_lx004_timeliness_facts() -> None:
    projected = project_customer_safe_result_item(
        {
            "record_id": "R-004",
            "rule_id": "LX0609-004",
            "rule_version": "2026-07-29",
            "status": "non_compliant",
            "reason_code": "threshold_exceeded",
            "customer_display_facts": {
                "failure_kind": "timeliness_requirement_not_met",
                "target_document": "rescue_record",
                "source_label": "抢救记录",
                "timeliness_state": "late",
                "threshold_hours": 6,
                "anchor_time": "2026-06-01 09:00:00",
                "observed_time": "2026-06-01 16:15:00",
                "elapsed_hours": 7.25,
                "source_document_id": "PRIVATE_RESCUE_DOCUMENT_ID",
                "raw_rescue_text": "PRIVATE_RESCUE_TEXT",
            },
        },
        hmac_key="unit-test-key",
    )

    assert projected["status"] == "non_compliant"
    assert projected["customer_display_facts"] == {
        "failure_kind": "timeliness_requirement_not_met",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "timeliness_state": "late",
        "threshold_hours": 6,
        "anchor_time": "2026-06-01 09:00:00",
        "observed_time": "2026-06-01 16:15:00",
        "elapsed_hours": 7.25,
    }
    assert "PRIVATE_RESCUE_TEXT" not in json.dumps(projected, ensure_ascii=False)
    assert "PRIVATE_RESCUE_DOCUMENT_ID" not in json.dumps(projected, ensure_ascii=False)


def test_customer_projector_preserves_only_controlled_lx018_criteria() -> None:
    projected = project_customer_safe_result_item(
        {
            "record_id": "PRIVATE_RECORD",
            "rule_id": "LX0609-018",
            "rule_version": "2026-07-28",
            "status": "non_compliant",
            "model_analysis": "原始模型医学分析：主诉的症状、病程与第一诊断之间缺少足够的特异性对应。",
            "criterion_results": [
                {
                    "criterion_id": "chief_complaint_length",
                    "kind": "text_length",
                    "status": "failed",
                    "reason_code": "complaint_too_long",
                    "actual_value": 21,
                    "expected_value": 20,
                    "operator": "lte",
                    "unit": "character",
                    "source_fact": "admission_record.chief_complaint",
                    "raw_text": "PRIVATE_COMPLAINT_TEXT",
                },
                {
                    "criterion_id": "diagnostic_direction",
                    "kind": "semantic_relation",
                    "status": "passed",
                    "reason_code": "requirement_satisfied",
                    "actual_value": "supported",
                    "left_fact": "admission_record.chief_complaint",
                    "right_fact": "admission_record.first_diagnosis",
                    "dimensions": [
                        "anatomic_site",
                        "symptom_pattern",
                        "PRIVATE_DIMENSION",
                    ],
                    "medical_analysis": "受控医学分析",
                },
            ],
        },
        hmac_key="unit-test-key",
    )

    assert projected["rule_version"] == "2026-07-28"
    assert [row["criterion_id"] for row in projected["criterion_results"]] == [
        "chief_complaint_length",
        "diagnostic_direction",
    ]
    assert projected["criterion_results"][0]["expected_value"] == 20
    assert projected["criterion_results"][1]["dimensions"] == [
        "anatomic_site",
        "symptom_pattern",
    ]
    assert projected["criterion_results"][1]["medical_analysis"] == "受控医学分析"
    assert projected["model_analysis"] == "原始模型医学分析：主诉的症状、病程与第一诊断之间缺少足够的特异性对应。"
    assert "PRIVATE" not in json.dumps(projected, ensure_ascii=False)


def test_old_018_result_is_logically_invalidated_without_deleting_storage() -> None:
    job = _job(
        items=[
            {
                "record_id": "R-OLD",
                "rule_id": "LX0609-018",
                "rule_version": "2026-06-09",
                "status": "non_compliant",
            },
            {
                "record_id": "R-NEW",
                "rule_id": "LX0609-018",
                "rule_version": "2026-07-28",
                "status": "non_compliant",
                "criterion_results": [
                    {
                        "criterion_id": "chief_complaint_length",
                        "kind": "text_length",
                        "status": "failed",
                        "reason_code": "complaint_too_long",
                        "actual_value": 21,
                        "expected_value": 20,
                    }
                ],
            },
        ]
    )

    projected = flatten_customer_safe_result_items(job, hmac_key="unit-test-key")

    assert len(projected) == 1
    assert projected[0]["rule_version"] == "2026-07-28"


def test_incomplete_historical_safe_dto_cannot_reuse_generic_confirmed_issue_text() -> None:
    projected = project_customer_safe_result_item(
        {
            "schema_version": "customer-qc-result-v1",
            "record_id": "R-OLD",
            "rule_id": "LX0609-025",
            "status": "non_compliant",
            "conclusion": "发现该质控点对应的明确问题。",
            "suggestion": "请按质控要求补充或修正记录。",
        },
        hmac_key="unit-test-key",
    )

    assert projected["status"] == "uncertain"
    assert projected["reason_code"] == "customer_explanation_incomplete"
    assert projected["conclusion"] != "发现该质控点对应的明确问题。"


def test_duplicate_record_rule_keeps_explained_latest_candidate_only() -> None:
    job = _job(
        items=[
            {
                "record_id": "R-ONE",
                "rule_id": "LX0609-025",
                "status": "non_compliant",
                "reason_code": "implant_information_incomplete",
            },
            {
                "record_id": "R-ONE",
                "rule_id": "LX0609-025",
                "status": "non_compliant",
                "reason_code": "implant_information_incomplete",
                "customer_display_facts": {
                    "failure_kind": "implant_information_incomplete",
                    "missing_fields": ["implant_quantity"],
                },
            },
        ]
    )

    raw = iter_unique_customer_result_source_items(job, hmac_key="unit-test-key")
    projected = flatten_customer_safe_result_items(job, hmac_key="unit-test-key")

    assert len(raw) == 1
    assert len(projected) == 1
    assert projected[0]["status"] == "non_compliant"
    assert projected[0]["customer_display_facts"]["missing_fields"] == ["implant_quantity"]


def test_old_018_result_is_also_hidden_from_grouped_rule_results() -> None:
    job = _job()
    job["rule_results"] = [
        {
            "rule_code": "LX0609-018",
            "rule_name": "主诉能导出第一诊断",
            "items": [
                {
                    "record_id": "R-OLD",
                    "rule_id": "LX0609-018",
                    "rule_version": "2026-06-09",
                    "status": "non_compliant",
                    "reason_code": "complaint_too_short",
                },
                {
                    "record_id": "R-NEW",
                    "rule_id": "LX0609-018",
                    "rule_version": "2026-07-28",
                    "status": "non_compliant",
                    "criterion_results": [
                        {
                            "criterion_id": "chief_complaint_length",
                            "kind": "text_length",
                            "status": "failed",
                            "reason_code": "complaint_too_long",
                            "actual_value": 21,
                            "expected_value": 20,
                        }
                    ],
                },
            ],
        }
    ]

    projected = project_customer_safe_batch_job(job, hmac_key="unit-test-key")

    assert [item["record_ref"] for item in projected["items"]] == [
        projected["rule_results"][0]["items"][0]["record_ref"]
    ]
    assert len(projected["rule_results"][0]["items"]) == 1
    assert projected["rule_results"][0]["items"][0]["rule_version"] == "2026-07-28"


def test_customer_projector_preserves_only_controlled_lx025_missing_fields() -> None:
    projected = project_customer_safe_result_item(
        {
            "record_id": "PRIVATE_RECORD",
            "rule_id": "LX0609-025",
            "status": "non_compliant",
            "customer_display_facts": {
                "missing_fields": [
                    "implant_specification",
                    "implant_material",
                    "PRIVATE_FIELD",
                ],
                "source_label": "PRIVATE_SOURCE",
                "raw_text": "PRIVATE_SURGERY_TEXT",
            },
            "customer_evidence": [{
                "source_type": "surgery_record",
                "source_document_id": "private-surgery-document-id",
            }],
        },
        hmac_key="unit-test-key",
    )

    assert projected["customer_display_facts"] == {
        "failure_kind": "implant_information_incomplete",
        "source_label": "手术记录",
        "missing_fields": ["implant_specification", "implant_material"],
    }
    assert projected["evidence"] == [{
        "source_type": "surgery_record",
        "source_ref": "src_" + __import__("hmac").new(
            b"unit-test-key",
            b"src:private-surgery-document-id",
            __import__("hashlib").sha256,
        ).hexdigest()[:24],
    }]
    assert "PRIVATE" not in json.dumps(projected, ensure_ascii=False)


def test_customer_projector_keeps_only_controlled_surgery_document_gap_facts() -> None:
    projected = project_customer_safe_result_item(
        {
            "record_id": "PRIVATE_RECORD",
            "rule_id": "LX0609-030",
            "status": "non_compliant",
            "customer_display_facts": {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_record",
                "performed_surgery_confirmed": True,
                "raw_text": "PRIVATE_SURGERY_TEXT",
            },
        },
        hmac_key="unit-test-key",
    )

    assert projected["customer_display_facts"] == {
        "failure_kind": "surgery_document_missing",
        "target_document": "surgery_record",
        "performed_surgery_confirmed": True,
    }
    assert "PRIVATE_SURGERY_TEXT" not in json.dumps(projected, ensure_ascii=False)


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


def test_customer_projector_persists_rule_specific_compliant_explanation() -> None:
    projected = project_customer_safe_result_item(
        {
            "record_id": "R-COMPLIANT",
            "schema_version": "lx0609-customer-result-v2",
            "rule_id": "LX0609-032",
            "status": "compliant",
            "reason_code": "requirement_satisfied",
            "findings": "符合质控要求",
        },
        hmac_key="unit-test-key",
    )

    assert projected["status"] == "compliant"
    assert projected["conclusion"] == "已确认本次手术具备手术安全核查表。"
    assert projected["findings"] == projected["conclusion"]


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
