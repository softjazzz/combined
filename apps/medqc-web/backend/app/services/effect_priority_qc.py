from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable


QUALITY_PROFILE_THROUGHPUT = "throughput_v1"
QUALITY_PROFILE_EFFECT_PRIORITY = "effect_priority_v1"
DEFAULT_REFINE_CONFIDENCE_THRESHOLD = 0.75
DEFAULT_MAX_REFINE_CANDIDATES = 3
BATCH_OUTPUT_MODE_FULL = "full"
BATCH_OUTPUT_MODE_MINIMAL = "minimal"

ALLOWED_QUALITY_PROFILES = {
    QUALITY_PROFILE_THROUGHPUT,
    QUALITY_PROFILE_EFFECT_PRIORITY,
}

ALLOWED_BATCH_OUTPUT_MODES = {
    BATCH_OUTPUT_MODE_FULL,
    BATCH_OUTPUT_MODE_MINIMAL,
}

EFFECT_FAMILY_PACK_CANDIDATES: dict[str, tuple[int, ...]] = {
    "presence_required": (10, 12, 15),
    "timeliness": (3, 5),
    "signature_authority": (3, 5),
    "content_completeness": (5, 8),
    "consistency_cross_doc": (3,),
    "procedure_order_linkage": (3, 5),
    "general": (5, 8),
}

# 线上保守固定值。候选集保留给离线基准探测，避免每份病历现场试包。
EFFECT_FAMILY_FIXED_PACK_SIZES: dict[str, int] = {
    "presence_required": 10,
    "timeliness": 3,
    "signature_authority": 3,
    "content_completeness": 5,
    "consistency_cross_doc": 3,
    "procedure_order_linkage": 3,
    "general": 5,
}

EFFECT_FAMILY_CHECK_LIMITS: dict[str, int] = {
    "presence_required": 360,
    "timeliness": 900,
    "signature_authority": 900,
    "content_completeness": 760,
    "consistency_cross_doc": 900,
    "procedure_order_linkage": 820,
    "general": 520,
}

HIGH_RISK_FAMILIES = {"timeliness", "signature_authority"}
CONTRADICTION_NO_CHANGE_PATTERNS = (
    r"(无需|无须).{0,4}(修改|调整|处理|整改|更改|改动|补充)",
    r"无需整改",
    r"无需处理",
    r"无需完善",
    r"符合规则要求",
    r"符合要求",
    r"无明显问题",
)
PROBLEM_STATUS = {"non_compliant", "uncertain"}


def normalize_quality_profile(value: Any) -> str:
    normalized = str(value or QUALITY_PROFILE_THROUGHPUT).strip().lower() or QUALITY_PROFILE_THROUGHPUT
    if normalized not in ALLOWED_QUALITY_PROFILES:
        return QUALITY_PROFILE_THROUGHPUT
    return normalized


def is_effect_priority_profile(value: Any) -> bool:
    return normalize_quality_profile(value) == QUALITY_PROFILE_EFFECT_PRIORITY


def normalize_batch_output_mode(value: Any, *, quality_profile: Any = QUALITY_PROFILE_THROUGHPUT) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in ALLOWED_BATCH_OUTPUT_MODES:
        return normalized
    if is_effect_priority_profile(quality_profile):
        return BATCH_OUTPUT_MODE_MINIMAL
    return BATCH_OUTPUT_MODE_FULL


def normalize_max_refine_candidates(value: Any, *, default: int = DEFAULT_MAX_REFINE_CANDIDATES) -> int:
    try:
        parsed = int(value)
    except Exception:
        return max(0, int(default or 0))
    return max(0, parsed)


def normalize_rule_family(value: Any) -> str:
    normalized = str(value or "general").strip().lower() or "general"
    return normalized if normalized in EFFECT_FAMILY_PACK_CANDIDATES else "general"


def family_pack_candidates(
    rule_family: Any,
    *,
    quality_profile: str,
    default_candidates: Iterable[int],
) -> tuple[int, ...]:
    if not is_effect_priority_profile(quality_profile):
        return tuple(int(item) for item in default_candidates)
    return EFFECT_FAMILY_PACK_CANDIDATES.get(normalize_rule_family(rule_family), EFFECT_FAMILY_PACK_CANDIDATES["general"])


def family_fixed_pack_size(
    rule_family: Any,
    *,
    available_count: int,
    max_pack_size: int,
) -> int:
    """返回线上固定安全包大小；不得在单病例请求中发起探测调用。"""

    configured = EFFECT_FAMILY_FIXED_PACK_SIZES.get(
        normalize_rule_family(rule_family),
        EFFECT_FAMILY_FIXED_PACK_SIZES["general"],
    )
    return max(1, min(int(configured), max(1, int(available_count)), max(1, int(max_pack_size))))


