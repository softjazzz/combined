from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any, Mapping

from .copy_content_similarity import compare_text_segments, split_sentences
from .luxian_0609_evidence_formatter import format_luxian_0609_evidence
from .luxian_0609_result_schema import apply_luxian_0609_result_schema
from .luxian_0609.decision_reducer import ReducedRuleDecision
from .luxian_0609_trigger_gate import (
    Luxian0609GateDecision,
    TRIGGER_ABSENT,
    TRIGGER_DATA_GAP,
    decision_to_result,
    _has_antibiotic_order_context,
    _has_level_4_surgery_context,
    _has_lx0609_024_malignant_tumor_surgery_context,
    _has_lx0609_028_class_i_ii_incision_context,
    _missing_lx0609_028_antibiotic_time_fields,
)

if TYPE_CHECKING:
    from .luxian_0609.customer_renderer import SafeTraceSink as DecisionTraceSink


_STATUS_PRIORITY = {
    "non_compliant": 50,
    "ai_suggested_non_compliant": 48,
    "data_gap": 45,
    "uncertain": 40,
    "ai_suggested_compliant": 25,
    "compliant": 20,
    "not_applicable": 10,
    "not_executed": 5,
    "technical_error": 60,
}

CANONICAL_RESULT_STATUSES = (
    "non_compliant",
    "ai_suggested_non_compliant",
    "compliant",
    "ai_suggested_compliant",
    "not_applicable",
    "data_gap",
    "uncertain",
    "not_executed",
    "technical_error",
)

_SENSITIVE_KEYS = {
    "raw_response",
    "raw_output",
    "llm_raw_output",
    "prompt",
    "embedding",
    "medical_text",
    "documents",
    "bundle",
    "record_content",
    "internal_data",
}
_SAFE_SOURCE_TYPE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
# 001 的 RuleDecision 会为“入院锚点可用性”绑定入院记录、出院记录及登记来源。
# 其中只有入院记录是客户需要核对的实际时限文书；其余来源仅用于计算锚点，
# 不得因通用事实反查而出现在该规则的客户证据中。
_EXACT_CUSTOMER_EVIDENCE_SOURCES_BY_RULE: dict[str, frozenset[str]] = {
    "LX0609-001": frozenset({"admission_record"}),
    # 005/006 的入院、出院来源仅用于确定入院锚点；实际被核对的首次查房
    # 均来自上级医师查房记录，不能把锚点文书投影成客户证据。
    "LX0609-005": frozenset({"senior_course_record"}),
    "LX0609-006": frozenset({"senior_course_record"}),
}


def _norm_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _confidence(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").strip().lower()
    if status in CANONICAL_RESULT_STATUSES:
        return status
    if status in {"technical_error_internal", "error"}:
        return "technical_error"
    if status in {"skipped", "unsupported"}:
        return "not_executed"
    return "compliant" if item.get("is_compliant") is True else "non_compliant"


def _strip_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_sensitive(item)
            for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_strip_sensitive(item) for item in value]
    return value


def _timeline_from_audit(audit_context: dict[str, Any] | None) -> dict[str, Any]:
    context = dict(audit_context or {})
    timeline = context.get("programmatic_timeline")
    if isinstance(timeline, dict):
        return timeline
    payload = context.get("evidence_payload")
    if isinstance(payload, dict) and isinstance(payload.get("programmatic_timeline"), dict):
        return dict(payload["programmatic_timeline"])
    return {}


def _has_explicit_source_coverage(
    audit_context: dict[str, Any] | None,
    source_key: str,
) -> bool:
    """仅接受快照或 bundle 明确声明的来源覆盖，缺失不能当作空来源。"""

    snapshot = dict(audit_context or {}).get("evidence_snapshot")
    observations = getattr(snapshot, "observations", ())
    for observation in observations if isinstance(observations, (tuple, list)) else ():
        if str(getattr(observation, "source_key", "") or "") != source_key:
            continue
        query_state = str(getattr(getattr(observation, "query_state", None), "value", "") or "")
        completeness = str(getattr(getattr(observation, "completeness", None), "value", "") or "")
        return query_state in {"available", "empty"} and completeness == "complete"

    coverage = _timeline_from_audit(audit_context).get("source_table_coverage")
    return bool(
        isinstance(coverage, dict)
        and isinstance(coverage.get(source_key), dict)
    )


def _doc_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(key) or "").strip()
        for key in ("case_characteristic", "content", "raw_text", "content_preview")
        if str(item.get(key) or "").strip()
    )


def _has_first_course_content(audit_context: dict[str, Any] | None) -> bool:
    timeline = _timeline_from_audit(audit_context)
    docs = timeline.get("documents")
    if not isinstance(docs, dict):
        return True
    first_courses = [item for item in list(docs.get("first_course_record") or []) if isinstance(item, dict)]
    if not first_courses:
        return False
    for item in first_courses:
        text = _doc_text(dict(item))
        normalized = "".join(text.split())
        if normalized and normalized not in {"首次病程记录", "首次病程"} and len(normalized) >= 20:
            return True
    return False


