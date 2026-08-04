"""LX0609 客户结果的唯一状态终结接口。"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ..luxian_0609_result_schema import CANONICAL_RESULT_STATUSES


_DEFAULT_INCOMPLETE_EXPLANATION = (
    "本次结果缺少规则专属、可核对的事实依据，暂不作为确定问题展示。",
    "未返回可展示的具体原因、核对标准或证据定位。",
    "请重新质控；如仍出现该提示，请补齐对应规则的受控事实和证据引用后再确认。",
)

_INCOMPLETE_EXPLANATION_BY_RULE = {
    "LX0609-040": (
        "暂无法确认是否需要进行四级手术术前多学科讨论",
        "当前缺少明确的手术级别或可核对的多学科讨论资料，不能将本项作为确定问题展示。",
        "请确认手术级别、术前讨论记录及参加科室信息后重新评估。",
    ),
}

_DATA_GAP_EXPLANATIONS = {
    "required_field_missing": {
        "reason_label": "关键字段缺失",
        "missing_sources": [],
        "missing_fields": ["完成判定所需的关键字段"],
        "customer_message": "已读取到相关资料，但缺少完成判定所需的关键字段，暂时无法完成本项质控。",
    },
    "source_unavailable": {
        "reason_label": "数据源未接入",
        "missing_sources": ["质控所需数据源"],
        "missing_fields": [],
        "customer_message": "本项质控所需的数据源尚未接入或本次未读取到，暂时无法完成判定。",
    },
    "source_empty": {
        "reason_label": "未读取到相关资料",
        "missing_sources": ["质控所需资料"],
        "missing_fields": [],
        "customer_message": "本次未读取到完成本项质控所需的相关资料，暂时无法完成判定。",
    },
    "source_truncated": {
        "reason_label": "输入资料不完整",
        "missing_sources": ["超出读取范围的后续资料"],
        "missing_fields": [],
        "customer_message": "相关资料数量超过本次读取范围，当前资料不完整，暂时无法完成本项质控。",
    },
    "source_readiness_unproven": {
        "reason_label": "数据同步状态未确认",
        "missing_sources": ["质控所需资料"],
        "missing_fields": [],
        "customer_message": "本项质控所需资料的同步状态尚未确认，暂时无法判断资料是否完整。",
    },
    "association_failed": {
        "reason_label": "资料关联失败",
        "missing_sources": ["需要相互核对的事件与文书"],
        "missing_fields": [],
        "customer_message": "已读取到相关资料，但暂时无法准确关联对应事件与文书，无法完成本项质控。",
    },
    "linkage_unresolved": {
        "reason_label": "关联资料不足",
        "missing_sources": ["需要相互核对的事件与文书"],
        "missing_fields": [],
        "customer_message": "现有资料不足以确认事件与文书的对应关系，暂时无法完成本项质控。",
    },
    "authoritative_time_missing": {
        "reason_label": "权威时间缺失",
        "missing_sources": [],
        "missing_fields": ["用于计算质控时限的权威时间"],
        "customer_message": "缺少用于计算质控时限的权威时间，暂时无法完成本项质控。",
    },
    "authoritative_time_conflict": {
        "reason_label": "权威时间冲突",
        "missing_sources": [],
        "missing_fields": ["相互一致的报告时间与评价截止时间"],
        "customer_message": "报告时间与本次住院的评价截止时间存在冲突，暂时无法完成本项质控。",
    },
    "evaluation_window_not_mature": {
        "reason_label": "评价窗口尚未结束",
        "missing_sources": [],
        "missing_fields": [],
        "customer_message": "截至本次评价日期尚未满规则要求的观察时限，本次暂不判定缺陷。",
    },
    "applicability_source_gap": {
        "reason_label": "适用性资料缺失",
        "missing_sources": ["判断质控点是否适用的关键资料"],
        "missing_fields": [],
        "customer_message": "缺少判断本质控点是否适用的关键资料，暂时无法继续判定。",
    },
}

_DEFAULT_DATA_GAP_EXPLANATION = {
    "reason_label": "现有资料不足",
    "missing_sources": ["完成本项质控所需资料"],
    "missing_fields": [],
    "customer_message": "现有资料不足，暂时无法完成本项质控；请补充或同步相关资料后重新评估。",
}

_CUSTOMER_SOURCE_LABELS = {
    "labtest_item_report": "检验结果明细",
    "exam_item_report": "检查报告明细",
    "consultation_record": "会诊记录",
    "inpat_drug_order": "药品医嘱",
    "inpat_nondrug_order": "非药品医嘱",
    "physician_change_event": "经治医师变更记录",
    "medical_order": "诊疗医嘱",
    "inpat_bill_item": "住院收费明细",
    "surgery_risk_assessment": "手术风险评估",
    "exam_attention_report": "检查危急值报告",
    "lab_attention_report": "检验危急值报告",
}


def _missing_sources_from_customer_facts(result: Mapping[str, Any]) -> list[str]:
    facts = result.get("customer_display_facts")
    if not isinstance(facts, Mapping):
        return []
    raw_values = facts.get("missing_sources")
    if not isinstance(raw_values, (list, tuple)):
        raw_values = [facts.get("missing_source")]
    labels: list[str] = []
    for value in raw_values:
        label = _CUSTOMER_SOURCE_LABELS.get(str(value or "").strip().lower())
        if label and label not in labels:
            labels.append(label)
    return labels


def _complete_data_gap_explanation(result: dict[str, Any]) -> None:
    reason_code = str(result.get("reason_code") or "").strip().lower()
    defaults = _DATA_GAP_EXPLANATIONS.get(
        reason_code,
        _DEFAULT_DATA_GAP_EXPLANATION,
    )
    existing_details = result.get("data_gap_details")
    completed_details = (
        dict(existing_details) if isinstance(existing_details, Mapping) else {}
    )

    def is_present(value: Any) -> bool:
        return value is not None and not (
            isinstance(value, str) and not value.strip()
        )

    def consistent_value(field: str, default: Any) -> Any:
        top_present = field in result and is_present(result.get(field))
        detail_present = field in completed_details and is_present(
            completed_details.get(field)
        )
        top_value = result.get(field)
        detail_value = completed_details.get(field)
        if top_present and detail_present and top_value != detail_value:
            raise ValueError(f"conflicting data gap explanation field: {field}")
        if top_present:
            return top_value
        if detail_present:
            return detail_value
        return default

    missing_sources = list(
        consistent_value(
            "missing_sources",
            _missing_sources_from_customer_facts(result)
            or defaults["missing_sources"],
        )
    )
    missing_fields = list(
        consistent_value("missing_fields", defaults["missing_fields"])
    )
    customer_message = str(
        consistent_value("customer_message", defaults["customer_message"])
    ).strip()
    result["missing_sources"] = missing_sources
    result["missing_fields"] = missing_fields
    result["customer_message"] = customer_message
    detail_reason_code = str(completed_details.get("reason_code") or "").strip().lower()
    if detail_reason_code and detail_reason_code != reason_code:
        raise ValueError("conflicting data gap explanation field: reason_code")
    completed_details.setdefault("reason_code", reason_code)
    completed_details.setdefault("reason_label", defaults["reason_label"])
    completed_details.setdefault("missing_sources", missing_sources)
    completed_details.setdefault("missing_fields", missing_fields)
    completed_details.setdefault("customer_message", customer_message)
    result["data_gap_details"] = completed_details


def _has_locatable_evidence(result: Mapping[str, Any]) -> bool:
    evidence_items = result.get("evidence_items")
    return isinstance(evidence_items, list) and any(
        isinstance(item, Mapping)
        and bool(str(item.get("quote") or "").strip())
        and bool(
            str(
                item.get("source_table")
                or item.get("source_document_id")
                or item.get("evidence_ref")
                or ""
            ).strip()
        )
        for item in evidence_items
    )


def _has_meaningful_value(value: Any) -> bool:
    """空字符串和空壳容器不能作为客户可核对的解释事实。"""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return any(_has_meaningful_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_has_meaningful_value(item) for item in value)
    # False 和 0 可能分别表示受控否定事实和精确计数，不能按普通真值丢弃。
    return True


def _is_compliant_for_status(status: str) -> bool | None:
    if status in {"compliant", "not_applicable"}:
        return True
    if status == "non_compliant":
        return False
    return None


def finalize_luxian_0609_canonical_result(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """生成最终客户结果；返回后状态字段不得再被下游改写。"""

    if not isinstance(result, Mapping):
        raise TypeError("result must be a mapping")
    rule_id = str(result.get("rule_id") or result.get("rule_code") or "").strip().upper()
    if not rule_id:
        raise ValueError("canonical result requires rule_id")
    status = str(result.get("status") or "").strip().lower()
    if status not in CANONICAL_RESULT_STATUSES:
        raise ValueError("canonical result has invalid status")

    finalized = deepcopy(dict(result))
    finalized["rule_id"] = rule_id
    finalized["status"] = status
    finalized["result_status"] = status
    finalized["is_compliant"] = _is_compliant_for_status(status)

    if status == "data_gap":
        _complete_data_gap_explanation(finalized)

    if status != "non_compliant":
        return finalized
    if (
        _has_meaningful_value(finalized.get("criterion_results"))
        or _has_meaningful_value(finalized.get("customer_display_facts"))
        or _has_locatable_evidence(finalized)
    ):
        return finalized

    findings, evidence, suggestion = _INCOMPLETE_EXPLANATION_BY_RULE.get(
        rule_id,
        _DEFAULT_INCOMPLETE_EXPLANATION,
    )
    finalized.update(
        {
            "status": "uncertain",
            "result_status": "uncertain",
            "is_compliant": None,
            "findings": findings,
            "evidence": evidence,
            "suggestion": suggestion,
            "reason_code": "customer_explanation_incomplete",
        }
    )
    return finalized
