"""N12客户解释支持；未接入新reason的本树以临时模块白名单替身隔离验证文案。

不改decision_model生产合同；真实完整执行由N12核心树联合验证。
"""
from copy import deepcopy

import pytest

from app.services.luxian_0609 import decision_model, decision_reducer
from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_canonical_result
from app.services.luxian_0609.customer_renderer import data_gap_customer_message, render_luxian_0609_customer_result

RULE = "LX0609-04-04-02"
REASON = "semantic_extraction_unresolved"
TITLE = "麻醉访视内容暂无法确认"
CONCLUSION = "现有访视正文的必填内容尚未形成可靠抽取结果，暂时无法判定填写是否完整。"
SUGGESTION = "请复核现有访视正文或重试质控；不要据此补写或改写记录。"


@pytest.fixture
def isolated_reason_allowlist(monkeypatch):
    # 此替身只隔离测试消息支持，不能证明本树正式reason合同已经接入。
    if REASON not in decision_model._ALL_ALLOWED_REASON_CODES:
        monkeypatch.setattr(decision_model, "_ALL_ALLOWED_REASON_CODES",
                            decision_model._ALL_ALLOWED_REASON_CODES | {REASON})
    allowed = dict(decision_reducer.ALLOWED_REASON_CODES_BY_FINAL_STATE)
    if REASON not in allowed["data_gap"]:
        allowed["data_gap"] = allowed["data_gap"] | {REASON}
        monkeypatch.setattr(decision_reducer, "ALLOWED_REASON_CODES_BY_FINAL_STATE", allowed)


def message_chain(rule=RULE, reason=REASON):
    original = decision_model.RuleDecision(
        rule_id=rule, snapshot_hash="a" * 64,
        applicability=decision_model.ApplicabilityState.APPLICABLE,
        evidence_state=decision_model.EvidenceState.DATA_GAP,
        qc_direction=decision_model.QcDirection.UNKNOWN,
        reason_code=reason, fact_refs=("b" * 64,), evaluator_version="n12-copy-support-v1",
    )
    reduced = decision_reducer.reduce_luxian_0609_rule_decision(original)
    rendered = render_luxian_0609_customer_result(decision=reduced)
    return reduced, rendered, finalize_luxian_0609_canonical_result(rendered)


def test_n12_message_support_full_reduced_renderer_finalizer_with_explicit_reason_stub(isolated_reason_allowlist):
    reduced, rendered, result = message_chain()
    assert reduced.final_state is decision_reducer.CustomerFinalState.DATA_GAP
    assert rendered["status"] == result["status"] == "data_gap"
    assert rendered["reason_code"] == result["reason_code"] == REASON
    assert rendered["findings"] == TITLE
    assert rendered["evidence"] == CONCLUSION
    assert rendered["suggestion"] == result["suggestion"] == SUGGESTION
    assert result["customer_message"] == CONCLUSION
    assert result["missing_sources"] == result["missing_fields"] == []
    assert result["data_gap_details"] == {
        "reason_code": REASON, "reason_label": "内容抽取待确认",
        "missing_sources": [], "missing_fields": [], "customer_message": CONCLUSION,
    }
    assert result["is_compliant"] is None
    assert not result.get("customer_display_facts")
    assert "源资料缺失" not in result["findings"]
    assert "完整可读取的文书" not in result["suggestion"]


@pytest.mark.parametrize("variant", ["direct", "precompleted"])
def test_n12_public_finalizer_defaults_are_extraction_gap_not_missing_data(variant):
    raw = {"rule_id": RULE, "status": "data_gap", "reason_code": REASON}
    if variant == "precompleted":
        raw["data_gap_details"] = {"reason_code": REASON, "missing_sources": [], "missing_fields": []}
    original = deepcopy(raw)
    result = finalize_luxian_0609_canonical_result(raw)
    assert raw == original
    assert result["status"] == "data_gap" and result["reason_code"] == REASON
    assert result["missing_sources"] == result["missing_fields"] == []
    assert result["data_gap_details"]["reason_label"] == "内容抽取待确认"
    assert result["customer_message"] == CONCLUSION


@pytest.mark.parametrize("reason,message,label,fields", [
    ("source_unavailable", "本项质控所需的数据源尚未接入或本次未读取到，暂时无法完成判定。", "数据源未接入", []),
    ("required_field_missing", "已读取到相关资料，但缺少完成判定所需的关键字段，暂时无法完成本项质控。", "关键字段缺失", ["完成判定所需的关键字段"]),
])
def test_n12_existing_reasons_keep_existing_finalizer_message(reason, message, label, fields):
    result = finalize_luxian_0609_canonical_result({"rule_id": RULE, "status": "data_gap", "reason_code": reason})
    assert result["customer_message"] == message
    assert result["data_gap_details"]["reason_label"] == label
    assert result["missing_fields"] == fields
    assert result["reason_code"] == reason


@pytest.mark.parametrize("rule", ["LX0609-05-01-02", "LX0609-04-04-01"])
def test_new_reason_does_not_change_other_rules_default_explanations(rule):
    result = finalize_luxian_0609_canonical_result({"rule_id": rule, "status": "data_gap", "reason_code": REASON})
    assert result["customer_message"] == "现有资料不足，暂时无法完成本项质控；请补充或同步相关资料后重新评估。"
    assert result["missing_sources"] == ["完成本项质控所需资料"]
    assert result["data_gap_details"]["reason_label"] == "现有资料不足"
    assert data_gap_customer_message(rule_id=rule, reason_code=REASON, missing_sources=[]) != CONCLUSION
