"""客户09299：冻结住院范围内阶段小结及交接/转科替代的30天循环。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from typing import Any, Mapping, Sequence

from ..basic_timeliness_facts import (
    AdmissionAnchorState,
    extract_admission_anchor,
    parse_authoritative_datetime,
)
from ..source_evidence_reader import authoritative_document_time_value

RULE_ID = "LX0609-10-04-01"
_PERIOD = timedelta(days=30)
_TITLES = {
    "summary_record": frozenset({"阶段小结"}),
    "handoff_record": frozenset({"交班记录", "交接班记录"}),
    "handover_record": frozenset({"接班记录", "交接班记录"}),
    "transfer_in_record": frozenset({"转入记录", "转科记录"}),
    "transfer_out_record": frozenset({"转出记录", "转科记录"}),
}


@dataclass(frozen=True)
class StageSummaryOutcome:
    final_state: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None
    document_refs: tuple[Mapping[str, str], ...] = ()
    consumed_rows: tuple[tuple[str, Mapping[str, Any]], ...] = ()


def _gap(reason: str) -> StageSummaryOutcome:
    return StageSummaryOutcome("data_gap", reason)


def _periods(start: datetime, end: datetime, events: Sequence[datetime]) -> tuple[str, tuple[datetime, ...]]:
    """迟到文书只重启下一周期，不能删除已经超期的周期。"""
    if end - start <= _PERIOD:
        return "not_applicable", ()
    anchor = start
    missed: list[datetime] = []
    for event in (*events, end):
        while event - anchor > _PERIOD:
            anchor += _PERIOD
            missed.append(anchor)
            if len(missed) > 100:
                return "data_gap", ()
        anchor = event
    return ("non_compliant" if missed else "compliant"), tuple(missed)


def evaluate_stage_summary_timeliness(
    *, registration_rows: Sequence[Mapping[str, Any]], admission_rows: Sequence[Mapping[str, Any]],
    document_rows: Mapping[str, Sequence[Mapping[str, Any]]], horizon_rows: Sequence[Mapping[str, Any]],
    source_error: str = "",
) -> StageSummaryOutcome:
    """纯判定，不查库、不调用模型、不补当前时间；来源完整性由同一快照证明。"""
    if source_error:
        return _gap(source_error)
    anchor = extract_admission_anchor(registration_rows=registration_rows,
        admission_rows=admission_rows, discharge_rows=(), allow_date_fallback=False)
    if anchor.state is AdmissionAnchorState.CONFLICT:
        return _gap("authoritative_time_conflict")
    if anchor.state is not AdmissionAnchorState.EXACT:
        return _gap("authoritative_time_missing")
    start = anchor.anchor_time
    if len(horizon_rows) != 1:
        return _gap("authoritative_time_missing" if not horizon_rows else "authoritative_time_conflict")
    horizon = horizon_rows[0]
    if horizon.get("basis") not in {"discharge_date", "evaluation_as_of"}:
        return _gap("authoritative_time_missing")
    raw_time = horizon.get("horizon_datetime")
    exact_end = parse_authoritative_datetime(raw_time)
    if raw_time is not None and str(raw_time).strip() and exact_end is None:
        return _gap("authoritative_time_missing")
    raw_date = horizon.get("horizon_date")
    try:
        end_date = date.fromisoformat(str(raw_date)) if raw_date else None
    except ValueError:
        return _gap("authoritative_time_missing")
    if exact_end is not None:
        if end_date is not None and exact_end.date() != end_date:
            return _gap("authoritative_time_conflict")
        end_date = exact_end.date()
        lower = upper = exact_end
    elif end_date is not None:
        # 冻结运行日期不具有具体时刻，仅当整日区间内结论一致才交付。
        lower = datetime.combine(end_date, datetime.min.time())
        upper = lower + timedelta(days=1) - timedelta(microseconds=1)
    else:
        return _gap("authoritative_time_missing")
    if upper < start:
        return _gap("authoritative_time_conflict")
    if lower < start:
        lower = start

    events: list[tuple[datetime, str, str]] = []
    consumed: dict[tuple[datetime, str, str], Mapping[str, Any]] = {}
    for source, titles in _TITLES.items():
        # 已知未来材料不参与正文、版本冲突或替代判断；未知时刻仍须校验。
        visible = tuple(
            (row, clock) for row in document_rows.get(source, ())
            if row.get("validation_material_state") not in {"held", "version_review"}
            if (clock := parse_authoritative_datetime(authoritative_document_time_value(row))) is None
            or clock <= upper
        )
        rows = tuple(row for row, _ in visible)
        for row, clock in visible:
            title = re.sub(r"\s+", "", str(row.get("document_title") or ""))
            body = str(row.get("record_content") or "").strip()
            if not title and body:
                return _gap("required_field_missing")
            if title not in titles:
                continue
            if not body:
                return _gap("required_field_missing")
            if clock is None:
                return _gap("authoritative_time_missing")
            if clock < start:
                return _gap("authoritative_time_conflict")
            document_id = str(row.get("document_id") or "").strip()
            if not document_id:
                return _gap("required_field_missing")
            if any(str(other.get("document_id") or "").strip() == document_id and dict(other) != dict(row)
                   for other in rows):
                return _gap("authoritative_time_conflict")
            events.append((clock, source, document_id))
            consumed[(clock, source, document_id)] = row
    events = sorted(set(events))
    if len(events) > 100:
        return _gap("candidate_scope_incomplete")
    low_status, low_missed = _periods(start, lower, [clock for clock, _, _ in events if clock <= lower])
    high_status, high_missed = _periods(start, upper, [clock for clock, _, _ in events])
    if "data_gap" in {low_status, high_status}:
        return _gap("candidate_scope_incomplete")
    if low_status == "non_compliant":
        # 整日下界已经缺失的周期不可能被同日较晚的补记抹掉。
        status, missed = low_status, low_missed
    elif low_status != high_status:
        return _gap("authoritative_time_missing")
    else:
        status, missed = high_status, high_missed
    facts = {
        "verification_kind": "stage_summary_interval_check",
        "admission_time": start.isoformat(sep=" "),
        "evaluation_time": exact_end.isoformat(sep=" ") if exact_end is not None else None,
        "evaluation_date": end_date.isoformat(), "threshold_days": 30,
        "summary_times": [clock.isoformat(sep=" ") for clock, source, _ in events if source == "summary_record"],
        "substitute_times": [clock.isoformat(sep=" ") for clock, source, _ in events if source != "summary_record"],
        "overdue_deadlines": [clock.isoformat(sep=" ") for clock in missed],
    }
    return StageSummaryOutcome(status, {
        "compliant": "requirement_satisfied", "non_compliant": "required_document_missing",
        "not_applicable": "trigger_absent_complete",
    }[status], facts, tuple({"source_type": source, "source_document_id": document_id}
                           for _, source, document_id in events),
        tuple((event[1], consumed[event]) for event in events))
