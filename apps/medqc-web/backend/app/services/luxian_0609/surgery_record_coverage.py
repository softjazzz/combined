"""手术族正式记录覆盖：仅以结构化事件日期证明缺失，不猜测关联。"""

from datetime import datetime, timedelta
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
    """同日多台（开始时刻不同）时，每台都须有能唯一关联到它的手术记录，否则未决。

    记录份数不等于台次。逐份记录确定可关联的台次：
    - 记录开始时刻与某台完全一致，只关联该台（同台初写、修订都只证明该台）；
    - 否则记录时段（开始至结束，无结束取开始时刻）须与该台时段（开始至已知结束，
      无结束取至下一台开始）相交；结束后才开始、或早于开始就已结束的记录不属于该台；
    - 与多台相交时以术式名称收窄，仍不唯一则不证明任何一台。
    缺开始时刻的记录不能证明任何台次。同台术式拆行开始时刻相同，按一台计。
    """
    from .surgery_event_association import procedure_matches_surgery

    surgeries_by_day: dict[object, dict[datetime, dict[str, object]]] = {}
    for row in master_rows:
        if not _coverage_candidate(row):
            continue
        begin = surgery_event_time(row)
        if begin is None:
            continue
        slot = surgeries_by_day.setdefault(begin.date(), {}).setdefault(
            begin, {"ends": set(), "names": set()}
        )
        end = surgery_event_time(row, end=True)
        if end is not None and end >= begin:
            slot["ends"].add(end)
        name = str(row.get("surgery_name") or "").strip()
        if name:
            slot["names"].add(name)
    records = tuple(
        (surgery_event_time(row), surgery_event_time(row, end=True),
         str(row.get("surgery_name") or "").strip())
        for row in record_rows
    )
    undated = any(begin is None for begin, _end, _name in records)
    for day, surgeries in surgeries_by_day.items():
        if len(surgeries) < 2:
            continue
        same_day = [item for item in records if item[0] is not None and item[0].date() == day]
        if not same_day and not undated:
            continue
        ordered = sorted(surgeries)
        spans: dict[datetime, tuple[datetime, datetime | None]] = {}
        for index, begin in enumerate(ordered):
            ends = surgeries[begin]["ends"]
            if len(ends) == 1:
                spans[begin] = (begin, next(iter(ends)))
            else:
                # 结束时间缺失或不一致时，以下一台开始为界（开区间）。
                later = ordered[index + 1] if index + 1 < len(ordered) else None
                spans[begin] = (begin, None if later is None else later - timedelta(microseconds=1))
        covered: set[datetime] = set()
        for record_begin, record_end, record_name in same_day:
            if record_begin in surgeries:
                covered.add(record_begin)
                continue
            record_stop = record_end if record_end is not None and record_end >= record_begin else record_begin
            candidates = [
                begin for begin, (span_begin, span_end) in spans.items()
                if record_stop >= span_begin and (span_end is None or record_begin <= span_end)
            ]
            if len(candidates) > 1 and record_name:
                named = [
                    begin for begin in candidates
                    if any(procedure_matches_surgery(record_name, name) for name in surgeries[begin]["names"])
                ]
                candidates = named or candidates
            if len(candidates) == 1:
                covered.add(candidates[0])
        if set(surgeries) - covered:
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
