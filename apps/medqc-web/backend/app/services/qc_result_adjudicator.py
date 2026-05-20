from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from .formal_qc_rule_criteria import (
    get_rule_specific_criteria,
    rule_criteria_metadata,
)


AdjudicatorGenerateFn = Callable[[str], Awaitable[dict[str, Any]]]

TERMINAL_DISPLAY_STATUSES = {
    "confirmed_defect",
    "data_quality_gap",
    "rejected_by_system",
    "technical_error_internal",
}
BOUNDARY_DISPLAY_STATUSES = {"qc_review_candidate", "needs_review", "rejected_by_system"}
DISPLAY_BUCKET_BY_STATUS = {
    "confirmed_defect": "确认缺陷",
    "data_quality_gap": "数据缺口",
    "rejected_by_system": "系统驳回",
    "technical_error_internal": "内部技术异常",
}
LABEL_BY_STATUS = {
    "confirmed_defect": "likely_valid",
    "data_quality_gap": "data_gap_not_defect",
    "rejected_by_system": "rejected_by_system",
    "technical_error_internal": "technical_error",
}
CONFIRMED_QUOTE_MIN_LEN = 18
ADJUDICATOR_MISSING_RETRY_CHUNK_SIZE = 5
TARGETED_COVERAGE_GUARDRAIL_RULES = {"SC-019", "SC-083", "SC-099", "SC-100", "SC-101"}
CONTEXT_MATRIX_GUARDRAIL_RULES = {"SC-012", "SC-013", "SC-034", "SC-118", "SC-121", "SC-122"}
NEGATIVE_ONLY_TERMS = ("未见", "缺失", "未提供", "未记录", "没有")
HEADER_ONLY_TERMS = (
    "记录时间",
    "文书名称",
    "标题",
    "手术医生签名",
    "术前诊断",
    "术中诊断",
    "切口愈合等级",
    "手术简要经过",
    "术后处理措施",
    "术后注意事项",
)
DATA_GAP_TERMS = (
    "缺文书",
    "缺源",
    "缺报告",
    "缺医嘱",
    "缺执行",
    "缺少",
    "无法判定",
    "未提供",
    "证据不足",
    "数据缺口",
    "覆盖不足",
    "缺少必要",
)
SEMANTIC_REJECTION_TECHNICAL_TERMS = (
    "错配",
    "错误匹配",
    "逻辑映射错误",
    "规则无关",
    "规则不适用",
    "文书无关",
    "完全无关",
    "引用错误",
    "与长期医嘱单格式无关",
    "证据片段为病程记录",
)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def _normalize_rule_id(value: Any) -> str:
    return _safe_text(value).upper()


def _normalize_rule_code(value: Any) -> str:
    text = _safe_text(value).upper()
    text = text.replace("－", "-").replace("—", "-").replace("–", "-").replace("_", "-")
    text = re.sub(r"\s+", "", text)
    match = re.search(r"(SC)-?0*([0-9]{1,3})", text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):03d}"
    return text


def _contains_any(text: str, terms: tuple[str, ...] | list[str] | set[str]) -> bool:
    return any(term and term in text for term in terms)


def _quote_is_record_time_only(text: str) -> bool:
    clean = re.sub(r"[\s:：,，;；\-_/年月日时分秒0-9]", "", _safe_text(text))
    return clean in {"记录时间", "时间记录"} or clean.startswith("记录时间")


def _quote_is_header_or_empty_fragment(text: str) -> bool:
    raw = _safe_text(text)
    raw = re.sub(r"(?i)\bsource_snippet\b[:：]\s*", "", raw)
    compact = re.sub(r"\s+", "", raw)
    if not compact:
        return True
    if _quote_is_record_time_only(raw):
        return True
    if len(compact) < CONFIRMED_QUOTE_MIN_LEN:
        return True
    if ("..." in raw or "…" in raw) and len(compact) < 80:
        return True
    if re.search(r"患者.{0,8}性别.{0,8}年龄.{0,12}以[“\"]?", compact) and len(compact) < 70:
        return True
    label_hits = sum(1 for term in HEADER_ONLY_TERMS if term in compact)
    content_after_labels = re.sub(
        r"(记录时间|文书名称|标题|手术医生签名|术前诊断|术中诊断|切口愈合等级|手术简要经过(?:\(术中所见\))?|术后处理措施|术后注意事项)[:：]?",
        "",
        compact,
    )
    content_after_labels = re.sub(r"[。；;:：,，\-.、\d年月日时分秒/\s]", "", content_after_labels)
    if label_hits and len(content_after_labels) < 12:
        return True
    return False


def _semantic_technical_error_should_be_rejected(reason: str, quote: str) -> bool:
    """二审偶尔把一审语义误判标成 technical_error；这类不应污染稳定性统计。"""
    combined = f"{_safe_text(reason)} {_safe_text(quote)}"
    if not combined.strip():
        return False
    return _contains_any(combined, SEMANTIC_REJECTION_TECHNICAL_TERMS)


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("metadata")
    return dict(value) if isinstance(value, dict) else {}


def _coverage_flags(item: dict[str, Any]) -> dict[str, Any]:
    metadata = _metadata(item)
    value = metadata.get("formal_evidence_coverage")
    if isinstance(value, dict):
        return dict(value)
    context = metadata.get("targeted_evidence_context")
    if isinstance(context, dict) and isinstance(context.get("coverage_flags"), dict):
        return dict(context.get("coverage_flags") or {})
    value = item.get("formal_evidence_coverage")
    return dict(value) if isinstance(value, dict) else {}


def _gate_metadata(item: dict[str, Any]) -> dict[str, Any]:
    direct = item.get("applicability_gate_metadata")
    if isinstance(direct, dict):
        return dict(direct)
    metadata = _metadata(item)
    nested = metadata.get("applicability_gate_metadata")
    return dict(nested) if isinstance(nested, dict) else {}


def _targeted_evidence_context(item: dict[str, Any]) -> dict[str, Any]:
    metadata = _metadata(item)
    context = metadata.get("targeted_evidence_context")
    return dict(context) if isinstance(context, dict) else {}


def _context_evidence_texts(context: dict[str, Any], key: str) -> list[str]:
    value = context.get(key)
    if not isinstance(value, list):
        return []
    texts: list[str] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        text = _safe_text(row.get("evidence_text") or row.get("source_quote") or row.get("text"))
        if text:
            texts.append(text)
    return texts


