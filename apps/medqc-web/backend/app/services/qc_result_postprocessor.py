from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.services.qc_applicability_gates import GateDecision, run_applicability_gate


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
DIAGNOSIS_RULES = {"SC-020", "SC-047", "SC-125"}
DISCHARGE_COMPLETENESS_RULES = {"SC-118", "SC-121", "SC-123", "SC-125"}
NEGATIVE_ABSENCE_RULES = {"SC-037", "SC-050", "SC-051", "SC-081", "SC-097", "SC-099", "SC-100", "SC-107", "SC-108", "SC-110"}

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
    "缺原报告单",
    "缺报告单",
    "缺执行记录",
    "缺执行清单",
]

TECHNICAL_ERROR_KEYWORDS = ["批量执行异常", "provider", "rate limit", "timeout", "timed out", "解析失败"]
TRIGGER_WORDS = ["当前文书", "记录", "诊断", "医嘱", "检查", "检验", "病程", "会诊", "手术", "时间", "结果"]
VIOLATION_WORDS = ["未", "无", "缺", "矛盾", "不全", "不一致", "未记录", "未分析", "未处理", "不规范", "遗漏"]
COMPLIANCE_CLAIM_KEYWORDS = [
    "合规",
    "符合要求",
    "已记录",
    "记录了",
    "已有记录",
    "已给出处理意见",
    "给出处理意见",
    "已处理",
    "已分析",
    "未见明显异常且已处理",
    "无需整改",
]
EXPLICIT_VIOLATION_PHRASES = [
    "不合规",
    "不符合",
    "未记录",
    "未分析",
    "未处理",
    "未体现",
    "未落实",
    "未见处理",
    "缺少",
    "缺乏",
    "缺失",
    "遗漏",
    "不一致",
    "矛盾",
    "不全",
    "不规范",
]


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


