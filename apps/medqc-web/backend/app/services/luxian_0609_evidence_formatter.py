from __future__ import annotations

from typing import Any

from .luxian_0609_trigger_gate import Luxian0609GateDecision


_FAMILY_HINTS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("时限类", ("24小时", "48", "72", "8 小时", "8小时", "6小时", "规定时间"), ("触发时间", "截止时间", "实际记录时间", "超时或缺失结论", "来源文书/表字段")),
    ("检查检验类", ("CT", "MRI", "培养", "阳性", "报告"), ("报告时间", "阳性结果", "24小时内病程分析", "来源报告", "对应病程记录")),
    ("会诊类", ("会诊",), ("会诊申请单", "会诊目的", "会诊意见", "执行记录")),
    ("复制类", ("复制", "重复", "相似"), ("重复文书", "重复片段", "相似原因", "记录时间")),
    ("手术麻醉类", ("手术", "麻醉", "术前", "术后", "安全核查"), ("手术时间", "麻醉记录", "安全核查单", "关键缺失项")),
    ("输血类", ("输血", "红细胞", "血浆", "血小板"), ("输血申请", "输血医嘱", "输血记录", "费用", "输血前检查项")),
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return "、".join(_text(item) for item in value if _text(item))
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            rendered = _text(item)
            if rendered:
                parts.append(f"{key}: {rendered}")
        return "；".join(parts)
    return str(value)


def _rule_profile(rule: dict[str, Any]) -> str:
    return "\n".join(
        _text(item)
        for item in [
            rule.get("rule_id"),
            rule.get("name"),
            rule.get("rule_name"),
            rule.get("description"),
            rule.get("trigger_condition"),
            rule.get("data_dependencies"),
            rule.get("applicable_document_labels"),
            rule.get("applicable_documents"),
        ]
        if item is not None
    )


def _detect_family(rule: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    profile = _rule_profile(rule)
    for family, markers, evidence_slots in _FAMILY_HINTS:
        if any(marker in profile for marker in markers):
            return family, evidence_slots
    return "通用质控", ("触发事实", "来源文书", "判定依据", "处理建议")


def format_luxian_0609_evidence(
    *,
    result: dict[str, Any],
    wrapper_rule: dict[str, Any],
    gate_decision: Luxian0609GateDecision | None = None,
) -> dict[str, Any]:
    """Normalize customer-facing evidence without changing the decision."""

    normalized = dict(result or {})
    metadata = dict(normalized.get("metadata") or {})
    family, expected_slots = _detect_family(wrapper_rule)
    current_evidence = _text(normalized.get("evidence")).strip()
    current_findings = _text(normalized.get("findings")).strip()
    current_suggestion = _text(normalized.get("suggestion")).strip()

    lines = [f"证据模板：{family}"]
    lines.append(f"质控点：{wrapper_rule.get('rule_id')} {wrapper_rule.get('name') or wrapper_rule.get('rule_name') or ''}".strip())
    if gate_decision is not None:
        lines.append(f"触发状态：{gate_decision.status}")
        lines.append(f"触发说明：{gate_decision.reason}")
        if gate_decision.matched_keywords:
            lines.append(f"触发关键词：{'、'.join(gate_decision.matched_keywords)}")
        if gate_decision.data_gap_fields:
            lines.append(f"数据缺口：{'、'.join(gate_decision.data_gap_fields)}")
    mapped_rule_ids = list(wrapper_rule.get("mapped_rule_ids") or [])
    if mapped_rule_ids:
        lines.append(f"映射执行规则：{'、'.join(str(item) for item in mapped_rule_ids)}")
    lines.append(f"应包含证据要素：{'、'.join(expected_slots)}")
    if current_evidence:
        lines.append(f"执行证据：{current_evidence}")
    elif current_findings:
        lines.append(f"执行证据：{current_findings}")
    else:
        lines.append("执行证据：当前结果未返回具体证据片段，需人工复核。")

    normalized["evidence"] = "\n".join(lines)
    if not current_findings:
        status = str(normalized.get("status") or "").strip()
        if status == "not_applicable":
            normalized["findings"] = "未发现该质控点所需触发事件，本次判定为不适用。"
        elif status == "data_gap":
            normalized["findings"] = "已发现触发事件，但缺少完成判定所需的数据。"
        elif status == "non_compliant":
            normalized["findings"] = "发现与该质控点相关的不合规问题。"
        elif status == "compliant":
            normalized["findings"] = "已检查该质控点，当前证据支持符合要求。"
        else:
            normalized["findings"] = "该质控点需要人工复核。"
    if not current_suggestion:
        normalized["suggestion"] = "请结合证据要素复核相关文书和结构化数据。"

    metadata["evidence_template_family"] = family
    metadata["evidence_template_slots"] = list(expected_slots)
    normalized["metadata"] = metadata
    return normalized
