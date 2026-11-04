"""Caché首页到住院时间上下文的最小只读适配；不推断在院/死亡状态。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

_EXACT_TIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:Z|[+-]\d{2}:?\d{2})?$"
)
_LOCAL = ZoneInfo("Asia/Shanghai")


def _exact_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and _EXACT_TIME.fullmatch(value.strip()):
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.year < 1900:
        return None
    return (
        parsed.astimezone(_LOCAL).replace(tzinfo=None)
        if parsed.utcoffset() is not None else parsed
    )


def project_mr_visit_times(rows: Sequence[Mapping[str, Any]]) -> dict[str, datetime] | None:
    """同一三键只能有唯一首页；日期不补零点，NULL不推断仍在院。"""
    if len(rows) != 1:
        return None
    row = rows[0]
    admission = _exact_time(row.get("admission_datetime"))
    if admission is None:
        return None
    result = {"admission_datetime": admission}
    raw_discharge = row.get("discharge_datetime")
    if raw_discharge is not None and str(raw_discharge).strip():
        discharge = _exact_time(raw_discharge)
        if discharge is None or discharge < admission:
            return None
        result["discharge_datetime"] = discharge
    return result
