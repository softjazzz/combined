"""LX0609-069 会诊申请与完成记录的一对一时限判定。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from .shared import _clean, _parse_datetime, _row_time


_REQUEST_TITLE_PATTERN = re.compile(r"会诊.*申请|申请.*会诊")
_RECORD_TITLE_PATTERN = re.compile(r"会诊.*(?:记录|意见)|(?:记录|意见).*会诊")
_REQUEST_TIME_FIELDS = (
    "consult_apply_time",
    "request_time",
    "request_datetime",
    "application_time",
    "application_datetime",
)
_COMPLETION_TIME_FIELDS = (
    "consultation_time",
    "consultation_datetime",
    "completion_time",
    "completion_datetime",
)


@dataclass(frozen=True)
class ConsultationTimelinessOutcome:
    final_state: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None
    consumed_document_rows: tuple[Mapping[str, Any], ...] = ()


def _business_id(row: Mapping[str, Any]) -> str:
    values = tuple(
        value
        for field in ("consultation_id", "application_id")
        if (value := _clean(row.get(field)))
    )
    unique_values = tuple(dict.fromkeys(values))
    return unique_values[0] if len(unique_values) == 1 else ""


def _has_conflicting_business_ids(row: Mapping[str, Any]) -> bool:
    values = tuple(
        value
        for field in ("consultation_id", "application_id")
        if (value := _clean(row.get(field)))
    )
    return len(set(values)) > 1


def _request_time(row: Mapping[str, Any]) -> datetime | None:
    value = next(
        (
            row.get(field)
            for field in _REQUEST_TIME_FIELDS
            if _clean(row.get(field))
        ),
        None,
    )
    return _parse_datetime(value) if value is not None else _row_time(row)


def _completion_time(
    row: Mapping[str, Any],
    *,
    allow_record_time: bool = False,
) -> datetime | None:
    value = next(
        (
            row.get(field)
            for field in _COMPLETION_TIME_FIELDS
            if _clean(row.get(field))
        ),
        None,
    )
    if value is not None:
        return _parse_datetime(value)
    return _row_time(row) if allow_record_time else None


def _has_value(row: Mapping[str, Any], fields: Sequence[str]) -> bool:
    return any(_clean(row.get(field)) for field in fields)


def _pair_separate_rows(
    request_rows: Sequence[Mapping[str, Any]],
    record_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], Mapping[str, Any]], ...] | None:
    if not request_rows or not record_rows or len(request_rows) != len(record_rows):
        return None
    if any(
        _has_conflicting_business_ids(row)
        for row in (*request_rows, *record_rows)
    ):
        return None

    if len(request_rows) == len(record_rows) == 1:
        request_id = _business_id(request_rows[0])
        record_id = _business_id(record_rows[0])
        if request_id or record_id:
            if not request_id or not record_id or request_id != record_id:
                return None
        else:
            # 无业务 ID 时只能接受同一时限窗口内的唯一角色配对；
            # 跨越 24 小时无法证明属于同一次会诊，不能把历史记录
            # 静默配成本次会诊并据此判定超时。
            request_time = _request_time(request_rows[0])
            completion_time = _completion_time(record_rows[0], allow_record_time=True)
            if (
                request_time is None
                or completion_time is None
                or completion_time < request_time
                or (completion_time - request_time).total_seconds() > 24 * 60 * 60
            ):
                return None
        return ((request_rows[0], record_rows[0]),)

    requests_by_id: dict[str, Mapping[str, Any]] = {}
    for row in request_rows:
        business_id = _business_id(row)
        if not business_id or business_id in requests_by_id:
            return None
        requests_by_id[business_id] = row

    records_by_id: dict[str, Mapping[str, Any]] = {}
    for row in record_rows:
        business_id = _business_id(row)
        if not business_id or business_id in records_by_id:
            return None
        records_by_id[business_id] = row
    if set(requests_by_id) != set(records_by_id):
        return None
    return tuple(
        (requests_by_id[business_id], records_by_id[business_id])
        for business_id in requests_by_id
    )


def evaluate_consultation_timeliness(
    *,
    consultation_rows: Sequence[Mapping[str, Any]],
    consultation_error: str,
) -> ConsultationTimelinessOutcome:
    if consultation_error:
        return ConsultationTimelinessOutcome("data_gap", consultation_error)
    if not consultation_rows:
        return ConsultationTimelinessOutcome(
            "not_applicable", "trigger_absent_complete"
        )

    has_explicit_request_time = any(
        _has_value(row, _REQUEST_TIME_FIELDS) for row in consultation_rows
    )
    has_request_document = any(
        _REQUEST_TITLE_PATTERN.search(_clean(row.get("document_title")))
        for row in consultation_rows
    )
    if not has_explicit_request_time and not has_request_document:
        if any(field in row for row in consultation_rows for field in _REQUEST_TIME_FIELDS):
            return ConsultationTimelinessOutcome(
                "data_gap", "authoritative_time_missing",
                consumed_document_rows=tuple(
                    row for row in consultation_rows
                    if any(field in row for field in _REQUEST_TIME_FIELDS)
                    and _clean(row.get("document_id") or row.get("id"))
                ),
            )
        # 当前机构接口可能只返回会诊记录及 record_time，却从未提供
        # consult_apply_time。此时缺失的是规则所需的申请时间数据源，
        # 不是两份已知资料之间的配对失败。
        return ConsultationTimelinessOutcome("data_gap", "source_unavailable")

    direct_events: list[tuple[datetime | None, datetime | None]] = []
    consumed_rows: list[Mapping[str, Any]] = []
    remaining_rows: list[Mapping[str, Any]] = []
    for row in consultation_rows:
        if _has_conflicting_business_ids(row):
            return ConsultationTimelinessOutcome("data_gap", "association_failed")
        title = _clean(row.get("document_title"))
        request_titled = bool(_REQUEST_TITLE_PATTERN.search(title))
        record_titled = bool(
            not request_titled and _RECORD_TITLE_PATTERN.search(title)
        )
        has_request_time = _has_value(row, _REQUEST_TIME_FIELDS)
        has_completion_time = _has_value(row, _COMPLETION_TIME_FIELDS)
        if has_request_time and (
            has_completion_time or not (request_titled or record_titled)
        ):
            direct_events.append((_request_time(row), _completion_time(row)))
            consumed_rows.append(row)
        else:
            remaining_rows.append(row)

    request_rows = tuple(
        row
        for row in remaining_rows
        if _REQUEST_TITLE_PATTERN.search(_clean(row.get("document_title")))
    )
    record_rows = tuple(
        row
        for row in remaining_rows
        if not _REQUEST_TITLE_PATTERN.search(_clean(row.get("document_title")))
        and _RECORD_TITLE_PATTERN.search(_clean(row.get("document_title")))
    )
    # Some source rows are historical consultation fragments without a title,
    # request/completion time, or any role marker.  They cannot form an event
    # and must not poison a valid request-record pair from the same visit.
    recognized_row_ids = {id(row) for row in (*request_rows, *record_rows)}
    unclassified_rows = tuple(
        row for row in remaining_rows if id(row) not in recognized_row_ids
    )
    recognized_rows = len(request_rows) + len(record_rows)
    if unclassified_rows and not recognized_rows and not direct_events:
        return ConsultationTimelinessOutcome("data_gap", "association_failed")
    if recognized_rows:
        pairs = _pair_separate_rows(request_rows, record_rows)
        if pairs is None:
            return ConsultationTimelinessOutcome("data_gap", "association_failed")
        consumed_rows.extend(row for pair in pairs for row in pair)
        paired_events = tuple(
            (
                _request_time(request_row),
                _completion_time(record_row, allow_record_time=True),
            )
            for request_row, record_row in pairs
        )
        events = (*direct_events, *paired_events)
    else:
        events = tuple(direct_events)
    if any(request_time is None or completion_time is None for request_time, completion_time in events):
        return ConsultationTimelinessOutcome(
            "data_gap", "authoritative_time_missing",
            consumed_document_rows=tuple(
                row for row in consumed_rows
                if _clean(row.get("document_id") or row.get("id"))
            ),
        )

    typed_events = tuple(
        (request_time, completion_time)
        for request_time, completion_time in events
        if request_time is not None and completion_time is not None
    )
    intervals = tuple(
        (completion_time - request_time).total_seconds() / 3600
        for request_time, completion_time in typed_events
    )
    interval_seconds = tuple(
        (completion_time - request_time).total_seconds()
        for request_time, completion_time in typed_events
    )
    facts = {
        "verification_kind": "consultation_timeliness_check",
        "threshold_hours": 24,
        "actual_interval_hours": [round(value, 2) for value in intervals],
        "request_times": [
            request_time.isoformat(sep=" ") for request_time, _ in typed_events
        ],
        "record_times": [
            completion_time.isoformat(sep=" ") for _, completion_time in typed_events
        ],
        "event_results": [
            {
                "sequence": sequence,
                "request_time": request_time.isoformat(sep=" "),
                "completion_time": completion_time.isoformat(sep=" "),
                "interval_seconds": int(seconds) if seconds.is_integer() else seconds,
                "outcome": (
                    "within_threshold"
                    if 0 <= seconds <= 24 * 60 * 60
                    else "time_conflict"
                    if seconds < 0
                    else "threshold_exceeded"
                ),
            }
            for sequence, ((request_time, completion_time), seconds) in enumerate(
                zip(typed_events, interval_seconds), start=1
            )
        ],
    }
    if any(seconds < 0 for seconds in interval_seconds):
        return ConsultationTimelinessOutcome(
            "data_gap", "authoritative_time_conflict", facts
        )
    compliant = all(interval <= 24 for interval in intervals)
    return ConsultationTimelinessOutcome(
        "compliant" if compliant else "non_compliant",
        "requirement_within_threshold" if compliant else "threshold_exceeded",
        facts,
    )
