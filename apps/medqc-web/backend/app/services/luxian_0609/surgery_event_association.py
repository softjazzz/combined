"""LX0609 已实施手术事件的受控计数与跨来源关联。"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping, Sequence

from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .source_evidence_reader import (
    has_qualified_traditional_surgery_row,
    has_trusted_performed_surgery,
    parse_strict_performed_time,
)


def count_associated_performed_surgery_events(
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[int | None, str]:
    """返回可逐台计数的已实施手术数及无法计数时的受控原因。

    单来源仅依据自己的稳定主键去重。两来源同时存在时，按手术编码（或完整
    手术名称）与严格的实际手术时间做双射匹配；绝不比较不同来源的物理主键。
    """

    try:
        surgery_record_rows = tuple(materials.rows("surgery_record"))
    except EvidenceMaterialTruncated:
        return None, "source_truncated"
    except EvidenceMaterialUnavailable:
        return None, "source_unavailable"

    surgery_record_events = tuple(
        row
        for row in surgery_record_rows
        if has_trusted_performed_surgery(source_key="surgery_record", row=row)
    )
    try:
        mr_surgery_rows = tuple(materials.rows("mr_surgery"))
    except EvidenceMaterialTruncated:
        return None, "source_truncated"
    except EvidenceMaterialUnavailable:
        return None, "source_unavailable"
    mr_surgery_events = tuple(
        row
        for row in mr_surgery_rows
        if has_qualified_traditional_surgery_row(row)
        and has_trusted_performed_surgery(source_key="mr_surgery", row=row)
    )

    surgery_records = _deduplicated_source_events(
        "surgery_record", surgery_record_events
    )
    mr_surgeries = _deduplicated_source_events("mr_surgery", mr_surgery_events)
    if surgery_records is None or mr_surgeries is None:
        return None, "association_failed"
    if not surgery_records:
        return len(mr_surgeries), ""
    if not mr_surgeries:
        return len(surgery_records), ""
    if len(surgery_records) != len(mr_surgeries):
        return None, "association_failed"

    matched_mr_indexes: set[int] = set()
    for surgery_record_row in surgery_records:
        matching_indexes = [
            index
            for index, mr_surgery_row in enumerate(mr_surgeries)
            if _is_strict_cross_source_match(surgery_record_row, mr_surgery_row)
        ]
        if len(matching_indexes) != 1 or matching_indexes[0] in matched_mr_indexes:
            return None, "association_failed"
        matched_mr_indexes.add(matching_indexes[0])
    if len(matched_mr_indexes) != len(mr_surgeries):
        return None, "association_failed"
    return len(surgery_records), ""


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _deduplicated_source_events(
    source_key: str,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...] | None:
    if len(rows) <= 1:
        return tuple(rows)
    # 单来源重复同步可由该来源的物理主键去重；缺少主键时不能把重复行猜成
    # 多台手术，也不能反向认定为同一台。
    identity_field = {
        "surgery_record": "document_id",
        "mr_surgery": "surgery_id",
    }[source_key]
    deduplicated: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        identity = _clean(row.get(identity_field))
        if not identity:
            return None
        deduplicated.setdefault(identity, row)
    return tuple(deduplicated.values())


def _normalized_surgery_code(row: Mapping[str, Any]) -> str:
    return re.sub(r"\s+", "", _clean(row.get("surgery_code"))).casefold()


def _normalized_surgery_name(row: Mapping[str, Any]) -> str:
    return re.sub(r"\s+", "", _clean(row.get("surgery_name"))).casefold()


def _boundary_time(
    source_key: str,
    row: Mapping[str, Any],
    boundary: str,
) -> tuple[datetime | None, bool]:
    """返回单边界时间；同一行双字段冲突时拒绝跨源关联。"""

    fields_by_source = {
        "surgery_record": {
            "begin": ("surgery_begin_time", "surgery_begin_datetime"),
            "end": ("surgery_end_time", "surgery_end_datetime"),
        },
        "mr_surgery": {
            "begin": ("surgery_begin_datetime",),
            "end": ("surgery_end_datetime",),
        },
    }
    values: set[datetime] = set()
    for field in fields_by_source[source_key][boundary]:
        value = row.get(field)
        if source_key == "surgery_record":
            parsed = parse_strict_performed_time(value)
        elif isinstance(value, datetime) and value.tzinfo is None:
            parsed = value
        else:
            parsed = None
        if parsed is not None:
            values.add(parsed)
    if len(values) > 1:
        return None, True
    return (next(iter(values)), False) if values else (None, False)


def _is_strict_cross_source_match(
    surgery_record_row: Mapping[str, Any],
    mr_surgery_row: Mapping[str, Any],
) -> bool:
    """只按已投影的业务事实做跨源一对一匹配，禁止互比物理主键。"""

    record_code = _normalized_surgery_code(surgery_record_row)
    mr_code = _normalized_surgery_code(mr_surgery_row)
    record_name = _normalized_surgery_name(surgery_record_row)
    mr_name = _normalized_surgery_name(mr_surgery_row)

    if record_code and mr_code:
        if record_code != mr_code:
            return False
        # 编码相同仍不允许同时存在的完整名称互相矛盾。
        if record_name and mr_name and record_name != mr_name:
            return False
    elif not (record_name and mr_name and record_name == mr_name):
        return False

    has_matching_boundary = False
    for boundary in ("begin", "end"):
        record_time, record_conflict = _boundary_time(
            "surgery_record", surgery_record_row, boundary
        )
        mr_time, mr_conflict = _boundary_time("mr_surgery", mr_surgery_row, boundary)
        if record_conflict or mr_conflict:
            return False
        if record_time is not None and mr_time is not None:
            if record_time != mr_time:
                return False
            has_matching_boundary = True
    return has_matching_boundary
