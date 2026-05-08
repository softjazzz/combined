from __future__ import annotations

import re
from collections import Counter
from typing import Any


CROSS_DOC_RULES = {
    "SC-036",
    "SC-038",
    "SC-070",
    "SC-074",
    "SC-107",
    "SC-123",
    "SC-125",
    "SC-143",
    "SC-146",
}

TEMPORAL_RULES = {"SC-037", "SC-051", "SC-052", "SC-105", "SC-118", "SC-119", "SC-121"}

DATA_GAP_KEYWORDS = [
    "未提供",
    "缺乏原文",
    "无法判定",
    "证据不足",
    "补充长期医嘱单",
    "补充临时医嘱单",
    "补充原报告单",
    "缺文书",
    "缺医嘱",
    "缺执行",
    "缺少可",
    "未取得",
    "无法获取",
    "缺对应医嘱原文",
]

TECHNICAL_ERROR_KEYWORDS = ["批量执行异常", "provider", "rate limit", "timeout", "timed out", "解析失败"]
TRIGGER_WORDS = ["当前文书", "记录", "诊断", "医嘱", "检查", "检验", "病程", "会诊", "手术", "时间", "结果"]
VIOLATION_WORDS = ["未", "无", "缺", "矛盾", "不全", "不一致", "未记录", "未分析", "未处理", "不规范", "遗漏"]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def _metadata(result: dict[str, Any]) -> dict[str, Any]:
    meta = result.get("metadata")
    return dict(meta) if isinstance(meta, dict) else {}


