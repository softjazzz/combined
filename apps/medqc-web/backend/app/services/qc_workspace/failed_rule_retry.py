"""部分失败任务的精确补跑范围与结果合并合同。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..case_identity import CaseRef
from ..llm_context_contract import CONTEXT_FAILURE_REASON_CODES


FAILED_RULE_RETRY_FILTER_KEY = "failed_rule_retry"
FAILED_RULE_RETRY_SCHEMA_VERSION = "failed-rule-retry-v1"
FAILED_RULE_AUTO_RETRY_MAX_ATTEMPTS = 3
_FAILED_RULE_AUTO_RETRY_DELAYS_SECONDS = (0.0, 1.0, 3.0)
_FAILED_RULE_AUTO_RETRY_PHASES = frozenset({"result_status", "result_missing"})
# 同样输入重跑仍会得到同样失败的确定性原因：隐私护栏拦截、程序缺陷、单条交付合同
# 不满足，以及执行器输出缺失/重复等结构问题。不自动补跑，避免空耗模型调用。
_DETERMINISTIC_FAILURE_REASON_CODES = frozenset({
    *CONTEXT_FAILURE_REASON_CODES,
    "privacy_guard_blocked",
    "execution_program_error",
    "customer_result_contract_violation",
    "family_result_invalid",
    "family_result_missing",
    "family_result_duplicate",
    "family_result_extra",
    "family_result_order_mismatch",
    "family_result_scope_mismatch",
    # 候选材料超出单次抽取规模上限（如 03-01-04 会诊措施逐项核对），由输入规模决定，重跑结果不变。
    "candidate_scope_incomplete",
})
# 模型输出不合格式：结构化抽取按温度 0 调用，同样输入重跑得到同样输出（第四轮 3 次补跑 19 条
# 未恢复）。不自动补跑；超时、网络、限流等偶发错误仍自动补跑，人工定向重跑不受影响。
_OUTPUT_FORMAT_FAILURE_REASON_CODES = frozenset({
    "model_invalid_output",
    "model_parse_error",
})


def _automatic_retryable_failure(failure: Mapping[str, Any]) -> bool:
    rule = str(failure.get("rule_id") or failure.get("rule_code") or "").strip().upper()
    if rule.startswith("LX0609-"):
        from ..luxian_0609.phase_scope import get_luxian_0609_phase_scope

        scope = get_luxian_0609_phase_scope(rule)
        if scope is not None and scope.phase_status == "pending_definition":
            return False
    reason = str(failure.get("reason_code") or "")
    if reason in _DETERMINISTIC_FAILURE_REASON_CODES or reason in _OUTPUT_FORMAT_FAILURE_REASON_CODES:
        return False
    if rule == "LX0609-05-01-03" and reason in {
        "model_invalid_output", "model_parse_error", "model_transport_error", "model_timeout",
        "model_rate_limited", "model_upstream_error", "model_http_error",
        "model_configuration_error", "execution_program_error",
    }:
        # 055已在一次规则执行内消费最多两次抽取预算，不再整条自动重跑。
        return False
    if rule == "LX0609-03-01-04" and reason in {
        "executor_exception",
        "model_invalid_output", "model_parse_error", "model_http_error",
        "model_configuration_error", "execution_program_error",
    }:
        return False
    return True


def build_failed_rule_auto_retry_plan(
    *,
    summary: Mapping[str, Any],
    failures: Sequence[Mapping[str, Any]],
    retry_scope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """决定是否自动补跑模型输出失败，不把永久错误变成无限调用。"""

    current_attempt = max(0, int((retry_scope or {}).get("attempt") or 0))
    base = {
        "max_attempts": FAILED_RULE_AUTO_RETRY_MAX_ATTEMPTS,
        "completed_attempts": current_attempt,
        "remaining_failure_count": len(failures),
    }
    if not failures:
        return {**base, "status": "completed", "should_retry": False}
    if str(summary.get("execution_status") or "").strip().lower() not in {
        "partial_failed",
        "failed",
    }:
        return {**base, "status": "not_applicable", "should_retry": False}
    if any(
        str(failure.get("error_phase") or "").strip().lower()
        not in _FAILED_RULE_AUTO_RETRY_PHASES
        for failure in failures
    ):
        return {**base, "status": "not_retryable", "should_retry": False}
    if not any(_automatic_retryable_failure(failure) for failure in failures):
        return {**base, "status": "not_retryable", "should_retry": False}
    if current_attempt >= FAILED_RULE_AUTO_RETRY_MAX_ATTEMPTS:
        return {**base, "status": "exhausted", "should_retry": False}

    return {
        **base,
        "status": "planned",
        "should_retry": True,
        "next_attempt": current_attempt + 1,
        "delay_seconds": _FAILED_RULE_AUTO_RETRY_DELAYS_SECONDS[current_attempt],
    }


def _rule_id(value: Mapping[str, Any]) -> str:
    return str(value.get("rule_id") or value.get("rule_code") or "").strip().upper()


def _case_ref(value: Mapping[str, Any]) -> CaseRef:
    return CaseRef.from_mapping(value)


def _result_key(value: Mapping[str, Any]) -> tuple[str, str, str, str]:
    case_ref = _case_ref(value)
    return (*case_ref, _rule_id(value))


def _ordered_unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def build_failed_rule_retry_scope(job: Mapping[str, Any], *, automatic_only: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """为叶子任务生成精确补跑范围，并补齐旧失败项缺失的三坐标。"""

    summary = job.get("summary") if isinstance(job.get("summary"), Mapping) else {}
    if (
        str(job.get("status") or "").strip().lower() != "failed"
        or str(summary.get("execution_status") or "").strip().lower()
        not in {"partial_failed", "failed"}
        or str(job.get("job_kind") or "leaf").strip().lower() == "parent"
        or not list(job.get("failed_records") or [])
    ):
        return None

    filters = job.get("filters") if isinstance(job.get("filters"), Mapping) else {}
    record_refs = [
        _case_ref(value)
        for value in list(filters.get("record_refs") or [])
        if isinstance(value, Mapping) and all(_case_ref(value))
    ]
    by_key = {case_ref.as_key(): case_ref for case_ref in record_refs}
    by_visit: dict[str, list[CaseRef]] = {}
    for case_ref in record_refs:
        by_visit.setdefault(case_ref.visit_id, []).append(case_ref)

    normalized_failures: list[dict[str, Any]] = []
    retry_refs: list[CaseRef] = []
    retry_rule_ids: list[str] = []
    retry_record_rule_map: dict[str, list[str]] = {}
    seen_pairs: set[tuple[str, str, str, str]] = set()
    for raw_failure in list(job.get("failed_records") or []):
        if not isinstance(raw_failure, Mapping):
            raise ValueError("失败规则补跑清单包含无效条目")
        rule_id = _rule_id(raw_failure)
        if not rule_id:
            raise ValueError("失败规则补跑清单缺少规则号")
        failure_ref = _case_ref(raw_failure)
        if not all(failure_ref):
            record_key = str(raw_failure.get("record_key") or "").strip()
            failure_ref = by_key.get(record_key, CaseRef("", "", ""))
        if not all(failure_ref):
            visit_id = str(raw_failure.get("visit_id") or raw_failure.get("record_id") or "").strip()
            matches = by_visit.get(visit_id, [])
            if len(matches) != 1:
                raise ValueError("失败规则补跑无法唯一定位病历三坐标")
            failure_ref = matches[0]
        if record_refs and failure_ref not in record_refs:
            raise ValueError("失败规则补跑引用了原任务范围外的病历")

        pair = (*failure_ref, rule_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        normalized_failures.append(
            {
                **dict(raw_failure),
                **failure_ref.as_dict(),
                "record_key": failure_ref.as_key(),
                "record_id": str(raw_failure.get("record_id") or failure_ref.visit_id).strip(),
                "rule_id": rule_id,
            }
        )
        if automatic_only and not _automatic_retryable_failure(raw_failure):
            continue
        if failure_ref not in retry_refs:
            retry_refs.append(failure_ref)
        retry_rule_ids.append(rule_id)
        retry_record_rule_map.setdefault(failure_ref.as_key(), []).append(rule_id)

    if not retry_refs:
        return None
    previous_scope = filters.get(FAILED_RULE_RETRY_FILTER_KEY)
    previous_attempt = (
        int(previous_scope.get("attempt") or 0)
        if isinstance(previous_scope, Mapping)
        else 0
    )
    original_rule_order = [str(value or "").strip().upper() for value in list(filters.get("rule_ids") or [])]
    retry_rule_set = set(retry_rule_ids)
    ordered_rule_ids = [rule_id for rule_id in original_rule_order if rule_id in retry_rule_set]
    ordered_rule_ids.extend(rule_id for rule_id in retry_rule_ids if rule_id not in ordered_rule_ids)
    return (
        {
            "schema_version": FAILED_RULE_RETRY_SCHEMA_VERSION,
            "attempt": previous_attempt + 1,
            "record_refs": [case_ref.as_dict() for case_ref in retry_refs],
            "rule_ids": _ordered_unique(ordered_rule_ids),
            "record_rule_map": {
                record_key: _ordered_unique(rule_ids)
                for record_key, rule_ids in retry_record_rule_map.items()
            },
            "pending_count": sum(len(values) for values in retry_record_rule_map.values()),
        },
        normalized_failures,
    )


def merge_failed_rule_retry_results(
    *,
    base_items: Sequence[Mapping[str, Any]],
    base_failures: Sequence[Mapping[str, Any]],
    retry_items: Sequence[Mapping[str, Any]],
    retry_failures: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """只允许补跑结果替换原失败病例规则对，避免改写既有有效结果。"""

    pending = {_result_key(value): dict(value) for value in base_failures}
    if any(not all(key) for key in pending):
        raise ValueError("失败规则补跑合并缺少完整病例三坐标或规则号")

    retried_items: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    retried_failures: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for raw_item in retry_items:
        item = dict(raw_item)
        key = _result_key(item)
        if key not in pending:
            raise ValueError("失败规则补跑返回了范围外的临床结果")
        if key in retried_items:
            raise ValueError("失败规则补跑对同一病例规则返回了重复结果")
        retried_items[key] = item
    for raw_failure in retry_failures:
        failure = dict(raw_failure)
        key = _result_key(failure)
        if key not in pending:
            raise ValueError("失败规则补跑返回了范围外的失败项")
        if key in retried_failures:
            raise ValueError("失败规则补跑对同一病例规则返回了重复失败项")
        retried_failures[key] = failure
    if set(retried_items) & set(retried_failures):
        raise ValueError("失败规则补跑对同一病例规则同时返回结果和失败")

    merged_items = [dict(value) for value in base_items]
    merged_items.extend(retried_items.values())
    merged_failures = [
        retried_failures.get(key, original)
        for key, original in pending.items()
        if key not in retried_items
    ]
    return merged_items, merged_failures


def merge_failed_rule_retry_rule_results(
    *,
    base_rule_results: Sequence[Mapping[str, Any]],
    retry_rule_results: Sequence[Mapping[str, Any]],
    merged_items: Sequence[Mapping[str, Any]],
    merged_failures: Sequence[Mapping[str, Any]],
    total_records: int,
) -> list[dict[str, Any]]:
    """重建规则视图，使明细、失败数与任务合并结果保持一致。"""

    ordered_rule_ids: list[str] = []
    templates: dict[str, dict[str, Any]] = {}
    for raw in [*base_rule_results, *retry_rule_results]:
        rule_result = dict(raw)
        rule_id = _rule_id(rule_result)
        if not rule_id:
            continue
        if rule_id not in templates:
            ordered_rule_ids.append(rule_id)
        templates[rule_id] = {**templates.get(rule_id, {}), **rule_result}

    items_by_rule: dict[str, list[dict[str, Any]]] = {}
    failures_by_rule: dict[str, list[dict[str, Any]]] = {}
    for raw in merged_items:
        item = dict(raw)
        items_by_rule.setdefault(_rule_id(item), []).append(item)
    for raw in merged_failures:
        failure = dict(raw)
        failures_by_rule.setdefault(_rule_id(failure), []).append(failure)

    rebuilt: list[dict[str, Any]] = []
    for rule_id in ordered_rule_ids:
        template = templates[rule_id]
        items = items_by_rule.get(rule_id, [])
        failures = failures_by_rule.get(rule_id, [])
        failed_record_keys = {_case_ref(value) for value in failures}
        issue_record_keys = {
            _case_ref(value)
            for value in items
            if str(value.get("status") or "").strip().lower()
            in {"non_compliant", "ai_suggested_non_compliant"}
        }
        compliant_record_keys = {
            _case_ref(value)
            for value in items
            if str(value.get("status") or "").strip().lower()
            in {"compliant", "ai_suggested_compliant"}
        }
        rebuilt.append(
            {
                **template,
                "rule_code": str(template.get("rule_code") or rule_id).strip().upper(),
                "status": "failed" if failures else "completed",
                "items": items,
                "failed_records": failures,
                "total_records": max(0, int(total_records)),
                "success_count": max(0, int(total_records) - len(failed_record_keys)),
                "failed_count": len(failures),
                "issue_records": len(issue_record_keys),
                "compliant_records": len(compliant_record_keys),
            }
        )
    return rebuilt
