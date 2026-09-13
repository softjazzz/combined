"""扩展文书规则共用的基础值与权威时间读取。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from ..source_evidence_reader import authoritative_document_time_value


_LX0609_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_datetime(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    normalized = text.replace("T", " ").replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_LX0609_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parsed


def _row_time(row: Mapping[str, Any]) -> datetime | None:
    value = authoritative_document_time_value(row)
    return _parse_datetime(
        value
        or row.get("death_datetime")
        or row.get("death_time")
        or row.get("discharge_datetime")
        or row.get("discharge_time")
    )
