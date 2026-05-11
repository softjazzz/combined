from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any


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


def _truncate(value: Any, limit: int = 900) -> str:
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


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


def _candidate_payload(item: dict[str, Any], rule: dict[str, Any] | None, index: int) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return {
        "index": index,
        "rule_id": _safe_text(item.get("rule_id")),
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
        "source_snippet": _truncate(
            item.get("evidence")
            or item.get("anchor_evidence")
            or metadata.get("source_snippet")
            or "",
            900,
        ),
    }


def _build_adjudicator_prompt(candidates: list[dict[str, Any]]) -> str:
    payload = json.dumps({"items": candidates}, ensure_ascii=False, indent=2)
    return f"""你是正式病历质控结果二审裁决器。请基于规则要求、第一轮 LLM 输出和证据片段独立裁决，不要把边界项推给人工。

只能输出 JSON，不要输出 Markdown。
终态只允许：
- confirmed_defect：规则核心要件成立，evidence 可直接支撑缺陷。
- data_quality_gap：缺少必要源文书、检查检验、医嘱、会诊、执行记录等，不能归咎医生。
- rejected_by_system：证据不足、结论自相矛盾、仅凭推测、规则要件不成立，或 evidence 支持合规。
- technical_error_internal：第一轮/二审存在 provider、解析、超时等技术异常。

严禁输出“待人工确认”“建议复核”“qc_review_candidate”等终态。

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
    metadata = next_item.get("metadata")
    if isinstance(metadata, dict):
        metadata["first_pass_display_status"] = first_pass_display_status
        metadata["adjudicated_display_status"] = status
        metadata["adjudicator_confidence"] = confidence
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


def needs_llm_adjudication(item: dict[str, Any]) -> bool:
    display_status = _safe_text(item.get("display_status"))
    if display_status not in BOUNDARY_DISPLAY_STATUSES:
        return False
    if _safe_bool(item.get("technical_error_internal")) or display_status == "technical_error_internal":
        return False
    return True


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
        return [dict(item) for item in rows]

    rules = rules_by_id or {}
    next_rows = [dict(item) for item in rows]
    if llm_generate is None:
        for index, item in candidates:
            next_rows[index] = _technical_error_for_candidate(item, "未配置正式质控二审 LLM，边界项进入内部技术异常。")
        return next_rows

    prompt_items = [
        _candidate_payload(
            item,
            rules.get(_safe_text(item.get("rule_id")).upper()),
            candidate_index,
        )
        for candidate_index, (_, item) in enumerate(candidates)
    ]
    try:
        response = await llm_generate(_build_adjudicator_prompt(prompt_items))
        payload = _extract_json_object(_extract_llm_content(response))
        adjudicated_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    except Exception as exc:
        for index, item in candidates:
            next_rows[index] = _technical_error_for_candidate(item, f"正式质控二审 LLM 调用失败：{exc}")
        return next_rows

    by_candidate_index: dict[int, dict[str, Any]] = {}
    for item in adjudicated_items:
        if not isinstance(item, dict):
            continue
        try:
            candidate_index = int(item.get("index"))
        except Exception:
            continue
        by_candidate_index[candidate_index] = item

    for candidate_index, (row_index, original_item) in enumerate(candidates):
        adjudication = by_candidate_index.get(candidate_index)
        if adjudication is None:
            next_rows[row_index] = _technical_error_for_candidate(
                original_item,
                "正式质控二审 LLM 响应缺少该规则裁决，进入内部技术异常。",
            )
            continue
        final_item = _apply_adjudication(original_item, adjudication)
        final_item["postprocess_mode"] = mode
        next_rows[row_index] = final_item
    return next_rows
