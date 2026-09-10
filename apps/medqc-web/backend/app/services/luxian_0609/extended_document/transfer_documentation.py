"""LX0609-072/073 转科文书按单次转科事件关联的确定性判定。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence

from ..source_evidence_reader import authoritative_document_time_value
from .shared import _clean, _parse_datetime


@dataclass(frozen=True)
class TransferDocumentationOutcome:
    final_state: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class _TransferRecordCandidate:
    state: str
    record_time: datetime | None = None


_TRANSFER_IN_DESTINATION_PATTERN = re.compile(
    r"转入(?:ICU|[\u4e00-\u9fffA-Za-z0-9]+科)",
    re.IGNORECASE,
)
_NON_CLINICAL_TRANSFER_MARKERS = ("药品", "病案")
_PLANNED_TRANSFER_MARKERS = ("拟转",)


def select_transfer_order_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """选择已正式下达且指向临床科室的转科医嘱。"""

    selected = []
    for row in rows:
        text = _clean(row.get("order_name") or row.get("record_content"))
        normalized_name = re.sub(r"\s+", "", text).strip("：:，,。；;")
        is_transfer = "转科" in text or (
            _TRANSFER_IN_DESTINATION_PATTERN.fullmatch(normalized_name) is not None
        )
        if not is_transfer:
            continue
        if any(marker in text for marker in _PLANNED_TRANSFER_MARKERS):
            continue
        if any(marker in text for marker in _NON_CLINICAL_TRANSFER_MARKERS):
            continue
        status = _clean(row.get("order_status"))
        if any(marker in status for marker in ("取消", "作废", "撤销", "未执行")):
            continue
        selected.append(row)
    return tuple(selected)


def _precise_datetime(value: Any) -> datetime | None:
    """只接受带时分秒的值；日期不能被伪造成午夜的转科时间。"""

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or ("T" not in text and " " not in text):
        return None
    return _parse_datetime(text)


def _date_value(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _candidate_for_order(
    row: Mapping[str, Any], *, order_time: datetime
) -> _TransferRecordCandidate:
    # transfer_date 描述转科事件发生日期，优先用于排除既往住院转科。
    # 即使文书后来补录、record_time 较新，也不能让历史事件满足本次医嘱。
    transfer_date_value = row.get("transfer_date")
    transfer_date = _date_value(transfer_date_value)
    if transfer_date is not None and transfer_date < order_time.date():
        return _TransferRecordCandidate("historical")

    document_value = authoritative_document_time_value(row)
    document_time = _precise_datetime(document_value)
    if document_time is not None:
        return _TransferRecordCandidate(
            "historical" if document_time < order_time else "current",
            document_time,
        )

    # transfer_date 是兼容字段。仅日期不能证明同日先后及24小时边界；
    # 但明确早于医嘱日期的记录可排除为历史记录。
    transfer_date_time = _precise_datetime(transfer_date_value)
    if transfer_date_time is not None:
        return _TransferRecordCandidate(
            "historical" if transfer_date_time < order_time else "current",
            transfer_date_time,
        )
    return _TransferRecordCandidate("time_unknown")


def _record_state(
    *,
    records: Sequence[Mapping[str, Any]],
    order_time: datetime,
) -> tuple[str, datetime | None]:
    """返回单类文书与唯一转科医嘱的关联状态及唯一时间。"""

    if not records:
        return "missing", None
    candidates = tuple(_candidate_for_order(row, order_time=order_time) for row in records)
    current = tuple(item for item in candidates if item.state == "current")
    has_unknown = any(item.state == "time_unknown" for item in candidates)
    if len(current) > 1:
        return "multiple", None
    if current and has_unknown:
        return "time_unknown", None
    if current:
        return "matched", current[0].record_time
    if has_unknown:
        return "time_unknown", None
    return "historical", None


def _unique_order_time(row: Mapping[str, Any]) -> tuple[datetime | None, bool]:
    """同一医嘱的多个正式时间必须一致，不能按字段顺序静默择一。"""

    values = tuple(
        value
        for field in ("start_time", "order_time", "prescribed_datetime")
        if (value := _precise_datetime(row.get(field))) is not None
    )
    unique_values = tuple(dict.fromkeys(values))
    if len(unique_values) > 1:
        return None, True
    return (unique_values[0] if unique_values else None), False


def _display_facts(
    *,
    rule_id: str,
    order_time: datetime | None,
    transfer_in_state: str,
    transfer_in_time: datetime | None,
    transfer_out_state: str,
    transfer_out_time: datetime | None,
) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "verification_kind": (
            "transfer_record_timeliness_check"
            if rule_id == "LX0609-072"
            else "transfer_record_presence_check"
        ),
        "transfer_order_time": order_time.isoformat(sep=" ") if order_time else None,
        "transfer_in_time": (
            transfer_in_time.isoformat(sep=" ") if transfer_in_time else None
        ),
        "transfer_out_time": (
            transfer_out_time.isoformat(sep=" ") if transfer_out_time else None
        ),
    }
    if rule_id == "LX0609-072" and order_time is not None:
        facts["threshold_hours"] = 24
        facts["transfer_in_interval_hours"] = (
            round((transfer_in_time - order_time).total_seconds() / 3600, 2)
            if transfer_in_time is not None
            else None
        )
        facts["transfer_out_interval_hours"] = (
            round((transfer_out_time - order_time).total_seconds() / 3600, 2)
            if transfer_out_time is not None
            else None
        )
    if rule_id == "LX0609-073":
        facts["transfer_in_associated"] = (
            True if transfer_in_state == "matched" else False if transfer_in_state in {"missing", "historical"} else None
        )
        facts["transfer_out_associated"] = (
            True if transfer_out_state == "matched" else False if transfer_out_state in {"missing", "historical"} else None
        )
    return facts


def _transfer_window_state(
    *,
    order_time: datetime,
    evaluation_horizon_date: date | None,
    evaluation_horizon_datetime: datetime | None,
    evaluation_horizon_error: str | None,
) -> tuple[bool | None, str | None]:
    """判断转科后 24 小时观察窗是否成熟，不用快照创建时间替代评价终点。"""

    if evaluation_horizon_error:
        return None, evaluation_horizon_error
    if evaluation_horizon_datetime is not None:
        if evaluation_horizon_datetime < order_time:
            return None, "authoritative_time_conflict"
        return evaluation_horizon_datetime >= order_time + timedelta(hours=24), None
    if evaluation_horizon_date is None:
        return None, "authoritative_time_missing"
    if evaluation_horizon_date < order_time.date():
        return None, "authoritative_time_conflict"
    # 仅日期不能证明已越过当日的 24 小时时点，按保守口径继续等待。
    return evaluation_horizon_date > (order_time + timedelta(hours=24)).date(), None


def evaluate_transfer_documentation(
    *,
    rule_id: str,
    nondrug_order_error: str,
    transfer_in_error: str,
    transfer_out_error: str,
    nondrug_order_rows: Sequence[Mapping[str, Any]],
    transfer_in_rows: Sequence[Mapping[str, Any]],
    transfer_out_rows: Sequence[Mapping[str, Any]],
    evaluation_horizon_date: date | None = None,
    evaluation_horizon_datetime: datetime | None = None,
    evaluation_horizon_error: str | None = None,
) -> TransferDocumentationOutcome:
    """按唯一转科医嘱关联转入/转出记录，不以旧住院记录满足本次事件。"""

    source_error = nondrug_order_error or transfer_in_error or transfer_out_error
    if source_error:
        return TransferDocumentationOutcome("data_gap", source_error)
    orders = select_transfer_order_rows(nondrug_order_rows)
    if not orders:
        return TransferDocumentationOutcome("not_applicable", "trigger_absent_complete")
    if len(orders) != 1:
        return TransferDocumentationOutcome(
            "data_gap",
            "association_failed",
            {
                "failure_kind": "transfer_event_association_gap",
                "transfer_order_count": len(orders),
                "transfer_in_count": len(transfer_in_rows),
                "transfer_out_count": len(transfer_out_rows),
            },
        )

    order_time, order_time_conflict = _unique_order_time(orders[0])
    if order_time_conflict:
        return TransferDocumentationOutcome("data_gap", "authoritative_time_conflict")
    if order_time is None:
        return TransferDocumentationOutcome("data_gap", "authoritative_time_missing")

    transfer_in_state, transfer_in_time = _record_state(
        records=transfer_in_rows, order_time=order_time
    )
    transfer_out_state, transfer_out_time = _record_state(
        records=transfer_out_rows, order_time=order_time
    )
    facts = _display_facts(
        rule_id=rule_id,
        order_time=order_time,
        transfer_in_state=transfer_in_state,
        transfer_in_time=transfer_in_time,
        transfer_out_state=transfer_out_state,
        transfer_out_time=transfer_out_time,
    )

    states = (transfer_in_state, transfer_out_state)
    if "multiple" in states:
        return TransferDocumentationOutcome("data_gap", "association_failed", facts)
    if "missing" in states or "historical" in states:
        if rule_id == "LX0609-072":
            window_mature, window_error = _transfer_window_state(
                order_time=order_time,
                evaluation_horizon_date=evaluation_horizon_date,
                evaluation_horizon_datetime=evaluation_horizon_datetime,
                evaluation_horizon_error=evaluation_horizon_error,
            )
            if window_error:
                return TransferDocumentationOutcome("data_gap", window_error, facts)
            if not window_mature:
                return TransferDocumentationOutcome(
                    "not_applicable", "evaluation_window_not_mature", facts
                )
        return TransferDocumentationOutcome(
            "non_compliant", "required_document_missing", facts
        )
    if "time_unknown" in states:
        return TransferDocumentationOutcome(
            "data_gap", "authoritative_time_missing", facts
        )
    if rule_id == "LX0609-073":
        return TransferDocumentationOutcome("compliant", "requirement_satisfied", facts)

    intervals = (
        (transfer_in_time - order_time).total_seconds() / 3600,
        (transfer_out_time - order_time).total_seconds() / 3600,
    )
    compliant = all(0 <= interval <= 24 for interval in intervals)
    return TransferDocumentationOutcome(
        "compliant" if compliant else "non_compliant",
        "requirement_within_threshold" if compliant else "threshold_exceeded",
        facts,
    )
