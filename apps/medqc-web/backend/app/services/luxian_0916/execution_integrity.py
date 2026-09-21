"""LX0916 批任务交付完整性合同，不解释临床结论。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import Luxian0916RuleResult
from .rule_catalog import LUXIAN_0916_RULE_CATALOG


_CATALOG_RULE_IDS = frozenset(rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG)
_IDENTITY_FIELDS = ("institute_id", "patient_id", "visit_id")
_RULE_ID_ALIASES = ("rule_code", "customer_rule_id", "qc_point_id")
LUXIAN_0916_RULE_SET_KEY = "luxian_0916_qc_v1"
LUXIAN_0916_RULE_IDS = tuple(rule.rule_id for rule in LUXIAN_0916_RULE_CATALOG)

RecordIdentity = tuple[str, str, str]
DeliveryPair = tuple[RecordIdentity, str]


def validate_luxian_0916_task_delivery(
    *,
    summary: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    expected_rule_ids: Sequence[str],
    expected_record_refs: Sequence[Mapping[str, Any]] = (),
) -> None:
    """验证每个计划病例和规则恰好形成一个结果或一条执行失败。"""

    if not isinstance(summary, Mapping):
        raise ValueError("0916 任务摘要无效")
    planned_rule_ids = _normalize_expected_rule_ids(expected_rule_ids)
    item_pairs = _collect_result_pairs(items, planned_rule_ids)
    failure_pairs = _collect_failure_pairs(failures, planned_rule_ids)
    overlap = item_pairs.intersection(failure_pairs)
    if overlap:
        raise ValueError("0916 同一病例规则不能同时存在结果和执行失败")

    observed_records = {identity for identity, _rule_id in item_pairs | failure_pairs}
    expected_records = _expected_records(
        expected_record_refs=expected_record_refs,
        observed_records=observed_records,
        summary=summary,
    )
    planned_pairs = {
        (identity, rule_id)
        for identity in expected_records
        for rule_id in planned_rule_ids
    }
    delivered_pairs = item_pairs | failure_pairs
    unexpected = delivered_pairs.difference(planned_pairs)
    if unexpected:
        raise ValueError("0916 交付含计划外病例或规则")
    missing = planned_pairs.difference(delivered_pairs)
    if missing:
        raise ValueError("0916 交付缺失计划病例规则")

    _validate_summary(
        summary=summary,
        expected_record_count=len(expected_records),
        expected_rule_count=len(planned_rule_ids),
        item_pairs=item_pairs,
        failure_pairs=failure_pairs,
    )


def _normalize_expected_rule_ids(values: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise ValueError("0916 计划规则必须是序列")
    rule_ids = tuple(str(value or "").strip().upper() for value in values)
    if not rule_ids or any(not rule_id for rule_id in rule_ids):
        raise ValueError("0916 计划规则不能为空")
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("0916 计划规则不能重复")
    if set(rule_ids).difference(_CATALOG_RULE_IDS):
        raise ValueError("0916 计划含未知规则")
    return rule_ids


def _collect_result_pairs(
    items: Sequence[Mapping[str, Any]],
    planned_rule_ids: Sequence[str],
) -> set[DeliveryPair]:
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise ValueError("0916 结果清单无效")
    planned = set(planned_rule_ids)
    pairs: set[DeliveryPair] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("0916 结果项无效")
        identity = _identity(item, kind="结果")
        rule_id = str(item.get("rule_id") or "").strip().upper()
        if rule_id not in planned:
            raise ValueError("0916 结果含计划外规则")
        for alias in _RULE_ID_ALIASES:
            alias_value = str(item.get(alias) or "").strip().upper()
            if alias_value and alias_value != rule_id:
                raise ValueError("0916 结果规则身份不一致")
        _validate_native_result(item, rule_id=rule_id)
        pair = (identity, rule_id)
        if pair in pairs:
            raise ValueError("0916 结果含重复病例规则")
        pairs.add(pair)
    return pairs


def _collect_failure_pairs(
    failures: Sequence[Mapping[str, Any]],
    planned_rule_ids: Sequence[str],
) -> set[DeliveryPair]:
    if not isinstance(failures, Sequence) or isinstance(
        failures, (str, bytes, bytearray)
    ):
        raise ValueError("0916 执行失败清单无效")
    planned = set(planned_rule_ids)
    pairs: set[DeliveryPair] = set()
    for failure in failures:
        if not isinstance(failure, Mapping):
            raise ValueError("0916 执行失败项无效")
        identity = _identity(failure, kind="执行失败")
        rule_id = str(failure.get("rule_id") or "").strip().upper()
        if rule_id not in planned:
            raise ValueError("0916 执行失败含计划外规则")
        if not str(failure.get("error_phase") or "").strip():
            raise ValueError("0916 执行失败缺少阶段")
        pair = (identity, rule_id)
        if pair in pairs:
            raise ValueError("0916 执行失败含重复病例规则")
        pairs.add(pair)
    return pairs


def _validate_native_result(item: Mapping[str, Any], *, rule_id: str) -> None:
    try:
        Luxian0916RuleResult(
            rule_id=rule_id,
            status=item.get("status"),
            reason_code=item.get("reason_code"),
            findings=item.get("findings"),
            evidence=_tuple_field(item.get("evidence"), field="evidence"),
            suggestion=item.get("suggestion") or "",
            document_anchors=_tuple_field(
                item.get("document_anchors"), field="document_anchors"
            ),
            diagnostics=item.get("diagnostics") or {},
            decision_facts=item.get("decision_facts") or {},
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("0916 结果不符合原生交付合同") from exc


def _tuple_field(value: Any, *, field: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"0916 结果字段 {field} 必须是列表")
    return tuple(value)


def _expected_records(
    *,
    expected_record_refs: Sequence[Mapping[str, Any]],
    observed_records: set[RecordIdentity],
    summary: Mapping[str, Any],
) -> set[RecordIdentity]:
    if expected_record_refs:
        records = [_identity(ref, kind="计划病例") for ref in expected_record_refs]
        if len(set(records)) != len(records):
            raise ValueError("0916 计划病例不能重复")
        expected_records = set(records)
    else:
        expected_records = set(observed_records)
    expected_count = _nonnegative_int(summary.get("total_records"), "total_records")
    if len(expected_records) != expected_count:
        raise ValueError("0916 病例计数与计划不一致")
    return expected_records


def _validate_summary(
    *,
    summary: Mapping[str, Any],
    expected_record_count: int,
    expected_rule_count: int,
    item_pairs: set[DeliveryPair],
    failure_pairs: set[DeliveryPair],
) -> None:
    failed_records = {identity for identity, _rule_id in failure_pairs}
    completed_record_count = expected_record_count - len(failed_records)
    expected_status = (
        "partial_failed"
        if failure_pairs and item_pairs
        else "failed"
        if failure_pairs
        else "completed"
    )
    expected_values = {
        "rule_count": expected_rule_count,
        "total_records": expected_record_count,
        "success_count": completed_record_count,
        "failed_count": len(failed_records),
        "completed_rule_count": len(item_pairs),
        "failed_rule_count": len(failure_pairs),
    }
    for key, expected in expected_values.items():
        if _nonnegative_int(summary.get(key), key) != expected:
            raise ValueError(f"0916 任务摘要 {key} 与交付不一致")
    if "failed_record_count" in summary and _nonnegative_int(
        summary.get("failed_record_count"), "failed_record_count"
    ) != len(failed_records):
        raise ValueError("0916 任务摘要 failed_record_count 与交付不一致")
    if str(summary.get("execution_status") or "").strip() != expected_status:
        raise ValueError("0916 任务状态与结果/失败分布不一致")


def _identity(value: Mapping[str, Any], *, kind: str) -> RecordIdentity:
    identity = tuple(str(value.get(field) or "").strip() for field in _IDENTITY_FIELDS)
    if not all(identity):
        raise ValueError(f"0916 {kind}缺少病例身份")
    return identity[0], identity[1], identity[2]


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"0916 任务摘要 {field} 无效")
    return value


__all__ = [
    "LUXIAN_0916_RULE_IDS",
    "LUXIAN_0916_RULE_SET_KEY",
    "validate_luxian_0916_task_delivery",
]