def _has_explicit_violation(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return _contains_any(compact, EXPLICIT_VIOLATION_PHRASES)


def _has_compliance_claim_without_violation(findings: str, evidence: str, suggestion: str) -> bool:
    findings_compact = re.sub(r"\s+", "", findings)
    evidence_compact = re.sub(r"\s+", "", evidence)
    suggestion_compact = re.sub(r"\s+", "", suggestion)
    if not findings_compact:
        return False
    if _contains_any(findings_compact, ["不合规", "不符合要求"]):
        return False
    if _contains_any(findings_compact, COMPLIANCE_CLAIM_KEYWORDS) and not _has_explicit_violation(findings_compact):
        return True
    if (
        _contains_any(evidence_compact + suggestion_compact, COMPLIANCE_CLAIM_KEYWORDS)
        and _contains_any(findings_compact, ["缺", "未", "无", "不详"])
        and not _has_explicit_violation(evidence_compact + suggestion_compact)
    ):
        return True
    return False


def _evidence_supports_claimed_missing_dose(findings: str, evidence: str) -> bool:
    if "剂量" not in findings:
        return False
    dosage_pattern = r"\d+(?:\.\d+)?\s*(?:贴|片|粒|颗|支|瓶|袋|丸|枚|mg|g|ml|mL|单位|U)"
    route_or_frequency = ["外用", "口服", "静滴", "静脉", "bid", "tid", "qd", "qn", "q12h", "每日", "每次"]
    return bool(re.search(dosage_pattern, evidence, flags=re.IGNORECASE)) and _contains_any(evidence, route_or_frequency)


def _chinese_ngrams(text: str, *, min_len: int = 2, max_len: int = 4) -> set[str]:
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    grams: set[str] = set()
    for size in range(min_len, max_len + 1):
        for index in range(0, max(0, len(chars) - size + 1)):
            grams.add(chars[index : index + size])
    return grams


def _looks_like_header_only_evidence(evidence: str) -> bool:
    compact = re.sub(r"\s+", "", evidence)
    if len(compact) <= 40 and re.fullmatch(r"(【当前文书】)?(记录时间[:：])?\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?\d{0,2}:?\d{0,2}:?\d{0,2}", compact):
        return True
    header_markers = ["记录时间", "医生签名", "签名", "姓名", "科别", "住院号"]
    clinical_markers = ["诊断", "病程", "医嘱", "检查", "检验", "治疗", "手术", "会诊", "症状", "体征", "处理", "分析"]
    return len(compact) <= 50 and any(marker in compact for marker in header_markers) and not any(marker in compact for marker in clinical_markers)


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

    if (
        _safe_bool(metadata.get("technical_error_internal"))
        or _safe_bool(result.get("technical_error_internal"))
        or _safe_text(metadata.get("final_decision_source") or result.get("final_decision_source")) == "technical_error_fallback"
    ):
        problems.append("provider_error")
    if (
        _safe_int(metadata.get("provider_error_count") or result.get("provider_error_count"))
        or _safe_int(metadata.get("timeout_count") or result.get("timeout_count"))
        or _safe_int(metadata.get("rate_limit_count") or result.get("rate_limit_count"))
    ):
        problems.append("provider_error")
    if _contains_any(combined_lower, TECHNICAL_ERROR_KEYWORDS) or (confidence == 0 and not evidence and status == "uncertain"):
        problems.append("provider_error")

    if not evidence:
        problems.append("empty_evidence")
    elif len(evidence) < 20:
        problems.append("short_evidence")
    elif status == "non_compliant" and "..." in evidence and len(evidence) < 180:
        problems.append("truncated_evidence")
    elif _looks_like_header_only_evidence(evidence):
        problems.append("header_only_evidence")
    elif status == "non_compliant" and len(evidence) < 50:
        problems.append("weak_evidence_length")

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

    if status == "non_compliant" and _has_compliance_claim_without_violation(findings, evidence, suggestion):
        problems.append("status_findings_contradiction")
    if status == "non_compliant" and _evidence_supports_claimed_missing_dose(findings, evidence):
        problems.append("evidence_supports_compliance")

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

    if status == "non_compliant" and rule_id in DIAGNOSIS_RULES and "诊断" not in evidence:
        problems.append("diagnosis_context_missing")

    if status == "non_compliant" and rule_id in DISCHARGE_COMPLETENESS_RULES:
        discharge_markers = ["入院日期", "出院日期", "入院情况", "入院诊断", "诊疗经过", "出院情况", "出院医嘱", "医师签名", "出院记录"]
        if sum(1 for marker in discharge_markers if marker in evidence) < 2:
            problems.append("document_completeness_context_missing")

    if status == "non_compliant" and rule_id in NEGATIVE_ABSENCE_RULES:
        absence_markers = ["未见", "无", "缺", "未记录", "缺失", "查无", "未提供", "未体现", "仅见", "均为"]
        finding_claims_absence = _contains_any(findings + suggestion, ["未", "无", "缺", "未记录", "缺失", "仅见", "均为"])
        evidence_supports_absence = _contains_any(evidence, absence_markers)
        if finding_claims_absence and not evidence_supports_absence:
            problems.append("absence_proof_missing")

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

    display_status = "qc_review_candidate"
    display_bucket = "二审候选"
    postprocess_label = "needs_human_review"
    postprocess_reason = "自动准入层无法确认 trigger evidence 与 violation evidence 是否同时成立。"
    can_show_as_defect = False
    can_show_to_doctor = True
    internal_only = False
    metadata = _metadata(next_result)
    is_subitem_anchor = _safe_bool(metadata.get("formal_subitem_anchor")) or bool(
        _safe_text(next_result.get("anchor_id") or next_result.get("subitem_id"))
    )

    if is_subitem_anchor:
        if _safe_text(next_result.get("display_status")) == "data_quality_gap" or "data_quality_gap" in problems:
            display_status = "data_quality_gap"
            display_bucket = "数据缺口"
            postprocess_label = "data_gap_not_defect"
            postprocess_reason = "正式质控子锚点缺少必要对照证据，不能作为医生病历缺陷。"
        else:
            display_status = "qc_review_candidate"
            display_bucket = "二审候选"
            postprocess_label = "needs_human_review"
            postprocess_reason = "正式质控子锚点默认进入二审候选，不直接作为确认缺陷。"
    elif "provider_error" in problems:
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
        can_show_to_doctor = False
    elif status == "uncertain":
        if set(problems) & {
            "empty_evidence",
            "short_evidence",
            "weak_evidence_length",
            "truncated_evidence",
            "header_only_evidence",
            "evidence_findings_mismatch",
        }:
            display_status = "rejected_by_system"
            display_bucket = "系统驳回"
            postprocess_label = "evidence_insufficient"
            postprocess_reason = "原始 uncertain 证据不足或与结论不匹配，不进入质控员主复核清单。"
            can_show_to_doctor = False
            internal_only = True
        else:
            display_status = "qc_review_candidate"
            display_bucket = "二审候选"
            postprocess_label = "needs_human_review"
            postprocess_reason = "原始结果为 uncertain，但具备一定病历证据，可作为质控员确认候选。"
    elif status == "non_compliant":
        rejected = {
            "empty_evidence",
            "short_evidence",
            "weak_evidence_length",
            "truncated_evidence",
            "header_only_evidence",
            "evidence_findings_mismatch",
            "trigger_missing",
            "violation_missing",
            "status_findings_contradiction",
            "evidence_supports_compliance",
        }
        review_candidate = {
            "cross_doc_proof_missing",
            "temporal_proof_missing",
            "diagnosis_context_missing",
            "document_completeness_context_missing",
            "absence_proof_missing",
        }
        if set(problems) & rejected:
            display_status = "rejected_by_system"
            display_bucket = "系统驳回"
            postprocess_label = "evidence_insufficient"
            postprocess_reason = "原始不合规结论存在证据不足、自相矛盾或证据支持合规的问题，系统驳回。"
            can_show_to_doctor = False
            internal_only = True
        elif set(problems) & review_candidate:
            display_status = "qc_review_candidate"
            display_bucket = "二审候选"
            postprocess_label = "needs_human_review"
            postprocess_reason = "疑似具备业务价值，但仍缺少跨文书、时间链或专门上下文闭环，需质控员确认。"
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
    next_result = _apply_applicability_gate(next_result, mode=mode)
    return next_result


def _apply_applicability_gate(result: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """Apply deterministic applicability gates after generic postprocess.

    Gates only narrow or route results. They never produce direct confirmed defects.
    """
    if "formal" not in _safe_text(mode):
        return result
    gate_result = run_applicability_gate(result)
    if gate_result.gate_decision == GateDecision.NO_ACTION:
        return result

    next_result = dict(result)
    metadata = _metadata(next_result)
    gate_payload = gate_result.to_metadata()
    metadata.update(
        {
            "applicability_gate": gate_payload,
            "applicability_gate_decision": gate_result.gate_decision.value,
            "applicability_gate_reason": gate_result.reason,
            "applicability_gate_metadata": dict(gate_result.metadata),
            "applicability_gate_evidence_quote": gate_result.evidence_quote,
            "applicability_gate_terminal": gate_result.gate_decision
            in {GateDecision.DATA_QUALITY_GAP, GateDecision.REJECTED_BY_SYSTEM},
        }
    )
    next_result.update(
        {
            "metadata": metadata,
            "applicability_gate": gate_result.gate_name,
            "applicability_gate_decision": gate_result.gate_decision.value,
            "applicability_gate_reason": gate_result.reason,
            "applicability_gate_metadata": dict(gate_result.metadata),
            "applicability_gate_evidence_quote": gate_result.evidence_quote,
            "applicability_gate_confirmed_allowed": False,
            "applicability_gate_needs_second_pass": gate_result.needs_second_pass_gate,
        }
    )

    if gate_result.gate_decision == GateDecision.DATA_QUALITY_GAP:
        next_result.update(
            {
                "display_status": "data_quality_gap",
                "display_bucket": "数据缺口",
                "postprocess_label": "data_gap_not_defect",
                "postprocess_reason": gate_result.reason,
                "can_show_as_defect": False,
                "can_show_to_doctor": False,
                "internal_only": False,
            }
        )
    elif gate_result.gate_decision == GateDecision.REJECTED_BY_SYSTEM:
        next_result.update(
            {
                "display_status": "rejected_by_system",
                "display_bucket": "系统驳回",
                "postprocess_label": "rejected_by_system",
                "postprocess_reason": gate_result.reason,
                "can_show_as_defect": False,
                "can_show_to_doctor": False,
                "internal_only": True,
            }
        )
    elif gate_result.gate_decision == GateDecision.PASS_TO_SECOND_GATE:
        next_result.update(
            {
                "display_status": "qc_review_candidate",
                "display_bucket": "二审候选",
                "postprocess_label": "needs_human_review",
                "postprocess_reason": gate_result.reason,
                "can_show_as_defect": False,
                "can_show_to_doctor": True,
                "internal_only": False,
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
        "qc_review_candidate_count": int(display_counts.get("qc_review_candidate") or 0),
        "needs_review_count": int(display_counts.get("qc_review_candidate") or display_counts.get("needs_review") or 0),
        "data_quality_gap_count": int(display_counts.get("data_quality_gap") or 0),
        "rejected_by_system_count": int(display_counts.get("rejected_by_system") or 0),
        "technical_error_internal_count": int(display_counts.get("technical_error_internal") or 0),
        "non_compliant_downgraded_count": len(downgraded),
        "downgraded_rule_top10": [
            {"rule_id": rule_id, "count": count}
            for rule_id, count in Counter(_safe_text(row.get("rule_id")) for row in downgraded).most_common(10)
        ],
    }
