"""扩展文书规则共用的基础值与权威时间读取。"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from ..source_evidence_reader import authoritative_document_time_value


_LX0609_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_BODY_SIGNATURE_PATTERN = re.compile(r"(?:医师|医生)签名[:：]\s*([一-鿿A-Za-z·]{2,8})")


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
    """病程记录医师签名：结构化签名优先，否则取正文末次“医师签名：X”。

    用户口径（2026-10-20）：源库病程结构化签名字段全部为空，签名只在正文末尾；
    正文签名须与提交人一致才认可，不一致或缺一项时视为签名缺失（不猜测是谁签的）。
    """

    structured = _clean(row.get("physician_sign"))
    if structured:
        return structured
    matches = _BODY_SIGNATURE_PATTERN.findall(_clean(row.get("record_content")))
    submitter = re.sub(r"\s+", "", _clean(row.get("submitter")))
    if matches and submitter and matches[-1] == submitter:
        return submitter
    return ""


def row_time_upper_bound(row: Mapping[str, Any]) -> datetime | None:
    """无权威记录时间时，以最后修改时间作为记录时间的上限（记录不晚于最后修改）。

    只用于证明文书“不可能落在某窗口内”，不能当作记录时间参与时效判断。
    """

    if _row_time(row) is not None:
        return None
    return _parse_datetime(row.get("last_modified_datetime"))
