from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TRIGGER_PRESENT = "present"
TRIGGER_ABSENT = "absent"
TRIGGER_DATA_GAP = "data_gap"
TRIGGER_UNKNOWN = "unknown"

_KNOWN_STATUSES = {TRIGGER_PRESENT, TRIGGER_ABSENT, TRIGGER_DATA_GAP, TRIGGER_UNKNOWN}


@dataclass(frozen=True)
class Luxian0609GateDecision:
    rule_id: str
    status: str
    reason: str
    data_gap_fields: tuple[str, ...] = field(default_factory=tuple)
    matched_keywords: tuple[str, ...] = field(default_factory=tuple)

    def to_metadata(self) -> dict[str, Any]:
        return {
            "trigger_gate_status": self.status,
            "trigger_gate_reason": self.reason,
            "data_gap_fields": list(self.data_gap_fields),
            "trigger_gate_matched_keywords": list(self.matched_keywords),
        }


_FAMILY_KEYWORDS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "surgery",
        ("手术", "术前", "术后", "安全核查", "麻醉", "切口", "术者", "手术操作"),
        ("手术记录", "手术名称", "术前讨论", "术前小结", "麻醉记录", "安全核查", "切口", "术后"),
    ),
    (
        "transfusion",
        ("输血", "血制品", "红细胞", "血浆", "血小板"),
        ("输血", "红细胞", "血浆", "血小板", "交叉配血", "输血记录", "输血申请"),
    ),
    (
        "consultation",
        ("会诊",),
        ("会诊记录", "会诊申请", "会诊意见", "会诊目的"),
    ),
    (
        "rescue",
        ("抢救",),
        ("抢救", "抢救记录", "抢救结束"),
    ),
    (
        "critical",
        ("病危", "病重", "危重"),
        ("病危", "病重", "危重", "病危医嘱", "病重医嘱"),
    ),
    (
        "imaging",
        ("CT", "MRI", "影像", "检查结果", "阳性结果"),
        ("CT", "MRI", "磁共振", "影像", "检查报告", "报告时间"),
    ),
    (
        "culture",
        ("细菌培养", "培养", "药敏", "阳性菌"),
        ("培养", "药敏", "阳性菌", "细菌"),
    ),
    (
        "pathology_tumor",
        ("病理", "恶性肿瘤", "肿瘤", "化疗", "癌"),
        ("病理", "肿瘤", "癌", "化疗", "淋巴结"),
    ),
)

_STRUCTURED_DEPENDENCY_MARKERS = (
    "医嘱",
    "费用",
    "收费",
    "报告时间",
    "检查时间",
    "培养结果",
    "手术时间",
    "麻醉记录",
    "输血记录",
)


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple, set)):
        return "\n".join(_norm_text(item) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(str(key))
            parts.append(_norm_text(item))
        return "\n".join(parts)
    return str(value)


def _rule_text(rule: dict[str, Any]) -> str:
    fields = [
        rule.get("rule_id"),
        rule.get("rule_name"),
        rule.get("name"),
        rule.get("description"),
        rule.get("trigger_condition"),
        rule.get("non_trigger_condition"),
        rule.get("dependency_type"),
        rule.get("data_status"),
        rule.get("applicable_documents"),
        rule.get("applicable_document_labels"),
        rule.get("data_dependencies"),
    ]
    return "\n".join(_norm_text(item) for item in fields if item is not None)


def _find_family(rule: dict[str, Any]) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    text = _rule_text(rule)
    for family, rule_markers, record_markers in _FAMILY_KEYWORDS:
        if any(marker in text for marker in rule_markers):
            return family, rule_markers, record_markers
    return None


def _find_keywords(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(keyword for keyword in keywords if keyword and keyword in text)


_NEGATED_TRIGGER_PHRASES: dict[str, tuple[str, ...]] = {
    "surgery": ("未行手术", "未做手术", "无手术", "未手术", "无需手术", "未予手术治疗"),
    "transfusion": ("未输血", "无输血", "未行输血", "未予输血", "未输注", "无需输血"),
    "consultation": ("未请会诊", "无会诊", "未会诊", "无需会诊", "未申请会诊"),
    "rescue": ("未抢救", "无抢救", "未行抢救", "无需抢救"),
    "critical": ("未下达病危医嘱", "无病危医嘱", "未下达病重医嘱", "无病重医嘱", "未下达病危", "未下达病重"),
    "imaging": ("未行CT", "未做CT", "无CT检查", "未行MRI", "未做MRI", "无MRI检查", "未行磁共振", "未做磁共振"),
    "culture": ("未送培养", "未做培养", "无培养", "未行细菌培养", "未见培养报告"),
    "pathology_tumor": ("未做病理", "无病理", "未行病理", "未化疗", "无化疗", "未行化疗"),
}


def _keyword_has_positive_context(text: str, keyword: str, negated_phrases: tuple[str, ...]) -> bool:
    if not keyword:
        return False
    start = 0
    while True:
        position = text.find(keyword, start)
        if position < 0:
            return False
        window = text[max(0, position - 10): position + len(keyword) + 10]
        if not any(phrase in window for phrase in negated_phrases):
            return True
        start = position + len(keyword)


def _find_positive_keywords(text: str, keywords: tuple[str, ...], family_name: str) -> tuple[str, ...]:
    negated_phrases = _NEGATED_TRIGGER_PHRASES.get(family_name, ())
    if not negated_phrases:
        return _find_keywords(text, keywords)
    return tuple(
        keyword
        for keyword in keywords
        if _keyword_has_positive_context(text, keyword, negated_phrases)
    )


def evaluate_luxian_0609_trigger_gates(
    *,
    rules: list[dict[str, Any]],
    visit_id: str = "",
    medical_text: str = "",
    evidence_payload: dict[str, Any] | None = None,
) -> dict[str, Luxian0609GateDecision]:
    """Return conservative trigger-gate decisions for Luxian 0609 customer rules.

    The gate is intentionally conservative: if a trigger cannot be ruled out from
    available text/bundle evidence, it returns ``unknown`` and lets the normal
    execution path decide. Only clear absence of a trigger produces
    ``absent``/``not_applicable``.
    """

    del visit_id  # reserved for future structured loaders; do not special-case visits.
    record_text = "\n".join(
        part for part in (_norm_text(medical_text), _norm_text(evidence_payload or {})) if part.strip()
    )
    decisions: dict[str, Luxian0609GateDecision] = {}

    for rule in rules:
        rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
        if not rule_id:
            continue
        family = _find_family(rule)
        data_dependencies = tuple(
            str(item).strip()
            for item in list(rule.get("data_dependencies") or [])
            if str(item).strip()
        )
        if family is None:
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_UNKNOWN,
                reason="未识别到可安全门控的触发族，进入常规执行",
            )
            continue

        family_name, _rule_markers, record_markers = family
        matched = _find_positive_keywords(record_text, record_markers, family_name)
        if not matched:
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_ABSENT,
                reason=f"病历文本和证据中未发现{family_name}相关触发事实",
            )
            continue

        gap_fields = tuple(
            dep
            for dep in data_dependencies
            if any(marker in dep for marker in _STRUCTURED_DEPENDENCY_MARKERS)
            and dep not in record_text
        )
        if gap_fields and any(marker in _rule_text(rule) for marker in ("跨表联查", "医嘱", "费用", "报告时间")):
            decisions[rule_id] = Luxian0609GateDecision(
                rule_id=rule_id,
                status=TRIGGER_DATA_GAP,
                reason="已发现触发事实，但缺少完成判定所需的结构化字段",
                data_gap_fields=gap_fields,
                matched_keywords=matched,
            )
            continue

        decisions[rule_id] = Luxian0609GateDecision(
            rule_id=rule_id,
            status=TRIGGER_PRESENT,
            reason="已发现相关触发事实，进入常规执行",
            matched_keywords=matched,
        )
    return decisions


