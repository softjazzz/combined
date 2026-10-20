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
        if not has_qualified_traditional_surgery_row(row):
            continue
        # 未命中目录的等级回退只能沿用旧适用性，不能据此新增缺记录缺陷。
        # 首页“手术及操作”也可能给非手术操作填等级；有明确切口等级时可独立确认。
        incision = str(row.get("surgical_incision_level") or row.get("surgial_incision_level") or "").strip().upper()
        if catalog_surgery_state(row) is None and incision not in {
            "I", "II", "III", "IV", "Ⅰ", "Ⅱ", "Ⅲ", "Ⅳ",
        }:
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
