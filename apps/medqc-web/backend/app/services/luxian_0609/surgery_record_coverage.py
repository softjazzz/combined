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
    """同日多台（开始时刻不同）时，无法证明每台都有自己的记录则判为未决。

    记录份数不等于台次：同一台的初写、修订等多份记录结构化开始时刻相同，
    只证明该台。逐台核对：记录开始时刻与某台完全一致的只覆盖该台；未被精确
    覆盖的台次须有开始时刻落在本台开始至下一台开始（及本台已知结束）之间的
    其他记录，否则未决。
    缺开始时刻的记录不能证明任何未被精确覆盖的台次。
    同台术式拆行开始时刻相同，按一台计。
    """
    begins_by_day: dict[object, set[datetime]] = {}
    ends: dict[datetime, datetime] = {}
    for row in master_rows:
        if not _coverage_candidate(row):
            continue
        begin = surgery_event_time(row)
        if begin is not None:
            begins_by_day.setdefault(begin.date(), set()).add(begin)
            end = surgery_event_time(row, end=True)
            if end is not None and end >= begin:
                ends[begin] = max(end, ends.get(begin, end))
    record_times = tuple(surgery_event_time(row) for row in record_rows)
    undated = sum(1 for value in record_times if value is None)
    for day, begins in begins_by_day.items():
        if len(begins) < 2:
            continue
        same_day = [value for value in record_times if value is not None and value.date() == day]
        if not same_day and not undated:
            continue
        covered = {value for value in same_day if value in begins}
        uncovered = begins - covered
        if not uncovered:
            continue
        if undated:
            return True
        ordered = sorted(begins)
        for begin in uncovered:
            later = [value for value in ordered if value > begin]
            upper = later[0] if later else None
            end = ends.get(begin)
            # 开始时刻早于本台、不早于下一台或晚于本台已知结束的记录都不可能是本台记录。
            if not any(
                value not in begins
                and begin <= value
                and (upper is None or value < upper)
                and (end is None or value <= end)
                for value in same_day
            ):
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