def decision_to_result(rule: dict[str, Any], decision: Luxian0609GateDecision) -> dict[str, Any] | None:
    status = decision.status if decision.status in _KNOWN_STATUSES else TRIGGER_UNKNOWN
    if status not in {TRIGGER_ABSENT, TRIGGER_DATA_GAP}:
        return None

    rule_id = str(rule.get("rule_id") or rule.get("rule_code") or decision.rule_id).strip().upper()
    rule_name = str(rule.get("name") or rule.get("rule_name") or rule_id)
    if status == TRIGGER_ABSENT:
        result_status = "not_applicable"
        findings = "未发现该质控点所需触发事件，本次判定为不适用。"
        suggestion = "无需整改；如病历存在相关事件，请补充结构化文书或医嘱后重新质控。"
        confidence = 0.88
    else:
        result_status = "data_gap"
        fields = "、".join(decision.data_gap_fields) or "必要结构化字段"
        findings = f"已发现触发事件，但缺少 {fields}，无法完成自动判定。"
        suggestion = f"请补齐 {fields} 后重新执行质控，或由质控员人工复核。"
        confidence = 0.72

    evidence = "\n".join(
        item
        for item in [
            f"触发门控：{decision.reason}",
            f"匹配关键词：{'、'.join(decision.matched_keywords) if decision.matched_keywords else '无'}",
            f"数据缺口：{'、'.join(decision.data_gap_fields) if decision.data_gap_fields else '无'}",
        ]
        if item
    )
    return {
        "rule_id": rule_id,
        "rule_code": rule_id,
        "rule_name": rule_name,
        "status": result_status,
        "is_compliant": result_status == "not_applicable",
        "findings": findings,
        "evidence": evidence,
        "suggestion": suggestion,
        "confidence": confidence,
        "metadata": {
            **decision.to_metadata(),
            "executor_type": "program",
            "aggregation_source": "trigger_gate",
        },
    }


def filter_executable_rules_by_gate(
    *,
    executable_rules: list[dict[str, Any]],
    wrapper_rules: list[dict[str, Any]],
    decisions: dict[str, Luxian0609GateDecision],
) -> list[dict[str, Any]]:
    """Skip executable rules only when every mapped customer rule is terminal."""

    rule_to_wrappers: dict[str, list[str]] = {}
    for wrapper in wrapper_rules:
        wrapper_id = str(wrapper.get("rule_id") or "").strip().upper()
        for mapped_rule_id in list(wrapper.get("mapped_rule_ids") or []):
            key = str(mapped_rule_id or "").strip().upper()
            if key and wrapper_id:
                rule_to_wrappers.setdefault(key, []).append(wrapper_id)

    filtered: list[dict[str, Any]] = []
    for rule in executable_rules:
        rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip().upper()
        wrapper_ids = rule_to_wrappers.get(rule_id) or []
        if not wrapper_ids:
            filtered.append(rule)
            continue
        terminal_count = 0
        for wrapper_id in wrapper_ids:
            decision = decisions.get(wrapper_id)
            if decision and decision.status in {TRIGGER_ABSENT, TRIGGER_DATA_GAP}:
                terminal_count += 1
        if terminal_count == len(wrapper_ids):
            continue
        filtered.append(rule)
    return filtered
