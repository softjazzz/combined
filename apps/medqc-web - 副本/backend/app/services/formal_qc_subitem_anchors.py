from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


FORMAL_P0_SUBITEM_ANCHOR_IDS = (
    "SC-009-trauma-location",
    "SC-036-abnormal-result-unaddressed",
    "SC-070-consultation-not-implemented",
)

_ANCHOR_DEFINITIONS: dict[str, dict[str, str]] = {
    "SC-009-trauma-location": {
        "parent_rule_id": "SC-009",
        "subitem_name": "外伤现病史地点/场景/致伤机制完整性",
    },
    "SC-036-abnormal-result-unaddressed": {
        "parent_rule_id": "SC-036",
        "subitem_name": "异常检查检验结果后续病程分析处理",
    },
    "SC-070-consultation-not-implemented": {
        "parent_rule_id": "SC-070",
        "subitem_name": "会诊意见落实与医嘱/执行闭环",
    },
}

_ADMISSION_TABLES = {"admission_record"}
_COURSE_TABLES = {"daily_course_record", "senior_course_record", "first_course_record", "postsurg_firstcourse_record"}
_ABNORMAL_TABLES = {
    "exam_attention_report",
    "lab_attention_report",
    "exam_item_report",
    "labtest_item_report",
    "pathology_exam_report",
    "crisis_value_record",
}
_CONSULTATION_TABLES = {"consultation_record"}
_ORDER_EXECUTION_TABLES = {"inpat_drug_order", "inpat_nondrug_order", "inpat_execution_record", "inpat_bill_item"}

_TRAUMA_TRIGGER_KEYWORDS = ("外伤", "摔伤", "跌倒", "车祸", "扭伤", "砸伤", "剪伤", "刺伤", "切割伤", "撞伤", "坠落", "损伤")
_TRAUMA_MECHANISM_PATTERNS = (
    r"被[^，。；;]{0,18}(砸|撞|压|剪|刺|切)",
    r"(摔|跌|扭|砸|剪|刺|撞|坠|车祸|损伤)",
)
_POST_INJURY_KEYWORDS = ("院外", "急诊", "处理", "未予", "就诊", "送入", "送至", "转入", "包扎", "清创")

_ABNORMAL_KEYWORDS = (
    "异常",
    "阳性",
    "低钾",
    "高钾",
    "升高",
    "降低",
    "感染",
    "结节",
    "占位",
    "骨折",
    "梗死",
    "积液",
    "狭窄",
    "肿瘤",
    "癌",
    "偏高",
    "偏低",
)
_COURSE_RESPONSE_KEYWORDS = ("分析", "处理", "复查", "会诊", "诊断", "治疗", "调整", "继续", "建议")
_CONSULTATION_KEYWORDS = ("会诊", "建议", "意见", "遵", "执行", "治疗", "处理", "康复", "复查")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _contains_any(text: str, keywords: tuple[str, ...] | list[str] | set[str]) -> bool:
    return any(keyword and keyword in text for keyword in keywords)


def _row_text(row: dict[str, Any]) -> str:
    preferred = (
        "content",
        "record_content",
        "assembled_text",
        "medical_text",
        "history_of_present_illness",
        "chief_complaint",
        "checkup",
        "assist_exam",
        "exam_result",
        "exam_impression",
        "exam_conclusion",
        "result",
        "finding",
        "diagnosis",
        "consultation_opinion",
        "consultation_advice",
        "order_name",
        "item_name",
        "course_content",
        "record_text",
        "note",
    )
    parts = [_safe_text(row.get(name)) for name in preferred if _safe_text(row.get(name))]
    if parts:
        return " ".join(dict.fromkeys(parts))
    fallback: list[str] = []
    for key, value in row.items():
        if key.startswith("_"):
            continue
        text = _safe_text(value)
        if len(text) >= 2:
            fallback.append(f"{key}:{text}")
    return " ".join(fallback)


