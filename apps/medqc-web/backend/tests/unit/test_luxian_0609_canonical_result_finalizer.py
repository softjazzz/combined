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
        ({"customer_display_facts": {"failure_kind": ""}}, "uncertain"),
        ({"criterion_results": [{"status": "", "details": {}}]}, "uncertain"),
        ({"customer_display_facts": {"failure_kind": "document_missing"}}, "non_compliant"),
        ({"customer_display_facts": {"requirement_met": False}}, "non_compliant"),
        ({"customer_display_facts": {"missing_count": 0}}, "non_compliant"),
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


def test_data_gap_always_has_customer_readable_missing_data_contract():
    result = _finalize(
        {
            "rule_id": "LX0609-011",
            "status": "data_gap",
            "reason_code": "required_field_missing",
        }
    )

    assert result["status"] == "data_gap"
    assert result["reason_code"] == "required_field_missing"
    assert result["missing_sources"] == []
    assert result["missing_fields"] == ["完成判定所需的关键字段"]
    assert result["customer_message"] == (
        "已读取到相关资料，但缺少完成判定所需的关键字段，暂时无法完成本项质控。"
    )
    assert result["data_gap_details"] == {
        "reason_code": "required_field_missing",
        "reason_label": "关键字段缺失",
        "missing_sources": [],
        "missing_fields": ["完成判定所需的关键字段"],
        "customer_message": result["customer_message"],
    }


def test_rule_009_candidate_scope_gap_does_not_claim_missing_source() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-009",
            "status": "data_gap",
            "reason_code": "candidate_scope_incomplete",
        }
    )

    assert result["missing_sources"] == []
    assert result["missing_fields"] == []
    assert result["data_gap_details"]["reason_label"] == "自动核对范围超限"
    assert "现有资料无需补充" in result["customer_message"]
    assert "后续资料" not in result["customer_message"]

    other_rule = _finalize(
        {
            "rule_id": "LX0609-054",
            "status": "data_gap",
            "reason_code": "candidate_scope_incomplete",
        }
    )
    assert other_rule["missing_sources"] == ["完成本项质控所需资料"]
    assert other_rule["data_gap_details"]["reason_label"] == "现有资料不足"


def test_rule_048_names_the_missing_anesthesia_record_instead_of_generic_materials() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-048",
            "status": "data_gap",
            "reason_code": "transfusion_comparison_fields_unavailable",
            "customer_display_facts": {
                "failure_kind": "transfusion_comparison_material_missing",
                "missing_sources": ["anesthesia_record"],
            },
        }
    )

    assert result["missing_sources"] == ["麻醉记录单"]
    assert result["missing_fields"] == []
    assert result["data_gap_details"]["reason_label"] == "术中输血比对资料不完整"
    assert "麻醉记录单" in result["customer_message"]
    assert "完成本项质控所需资料" not in result["missing_sources"]


def test_rule_031_signature_association_gap_names_the_unavailable_signature_fields() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-031",
            "status": "data_gap",
            "reason_code": "association_failed",
        }
    )

    assert result["missing_sources"] == []
    assert result["missing_fields"] == ["主刀医师签名", "手术事件与手术记录的对应关系"]
    assert result["data_gap_details"]["reason_label"] == "手术签名信息暂无法核对"
    assert "主刀医师签名" in result["customer_message"]
    assert "提交人" not in result["customer_message"]


def test_rule_028_required_field_gap_names_the_actual_prophylaxis_inputs() -> None:
    result = _finalize(
        {
            "rule_id": "LX0609-028",
            "status": "data_gap",
            "reason_code": "required_field_missing",
        }
    )

    assert result["missing_sources"] == []
    assert result["missing_fields"] == [
        "手术切口等级",
        "预防性用药属性",
        "抗菌药物实际给药时间",
        "抗菌药物实际停用时间",
    ]
    assert result["data_gap_details"]["reason_label"] == "预防性抗菌药物时长字段不完整"
    assert "实际停用时间" in result["customer_message"]
    assert "医嘱更新时间不能替代实际停用时间" in result["customer_message"]