def _context_texts_by_keys(context: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    texts: list[str] = []
    for key in keys:
        texts.extend(_context_evidence_texts(context, key))
    return texts


def _has_any_term(text: str, terms: tuple[str, ...] | list[str] | set[str]) -> bool:
    compact = _safe_text(text)
    return any(term and term in compact for term in terms)


def _matrix_terms(text: str, terms: tuple[str, ...] | list[str] | set[str]) -> bool:
    return _has_any_term(text, terms)


def _matrix_missing_fields(matrix: dict[str, bool]) -> list[str]:
    return [key for key, value in matrix.items() if not value]


def _apply_context_matrix_metadata(item: dict[str, Any], result: dict[str, Any]) -> None:
    payload = {
        "confirmed_context_matrix_rule": result.get("rule"),
        "confirmed_context_document_type": result.get("document_type"),
        "confirmed_context_section": result.get("section"),
        "confirmed_context_matrix": result.get("matrix") or {},
        "confirmed_context_matrix_complete": bool(result.get("matrix_complete")),
        "confirmed_blocked_reason": result.get("blocked_reason") or "",
        "policy_pending_flags": result.get("policy_pending_flags") or [],
    }
    item.update(payload)
    metadata = item.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        item["metadata"] = metadata
    metadata.update(payload)


def _truncate(value: Any, limit: int = 900) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _truncate_jsonable(value: Any, *, limit: int = 3000) -> Any:
    """Keep adjudicator prompt bounded while preserving structured evidence."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate(value, limit)
    if isinstance(value, list):
        result: list[Any] = []
        budget = limit
        for item in value[:12]:
            compact = _truncate_jsonable(item, limit=max(120, budget // 2))
            result.append(compact)
            budget -= len(json.dumps(compact, ensure_ascii=False, default=str))
            if budget <= 0:
                break
        return result
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        budget = limit
        for key, item in value.items():
            key_text = _safe_text(key)
            compact = _truncate_jsonable(item, limit=max(120, budget // 2))
            result[key_text] = compact
            budget -= len(key_text) + len(json.dumps(compact, ensure_ascii=False, default=str))
            if budget <= 0:
                break
        return result
    return _truncate(value, limit)


def _extract_llm_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            return _safe_text(message.get("content"))
        return _safe_text(choices[0].get("text") if isinstance(choices[0], dict) else choices[0])
    return _safe_text(response.get("content") or response.get("text") or response.get("output"))


def _extract_json_object(text: str) -> dict[str, Any]:
    clean = _safe_text(text)
    if not clean:
        return {}
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", clean, flags=re.IGNORECASE)
    if fenced:
        clean = fenced.group(1).strip()
    try:
        payload = json.loads(clean)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end > start:
        try:
            payload = json.loads(clean[start : end + 1])
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}
    return {}


def _rule_requirement(rule: dict[str, Any]) -> str:
    parts = [
        rule.get("rule_id") or rule.get("rule_code"),
        rule.get("name") or rule.get("rule_name"),
        rule.get("description"),
        rule.get("check_requirement") or rule.get("requirement"),
        rule.get("quality_point") or rule.get("content"),
    ]
    return "\n".join(_safe_text(item) for item in parts if _safe_text(item))


def _collect_context_text_stats(targeted_context: Any) -> dict[str, Any]:
    if not isinstance(targeted_context, dict):
        return {}

    def _extract_texts(value: Any) -> list[str]:
        if isinstance(value, str):
            return [_safe_text(value)]
        if isinstance(value, dict):
            return [
                _safe_text(
                    value.get("evidence_text")
                    or value.get("content")
                    or value.get("text")
                    or value.get("quote")
                    or ""
                )
            ]
        if isinstance(value, list):
            texts: list[str] = []
            for item in value:
                texts.extend(_extract_texts(item))
            return texts
        return []

    discharge_text = "\n".join(_extract_texts(targeted_context.get("discharge_record_evidence")))
    admission_text = "\n".join(_extract_texts(targeted_context.get("admission_record_evidence")))
    present_illness_text = "\n".join(_extract_texts(targeted_context.get("present_illness_evidence")))
    past_history_text = "\n".join(_extract_texts(targeted_context.get("past_history_evidence")))
    discharge_compact = re.sub(r"\s+", "", discharge_text)
    admission_compact = re.sub(r"\s+", "", admission_text or present_illness_text or past_history_text)
    return {
        "discharge_record_context_char_count": len(discharge_compact),
        "discharge_record_context_near_full": len(discharge_compact) >= 500,
        "discharge_record_has_treatment_course_marker": any(
            term in discharge_text for term in ("诊疗经过", "治疗经过", "治疗上", "予以", "给予")
        ),
        "discharge_record_has_advice_marker": any(term in discharge_text for term in ("出院医嘱", "出院指导", "随访", "复查")),
        "admission_context_char_count": len(admission_compact),
        "admission_context_near_full": len(admission_compact) >= 400,
        "context_hint_note": (
            "targeted_evidence_context contains near-full source context; "
            "do not treat short item.evidence/supporting_quote as truncated if it can link back to this context."
        ),
    }


def _chunked(values: list[int], size: int) -> list[list[int]]:
    if size <= 0:
        return [values]
    return [values[index : index + size] for index in range(0, len(values), size)]


def _candidate_payload(item: dict[str, Any], rule: dict[str, Any] | None, index: int) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    targeted_context = metadata.get("targeted_evidence_context")
    coverage = metadata.get("formal_evidence_coverage")
    rule_id = _safe_text(item.get("rule_id"))
    criteria = get_rule_specific_criteria(rule_id)
    return {
        "index": index,
        "rule_id": rule_id,
        "rule_name": _safe_text(item.get("rule_name")),
        "first_pass_status": _safe_text(item.get("status")),
        "first_pass_display_status": _safe_text(item.get("display_status")),
        "findings": _truncate(item.get("findings"), 700),
        "evidence": _truncate(item.get("evidence"), 900),
        "suggestion": _truncate(item.get("suggestion"), 500),
        "confidence": item.get("confidence"),
        "evidence_problem_type": _safe_text(item.get("evidence_problem_type")),
        "target_document_type": _safe_text(item.get("target_document_type") or item.get("document_type")),
        "rule_requirement": _truncate(_rule_requirement(rule or {}), 900),
        "pack_id": _safe_text(item.get("pack_id") or metadata.get("pack_id")),
        "formal_evidence_coverage": _truncate_jsonable(coverage, limit=1200) if isinstance(coverage, dict) else {},
        "rule_specific_criteria": _truncate_jsonable(criteria, limit=2600) if criteria else {},
        "rule_context_coverage_hint": _collect_context_text_stats(targeted_context),
        "targeted_evidence_context": (
            _truncate_jsonable(targeted_context, limit=3200) if isinstance(targeted_context, dict) else {}
        ),
        "source_snippet": _truncate(
            item.get("evidence")
            or item.get("anchor_evidence")
            or metadata.get("source_snippet")
            or "",
            900,
        ),
    }


def _build_adjudicator_prompt(
    candidates: list[dict[str, Any]],
    *,
    retry_missing_rule_ids: list[str] | None = None,
) -> str:
    expected_rule_ids = [_normalize_rule_code(item.get("rule_id")) for item in candidates]
    payload = json.dumps(
        {
            "expected_rule_ids": expected_rule_ids,
            "items": candidates,
        },
        ensure_ascii=False,
        indent=2,
    )
    retry_note = ""
    if retry_missing_rule_ids:
        retry_note = (
            "\n这是缺失补裁请求。上一轮二审响应遗漏了部分 expected_rule_ids。"
            f"本轮只允许返回这些缺失规则：{json.dumps(retry_missing_rule_ids, ensure_ascii=False)}。"
            "不要返回其他规则。"
        )
    return f"""你是正式病历质控结果二审裁决器。请基于规则要求、第一轮 LLM 输出和证据片段独立裁决，不要把边界项推给人工。

只能输出 JSON，不要输出 Markdown。
必须逐一返回 expected_rule_ids 中每个 rule_id 的裁决，不允许省略，不允许只返回异常项。{retry_note}
终态只允许：
- confirmed_defect：规则核心要件成立，evidence 可直接支撑缺陷。
- data_quality_gap：缺少必要源文书、检查检验、医嘱、会诊、执行记录等，不能归咎医生。
- rejected_by_system：证据不足、结论自相矛盾、仅凭推测、规则要件不成立，或 evidence 支持合规。
- technical_error_internal：第一轮/二审存在 provider、解析、超时等技术异常。

严禁输出“待人工确认”“建议复核”“qc_review_candidate”等终态。

专项适用性口径：
- SC-099 仅在 formal_evidence_coverage.has_specimen_or_pathology_trigger=true 且可引用取材/送病理/活检/标本等触发片段时，才可能 confirmed_defect；无触发时应 rejected_by_system，缺病理来源时应 data_quality_gap。
- SC-100 仅在 has_implant_trigger=true 且条码/追溯码来源域可核时，才可能 confirmed_defect；有植入物但缺耗材/条码来源时应 data_quality_gap。
- SC-101 仅在 has_implant_trigger=true 且 implant_detail_completeness=none 时，才可能 confirmed_defect；partial 表示已有部分植入物种类/数量记录，不能直接确认“未记录”。

规则专属判定标准：
- 若 item.rule_specific_criteria 非空，必须优先遵守其中 required_document、required_section、required_fields、confirmed_conditions、not_confirmed_conditions、data_quality_gap_conditions。
- SC-012/SC-013 只评价入院记录对应段落；缺完整入院记录上下文时 data_quality_gap。
- SC-034 confirmed 必须同时有病情/治疗/医嘱变化事件与缺少分析/处理依据的证据；仅症状 + 对症处理不得 confirmed。
- SC-118/SC-121 必须基于完整或近完整出院记录字段矩阵；若 item.rule_context_coverage_hint.discharge_record_context_near_full=true，不能只因 item.evidence/supporting_quote 较短就转 data_quality_gap，必须结合 targeted_evidence_context.discharge_record_evidence 判断具体缺失字段。
- SC-121 若缺陷并非“主要药品名称缺失”，has_discharge_medication_text=false 不得一票否决 confirmed。
- SC-122 必须基于完整出院医嘱段；只有随访/复查/局部建议片段时 data_quality_gap。
- SC-123 必须先确认存在出院带药/出院用药；非药品出院医嘱不得当出院带药，字段完整时 rejected_by_system。

输出格式：
{{
  "items": [
    {{
      "index": 0,
      "rule_id": "SC-xxx",
      "adjudicated_display_status": "confirmed_defect|data_quality_gap|rejected_by_system|technical_error_internal",
      "adjudicator_reason": "简短裁决理由",
      "adjudicator_supporting_quote": "最能支撑裁决的原文短引；没有则为空",
      "adjudicator_confidence": 0.0,
      "rule_requirement_match": "matched|not_matched|data_gap|technical_error"
    }}
  ]
}}

待裁决项目：
{payload}
"""


def _normalize_adjudicated_status(value: Any) -> str:
    status = _safe_text(value).lower()
    if status in TERMINAL_DISPLAY_STATUSES:
        return status
    return "rejected_by_system"


def _apply_adjudication(
    item: dict[str, Any],
    adjudication: dict[str, Any],
    *,
    fallback_reason: str = "",
) -> dict[str, Any]:
    next_item = dict(item)
    first_pass_status = _safe_text(next_item.get("status"))
    first_pass_display_status = _safe_text(next_item.get("display_status"))
    status = _normalize_adjudicated_status(adjudication.get("adjudicated_display_status"))
    reason = _safe_text(adjudication.get("adjudicator_reason") or fallback_reason)
    quote = _safe_text(adjudication.get("adjudicator_supporting_quote"))
    confidence = _safe_float(adjudication.get("adjudicator_confidence"), 0.0)
    match = _safe_text(adjudication.get("rule_requirement_match"))
    if status == "technical_error_internal" and _semantic_technical_error_should_be_rejected(reason, quote):
        status = "rejected_by_system"
        match = "not_matched"
        reason = reason or "二审判定为一审语义或文书域错配，按系统驳回处理。"

    next_item.update(
        {
            "first_pass_status": first_pass_status,
            "first_pass_display_status": first_pass_display_status,
            "adjudicated_display_status": status,
            "adjudicator_reason": reason,
            "adjudicator_supporting_quote": quote,
            "adjudicator_confidence": confidence,
            "rule_requirement_match": match or "not_matched",
            "display_status": status,
            "display_bucket": DISPLAY_BUCKET_BY_STATUS[status],
            "postprocess_label": LABEL_BY_STATUS[status],
            "postprocess_reason": reason or "二审裁决已生成正式展示终态。",
            "can_show_as_defect": status == "confirmed_defect",
            "can_show_to_doctor": status == "confirmed_defect",
            "internal_only": status in {"rejected_by_system", "technical_error_internal"},
            "postprocess_mode": _safe_text(next_item.get("postprocess_mode")) or "formal_final_online",
        }
    )
    if status == "technical_error_internal":
        next_item["technical_error_internal"] = True
    criteria_metadata = rule_criteria_metadata(next_item.get("rule_id") or next_item.get("rule_code"))
    if criteria_metadata:
        next_item.update(criteria_metadata)
        if status == "data_quality_gap":
            next_item["data_gap_reason"] = reason
        elif status == "rejected_by_system":
            next_item["rejected_reason"] = reason
        elif status == "confirmed_defect":
            next_item["confirmed_guardrail_reason"] = reason
    metadata = next_item.get("metadata")
    if isinstance(metadata, dict):
        metadata["first_pass_display_status"] = first_pass_display_status
        metadata["adjudicated_display_status"] = status
        metadata["adjudicator_confidence"] = confidence
        if criteria_metadata:
            metadata.update(criteria_metadata)
            if status == "data_quality_gap":
                metadata["data_gap_reason"] = reason
            elif status == "rejected_by_system":
                metadata["rejected_reason"] = reason
            elif status == "confirmed_defect":
                metadata["confirmed_guardrail_reason"] = reason
    return next_item


def _set_display_status(item: dict[str, Any], status: str, *, reason: str) -> dict[str, Any]:
    next_item = dict(item)
    next_item.update(
        {
            "display_status": status,
            "display_bucket": DISPLAY_BUCKET_BY_STATUS[status],
            "postprocess_label": LABEL_BY_STATUS[status],
            "postprocess_reason": reason,
            "can_show_as_defect": status == "confirmed_defect",
            "can_show_to_doctor": status == "confirmed_defect",
            "internal_only": status in {"rejected_by_system", "technical_error_internal"},
        }
    )
    if status == "technical_error_internal":
        next_item["technical_error_internal"] = True
    criteria_metadata = rule_criteria_metadata(next_item.get("rule_id") or next_item.get("rule_code"))
    if criteria_metadata:
        next_item.update(criteria_metadata)
        if status == "data_quality_gap":
            next_item["data_gap_reason"] = reason
        elif status == "rejected_by_system":
            next_item["rejected_reason"] = reason
        elif status == "confirmed_defect":
            next_item["confirmed_guardrail_reason"] = reason
        metadata = next_item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
            next_item["metadata"] = metadata
        metadata.update(criteria_metadata)
        if status == "data_quality_gap":
            metadata["data_gap_reason"] = reason
        elif status == "rejected_by_system":
            metadata["rejected_reason"] = reason
        elif status == "confirmed_defect":
            metadata["confirmed_guardrail_reason"] = reason
    return next_item


def _guardrail_targeted_rule(
    *,
    rule_id: str,
    coverage: dict[str, Any],
) -> tuple[str, str] | None:
    if not coverage:
        return (
            "data_quality_gap",
            f"{rule_id} 确认缺陷需要结构化 formal_evidence_coverage；当前结果缺少证据覆盖标记，不能直接 confirmed。",
        )
    if rule_id == "SC-083":
        if not (
            bool(coverage.get("has_surgery_source"))
            and bool(coverage.get("has_presurg_discussion"))
            and bool(coverage.get("has_mdt_or_consultation_source"))
        ):
            return (
                "data_quality_gap",
                "SC-083 确认缺陷需要手术来源、术前讨论和 MDT/会诊来源均覆盖；当前结构化覆盖不完整。",
            )
    if rule_id == "SC-019":
        if not (
            bool(coverage.get("has_admission_record_source"))
            and bool(coverage.get("has_source_report"))
            and bool(coverage.get("has_admission_assist_exam_text"))
        ):
            return (
                "data_quality_gap",
                "SC-019 确认缺陷需要入院记录、辅助检查段落和原始检查/检验报告来源均覆盖；当前结构化覆盖不完整。",
            )
    if rule_id == "SC-099":
        if not bool(coverage.get("has_specimen_or_pathology_trigger")):
            return (
                "rejected_by_system",
                "SC-099 仅适用于存在术中取材、送病理、活检或标本等触发证据的手术；当前未见适用触发证据。",
            )
        coverage_status = _safe_text(coverage.get("specimen_pathology_coverage"))
        if coverage_status == "source_missing" or not bool(coverage.get("has_pathology_source")):
            return (
                "data_quality_gap",
                "SC-099 已见取材/病理触发线索，但缺少病理来源表或结果对照，不能直接确认为手术记录缺陷。",
            )
        if coverage_status not in {"documented", "missing"}:
            return (
                "data_quality_gap",
                "SC-099 需要明确取材/病理结果覆盖状态；当前结构化覆盖不足。",
            )
    if rule_id == "SC-100":
        if not (bool(coverage.get("has_surgery_record")) or bool(coverage.get("has_surgery_record_source"))):
            return (
                "data_quality_gap",
                "SC-100 确认缺陷需要手术记录来源覆盖；当前结构化覆盖不完整。",
            )
        if not bool(coverage.get("has_implant_trigger", coverage.get("has_implant_or_consumable_text"))):
            return (
                "rejected_by_system",
                "SC-100 仅适用于存在植入物的手术；当前未见植入物触发证据。",
            )
        if not bool(coverage.get("has_consumable_cross_source")) or not bool(
            coverage.get("has_implant_barcode_source", coverage.get("has_barcode_source"))
        ):
            return (
                "data_quality_gap",
                "SC-100 确认缺陷需要耗材/植入物对照来源和条码/追溯码记录域覆盖；当前结构化覆盖不完整。",
            )
    if rule_id == "SC-101":
        if not bool(coverage.get("has_implant_trigger")):
            return (
                "rejected_by_system",
                "SC-101 仅适用于存在植入物的手术；当前未见植入物触发证据。",
            )
        completeness = _safe_text(coverage.get("implant_detail_completeness"))
        if completeness == "partial":
            return (
                "data_quality_gap",
                "SC-101 已见植入物种类/数量等部分记录，不能直接确认“未记录”；需完整耗材/条码/型号对照后再判定。",
            )
        if completeness == "complete":
            return (
                "rejected_by_system",
                "SC-101 结构化覆盖显示植入物详情已相对完整，不支持确认“未记录”。",
            )
        if completeness != "none":
            return (
                "data_quality_gap",
                "SC-101 需要明确植入物详情完整性；当前结构化覆盖不足。",
            )
    return None


def _context_matrix_result(
    *,
    rule: str,
    document_type: str,
    section: str,
    matrix: dict[str, bool],
    failure_status: str = "",
    failure_reason: str = "",
    policy_pending_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "rule": rule,
        "document_type": document_type,
        "section": section,
        "matrix": matrix,
        "matrix_complete": not _matrix_missing_fields(matrix),
        "failure_status": failure_status,
        "failure_reason": failure_reason,
        "blocked_reason": failure_reason,
        "policy_pending_flags": policy_pending_flags or [],
    }


def _guardrail_admission_present_illness_matrix(item: dict[str, Any]) -> dict[str, Any]:
    context = _targeted_evidence_context(item)
    admission_text = "\n".join(_context_evidence_texts(context, "admission_record_evidence"))
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    evidence = _safe_text(item.get("evidence"))
    combined = f"{admission_text}\n{quote}\n{evidence}"
    source_ok = bool(admission_text) and (
        _matrix_terms(admission_text, ("现病史", "发病以来", "发病后", "入院前", "门诊", "急诊", "收入"))
        or _safe_text(context.get("rule_id")) == "ADMISSION-STRUCTURED-CONTEXT"
    )
    matrix = {
        "onset_course": _matrix_terms(combined, ("起病", "发病", "出现", "诉", "主诉")),
        "preadmission_visit": _matrix_terms(combined, ("院外", "外院", "门诊", "急诊", "卫生院", "社区医院", "我院")),
        "preadmission_exam": _matrix_terms(combined, ("检查", "检验", "CT", "MRI", "彩超", "腹部彩超", "辅助检查")),
        "preadmission_treatment": _matrix_terms(combined, ("治疗", "输液", "用药", "服药", "口服", "针灸", "理疗")),
        "treatment_effect": _matrix_terms(combined, ("无好转", "好转", "缓解", "改善", "无明显改善", "效果欠佳", "加重")),
    }
    if not source_ok:
        return _context_matrix_result(
            rule="SC-012",
            document_type="admission_record",
            section="present_illness",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-012 confirmed 需要证明证据来自入院记录现病史/发病后至入院前段落；当前来源或段落不足。",
        )
    if "具体不详" in combined and matrix["preadmission_treatment"]:
        return _context_matrix_result(
            rule="SC-012",
            document_type="admission_record",
            section="present_illness",
            matrix=matrix,
        )
    if not (matrix["preadmission_visit"] and matrix["preadmission_treatment"]):
        return _context_matrix_result(
            rule="SC-012",
            document_type="admission_record",
            section="present_illness",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-012 confirmed 需要院前就诊/治疗触发和现病史字段矩阵支撑；当前只能证明片段存在，不能确认缺陷。",
        )
    return _context_matrix_result(
        rule="SC-012",
        document_type="admission_record",
        section="present_illness",
        matrix=matrix,
    )


def _guardrail_admission_past_history_matrix(item: dict[str, Any]) -> dict[str, Any]:
    context = _targeted_evidence_context(item)
    admission_text = "\n".join(_context_evidence_texts(context, "admission_record_evidence"))
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    evidence = _safe_text(item.get("evidence"))
    combined = f"{admission_text}\n{quote}\n{evidence}"
    source_ok = bool(admission_text) and (
        _matrix_terms(admission_text, ("既往", "一般情况", "慢病", "传染病史", "手术史", "输血史", "过敏史", "预防接种史"))
        or _safe_text(context.get("rule_id")) == "ADMISSION-STRUCTURED-CONTEXT"
    )
    matrix = {
        "prior_disease_history": _matrix_terms(combined, ("慢病", "既往", "疾病史", "高血压", "糖尿病", "冠心病")),
        "infectious_disease_history": _matrix_terms(combined, ("传染病史", "肝炎", "结核")),
        "surgery_trauma_history": _matrix_terms(combined, ("手术史", "外伤史", "手术外伤")),
        "transfusion_history": _matrix_terms(combined, ("输血史", "输血")),
        "allergy_history": _matrix_terms(combined, ("过敏史", "过敏")),
        "vaccination_history": _matrix_terms(combined, ("预防接种史", "接种史")),
    }
    if not source_ok:
        return _context_matrix_result(
            rule="SC-013",
            document_type="admission_record",
            section="past_history",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-013 confirmed 需要证明证据来自入院记录既往史完整段落；当前来源或段落不足。",
        )
    if "不详预防接种史" in combined:
        return _context_matrix_result(
            rule="SC-013",
            document_type="admission_record",
            section="past_history",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-013 中“不详预防接种史”属于客户口径敏感项；未确认必须明确记录前不直接 confirmed。",
            policy_pending_flags=["policy_pending_vaccination_unknown"],
        )
    if _matrix_missing_fields(matrix):
        return _context_matrix_result(
            rule="SC-013",
            document_type="admission_record",
            section="past_history",
            matrix=matrix,
        )
    return _context_matrix_result(
        rule="SC-013",
        document_type="admission_record",
        section="past_history",
        matrix=matrix,
        failure_status="rejected_by_system",
        failure_reason="SC-013 既往史字段矩阵已覆盖主要规定字段，不支持 confirmed。",
    )


def _guardrail_discharge_record_matrix(item: dict[str, Any]) -> dict[str, Any]:
    context = _targeted_evidence_context(item)
    discharge_text = "\n".join(_context_evidence_texts(context, "discharge_record_evidence"))
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    evidence = _safe_text(item.get("evidence"))
    source_text = discharge_text or evidence
    source_ok = len(re.sub(r"\s+", "", discharge_text)) >= 120
    matrix = {
        "admission_date": bool(re.search(r"(入院日期|入院时间|于\d{4}[-年]\d{1,2}[-月]\d{1,2}.{0,8}入院)", source_text)),
        "discharge_date": bool(re.search(r"(出院日期|出院时间|于\d{4}[-年]\d{1,2}[-月]\d{1,2}.{0,8}出院)", source_text)),
        "admission_condition": _matrix_terms(source_text, ("入院情况", "入院查体", "查体", "主诉")),
        "admission_diagnosis": _matrix_terms(source_text, ("入院诊断",)),
        "treatment_course": _matrix_terms(source_text, ("诊疗经过", "治疗经过", "给予", "完善", "治疗")),
        "discharge_condition": _matrix_terms(source_text, ("出院情况", "病情好转", "予以出院", "转院", "出院时")),
        "discharge_advice": _matrix_terms(source_text, ("出院医嘱", "出院带药", "门诊随访", "随访", "复查")),
        "doctor_signature": _matrix_terms(source_text, ("医师签名", "医生签名", "签名医师", "签名")),
    }
    if not source_ok:
        return _context_matrix_result(
            rule="SC-118",
            document_type="discharge_record",
            section="discharge_record_fields",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-118 confirmed 需要完整出院记录或结构化字段矩阵；当前仅见短片段，不能确认缺项。",
        )
    if _matrix_missing_fields(matrix):
        return _context_matrix_result(
            rule="SC-118",
            document_type="discharge_record",
            section="discharge_record_fields",
            matrix=matrix,
        )
    return _context_matrix_result(
        rule="SC-118",
        document_type="discharge_record",
        section="discharge_record_fields",
        matrix=matrix,
        failure_status="rejected_by_system",
        failure_reason="SC-118 出院记录字段矩阵未见明确缺项，不支持 confirmed。",
    )


def _guardrail_discharge_treatment_course_matrix(item: dict[str, Any]) -> dict[str, Any]:
    context = _targeted_evidence_context(item)
    discharge_text = "\n".join(_context_evidence_texts(context, "discharge_record_evidence"))
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    reason = _safe_text(item.get("adjudicator_reason"))
    contrast_quote = _safe_text(context.get("contrast_quote"))
    evidence = _safe_text(item.get("evidence"))
    combined = f"{discharge_text}\n{quote}\n{reason}\n{contrast_quote}\n{evidence}"
    source_len = len(re.sub(r"\s+", "", discharge_text))
    source_ok = source_len >= 120 or (source_len >= 80 and "诊疗经过" in discharge_text)
    claims_missing_drug = _matrix_terms(reason, ("主要药品", "药品名称", "主要药物", "用药", "抗凝", "治疗方案"))
    contrast_compact = re.sub(r"\s+", "", contrast_quote)
    has_contrast = bool(contrast_compact) and len(contrast_compact) >= 8 and not _quote_is_record_time_only(contrast_quote)
    matrix = {
        "main_treatment_measures": _matrix_terms(combined, ("治疗", "给予", "予以", "手术", "补液", "护胃", "抗感染", "平喘", "利尿")),
        "main_drug_names_or_treatment_plan": _matrix_terms(combined, ("多索茶碱", "甲泼尼龙", "哌拉西林", "他唑巴坦", "呋塞米", "螺内酯", "艾司奥美拉唑", "抗凝", "抗感染", "药")),
        "important_auxiliary_exam_results_related_to_diagnosis": _matrix_terms(combined, ("CT", "MRI", "CTA", "血常规", "检验", "检查", "辅助检查", "诊断")),
        "treatment_response_or_outcome": _matrix_terms(combined, ("好转", "缓解", "稳定", "转院", "出院", "效果", "症状")),
        "contrast_order_or_consultation_if_claiming_missing_drug": (not claims_missing_drug) or has_contrast,
    }
    if not source_ok:
        return _context_matrix_result(
            rule="SC-121",
            document_type="discharge_record",
            section="treatment_course",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-121 confirmed 需要完整出院记录诊疗经过段；当前仅见短句或片段，不能确认诊疗经过不全面。",
        )
    if claims_missing_drug and not has_contrast:
        return _context_matrix_result(
            rule="SC-121",
            document_type="discharge_record",
            section="treatment_course",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-121 若判“无主要药品名称”，必须有医嘱、会诊建议或治疗方案对照；当前缺少跨文书对照。",
        )
    if claims_missing_drug and has_contrast:
        return _context_matrix_result(
            rule="SC-121",
            document_type="discharge_record",
            section="treatment_course",
            matrix=matrix,
        )
    quote_compact = re.sub(r"\s+", "", quote)
    if quote_compact in {"治疗上予以护胃、补液等对症支持治疗。", "治疗上予以护胃、补液等对症支持治疗"} and not has_contrast:
        return _context_matrix_result(
            rule="SC-121",
            document_type="discharge_record",
            section="treatment_course",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-121 不能仅凭“护胃、补液”等短句确认诊疗经过不详细，需要完整诊疗经过或跨文书对照。",
        )
    if _matrix_missing_fields(matrix):
        return _context_matrix_result(
            rule="SC-121",
            document_type="discharge_record",
            section="treatment_course",
            matrix=matrix,
        )
    return _context_matrix_result(
        rule="SC-121",
        document_type="discharge_record",
        section="treatment_course",
        matrix=matrix,
        failure_status="rejected_by_system",
        failure_reason="SC-121 诊疗经过字段矩阵未见明确缺项，不支持 confirmed。",
    )


def _guardrail_discharge_advice_matrix(item: dict[str, Any]) -> dict[str, Any]:
    context = _targeted_evidence_context(item)
    discharge_text = "\n".join(_context_evidence_texts(context, "discharge_record_evidence"))
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    evidence = _safe_text(item.get("evidence"))
    combined = f"{discharge_text}\n{quote}\n{evidence}"
    compact_discharge = re.sub(r"\s+", "", discharge_text)
    quote_compact = re.sub(r"\s+", "", quote)
    section_present = _matrix_terms(combined, ("出院医嘱", "出院指导", "出院注意事项", "出院后"))
    source_full_section = bool(compact_discharge) and len(compact_discharge) >= 70 and section_present
    followup_only_fragment = bool(quote_compact) and len(quote_compact) < 60 and _matrix_terms(
        quote_compact, ("随访方式", "随访周期", "随访日期", "无需随访")
    )
    matrix = {
        "discharge_advice_section_present": section_present,
        "source_is_full_discharge_advice_section": source_full_section,
        "medication_advice_present": _matrix_terms(combined, ("出院带药", "出院用药", "口服", "外用", "胶囊", "片", "颗粒")),
        "followup_advice_present": _matrix_terms(combined, ("随访", "复查", "门诊", "就诊")),
        "diet_or_activity_advice_present": _matrix_terms(combined, ("饮食", "休息", "休养", "活动", "功能锻炼", "避免")),
        "warning_signs_or_return_visit_present": _matrix_terms(combined, ("不适", "加重", "及时就诊", "返院", "急诊")),
    }
    if followup_only_fragment or not source_full_section:
        return _context_matrix_result(
            rule="SC-122",
            document_type="discharge_record",
            section="discharge_advice",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-122 confirmed 需要完整出院医嘱段；当前仅见随访方式/周期等局部片段，不能确认出院医嘱缺失或不全。",
        )
    if matrix["followup_advice_present"] and (
        matrix["medication_advice_present"]
        or matrix["diet_or_activity_advice_present"]
        or matrix["warning_signs_or_return_visit_present"]
    ):
        return _context_matrix_result(
            rule="SC-122",
            document_type="discharge_record",
            section="discharge_advice",
            matrix=matrix,
            failure_status="rejected_by_system",
            failure_reason="SC-122 出院医嘱段已包含随访及用药/饮食活动/注意事项等合理内容，不支持 confirmed。",
        )
    return _context_matrix_result(
        rule="SC-122",
        document_type="discharge_record",
        section="discharge_advice",
        matrix=matrix,
    )


def _guardrail_course_order_change_matrix(item: dict[str, Any]) -> dict[str, Any]:
    context = _targeted_evidence_context(item)
    course_text = "\n".join(
        _context_texts_by_keys(context, ("daily_course_evidence", "senior_course_evidence", "course_record_evidence"))
    )
    order_text = "\n".join(
        _context_texts_by_keys(
            context,
            (
                "order_or_consult_evidence",
                "order_evidence",
                "drug_order_evidence",
                "nondrug_order_evidence",
                "execution_evidence",
            ),
        )
    )
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    evidence = _safe_text(item.get("evidence"))
    reason = _safe_text(item.get("adjudicator_reason"))
    combined = f"{course_text}\n{order_text}\n{quote}\n{evidence}\n{reason}"
    order_quote = order_text or _safe_text(context.get("contrast_quote"))
    trigger_event_present = _matrix_terms(
        combined,
        ("呕吐", "发热", "疼痛", "呼吸困难", "血压", "血糖", "病情变化", "症状", "体征", "异常"),
    )
    order_change_present = bool(order_quote) and _matrix_terms(
        order_quote,
        ("新开", "停", "调整", "改", "加用", "减量", "医嘱", "用药", "治疗", "胃复安", "止吐"),
    )
    course_analysis_present = _matrix_terms(
        course_text or quote,
        ("考虑", "原因", "分析", "由于", "因", "依据", "评估", "计划", "续观", "复查", "调整"),
    )
    if re.search(r"(未见|未记录|缺乏|无).{0,12}(原因|病因|分析|依据|效果|后续|计划|调整)", course_text):
        course_analysis_present = False
    matrix = {
        "trigger_event_present": trigger_event_present,
        "trigger_event_quote": bool(course_text or quote),
        "order_or_treatment_change_present": order_change_present,
        "order_or_treatment_change_quote": bool(order_quote),
        "course_analysis_present": course_analysis_present,
        "course_analysis_quote": bool(course_text and course_analysis_present),
        "course_analysis_missing": bool(trigger_event_present and order_change_present and not course_analysis_present),
        "treatment_effect_or_followup_present": _matrix_terms(combined, ("好转", "缓解", "无好转", "继续", "续观", "复查", "观察")),
    }
    if not order_change_present:
        return _context_matrix_result(
            rule="SC-034",
            document_type="daily_course_record",
            section="order_treatment_change_analysis",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-034 confirmed 需要医嘱/治疗变化来源 quote；当前仅见症状与对症处理片段，不能证明“医嘱变化未记录或未分析”。",
        )
    if not course_text:
        return _context_matrix_result(
            rule="SC-034",
            document_type="daily_course_record",
            section="order_treatment_change_analysis",
            matrix=matrix,
            failure_status="data_quality_gap",
            failure_reason="SC-034 confirmed 需要病程记录上下文对照；当前缺少可核查病程正文。",
        )
    if not matrix["course_analysis_missing"]:
        return _context_matrix_result(
            rule="SC-034",
            document_type="daily_course_record",
            section="order_treatment_change_analysis",
            matrix=matrix,
            failure_status="rejected_by_system",
            failure_reason="SC-034 未形成“医嘱/治疗变化 + 病程分析缺失”的完整缺陷链，不能 confirmed。",
        )
    return _context_matrix_result(
        rule="SC-034",
        document_type="daily_course_record",
        section="order_treatment_change_analysis",
        matrix=matrix,
    )


def _guardrail_context_matrix(item: dict[str, Any], rule_id: str) -> dict[str, Any] | None:
    if rule_id == "SC-012":
        return _guardrail_admission_present_illness_matrix(item)
    if rule_id == "SC-013":
        return _guardrail_admission_past_history_matrix(item)
    if rule_id == "SC-034":
        return _guardrail_course_order_change_matrix(item)
    if rule_id == "SC-118":
        return _guardrail_discharge_record_matrix(item)
    if rule_id == "SC-121":
        return _guardrail_discharge_treatment_course_matrix(item)
    if rule_id == "SC-122":
        return _guardrail_discharge_advice_matrix(item)
    return None


def _guardrail_sc099_gate_context(item: dict[str, Any]) -> tuple[str, str] | None:
    gate_meta = _gate_metadata(item)
    linkage = gate_meta.get("pathology_linkage_context")
    if not isinstance(linkage, dict):
        return None
    quote = _safe_text(item.get("adjudicator_supporting_quote"))
    surgery_quote = _safe_text(linkage.get("surgery_specimen_quote"))
    pathology_quote = _safe_text(linkage.get("pathology_specimen_quote") or linkage.get("pathology_diagnosis_quote"))
    linkage_status = _safe_text(linkage.get("linkage_status"))
    if _quote_is_header_or_empty_fragment(quote) or len(re.sub(r"\s+", "", quote)) < 40:
        return (
            "data_quality_gap",
            "SC-099 confirmed 不能只凭短句或截断 quote，需要二审 quote 本身包含可审计的手术取材/送病理与病理结果对照。",
        )
    if linkage_status != "linked":
        return (
            "data_quality_gap",
            "SC-099 confirmed 需要手术记录取材/送病理 quote 与病理来源 quote 对照；当前 linkage_status 不是 linked。",
        )
    if _quote_is_header_or_empty_fragment(surgery_quote) or _quote_is_header_or_empty_fragment(pathology_quote):
        return (
            "data_quality_gap",
            "SC-099 confirmed 需要可追溯的手术取材/送病理 quote 与病理诊断/标本 quote；当前对照引用不足。",
        )
    return None


def _guardrail_sc123_gate_matrix(item: dict[str, Any]) -> tuple[str, str] | None:
    gate_meta = _gate_metadata(item)
    if _safe_bool(gate_meta.get("medication_fields_complete")):
        return (
            "rejected_by_system",
            "SC-123 出院带药字段完整性矩阵显示药品名称、剂量、频次和用法/途径基本完整，不支持 confirmed。",
        )
    matrix = gate_meta.get("discharge_medication_matrix")
    if not isinstance(matrix, list):
        return None
    trigger_strength = _safe_text(gate_meta.get("trigger_strength"))
    if trigger_strength and trigger_strength != "explicit":
        return (
            "rejected_by_system",
            "SC-123 confirmed 需要明确出院带药/出院用药段落；当前仅为弱出院语境或普通治疗用药，不能确认出院带药缺陷。",
        )
    valid_items = [row for row in matrix if isinstance(row, dict)]
    if not valid_items:
        return (
            "data_quality_gap",
            "SC-123 confirmed 需要逐药品字段矩阵支撑；当前未见可核查出院带药药品明细。",
        )
    missing_rows = [
        row
        for row in valid_items
        if isinstance(row.get("missing_fields"), list) and row.get("missing_fields")
    ]
    if not missing_rows:
        return (
            "rejected_by_system",
            "SC-123 出院带药字段矩阵显示药品名称、剂量、频次、用法和天数/数量初步完整，不支持 confirmed。",
        )
    if any("..." in _safe_text(row.get("source_quote")) or "…" in _safe_text(row.get("source_quote")) for row in missing_rows):
        return (
            "data_quality_gap",
            "SC-123 出院带药字段矩阵来自截断 quote，不能直接确认药品字段缺失。",
        )
    if not any(not _quote_is_header_or_empty_fragment(_safe_text(row.get("source_quote"))) for row in missing_rows):
        return (
            "data_quality_gap",
            "SC-123 confirmed 需要可追溯的出院带药药品 quote；当前字段缺失只来自短片段或不可审计证据。",
        )
    missing_union = {
        _safe_text(field)
        for row in missing_rows
        for field in (row.get("missing_fields") or [])
        if _safe_text(field)
    }
    if missing_union and missing_union.issubset({"用法/途径", "天数/数量/疗程", "频次"}):
        return (
            "rejected_by_system",
            "SC-123 当前字段矩阵仅提示常见隐含用法/疗程或频次边界，缺少可直接展示为缺陷的强证据。",
        )
    if any(len(row.get("missing_fields") or []) >= 3 for row in missing_rows):
        return (
            "data_quality_gap",
            "SC-123 单个药品缺失字段过多，多数来自证据截断或上下文不足，应先补全出院带药全文。",
        )
    return None


def _confirmed_guardrail(item: dict[str, Any]) -> dict[str, Any]:
    if _safe_text(item.get("display_status")) != "confirmed_defect":
        return dict(item)

    next_item = dict(item)
    rule_id = _normalize_rule_id(next_item.get("rule_id") or next_item.get("rule_code"))
    reason = _safe_text(next_item.get("adjudicator_reason"))
    quote = _safe_text(next_item.get("adjudicator_supporting_quote"))
    evidence = _safe_text(next_item.get("evidence"))
    findings = _safe_text(next_item.get("findings"))
    problem_type = _safe_text(next_item.get("evidence_problem_type"))
    combined = f"{findings}\n{evidence}\n{quote}\n{reason}\n{problem_type}"
    context_matrix = _guardrail_context_matrix(next_item, rule_id)
    if context_matrix:
        _apply_context_matrix_metadata(next_item, context_matrix)

    failure_status = ""
    failure_reason = ""
    if not reason:
        failure_status = "data_quality_gap" if rule_id in TARGETED_COVERAGE_GUARDRAIL_RULES else "rejected_by_system"
        failure_reason = "confirmed_defect 缺少二审 adjudicator_reason，不能作为正式确认缺陷。"
    elif rule_id == "SC-099":
        gate_failure = _guardrail_sc099_gate_context(next_item)
        if gate_failure:
            failure_status, failure_reason = gate_failure
        else:
            targeted_failure = _guardrail_targeted_rule(
                rule_id=rule_id,
                coverage=_coverage_flags(next_item),
            )
            if targeted_failure:
                failure_status, failure_reason = targeted_failure
    elif rule_id == "SC-123":
        gate_failure = _guardrail_sc123_gate_matrix(next_item)
        if gate_failure:
            failure_status, failure_reason = gate_failure
    elif context_matrix is not None:
        if context_matrix.get("failure_status"):
            failure_status = _safe_text(context_matrix.get("failure_status"))
            failure_reason = _safe_text(context_matrix.get("failure_reason"))
    elif rule_id in TARGETED_COVERAGE_GUARDRAIL_RULES:
        targeted_failure = _guardrail_targeted_rule(
            rule_id=rule_id,
            coverage=_coverage_flags(next_item),
        )
        if targeted_failure:
            failure_status, failure_reason = targeted_failure
    elif "具体药物不详" in quote:
        failure_status = "data_quality_gap"
        failure_reason = "confirmed_defect 仅依据院外用药“具体药物不详”等短片段，缺少完整院外治疗经过和效果对照，不能直接确认缺陷。"
    elif rule_id == "SC-015" and "不详预防接种史" in quote:
        failure_status = "rejected_by_system"
        failure_reason = "SC-015 中“不详预防接种史”属于个人史边界记录，缺少客户明确口径时不应直接 confirmed。"
    elif rule_id == "SC-004" and len(re.sub(r"\s+", "", quote)) < 60:
        failure_status = "data_quality_gap"
        failure_reason = "SC-004 再次入院小结缺陷需要较完整的前次诊疗经过对照；当前 quote 过短，不能直接 confirmed。"
    elif rule_id == "SC-081" and re.search(r"患者.{0,8}性别.{0,8}年龄", quote):
        failure_status = "data_quality_gap"
        failure_reason = "SC-081 confirmed 不能仅凭患者基本信息片段判断术前小结缺项，需要完整术前小结正文覆盖。"
    elif _quote_is_header_or_empty_fragment(quote):
        failure_status = "data_quality_gap"
        failure_reason = "confirmed_defect 的支撑 quote 为空、过短，或仅包含记录时间/标题/文书头/空字段，不能作为正式确认缺陷。"
    elif len(quote) < CONFIRMED_QUOTE_MIN_LEN:
        failure_status = "data_quality_gap"
        failure_reason = "confirmed_defect 缺少足够长度的 adjudicator_supporting_quote，不能证明规则核心要件。"
    elif rule_id in {"SC-099", "SC-100", "SC-101"} and _quote_is_record_time_only(quote):
        failure_status = "data_quality_gap"
        failure_reason = f"{rule_id} confirmed_defect 不能仅凭记录时间作为支撑原文，需要可追溯的取材/病理或植入物详情证据。"
    elif rule_id in TARGETED_COVERAGE_GUARDRAIL_RULES and _contains_any(quote, NEGATIVE_ONLY_TERMS):
        failure_status = "data_quality_gap"
        failure_reason = "confirmed_defect 仅凭缺失类表述成立，但目标规则缺陷需要结构化证据域覆盖。"

    if not failure_status:
        next_item.setdefault("adjudicator_guardrail_failed", False)
        return next_item

    if (
        failure_status == "rejected_by_system"
        and rule_id != "SC-123"
        and _contains_any(combined, DATA_GAP_TERMS)
    ):
        failure_status = "data_quality_gap"

    next_item["original_adjudicated_display_status"] = _safe_text(
        next_item.get("adjudicated_display_status")
    ) or "confirmed_defect"
    next_item["adjudicated_display_status"] = failure_status
    next_item["adjudicator_guardrail_failed"] = True
    next_item["adjudicator_guardrail_reason"] = failure_reason
    next_item = _set_display_status(next_item, failure_status, reason=failure_reason)

    metadata = next_item.get("metadata")
    if isinstance(metadata, dict):
        metadata["original_adjudicated_display_status"] = "confirmed_defect"
        metadata["adjudicator_guardrail_failed"] = True
        metadata["adjudicator_guardrail_reason"] = failure_reason
        if context_matrix:
            metadata["confirmed_blocked_reason"] = failure_reason
    return next_item


def _technical_error_for_candidate(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return _apply_adjudication(
        item,
        {
            "adjudicated_display_status": "technical_error_internal",
            "adjudicator_reason": reason,
            "adjudicator_supporting_quote": "",
            "adjudicator_confidence": 0.0,
            "rule_requirement_match": "technical_error",
        },
    )


def _with_adjudicator_diagnostics(
    item: dict[str, Any],
    diagnostics: dict[str, Any],
    *,
    recovered_by_retry: bool = False,
) -> dict[str, Any]:
    next_item = dict(item)
    next_item.update(diagnostics)
    if recovered_by_retry:
        next_item["recovered_by_adjudicator_missing_rule_retry"] = True
    metadata = next_item.get("metadata")
    if isinstance(metadata, dict):
        metadata.update(diagnostics)
        if recovered_by_retry:
            metadata["recovered_by_adjudicator_missing_rule_retry"] = True
    return next_item


def _collect_adjudications(
    adjudicated_items: list[Any],
    prompt_items: list[dict[str, Any]],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    expected_codes = [_normalize_rule_code(item.get("rule_id")) for item in prompt_items]
    expected_code_to_indexes: dict[str, list[int]] = defaultdict(list)
    for index, code in enumerate(expected_codes):
        expected_code_to_indexes[code].append(index)

    by_candidate_index: dict[int, dict[str, Any]] = {}
    actual_codes: list[str] = []
    extra_rule_codes: list[str] = []
    duplicate_rule_codes: list[str] = []

    for item in adjudicated_items:
        if not isinstance(item, dict):
            continue
        code = _normalize_rule_code(item.get("rule_id"))
        target_index: int | None = None
        try:
            raw_index = int(item.get("index"))
        except Exception:
            raw_index = -1
        if 0 <= raw_index < len(prompt_items):
            expected_at_index = expected_codes[raw_index]
            if not code or code == expected_at_index:
                target_index = raw_index
        if target_index is None and code in expected_code_to_indexes and len(expected_code_to_indexes[code]) == 1:
            target_index = expected_code_to_indexes[code][0]
        if target_index is None:
            if code:
                extra_rule_codes.append(code)
            continue

        actual_code = expected_codes[target_index]
        actual_codes.append(actual_code)
        if target_index in by_candidate_index:
            duplicate_rule_codes.append(actual_code)
            continue
        by_candidate_index[target_index] = item

    missing_indexes = [index for index in range(len(prompt_items)) if index not in by_candidate_index]
    missing_codes = [expected_codes[index] for index in missing_indexes]
    diagnostics = {
        "expected_rule_codes": expected_codes,
        "actual_rule_codes": sorted(set(actual_codes)),
        "missing_rule_indexes": missing_indexes,
        "missing_rule_codes": missing_codes,
        "extra_rule_codes": sorted(set(extra_rule_codes)),
        "duplicate_rule_codes": sorted(set(duplicate_rule_codes)),
    }
    return by_candidate_index, diagnostics


def _adjudicator_stats(
    *,
    expected_codes: list[str],
    final_missing_codes: list[str],
    initial_missing_codes: list[str],
    extra_rule_codes: list[str],
    duplicate_rule_codes: list[str],
    retry_attempted: bool,
    retry_recovered_count: int,
    retry_failed_count: int,
) -> dict[str, Any]:
    actual_codes = [code for code in expected_codes if code not in set(final_missing_codes)]
    return {
        "adjudicator_expected_rule_count": len(expected_codes),
        "adjudicator_expected_rule_codes": expected_codes,
        "adjudicator_actual_rule_count": len(actual_codes),
        "adjudicator_actual_rule_codes": actual_codes,
        "adjudicator_initial_missing_rule_count": len(initial_missing_codes),
        "adjudicator_initial_missing_rule_codes": initial_missing_codes,
        "adjudicator_missing_rule_count": len(final_missing_codes),
        "adjudicator_missing_rule_codes": final_missing_codes,
        "adjudicator_retry_attempted": retry_attempted,
        "adjudicator_retry_recovered_count": retry_recovered_count,
        "adjudicator_retry_failed_count": retry_failed_count,
        "adjudicator_missing_rule_output_count": len(final_missing_codes),
        "adjudicator_extra_rule_codes": extra_rule_codes,
        "adjudicator_duplicate_rule_codes": duplicate_rule_codes,
    }


def needs_llm_adjudication(item: dict[str, Any]) -> bool:
    display_status = _safe_text(item.get("display_status"))
    if display_status not in BOUNDARY_DISPLAY_STATUSES:
        return False
    metadata = _metadata(item)
    gate_decision = _safe_text(
        item.get("applicability_gate_decision") or metadata.get("applicability_gate_decision")
    )
    gate_terminal = _safe_bool(item.get("applicability_gate_terminal") or metadata.get("applicability_gate_terminal"))
    if gate_terminal or gate_decision in {"data_quality_gap", "rejected_by_system"}:
        return False
    if _safe_bool(item.get("technical_error_internal")) or display_status == "technical_error_internal":
        return False
    return True


def apply_confirmed_guardrails(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_confirmed_guardrail(dict(item)) for item in rows]


async def adjudicate_postprocessed_qc_results(
    rows: list[dict[str, Any]],
    *,
    rules_by_id: dict[str, dict[str, Any]] | None = None,
    llm_generate: AdjudicatorGenerateFn | None = None,
    mode: str = "formal_final_online",
) -> list[dict[str, Any]]:
    candidates = [
        (index, dict(item))
        for index, item in enumerate(rows)
        if isinstance(item, dict) and needs_llm_adjudication(item)
    ]
    if not candidates:
        return apply_confirmed_guardrails(rows)

    rules = rules_by_id or {}
    next_rows = [dict(item) for item in rows]
    if llm_generate is None:
        for index, item in candidates:
            next_rows[index] = _technical_error_for_candidate(item, "未配置正式质控二审 LLM，边界项进入内部技术异常。")
        return apply_confirmed_guardrails(next_rows)

    prompt_items = [
        _candidate_payload(
            item,
            rules.get(_safe_text(item.get("rule_id")).upper()),
            candidate_index,
        )
        for candidate_index, (_, item) in enumerate(candidates)
    ]
    initial_call_error = ""
    try:
        response = await llm_generate(_build_adjudicator_prompt(prompt_items))
        payload = _extract_json_object(_extract_llm_content(response))
        adjudicated_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    except Exception as exc:
        initial_call_error = f"正式质控二审 LLM 调用失败：{exc}"
        adjudicated_items = []

    by_candidate_index, initial_diagnostics = _collect_adjudications(adjudicated_items, prompt_items)
    expected_codes = initial_diagnostics["expected_rule_codes"]
    initial_missing_indexes = list(range(len(candidates))) if initial_call_error else list(initial_diagnostics["missing_rule_indexes"])
    initial_missing_codes = list(initial_diagnostics["missing_rule_codes"])
    if initial_call_error:
        initial_missing_codes = list(initial_diagnostics["expected_rule_codes"])
    extra_rule_codes = list(initial_diagnostics["extra_rule_codes"])
    duplicate_rule_codes = list(initial_diagnostics["duplicate_rule_codes"])
    retry_attempted = bool(initial_missing_indexes)
    retry_recovered_count = 0

    if initial_missing_indexes:
        recovered_original_indexes: set[int] = set()
        for missing_chunk in _chunked(initial_missing_indexes, ADJUDICATOR_MISSING_RETRY_CHUNK_SIZE):
            retry_candidates = [candidates[index] for index in missing_chunk]
            retry_prompt_items = [
                _candidate_payload(
                    item,
                    rules.get(_safe_text(item.get("rule_id")).upper()),
                    retry_index,
                )
                for retry_index, (_, item) in enumerate(retry_candidates)
            ]
            retry_expected_codes = [_normalize_rule_code(item.get("rule_id")) for item in retry_prompt_items]
            try:
                retry_response = await llm_generate(
                    _build_adjudicator_prompt(
                        retry_prompt_items,
                        retry_missing_rule_ids=retry_expected_codes,
                    )
                )
                retry_payload = _extract_json_object(_extract_llm_content(retry_response))
                retry_items = retry_payload.get("items") if isinstance(retry_payload.get("items"), list) else []
                retry_by_index, retry_diagnostics = _collect_adjudications(retry_items, retry_prompt_items)
                extra_rule_codes = sorted(set(extra_rule_codes + list(retry_diagnostics["extra_rule_codes"])))
                duplicate_rule_codes = sorted(
                    set(duplicate_rule_codes + list(retry_diagnostics["duplicate_rule_codes"]))
                )
                for retry_index, adjudication in retry_by_index.items():
                    if retry_index >= len(missing_chunk):
                        continue
                    original_candidate_index = missing_chunk[retry_index]
                    recovered = dict(adjudication)
                    recovered["recovered_by_adjudicator_missing_rule_retry"] = True
                    by_candidate_index[original_candidate_index] = recovered
                    recovered_original_indexes.add(original_candidate_index)
            except Exception as exc:
                for original_candidate_index in missing_chunk:
                    row_index, original_item = candidates[original_candidate_index]
                    next_rows[row_index] = _technical_error_for_candidate(
                        original_item,
                        f"正式质控二审缺失补裁调用失败：{exc}",
                    )
        retry_recovered_count = len(recovered_original_indexes)

    final_missing_indexes = [index for index in range(len(candidates)) if index not in by_candidate_index]
    final_missing_codes = [expected_codes[index] for index in final_missing_indexes]
    retry_failed_count = len(final_missing_indexes) if retry_attempted else 0
    diagnostics = _adjudicator_stats(
        expected_codes=expected_codes,
        final_missing_codes=final_missing_codes,
        initial_missing_codes=initial_missing_codes,
        extra_rule_codes=extra_rule_codes,
        duplicate_rule_codes=duplicate_rule_codes,
        retry_attempted=retry_attempted,
        retry_recovered_count=retry_recovered_count,
        retry_failed_count=retry_failed_count,
    )

    for candidate_index, (row_index, original_item) in enumerate(candidates):
        if next_rows[row_index].get("display_status") == "technical_error_internal" and candidate_index in final_missing_indexes:
            next_rows[row_index] = _with_adjudicator_diagnostics(next_rows[row_index], diagnostics)
            continue
        adjudication = by_candidate_index.get(candidate_index)
        if adjudication is None:
            final_item = _technical_error_for_candidate(
                original_item,
                "adjudicator_missing_rule_output_after_retry: 正式质控二审补裁后仍缺少该规则裁决，进入内部技术异常。",
            )
            next_rows[row_index] = _with_adjudicator_diagnostics(final_item, diagnostics)
            continue
        final_item = _apply_adjudication(original_item, adjudication)
        final_item["postprocess_mode"] = mode
        final_item = _with_adjudicator_diagnostics(
            final_item,
            diagnostics,
            recovered_by_retry=_safe_bool(adjudication.get("recovered_by_adjudicator_missing_rule_retry")),
        )
        next_rows[row_index] = final_item
    return apply_confirmed_guardrails(next_rows)
