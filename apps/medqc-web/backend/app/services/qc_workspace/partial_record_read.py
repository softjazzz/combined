"""只读展示同次失败任务已保存的规范结果，不升级为完整正式交付。"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from typing import Any

from ..case_identity import CaseRef
from ..luxian_0609.phase_scope import frozen_luxian_0609_delivery_scope
from .canonical_result_store import (
    canonical_envelope_items_are_consistent, keyed_ref, validated_customer_explanation,
)


# Worker 也曾以 material_capture 保存装配失败，装配专属码不属于取材失败。
MATERIAL_PREPARATION_FAILURE_CODES = frozenset({
    "material_capture_failed",
    "material_source_contract_incomplete",
    "material_source_contract_unavailable",
    "material_source_unavailable",
    "original_task_material_not_retained",
    "material_retry_lineage_invalid",
    "material_integrity_failed",
    "material_reference_corrupt",
    "material_object_unavailable",
    "material_identity_or_source_mismatch",
    "material_publication_identity_conflict",
    "material_publication_version_conflict",
    "cdm_publication_window_unconfirmed",
})
MATERIAL_PREPARATION_FAILURE_STAGES = frozenset({"material_capture", "material_preparation"})
_LEGACY_PREPARATION_CODES = frozenset({
    "material_source_contract_incomplete", "material_identity_or_source_mismatch",
})


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


def _record_material_preparation_failure(
    items: list[dict[str, Any]], failures: list[Mapping[str, Any]], ref: CaseRef,
) -> dict[str, str]:
    """只认 Worker 保存的同病例、无规则身份且零项的资料准备失败。"""
    if items or len(failures) != 1:
        return {}
    failure = failures[0]
    reason = failure.get("reason_code", failure.get("error"))
    stage = failure.get("material_failure_stage")
    if (
        failure.get("error_phase") != "material_capture"
        or not isinstance(reason, str) or reason not in MATERIAL_PREPARATION_FAILURE_CODES
        or stage not in (None, "capture")
        or failure.get("record_key", ref.as_key()) != ref.as_key()
        or failure.get("rule_id") or failure.get("rule_code")
    ):
        return {}
    # 旧任务没有子阶段，部分原因也可能在装配阶段产生。
    failure_stage = (
        "material_preparation" if stage is None and reason in _LEGACY_PREPARATION_CODES
        else "material_capture"
    )
    return {"reason_code": reason, "failure_stage": failure_stage}


def _has_exact_preparation_identity(entry: Mapping[str, Any]) -> bool:
    return all(
        isinstance(entry.get(key), str) and entry[key] and entry[key] == entry[key].strip()
        for key in CaseRef._fields
    ) and entry.get("record_id", entry["visit_id"]) == entry["visit_id"]


@dataclass
class SavedPartialRecordBatch:
    """一次摘要请求内按任务解析并索引，按原始病例三键读回。"""

    has_rule_results: bool
    items: dict[CaseRef, list[dict[str, Any]]]
    failures: dict[CaseRef, list[Mapping[str, Any]]]
    preparation_identities_valid: bool

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> SavedPartialRecordBatch:
        try:
            summary = json.loads(row["summary_json"])
            items = json.loads(row["items_json"])
            failures = json.loads(row["failed_records_json"])
        except (TypeError, ValueError):
            raise ValueError("saved_partial_result_invalid") from None
        if not (isinstance(summary, dict) and isinstance(items, list) and isinstance(failures, list)):
            raise ValueError("saved_partial_result_invalid")
        items_by_ref: dict[CaseRef, list[dict[str, Any]]] = {}
        failures_by_ref: dict[CaseRef, list[Mapping[str, Any]]] = {}
        exact_identities = True
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("saved_partial_result_invalid")
            items_by_ref.setdefault(CaseRef.from_mapping(item), []).append(item)
            exact_identities = exact_identities and _has_exact_preparation_identity(item)
        for failure in failures:
            if not isinstance(failure, Mapping) or not all(ref := CaseRef.from_mapping(failure)):
                raise ValueError("saved_partial_failure_invalid")
            failures_by_ref.setdefault(ref, []).append(failure)
            exact_identities = exact_identities and _has_exact_preparation_identity(failure)
        return cls(isinstance(summary.get("rule_results"), list), items_by_ref, failures_by_ref, exact_identities)

    def read(
        self, *, ref: CaseRef, expected_rules: list[str], projection_key: str,
        projector: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        items = self.items.get(ref, [])
        failures = self.failures.get(ref, [])
        if self.preparation_identities_valid:
            preparation_failure = _record_material_preparation_failure(items, failures, ref)
            if preparation_failure:
                return {**preparation_failure, "items": []}
        if not self.has_rule_results:
            raise ValueError("saved_partial_result_invalid")
        return _project_saved_partial_record(
            items=items, failures=failures, ref=ref, expected_rules=expected_rules,
            projection_key=projection_key, projector=projector,
        )


def read_saved_partial_record_row(
    row: Mapping[str, Any], *, ref: CaseRef, expected_rules: list[str],
    projection_key: str, projector: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """单例详情和批量摘要共用持久失败任务的读取边界。"""
    return SavedPartialRecordBatch.from_row(row).read(
        ref=ref, expected_rules=expected_rules,
        projection_key=projection_key, projector=projector,
    )


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
        if CaseRef.from_mapping(item) == ref:
            rows.append(item)
    matching_failures = []
    for failure in failures:
        if not isinstance(failure, Mapping) or not all(CaseRef.from_mapping(failure)):
            raise ValueError("saved_partial_failure_invalid")
        if CaseRef.from_mapping(failure) == ref:
            matching_failures.append(failure)
    return _project_saved_partial_record(
        items=rows, failures=matching_failures, ref=ref, expected_rules=expected_rules,
        projection_key=projection_key, projector=projector,
    )


def _project_saved_partial_record(
    *, items: list[dict[str, Any]], failures: list[Mapping[str, Any]], ref: CaseRef,
    expected_rules: list[str], projection_key: str,
    projector: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    for item in items:
        rule_id = str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        if not all(ref) or not rule_id or rule_id not in expected_rules:
            raise ValueError("saved_partial_result_invalid")
        if item.get("schema_version") not in {"lx0609-customer-result-v2", "customer-qc-result-v1"}:
            raise ValueError("saved_partial_result_invalid")
    if not canonical_envelope_items_are_consistent(items):
        raise ValueError("saved_partial_result_invalid")
    failed_rules: list[str] = []
    safe_failures: list[dict[str, str]] = []
    for failure in failures:
        rule_id = str(failure.get("rule_id") or failure.get("rule_code") or "").strip().upper()
        if rule_id not in expected_rules or rule_id in failed_rules:
            raise ValueError("saved_partial_failure_invalid")
        failed_rules.append(rule_id)
        # 失败详情只暴露规则身份，不输出原始异常或患者坐标。
        safe_failures.append({"rule_id": rule_id})
    delivered = {str(item.get("rule_id") or item.get("rule_code")) for item in items}
    if (not failed_rules or delivered & set(failed_rules)
            or delivered | set(failed_rules) != set(expected_rules)):
        raise ValueError("saved_partial_scope_invalid")
    record_ref = keyed_ref("rec", ref.as_key(), hmac_key=projection_key)
    projected = []
    for item in items:
        try:
            validated_customer_explanation(item, rule_id=item["rule_id"], status=item["status"])
            public = projector(item)
        except (KeyError, ValueError):
            raise ValueError("saved_partial_result_invalid") from None
        public["record_ref"] = record_ref
        projected.append(public)
    return {
        "record_ref": record_ref, "items": projected,
        "execution_status": "partial_failed" if items else "failed",
        "failed_rule_ids": failed_rules, "failed_rule_count": len(failed_rules),
        "failed_rules": safe_failures, "completed_rule_count": len(items),
    }
