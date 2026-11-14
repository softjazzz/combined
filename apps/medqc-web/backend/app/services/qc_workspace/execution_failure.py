"""任务执行失败分流与检查检验模型计数，不判定临床语义。"""

import re
from typing import Any, Dict, Optional

from ..qc_execution_errors import safe_failure_projection
from .canonical_result_store import (
    canonical_envelope_items_are_consistent,
    validated_customer_explanation,
)

_LUXIAN_EXECUTION_FAILURE_STATUSES = frozenset(
    {"technical_error", "uncertain", "evaluation_unknown", "model_failure"}
)
_LUXIAN_MODEL_EXECUTION_COUNT_KEYS = (
    "requested_rule_count",
    "first_success_rule_count",
    "retried_rule_count",
    "recovered_rule_count",
    "failed_rule_count",
)


def _normalize_luxian_model_execution_stats(value: Any) -> Optional[Dict[str, int]]:
    """只接受检查检验族的计数；任务层统一按病例累加并重算比率。"""

    if not isinstance(value, dict):
        return None
    scope = str(value.get("scope") or "").strip().lower()
    if scope and scope != "exam_lab":
        return None
    normalized: Dict[str, int] = {}
    for key in _LUXIAN_MODEL_EXECUTION_COUNT_KEYS:
        raw = value.get(key)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            return None
        normalized[key] = raw
    if (
        normalized["first_success_rule_count"] + normalized["retried_rule_count"] > normalized["requested_rule_count"]
        or normalized["recovered_rule_count"] > normalized["retried_rule_count"]
        or normalized["first_success_rule_count"] + normalized["recovered_rule_count"] + normalized["failed_rule_count"] != normalized["requested_rule_count"]
    ):
        return None
    return normalized


def _merge_luxian_model_execution_stats(
    current: Optional[Dict[str, int]],
    incoming: Optional[Dict[str, int]],
) -> Optional[Dict[str, int]]:
    if incoming is None:
        return current
    merged = dict(current or {key: 0 for key in _LUXIAN_MODEL_EXECUTION_COUNT_KEYS})
    for key in _LUXIAN_MODEL_EXECUTION_COUNT_KEYS:
        merged[key] = int(merged.get(key) or 0) + int(incoming.get(key) or 0)
    return merged


def _extract_luxian_model_execution_stats(value: Any) -> Optional[Dict[str, int]]:
    """读取执行入口已有的统计字段，不从规则结果重复累加。"""

    if not isinstance(value, dict):
        return None
    return _normalize_luxian_model_execution_stats(value.get("model_execution_stats"))


def _is_luxian_execution_failure(
    *,
    raw_status: str,
    eval_item: Dict[str, Any],
    metadata: Dict[str, Any],
) -> bool:
    """将不可交付的正式结果留在失败集合，避免后续层伪装为资料缺口或合规。"""

    status_candidates = {
        str(raw_status or "").strip().lower(),
        str(eval_item.get("status") or "").strip().lower(),
        str(eval_item.get("result_status") or "").strip().lower(),
        str(eval_item.get("display_status") or "").strip().lower(),
    }
    if status_candidates & _LUXIAN_EXECUTION_FAILURE_STATUSES:
        return True
    if metadata.get("technical_error_internal") is True:
        return True
    return metadata.get("result_fallback") == "missing_customer_result"


def _safe_luxian_failure_reason_code(
    eval_item: Dict[str, Any],
    metadata: Dict[str, Any],
) -> str:
    for source in (eval_item, metadata):
        value = str(source.get("reason_code") or "").strip().lower()
        if re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", value) and len(value) <= 64:
            return value
    return "execution_failed"


def _build_luxian_execution_failure_record(
    *,
    rule_job_id: str,
    rule_id: str,
    rule_code: str,
    rule_name: str,
    record_id: str,
    record_key: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    raw_status: str,
    eval_item: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "rule_job_id": rule_job_id,
        "rule_id": str(rule_id or "").strip().upper(),
        "rule_code": str(rule_code or rule_id or "").strip().upper(),
        "rule_name": str(rule_name or rule_id or "").strip(),
        "record_id": record_id,
        "record_key": record_key,
        "institute_id": institute_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "error_phase": "result_status",
        "failure_status": str(raw_status or eval_item.get("status") or "execution_failed")
        .strip()
        .lower(),
        **safe_failure_projection({
            "reason_code": _safe_luxian_failure_reason_code(eval_item, metadata),
            "retryable": eval_item.get("retryable", metadata.get("retryable")),
        }),
    }


def _build_luxian_model_execution_summary(
    totals: Optional[Dict[str, int]],
) -> Optional[Dict[str, Any]]:
    if totals is None:
        return None
    requested = int(totals.get("requested_rule_count") or 0)
    retried = int(totals.get("retried_rule_count") or 0)
    return {
        "scope": "exam_lab",
        **{key: int(totals.get(key) or 0) for key in _LUXIAN_MODEL_EXECUTION_COUNT_KEYS},
        "first_answer_success_rate": (
            int(totals.get("first_success_rule_count") or 0) / requested
            if requested
            else None
        ),
        "recovery_success_rate": (
            int(totals.get("recovered_rule_count") or 0) / retried
            if retried
            else None
        ),
        "model_failure_rate": (
            int(totals.get("failed_rule_count") or 0) / requested
            if requested
            else None
        ),
    }


def validate_failed_task_items(summary: dict, items: list, failures: list) -> None:
    """失败任务只保存已形成合法结论的条目，不能借失败分支绕过交付校验。"""
    if not failures or any(not isinstance(row, dict) for row in failures):
        raise ValueError("执行失败任务必须保留失败清单")
    if summary.get("execution_status") != ("partial_failed" if items else "failed"):
        raise ValueError("执行失败任务状态与有效条目不一致")
    if summary.get("completed_rule_count") != len(items) or summary.get("failed_rule_count") != len(failures):
        raise ValueError("执行失败任务计数与条目不一致")
    grouped: dict[tuple, list] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("执行失败任务含非法结果项")
        key = tuple(str(item.get(field) or "").strip() for field in ("institute_id", "patient_id", "visit_id"))
        if not all(key):
            raise ValueError("执行失败任务的有效结果缺少病例身份")
        grouped.setdefault(key, []).append(item)
    for rows in grouped.values():
        if not canonical_envelope_items_are_consistent(rows):
            raise ValueError("执行失败任务含不可交付的临床条目")
        for item in rows:
            validated_customer_explanation(item, rule_id=str(item.get("rule_id") or item.get("rule_code")), status=item["status"])
