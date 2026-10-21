"""扩展文书规则共用的基础值与权威时间读取。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from ..source_evidence_reader import authoritative_document_time_value
from app.services.document_assembly.signatures import course_physician_signatures


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


def course_record_signer(row: Mapping[str, Any]) -> str:
    """结构化签名优先，否则读取正文末尾唯一、明确的医师签名。

    提交人可能是代录人员，不是签名成立的前置条件。只接受独立签名栏的
    单一姓名，不能从正文提及、上级签名或多人未分角色的签名中猜测记录医师。
    """

    names = course_physician_signatures(row)
    return names[0] if len(names) == 1 else ""


def row_time_upper_bound(row: Mapping[str, Any]) -> datetime | None:
    """无权威记录时间时，以最后修改时间作为记录时间的上限（记录不晚于最后修改）。

    只用于证明文书“不可能落在某窗口内”，不能当作记录时间参与时效判断。
    """

    if _row_time(row) is not None:
        return None
    return _parse_datetime(row.get("last_modified_datetime"))
