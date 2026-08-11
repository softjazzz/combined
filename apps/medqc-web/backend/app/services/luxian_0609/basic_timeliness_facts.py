"""LX0609 基础时限规则的受控事实与最小事件关联。

本模块只把请求内材料标准化为时间、文书和医生职级事实，不产生质控状态，
也不读取数据库。最终状态仍由 ``native_basic_timeliness`` 决定。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
import re
from typing import Any, Mapping, Sequence

from .source_evidence_reader import (
    authoritative_document_time_value,
    parse_luxian_0609_rescue_end_time,
)


_AUTHORITATIVE_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?$"
)
_INLINE_RESCUE_END_TIME_PATTERN = re.compile(
    r"(?<![\w\u4e00-\u9fff])抢救结束时间\s*[:：]\s*(?P<value>"
    r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?"
    r"|\d{4}年\d{1,2}月\d{1,2}日\s+\d{1,2}:\d{2}(?::\d{2})?"
    r")"
)
_ATTENDING_MARKERS = ("主治医师", "主治查房", "代主治医师", "代主治查房")
_SENIOR_MARKERS = ("副主任医师", "主任医师", "副主任查房", "主任查房", "高级职称")
_ATTENDING_OR_ABOVE_DOCUMENT_TITLES = frozenset(
    {
        "上级医师查房记录",
        "上级医师首次查房记录",
        "上级医生查房记录",
        "上级医生首次查房记录",
    }
)


class AdmissionAnchorState(str, Enum):
    EXACT = "exact"
    DATE_ONLY = "date_only"
    MISSING = "missing"
    CONFLICT = "conflict"


class CourseRoundRole(str, Enum):
    NONE = "none"
    AMBIGUOUS = "ambiguous"
    ATTENDING_OR_ABOVE = "attending_or_above"
    SENIOR = "senior"


@dataclass(frozen=True)
class AdmissionAnchorFact:
    state: AdmissionAnchorState
    anchor_time: datetime | None = None
    anchor_date: date | None = None
    source_key: str = ""
    candidate_count: int = 0


@dataclass(frozen=True)
class DocumentEvent:
    observed_time: datetime | None
    document_id: str | None
    row: Mapping[str, Any]


@dataclass(frozen=True)
class RescueEvent:
    rescue_end_time: datetime | None
    document: DocumentEvent


@dataclass(frozen=True)
class TimelinessAssociation:
    state: str
    elapsed_hours: float
    overdue_hours: float
    anchor_time: datetime
    observed_event: DocumentEvent


def parse_authoritative_datetime(value: Any) -> datetime | None:
    """只接受权威字段整值，不从标题或普通正文猜测时间。"""

    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not _AUTHORITATIVE_DATETIME_PATTERN.fullmatch(normalized):
        return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is None else None


def parse_authoritative_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == normalized else None


def extract_document_events(rows: Sequence[Mapping[str, Any]]) -> tuple[DocumentEvent, ...]:
    return tuple(
        DocumentEvent(
            observed_time=parse_authoritative_datetime(
                authoritative_document_time_value(row)
            ),
            document_id=str(row.get("document_id") or "").strip() or None,
            row=row,
        )
        for row in rows
    )


def _unique_times(rows: Sequence[Mapping[str, Any]], *fields: str) -> tuple[datetime, ...]:
    return tuple(
        sorted(
            {
                parsed
                for row in rows
                for field in fields
                if (parsed := parse_authoritative_datetime(row.get(field))) is not None
            }
        )
    )


def extract_admission_anchor(
    *,
    registration_rows: Sequence[Mapping[str, Any]],
    admission_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]],
    allow_date_fallback: bool,
) -> AdmissionAnchorFact:
    """按既有优先级抽取入院锚点，同一权威层出现多值时显式冲突。"""

    tiers = (
        (
            "inpat_registration",
            _unique_times(registration_rows, "admission_datetime", "admission_time"),
        ),
        ("admission_record", _unique_times(admission_rows, "admission_datetime")),
    )
    for source_key, candidates in tiers:
        if len(candidates) > 1:
            return AdmissionAnchorFact(
                state=AdmissionAnchorState.CONFLICT,
                source_key=source_key,
                candidate_count=len(candidates),
            )
        if candidates:
            return AdmissionAnchorFact(
                state=AdmissionAnchorState.EXACT,
                anchor_time=candidates[0],
                source_key=source_key,
                candidate_count=1,
            )

    if allow_date_fallback:
        dates = tuple(
            sorted(
                {
                    parsed
                    for row in discharge_rows
                    if (parsed := parse_authoritative_date(row.get("admission_date")))
                    is not None
                }
            )
        )
        if len(dates) > 1:
            return AdmissionAnchorFact(
                state=AdmissionAnchorState.CONFLICT,
                source_key="discharge_record",
                candidate_count=len(dates),
            )
        if dates:
            return AdmissionAnchorFact(
                state=AdmissionAnchorState.DATE_ONLY,
                anchor_date=dates[0],
                source_key="discharge_record",
                candidate_count=1,
            )
    return AdmissionAnchorFact(state=AdmissionAnchorState.MISSING)


def parse_rescue_end_time(value: Any) -> datetime | None:
    parsed = parse_luxian_0609_rescue_end_time(value)
    if parsed is not None or not isinstance(value, str):
        return parsed
    match = _INLINE_RESCUE_END_TIME_PATTERN.search(value)
    if match is None:
        return None
    normalized = match.group("value").strip()
    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y年%m月%d日 %H:%M:%S",
        "%Y年%m月%d日 %H:%M",
    ):
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    return None


def extract_rescue_events(rows: Sequence[Mapping[str, Any]]) -> tuple[RescueEvent, ...]:
    documents = extract_document_events(rows)
    return tuple(
        RescueEvent(
            rescue_end_time=parse_rescue_end_time(
                document.row.get("record_content")
                or document.row.get("content")
            ),
            document=document,
        )
        for document in documents
    )


def classify_course_round_role(row: Mapping[str, Any]) -> CourseRoundRole:
    document_titles = tuple(
        re.sub(r"\s+", "", str(row.get(field) or "").strip())
        for field in ("document_title", "title")
    )
    author_title = str(row.get("author_title") or "").strip()
    role_text = " ".join((*document_titles, author_title))
    if any(marker in role_text for marker in _SENIOR_MARKERS):
        return CourseRoundRole.SENIOR
    if any(marker in role_text for marker in _ATTENDING_MARKERS):
        return CourseRoundRole.ATTENDING_OR_ABOVE
    if is_generic_upper_physician_round(row):
        return CourseRoundRole.ATTENDING_OR_ABOVE
    if "查房" in role_text:
        return CourseRoundRole.AMBIGUOUS
    return CourseRoundRole.NONE


def is_generic_upper_physician_round(row: Mapping[str, Any]) -> bool:
    """识别仅声明“上级医师”、但未声明具体职称的标准查房文书类型。"""

    return any(
        re.sub(r"\s+", "", str(row.get(field) or "").strip())
        in _ATTENDING_OR_ABOVE_DOCUMENT_TITLES
        for field in ("document_title", "title")
    )


def associate_timeliness_event(
    *,
    anchor_time: datetime,
    observed_event: DocumentEvent,
    threshold_hours: int,
) -> TimelinessAssociation | None:
    observed_time = observed_event.observed_time
    if observed_time is None:
        return None
    elapsed_hours = (observed_time - anchor_time).total_seconds() / 3600
    state = (
        "before"
        if elapsed_hours < 0
        else "within" if elapsed_hours <= threshold_hours else "late"
    )
    return TimelinessAssociation(
        state=state,
        elapsed_hours=elapsed_hours,
        overdue_hours=max(elapsed_hours - threshold_hours, 0),
        anchor_time=anchor_time,
        observed_event=observed_event,
    )


__all__ = [
    "AdmissionAnchorFact",
    "AdmissionAnchorState",
    "CourseRoundRole",
    "DocumentEvent",
    "RescueEvent",
    "TimelinessAssociation",
    "associate_timeliness_event",
    "classify_course_round_role",
    "is_generic_upper_physician_round",
    "extract_admission_anchor",
    "extract_document_events",
    "extract_rescue_events",
    "parse_authoritative_date",
    "parse_authoritative_datetime",
    "parse_rescue_end_time",
]
