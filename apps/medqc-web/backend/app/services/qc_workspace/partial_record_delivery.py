"""从部分失败批次中选出可以独立正式交付的完整病历。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..case_identity import CaseRef


def select_complete_record_items(
    *,
    items: Sequence[Mapping[str, Any]],
    failures: Sequence[Mapping[str, Any]],
    expected_rule_ids: Sequence[str],
) -> tuple[tuple[dict[str, Any], ...], tuple[CaseRef, ...]]:
    """仅返回没有失败项且规则集合完整的病历结果。

    任一失败项缺少病例三坐标时无法证明其他结果属于独立病例，整批保持不交付。
    Canonical Store 仍负责状态一致性、客户解释和证据合同的最终校验。
    """

    expected = {
        str(rule_id or "").strip().upper()
        for rule_id in expected_rule_ids
        if str(rule_id or "").strip()
    }
    if not expected:
        return (), ()

    failed_refs: set[CaseRef] = set()
    for failure in failures:
        if not isinstance(failure, Mapping):
            return (), ()
        record_ref = CaseRef.from_mapping(failure)
        if not all(record_ref):
            return (), ()
        failed_refs.add(record_ref)

    grouped: dict[CaseRef, list[dict[str, Any]]] = {}
    record_order: list[CaseRef] = []
    for item in items:
        if not isinstance(item, Mapping):
            return (), ()
        record_ref = CaseRef.from_mapping(item)
        if not all(record_ref):
            return (), ()
        if record_ref not in grouped:
            grouped[record_ref] = []
            record_order.append(record_ref)
        grouped[record_ref].append(dict(item))

    complete_refs: list[CaseRef] = []
    complete_items: list[dict[str, Any]] = []
    for record_ref in record_order:
        if record_ref in failed_refs:
            continue
        record_items = grouped[record_ref]
        delivered_rule_ids = [
            str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
            for item in record_items
        ]
        if (
            any(not rule_id for rule_id in delivered_rule_ids)
            or len(delivered_rule_ids) != len(set(delivered_rule_ids))
            or set(delivered_rule_ids) != expected
        ):
            continue
        complete_refs.append(record_ref)
        complete_items.extend(record_items)

    return tuple(complete_items), tuple(complete_refs)


__all__ = ["select_complete_record_items"]
