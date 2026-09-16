"""LX0916-024..026 的逐项文书完整性合同。

此模块只净化模型事实并绑定同一份受控原文，不形成质控状态。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


_MAX_REQUIRED_ITEM_QUOTE_CHARS = 180
_FACT_BY_RULE = {
    "LX0916-024": "anesthesia_record",
    "LX0916-025": "surgery_record",
    "LX0916-026": "surgery_safety_check",
}
_ITEM_LABELS: dict[str, dict[str, str]] = {
    "anesthesia_record": {
        "patient_general_information": "患者一般情况",
        "preoperative_medication": "术前用药",
        "preoperative_special_conditions": "术前特殊情况",
        "preoperative_diagnosis": "术前诊断",
        "intraoperative_diagnosis": "术中诊断",
        "surgery_method": "手术方式",
        "anesthesia_method": "麻醉方式",
        "surgery_date": "手术日期",
        "anesthesia_induction_and_operation_times": "麻醉诱导及各项操作开始/结束时间",
        "surgery_start_end_time": "手术起止时间",
        "anesthesia_medication_name": "麻醉期间用药名称",
        "anesthesia_medication_method": "麻醉期间用药方式",
        "anesthesia_medication_dose": "麻醉期间用药剂量",
        "special_circumstance_management": "特殊情况及处理",
        "anesthesiologist_signature": "麻醉医师签名",
    },
    "surgery_record": {
        "patient_general_information": "患者一般项目",
        "operation_datetime": "手术日期",
        "preoperative_diagnosis": "术前诊断",
        "intraoperative_diagnosis": "术中诊断",
        "operation_name": "手术名称",
        "operator_and_assistants": "手术者及助手",
        "anesthesia_method": "麻醉方法",
        "operation_procedure": "手术经过",
        "blood_loss": "出血量",
        "transfusion_volume": "输血量",
        "intraoperative_condition_and_management": "术中情况及处理",
    },
    "surgery_safety_check": {
        "before_anesthesia_identity_site_and_procedure": "麻醉实施前患者身份、手术部位和方式核查",
        "before_anesthesia_risk_assessment": "麻醉实施前风险核查",
        "before_anesthesia_three_party_signatures": "麻醉实施前三方逐次确认签字",
        "before_incision_identity_site_and_procedure": "手术开始前患者身份、手术部位和方式核查",
        "before_incision_risk_and_equipment_confirmation": "手术开始前风险及设备核查",
        "before_incision_three_party_signatures": "手术开始前三方逐次确认签字",
        "before_exit_identity_and_actual_procedure_confirmation": "患者离开手术室前患者身份及实际手术方式核查",
        "before_exit_instrument_and_material_count_confirmation": "患者离开手术室前器械和物品清点核查",
        "before_exit_three_party_signatures": "患者离开手术室前三方逐次确认签字",
    },
}


@dataclass(frozen=True)
class GroundedDocumentCompleteness:
    required_items: dict[str, str | None]
    missing_items: tuple[str, ...]


def is_target_fact(fact_key: str) -> bool:
    return fact_key in _ITEM_LABELS


def instruction_for(rule_ids: Sequence[str]) -> str:
    active = {
        fact_key: _ITEM_LABELS[fact_key]
        for rule_id, fact_key in _FACT_BY_RULE.items()
        if rule_id in rule_ids
    }
    if not active:
        return ""
    return (
        "对于本次请求中的以下 document_facts，必须额外返回 required_items，其键必须严格等于对应合同："
        + json.dumps(active, ensure_ascii=False, separators=(",", ":"))
        + "。每个值只能是 null 或同一 document_id 文书内不超过180字的非空连续原文片段；不得改写、概括、跨文书拼接或以同一笼统长片段支撑多个不同项目。"
        + "这些文书不得输出 completeness 或 missing_items，Python 会在逐项原文定位后自行推导。"
        + "标本和输血核对仅在有明确适用事实时另行核对，本次不把未知适用性反推为缺项。"
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _valid_required_items(fact_key: str, value: Any) -> bool:
    expected = _ITEM_LABELS.get(fact_key)
    if expected is None or not isinstance(value, Mapping) or set(value) != set(expected):
        return False
    quotes: list[str] = []
    for quote in value.values():
        if quote is None:
            continue
        if not isinstance(quote, str) or not quote.strip() or len(quote) > _MAX_REQUIRED_ITEM_QUOTE_CHARS:
            return False
        quotes.append(quote)
    return len(quotes) == len(set(quotes))


def sanitize_model_fact(fact_key: str, raw_fact: Any) -> dict[str, Any] | None:
    """保留可验证存在性；畸形逐项合同不进入完整性路径。"""
    fact = _mapping(raw_fact)
    document_id = fact.get("document_id")
    source_type = fact.get("source_type")
    if (
        fact.get("presence") != "present"
        or not isinstance(document_id, str)
        or not document_id.strip()
        or not isinstance(source_type, str)
        or not source_type.strip()
    ):
        return None
    base = {"presence": "present", "document_id": document_id, "source_type": source_type}
    if (
        set(fact) == {"presence", "document_id", "source_type", "required_items"}
        and _valid_required_items(fact_key, fact.get("required_items"))
    ):
        return dict(fact)
    return base


def ground_document_fact(
    fact_key: str, fact: Mapping[str, Any], document: Mapping[str, Any]
) -> GroundedDocumentCompleteness | None:
    """从精确合同及同一受控文书生成可消费的完整性事实。"""
    expected = _ITEM_LABELS[fact_key]
    raw_items = _mapping(fact.get("required_items"))
    if not _valid_required_items(fact_key, raw_items):
        return None
    content = document.get("content")
    if not isinstance(content, str):
        return None
    items = {key: raw_items[key] for key in expected}
    if any(quote is not None and quote not in content for quote in items.values()):
        return None
    return GroundedDocumentCompleteness(
        required_items=items,
        missing_items=tuple(label for key, label in expected.items() if items[key] is None),
    )


def validated_missing_items(fact_key: str, fact: Mapping[str, Any]) -> tuple[str, ...] | None:
    """验证执行器可消费的本轮 grounded 文书事实，返回派生缺项。"""
    if not is_target_fact(fact_key) or set(fact) != {
        "presence", "document_id", "source_type", "evidence", "anchors",
        "completeness", "completeness_basis", "required_items", "missing_items",
    }:
        return None
    document_id, source_type = fact.get("document_id"), fact.get("source_type")
    if (
        fact.get("presence") != "present"
        or not isinstance(document_id, str) or not document_id.strip()
        or not isinstance(source_type, str) or not source_type.strip()
        or fact.get("completeness_basis") != "grounded_required_items"
        or not _valid_required_items(fact_key, fact.get("required_items"))
    ):
        return None
    expected_missing = tuple(
        label for key, label in _ITEM_LABELS[fact_key].items()
        if fact["required_items"][key] is None
    )
    missing = fact.get("missing_items")
    if (
        not isinstance(missing, Sequence) or isinstance(missing, (str, bytes))
        or tuple(missing) != expected_missing
        or fact.get("completeness") != ("incomplete" if expected_missing else "complete")
    ):
        return None
    evidence, anchors = fact.get("evidence"), fact.get("anchors")
    fields = {"presence", "completeness", *(f"required_items.{key}" for key in _ITEM_LABELS[fact_key])}
    if (
        not isinstance(evidence, Sequence) or isinstance(evidence, (str, bytes))
        or not evidence or any(not isinstance(item, str) or not item.strip() for item in evidence)
        or not isinstance(anchors, Sequence) or isinstance(anchors, (str, bytes))
        or not any(
            isinstance(anchor, Mapping)
            and anchor.get("document_type") == source_type
            and anchor.get("document_id") == document_id
            and isinstance(anchor.get("fields"), Sequence)
            and not isinstance(anchor["fields"], (str, bytes))
            and set(anchor["fields"]) == fields
            for anchor in anchors
        )
    ):
        return None
    return expected_missing


__all__ = [
    "GroundedDocumentCompleteness",
    "ground_document_fact",
    "instruction_for",
    "is_target_fact",
    "sanitize_model_fact",
    "validated_missing_items",
]
