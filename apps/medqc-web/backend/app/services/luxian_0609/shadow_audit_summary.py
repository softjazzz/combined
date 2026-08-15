"""LX0609 专项影子运行的安全审计摘要。

这里是影子结果离开执行上下文前的唯一投影边界。它只保留受控枚举、计数、
Token 与耗时；不保留三坐标、文书/事件标识、正文或模型报文。摘要只写入
批量任务 ``summary_json``，不会写入正式 Canonical 结果。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .surgery_text_fact_contract import LX0609_025_REQUIRED_FIELDS


_SHADOW_SPECS = {
    "luxian_0609_025_shadow": {
        "contract_version": "lx0609-025-shadow-v1",
        "count_fields": (
            "operation_count",
            "llm_calls",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "elapsed_ms",
        ),
        "counter_fields": {"missing_field_counts": frozenset(LX0609_025_REQUIRED_FIELDS)},
        "allowed_reasons": frozenset(
            {
                "surgery_text_fact_satisfied",
                "surgery_text_fact_defect",
                "surgery_text_fact_absent",
                "surgery_text_fact_unknown",
                "source_missing",
                "source_query_error",
                "source_unavailable",
                "source_truncated",
                "source_material_invalid",
                "evaluation_failed",
                "result_contract_invalid",
            }
        ),
    },
    "luxian_0609_059_shadow": {
        "contract_version": "lx0609-059-shadow-v1",
        "count_fields": (
            "event_count",
            "matched_order_count",
            "missing_order_count",
            "conflict_order_count",
            "llm_calls",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "elapsed_ms",
        ),
        "counter_fields": {},
        "allowed_reasons": frozenset(
            {
                "trigger_absent_complete",
                "event_kind_unsupported",
                "event_id_missing",
                "event_id_duplicated",
                "event_source_ref_missing",
                "event_time_missing",
                "order_association_key_missing",
                "order_association_ambiguous",
                "order_association_conflict",
                "order_association_unresolved",
                "order_reused_across_events",
                "order_source_ref_missing",
                "order_time_missing",
                "order_action_unknown",
                "required_order_missing",
                "course_documentation_missing",
                "course_documentation_conflict",
                "course_source_ref_missing",
                "course_source_ref_conflict",
                "semantic_association_ambiguous",
                "requirement_satisfied",
                "llm_context_oversized",
                "llm_prompt_token_limit_exceeded",
                "llm_token_count_invalid",
                "redaction_terms_missing",
                "llm_transport_error",
                "llm_response_invalid",
                "llm_usage_invalid",
                "llm_usage_prompt_token_limit_exceeded",
                "llm_output_token_limit_exceeded",
                "events_source_unavailable",
                "events_source_truncated",
                "events_source_query_error",
                "events_source_state_invalid",
                "orders_source_unavailable",
                "orders_source_truncated",
                "orders_source_query_error",
                "orders_source_state_invalid",
                "course_notes_source_unavailable",
                "course_notes_source_truncated",
                "course_notes_source_query_error",
                "course_notes_source_state_invalid",
                "adapter_failed",
                "evaluation_failed",
                "result_contract_invalid",
            }
        ),
    },
}
_ALLOWED_STATUSES = frozenset(
    {"compliant", "non_compliant", "not_applicable", "data_gap", "shadow_error"}
)


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("invalid shadow counter")
    return value


def _invalid_summary(*, spec: Mapping[str, Any]) -> dict[str, Any]:
    contract_version = str(spec["contract_version"])
    return {
        "shadow_only": True,
        "release_eligible": False,
        "status": "shadow_error",
        "reason_code": "result_contract_invalid",
        "contract_version": contract_version,
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "elapsed_ms": 0,
        **{field_name: 0 for field_name in tuple(spec["count_fields"])},
        **{field_name: {} for field_name in dict(spec["counter_fields"])},
    }


def _project_one(raw: object, *, spec: Mapping[str, Any]) -> dict[str, Any]:
    contract_version = str(spec["contract_version"])
    if not isinstance(raw, Mapping):
        return _invalid_summary(spec=spec)
    try:
        status = raw.get("status")
        reason_code = raw.get("reason_code")
        if (
            raw.get("shadow_only") is not True
            or raw.get("release_eligible") is not False
            or status not in _ALLOWED_STATUSES
            or not isinstance(reason_code, str)
            or reason_code not in spec["allowed_reasons"]
            or raw.get("contract_version") != contract_version
        ):
            raise ValueError("invalid shadow header")
        projected: dict[str, Any] = {
            "shadow_only": True,
            "release_eligible": False,
            "status": status,
            "reason_code": reason_code,
            "contract_version": contract_version,
        }
        for field_name in tuple(spec["count_fields"]):
            projected[field_name] = _nonnegative_int(raw.get(field_name, 0))
        status_counts = raw.get("status_counts", {})
        if not isinstance(status_counts, Mapping):
            raise ValueError("invalid status counts")
        projected["status_counts"] = {
            key: _nonnegative_int(value)
            for key, value in status_counts.items()
            if isinstance(key, str) and key in _ALLOWED_STATUSES
        }
        if len(projected["status_counts"]) != len(status_counts):
            raise ValueError("invalid status counts")
        for field_name, allowed_keys in dict(spec["counter_fields"]).items():
            counters = raw.get(field_name, {})
            if not isinstance(counters, Mapping):
                raise ValueError("invalid shadow counters")
            projected[field_name] = {
                key: _nonnegative_int(value)
                for key, value in counters.items()
                if isinstance(key, str) and key in allowed_keys
            }
            if len(projected[field_name]) != len(counters):
                raise ValueError("invalid shadow counters")
        return projected
    except (TypeError, ValueError):
        return _invalid_summary(spec=spec)


def project_luxian_0609_shadow_summaries(orchestrated: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """将执行上下文中的影子结果投影为可持久化的安全摘要。"""

    if not isinstance(orchestrated, Mapping):
        return {}
    return {
        key: _project_one(orchestrated[key], spec=spec)
        for key, spec in _SHADOW_SPECS.items()
        if key in orchestrated
    }


def merge_luxian_0609_shadow_summaries(
    aggregate: dict[str, dict[str, Any]],
    summaries: Mapping[str, Any],
) -> None:
    """按批量任务汇总已投影的影子摘要，不记录病例身份或逐事件事实。"""

    for key, spec in _SHADOW_SPECS.items():
        raw = summaries.get(key) if isinstance(summaries, Mapping) else None
        if raw is None:
            continue
        summary = _project_one(raw, spec=spec)
        target = aggregate.setdefault(
            key,
            {
                "shadow_only": True,
                "release_eligible": False,
                "contract_version": str(spec["contract_version"]),
                "records_evaluated": 0,
                "status_counts": {},
                "reason_counts": {},
                **{field_name: 0 for field_name in tuple(spec["count_fields"])},
                **{field_name: {} for field_name in dict(spec["counter_fields"])},
            },
        )
        target["records_evaluated"] += 1
        status = str(summary["status"])
        reason = str(summary["reason_code"])
        target["status_counts"][status] = int(target["status_counts"].get(status, 0)) + 1
        target["reason_counts"][reason] = int(target["reason_counts"].get(reason, 0)) + 1
        for field_name in tuple(spec["count_fields"]):
            target[field_name] += int(summary[field_name])
        for field_name in dict(spec["counter_fields"]):
            counters = target[field_name]
            for counter_key, counter_value in dict(summary[field_name]).items():
                counters[counter_key] = int(counters.get(counter_key, 0)) + int(counter_value)


__all__ = [
    "merge_luxian_0609_shadow_summaries",
    "project_luxian_0609_shadow_summaries",
]