@pytest.mark.parametrize(
    ("reason_code", "reason_label", "expected_phrase"),
    [
        ("source_unavailable", "数据源未接入", "尚未接入"),
        ("source_empty", "未读取到相关资料", "未读取到"),
        ("source_truncated", "输入资料不完整", "超过本次读取范围"),
        ("source_readiness_unproven", "数据同步状态未确认", "同步状态"),
        ("association_failed", "资料关联失败", "无法准确关联"),
        ("linkage_unresolved", "关联资料不足", "对应关系"),
        ("authoritative_time_missing", "权威时间缺失", "权威时间"),
        ("authoritative_time_conflict", "权威时间冲突", "存在冲突"),
        ("evaluation_window_not_mature", "评价窗口尚未结束", "尚未满"),
        ("applicability_source_gap", "适用性资料缺失", "是否适用"),
        ("unexpected_gap", "现有资料不足", "现有资料不足"),
    ],
)
def test_every_data_gap_reason_gets_a_controlled_customer_explanation(
    reason_code: str,
    reason_label: str,
    expected_phrase: str,
):
    result = _finalize(
        {
            "rule_id": "LX0609-054",
            "status": "data_gap",
            "reason_code": reason_code,
        }
    )

    assert result["data_gap_details"]["reason_label"] == reason_label
    assert expected_phrase in result["customer_message"]
    assert isinstance(result["missing_sources"], list)
    assert isinstance(result["missing_fields"], list)


def test_data_gap_completion_preserves_more_precise_existing_details():
    result = _finalize(
        {
            "rule_id": "LX0609-052",
            "status": "data_gap",
            "reason_code": "required_field_missing",
            "missing_sources": ["检验结果明细"],
            "missing_fields": ["危急值标志"],
            "customer_message": "缺少检验结果明细中的危急值标志，暂时无法核对。",
            "data_gap_details": {"availability": "unavailable"},
        }
    )

    assert result["missing_sources"] == ["检验结果明细"]
    assert result["missing_fields"] == ["危急值标志"]
    assert result["customer_message"] == "缺少检验结果明细中的危急值标志，暂时无法核对。"
    assert result["data_gap_details"]["availability"] == "unavailable"
    assert result["data_gap_details"]["reason_label"] == "关键字段缺失"


def test_data_gap_completion_does_not_overwrite_rule_specific_detail_fields():
    existing_details = {
        "reason_code": "authoritative_time_missing",
        "reason_label": "病例评价时间待确认",
        "missing_sources": [],
        "missing_fields": ["有效出院时间"],
        "customer_message": "请确认本次住院的有效出院时间。",
    }
    result = _finalize(
        {
            "rule_id": "LX0609-012",
            "status": "data_gap",
            "reason_code": "authoritative_time_missing",
            "data_gap_details": existing_details,
        }
    )

    assert result["data_gap_details"] == existing_details
    assert result["missing_sources"] == existing_details["missing_sources"]
    assert result["missing_fields"] == existing_details["missing_fields"]
    assert result["customer_message"] == existing_details["customer_message"]


def test_data_gap_rejects_conflicting_top_level_and_detail_explanations():
    with pytest.raises(ValueError, match="conflicting data gap explanation field"):
        _finalize(
            {
                "rule_id": "LX0609-012",
                "status": "data_gap",
                "reason_code": "authoritative_time_missing",
                "customer_message": "顶层解释",
                "data_gap_details": {
                    "reason_code": "authoritative_time_missing",
                    "customer_message": "嵌套解释",
                },
            }
        )


def test_data_gap_uses_controlled_missing_source_from_customer_facts():
    result = _finalize(
        {
            "rule_id": "LX0609-052",
            "status": "data_gap",
            "reason_code": "required_field_missing",
            "customer_display_facts": {
                "failure_kind": "critical_value_result_detail_missing",
                "missing_source": "labtest_item_report",
            },
        }
    )

    assert result["missing_sources"] == ["检验结果明细"]
    assert result["missing_fields"] == ["完成判定所需的关键字段"]