def _documents_by_table(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    structured = bundle.get("structured_context") if isinstance(bundle.get("structured_context"), dict) else {}
    documents = structured.get("documents") if isinstance(structured, dict) else {}
    if isinstance(documents, dict):
        for table_name, rows in documents.items():
            if isinstance(rows, list):
                grouped[str(table_name)].extend([dict(row) for row in rows if isinstance(row, dict)])
    for item in list(bundle.get("source_documents") or []):
        if not isinstance(item, dict):
            continue
        table_name = _safe_text(item.get("source_table") or item.get("table_name") or item.get("document_type"))
        if table_name:
            grouped[table_name].append(dict(item))
    return dict(grouped)


def _snippets(grouped: dict[str, list[dict[str, Any]]], tables: set[str], keywords: tuple[str, ...], *, max_items: int = 3) -> list[str]:
    snippets: list[str] = []
    for table_name in tables:
        for row in grouped.get(table_name, []):
            text = re.sub(r"\s+", " ", _row_text(row)).strip()
            if not text:
                continue
            if keywords and not _contains_any(text, keywords):
                continue
            snippets.append(f"[{table_name}] {text[:260]}")
            if len(snippets) >= max_items:
                return snippets
    return snippets


def _is_abnormal_row(row: dict[str, Any], text: str) -> bool:
    flag_fields = ("abnormal_flag", "abnormal", "result_flag", "flag", "is_abnormal", "critical_flag")
    for field_name in flag_fields:
        value = _safe_text(row.get(field_name)).upper()
        if value in {"H", "L", "HH", "LL", "+", "++", "+++", "++++", "TRUE", "1", "Y", "YES"}:
            return True
        if _contains_any(value, ("异常", "阳性", "偏高", "偏低")):
            return True
    return _contains_any(text, _ABNORMAL_KEYWORDS)


def _abnormal_snippets(grouped: dict[str, list[dict[str, Any]]], *, max_items: int = 4) -> list[str]:
    snippets: list[str] = []
    for table_name in _ABNORMAL_TABLES:
        for row in grouped.get(table_name, []):
            text = re.sub(r"\s+", " ", _row_text(row)).strip()
            if not text or not _is_abnormal_row(row, text):
                continue
            snippets.append(f"[{table_name}] {text[:260]}")
            if len(snippets) >= max_items:
                return snippets
    return snippets


def _trauma_event_sentences(text: str) -> list[str]:
    sentences = [part.strip() for part in re.split(r"[。；;\n]", text) if part.strip()]
    return [sentence for sentence in sentences if _contains_any(sentence, _TRAUMA_TRIGGER_KEYWORDS)]


def _has_trauma_scene_expression(sentence: str) -> bool:
    normalized = re.sub(r"\s+", "", sentence)
    post_treatment_noise = ("院外未做处理", "院外未予处理", "院外未特殊处理", "急诊入院", "急诊入我科", "送入我院", "送至我院")
    for noise in post_treatment_noise:
        normalized = normalized.replace(noise, "")
    scene_patterns = (
        r"(?:在|于|从)[^，。；;]{1,28}(?:时|处|中|上|下|旁|内|外|被|摔|跌|扭|砸|剪|刺|撞|坠|损伤)",
        r"[^，。；;]{1,18}(?:工作|劳动|过路|行走|骑车|乘车|搬运|施工|干活|下楼|上楼)时",
    )
    return any(re.search(pattern, normalized) for pattern in scene_patterns)


def _build_anchor_result(
    *,
    parent_rule_id: str,
    anchor_id: str,
    subitem_name: str,
    evidence_status: str,
    evidence: str,
    decision_reason: str,
    display_status: str = "needs_review",
) -> dict[str, Any]:
    postprocess_label = "data_gap_not_defect" if display_status == "data_quality_gap" else "needs_human_review"
    return {
        "rule_id": parent_rule_id,
        "parent_rule_id": parent_rule_id,
        "anchor_id": anchor_id,
        "subitem_id": anchor_id,
        "subitem_name": subitem_name,
        "status": "uncertain",
        "findings": decision_reason,
        "evidence": evidence,
        "suggestion": "请人工复核该父规则子锚点，确认当前病历是否仍存在对应缺陷。",
        "confidence": 0.0,
        "anchor_evidence_status": evidence_status,
        "anchor_evidence": evidence,
        "anchor_decision_reason": decision_reason,
        "display_status": display_status,
        "display_bucket": "数据缺口" if display_status == "data_quality_gap" else "待复核",
        "postprocess_label": postprocess_label,
        "postprocess_reason": "正式质控子锚点默认不进入确认缺陷，仅作为待复核候选。" if display_status != "data_quality_gap" else "缺少执行/对照证据，不能作为医生病历缺陷。",
        "evidence_problem_type": "formal_subitem_anchor",
        "can_show_as_defect": False,
        "can_show_to_doctor": True,
        "internal_only": False,
        "metadata": {
            "formal_subitem_anchor": True,
            "parent_rule_id": parent_rule_id,
            "anchor_id": anchor_id,
            "subitem_id": anchor_id,
            "subitem_name": subitem_name,
            "anchor_evidence_status": evidence_status,
        },
    }


def _evaluate_sc009_trauma_location(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    snippets = _snippets(grouped, _ADMISSION_TABLES, _TRAUMA_TRIGGER_KEYWORDS, max_items=2)
    if not snippets:
        return []
    text = " ".join(snippets)
    event_sentences = _trauma_event_sentences(text) or [text]
    has_location = any(_has_trauma_scene_expression(sentence) for sentence in event_sentences)
    has_mechanism = any(re.search(pattern, sentence) for sentence in event_sentences for pattern in _TRAUMA_MECHANISM_PATTERNS)
    has_post_treatment = _contains_any(text, _POST_INJURY_KEYWORDS)
    missing = []
    if not has_location:
        missing.append("受伤地点/场景")
    if not has_mechanism:
        missing.append("致伤机制")
    if not has_post_treatment:
        missing.append("伤后处理")
    if not missing:
        return []
    definition = _ANCHOR_DEFINITIONS["SC-009-trauma-location"]
    return [
        _build_anchor_result(
            parent_rule_id=definition["parent_rule_id"],
            anchor_id="SC-009-trauma-location",
            subitem_name=definition["subitem_name"],
            evidence_status="potential_missing_trauma_context",
            evidence="\n".join(snippets),
            decision_reason=f"外伤现病史触发，但疑似缺少：{'、'.join(missing)}；仅生成待复核子锚点。",
        )
    ]


def _evaluate_sc036_abnormal_result_unaddressed(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    abnormal = _abnormal_snippets(grouped, max_items=4)
    if not abnormal:
        return []
    course = _snippets(grouped, _COURSE_TABLES, _COURSE_RESPONSE_KEYWORDS, max_items=4)
    definition = _ANCHOR_DEFINITIONS["SC-036-abnormal-result-unaddressed"]
    if not course:
        return [
            _build_anchor_result(
                parent_rule_id=definition["parent_rule_id"],
                anchor_id="SC-036-abnormal-result-unaddressed",
                subitem_name=definition["subitem_name"],
                evidence_status="missing_course_followup_evidence",
                evidence="\n".join(abnormal),
                decision_reason="找到异常检查/检验/病理证据，但缺少后续病程对照，不能确认缺陷。",
            )
        ]
    return [
        _build_anchor_result(
            parent_rule_id=definition["parent_rule_id"],
            anchor_id="SC-036-abnormal-result-unaddressed",
            subitem_name=definition["subitem_name"],
            evidence_status="abnormal_and_course_evidence_needs_review",
            evidence="\n".join([*abnormal, *course]),
            decision_reason="找到异常结果和后续病程片段，但是否未分析处理需人工复核完整时序。",
        )
    ]


def _evaluate_sc070_consultation_not_implemented(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    consultation = _snippets(grouped, _CONSULTATION_TABLES, _CONSULTATION_KEYWORDS, max_items=4)
    if not consultation:
        return []
    execution = _snippets(grouped, _ORDER_EXECUTION_TABLES | _COURSE_TABLES, _CONSULTATION_KEYWORDS, max_items=4)
    definition = _ANCHOR_DEFINITIONS["SC-070-consultation-not-implemented"]
    if not execution:
        return [
            _build_anchor_result(
                parent_rule_id=definition["parent_rule_id"],
                anchor_id="SC-070-consultation-not-implemented",
                subitem_name=definition["subitem_name"],
                evidence_status="missing_execution_evidence",
                evidence="\n".join(consultation),
                decision_reason="找到会诊意见，但缺少医嘱/执行清单或病程落实对照，不能确认缺陷。",
                display_status="data_quality_gap",
            )
        ]
    return [
        _build_anchor_result(
            parent_rule_id=definition["parent_rule_id"],
            anchor_id="SC-070-consultation-not-implemented",
            subitem_name=definition["subitem_name"],
            evidence_status="consultation_and_execution_evidence_needs_review",
            evidence="\n".join([*consultation, *execution]),
            decision_reason="找到会诊意见及执行/病程相关片段，是否未落实需人工核对医嘱闭环。",
        )
    ]


def evaluate_formal_qc_p0_subitem_anchors(
    *,
    results: list[dict[str, Any]] | None = None,
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate conservative P0 subitem anchors for formal final fast_screen.

    The function never upgrades a parent rule to confirmed_defect. It only returns
    needs_review/data_quality_gap candidates with explicit parent_rule_id/anchor_id.
    """
    grouped = _documents_by_table(bundle or {})
    anchor_results: list[dict[str, Any]] = []
    anchor_results.extend(_evaluate_sc009_trauma_location(grouped))
    anchor_results.extend(_evaluate_sc036_abnormal_result_unaddressed(grouped))
    anchor_results.extend(_evaluate_sc070_consultation_not_implemented(grouped))
    return anchor_results


def attach_subitem_anchors_to_parent_results(
    results: list[dict[str, Any]],
    anchor_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for anchor in anchor_results:
        parent_rule_id = _safe_text(anchor.get("parent_rule_id") or anchor.get("rule_id")).upper()
        if parent_rule_id:
            by_parent[parent_rule_id].append(anchor)
    next_results: list[dict[str, Any]] = []
    for item in results:
        row = dict(item)
        rule_id = _safe_text(row.get("rule_id")).upper()
        anchors = by_parent.get(rule_id) or []
        if anchors:
            metadata = row.setdefault("metadata", {})
            if isinstance(metadata, dict):
                metadata["subitem_anchors"] = [
                    {
                        "anchor_id": anchor.get("anchor_id"),
                        "subitem_id": anchor.get("subitem_id"),
                        "subitem_name": anchor.get("subitem_name"),
                        "anchor_evidence_status": anchor.get("anchor_evidence_status"),
                        "anchor_decision_reason": anchor.get("anchor_decision_reason"),
                    }
                    for anchor in anchors
                ]
                metadata["subitem_anchor_count"] = len(anchors)
        next_results.append(row)
    return next_results