def _compact_quote(value: Any, *, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _copy_document_label(source_table: Any, fallback: Any) -> str:
    source = str(source_table or "").strip()
    mapping = {
        "daily_course_record": "日常病程记录",
        "senior_course_record": "上级医师查房记录",
        "first_course_record": "首次病程记录",
        "admission_record": "入院记录",
    }
    return mapping.get(source, str(fallback or source or "病程记录"))


def _copy_compare_documents(audit_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    timeline = _timeline_from_audit(audit_context)
    docs = timeline.get("documents")
    if not isinstance(docs, dict):
        return []
    source_tables = ("daily_course_record", "senior_course_record")
    candidates: list[dict[str, Any]] = []
    for source_table in source_tables:
        for item in list(docs.get(source_table) or []):
            if not isinstance(item, dict):
                continue
            content = _doc_text(dict(item))
            normalized = "".join(content.split())
            if len(normalized) < 80:
                continue
            candidates.append(
                {
                    "source_table": source_table,
                    "document_id": str(item.get("document_id") or ""),
                    "document_title": str(item.get("document_title") or source_table),
                    "display_time": str(
                        item.get("display_time")
                        or item.get("record_time")
                        or item.get("submit_datetime")
                        or item.get("update_time")
                        or ""
                    ),
                    "content": content,
                }
            )
    candidates.sort(key=lambda item: (str(item.get("display_time") or ""), str(item.get("document_id") or "")))
    return candidates


def _best_copy_sentence_pairs(
    previous_text: str,
    current_text: str,
    *,
    threshold: float = 0.7,
    max_pairs: int = 3,
) -> list[dict[str, Any]]:
    previous_sentences = split_sentences(previous_text)
    current_sentences = split_sentences(current_text)
    candidates: list[dict[str, Any]] = []
    for previous_sentence in previous_sentences:
        previous_normalized = "".join(str(previous_sentence or "").split())
        if len(previous_normalized) < 12:
            continue
        for current_sentence in current_sentences:
            current_normalized = "".join(str(current_sentence or "").split())
            if len(current_normalized) < 12:
                continue
            ratio = SequenceMatcher(None, previous_sentence, current_sentence).ratio()
            if ratio < threshold:
                continue
            candidates.append(
                {
                    "previous_sentence": previous_sentence,
                    "current_sentence": current_sentence,
                    "previous_normalized": previous_normalized,
                    "current_normalized": current_normalized,
                    "similarity": ratio,
                }
            )
    selected: list[dict[str, Any]] = []
    used_previous: set[str] = set()
    used_current: set[str] = set()
    for candidate in sorted(candidates, key=lambda item: float(item.get("similarity") or 0.0), reverse=True):
        previous_key = str(candidate.get("previous_normalized") or "")
        current_key = str(candidate.get("current_normalized") or "")
        if previous_key in used_previous or current_key in used_current:
            continue
        selected.append(
            {
                "previous_quote": _compact_quote(candidate.get("previous_sentence"), limit=220),
                "current_quote": _compact_quote(candidate.get("current_sentence"), limit=220),
                "similarity": round(float(candidate.get("similarity") or 0.0), 4),
            }
        )
        used_previous.add(previous_key)
        used_current.add(current_key)
        if len(selected) >= max_pairs:
            break
    if selected:
        return selected
    return [
        {
            "previous_quote": _compact_quote(previous_text),
            "current_quote": _compact_quote(current_text),
            "similarity": 0.0,
        }
    ]


def _best_copy_sentence_pair(previous_text: str, current_text: str) -> tuple[str, str]:
    pairs = _best_copy_sentence_pairs(previous_text, current_text, max_pairs=1)
    if pairs:
        return (
            str(pairs[0].get("previous_quote") or ""),
            str(pairs[0].get("current_quote") or ""),
        )
    return (_compact_quote(previous_text), _compact_quote(current_text))


def _best_copy_compare_evidence(audit_context: dict[str, Any] | None) -> dict[str, Any] | None:
    documents = _copy_compare_documents(audit_context)
    if len(documents) < 2:
        return None
    best: dict[str, Any] | None = None
    for index, current in enumerate(documents[1:], start=1):
        current_text = str(current.get("content") or "")
        for previous in documents[:index]:
            previous_text = str(previous.get("content") or "")
            metrics = compare_text_segments(previous_text, current_text)
            later_cover = float(metrics.target_to_source_sentence_coverage or 0.0)
            similarity_ratio = float(metrics.full_similarity_ratio or 0.0)
            score = max(similarity_ratio, later_cover)
            if best is None or score > float(best.get("score") or 0.0):
                quote_pairs = _best_copy_sentence_pairs(previous_text, current_text)
                previous_quote = str(quote_pairs[0].get("previous_quote") or "") if quote_pairs else ""
                current_quote = str(quote_pairs[0].get("current_quote") or "") if quote_pairs else ""
                best = {
                    "score": score,
                    "similarity_ratio": similarity_ratio,
                    "later_cover": later_cover,
                    "previous": previous,
                    "current": current,
                    "previous_quote": previous_quote,
                    "current_quote": current_quote,
                    "quote_pairs": quote_pairs,
                }
    if not best:
        return None
    if float(best.get("similarity_ratio") or 0.0) < 0.9 and float(best.get("later_cover") or 0.0) < 0.8:
        return None
    return best


def _apply_copy_compare_evidence_for_lx017(
    *,
    wrapper_id: str,
    selected: dict[str, Any],
    audit_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if wrapper_id != "LX0609-017":
        return selected
    compare = _best_copy_compare_evidence(audit_context)
    if not compare:
        return selected
    previous = dict(compare.get("previous") or {})
    current = dict(compare.get("current") or {})
    similarity_ratio = float(compare.get("similarity_ratio") or 0.0)
    later_cover = float(compare.get("later_cover") or 0.0)
    metadata = dict(selected.get("metadata") or {})
    metadata["customer_display_guard"] = "copy_compare_evidence"
    metadata["copy_similarity_ratio"] = round(similarity_ratio, 4)
    metadata["copy_later_cover"] = round(later_cover, 4)
    quote_pairs = [
        dict(item)
        for item in list(compare.get("quote_pairs") or [])
        if isinstance(item, dict)
    ]
    previous_label = _copy_document_label(
        previous.get("source_table"),
        previous.get("document_title") or "前次病程/查房记录",
    )
    current_label = _copy_document_label(
        current.get("source_table"),
        current.get("document_title") or "本次病程/查房记录",
    )
    evidence_items: list[dict[str, Any]] = [
        {
            "evidence_id": "COPY-PREVIOUS",
            "evidence_role": "source_previous_snippet",
            "source_table": str(previous.get("source_table") or ""),
            "source_document_type": "前次病程/查房记录",
            "source_document_name": previous_label,
            "source_document_id": str(previous.get("document_id") or ""),
            "record_time": str(previous.get("display_time") or ""),
            "field_path": "前次病程/查房片段",
            "source_field": "正文片段",
            "quote": str(compare.get("previous_quote") or ""),
        },
        {
            "evidence_id": "COPY-CURRENT",
            "evidence_role": "target_current_snippet",
            "source_table": str(current.get("source_table") or ""),
            "source_document_type": "本次病程/查房记录",
            "source_document_name": current_label,
            "source_document_id": str(current.get("document_id") or ""),
            "record_time": str(current.get("display_time") or ""),
            "field_path": "本次病程/查房片段",
            "source_field": "正文片段",
            "quote": str(compare.get("current_quote") or ""),
        },
    ]
    for index, pair in enumerate(quote_pairs[:3], start=1):
        pair_similarity = float(pair.get("similarity") or 0.0)
        evidence_items.extend(
            [
                {
                    "evidence_id": f"COPY-PAIR-{index}-PREVIOUS",
                    "evidence_role": "copy_compare_previous_pair",
                    "source_table": str(previous.get("source_table") or ""),
                    "source_document_type": "前次病程/查房记录",
                    "source_document_name": previous_label,
                    "source_document_id": str(previous.get("document_id") or ""),
                    "record_time": str(previous.get("display_time") or ""),
                    "field_path": f"前次记录重复片段 {index}",
                    "source_field": f"重复片段 {index}",
                    "quote": str(pair.get("previous_quote") or ""),
                    "actual_value": f"片段相似度 {pair_similarity:.2f}",
                },
                {
                    "evidence_id": f"COPY-PAIR-{index}-CURRENT",
                    "evidence_role": "copy_compare_current_pair",
                    "source_table": str(current.get("source_table") or ""),
                    "source_document_type": "本次病程/查房记录",
                    "source_document_name": current_label,
                    "source_document_id": str(current.get("document_id") or ""),
                    "record_time": str(current.get("display_time") or ""),
                    "field_path": f"本次记录重复片段 {index}",
                    "source_field": f"重复片段 {index}",
                    "quote": str(pair.get("current_quote") or ""),
                    "actual_value": f"片段相似度 {pair_similarity:.2f}",
                },
            ]
        )
    evidence_items.extend(
        [
            {
                "evidence_id": "COPY-MISSING-DIFFERENCE",
                "evidence_role": "copy_missing_difference",
                "source_table": "copy_compare",
                "source_document_type": "差异不足说明",
                "source_document_name": "本次记录新增内容",
                "field_path": "缺少差异说明",
                "source_field": "病情变化/分析/计划",
                "quote": (
                    "未见本次记录相较前次记录补充明确病情变化、诊疗分析或后续计划调整；"
                    "建议质控员确认完整病程原文。"
                ),
            },
            {
                "evidence_id": "COPY-METRIC",
                "evidence_role": "copy_similarity_metric",
                "source_table": "copy_compare",
                "source_document_type": "复制病历比对指标",
                "source_document_name": "相似度与覆盖率",
                "field_path": "重复度判定",
                "source_field": "相似度指标",
                "quote": f"两份病程记录全文相似度 {similarity_ratio:.2f}，本次记录被前次记录覆盖率 {later_cover:.2f}。",
                "threshold": "相似度或覆盖率超过 0.70 需复核",
                "actual_value": f"全文相似度 {similarity_ratio:.2f}；覆盖率 {later_cover:.2f}",
                "delta": round(max(similarity_ratio - 0.7, later_cover - 0.7), 4),
            },
        ]
    )
    patched = dict(selected)
    patched.update(
        {
            "status": "non_compliant",
            "is_compliant": False,
            "findings": (
                "两份病程或查房记录内容高度相似，缺少本次病情变化、分析或诊疗计划的实质差异。"
            ),
            "evidence": (
                f"两份病程记录相似度超过70%。前次记录：{previous.get('document_title') or previous.get('source_table')}；"
                f"本次记录：{current.get('document_title') or current.get('source_table')}；"
                f"全文相似度 {similarity_ratio:.2f}，本次记录被前次记录覆盖率 {later_cover:.2f}。"
            ),
            "suggestion": (
                "请对照两次记录补充本次查房发现、病情变化、诊疗分析和后续计划，避免直接复制既往病程。"
            ),
            "confidence": max(float(selected.get("confidence") or 0.0), 0.88),
            "metadata": metadata,
            "evidence_items": evidence_items,
        }
    )
    return patched


def _guard_copy_rule_without_first_course(
    *,
    wrapper_id: str,
    selected: dict[str, Any],
    audit_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if wrapper_id != "LX0609-016" or _status(selected) != "non_compliant":
        return selected
    display_facts = selected.get("customer_display_facts")
    if (
        isinstance(display_facts, Mapping)
        and display_facts.get("failure_kind")
        == "admission_first_course_copy_detected"
    ):
        return selected
    if _has_first_course_content(audit_context):
        return selected
    guarded = dict(selected)
    metadata = dict(guarded.get("metadata") or {})
    metadata.update(
        {
            "copy_rule_priority_guard": "first_course_missing",
            "data_gap_reason": "首次病程记录缺失或正文为空，无法进行复制病历比对",
        }
    )
    guarded.update(
        {
            "status": "data_gap",
            "is_compliant": False,
            "findings": "首次病程记录缺失或正文为空，无法判断是否存在复制病历内容。",
            "evidence": "数据缺口：首次病程记录正文为空；复制病历比对未执行。",
            "suggestion": "请先补齐首次病程记录正文，再复核是否与入院记录或其他病程存在复制。",
            "metadata": metadata,
        }
    )
    return guarded


def _has_any(text: str, *needles: str) -> bool:
    return any(needle and needle in text for needle in needles)


_PATHOLOGY_OBJECTIVE_POSITIVE_PATTERN = re.compile(
    r"("
    r"(?:送检|送病理|送病检|标本|取材).{0,60}(?:冰冻病理|术中冰冻|病理提示|病理诊断|病理结果|浸润性腺癌|腺癌|癌转移|恶性)"
    r"|(?:冰冻病理|术中冰冻|病理提示|病理诊断|病理结果|浸润性腺癌|腺癌|癌转移|恶性).{0,60}(?:送检|送病理|送病检|标本|取材)"
    r")"
)
_PATHOLOGY_MATERIAL_ABSENCE_PATTERN = re.compile(
    r"("
    r"(?:未记录|未见|缺失|缺少|不完整|仅笼统|未详细|未明确|无记录).{0,24}(?:取材|标本|送检|送病理|送病检|冰冻|术中病理|淋巴结清扫)"
    r"|(?:取材|标本|送检|送病理|送病检|淋巴结清扫).{0,24}(?:未记录|未见|缺失|缺少|不完整|仅笼统|未详细|未明确|无记录)"
    r")"
)
_PATHOLOGY_MATERIAL_HARD_ABSENCE_PATTERN = re.compile(
    r"("
    r"(?:未记录|未见|缺失|缺少|无记录).{0,24}(?:取材|标本|送检|送病理|送病检|冰冻|术中病理|淋巴结清扫)"
    r"|(?:取材|标本|送检|送病理|送病检|淋巴结清扫).{0,24}(?:未记录|未见|缺失|缺少|无记录)"
    r")"
)
_PATHOLOGY_OBJECTIVE_NEGATIVE_CONTEXT_PATTERN = re.compile(
    r"缺(?:少)?病理(?:结果|诊断|来源|报告|对照)|未见病理(?:结果|诊断|报告)|病理(?:结果|诊断|报告)?对照不足"
)
_PATHOLOGY_SPECIMEN_SOURCE_FACT_PATTERN = re.compile(
    r"("
    r"【[^】]*(?:病理|活检|手术记录|病程记录)[^】]*】.{0,180}(?:病理报告|病理诊断|病理结果|活检|送检|送病理|送病检|标本|取材|冰冻病理|术中冰冻|腺癌|鳞癌|癌)"
    r"|(?:病理报告|病理检查|病理诊断|活检|穿刺活检|标本|送检|送病理|送病检|冰冻病理|术中冰冻).{0,120}(?:报告|诊断|提示|组织|阑尾|胃|淋巴|癌|取材|标本)"
    r"|(?:手术记录|术中|手术).{0,80}(?:取材|标本|送检|送病理|送病检|病理)"
    r")"
)
_PATHOLOGY_SIMPLE_SPECIMEN_RECORDED_IN_SURGERY_PATTERN = re.compile(
    r"("
    r"(?:切除|取出).{0,80}(?:阑尾|胆囊).{0,80}(?:送检|送病理|送病检|活检|病理)"
    r"|(?:阑尾|胆囊).{0,80}(?:展示后)?(?:送检|送病理|送病检|活检|病理)"
    r")"
)


def _has_recorded_pathology_material(text: str) -> bool:
    if not text:
        return False
    explicit_positive = _has_any(
        text,
        "已记录术中取材",
        "已记录取材",
        "已记录术中取材及冰冻病理结果",
        "记录了术中冰冻病理结果",
        "记录术中冰冻病理结果",
    )
    objective_positive = bool(_PATHOLOGY_OBJECTIVE_POSITIVE_PATTERN.search(text))
    if objective_positive and _PATHOLOGY_OBJECTIVE_NEGATIVE_CONTEXT_PATTERN.search(text):
        objective_positive = False
    specimen_recorded_in_surgery = bool(_PATHOLOGY_SIMPLE_SPECIMEN_RECORDED_IN_SURGERY_PATTERN.search(text))
    if specimen_recorded_in_surgery:
        return not bool(_PATHOLOGY_MATERIAL_HARD_ABSENCE_PATTERN.search(text))
    if not explicit_positive and not objective_positive and not specimen_recorded_in_surgery:
        return False
    return not bool(_PATHOLOGY_MATERIAL_ABSENCE_PATTERN.search(text))


def _has_pathology_specimen_source_fact(text: str) -> bool:
    if not text:
        return False
    return bool(_PATHOLOGY_SPECIMEN_SOURCE_FACT_PATTERN.search(text))


def _extract_execution_evidence(text: str) -> str:
    marker = "执行证据："
    index = text.find(marker)
    if index < 0:
        return text.strip()
    return text[index + len(marker):].strip()


def _readable_uncertain_evidence(
    text: str,
    fallback: str = "系统未能提取到可直接支撑判定的结构化证据片段。",
) -> str:
    evidence = _extract_execution_evidence(text)
    if _has_any(evidence, "LLM", "非结构化结果", "原始输出", "底层", "映射规则"):
        return fallback
    return evidence or fallback


def _readable_uncertain_findings(wrapper_id: str) -> tuple[str, str, str]:
    if wrapper_id == "LX0609-017":
        return (
            "病程记录重复度未形成可靠自动结论，建议质控员确认。",
            "系统未能提取到可直接比较的两份以上病程记录结构化片段。",
            "请质控员比对两次以上病程记录的主要内容、记录时间和病情变化描述，确认是否存在复制粘贴。",
        )
    return (
        "本质控点未形成可靠自动结论，建议质控员确认。",
        "系统未能提取到可直接支撑判定的结构化证据片段。",
        "请质控员结合来源文书、记录时间和关键字段确认。",
    )


def _readable_copy_uncertain_evidence(audit_context: dict[str, Any] | None) -> str:
    documents = _copy_compare_documents(audit_context)
    if len(documents) < 2:
        return "系统未能提取到可直接比较的两份以上病程记录结构化片段。"

    best_similarity = 0.0
    best_cover = 0.0
    for index, current in enumerate(documents[1:], start=1):
        current_text = str(current.get("content") or "")
        for previous in documents[:index]:
            metrics = compare_text_segments(str(previous.get("content") or ""), current_text)
            best_similarity = max(best_similarity, float(metrics.full_similarity_ratio or 0.0))
            best_cover = max(best_cover, float(metrics.target_to_source_sentence_coverage or 0.0))

    return (
        f"已提取到 {len(documents)} 份可比较的病程/查房记录，但相似度未达到可靠自动判定阈值。"
        f"最高全文相似度 {best_similarity:.2f}，最高后次记录覆盖率 {best_cover:.2f}；"
        "需人工比对是否存在复制粘贴。"
    )


def _consultation_execution_missing(text: str) -> bool:
    return _has_any(
        text,
        "未体现具体执行",
        "未记载具体执行",
        "未记录具体执行",
        "未体现会诊意见的具体执行",
        "未记录执行情况",
        "无请会诊执行记录",
        "执行记录缺失",
        "仅描述",
        "照抄会诊意见",
    )


def _consultation_purpose_issue(text: str) -> bool:
    return _has_any(
        text,
        "会诊目的不明确",
        "目的不明确",
        "未明确会诊目的",
        "缺少会诊目的",
        "会诊目的笼统",
        "会诊目的仅写",
        "申请目的：请会诊",
        "会诊目的：请会诊",
    )


def _consultation_signature_only_issue(text: str) -> bool:
    return "签名" in text and not _consultation_purpose_issue(text)


def _consultation_opinion_quality_issue(text: str) -> bool:
    return _has_any(
        text,
        "会诊意见不明确",
        "会诊意见笼统",
        "意见不明确",
        "意见笼统",
        "缺少具体意见",
        "缺少针对性意见",
        "未提出明确处理意见",
        "建议完善相关检查，继续目前治疗",
        "必要时调整用药",
        "继续目前治疗",
        "对症治疗",
    )


def _consultation_record_presence_or_signature_issue(text: str) -> bool:
    return _has_any(
        text,
        "缺会诊时间",
        "缺少会诊时间",
        "会诊时间缺失",
        "会诊记录缺失",
        "缺失会诊记录",
        "缺少会诊记录",
        "缺会诊记录文书",
        "缺失会诊记录文书",
        "会诊记录文书缺失",
        "未见会诊记录",
        "无会诊记录",
        "会诊记录单缺失",
        "会诊医师签名",
        "申请医师签名",
        "签名缺失",
        "缺少签名",
    )


def _consultation_positive_execution(text: str) -> bool:
    return _has_any(
        text,
        "已包含执行情况",
        "已记录执行情况",
        "已记录会诊意见及执行情况",
        "已书写执行情况",
        "已体现执行情况",
        "已有执行记录",
        "有执行记录",
        "符合规则要求",
        "符合本规则要求",
        "符合规则",
        "未发现未书写问题",
        "未违反规则",
        "未违反本规则",
    )


def _consultation_has_strong_source_evidence(selected: dict[str, Any], text: str) -> bool:
    for item in list(selected.get("evidence_items") or []):
        if not isinstance(item, dict):
            continue
        source_table = str(item.get("source_table") or "").strip()
        if source_table == "consultation_record":
            return True
        source_document = " ".join(
            str(item.get(key) or "")
            for key in (
                "source_document_type",
                "source_document_name",
            )
        )
        if re.search(r"(会诊申请单|会诊记录单|会诊记录)", source_document):
            return True

    execution_evidence = _extract_execution_evidence(text)
    return bool(
        re.search(r"【[^】]*(会诊申请单|会诊记录单|会诊意见|会诊记录)[^】]*】", execution_evidence)
        or re.search(r"(来源文书|来源表|source_table).{0,24}consultation_record", execution_evidence)
    )


_COPY_TWO_COURSE_RELIABLE_PATTERNS = (
    re.compile(r"(两次|2次|二次|两份|2份|多次|连续).{0,20}(病程记录|查房记录|日常病程)"),
    re.compile(r"(病程记录|查房记录|日常病程).{0,20}(两次|2次|二次|两份|2份|多次|连续)"),
    re.compile(r"(相似度|重复率).{0,12}(?:大于|超过|>|≥)?\s*70%"),
)


def _has_reliable_two_course_copy_evidence(text: str) -> bool:
    if not text.strip():
        return False
    if any(pattern.search(text) for pattern in _COPY_TWO_COURSE_RELIABLE_PATTERNS):
        return True
    date_course_mentions = re.findall(
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}.{0,24}(?:病程记录|查房记录|日常病程)",
        text,
    )
    return len(set(date_course_mentions)) >= 2


def _copy_rule_has_insufficient_records_language(text: str) -> bool:
    return _has_any(
        text,
        "仅见单次查房记录",
        "仅见单次病程记录",
        "仅见1次查房记录",
        "仅见1次病程记录",
        "仅见一次查房记录",
        "仅见一次病程记录",
        "仅有单次查房记录",
        "仅有单次病程记录",
        "仅有1次查房记录",
        "仅有1次病程记录",
        "仅有一次查房记录",
        "仅有一次病程记录",
        "无法判定",
        "不能判定",
        "无法判断",
        "不能判断",
        "未能判定",
        "未能判断",
        "证据不足",
    )


def _first_course_copy_positive_non_defect(text: str) -> bool:
    if not text.strip():
        return False
    return _has_any(
        text,
        "非完全相同",
        "并非完全相同",
        "不完全相同",
        "存在实质性差异",
        "存在明显差异",
        "未发现复制",
        "未见复制",
        "不支持复制",
        "不构成复制",
        "符合规则要求",
        "未违反规则",
    )


def _preop_discussion_mismatch_issue(text: str) -> bool:
    if not _has_any(text, "麻醉科风险评估", "麻醉风险评估", "麻醉评估", "麻醉科医师签名", "麻醉医师签名"):
        return False
    if _has_any(text, "麻醉科医师签名", "麻醉医师签名") and not _has_any(
        text,
        "无术前讨论",
        "缺少术前讨论",
        "未见术前讨论",
        "术前讨论记录缺失",
        "术者未参加",
        "术者未参与",
    ):
        return True
    return not _has_any(
        text,
        "术前讨论",
        "术前讨论记录",
        "术者参加",
        "术者未参加",
        "手术医师参加",
        "参会人员",
        "替代方案",
        "手术方案",
    )


def _preop_discussion_signature_contradiction_issue(text: str) -> bool:
    if not _has_any(
        text,
        "缺少主持人",
        "缺主持人",
        "缺少记录医师",
        "缺记录医师",
        "缺失关键签名",
        "缺少关键签名",
        "签名缺失",
        "缺少签名",
    ):
        return False
    has_moderator = bool(re.search(r"主持人签名[:：]\s*[\u4e00-\u9fa5A-Za-z0-9]{2,}", text))
    has_recorder = bool(re.search(r"记录医师[:：]\s*[\u4e00-\u9fa5A-Za-z0-9]{2,}", text))
    return has_moderator and has_recorder


def _preop_discussion_presence_contradiction_issue(text: str) -> bool:
    if not _has_any(text, "缺少术前讨论", "缺术前讨论", "未见术前讨论", "无术前讨论", "术前讨论记录缺失"):
        return False
    return bool(re.search(r"(【术前讨论】|术前讨论记录).{0,40}(讨论时间|记录时间|主持人|参会|术者)", text))


def _preop_discussion_positive_language(text: str) -> bool:
    if not _has_any(text, "术前讨论", "术前讨论记录", "【术前讨论】"):
        return False
    return _has_any(
        text,
        "内容完整",
        "符合规则要求",
        "符合本规则要求",
        "符合规则",
        "已记录术前讨论",
        "存在术前讨论记录",
    ) and not _has_any(text, "但", "然而", "缺少", "缺失", "未明确", "未见", "无")


def _preop_discussion_exists(text: str) -> bool:
    return bool(
        re.search(r"(【术前讨论】|术前讨论记录|术前讨论).{0,80}(讨论时间|记录时间|主持人|参会|参与人员|术者|手术方案|替代方案)", text)
        or re.search(r"(讨论时间|主持人|参会人员|参与人员).{0,40}(术前讨论|手术方案)", text)
    )


def _preop_discussion_surgeon_participation_defect(text: str) -> bool:
    return _has_any(
        text,
        "术者未参加",
        "术者未参与",
        "术者缺席",
        "手术医师未参加",
        "手术医师未参与",
        "主刀医师未参加",
        "主刀医师未参与",
        "未明确体现为“术者”",
        "未明确体现为术者",
        "未见术者参加",
        "未见主刀医师参加",
    )


def _has_surgery_consent_source_coverage(selected: dict[str, Any], text: str, audit_context: dict[str, Any] | None) -> bool:
    for item in list(selected.get("evidence_items") or []):
        if not isinstance(item, dict):
            continue
        source_text = " ".join(
            str(item.get(key) or "")
            for key in (
                "source_table",
                "source_document_type",
                "source_document_name",
                "field_path",
            )
        )
        if _has_any(source_text, "surgery_inform_consent", "手术知情同意书", "签署文书", "同意书"):
            return True
    audit_text = _audit_context_text(audit_context)
    return _has_any(
        f"{text}\n{audit_text}",
        "surgery_inform_consent",
        "signed_document",
        "consent_form",
        "手术知情同意书来源",
        "已同步手术知情同意书",
        "签署文书表",
    )


def _surgery_consent_missing_language(text: str) -> bool:
    return bool(
        re.search(r"(未找到|未见|未包含|未提供|缺少|缺失|无|未检出|未检索到|未检索).{0,16}(手术知情同意书|知情同意书|同意书)", text)
        or re.search(r"(手术知情同意书|知情同意书|同意书).{0,16}(未找到|未见|未包含|未提供|缺少|缺失|无|未检出|未检索到|未检索)", text)
    )


def _data_gap_guarded_result(
    selected: dict[str, Any],
    *,
    findings: str,
    evidence: str,
    suggestion: str,
    guard: str,
) -> dict[str, Any]:
    guarded = dict(selected)
    guarded.update(
        {
            "status": "data_gap",
            "is_compliant": False,
            "findings": findings,
            "evidence": evidence,
            "suggestion": suggestion,
        }
    )
    metadata = dict(guarded.get("metadata") or {})
    metadata["customer_display_guard"] = guard
    guarded["metadata"] = metadata
    return guarded


def _not_applicable_guarded_result(
    selected: dict[str, Any],
    *,
    findings: str,
    evidence: str,
    suggestion: str,
    guard: str,
) -> dict[str, Any]:
    guarded = dict(selected)
    guarded.update(
        {
            "status": "not_applicable",
            "is_compliant": True,
            "findings": findings,
            "evidence": evidence,
            "suggestion": suggestion,
        }
    )
    metadata = dict(guarded.get("metadata") or {})
    metadata["customer_display_guard"] = guard
    guarded["metadata"] = metadata
    return guarded


def _implant_absence_language(text: str) -> bool:
    return _has_any(
        text,
        "未提及植入物",
        "未见植入物",
        "无植入物",
        "未发现植入物",
        "无法判断是否存在植入物",
    )


def _implant_strong_fact(text: str) -> bool:
    return _has_any(
        text,
        "植入物",
        "内固定",
        "螺钉",
        "钢板",
        "支架",
        "输尿管支架",
        "双J管",
        "双 J 管",
        "D-J管",
        "DJ管",
        "假体",
        "补片",
        "网片",
        "人工补片",
        "融合器",
        "钉棒",
    )


def _implant_specific_material_fact(text: str) -> bool:
    return _has_any(
        text,
        "内固定",
        "螺钉",
        "钢板",
        "骨水泥",
        "支架",
        "输尿管支架",
        "双J管",
        "双 J 管",
        "D-J管",
        "DJ管",
        "假体",
        "补片",
        "网片",
        "人工补片",
        "融合器",
        "钉棒",
    )


def _surgery_consent_source_gap(text: str) -> bool:
    if not _has_any(
        text,
        "未找到独立同意书",
        "未见手术知情同意书",
        "缺手术知情同意书",
        "无手术知情同意书",
        "未检索到手术知情同意书",
        "未检出手术知情同意书",
    ):
        return False
    return not _has_any(text, "surgery_inform_consent", "手术知情同意书来源", "已同步手术知情同意书")


def _no_bottom_result_language(text: str) -> bool:
    return _has_any(
        text,
        "未返回底层执行结果",
        "底层未返回结果",
        "未形成可靠结论",
        "规则未形成结论",
        "未返回可复核结果",
    )


def _has_chemo_treatment_fact(text: str) -> bool:
    return bool(
        re.search(
            r"(化疗医嘱|化疗记录|化学治疗记录|辅助化疗|新辅助化疗|化疗方案|"
            r"奥沙利铂|卡培他滨|顺铂|紫杉醇|吉西他滨|氟尿嘧啶|替吉奥|伊立替康|多西他赛)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _anesthesia_consent_result_not_record_sheet(text: str) -> bool:
    if not _has_any(text, "知情同意书", "同意书"):
        return False
    return not _has_any(
        text,
        "无麻醉记录",
        "缺少麻醉记录",
        "未见麻醉记录",
        "麻醉记录单缺失",
        "麻醉记录缺失",
        "麻醉记录单未见",
        "无麻醉记录单",
    )


def _stable_round_result_has_critical_context(text: str) -> bool:
    if not text:
        return False
    return _has_any(
        text,
        "抢救",
        "提示病情危重",
        "病情危重",
        "危重症",
        "来源线索：病危",
        "来源线索：危重",
        "来源线索:病危",
        "来源线索:危重",
    )


def _consultation_has_concrete_execution(text: str) -> bool:
    if not text.strip():
        return False
    if not re.search(r"(会诊|遵会诊|按会诊|会诊意见|请会诊)", text):
        return False
    concrete_markers = (
        "穿刺成功",
        "蛛网膜下腔给药",
        "硬膜外",
        "PCA",
        "麻醉平面",
        "已开立",
        "调整用药",
        "予以",
        "给予",
        "镇痛泵",
        "药物",
        "补液",
    )
    if any(marker in text for marker in concrete_markers):
        return True
    return bool(re.search(r"\d{1,2}:\d{2}.{0,40}(给药|穿刺|开立|执行|复查|检查|治疗|处理)", text))


def _audit_context_text(audit_context: dict[str, Any] | None) -> str:
    timeline = _timeline_from_audit(audit_context)
    docs = timeline.get("documents")
    parts: list[str] = []
    if isinstance(docs, dict):
        for items in docs.values():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                parts.extend(
                    str(item.get(key) or "").strip()
                    for key in (
                        "document_title",
                        "content",
                        "raw_text",
                        "content_preview",
                        "display_time",
                        "record_time",
                        "submit_datetime",
                        "update_time",
                    )
                    if str(item.get(key) or "").strip()
                )
    return "\n".join(parts)


def _guard_customer_display_result(
    *,
    wrapper_id: str,
    selected: dict[str, Any],
    audit_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = _status(selected)
    findings = str(selected.get("findings") or "")
    evidence = str(selected.get("evidence") or "")
    suggestion = str(selected.get("suggestion") or "")
    metadata = selected.get("metadata") if isinstance(selected.get("metadata"), dict) else {}
    if metadata.get("customer_display_guard") and wrapper_id != "LX0609-019":
        return selected
    trace_text = "\n".join(
        str(item or "")
        for item in [
            selected.get("source_evidence"),
            selected.get("source_conclusion"),
            selected.get("diagnostic_trace"),
            metadata.get("diagnostic_trace"),
            metadata.get("source_execution_results"),
            metadata.get("trigger_decision"),
        ]
        if item
    )
    combined_text = f"{findings}\n{evidence}\n{suggestion}\n{trace_text}"
    audit_text = _audit_context_text(audit_context)
    factual_text = f"{audit_text}\n{combined_text}"
    needs_guard_statuses = {"non_compliant", "ai_suggested_non_compliant", "data_gap", "uncertain"}

    if wrapper_id in {"LX0609-029", "LX0609-032"} and status in {
        "non_compliant",
        "ai_suggested_non_compliant",
    }:
        required_source = (
            "presurg_summary"
            if wrapper_id == "LX0609-029"
            else "surgery_safecheck_record"
        )
        if not _has_explicit_source_coverage(audit_context, required_source):
            return _data_gap_guarded_result(
                selected,
                findings="当前结论提示目标手术文书缺失，但正式来源覆盖未能证明该文书表已完成查询，不能直接判定为业务缺陷。",
                evidence="目标文书来源覆盖不足，无法区分‘确实不存在’与‘来源未同步或未投影’。",
                suggestion="请确认目标文书来源已接入并完成当前住院查询；补齐来源覆盖后重新质控。",
                guard="surgery_document_target_source_unproven",
            )

    if wrapper_id == "LX0609-028" and status in {"non_compliant", "data_gap", "uncertain"}:
        has_incision, incision_markers = _has_lx0609_028_class_i_ii_incision_context(factual_text)
        if not has_incision:
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "not_applicable",
                    "is_compliant": True,
                    "findings": "未发现I类/II类切口或常见清洁、清洁-污染切口手术事实，本质控点不适用。",
                    "evidence": "当前证据未能确认属于I类或II类切口手术，不按预防抗菌药物使用时限缺陷处理。",
                    "suggestion": "无需按本质控点整改；如源病历实际存在I类/II类切口手术，请补齐手术切口分类或手术名称后重新质控。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "antibiotic_rule_requires_class_i_ii_incision"
            guarded["metadata"] = metadata
            return guarded

        has_antibiotic, antibiotic_markers = _has_antibiotic_order_context(factual_text)
        if not has_antibiotic:
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "not_applicable",
                    "is_compliant": True,
                    "findings": "已识别到I类/II类切口相关手术，但未发现预防使用抗菌药物医嘱，本质控点不适用。",
                    "evidence": f"已识别手术适用线索：{'；'.join(incision_markers) or 'I/II类切口相关手术'}；未发现抗菌药物医嘱或预防用药事实。",
                    "suggestion": "无需按抗菌药物使用时限缺陷处理；如实际有预防抗菌药物医嘱，请补齐医嘱数据后重新质控。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "antibiotic_rule_requires_antibiotic_order"
            guarded["metadata"] = metadata
            return guarded

        missing_time_fields = _missing_lx0609_028_antibiotic_time_fields(factual_text)
        if missing_time_fields:
            fields = "、".join(missing_time_fields)
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "data_gap",
                    "is_compliant": False,
                    "findings": f"已识别到I类/II类切口相关手术及预防抗菌药物医嘱，但缺少{fields}，无法自动判断是否超过24小时。",
                    "evidence": (
                        f"手术适用线索：{'；'.join(incision_markers) or 'I/II类切口相关手术'}；"
                        f"抗菌药物线索：{'；'.join(antibiotic_markers) or '预防抗菌药物医嘱'}；"
                        f"缺失字段：{fields}"
                    ),
                    "suggestion": f"请补齐{fields}后重新质控，或由质控员确认抗菌药物使用时长。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "antibiotic_rule_missing_order_time"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-016" and status in {"non_compliant", "data_gap", "uncertain"}:
        if _first_course_copy_positive_non_defect(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "首次病程记录与入院记录、现病史未形成完全相同的复制粘贴结论，本质控点未形成缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": "当前无需按首次病程复制入院记录处理；如质控员仍有疑点，可人工对照完整原文。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "first_course_copy_positive_non_defect"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-007" and status == "non_compliant":
        if _stable_round_result_has_critical_context(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "病历中存在抢救或危重线索，不能直接按“病情稳定患者3天内无查房病程记录”判为缺陷。",
                    "evidence": _extract_execution_evidence(evidence)
                    or "当前结果包含抢救或危重相关线索，需先核对是否存在病危、病重医嘱及对应病程记录。",
                    "suggestion": "请先核对病危/病重医嘱、抢救记录和查房病程时间轴，再决定适用稳定患者查房规则或病危病重查房规则。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "stable_round_has_critical_context"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-003" and status == "non_compliant":
        if _has_any(combined_text, "未超过24小时", "未超24小时", "符合质控规则要求", "符合规则要求"):
            guarded = dict(selected)
            has_missing_cross_check = _has_any(combined_text, "缺少麻醉记录", "无法通过", "无法交叉验证", "证据不足")
            guarded.update(
                {
                    "status": "data_gap" if has_missing_cross_check else "compliant",
                    "is_compliant": False if has_missing_cross_check else True,
                    "findings": (
                        "手术记录时间未超过术后24小时，但缺少麻醉记录等交叉核对字段，暂不能作为缺陷展示。"
                        if has_missing_cross_check
                        else "手术记录完成时间未超过术后24小时，本质控点未形成缺陷。"
                    ),
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": (
                        "请补齐麻醉记录或手术结束时间等交叉核对字段后复核。"
                        if has_missing_cross_check
                        else "当前无需按超时缺陷处理。"
                    ),
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "lx0609_003_positive_time_result"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-038" and status == "non_compliant":
        if _anesthesia_consent_result_not_record_sheet(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "当前证据主要指向麻醉知情同意书问题，不能直接判定为无麻醉记录单。",
                    "evidence": "本质控点需要核对麻醉记录单；当前底层证据不足以支撑“无麻醉记录单”缺陷。",
                    "suggestion": "请质控员确认是否存在麻醉记录单；如需检查麻醉知情同意书，应使用对应质控点处理。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "anesthesia_consent_not_record_sheet_defect"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-025" and status in needs_guard_statuses:
        if not _implant_specific_material_fact(factual_text):
            return _not_applicable_guarded_result(
                selected,
                findings="未发现植入物、补片、假体、双J管或内固定材料等强触发事实，本质控点不适用。",
                evidence="当前证据未能确认存在需要核对条码或追溯码的植入物材料。",
                suggestion="无需按植入物条码缺陷处理；如源病历实际存在植入物，请补齐手术记录、耗材或条码来源后重新质控。",
                guard="implant_rule_requires_implant_fact",
            )
        if _implant_strong_fact(factual_text) and _has_any(combined_text, "无法判定", "证据不足", "结构化覆盖不足", "缺少条码", "未见条码", "无条码"):
            return _data_gap_guarded_result(
                selected,
                findings="已发现植入物或高值耗材线索，但缺少条码、追溯码或耗材对照来源，无法自动确认条码是否齐全。",
                evidence=_extract_execution_evidence(evidence) or "已发现植入物线索，但条码/追溯码来源不足。",
                suggestion="请补齐手术耗材、条码/追溯码或费用对照数据后重新质控。",
                guard="implant_rule_missing_barcode_source",
            )

    if wrapper_id == "LX0609-024" and status in needs_guard_statuses:
        has_current_tumor_surgery, markers = _has_lx0609_024_malignant_tumor_surgery_context(factual_text)
        if not has_current_tumor_surgery:
            return _not_applicable_guarded_result(
                selected,
                findings="未发现本次手术属于恶性肿瘤手术或淋巴结清扫相关手术，本质控点不适用。",
                evidence="当前证据不能证明本次手术为恶性肿瘤根治、肿瘤切除或淋巴结清扫相关手术，不按淋巴结清扫记录缺陷处理。",
                suggestion="无需按本质控点整改；如源病历实际为恶性肿瘤相关手术，请补齐手术名称、术前/术后诊断或术中所见后重新质控。",
                guard="malignant_tumor_surgery_requires_current_surgery_fact",
            )
        metadata = dict(selected.get("metadata") or {})
        metadata["lx0609_024_current_surgery_markers"] = list(markers)
        selected = {**selected, "metadata": metadata}

    if wrapper_id == "LX0609-019" and status in {"non_compliant", "ai_suggested_non_compliant", "data_gap", "uncertain"}:
        source_only_text = "\n".join(
            str(item or "")
            for item in [
                selected.get("source_evidence"),
                metadata.get("source_execution_results"),
                metadata.get("diagnostic_trace"),
            ]
            if item
        )
        if _PATHOLOGY_SIMPLE_SPECIMEN_RECORDED_IN_SURGERY_PATTERN.search(source_only_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "手术记录已记录标本送病检事实，本质控点未形成缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or selected.get("source_evidence") or findings,
                    "suggestion": "当前无需按取材或送检记录缺陷处理。",
                }
            )
            guarded_metadata = dict(guarded.get("metadata") or {})
            guarded_metadata["customer_display_guard"] = "pathology_simple_specimen_sent_recorded"
            guarded["metadata"] = guarded_metadata
            return guarded

    if wrapper_id in {"LX0609-019", "LX0609-024"} and status in {"non_compliant", "ai_suggested_non_compliant"}:
        if _has_recorded_pathology_material(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "手术记录已记录术中取材及冰冻/病理相关结果，本质控点未形成缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": "当前无需按取材或病理记录缺陷处理；如需确认手术范围调整，请按对应规则处理。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "pathology_specimen_positive_recorded"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-019" and status in needs_guard_statuses:
        execution_evidence = _extract_execution_evidence(evidence)
        if not _has_pathology_specimen_source_fact(execution_evidence):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "not_applicable",
                    "is_compliant": True,
                    "findings": "未发现病理报告、活检取材或手术送检等强触发事实，本质控点不适用。",
                    "evidence": "当前证据未引用病理报告、活检取材、手术送检或标本处理原文，不按取材记录缺陷处理。",
                    "suggestion": "无需按病理取材记录缺陷处理；如源病历实际存在病理或送检记录，请补齐相关文书后重新质控。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "pathology_specimen_requires_source_fact"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-021" and status == "non_compliant":
        if _consultation_signature_only_issue(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "当前证据主要指向会诊申请或会诊记录签名缺项，不能直接判定为会诊目的不明确。",
                    "evidence": _extract_execution_evidence(evidence) or "需核对会诊申请单中的会诊目的和医师签名字段。",
                    "suggestion": "请人工区分会诊目的不明确、签名缺项和会诊执行记录缺陷，避免串用质控点。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "consultation_signature_only_not_purpose_defect"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-022" and status == "non_compliant":
        if _consultation_record_presence_or_signature_issue(combined_text) and not _consultation_opinion_quality_issue(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "当前证据主要指向会诊时间、签名或会诊记录缺失，不能直接判定为会诊意见不明确。",
                    "evidence": _extract_execution_evidence(evidence) or "需核对会诊记录单中是否存在明确、可执行的会诊意见。",
                    "suggestion": "请人工区分会诊意见不明确、会诊记录缺失和签名缺项，避免串用质控点。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "consultation_record_presence_not_opinion_quality_defect"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id in {"LX0609-020", "LX0609-023"} and status in {"non_compliant", "data_gap", "uncertain"}:
        if _consultation_has_concrete_execution(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "病程或会诊相关记录已体现具体执行措施，本质控点未形成会诊执行缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": "当前无需按会诊执行记录缺陷处理；如需核对签名或会诊目的，请按对应质控点处理。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "consultation_concrete_execution_recorded"
            guarded["metadata"] = metadata
            return guarded
        if _consultation_positive_execution(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "compliant",
                    "is_compliant": True,
                    "findings": "会诊意见执行情况已有记录，本质控点未形成缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": "当前无需按会诊执行情况缺陷处理；如需核对签名或申请单项目，请按对应质控点处理。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "consultation_execution_positive_recorded"
            guarded["metadata"] = metadata
            return guarded
        if not _consultation_has_strong_source_evidence(selected, combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "not_applicable",
                    "is_compliant": True,
                    "findings": "未发现会诊申请单、会诊记录单或会诊意见等强触发事实，本质控点不适用。",
                    "evidence": "当前证据未引用会诊申请单、会诊记录单或会诊意见原文，不按会诊执行记录缺陷处理。",
                    "suggestion": "无需按会诊执行情况缺陷处理；如源病历实际存在会诊记录，请补齐会诊文书后重新质控。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "consultation_requires_strong_source_evidence"
            guarded["metadata"] = metadata
            return guarded
        if _consultation_signature_only_issue(combined_text) and not _consultation_execution_missing(combined_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "当前证据主要指向签名或申请记录问题，未能确认会诊意见执行情况缺陷。",
                    "evidence": _extract_execution_evidence(evidence) or findings,
                    "suggestion": "请人工区分签名缺项、会诊申请缺项和会诊意见执行情况缺陷，避免串用质控点。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "consultation_signature_only_not_execution_defect"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-017" and status == "non_compliant":
        if _copy_rule_has_insufficient_records_language(combined_text) or not _has_reliable_two_course_copy_evidence(combined_text):
            readable_findings, readable_evidence, readable_suggestion = _readable_uncertain_findings(wrapper_id)
            comparable_documents = _copy_compare_documents(audit_context)
            if len(comparable_documents) >= 2:
                guarded = dict(selected)
                guarded.update(
                    {
                        "status": "compliant",
                        "is_compliant": True,
                        "findings": "已比对两份以上病程/查房记录，未达到复制粘贴自动判定阈值，本质控点未形成缺陷。",
                        "evidence": _readable_copy_uncertain_evidence(audit_context),
                        "suggestion": "当前无需按复制粘贴缺陷处理；如质控员仍有疑点，可人工抽查病程记录差异。",
                    }
                )
                metadata = dict(guarded.get("metadata") or {})
                metadata["customer_display_guard"] = "copy_rule_below_threshold_no_defect"
                guarded["metadata"] = metadata
                return guarded
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": readable_findings,
                    "evidence": _readable_copy_uncertain_evidence(audit_context) or readable_evidence,
                    "suggestion": readable_suggestion,
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "copy_rule_requires_two_course_records"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-027" and status == "non_compliant" and _no_bottom_result_language(combined_text):
        guarded = dict(selected)
        guarded.update(
            {
                "status": "uncertain",
                "is_compliant": False,
                "findings": "当前自动判定未形成可靠结论，建议质控员确认。",
                "evidence": _readable_uncertain_evidence(evidence),
                "suggestion": "请质控员核对出院记录、肿瘤病理结果及后续治疗计划后再形成结论。",
            }
        )
        metadata = dict(guarded.get("metadata") or {})
        metadata["customer_display_guard"] = "bottom_rule_no_reliable_result"
        guarded["metadata"] = metadata
        return guarded

    if wrapper_id == "LX0609-026" and status != "not_applicable":
        execution_evidence = _extract_execution_evidence(evidence)
        factual_text = f"{findings}\n{execution_evidence}\n{suggestion}"
        if not _has_chemo_treatment_fact(factual_text):
            guarded = dict(selected)
            guarded.update(
                {
                    "status": "not_applicable",
                    "is_compliant": True,
                    "findings": "未发现明确化疗医嘱或化疗记录，本次不适用化疗记录一致性质控点。",
                    "evidence": execution_evidence or "当前结果未提供化疗医嘱、化疗记录或具体化疗药物证据。",
                    "suggestion": "无需按化疗记录一致性处理；如病历存在化疗医嘱或化疗记录，请补充结构化数据后重新质控。",
                }
            )
            metadata = dict(guarded.get("metadata") or {})
            metadata["customer_display_guard"] = "chemo_rule_requires_chemo_fact"
            guarded["metadata"] = metadata
            return guarded

    if wrapper_id == "LX0609-039" and status in {"non_compliant", "ai_suggested_non_compliant"} and _preop_discussion_positive_language(combined_text):
        guarded = dict(selected)
        guarded.update(
            {
                "status": "compliant",
                "is_compliant": True,
                "findings": "术前讨论记录已存在且当前证据未形成术者参与不足或讨论内容缺陷，本质控点未形成缺陷。",
                "evidence": _extract_execution_evidence(evidence) or findings,
                "suggestion": "当前无需按无术前讨论或术者未参加处理；如需进一步核对讨论质量，请查看术前讨论原文。",
            }
        )
        metadata = dict(guarded.get("metadata") or {})
        metadata["customer_display_guard"] = "preop_discussion_positive_result_not_defect"
        guarded["metadata"] = metadata
        return guarded

    if wrapper_id == "LX0609-039" and status in {"non_compliant", "ai_suggested_non_compliant"} and _preop_discussion_mismatch_issue(combined_text):
        return _data_gap_guarded_result(
            selected,
            findings="当前证据主要指向麻醉风险评估，不能直接判定为术前讨论记录缺失或术者未参加。",
            evidence=_extract_execution_evidence(evidence) or findings,
            suggestion="请结合术前讨论记录、参会人员和术者参与情况确认；麻醉风险评估问题应按对应质控点处理。",
            guard="preop_discussion_mismatch_anesthesia_risk",
        )

    if wrapper_id == "LX0609-039" and status in {"non_compliant", "ai_suggested_non_compliant"} and _preop_discussion_signature_contradiction_issue(combined_text):
        return _data_gap_guarded_result(
            selected,
            findings="当前结论与证据存在矛盾：结论提示缺少主持人或记录医师签名，但证据中已出现相应签名信息。",
            evidence=_extract_execution_evidence(evidence) or findings,
            suggestion="请结合术前讨论记录原文、签名栏和参会人员信息确认后再形成结论。",
            guard="preop_discussion_signature_contradiction",
        )

    if wrapper_id == "LX0609-039" and status in {"non_compliant", "ai_suggested_non_compliant"} and _preop_discussion_presence_contradiction_issue(combined_text):
        return _data_gap_guarded_result(
            selected,
            findings="当前结论与证据存在矛盾：结论提示缺少术前讨论记录，但证据中已出现术前讨论记录线索。",
            evidence=_extract_execution_evidence(evidence) or findings,
            suggestion="请结合术前讨论记录原文、记录时间、参会人员和术者参与情况确认；不能按“无术前讨论”直接判缺陷。",
            guard="preop_discussion_presence_contradiction",
        )

    if wrapper_id == "LX0609-039" and status in {"non_compliant", "ai_suggested_non_compliant"} and _preop_discussion_exists(combined_text) and not _preop_discussion_surgeon_participation_defect(combined_text):
        return _data_gap_guarded_result(
            selected,
            findings="已发现术前讨论记录，当前证据不足以直接判定为“无术前讨论”或“术者未参加”。",
            evidence=_extract_execution_evidence(evidence) or findings,
            suggestion="请继续核对术前讨论记录中的术者参与、讨论内容和签名信息；不能仅因目录或元数据异常判为缺陷。",
            guard="preop_discussion_exists_need_participation_check",
        )

    if wrapper_id == "LX0609-040" and status in needs_guard_statuses:
        has_level_4, markers = _has_level_4_surgery_context(factual_text)
        if not has_level_4:
            return _not_applicable_guarded_result(
                selected,
                findings="未发现四级手术或重大手术强证据，本质控点不适用。",
                evidence="当前证据不能证明本次手术属于四级手术、重大手术或明确需要MDT讨论的高风险手术，不按MDT缺失处理。",
                suggestion="无需按四级手术MDT讨论缺陷处理；如源病历实际为四级手术，请补齐手术分级、手术名称或重大手术审批记录后重新质控。",
                guard="mdt_rule_requires_level_4_surgery_fact",
            )
        metadata = dict(selected.get("metadata") or {})
        metadata["lx0609_040_level_4_markers"] = list(markers)
        selected = {**selected, "metadata": metadata}

    if wrapper_id == "LX0609-033" and status in {"non_compliant", "ai_suggested_non_compliant"} and (
        _surgery_consent_source_gap(combined_text)
        or (_surgery_consent_missing_language(combined_text) and not _has_surgery_consent_source_coverage(selected, combined_text, audit_context))
    ):
        return _data_gap_guarded_result(
            selected,
            findings="当前仅提示未找到独立手术知情同意书，但缺少同意书/签署文书来源覆盖，不能直接判定为业务缺陷。",
            evidence=_extract_execution_evidence(evidence) or "未见可核对的手术知情同意书来源表或签署文书证据。",
            suggestion="请确认客户库是否已同步手术知情同意书、签署文书或扫描件目录；补齐后重新质控。",
            guard="surgery_consent_source_gap",
        )

    if status == "uncertain" and _has_any(combined_text, "LLM", "非结构化结果", "原始输出"):
        readable_findings, readable_evidence, readable_suggestion = _readable_uncertain_findings(wrapper_id)
        guarded = dict(selected)
        guarded.update(
            {
                "status": "uncertain",
                "is_compliant": False,
                "findings": readable_findings,
                "evidence": _readable_uncertain_evidence(evidence, readable_evidence),
                "suggestion": readable_suggestion,
            }
        )
        metadata = dict(guarded.get("metadata") or {})
        metadata["customer_display_guard"] = "customer_readable_uncertain"
        guarded["metadata"] = metadata
        return guarded

    return selected


def _select_best_result(
    *,
    mapped_results: list[dict[str, Any]],
    primary_rule_id: str,
) -> tuple[dict[str, Any] | None, str]:
    if not mapped_results:
        return None, "missing_mapped_result"

    primary = [item for item in mapped_results if _norm_id(item.get("rule_id") or item.get("rule_code")) == primary_rule_id]
    for target_status, source in (
        ("technical_error", "mapped_technical_error"),
        ("non_compliant", "mapped_non_compliant"),
        ("data_gap", "mapped_data_gap"),
        ("uncertain", "mapped_uncertain"),
        ("not_executed", "mapped_not_executed"),
    ):
        candidates = [item for item in mapped_results if _status(item) == target_status]
        if candidates:
            candidates.sort(key=lambda item: (_confidence(item.get("confidence")), _norm_id(item.get("rule_id"))), reverse=True)
            primary_match = [item for item in primary if _status(item) == target_status]
            if primary_match:
                return primary_match[0], f"primary_{target_status}"
            return candidates[0], source

    if primary:
        return primary[0], "primary_result"
    return mapped_results[0], "first_mapped_result"


def _source_evidence_snapshot(item: dict[str, Any]) -> Any:
    evidence_items = item.get("evidence_items")
    if isinstance(evidence_items, list) and evidence_items:
        return _strip_sensitive(evidence_items[:8])
    evidence = str(item.get("evidence") or "").strip()
    if evidence:
        return evidence[:1200]
    return ""


def _source_execution_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    return _strip_sensitive(
        {
            "source_rule_id": _norm_id(item.get("rule_id") or item.get("rule_code")),
            "source_status": _status(item),
            "source_conclusion": str(
                item.get("findings")
                or item.get("conclusion")
                or item.get("summary")
                or ""
            ).strip(),
            "source_evidence": _source_evidence_snapshot(item),
            "confidence": _confidence(item.get("confidence")),
            "executor_type": str(metadata.get("executor_type") or item.get("executor_type") or ""),
            "model_version": str(metadata.get("model_version") or item.get("model_version") or ""),
            "final_decision_source": str(
                metadata.get("final_decision_source")
                or item.get("final_decision_source")
                or ""
            ),
            "postprocess_reason": str(
                metadata.get("postprocess_reason")
                or item.get("postprocess_reason")
                or ""
            ),
        }
    )


def _customerize_review_wording(text: Any) -> str:
    rendered = str(text or "").strip()
    if not rendered:
        return ""
    replacements = (
        ("待人工复核", "AI判断后建议确认"),
        ("待人工核对", "AI判断后建议确认"),
        ("建议人工复核", "建议结合原文确认"),
        ("建议人工核对", "建议结合原文确认"),
        ("需人工复核", "需结合原文确认"),
        ("需人工核对", "需结合原文确认"),
        ("需要人工复核", "需要结合原文确认"),
        ("需要人工核对", "需要结合原文确认"),
        ("人工复核", "结合原文确认"),
        ("人工核对", "结合原文确认"),
        ("待复核", "AI判断"),
    )
    for source, target in replacements:
        rendered = rendered.replace(source, target)
    return rendered


def _split_uncertain_customer_result(*, wrapper_id: str, selected: dict[str, Any]) -> dict[str, Any]:
    """Convert internal uncertain into customer-facing statuses.

    Trace keeps the original uncertain status, while customer UI gets a concrete
    display bucket: AI suggestion, data gap, or not applicable.
    """

    if _status(selected) != "uncertain":
        return selected

    guarded = dict(selected)
    findings = _customerize_review_wording(guarded.get("findings"))
    evidence = _customerize_review_wording(guarded.get("evidence"))
    suggestion = _customerize_review_wording(guarded.get("suggestion"))
    combined = f"{findings}\n{evidence}\n{suggestion}"
    normalized = re.sub(r"\s+", "", combined)

    if _has_any(normalized, "不适用", "未发现触发", "无触发", "不按", "无需按"):
        status = "not_applicable"
        is_compliant = True
        default_findings = "未发现本质控点的强触发事实，本次不适用。"
        default_suggestion = "当前无需按本质控点处理；如源病历实际存在触发文书或结构化数据，请补齐后重新质控。"
    elif _has_any(
        normalized,
        "缺少",
        "缺失",
        "无法",
        "未能",
        "证据不足",
        "未形成可靠",
        "为空",
        "未返回",
        "未提取",
        "数据不足",
    ):
        status = "data_gap"
        is_compliant = False
        default_findings = "自动判定所需证据不完整，暂不能形成确定结论。"
        default_suggestion = "请补齐缺失字段或相关文书后重新质控，必要时结合原文确认。"
    elif _has_any(normalized, "未形成缺陷", "无需", "未发现问题", "符合", "未达到阈值"):
        status = "ai_suggested_compliant"
        is_compliant = True
        default_findings = "AI判断当前证据未形成质控问题。"
        default_suggestion = "当前无需整改；如仍有疑点，可结合原文抽查确认。"
    else:
        status = "ai_suggested_non_compliant"
        is_compliant = False
        default_findings = "AI判断当前证据存在疑似质控问题。"
        default_suggestion = "建议结合原文确认后再纳入整改或扣分。"

    guarded.update(
        {
            "status": status,
            "is_compliant": is_compliant,
            "findings": findings or default_findings,
            "evidence": evidence or findings or default_findings,
            "suggestion": suggestion or default_suggestion,
        }
    )
    metadata = dict(guarded.get("metadata") or {})
    metadata.setdefault("internal_original_status", "uncertain")
    metadata["customer_display_status"] = status
    metadata["customer_display_guard"] = metadata.get("customer_display_guard") or "split_internal_uncertain"
    if wrapper_id:
        metadata["customer_rule_id"] = wrapper_id
    guarded["metadata"] = metadata
    return guarded


def _trigger_decision_snapshot(decision: Luxian0609GateDecision | None) -> dict[str, Any]:
    if decision is None:
        return {}
    return {
        "rule_id": _norm_id(decision.rule_id),
        "status": decision.status,
        "reason": decision.reason,
        "data_gap_fields": list(decision.data_gap_fields),
        "matched_keywords": list(decision.matched_keywords),
    }


def _build_diagnostic_trace(
    *,
    wrapper_id: str,
    selected: dict[str, Any],
    mapped_results: list[dict[str, Any]],
    source: str,
    gate_decision: Luxian0609GateDecision | None,
    primary_rule_id: str,
    mapped_rule_ids: list[str],
) -> dict[str, Any]:
    selected_source_rule_id = _norm_id(selected.get("rule_id") or selected.get("rule_code"))
    source_results = [_source_execution_snapshot(item) for item in mapped_results if isinstance(item, dict)]
    if not source_results and source not in {"trigger_gate", "missing_mapped_result"}:
        source_results = [_source_execution_snapshot(selected)]
    selected_metadata = dict(selected.get("metadata") or {})
    aggregation_reason = (
        f"{source}: selected {selected_source_rule_id or wrapper_id} "
        f"from {len(mapped_results)} mapped execution result(s)"
    )
    postprocess_reason = str(
        selected_metadata.get("postprocess_reason")
        or selected.get("postprocess_reason")
        or selected_metadata.get("customer_display_guard")
        or ""
    )
    original_status = str(selected_metadata.get("internal_original_status") or "").strip().lower()
    customer_status = _status(selected)
    return _strip_sensitive(
        {
            "customer_rule_id": wrapper_id,
            "source_rule_id": selected_source_rule_id or wrapper_id,
            "source_status": original_status or customer_status,
            "customer_status": customer_status,
            "source_conclusion": str(
                selected.get("findings")
                or selected.get("conclusion")
                or selected.get("summary")
                or ""
            ).strip(),
            "source_evidence": _source_evidence_snapshot(selected),
            "trigger_decision": _trigger_decision_snapshot(gate_decision),
            "aggregation_reason": aggregation_reason,
            "postprocess_reason": postprocess_reason,
            "primary_execution_rule_id": primary_rule_id,
            "mapped_rule_ids": mapped_rule_ids,
            "selected_execution_rule_id": selected_source_rule_id,
            "source_execution_results": source_results,
        }
    )


def _copy_customer_fields(
    *,
    wrapper: dict[str, Any],
    selected: dict[str, Any],
    mapped_results: list[dict[str, Any]],
    source: str,
    gate_decision: Luxian0609GateDecision | None,
) -> dict[str, Any]:
    wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
    primary_rule_id = _norm_id(wrapper.get("primary_execution_rule_id"))
    mapped_rule_ids = [_norm_id(item) for item in list(wrapper.get("mapped_rule_ids") or []) if _norm_id(item)]
    selected = _split_uncertain_customer_result(wrapper_id=wrapper_id, selected=selected)
    status = _status(selected)
    if status not in {
        "compliant",
        "non_compliant",
        "ai_suggested_non_compliant",
        "ai_suggested_compliant",
        "not_applicable",
        "data_gap",
        "uncertain",
        "not_executed",
        "technical_error",
    }:
        status = "data_gap"
    metadata = _strip_sensitive(dict(selected.get("metadata") or {}))
    if gate_decision is not None:
        metadata.update(gate_decision.to_metadata())
    metadata.update(
        {
            "mapped_rule_ids": mapped_rule_ids,
            "primary_execution_rule_id": primary_rule_id,
            "aggregation_source": source,
            "selected_execution_rule_id": _norm_id(selected.get("rule_id") or selected.get("rule_code")),
            "mapped_result_count": len(mapped_results),
            "customer_rule_id": wrapper_id,
        }
    )
    diagnostic_trace = _build_diagnostic_trace(
        wrapper_id=wrapper_id,
        selected=selected,
        mapped_results=mapped_results,
        source=source,
        gate_decision=gate_decision,
        primary_rule_id=primary_rule_id,
        mapped_rule_ids=mapped_rule_ids,
    )
    metadata["diagnostic_trace"] = diagnostic_trace
    metadata["source_execution_results"] = diagnostic_trace.get("source_execution_results") or []
    metadata["trigger_decision"] = diagnostic_trace.get("trigger_decision") or {}
    metadata["postprocess_reason"] = diagnostic_trace.get("postprocess_reason") or ""
    result = {
        **_strip_sensitive(selected),
        "rule_id": wrapper_id,
        "rule_code": wrapper_id,
        "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or selected.get("rule_name") or wrapper_id),
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable", "ai_suggested_compliant"},
        "metadata": metadata,
        "diagnostic_trace": diagnostic_trace,
        "source_rule_id": diagnostic_trace.get("source_rule_id") or "",
        "source_status": diagnostic_trace.get("source_status") or "",
        "source_conclusion": diagnostic_trace.get("source_conclusion") or "",
        "source_evidence": diagnostic_trace.get("source_evidence") or "",
        "trigger_decision": diagnostic_trace.get("trigger_decision") or {},
        "postprocess_reason": diagnostic_trace.get("postprocess_reason") or "",
    }
    return result


def safe_luxian_0609_customer_display_facts(
    *, rule_id: str, raw: Any
) -> dict[str, Any] | None:
    """旧原生分支只保留尚未迁移到通用子结论合同的受控展示事实。"""
    if not isinstance(raw, Mapping):
        return None
    if rule_id == "LX0609-048" and (
        raw.get("failure_kind") == "system_data_contract_gap"
        and raw.get("system_gap_reason")
        == "transfusion_comparison_fields_unavailable"
        and raw.get("gap_owner") == "system_integration"
    ):
        return {
            "failure_kind": "system_data_contract_gap",
            "system_gap_reason": "transfusion_comparison_fields_unavailable",
            "gap_owner": "system_integration",
        }
    if rule_id in {"LX0609-044", "LX0609-046", "LX0609-047", "LX0609-048"}:
        allowed = {
            "LX0609-044": (
                "pretransfusion_assessment",
                ["bloodtrans_record", "blood_application", "course_record"],
            ),
            "LX0609-046": ("purpose_or_indication", ["bloodtrans_record"]),
            "LX0609-047": (
                "posttransfusion_evaluation",
                ["bloodtrans_record", "course_record"],
            ),
            "LX0609-048": (
                "postop_first_course_transfusion",
                ["surgery_record", "postsurg_firstcourse_record"],
            ),
        }
        requirement, checked_sources = allowed[rule_id]
        if (
            raw.get("failure_kind") != "transfusion_requirement_not_documented"
            or raw.get("requirement") != requirement
            or raw.get("checked_sources") != checked_sources
        ):
            return None
        return {
            "failure_kind": "transfusion_requirement_not_documented",
            "requirement": requirement,
            "checked_sources": list(checked_sources),
        }
    if rule_id in {"LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"}:
        subject = raw.get("subject")
        requirement = raw.get("requirement")
        event_phase = raw.get("event_phase")
        checked_sources = raw.get("checked_sources")
        allowed_requirements = {
            "LX0609-010": "reason_before_order",
            "LX0609-011": "result_recording_within_24h",
            "LX0609-012": "positive_result_analysis_within_24h",
            "LX0609-014": "result_recording_within_24h",
            "LX0609-015": "positive_result_analysis_within_24h",
        }
        expected_subject = (
            "ct_mri" if rule_id in {"LX0609-010", "LX0609-011", "LX0609-012"}
            else "culture_susceptibility"
        )
        expected_phase = "order" if rule_id == "LX0609-010" else "report"
        expected_sources = (
            ["exam_lab_order", "course_record"]
            if rule_id == "LX0609-010"
            else ["exam_lab_report", "course_record"]
        )
        failure_kind = raw.get("failure_kind")
        verification_kind = raw.get("verification_kind")
        if (
            (
                failure_kind != "exam_lab_requirement_not_documented"
                and verification_kind != "exam_lab_requirement_checked"
            )
            or (failure_kind is not None and verification_kind is not None)
            or subject != expected_subject
            or requirement != allowed_requirements[rule_id]
            or event_phase != expected_phase
            or checked_sources != expected_sources
        ):
            return None
        facts: dict[str, Any] = {
            (
                "failure_kind" if failure_kind is not None else "verification_kind"
            ): (
                "exam_lab_requirement_not_documented"
                if failure_kind is not None
                else "exam_lab_requirement_checked"
            ),
            "subject": subject,
            "requirement": requirement,
            "event_phase": event_phase,
            "checked_sources": list(checked_sources),
        }
        optional_bool_fields = ("applicable", "requirement_met")
        for key in optional_bool_fields:
            value = raw.get(key)
            if value is not None:
                if not isinstance(value, bool):
                    return None
                facts[key] = value
        positive_state = raw.get("positive_state")
        if positive_state is not None:
            if positive_state not in {"positive", "negative", "not_relevant"}:
                return None
            facts["positive_state"] = positive_state
        for key in ("report_time", "response_record_time"):
            value = raw.get(key)
            if value is not None:
                if not isinstance(value, str) or not re.fullmatch(
                    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value
                ):
                    return None
                facts[key] = value
        threshold_hours = raw.get("threshold_hours")
        if threshold_hours is not None:
            if threshold_hours != 24:
                return None
            facts["threshold_hours"] = 24
        response_count = raw.get("response_record_count")
        if response_count is not None:
            if not isinstance(response_count, int) or response_count < 0:
                return None
            facts["response_record_count"] = response_count
        interval_hours = raw.get("interval_hours")
        if interval_hours is not None:
            if not isinstance(interval_hours, (int, float)) or interval_hours < 0:
                return None
            facts["interval_hours"] = round(float(interval_hours), 2)
        return facts
    if rule_id == "LX0609-013":
        trigger_sources = raw.get("pathology_trigger_sources")
        checked_sources = raw.get("checked_target_sources")
        if (
            raw.get("verification_kind")
            != "pathology_result_documentation_check"
            or not isinstance(trigger_sources, list)
            or not trigger_sources
            or any(
                value not in {"pathology_exam_master", "pathology_exam_report"}
                for value in trigger_sources
            )
            or not isinstance(checked_sources, list)
            or checked_sources
            != [
                {"source": "surgery_record", "state": checked_sources[0].get("state")}
                if len(checked_sources) > 0 and isinstance(checked_sources[0], Mapping)
                else {},
                {"source": "daily_course_record", "state": checked_sources[1].get("state")}
                if len(checked_sources) > 1 and isinstance(checked_sources[1], Mapping)
                else {},
            ]
            or any(
                item.get("state") not in {"present", "empty"}
                for item in checked_sources
            )
            or not isinstance(raw.get("requirement_met"), bool)
        ):
            return None
        facts = {
            "verification_kind": "pathology_result_documentation_check",
            "pathology_trigger_sources": list(dict.fromkeys(trigger_sources)),
            "checked_target_sources": [dict(item) for item in checked_sources],
            "requirement_met": raw["requirement_met"],
        }
        report_time = raw.get("report_time")
        if report_time is not None:
            if not isinstance(report_time, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", report_time
            ):
                return None
            facts["report_time"] = report_time
        return facts
    if rule_id == "LX0609-026":
        field_results = raw.get("field_results")
        missing_order_fields = raw.get("missing_order_fields")
        allowed_fields = {"drug_name", "dose", "route", "time"}
        if (
            raw.get("verification_kind")
            != "chemotherapy_order_course_comparison"
            or not isinstance(raw.get("order_count"), int)
            or raw.get("order_count") < 1
            or not isinstance(field_results, Mapping)
            or set(field_results) != allowed_fields
            or any(
                value not in {"matched", "mismatched", "unknown"}
                for value in field_results.values()
            )
            or not isinstance(missing_order_fields, list)
            or any(value not in allowed_fields for value in missing_order_fields)
        ):
            return None
        return {
            "verification_kind": "chemotherapy_order_course_comparison",
            "order_count": raw["order_count"],
            "field_results": {
                field: field_results[field]
                for field in ("drug_name", "dose", "route", "time")
            },
            "missing_order_fields": list(dict.fromkeys(missing_order_fields)),
        }
    if rule_id == "LX0609-027":
        plan_items = raw.get("plan_items")
        if (
            raw.get("verification_kind") != "malignant_discharge_plan_check"
            or raw.get("malignant_diagnosis_present") is not True
            or not isinstance(plan_items, Mapping)
            or set(plan_items) != {"future_plan", "tumor_treatment", "follow_up"}
            or any(not isinstance(value, bool) for value in plan_items.values())
            or not isinstance(raw.get("requirement_met"), bool)
        ):
            return None
        return {
            "verification_kind": "malignant_discharge_plan_check",
            "malignant_diagnosis_present": True,
            "plan_items": {
                key: plan_items[key]
                for key in ("future_plan", "tumor_treatment", "follow_up")
            },
            "requirement_met": raw["requirement_met"],
        }
    if rule_id == "LX0609-019":
        if raw.get("verification_kind") == "pathology_sampling_documentation_check":
            trigger_sources = raw.get("pathology_trigger_sources")
            checked_sources = raw.get("checked_target_sources")
            documented_sources = raw.get("documented_sources")
            if (
                not isinstance(trigger_sources, list)
                or not trigger_sources
                or any(
                    value not in {"pathology_exam_master", "pathology_exam_report"}
                    for value in trigger_sources
                )
                or not isinstance(checked_sources, list)
                or len(checked_sources) != 2
                or checked_sources
                != [
                    {
                        "source": "surgery_record",
                        "state": checked_sources[0].get("state"),
                    }
                    if isinstance(checked_sources[0], Mapping)
                    else {},
                    {
                        "source": "daily_course_record",
                        "state": checked_sources[1].get("state"),
                    }
                    if isinstance(checked_sources[1], Mapping)
                    else {},
                ]
                or any(
                    item.get("state") not in {"present", "empty"}
                    for item in checked_sources
                )
                or not isinstance(documented_sources, list)
                or not documented_sources
                or any(
                    value not in {"surgery_record", "daily_course_record"}
                    for value in documented_sources
                )
                or raw.get("requirement_met") is not True
            ):
                return None
            return {
                "verification_kind": "pathology_sampling_documentation_check",
                "pathology_trigger_sources": list(dict.fromkeys(trigger_sources)),
                "checked_target_sources": [dict(item) for item in checked_sources],
                "documented_sources": list(dict.fromkeys(documented_sources)),
                "requirement_met": True,
            }
        trigger_sources = raw.get("pathology_trigger_sources")
        checked_sources = raw.get("checked_target_sources")
        if (
            raw.get("failure_kind") != "pathology_sampling_not_documented"
            or not isinstance(trigger_sources, list)
            or not trigger_sources
            or not isinstance(checked_sources, list)
            or len(checked_sources) != 2
        ):
            return None
        safe_trigger_sources = list(
            dict.fromkeys(
                source
                for source in trigger_sources
                if source in {"pathology_exam_master", "pathology_exam_report"}
            )
        )
        if not safe_trigger_sources:
            return None
        safe_checked_sources: list[dict[str, str]] = []
        seen_sources: set[str] = set()
        for candidate in checked_sources:
            if not isinstance(candidate, Mapping):
                return None
            source = candidate.get("source")
            state = candidate.get("state")
            if (
                source not in {"surgery_record", "daily_course_record"}
                or state not in {"present", "empty"}
                or source in seen_sources
            ):
                return None
            seen_sources.add(source)
            safe_checked_sources.append({"source": source, "state": state})
        if seen_sources != {"surgery_record", "daily_course_record"}:
            return None
        return {
            "failure_kind": "pathology_sampling_not_documented",
            "pathology_trigger_sources": safe_trigger_sources,
            "checked_target_sources": safe_checked_sources,
        }
    if rule_id == "LX0609-024":
        checked_sources = raw.get("checked_sources")
        if (
            raw.get("failure_kind") != "lymph_node_dissection_not_documented"
            or raw.get("performed_surgery_confirmed") is not True
            or raw.get("malignant_surgery_confirmed") is not True
            or not isinstance(checked_sources, list)
        ):
            return None
        safe_checked_sources = list(
            dict.fromkeys(
                source
                for source in checked_sources
                if source
                in {
                    "surgery_record",
                    "pathology_exam_master",
                    "pathology_exam_report",
                }
            )
        )
        if not safe_checked_sources:
            return None
        return {
            "failure_kind": "lymph_node_dissection_not_documented",
            "performed_surgery_confirmed": True,
            "malignant_surgery_confirmed": True,
            "checked_sources": safe_checked_sources,
        }
    if rule_id == "LX0609-028":
        failure_kind = raw.get("failure_kind")
        start_time = raw.get("start_time")
        end_time = raw.get("end_time")
        duration_hours = raw.get("duration_hours")
        threshold_hours = raw.get("threshold_hours")
        if (
            failure_kind
            not in {
                "prophylaxis_duration_over_48h",
                "prophylaxis_extension_reason_missing",
            }
            or raw.get("incision_class") not in {"I", "II"}
            or not isinstance(start_time, str)
            or not isinstance(end_time, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", start_time)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", end_time)
            or not isinstance(duration_hours, (int, float))
            or duration_hours <= 24
            or threshold_hours not in {24, 48}
        ):
            return None
        if (
            failure_kind == "prophylaxis_duration_over_48h"
            and (threshold_hours != 48 or duration_hours <= 48)
        ):
            return None
        if (
            failure_kind == "prophylaxis_extension_reason_missing"
            and (threshold_hours != 24 or duration_hours > 48)
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "incision_class": raw.get("incision_class"),
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": round(float(duration_hours), 2),
            "threshold_hours": threshold_hours,
        }
    if rule_id in {"LX0609-034", "LX0609-035"}:
        checked_sources = raw.get("checked_sources")
        if (
            raw.get("failure_kind") != "anesthesia_consent_missing"
            or raw.get("performed_anesthesia_confirmed") is not True
            or raw.get("consent_state") != "missing"
            or checked_sources != ["consent_form"]
        ):
            return None
        return {
            "failure_kind": "anesthesia_consent_missing",
            "performed_anesthesia_confirmed": True,
            "consent_state": "missing",
            "checked_sources": ["consent_form"],
        }
    if rule_id in {"LX0609-036", "LX0609-037"}:
        missing_sources = raw.get("missing_visit_sources")
        if (
            raw.get("failure_kind") != "anesthesia_visit_missing"
            or raw.get("performed_anesthesia_confirmed") is not True
            or not isinstance(missing_sources, list)
        ):
            return None
        safe_sources = list(
            dict.fromkeys(
                source
                for source in missing_sources
                if source in {"preane_surveil_record", "postane_surveil_record"}
            )
        )
        if not safe_sources:
            return None
        return {
            "failure_kind": "anesthesia_visit_missing",
            "performed_anesthesia_confirmed": True,
            "missing_visit_sources": safe_sources,
        }
    if rule_id == "LX0609-039":
        checked_sources = raw.get("checked_sources")
        if (
            raw.get("failure_kind") != "preop_discussion_missing"
            or raw.get("performed_surgery_confirmed") is not True
            or raw.get("emergency_rescue_exception_absent") is not True
            or checked_sources != ["presurg_discussion"]
        ):
            return None
        return {
            "failure_kind": "preop_discussion_missing",
            "performed_surgery_confirmed": True,
            "emergency_rescue_exception_absent": True,
            "checked_sources": ["presurg_discussion"],
        }
    if rule_id == "LX0609-040":
        performed = raw.get("performed_surgery_confirmed")
        procedure_kind = raw.get("procedure_kind")
        effective_level = raw.get("effective_surgery_level")
        level_source = raw.get("surgery_level_source")
        discussion_state = raw.get("mdt_discussion_state")
        if (
            not isinstance(performed, bool)
            or procedure_kind not in {"surgery", "non_surgical_operation", "none", "unknown"}
            or (
                effective_level is not None
                and effective_level not in {"一级", "二级", "三级", "四级"}
            )
            or (
                level_source is not None
                and level_source
                not in {"hospital_performance", "national_catalog", "structured_field"}
            )
            or (
                discussion_state is not None
                and discussion_state not in {"completed", "missing", "unknown"}
            )
        ):
            return None
        facts: dict[str, Any] = {
            "performed_surgery_confirmed": performed,
            "procedure_kind": procedure_kind,
        }
        if effective_level is not None:
            facts["effective_surgery_level"] = effective_level
        if level_source is not None:
            facts["surgery_level_source"] = level_source
        if discussion_state is not None:
            facts["mdt_discussion_state"] = discussion_state
        return facts
    if rule_id == "LX0609-025":
        missing = raw.get("missing_fields")
        if not isinstance(missing, list):
            return None
        facts = {
            "failure_kind": "implant_information_incomplete",
            "source_label": "手术记录",
            "missing_fields": [
                value
                for value in missing
                if value in {
                    "implant_name", "implant_type", "implant_specification",
                    "implant_material", "implant_quantity", "implant_barcode",
                }
            ]
        }
        if not facts["missing_fields"]:
            return None
        return facts
    if rule_id == "LX0609-003":
        surgery_end_time = raw.get("surgery_end_time")
        record_time = raw.get("record_time")
        elapsed_hours = raw.get("elapsed_hours")
        if (
            raw.get("failure_kind") != "surgery_record_late"
            or raw.get("performed_surgery_confirmed") is not True
            or not isinstance(surgery_end_time, str)
            or not isinstance(record_time, str)
            or not isinstance(elapsed_hours, (int, float))
            or elapsed_hours <= 24
            or raw.get("threshold_hours") != 24
        ):
            return None
        return {
            "failure_kind": "surgery_record_late",
            "performed_surgery_confirmed": True,
            "surgery_end_time": surgery_end_time,
            "record_time": record_time,
            "elapsed_hours": round(float(elapsed_hours), 2),
            "threshold_hours": 24,
            "source_label": "手术记录",
        }
    if rule_id == "LX0609-033":
        failure_kind = raw.get("failure_kind")
        consent_state = raw.get("consent_state")
        valid_pairs = {
            ("surgery_consent_document_missing", "missing"),
            ("surgery_consent_body_missing", "blank"),
            ("surgery_consent_signature_missing", "signature_missing"),
            ("surgery_consent_source_unproven", "source_unproven"),
        }
        if (
            raw.get("performed_surgery_confirmed") is not True
            or (failure_kind, consent_state) not in valid_pairs
        ):
            return None
        facts: dict[str, Any] = {
            "failure_kind": failure_kind,
            "consent_state": consent_state,
            "performed_surgery_confirmed": True,
        }
        if consent_state == "signature_missing":
            roles = raw.get("missing_signature_roles")
            if not isinstance(roles, list):
                return None
            safe_roles = [role for role in roles if role in {"patient", "surgeon"}]
            if not safe_roles:
                return None
            facts["missing_signature_roles"] = safe_roles
        return facts
    if rule_id == "LX0609-007":
        failure_kind = raw.get("failure_kind")
        if failure_kind == "unstable_patient_order_present":
            return (
                {
                    "failure_kind": failure_kind,
                    "stable_course_rule_applicable": False,
                }
                if raw.get("stable_course_rule_applicable") is False
                else None
            )
        recorded_dates = raw.get("recorded_dates")
        interval_hours = raw.get("interval_hours")
        if (
            failure_kind
            not in {
                "course_record_interval_over_72h",
                "course_record_interval_within_72h",
            }
            or raw.get("interval_start_source")
            not in {"daily_course_record", "senior_course_record"}
            or raw.get("interval_end_source")
            not in {"daily_course_record", "senior_course_record"}
            or not all(
                isinstance(raw.get(key), str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", raw[key])
                for key in ("interval_start_time", "interval_end_time")
            )
            or not isinstance(interval_hours, (int, float))
            or raw.get("threshold_hours") != 72
            or not isinstance(recorded_dates, list)
            or len(recorded_dates) < 2
            or len(recorded_dates) > 64
            or not all(
                isinstance(value, str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                for value in recorded_dates
            )
            or (
                failure_kind == "course_record_interval_over_72h"
                and float(interval_hours) <= 72
            )
            or (
                failure_kind == "course_record_interval_within_72h"
                and float(interval_hours) > 72
            )
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "interval_start_source": raw["interval_start_source"],
            "interval_end_source": raw["interval_end_source"],
            "interval_start_time": raw["interval_start_time"],
            "interval_end_time": raw["interval_end_time"],
            "interval_hours": round(float(interval_hours), 2),
            "threshold_hours": 72,
            "recorded_dates": list(recorded_dates),
        }
    if rule_id == "LX0609-008":
        failure_kind = raw.get("failure_kind")
        allowed = {
            "failure_kind": failure_kind,
            "severity": "serious",
            "threshold_days": 2,
        }
        if failure_kind not in {
            "severity_course_gap_exceeded",
            "severity_course_interval_satisfied",
        }:
            return None
        dates = {
            key: raw.get(key) for key in ("anchor_date", "horizon_date")
        }
        recorded_dates = raw.get("recorded_dates")
        gap_days = raw.get("gap_days")
        if (
            any(raw.get(key) != value for key, value in allowed.items())
            or not all(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in dates.values())
            or (
                recorded_dates is not None
                and (
                    not isinstance(recorded_dates, list)
                    or len(recorded_dates) > 64
                    or not all(
                        isinstance(value, str)
                        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                        for value in recorded_dates
                    )
                )
            )
        ):
            return None
        if failure_kind == "severity_course_gap_exceeded":
            gap_dates = {
                key: raw.get(key) for key in ("gap_start_date", "gap_end_date")
            }
            if (
                not all(
                    isinstance(value, str)
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                    for value in gap_dates.values()
                )
                or not isinstance(gap_days, int)
                or gap_days <= 2
            ):
                return None
            facts = {
                **allowed,
                **dates,
                **gap_dates,
                "gap_days": gap_days,
            }
            if isinstance(recorded_dates, list):
                facts["recorded_dates"] = list(recorded_dates)
            return facts
        maximum_gap_days = raw.get("maximum_gap_days")
        if not isinstance(maximum_gap_days, int) or not 0 <= maximum_gap_days <= 2:
            return None
        return {
            **allowed,
            **dates,
            "maximum_gap_days": maximum_gap_days,
            "recorded_dates": list(recorded_dates),
        }
    if rule_id == "LX0609-009":
        scope_valid = (
            raw.get("evaluated_scope") == "critical_daily_course_coverage"
            and raw.get("pending_scope")
            == ["condition_change_course_documentation"]
        )
        if raw.get("failure_kind") == "critical_daily_record_coverage_satisfied":
            required_dates = raw.get("required_dates")
            covered_dates = raw.get("covered_dates")
            anchor_date = raw.get("anchor_date")
            horizon_date = raw.get("horizon_date")
            if (
                not scope_valid
                or raw.get("severity") != "critical"
                or raw.get("missing_count") != 0
                or not isinstance(required_dates, list)
                or not required_dates
                or not isinstance(covered_dates, list)
                or required_dates != covered_dates
                or not all(
                    isinstance(value, str)
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                    for value in required_dates
                )
                or not isinstance(anchor_date, str)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", anchor_date)
                or not isinstance(horizon_date, str)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", horizon_date)
            ):
                return None
            return {
                "failure_kind": "critical_daily_record_coverage_satisfied",
                "severity": "critical",
                "evaluated_scope": "critical_daily_course_coverage",
                "pending_scope": ["condition_change_course_documentation"],
                "anchor_date": anchor_date,
                "horizon_date": horizon_date,
                "required_dates": list(required_dates),
                "covered_dates": list(covered_dates),
                "missing_count": 0,
            }
        missing_dates = raw.get("missing_dates")
        required_dates = raw.get("required_dates")
        covered_dates = raw.get("covered_dates")
        missing_count = raw.get("missing_count")
        first_date = raw.get("missing_first_date")
        last_date = raw.get("missing_last_date")
        if (
            not scope_valid
            or raw.get("failure_kind") != "critical_daily_record_missing"
            or raw.get("severity") != "critical"
            or not isinstance(required_dates, list)
            or not isinstance(covered_dates, list)
            or not all(
                isinstance(value, str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                for value in (*required_dates, *covered_dates)
            )
            or not set(covered_dates).issubset(set(required_dates))
            or not isinstance(missing_dates, list)
            or not missing_dates
            or len(missing_dates) > 7
            or not all(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) for value in missing_dates)
            or not isinstance(missing_count, int)
            or missing_count < len(missing_dates)
            or not isinstance(first_date, str)
            or not isinstance(last_date, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", first_date)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_date)
        ):
            return None
        facts = {
            "failure_kind": "critical_daily_record_missing",
            "severity": "critical",
            "evaluated_scope": "critical_daily_course_coverage",
            "pending_scope": ["condition_change_course_documentation"],
            "required_dates": list(required_dates),
            "covered_dates": list(covered_dates),
            "missing_dates": list(missing_dates),
            "missing_count": missing_count,
            "missing_first_date": first_date,
            "missing_last_date": last_date,
        }
        for key in ("anchor_date", "horizon_date"):
            value = raw.get(key)
            if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                facts[key] = value
        return facts
    surgery_document_targets = {
        "LX0609-029": "presurg_summary",
        "LX0609-030": "surgery_record",
        "LX0609-032": "surgery_safecheck_record",
    }
    target_document = surgery_document_targets.get(rule_id)
    if target_document is not None:
        failure_kind = raw.get("failure_kind")
        if (
            rule_id == "LX0609-030"
            and raw.get("verification_kind") == "surgery_document_present"
            and raw.get("target_document") == target_document
            and raw.get("performed_surgery_confirmed") is True
        ):
            return {
                "verification_kind": "surgery_document_present",
                "target_document": target_document,
                "performed_surgery_confirmed": True,
            }
        if (
            failure_kind not in {"surgery_document_missing", "surgery_document_blank"}
            or raw.get("target_document") != target_document
            or raw.get("performed_surgery_confirmed") is not True
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "target_document": target_document,
            "performed_surgery_confirmed": True,
        }
    if rule_id == "LX0609-017":
        failure_kind = raw.get("failure_kind")
        source_types = raw.get("copy_document_sources")
        record_times = raw.get("copy_document_record_times")
        similarity = raw.get("copy_similarity")
        threshold = raw.get("copy_similarity_threshold")
        if (
            failure_kind
            not in {
                "copy_similarity_threshold_exceeded",
                "copy_similarity_within_threshold",
            }
            or not isinstance(source_types, list)
            or len(source_types) != 2
            or any(value not in {"daily_course_record", "senior_course_record"} for value in source_types)
            or not isinstance(record_times, list)
            or len(record_times) != 2
            or not all(isinstance(value, str) and value for value in record_times)
            or not isinstance(similarity, (int, float))
            or not isinstance(threshold, (int, float))
            or (
                failure_kind == "copy_similarity_threshold_exceeded"
                and float(similarity) <= float(threshold)
            )
            or (
                failure_kind == "copy_similarity_within_threshold"
                and float(similarity) > float(threshold)
            )
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "copy_similarity": round(float(similarity), 4),
            "copy_similarity_threshold": round(float(threshold), 4),
            "copy_document_sources": list(source_types),
            "copy_document_record_times": list(record_times),
        }
    if rule_id == "LX0609-068":
        failure_kind = raw.get("failure_kind")
        checked_dates = raw.get("checked_dates")
        approval_present = raw.get("approval_present")
        discharge_date = raw.get("discharge_date")
        if (
            failure_kind
            not in {
                "senior_discharge_approval_present",
                "senior_discharge_approval_missing",
            }
            or raw.get("checked_source") != "senior_course_record"
            or not isinstance(checked_dates, (list, tuple))
            or len(checked_dates) != 2
            or not all(
                isinstance(value, str)
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
                for value in checked_dates
            )
            or not isinstance(discharge_date, str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", discharge_date)
            or approval_present
            != (failure_kind == "senior_discharge_approval_present")
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "discharge_date": discharge_date,
            "checked_dates": list(checked_dates),
            "checked_source": "senior_course_record",
            "approval_present": approval_present,
        }
    if rule_id == "LX0609-016":
        similarity = raw.get("copy_similarity")
        relation = raw.get("copy_relation")
        sections = raw.get("compared_sections")
        source_document_ids = raw.get("source_document_ids")
        failure_kind = raw.get("failure_kind")
        if (
            failure_kind
            not in {
                "admission_first_course_copy_detected",
                "admission_first_course_not_identical",
            }
            or not isinstance(similarity, (int, float))
            or not 0 <= float(similarity) <= 1
            or relation
            not in {"completely_identical", "not_completely_identical"}
            or (relation == "completely_identical") != (float(similarity) == 1.0)
            or (failure_kind == "admission_first_course_copy_detected")
            != (relation == "completely_identical")
            or sections != ["入院记录现病史", "首次病程记录病例特点"]
            or not isinstance(source_document_ids, list)
        ):
            return None
        return {
            "failure_kind": failure_kind,
            "copy_similarity": round(float(similarity), 4),
            "copy_relation": relation,
            "compared_sections": list(sections),
            "source_document_ids": [
                value
                for value in dict.fromkeys(source_document_ids)
                if isinstance(value, str) and value.strip()
            ][:2],
        }
    if rule_id == "LX0609-023":
        missing_details = raw.get("missing_details")
        source_document_ids = raw.get("source_document_ids")
        if (
            raw.get("failure_kind") != "consultation_execution_too_generic"
            or raw.get("observed_expression") != "仅笼统记录已按会诊意见执行"
            or missing_details != ["具体执行措施", "执行结果或后续安排"]
            or not isinstance(source_document_ids, list)
        ):
            return None
        return {
            "failure_kind": "consultation_execution_too_generic",
            "observed_expression": "仅笼统记录已按会诊意见执行",
            "missing_details": list(missing_details),
            "source_document_ids": [
                value
                for value in dict.fromkeys(source_document_ids)
                if isinstance(value, str) and value.strip()
            ][:8],
        }
    basic_timeliness_targets = {
        "LX0609-001": "admission_record",
        "LX0609-002": "first_course_record",
        "LX0609-004": "rescue_record",
        "LX0609-005": "attending_course_record",
        "LX0609-006": "senior_course_record",
    }
    target_document = basic_timeliness_targets.get(rule_id)
    if target_document is not None:
        failure_kind = raw.get("failure_kind")
        state = raw.get("timeliness_state")
        threshold = raw.get("threshold_hours")
        source_label = raw.get("source_label")
        valid_state = (
            state in {"missing", "late"}
            if failure_kind == "timeliness_requirement_not_met"
            else state == "within"
        )
        if (
            failure_kind
            not in {
                "timeliness_requirement_not_met",
                "timeliness_requirement_satisfied",
            }
            or raw.get("target_document") != target_document
            or not valid_state
            or not isinstance(threshold, int)
            or threshold <= 0
            or not isinstance(source_label, str)
            or not source_label.strip()
        ):
            return None
        facts: dict[str, Any] = {
            "failure_kind": failure_kind,
            "target_document": target_document,
            "timeliness_state": state,
            "threshold_hours": threshold,
            "source_label": source_label.strip(),
        }
        for key in ("anchor_time", "anchor_date", "observed_time"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                facts[key] = value.strip()
        elapsed_hours = raw.get("elapsed_hours")
        if isinstance(elapsed_hours, (int, float)) and elapsed_hours >= 0:
            normalized_elapsed = round(float(elapsed_hours), 2)
            facts["elapsed_hours"] = normalized_elapsed
            if state == "late" and float(elapsed_hours) > threshold:
                facts["overdue_hours"] = round(
                    float(elapsed_hours) - threshold,
                    2,
                )
            elif state == "within":
                facts["remaining_hours"] = round(
                    max(0.0, threshold - float(elapsed_hours)),
                    2,
                )
        return facts
    return None


def _timeliness_customer_findings(
    *,
    rule_id: str,
    facts: Mapping[str, Any] | None,
) -> str:
    """从已白名单化的时限事实生成客户可直接核对的结论。"""

    if (
        rule_id != "LX0609-002"
        or not isinstance(facts, Mapping)
        or facts.get("failure_kind") != "timeliness_requirement_not_met"
        or facts.get("timeliness_state") != "late"
    ):
        return ""
    anchor_time = facts.get("anchor_time")
    observed_time = facts.get("observed_time")
    threshold_hours = facts.get("threshold_hours")
    elapsed_hours = facts.get("elapsed_hours")
    overdue_hours = facts.get("overdue_hours")
    if (
        not isinstance(anchor_time, str)
        or not anchor_time
        or not isinstance(observed_time, str)
        or not observed_time
        or not isinstance(threshold_hours, int)
        or not isinstance(elapsed_hours, (int, float))
        or not isinstance(overdue_hours, (int, float))
    ):
        return ""
    return (
        f"首次病程记录于入院后 {elapsed_hours:g} 小时完成"
        f"（入院时间 {anchor_time}；记录时间 {observed_time}），"
        f"超过 {threshold_hours} 小时要求 {overdue_hours:g} 小时。"
    )


def _customer_evidence_from_display_facts(
    *, rule_id: str, raw: Any
) -> list[dict[str, str]]:
    """将已验证的内部文书 ID 交给客户投影层做不可逆引用。

    此处不输出 ID 给客户；`custom_qc_workspace_service` 会统一将其 HMAC
    为 `src_…`，与文书列表中的安全引用一一对应。
    """

    if not isinstance(raw, Mapping):
        return []
    # 先复用展示事实白名单验证业务形态；内部 ID 只在此函数中转成
    # customer_evidence，绝不能进入 customer_display_facts。
    if safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw) is None:
        return []

    def valid_document_id(value: Any) -> str:
        candidate = str(value or "").strip()
        return (
            candidate
            if candidate
            and len(candidate) <= 256
            and "\n" not in candidate
            and "\r" not in candidate
            else ""
        )

    source_document_id = valid_document_id(raw.get("source_document_id"))
    single_source_types = {
        "LX0609-004": "rescue_record",
        "LX0609-005": "senior_course_record",
        "LX0609-006": "senior_course_record",
        "LX0609-025": "surgery_record",
        "LX0609-034": "anesthesia_record",
        "LX0609-036": "anesthesia_record",
    }
    source_type = single_source_types.get(rule_id)
    if rule_id == "LX0609-039":
        candidate = str(raw.get("source_document_type") or "").strip()
        source_type = (
            candidate
            if candidate in {"surgery_record", "mr_surgery"}
            else ""
        )
    if source_type and source_document_id:
        return [{"source_type": source_type, "source_document_id": source_document_id}]

    if rule_id not in {"LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"}:
        return []
    raw_ids = raw.get("source_document_ids")
    if not isinstance(raw_ids, list):
        return []
    document_ids = tuple(
        dict.fromkeys(
            candidate
            for value in raw_ids[:8]
            if (candidate := valid_document_id(value))
        )
    )
    # 这些来源行仅在显式存在 document_id 时进入此列表。类型无法可靠区分
    # 时统一按 document 交给病历对照页按 source_ref 精确解析，禁止猜测标题。
    return [
        {"source_type": "document", "source_document_id": document_id}
        for document_id in document_ids
    ]


def _guard_customer_explanation_result(result: dict[str, Any]) -> dict[str, Any]:
    """缺少可展示事实的不合规结果不得以泛化缺陷文案离开客户出口。"""

    if str(result.get("status") or "") != "non_compliant":
        return result
    evidence_items = result.get("evidence_items")
    has_locatable_evidence = isinstance(evidence_items, list) and any(
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
    if (
        result.get("criterion_results")
        or result.get("customer_display_facts")
        or has_locatable_evidence
    ):
        return result
    guarded_messages = {
        "LX0609-040": (
            "暂无法确认是否需要进行四级手术术前多学科讨论",
            "当前缺少明确的手术级别或可核对的多学科讨论资料，不能将本项作为确定问题展示。",
            "请确认手术级别、术前讨论记录及参加科室信息后重新评估。",
        ),
    }
    findings, evidence, suggestion = guarded_messages.get(
        str(result.get("rule_id") or ""),
        (
            "本次结果缺少规则专属、可核对的事实依据，暂不作为确定问题展示。",
            "未返回可展示的具体原因、核对标准或证据定位。",
            "请重新质控；如仍出现该提示，请补齐对应规则的受控事实和证据引用后再确认。",
        ),
    )
    guarded = dict(result)
    guarded.update(
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
    return guarded


def _valid_customer_evidence_document_id(value: Any) -> str:
    """仅允许内部已验证的文书 ID 进入后续安全签名环节。"""

    candidate = str(value or "").strip()
    return (
        candidate
        if candidate
        and len(candidate) <= 256
        and "\n" not in candidate
        and "\r" not in candidate
        else ""
    )


def _customer_evidence_from_reduced_decision(
    *,
    decision: ReducedRuleDecision,
    evidence_snapshot: Any,
    evidence_materials: Any,
) -> list[dict[str, str]]:
    """由 RuleDecision 的事实引用反查已存在的原始文书。

    所有原生规则复用这一条路径：只接受 decision 已引用的 FactV2，且 FactV2
    自身明确携带 ``source_document_id`` 时才输出。这里不猜标题、不以正文相似度
    选文书；真正不可逆的 ``src_…`` 引用仍由客户安全投影统一生成。
    """

    facts = getattr(evidence_snapshot, "facts", ())
    observations = getattr(evidence_snapshot, "observations", ())
    if not decision.fact_refs:
        return []
    referenced = set(decision.fact_refs)
    exact_source_keys = _EXACT_CUSTOMER_EVIDENCE_SOURCES_BY_RULE.get(
        str(decision.rule_id or "").strip().upper()
    )
    rows: list[dict[str, str]] = []
    seen_document_ids: set[str] = set()
    for fact in facts if isinstance(facts, tuple) else ():
        fact_id = str(getattr(fact, "fact_id", "") or "")
        source_snapshot_hash = str(
            getattr(fact, "source_snapshot_hash", "") or ""
        ).removeprefix("sha256:")
        if fact_id not in referenced and source_snapshot_hash not in referenced:
            continue
        document_id = _valid_customer_evidence_document_id(
            getattr(fact, "source_document_id", "")
        )
        source_type = str(getattr(fact, "source_key", "") or "").strip().lower()
        if (
            not document_id
            or document_id in seen_document_ids
            or not _SAFE_SOURCE_TYPE.fullmatch(source_type)
            or (exact_source_keys is not None and source_type not in exact_source_keys)
        ):
            continue
        seen_document_ids.add(document_id)
        rows.append(
            {
                "source_type": source_type,
                "source_document_id": document_id,
            }
        )
        if len(rows) >= 8:
            return rows

    # 一部分纯 Python 决策直接绑定来源快照而非 FactV2。例如 018 同时依赖
    # 入院记录和初步诊断；这时仅当该来源在同一 Evidence Session 内唯一对应一份
    # 原始文书，才可补出引用。多文书来源保持无引用，禁止猜测哪一份支持结论。
    source_keys: set[str] = set()
    if isinstance(observations, tuple):
        for observation in observations:
            snapshot_ref = str(
                getattr(observation, "snapshot_ref", "") or ""
            ).removeprefix("sha256:")
            if snapshot_ref in referenced:
                source_keys.add(
                    str(getattr(observation, "source_key", "") or "").strip().lower()
                )
    for source_key in sorted(source_keys):
        if (
            not _SAFE_SOURCE_TYPE.fullmatch(source_key)
            or (exact_source_keys is not None and source_key not in exact_source_keys)
        ):
            continue
        try:
            material_rows = tuple(evidence_materials.rows(source_key))
        except Exception:
            continue
        document_ids = tuple(
            dict.fromkeys(
                candidate
                for row in material_rows
                if isinstance(row, Mapping)
                for candidate in (
                    _valid_customer_evidence_document_id(
                        row.get("document_id") or row.get("id")
                    ),
                )
                if candidate
            )
        )
        if len(document_ids) != 1 or document_ids[0] in seen_document_ids:
            continue
        seen_document_ids.add(document_ids[0])
        rows.append(
            {"source_type": source_key, "source_document_id": document_ids[0]}
        )
        if len(rows) >= 8:
            break
    return rows


def _merge_customer_evidence(
    *groups: list[dict[str, str]],
) -> list[dict[str, str]]:
    """显式规则证据优先，通用 fact 反查只补足缺失引用。"""

    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            document_id = _valid_customer_evidence_document_id(
                item.get("source_document_id")
            )
            source_type = str(item.get("source_type") or "").strip().lower()
            if (
                not document_id
                or document_id in seen
                or not _SAFE_SOURCE_TYPE.fullmatch(source_type)
            ):
                continue
            seen.add(document_id)
            merged.append(
                {"source_type": source_type, "source_document_id": document_id}
            )
            if len(merged) >= 8:
                return merged
    return merged


def _copy_native_customer_fields(*, wrapper: dict[str, Any], selected: dict[str, Any]) -> dict[str, Any]:
    """原生结果不携带旧映射诊断，并保留程序/模型执行类型。"""
    wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
    status = _status(selected)
    if status not in {"compliant", "non_compliant", "not_applicable", "data_gap", "uncertain", "technical_error"}:
        status = "technical_error"
    selected_metadata = _strip_sensitive(dict(selected.get("metadata") or {}))
    metadata = {
        key: selected_metadata.get(key)
        for key in (
            "execution_source",
            "executor_type",
            "finding_kind",
            "source_state",
            "reason_code",
            "comparable_document_count",
            "maximum_similarity",
            "similarity_threshold",
            "best_match_source_types",
        )
        if key in selected_metadata
    }

    metadata["execution_source"] = "lx0609_native"
    metadata["aggregation_source"] = (
        "native_llm"
        if str(metadata.get("executor_type") or "").strip().lower() == "llm"
        else "native_programmatic"
    )
    metadata["customer_rule_id"] = wrapper_id
    result = {
        **_strip_sensitive(selected),
        "rule_id": wrapper_id,
        "rule_code": wrapper_id,
        "rule_name": str(wrapper.get("name") or wrapper.get("rule_name") or wrapper_id),
        "status": status,
        "is_compliant": status in {"compliant", "not_applicable"},
        "metadata": metadata,
        "diagnostic_trace": {},
        "source_rule_id": "",
        "source_status": str(metadata.get("source_state") or ""),
        "source_conclusion": "",
        "source_evidence": "",
        "trigger_decision": {},
        "postprocess_reason": str(metadata.get("reason_code") or ""),
    }
    display_facts = safe_luxian_0609_customer_display_facts(
        rule_id=wrapper_id,
        raw=selected_metadata.get("customer_display_facts"),
    )
    if display_facts:
        result["customer_display_facts"] = display_facts
    customer_evidence = _customer_evidence_from_display_facts(
        rule_id=wrapper_id,
        raw=(selected.get("metadata") or {}).get("customer_display_facts"),
    )
    if customer_evidence:
        result["customer_evidence"] = customer_evidence
    return result


def _index_reduced_decisions(
    *,
    wrapper_rules: list[dict[str, Any]],
    reduced_decisions: tuple[ReducedRuleDecision, ...],
) -> dict[str, ReducedRuleDecision]:
    if type(reduced_decisions) is not tuple or any(
        not isinstance(item, ReducedRuleDecision) for item in reduced_decisions
    ):
        raise TypeError("reduced_decisions must be a tuple of ReducedRuleDecision")
    wrapper_ids = tuple(
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in wrapper_rules
        if _norm_id(item.get("rule_id") or item.get("rule_code"))
    )
    if reduced_decisions and len(wrapper_ids) != len(set(wrapper_ids)):
        raise ValueError("duplicate customer wrapper scope")
    actual_ids = tuple(item.rule_id for item in reduced_decisions)
    if len(actual_ids) != len(set(actual_ids)):
        raise ValueError("duplicate reduced decision")
    if any(rule_id not in wrapper_ids for rule_id in actual_ids):
        raise ValueError("reduced decision is outside customer scope")
    actual_id_set = set(actual_ids)
    expected_order = tuple(rule_id for rule_id in wrapper_ids if rule_id in actual_id_set)
    if actual_ids != expected_order:
        raise ValueError("reduced decision order mismatch")
    return {item.rule_id: item for item in reduced_decisions}


def aggregate_luxian_0609_results(
    *,
    wrapper_rules: list[dict[str, Any]],
    execution_results: list[dict[str, Any]],
    gate_decisions: dict[str, Luxian0609GateDecision] | None = None,
    format_evidence: bool = True,
    audit_context: dict[str, Any] | None = None,
    reduced_decisions: tuple[ReducedRuleDecision, ...] = (),
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = (),
    decision_trace_sink: DecisionTraceSink | None = None,
) -> list[dict[str, Any]]:
    # 延迟加载避免聚合器导入时触发 luxian_0609 包的公开 re-export，
    # 从而与 customer_rule_package 形成循环依赖。
    from .luxian_0609.customer_renderer import render_luxian_0609_customer_result

    reduced_by_rule = _index_reduced_decisions(
        wrapper_rules=wrapper_rules,
        reduced_decisions=reduced_decisions,
    )
    display_facts_by_rule: dict[str, dict[str, Any]] = {}
    customer_evidence_by_rule: dict[str, list[dict[str, str]]] = {}
    wrapper_rule_ids = {
        _norm_id(item.get("rule_id") or item.get("rule_code"))
        for item in wrapper_rules
    }
    for rule_id, facts in customer_display_facts:
        if (
            rule_id in display_facts_by_rule
            or rule_id not in wrapper_rule_ids
            or not isinstance(facts, Mapping)
        ):
            raise ValueError("invalid customer display facts scope")
        display_facts_by_rule[rule_id] = (
            safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=facts)
            or _strip_sensitive(dict(facts))
        )
        customer_evidence = _customer_evidence_from_display_facts(
            rule_id=rule_id,
            raw=facts,
        )
        if customer_evidence:
            customer_evidence_by_rule[rule_id] = customer_evidence
    result_by_rule: dict[str, list[dict[str, Any]]] = {}
    for item in execution_results:
        key = _norm_id(item.get("rule_id") or item.get("rule_code"))
        if key in reduced_by_rule:
            continue
        if key:
            result_by_rule.setdefault(key, []).append(dict(item))

    customer_results: list[dict[str, Any]] = []
    decisions = gate_decisions or {}
    for wrapper in wrapper_rules:
        wrapper_id = _norm_id(wrapper.get("rule_id") or wrapper.get("rule_code"))
        if not wrapper_id:
            continue
        reduced = reduced_by_rule.get(wrapper_id)
        if reduced is not None:
            result = render_luxian_0609_customer_result(
                decision=reduced,
                trace_sink=decision_trace_sink,
            )
            if wrapper_id in display_facts_by_rule:
                result["customer_display_facts"] = display_facts_by_rule[wrapper_id]
                precise_findings = _timeliness_customer_findings(
                    rule_id=wrapper_id,
                    facts=display_facts_by_rule[wrapper_id],
                )
                if precise_findings:
                    result["findings"] = precise_findings
            decision_evidence = _customer_evidence_from_reduced_decision(
                decision=reduced,
                evidence_snapshot=(audit_context or {}).get("evidence_snapshot"),
                evidence_materials=(audit_context or {}).get("evidence_materials"),
            )
            customer_evidence = _merge_customer_evidence(
                customer_evidence_by_rule.get(wrapper_id, []),
                decision_evidence,
            )
            if customer_evidence:
                result["customer_evidence"] = customer_evidence
            result = _guard_customer_explanation_result(result)
            customer_results.append(result)
            continue
        decision = decisions.get(wrapper_id)
        gate_result = None
        if decision and (
            decision.status == TRIGGER_ABSENT
            or (wrapper_id == "LX0609-016" and decision.status == TRIGGER_DATA_GAP)
        ):
            gate_result = decision_to_result(wrapper, decision)
            if gate_result is not None:
                result = _copy_customer_fields(
                    wrapper=wrapper,
                    selected=gate_result,
                    mapped_results=[],
                    source="trigger_gate",
                    gate_decision=decision,
                )
                if format_evidence:
                    result = format_luxian_0609_evidence(
                        result=result,
                        wrapper_rule=wrapper,
                        gate_decision=decision,
                    )
                result = apply_luxian_0609_result_schema(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                    audit_context=audit_context,
                )
                customer_results.append(result)
                continue

        direct_results = list(result_by_rule.get(wrapper_id) or [])
        if direct_results:
            direct_results.sort(
                # 同一客户规则同时存在原生结果和兼容映射结果时，原生结果是
                # 唯一可用的客户结论来源。不能让遗留 LLM 的置信度覆盖原生
                # 受控事实（例如 018 的字数、诊断指向两个子结论）。
                key=lambda item: (
                    str((item.get("metadata") or {}).get("execution_source") or "")
                    == "lx0609_native",
                    _confidence(item.get("confidence")),
                    _norm_id(item.get("rule_id")),
                ),
                reverse=True,
            )
            selected = direct_results[0]
            if str((selected.get("metadata") or {}).get("execution_source") or "") == "lx0609_native":
                result = _copy_native_customer_fields(wrapper=wrapper, selected=selected)
                if wrapper_id in display_facts_by_rule:
                    result["customer_display_facts"] = display_facts_by_rule[wrapper_id]
                    precise_findings = _timeliness_customer_findings(
                        rule_id=wrapper_id,
                        facts=display_facts_by_rule[wrapper_id],
                    )
                    if precise_findings:
                        result["findings"] = precise_findings
                if wrapper_id in customer_evidence_by_rule:
                    result["customer_evidence"] = customer_evidence_by_rule[wrapper_id]
                native_audit_context = {
                    key: value
                    for key, value in dict(audit_context or {}).items()
                    if key not in {"visit_id", "patient_id", "evidence_payload"}
                }
                result = apply_luxian_0609_result_schema(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                    audit_context=native_audit_context,
                )
                native_audit = dict(result.get("audit") or {})
                for internal_key in (
                    "visit_id",
                    "patient_id",
                    "model_name",
                    "prompt_version",
                    "error_message",
                ):
                    native_audit.pop(internal_key, None)
                result["audit"] = native_audit
                result = _guard_customer_explanation_result(result)
                customer_results.append(result)
                continue
            selected = _guard_copy_rule_without_first_course(
                wrapper_id=wrapper_id,
                selected=selected,
                audit_context=audit_context,
            )
            selected = _apply_copy_compare_evidence_for_lx017(
                wrapper_id=wrapper_id,
                selected=selected,
                audit_context=audit_context,
            )
            selected = _guard_customer_display_result(
                wrapper_id=wrapper_id,
                selected=selected,
                audit_context=audit_context,
            )
            source = "customer_programmatic"
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=selected,
                mapped_results=direct_results,
                source=source,
                gate_decision=decision,
            )
            result = _guard_customer_display_result(
                wrapper_id=wrapper_id,
                selected=result,
                audit_context=audit_context,
            )
            if format_evidence:
                result = format_luxian_0609_evidence(
                    result=result,
                    wrapper_rule=wrapper,
                    gate_decision=decision,
                )
            result = apply_luxian_0609_result_schema(
                result=result,
                wrapper_rule=wrapper,
                gate_decision=decision,
                audit_context=audit_context,
            )
            result = _guard_customer_explanation_result(result)
            customer_results.append(result)
            continue
        if decision and decision.status in {TRIGGER_ABSENT, TRIGGER_DATA_GAP}:
            gate_result = decision_to_result(wrapper, decision)
        if gate_result is not None:
            source = "trigger_gate"
            mapped_results: list[dict[str, Any]] = []
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=gate_result,
                mapped_results=mapped_results,
                source=source,
                gate_decision=decision,
            )
        else:
            mapped_rule_ids = [_norm_id(item) for item in list(wrapper.get("mapped_rule_ids") or []) if _norm_id(item)]
            mapped_results = []
            for rule_id in mapped_rule_ids:
                mapped_results.extend(result_by_rule.get(rule_id) or [])
            selected, source = _select_best_result(
                mapped_results=mapped_results,
                primary_rule_id=_norm_id(wrapper.get("primary_execution_rule_id")),
            )
            if selected is None:
                selected = {
                    "rule_id": wrapper_id,
                    "rule_name": str(wrapper.get("name") or wrapper_id),
                    "status": "uncertain",
                    "is_compliant": False,
                    "findings": "当前自动判定未形成可靠结论，建议质控员确认。",
                    "evidence": "",
                    "suggestion": "请质控员结合相关病历文书和诊疗记录确认；必要时重新执行质控。",
                    "confidence": 0.0,
                    "metadata": {"technical_error_internal": True},
                }
            else:
                selected = _guard_copy_rule_without_first_course(
                    wrapper_id=wrapper_id,
                    selected=selected,
                    audit_context=audit_context,
                )
                selected = _apply_copy_compare_evidence_for_lx017(
                    wrapper_id=wrapper_id,
                    selected=selected,
                    audit_context=audit_context,
                )
                selected = _guard_customer_display_result(
                    wrapper_id=wrapper_id,
                    selected=selected,
                    audit_context=audit_context,
                )
            result = _copy_customer_fields(
                wrapper=wrapper,
                selected=selected,
                mapped_results=mapped_results,
                source=source,
                gate_decision=decision,
            )
            result = _guard_customer_display_result(
                wrapper_id=wrapper_id,
                selected=result,
                audit_context=audit_context,
            )

        if format_evidence:
            result = format_luxian_0609_evidence(
                result=result,
                wrapper_rule=wrapper,
                gate_decision=decision,
            )
        result = apply_luxian_0609_result_schema(
            result=result,
            wrapper_rule=wrapper,
            gate_decision=decision,
            audit_context=audit_context,
        )
        result = _guard_customer_explanation_result(result)
        customer_results.append(result)
    return customer_results


def summarize_luxian_0609_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {status: 0 for status in CANONICAL_RESULT_STATUSES}
    for item in results:
        status = _status(item)
        status_counts[status] = int(status_counts.get(status) or 0) + 1
    total = len(results)
    not_applicable = int(status_counts.get("not_applicable") or 0)
    data_gap = int(status_counts.get("data_gap") or 0)
    not_executed = int(status_counts.get("not_executed") or 0)
    technical_error = int(status_counts.get("technical_error") or 0)
    compliance_denominator = max(0, total - not_applicable - data_gap - not_executed - technical_error)
    compliant = int(status_counts.get("compliant") or 0)
    ai_suggested_non_compliant = int(status_counts.get("ai_suggested_non_compliant") or 0)
    ai_suggested_compliant = int(status_counts.get("ai_suggested_compliant") or 0)
    compliance_rate = round((compliant / compliance_denominator * 100.0), 2) if compliance_denominator else 100.0
    return {
        "customer_rule_count": total,
        "status_counts": status_counts,
        "defect_count": int(status_counts.get("non_compliant") or 0),
        "ai_suggested_non_compliant_count": ai_suggested_non_compliant,
        "ai_suggested_compliant_count": ai_suggested_compliant,
        "not_applicable_count": not_applicable,
        "data_gap_count": data_gap,
        "uncertain_count": int(status_counts.get("uncertain") or 0),
        "not_executed_count": not_executed,
        "technical_error_count": technical_error,
        "compliant_count": compliant + ai_suggested_compliant,
        "compliance_denominator": compliance_denominator,
        "compliance_rate": compliance_rate,
    }