def family_check_limit(rule_family: Any, *, quality_profile: str) -> int:
    if not is_effect_priority_profile(quality_profile):
        return 200
    return EFFECT_FAMILY_CHECK_LIMITS.get(normalize_rule_family(rule_family), EFFECT_FAMILY_CHECK_LIMITS["general"])


def evidence_limits_for_family(rule_family: Any, *, quality_profile: str) -> dict[str, int]:
    if not is_effect_priority_profile(quality_profile):
        return {
            "primary_limit": 12000,
            "support_limit": 6,
            "support_snippet_limit": 500,
            "timeline_limit": 12,
            "timeline_snippet_limit": 220,
            "min_primary_limit": 1500,
        }

    family = normalize_rule_family(rule_family)
    if family == "presence_required":
        return {
            "primary_limit": 9000,
            "support_limit": 10,
            "support_snippet_limit": 360,
            "timeline_limit": 8,
            "timeline_snippet_limit": 220,
            "min_primary_limit": 2200,
        }
    if family == "timeliness":
        return {
            "primary_limit": 15000,
            "support_limit": 10,
            "support_snippet_limit": 620,
            "timeline_limit": 40,
            "timeline_snippet_limit": 320,
            "min_primary_limit": 3200,
        }
    if family == "signature_authority":
        return {
            "primary_limit": 16000,
            "support_limit": 10,
            "support_snippet_limit": 760,
            "timeline_limit": 12,
            "timeline_snippet_limit": 240,
            "min_primary_limit": 3600,
        }
    if family == "content_completeness":
        return {
            "primary_limit": 18000,
            "support_limit": 8,
            "support_snippet_limit": 900,
            "timeline_limit": 16,
            "timeline_snippet_limit": 260,
            "min_primary_limit": 4200,
        }
    if family == "consistency_cross_doc":
        return {
            "primary_limit": 16000,
            "support_limit": 12,
            "support_snippet_limit": 820,
            "timeline_limit": 16,
            "timeline_snippet_limit": 260,
            "min_primary_limit": 4200,
        }
    if family == "procedure_order_linkage":
        return {
            "primary_limit": 15000,
            "support_limit": 12,
            "support_snippet_limit": 760,
            "timeline_limit": 24,
            "timeline_snippet_limit": 280,
            "min_primary_limit": 3600,
        }
    return {
        "primary_limit": 14000,
        "support_limit": 8,
        "support_snippet_limit": 620,
        "timeline_limit": 16,
        "timeline_snippet_limit": 240,
        "min_primary_limit": 2600,
    }


def family_keywords(rule_family: Any) -> tuple[str, ...]:
    family = normalize_rule_family(rule_family)
    if family == "presence_required":
        return ("记录", "文书", "表单", "审批", "缺失", "未见", "入院", "出院", "病程", "手术", "麻醉")
    if family == "timeliness":
        return ("时间", "小时", "24", "8", "入院", "出院", "术后", "记录时间", "完成时间", "日期")
    if family == "signature_authority":
        return ("签名", "签字", "医师", "审核", "审签", "主任", "上级", "授权", "记录者", "书写")
    if family == "content_completeness":
        return ("病例特点", "诊断依据", "鉴别诊断", "诊疗计划", "诊疗经过", "现病史", "主诉", "出院情况")
    if family == "consistency_cross_doc":
        return ("一致", "诊断", "主诉", "现病史", "出院诊断", "入院诊断", "手术名称", "检查结果")
    if family == "procedure_order_linkage":
        return ("手术", "麻醉", "医嘱", "检查", "检验", "病理", "治疗", "术前", "术后")
    return ()