def _contains_any(text: str, keywords: list[str] | set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _chinese_ngrams(text: str, *, min_len: int = 2, max_len: int = 4) -> set[str]:
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    grams: set[str] = set()
    for size in range(min_len, max_len + 1):
        for index in range(0, max(0, len(chars) - size + 1)):
            grams.add(chars[index : index + size])
    return grams


def _problem_types(result: dict[str, Any], *, bundle_metadata: dict[str, Any] | None = None) -> list[str]:
    rule_id = _safe_text(result.get("rule_id")).upper()
    status = _safe_text(result.get("status"))
    confidence = _safe_float(result.get("confidence"))
    findings = _safe_text(result.get("findings"))
    evidence = _safe_text(result.get("evidence"))
    suggestion = _safe_text(result.get("suggestion"))
    metadata = _metadata(result)
    combined = f"{findings} {evidence} {suggestion}"
    combined_lower = combined.lower()
    problems: list[str] = []

    if _safe_bool(metadata.get("technical_error_internal")) or _safe_text(metadata.get("final_decision_source")) == "technical_error_fallback":
        problems.append("provider_error")
    if _safe_int(metadata.get("provider_error_count")) or _safe_int(metadata.get("timeout_count")) or _safe_int(metadata.get("rate_limit_count")):
        problems.append("provider_error")
    if _contains_any(combined_lower, TECHNICAL_ERROR_KEYWORDS) or (confidence == 0 and not evidence and status == "uncertain"):
        problems.append("provider_error")

    if not evidence:
        problems.append("empty_evidence")
    elif len(evidence) < 20:
        problems.append("short_evidence")

    if _contains_any(combined, DATA_GAP_KEYWORDS):
        problems.append("data_quality_gap")

    data_quality_flags = " ".join(str(item) for item in list((bundle_metadata or {}).get("data_quality_flags") or []))
    data_quality_flags += " " + _safe_text(result.get("data_quality_flags"))
    if "missing:" in data_quality_flags and _contains_any(combined, ["缺文书", "缺医嘱", "缺执行", "无法判定", "补充原", "补充长期"]):
        problems.append("source_doc_missing")

    has_trigger = _contains_any(evidence + " " + findings, TRIGGER_WORDS)
    has_violation = _contains_any(findings + " " + suggestion, VIOLATION_WORDS)
    if status == "non_compliant" and not has_trigger:
        problems.append("trigger_missing")
    if status == "non_compliant" and not has_violation:
        problems.append("violation_missing")

    if status == "non_compliant" and evidence and findings:
        evidence_tokens = _chinese_ngrams(evidence)
        finding_tokens = _chinese_ngrams(findings)
        if len(evidence_tokens & finding_tokens) < 1 and len(evidence) < 80:
            problems.append("evidence_findings_mismatch")

    if rule_id in CROSS_DOC_RULES:
        cross_markers = ["检查", "检验", "报告", "医嘱", "会诊", "诊断", "病程", "对照", "时间", "复查", "处理", "执行"]
        marker_hits = sum(1 for marker in cross_markers if marker in combined)
        current_doc_only = evidence.startswith("【当前文书】") and len(evidence) < 180
        if marker_hits < 2 or current_doc_only:
            problems.append("cross_doc_proof_missing")

    if rule_id in TEMPORAL_RULES:
        has_date = bool(re.search(r"\d{4}[-年/]\d{1,2}|\d{1,2}月\d{1,2}日|\d{1,2}:\d{2}|小时|天|日", combined))
        has_interval = _contains_any(combined, ["至", "到", "后", "前", "间隔", "连续", "超过", "未在"])
        if not (has_date and has_interval):
            problems.append("temporal_proof_missing")

    return sorted(set(problems)) or ["none"]


def postprocess_qc_result(
    result: dict[str, Any],
    *,
    bundle_metadata: dict[str, Any] | None = None,
    mode: str = "formal_final",
) -> dict[str, Any]:
    next_result = dict(result)
    status = _safe_text(next_result.get("status"))
    problems = _problem_types(next_result, bundle_metadata=bundle_metadata)

    display_status = "needs_review"
    display_bucket = "待复核"
    postprocess_label = "needs_human_review"
    postprocess_reason = "自动准入层无法确认 trigger evidence 与 violation evidence 是否同时成立。"
    can_show_as_defect = False
    can_show_to_doctor = True
    internal_only = False

    if "provider_error" in problems:
        display_status = "technical_error_internal"
        display_bucket = "内部技术异常"
        postprocess_label = "technical_error"
        postprocess_reason = "provider、批量解析或 pack 执行异常，仅进入内部诊断，不作为医生缺陷。"
        can_show_to_doctor = False
        internal_only = True
    elif status in {"compliant", "not_applicable"}:
        display_status = status
        display_bucket = "合规/不适用"
        postprocess_label = "pass_through"
        postprocess_reason = "原始结果为合规或不适用，不进入缺陷清单。"
        can_show_to_doctor = False
    elif "data_quality_gap" in problems or "source_doc_missing" in problems:
        display_status = "data_quality_gap"
        display_bucket = "数据缺口"
        postprocess_label = "data_gap_not_defect"
        postprocess_reason = "结果依赖缺文书、缺医嘱、缺执行清单或其他数据缺口，不能作为医生病历缺陷。"
    elif status == "uncertain":
        display_status = "needs_review"
        display_bucket = "待复核"
        postprocess_label = "evidence_insufficient" if set(problems) & {"empty_evidence", "short_evidence"} else "needs_human_review"
        postprocess_reason = "原始结果为 uncertain，需人工复核后才能进入缺陷层。"
    elif status == "non_compliant":
        blocking = {
            "empty_evidence",
            "short_evidence",
            "evidence_findings_mismatch",
            "trigger_missing",
            "violation_missing",
            "cross_doc_proof_missing",
            "temporal_proof_missing",
        }
        if set(problems) & blocking:
            display_status = "needs_review"
            display_bucket = "待复核"
            postprocess_label = "evidence_insufficient"
            postprocess_reason = "evidence 不足或缺少跨文书/时间链对照，不能直接作为确认缺陷。"
        else:
            display_status = "confirmed_defect"
            display_bucket = "确认缺陷"
            postprocess_label = "likely_valid"
            postprocess_reason = "具备可读 evidence，未命中技术异常、数据缺口或关键证据不足。"
            can_show_as_defect = True

    next_result.update(
        {
            "display_status": display_status,
            "display_bucket": display_bucket,
            "postprocess_label": postprocess_label,
            "postprocess_reason": postprocess_reason,
            "evidence_problem_type": ",".join(problems),
            "can_show_as_defect": can_show_as_defect,
            "can_show_to_doctor": can_show_to_doctor,
            "internal_only": internal_only,
            "postprocess_mode": mode,
        }
    )
    return next_result


def postprocess_qc_results(
    results: list[dict[str, Any]],
    *,
    bundle_metadata: dict[str, Any] | None = None,
    mode: str = "formal_final",
) -> list[dict[str, Any]]:
    return [postprocess_qc_result(dict(item), bundle_metadata=bundle_metadata, mode=mode) for item in results]


def summarize_postprocessed_results(rows: list[dict[str, Any]]) -> dict[str, Any]:
    display_counts = Counter(_safe_text(row.get("display_status")) for row in rows)
    label_counts = Counter(_safe_text(row.get("postprocess_label")) for row in rows)
    confirmed = [row for row in rows if _safe_bool(row.get("can_show_as_defect"))]
    downgraded = [
        row
        for row in rows
        if _safe_text(row.get("status")) == "non_compliant" and not _safe_bool(row.get("can_show_as_defect"))
    ]
    return {
        "total": len(rows),
        "raw_status_counts": dict(Counter(_safe_text(row.get("status")) for row in rows)),
        "display_status_counts": dict(display_counts),
        "postprocess_label_counts": dict(label_counts),
        "confirmed_defect_count": len(confirmed),
        "needs_review_count": int(display_counts.get("needs_review") or 0),
        "data_quality_gap_count": int(display_counts.get("data_quality_gap") or 0),
        "technical_error_internal_count": int(display_counts.get("technical_error_internal") or 0),
        "non_compliant_downgraded_count": len(downgraded),
        "downgraded_rule_top10": [
            {"rule_id": rule_id, "count": count}
            for rule_id, count in Counter(_safe_text(row.get("rule_id")) for row in downgraded).most_common(10)
        ],
    }
