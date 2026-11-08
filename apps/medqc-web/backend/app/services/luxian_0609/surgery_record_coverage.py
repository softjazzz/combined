"""手术族正式记录覆盖：仅以结构化事件日期证明缺失，不猜测关联。"""

from datetime import datetime
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from .source_evidence_reader import (
    has_qualified_traditional_surgery_row,
    parse_strict_performed_time,
)
from .surgery_procedure_catalog import catalog_surgery_state


def surgery_event_time(row: Mapping[str, object], *, end: bool = False) -> datetime | None:
    fields = ("surgery_end_datetime", "surgery_end_time") if end else (
        "surgery_begin_datetime", "surgery_begin_time",
    )
    for field in fields:
        value = row.get(field)
        if isinstance(value, str):
            parsed = parse_strict_performed_time(value)
            if parsed is None:
                try:
                    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
                except ValueError:
                    continue
            value = parsed
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.astimezone(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
            return value
    return None


def _coverage_candidate(row: Mapping[str, object]) -> bool:
    if not has_qualified_traditional_surgery_row(row):
        return False
    incision = str(row.get("surgical_incision_level") or row.get("surgial_incision_level") or "").strip().upper()
    return catalog_surgery_state(row) is not None or incision in {
        "I", "II", "III", "IV", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ",
    }


def same_day_surgery_coverage_unresolved(
    master_rows: Sequence[Mapping[str, object]],
    record_rows: Sequence[Mapping[str, object]],
) -> bool:
    """同日多台（开始时刻不同）而当日记录份数不足时，无法证明每台都有记录。

    同台术式拆行开始时刻相同，按一台计；缺时间的记录可能属于任一天，也不能证明逐台覆盖。
    """
    begins_by_day: dict[object, set[datetime]] = {}
    for row in master_rows:
        if not _coverage_candidate(row):
            continue
        begin = surgery_event_time(row)
        if begin is not None:
            begins_by_day.setdefault(begin.date(), set()).add(begin)
    record_times = tuple(surgery_event_time(row) for row in record_rows)
    undated = sum(1 for value in record_times if value is None)
    for day, begins in begins_by_day.items():
        if len(begins) < 2:
            continue
        dated = sum(1 for value in record_times if value is not None and value.date() == day)
        if dated + undated >= 1 and dated < len(begins):
            return True
    return False


def definitely_uncovered_surgery_rows(
    master_rows: Sequence[Mapping[str, object]],
    record_rows: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    """完整来源中无记录，或所有记录明确属于其他日期，才能证明缺失。

    同日多台、记录缺事件时间等仍交给原关联判定，不能将未关联直接当缺失。
    同台术式拆行可共用记录，不能用行数差推断缺失。
    """
    missing = []
    record_times = tuple(surgery_event_time(row) for row in record_rows)
    for row in master_rows:
        # 未命中目录的等级回退只能沿用旧适用性，不能据此新增缺记录缺陷。
        # 首页“手术及操作”也可能给非手术操作填等级；有明确切口等级时可独立确认。
        if not _coverage_candidate(row):
            continue
        begin = surgery_event_time(row)
        end = surgery_event_time(row, end=True)
        if begin is None and end is None:
            continue
        if not record_rows:
            missing.append(row)
        elif begin is not None and all(
            value is not None and value.date() != begin.date()
            for value in record_times
        ):
            missing.append(row)
    return tuple(missing)