def select_family_snippet(text: Any, *, rule_family: Any, limit: int) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw

    keywords = family_keywords(rule_family)
    if not keywords:
        return raw[:limit] + "..."

    windows: list[str] = []
    half = max(120, int(limit / max(2, min(4, len(keywords)))))
    lowered = raw.lower()
    for keyword in keywords:
        marker = str(keyword).lower()
        pos = lowered.find(marker)
        if pos < 0:
            continue
        start = max(0, pos - half)
        end = min(len(raw), pos + half)
        windows.append(raw[start:end].strip())
        if sum(len(item) for item in windows) >= limit:
            break

    if not windows:
        if normalize_rule_family(rule_family) == "signature_authority":
            head = raw[: max(1, limit // 2)]
            tail = raw[-max(1, limit // 2) :]
            return f"{head}\n...\n{tail}"
        return raw[:limit] + "..."

    snippet = "\n...\n".join(windows)
    if len(snippet) > limit:
        snippet = snippet[:limit] + "..."
    return snippet


def has_logical_contradiction(result: dict[str, Any]) -> bool:
    status = str(result.get("status") or "").strip().lower()
    findings = str(result.get("findings") or "").strip()
    suggestion = str(result.get("suggestion") or "").strip()
    evidence = str(result.get("evidence") or "").strip()
    combined_no_space = f"{findings}{suggestion}".replace(" ", "")

    if status == "non_compliant":
        if not evidence:
            return True
        return any(re.search(pattern, combined_no_space) for pattern in CONTRADICTION_NO_CHANGE_PATTERNS)
    if status == "compliant":
        return any(token in combined_no_space for token in ("不合规", "未完成", "缺失", "未见", "建议补充", "建议修正"))
    return False


def select_refine_candidates(
    results: list[dict[str, Any]],
    *,
    rules_by_id: dict[str, dict[str, Any]],
    confidence_threshold: float = DEFAULT_REFINE_CONFIDENCE_THRESHOLD,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    threshold = float(confidence_threshold or DEFAULT_REFINE_CONFIDENCE_THRESHOLD)

    for result in results:
        rule_id = str(result.get("rule_id") or result.get("rule_code") or "").strip().upper()
        if not rule_id or rule_id in seen:
            continue
        rule = dict(rules_by_id.get(rule_id) or {})
        metadata = dict(result.get("metadata") or {})
        family = normalize_rule_family(metadata.get("rule_family") or rule.get("rule_family"))
        status = str(result.get("status") or "").strip().lower()
        confidence = _safe_float(result.get("confidence"), default=0.0)
        defect_level = str(rule.get("defect_level") or result.get("defect_level") or "").strip()

        reasons: list[str] = []
        if status == "uncertain":
            reasons.append("uncertain")
        if confidence < threshold:
            reasons.append("low_confidence")
        if status == "non_compliant" and ("严重" in defect_level or "重度" in defect_level):
            reasons.append("severe_non_compliant")
        if status in PROBLEM_STATUS and family in HIGH_RISK_FAMILIES:
            reasons.append(f"high_risk_family:{family}")
        if has_logical_contradiction(result):
            reasons.append("logical_contradiction")

        if reasons:
            candidates.append(
                {
                    "rule_id": rule_id,
                    "rule": rule,
                    "screening_result": result,
                    "refine_reason": ",".join(dict.fromkeys(reasons)),
                }
            )
            seen.add(rule_id)
    return candidates


def merge_refined_results(
    *,
    screening_results: list[dict[str, Any]],
    refined_results_by_rule: dict[str, dict[str, Any]],
    refine_reasons_by_rule: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    refine_reason_counter: Counter[str] = Counter()
    refined_rule_count = 0
    refine_failed_count = 0

    for item in screening_results:
        rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        reason = str(refine_reasons_by_rule.get(rule_id) or "")
        screening_metadata = dict(item.get("metadata") or {})
        if reason:
            for part in [token for token in reason.split(",") if token.strip()]:
                refine_reason_counter[part] += 1

        if rule_id in refined_results_by_rule:
            refined = dict(refined_results_by_rule[rule_id] or {})
            screening_status = str(item.get("status") or "")
            metadata = dict(refined.get("metadata") or {})
            for key in (
                "executor_type",
                "rule_version",
                "prompt_version",
                "model_version",
                "evidence_source",
                "execution_domain",
                "doc_scope",
                "rule_family",
                "cost_class",
                "bucket_strategy",
                "bucket_key",
                "quality_profile",
            ):
                if screening_metadata.get(key) not in (None, ""):
                    metadata.setdefault(key, screening_metadata.get(key))
            metadata.update(
                {
                    "qc_stage": "refine",
                    "refined": True,
                    "refine_reason": reason,
                    "screening_status": screening_status,
                    "final_decision_source": "single_refine",
                }
            )
            refined["metadata"] = metadata
            refined_rule_count += 1
            merged.append(refined)
            continue

        fallback = dict(item or {})
        metadata = dict(fallback.get("metadata") or {})
        if reason:
            refine_failed_count += 1 if metadata.get("refine_failed") else 0
        metadata.setdefault("qc_stage", "screening")
        metadata.setdefault("refined", False)
        metadata.setdefault("refine_reason", reason)
        metadata.setdefault("screening_status", str(item.get("status") or ""))
        metadata.setdefault("final_decision_source", "batch")
        fallback["metadata"] = metadata
        merged.append(fallback)

    summary = {
        "refined_rule_count": refined_rule_count,
        "refine_failed_count": refine_failed_count,
        "refine_reasons": dict(refine_reason_counter),
    }
    return merged, summary


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default
