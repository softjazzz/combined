"""只读展示同次失败任务已保存的规范结果，不升级为完整正式交付。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..case_identity import CaseRef
from ..luxian_0609.phase_scope import frozen_luxian_0609_delivery_scope
from .canonical_result_store import (
    canonical_envelope_items_are_consistent, keyed_ref, validated_customer_explanation,
)


def saved_record_rule_scope(filters: Mapping[str, Any], ref: CaseRef) -> list[str]:
    scope = frozen_luxian_0609_delivery_scope(filters)
    mapping = filters.get("record_rule_map")
    if not isinstance(mapping, Mapping) or not mapping:
        return scope
    values = mapping.get(ref.as_key(), mapping.get(ref.visit_id))
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError("saved_record_scope_invalid")
    scoped = list(dict.fromkeys([
        *(value.strip().upper() for value in values),
        *filters.get("paused_customer_rule_ids", []),
        *filters.get("gate_only_customer_rule_ids", []),
    ]))
    if not scoped or not set(scoped) <= set(scope):
        raise ValueError("saved_record_scope_invalid")
    return scoped


def read_saved_partial_record(
    *, summary: Mapping[str, Any], items: list[Any], failures: list[Any], ref: CaseRef,
    expected_rules: list[str], projection_key: str,
    projector: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """从顶层权威成功项校验同病例、同范围；不重判、不拼接其他轮次。"""
    if (
        not isinstance(summary, Mapping)
        or not isinstance(summary.get("rule_results"), list)
        or not isinstance(items, list)
        or not isinstance(failures, list)
    ):
        raise ValueError("saved_partial_result_invalid")
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("saved_partial_result_invalid")
        item_ref = CaseRef.from_mapping(item)
        if item_ref == ref:
            rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
            if not all(item_ref) or not rule_id or rule_id not in expected_rules:
                raise ValueError("saved_partial_result_invalid")
            if item.get("schema_version") not in {"lx0609-customer-result-v2", "customer-qc-result-v1"}:
                raise ValueError("saved_partial_result_invalid")
            rows.append(item)
    if not canonical_envelope_items_are_consistent(rows):
        raise ValueError("saved_partial_result_invalid")
    failed_rules: list[str] = []
    safe_failures: list[dict[str, str]] = []
    for failure in failures:
        if not isinstance(failure, Mapping) or not all(CaseRef.from_mapping(failure)):
            raise ValueError("saved_partial_failure_invalid")
        if CaseRef.from_mapping(failure) != ref:
            continue
        rule_id = str(failure.get("rule_id") or failure.get("rule_code") or "").strip().upper()
        if rule_id not in expected_rules or rule_id in failed_rules:
            raise ValueError("saved_partial_failure_invalid")
        failed_rules.append(rule_id)
        # 失败详情只暴露规则身份，不输出原始异常或患者坐标。
        safe_failures.append({"rule_id": rule_id})
    delivered = {str(item.get("rule_id") or item.get("rule_code")) for item in rows}
    if (not failed_rules or delivered & set(failed_rules)
            or delivered | set(failed_rules) != set(expected_rules)):
        raise ValueError("saved_partial_scope_invalid")
    record_ref = keyed_ref("rec", ref.as_key(), hmac_key=projection_key)
    projected = []
    for item in rows:
        try:
            validated_customer_explanation(item, rule_id=item["rule_id"], status=item["status"])
            public = projector(item)
        except ValueError:
            raise ValueError("saved_partial_result_invalid") from None
        public["record_ref"] = record_ref
        projected.append(public)
    return {
        "record_ref": record_ref, "items": projected,
        "execution_status": "partial_failed" if rows else "failed",
        "failed_rule_ids": failed_rules, "failed_rule_count": len(failed_rules),
        "failed_rules": safe_failures, "completed_rule_count": len(rows),
    }
