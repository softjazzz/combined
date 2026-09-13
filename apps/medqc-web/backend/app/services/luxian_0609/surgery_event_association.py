"""LX0609 已实施手术事件的受控计数与跨来源关联。"""

from __future__ import annotations

from datetime import date, datetime
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
    trusted_performed_surgery_times,
)

_RECORD_CONTENT_PLACEHOLDERS = frozenset({"无", "无。", "-", "不详", "未记录"})


def count_associated_performed_surgery_events(
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[int | None, str]:
    """返回可逐台计数的已实施手术数及无法计数时的受控原因。

    单来源仅依据自己的稳定主键去重。两来源同时存在时，优先按手术编码（或
    完整手术名称）与严格的实际手术时间做双射匹配；若唯一实质正式手术记录
    对应同日复合组件，则按自然日收拢为一台事件。绝不比较不同来源的物理主键。
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
    qualified_mr_surgery_rows = tuple(
        row
        for row in mr_surgery_rows
        if has_qualified_traditional_surgery_row(row)
    )
    mr_surgery_events = tuple(
        row
        for row in qualified_mr_surgery_rows
        if has_trusted_performed_surgery(source_key="mr_surgery", row=row)
    )

    surgery_records = _deduplicated_source_events(
        "surgery_record",
        _remove_duplicate_time_shells(surgery_record_events),
    )
    mr_surgeries = _deduplicated_source_events("mr_surgery", mr_surgery_events)
    if surgery_records is None or mr_surgeries is None:
        return None, "association_failed"
    if not surgery_records:
        return len(mr_surgeries), ""
    trusted_mr_ids = {
        _clean(row.get("surgery_id")) for row in mr_surgery_events
    }
    if any(
        not has_trusted_performed_surgery(source_key="mr_surgery", row=row)
        and not (
            (identity := _clean(row.get("surgery_id")))
            and identity in trusted_mr_ids
        )
        for row in qualified_mr_surgery_rows
    ):
        return None, "association_failed"
    if not mr_surgeries:
        return len(surgery_records), ""
    if len(surgery_records) == len(mr_surgeries):
        matched_mr_indexes: set[int] = set()
        for surgery_record_row in surgery_records:
            matching_indexes = [
                index
                for index, mr_surgery_row in enumerate(mr_surgeries)
                if _is_strict_cross_source_match(surgery_record_row, mr_surgery_row)
            ]
            if len(matching_indexes) != 1 or matching_indexes[0] in matched_mr_indexes:
                break
            matched_mr_indexes.add(matching_indexes[0])
        else:
            if len(matched_mr_indexes) == len(mr_surgeries):
                return len(surgery_records), ""

    if _is_single_composite_event(surgery_records, mr_surgeries):
        return 1, ""
    return None, "association_failed"


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _has_effective_content(
    value: Any, *, placeholders: frozenset[str] = frozenset()
) -> bool:
    if isinstance(value, str):
        cleaned = value.strip()
        return bool(cleaned) and cleaned not in placeholders
    return value is not None and bool(value)


def _is_substantive_surgery_record(row: Mapping[str, Any]) -> bool:
    return _has_effective_content(row.get("surgery_process")) or _has_effective_content(
        row.get("record_content"), placeholders=_RECORD_CONTENT_PLACEHOLDERS
    )


def _same_surgery_identity(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> bool:
    left_code = _normalized_surgery_code(left)
    right_code = _normalized_surgery_code(right)
    if left_code and right_code and left_code == right_code:
        return True
    left_name = _normalized_surgery_name(left)
    right_name = _normalized_surgery_name(right)
    return bool(left_name and right_name and left_name == right_name)


def _remove_duplicate_time_shells(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """仅移除有相同实质手术副本的无正文时间壳记录。"""

    substantive_rows = tuple(row for row in rows if _is_substantive_surgery_record(row))
    if not substantive_rows:
        return tuple(rows)
    return tuple(
        row
        for row in rows
        if _is_substantive_surgery_record(row)
        or not any(_same_surgery_identity(row, candidate) for candidate in substantive_rows)
    )


def _natural_day(source_key: str, row: Mapping[str, Any]) -> date | None:
    days = {
        value.date()
        for value in trusted_performed_surgery_times(source_key=source_key, row=row)
    }
    return next(iter(days)) if len(days) == 1 else None


def _is_single_composite_event(
    surgery_records: Sequence[Mapping[str, Any]],
    mr_surgeries: Sequence[Mapping[str, Any]],
) -> bool:
    """在唯一正式记录下按自然日安全收拢 mr_surgery 组件。"""

    if (
        len(surgery_records) != 1
        or not mr_surgeries
        or not _is_substantive_surgery_record(surgery_records[0])
    ):
        return False
    record = surgery_records[0]
    record_day = _natural_day("surgery_record", record)
    if record_day is None:
        return False
    for component in mr_surgeries:
        if _natural_day("mr_surgery", component) != record_day:
            return False
    return True


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
