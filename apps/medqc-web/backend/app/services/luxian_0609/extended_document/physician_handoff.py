"""LX0609-10-01-01 经治医师变更交接记录的确定性关联。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import ceil
from typing import Any, Mapping, Sequence

from .shared import _clean, _parse_datetime, _row_time
from ..evaluation_horizon import after_frozen_horizon, frozen_window_is_mature
from app.services.document_assembly.signatures import course_physician_signatures


_PHYSICIAN_CHANGE_ORDER_PATTERN = re.compile(
    r"经治医师(?:发生)?变更|更换经治医师|交接班医嘱"
)
_NON_ROUTINE_COURSE_TITLE_PATTERN = re.compile(
    r"上级医师查房|副主任医师查房|主任医师查房|会诊|手术|麻醉|抢救|"
    r"交接班|交班|接班|术前|术后|转科|转入|转出|死亡|出院"
)


@dataclass(frozen=True)
class PhysicianHandoffOutcome:
    final_state: str
    reason_code: str
    change_source_key: str
    display_facts: Mapping[str, Any] | None = None
    pending_change_rows: tuple[Mapping[str, Any], ...] = ()
    pending_binding_facts: Mapping[str, Any] | None = None


def _document_refs(
    source_rows: Sequence[tuple[str, Sequence[Mapping[str, Any]]]],
) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source_type, rows in source_rows:
        for row in rows:
            document_id = _clean(row.get("document_id") or row.get("id"))
            ref_key = (source_type, document_id)
            if not document_id or ref_key in seen:
                continue
            seen.add(ref_key)
            refs.append(
                {
                    "source_type": source_type,
                    "source_document_id": document_id,
                }
            )
            if len(refs) >= 8:
                return refs
    return refs


def _shift_time(row: Mapping[str, Any]) -> datetime | None:
    """返回交接班所属变更事件的时间，不以书写时间代替。"""

    return _parse_datetime(row.get("shift_time"))


def _handoff_record_time(
    row: Mapping[str, Any], *, field: str
) -> datetime | None:
    """返回交班/接班业务完成时间，缺失时才回退文书书写时间。"""

    raw_value = row.get(field)
    if _clean(raw_value):
        # 显式业务时间解析失败时不能偷偷消费 record_time，避免时间字段错位。
        return _parse_datetime(raw_value)
    return _row_time(row)


def _evaluate_explicit_order_events(
    *,
    change_times: Sequence[datetime],
    handoff_rows: Sequence[Mapping[str, Any]],
    handover_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    """无医师身份的医嘱回退只接受相同精确班次时间的一对一关联。"""

    ordered_change_times = tuple(sorted(change_times))
    all_refs = _document_refs(
        (
            ("handoff_record", handoff_rows),
            ("handover_record", handover_rows),
        )
    )
    change_rows = tuple(
        {
            "change_datetime": value.isoformat(sep=" "),
            "old_physician_name": "__shared_shift__",
            "new_physician_name": "__shared_shift__",
        }
        for value in ordered_change_times
    )
    normalized_handoffs = tuple(
        {**row, "handoff_doctor": "__shared_shift__"} for row in handoff_rows
    )
    normalized_handovers = tuple(
        {**row, "handover_doctor": "__shared_shift__"} for row in handover_rows
    )
    final_state, reason_code, facts = _evaluate_structured_change_events(
        change_rows=change_rows,
        handoff_rows=normalized_handoffs,
        handover_rows=normalized_handovers,
    )
    if final_state != "non_compliant":
        return final_state, reason_code, facts
    if not handoff_rows or not handover_rows:
        return final_state, reason_code, facts
    if facts.get("handoff_times") and facts.get("handover_times"):
        return final_state, reason_code, facts
    return (
        "data_gap",
        "association_failed",
        {
            "failure_kind": "physician_handoff_association_failed",
            "change_event_count": len(ordered_change_times),
            "change_times": [
                value.isoformat(sep=" ") for value in ordered_change_times
            ],
            "handoff_record_count": len(handoff_rows),
            "handoff_times": [
                value.isoformat(sep=" ")
                for row in handoff_rows
                if (value := _handoff_record_time(row, field="handoff_time")) is not None
            ],
            "handover_record_count": len(handover_rows),
            "handover_times": [
                value.isoformat(sep=" ")
                for row in handover_rows
                if (value := _handoff_record_time(row, field="handover_time")) is not None
            ],
            "handover_threshold_hours": 24,
            "source_document_refs": all_refs,
        },
    )


_SIGNATURE_LABEL_PATTERN = re.compile(r"(?:医师|医生)签名\s*[:：]")


def _is_blank_course(row: Mapping[str, Any]) -> bool:
    body = _SIGNATURE_LABEL_PATTERN.sub("", _clean(row.get("record_content")))
    return not body.strip() and not course_physician_signatures(row)


def _derive_change_rows_from_daily_courses(
    daily_course_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], str, Mapping[str, Any] | None]:
    """从普通病程的医师签名序列推导稳定的经治医师变更。"""

    eligible_count = 0
    missing_field_rows: list[Mapping[str, Any]] = []
    timed_signed_rows: list[tuple[datetime, str, Mapping[str, Any]]] = []
    missing_title_count = 0
    missing_time_count = 0
    missing_signature_count = 0
    ambiguous_signature_count = 0
    for row in daily_course_rows:
        title = _clean(row.get("document_title"))
        # 用户口径（2026-10-21）：经治医师变更只看普通病程的签名序列，标题不是
        # 质控要求。有标题且属于查房、手术、交接班等非常规病程的仍排除；缺标题
        # 不再使整例资料不足（1019 中院方另一路写入的病程均无标题）。
        if title and _NON_ROUTINE_COURSE_TITLE_PATTERN.search(title):
            continue
        if _is_blank_course(row):
            # 无正文且无签名的空白文书不含任何书写医师信息，不进入序列。
            continue
        eligible_count += 1
        record_time = _row_time(row)
        # 提交人是文书元数据，可能与签名医师不同；缺结构化签名时只读取
        # 明确的正文签名栏，不能把任意正文姓名或提交人当作经治医师。
        signers = course_physician_signatures(row)
        physician_name = signers[0] if len(signers) == 1 else ""
        if record_time is None:
            missing_time_count += 1
        if not signers:
            missing_signature_count += 1
        elif len(signers) > 1:
            ambiguous_signature_count += 1
        if record_time is None or not physician_name:
            missing_field_rows.append(row)
        if record_time is not None and physician_name:
            timed_signed_rows.append((record_time, physician_name, row))

    if missing_title_count or missing_time_count or missing_signature_count or ambiguous_signature_count:
        return (
            (),
            "required_field_missing",
            {
                "failure_kind": "physician_signature_timeline_incomplete",
                "daily_course_record_count": len(daily_course_rows),
                "eligible_daily_course_count": eligible_count,
                "missing_title_count": missing_title_count,
                "missing_time_count": missing_time_count,
                "missing_signature_count": missing_signature_count,
                **({"ambiguous_signature_count": ambiguous_signature_count} if ambiguous_signature_count else {}),
                "source_document_refs": _document_refs(
                    (("daily_course_record", missing_field_rows),)
                ),
            },
        )

    ordered_rows = sorted(timed_signed_rows, key=lambda item: item[0])
    if not ordered_rows:
        return (), "", None

    runs: list[list[tuple[datetime, str, Mapping[str, Any]]]] = []
    for item in ordered_rows:
        if runs and runs[-1][0][1].casefold() == item[1].casefold():
            runs[-1].append(item)
        else:
            runs.append([item])

    # 起始经治医师同样须连续书写才成立：开头一份异名文书（如值班医师写的危急值
    # 处理记录，1019 C14/C17）与中途临时代班同理，不能据此把后续主管医师判为变更。
    start = next((index for index, run in enumerate(runs) if len(run) >= 2), None)
    if start is None:
        return (), "", None
    current_physician = runs[start][0][1]
    change_rows: list[Mapping[str, Any]] = []
    for run in runs[start + 1:]:
        new_physician = run[0][1]
        if new_physician.casefold() == current_physician.casefold():
            continue
        # 单份异名文书可能来自临时代班，不足以证明经治医师发生变更。
        if len(run) < 2:
            continue
        change_time, _, first_row = run[0]
        change_rows.append(
            {
                "change_datetime": change_time.isoformat(sep=" "),
                "old_physician_name": current_physician,
                "new_physician_name": new_physician,
                "document_id": first_row.get("document_id") or first_row.get("id"),
            }
        )
        current_physician = new_physician
    return tuple(change_rows), "", None


def _evaluate_derived_change_events(
    *,
    change_rows: Sequence[Mapping[str, Any]],
    handoff_rows: Sequence[Mapping[str, Any]],
    handover_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    """按签名推导时间，为每次变更选择身份相符且时间最近的交接文书。"""

    normalized_handoffs: list[Mapping[str, Any]] = []
    normalized_handovers: list[Mapping[str, Any]] = []
    for rows, field in (
        (handoff_rows, "handoff_time"),
        (handover_rows, "handover_time"),
    ):
        if any(_handoff_record_time(row, field=field) is None for row in rows):
            return (
                "data_gap",
                "authoritative_time_missing",
                {
                    "failure_kind": "physician_handoff_record_time_missing",
                    "change_event_count": len(change_rows),
                    "handoff_record_count": len(handoff_rows),
                    "handover_record_count": len(handover_rows),
                    "handover_threshold_hours": 24,
                    "source_document_refs": _document_refs(
                        (("handoff_record", handoff_rows), ("handover_record", handover_rows))
                    ),
                },
            )

    ordered_changes = tuple(
        sorted(change_rows, key=lambda row: _parse_datetime(row.get("change_datetime")) or datetime.min)
    )
    for position, change_row in enumerate(ordered_changes):
        change_time = _parse_datetime(change_row.get("change_datetime"))
        assert change_time is not None
        previous_change_time = (
            _parse_datetime(ordered_changes[position - 1].get("change_datetime"))
            if position
            else None
        )
        next_change_time = (
            _parse_datetime(ordered_changes[position + 1].get("change_datetime"))
            if position + 1 < len(ordered_changes)
            else None
        )
        old_physicians = _identity_tokens(change_row, _OLD_PHYSICIAN_FIELDS)
        new_physicians = _identity_tokens(change_row, _NEW_PHYSICIAN_FIELDS)
        handoff_candidates = [
            row
            for row in handoff_rows
            if _identity_tokens(row, _HANDOFF_PHYSICIAN_FIELDS).intersection(old_physicians)
            and (record_time := _handoff_record_time(row, field="handoff_time")) is not None
            and (previous_change_time is None or record_time >= previous_change_time)
            and record_time <= change_time
        ]
        handover_candidates = [
            row
            for row in handover_rows
            if _identity_tokens(row, _HANDOVER_PHYSICIAN_FIELDS).intersection(new_physicians)
            and (record_time := _handoff_record_time(row, field="handover_time")) is not None
            and record_time >= change_time
            and (next_change_time is None or record_time < next_change_time)
        ]
        ambiguous_handoff_identity = any(
            not _identity_tokens(row, _HANDOFF_PHYSICIAN_FIELDS)
            and (record_time := _handoff_record_time(row, field="handoff_time")) is not None
            and (previous_change_time is None or record_time >= previous_change_time)
            and record_time <= change_time
            for row in handoff_rows
        )
        ambiguous_handover_identity = any(
            not _identity_tokens(row, _HANDOVER_PHYSICIAN_FIELDS)
            and (record_time := _handoff_record_time(row, field="handover_time")) is not None
            and record_time >= change_time
            and (next_change_time is None or record_time < next_change_time)
            for row in handover_rows
        )
        if (
            not handoff_candidates
            and ambiguous_handoff_identity
            or not handover_candidates
            and ambiguous_handover_identity
        ):
            return (
                "data_gap",
                "association_failed",
                {
                    "failure_kind": "physician_handoff_identity_missing",
                    "change_event_count": len(change_rows),
                    "change_times": [
                        _clean(row.get("change_datetime")) for row in ordered_changes
                    ],
                    "handoff_record_count": len(handoff_rows),
                    "handoff_times": [
                        value.isoformat(sep=" ")
                        for row in handoff_rows
                        if (value := _handoff_record_time(row, field="handoff_time"))
                        is not None
                    ],
                    "handover_record_count": len(handover_rows),
                    "handover_times": [
                        value.isoformat(sep=" ")
                        for row in handover_rows
                        if (value := _handoff_record_time(row, field="handover_time"))
                        is not None
                    ],
                    "handover_threshold_hours": 24,
                    "source_document_refs": _document_refs((
                        ("daily_course_record", change_rows),
                        ("handoff_record", handoff_rows),
                        ("handover_record", handover_rows),
                    )),
                },
            )
        if handoff_candidates:
            selected = max(
                handoff_candidates,
                key=lambda row: _handoff_record_time(row, field="handoff_time") or datetime.min,
            )
            normalized_handoffs.append({**selected, "shift_time": change_row["change_datetime"]})
        if handover_candidates:
            selected = min(
                handover_candidates,
                key=lambda row: _handoff_record_time(row, field="handover_time") or datetime.max,
            )
            normalized_handovers.append({**selected, "shift_time": change_row["change_datetime"]})

    state, reason, facts = _evaluate_structured_change_events(
        change_rows=change_rows,
        handoff_rows=tuple(normalized_handoffs),
        handover_rows=tuple(normalized_handovers),
    )
    facts["source_document_refs"] = _document_refs((
        ("daily_course_record", change_rows),
        ("handoff_record", normalized_handoffs),
        ("handover_record", normalized_handovers),
    ))
    return state, reason, facts


def _identity_tokens(
    row: Mapping[str, Any],
    fields: Sequence[str],
) -> frozenset[str]:
    return frozenset(
        value.casefold()
        for field in fields
        if (value := _clean(row.get(field)))
    )


_OLD_PHYSICIAN_FIELDS = (
    "old_physician_id",
    "old_physician_name",
    "original_physician_id",
    "original_physician_name",
    "former_physician_id",
    "former_physician_name",
)
_NEW_PHYSICIAN_FIELDS = (
    "new_physician_id",
    "new_physician_name",
    "receiving_physician_id",
    "receiving_physician_name",
)
_HANDOFF_PHYSICIAN_FIELDS = (
    "handoff_doctor_id",
    "handoff_doctor",
    "handoff_physician_id",
    "handoff_physician_name",
)
_HANDOVER_PHYSICIAN_FIELDS = (
    "handover_doctor_id",
    "handover_doctor",
    "handover_physician_id",
    "handover_physician_name",
)


def _evaluate_structured_change_events(
    *,
    change_rows: Sequence[Mapping[str, Any]],
    handoff_rows: Sequence[Mapping[str, Any]],
    handover_rows: Sequence[Mapping[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    """按变更时间及原、新经治医师身份逐事件关联交接班文书。"""

    ordered_changes = tuple(
        sorted(
            (
                (_parse_datetime(row.get("change_datetime")), row)
                for row in change_rows
            ),
            key=lambda item: item[0] or datetime.min,
        )
    )
    change_times = tuple(item[0] for item in ordered_changes if item[0] is not None)
    all_refs = _document_refs(
        (
            ("handoff_record", handoff_rows),
            ("handover_record", handover_rows),
        )
    )
    handoff_data = tuple(
        (
            _shift_time(row),
            _handoff_record_time(row, field="handoff_time"),
            _identity_tokens(row, _HANDOFF_PHYSICIAN_FIELDS),
            row,
        )
        for row in handoff_rows
    )
    handover_data = tuple(
        (
            _shift_time(row),
            _handoff_record_time(row, field="handover_time"),
            _identity_tokens(row, _HANDOVER_PHYSICIAN_FIELDS),
            row,
        )
        for row in handover_rows
    )

    def association_failed() -> tuple[str, str, dict[str, Any]]:
        return (
            "data_gap",
            "association_failed",
            {
                "failure_kind": "physician_handoff_association_failed",
                "change_event_count": len(change_rows),
                "change_times": [value.isoformat(sep=" ") for value in change_times],
                "handoff_record_count": len(handoff_rows),
                "handoff_times": [
                    value.isoformat(sep=" ")
                    for _, value, _, _ in handoff_data
                    if value is not None
                ],
                "handover_record_count": len(handover_rows),
                "handover_times": [
                    value.isoformat(sep=" ")
                    for _, value, _, _ in handover_data
                    if value is not None
                ],
                "handover_threshold_hours": 24,
                "source_document_refs": all_refs,
            },
        )

    if len(change_times) != len(change_rows):
        return association_failed()
    missing_handoff_time_count = sum(
        record_time is None for _, record_time, _, _ in handoff_data
    )
    missing_handover_time_count = sum(
        record_time is None for _, record_time, _, _ in handover_data
    )
    if missing_handoff_time_count or missing_handover_time_count:
        return (
            "data_gap",
            "authoritative_time_missing",
            {
                "failure_kind": "physician_handoff_record_time_missing",
                "change_event_count": len(change_rows),
                "handoff_record_count": len(handoff_rows),
                "missing_handoff_time_count": missing_handoff_time_count,
                "handover_record_count": len(handover_rows),
                "missing_handover_time_count": missing_handover_time_count,
                "handover_threshold_hours": 24,
                "source_document_refs": all_refs,
            },
        )
    if any(shift_time is None for shift_time, _, _, _ in (*handoff_data, *handover_data)):
        # 文书本身有记录时间，但缺少所属交接班事件时间时，无法把它安全关联到
        # 某次经治医师变更。保留已有数量、时间和证据供客户核对，不能返回空事实，
        # 否则正式交付合同会拒绝整份质控结果。
        return association_failed()

    events: list[dict[str, Any]] = []
    selected_rows: list[tuple[str, Sequence[Mapping[str, Any]]]] = []
    all_completed = True
    for position, (change_time, change_row) in enumerate(ordered_changes, start=1):
        assert change_time is not None
        old_physicians = _identity_tokens(change_row, _OLD_PHYSICIAN_FIELDS)
        new_physicians = _identity_tokens(change_row, _NEW_PHYSICIAN_FIELDS)
        if not old_physicians or not new_physicians:
            return association_failed()

        exact_handoffs = tuple(item for item in handoff_data if item[0] == change_time)
        exact_handovers = tuple(item for item in handover_data if item[0] == change_time)
        if any(
            record_time is None
            for _, record_time, _, _ in (*exact_handoffs, *exact_handovers)
        ):
            return "data_gap", "authoritative_time_missing", {}
        if any(
            not doctor_tokens
            for _, _, doctor_tokens, _ in (*exact_handoffs, *exact_handovers)
        ):
            return association_failed()
        handoff_candidates = tuple(
            item
            for item in exact_handoffs
            if item[2].intersection(old_physicians)
        )
        handover_candidates = tuple(
            item
            for item in exact_handovers
            if item[2].intersection(new_physicians)
        )
        if len(handoff_candidates) > 1 or len(handover_candidates) > 1:
            return association_failed()

        selected_handoff = handoff_candidates[0] if handoff_candidates else None
        selected_handover = handover_candidates[0] if handover_candidates else None
        handoff_record_time = selected_handoff[1] if selected_handoff else None
        handover_record_time = selected_handover[1] if selected_handover else None
        if handover_record_time is not None and handover_record_time < change_time:
            return (
                "data_gap",
                "authoritative_time_conflict",
                association_failed()[2],
            )
        interval_seconds = (
            ceil((handover_record_time - change_time).total_seconds())
            if handover_record_time is not None
            else None
        )
        if selected_handoff is None or (
            handoff_record_time is not None and handoff_record_time > change_time
        ):
            outcome = "handoff_missing"
        elif selected_handover is None:
            outcome = "handover_missing"
        elif interval_seconds is not None and interval_seconds > 86400:
            outcome = "handover_late"
        else:
            outcome = "completed_within_threshold"
        all_completed = all_completed and outcome == "completed_within_threshold"
        events.append(
            {
                "event_position": position,
                "change_time": change_time.isoformat(sep=" "),
                "handoff_time": (
                    handoff_record_time.isoformat(sep=" ")
                    if outcome != "handoff_missing" and handoff_record_time is not None
                    else None
                ),
                "handover_time": (
                    handover_record_time.isoformat(sep=" ")
                    if handover_record_time is not None
                    else None
                ),
                "handover_interval_seconds": interval_seconds,
                "outcome": outcome,
            }
        )
        for source_type, selected in (
            ("handoff_record", selected_handoff),
            ("handover_record", selected_handover),
        ):
            if selected is not None:
                selected_rows.append((source_type, (selected[3],)))

    state = "compliant" if all_completed else "non_compliant"
    reason = "requirement_satisfied" if all_completed else "requirement_violated"
    refs = _document_refs(tuple(selected_rows))
    if len(events) == 1:
        event = events[0]
        return (
            state,
            reason,
            {
                "verification_kind": "physician_handoff_timeliness_check",
                "change_time": event["change_time"],
                "handoff_times": (
                    [event["handoff_time"]] if event["handoff_time"] else []
                ),
                "handover_times": (
                    [event["handover_time"]] if event["handover_time"] else []
                ),
                "handover_threshold_hours": 24,
                "source_document_refs": refs,
            },
        )
    return (
        state,
        reason,
        {
            "verification_kind": "physician_handoff_multi_event_check",
            "change_event_count": len(events),
            "handover_threshold_hours": 24,
            "events": events,
            "source_document_refs": refs,
        },
    )




def _mature_handoff_outcome(
    state: str, reason: str, facts: Mapping[str, Any] | None,
    horizon: datetime | date | None, horizon_error: str,
) -> tuple[str, str, Mapping[str, Any] | None]:
    if state != "non_compliant" or not isinstance(facts, Mapping):
        return state, reason, facts
    events = facts.get("events") or ({
        "change_time": facts.get("change_time"),
        "handoff_time": next(iter(facts.get("handoff_times") or ()), None),
        "handover_time": next(iter(facts.get("handover_times") or ()), None),
    },)
    events = [dict(item) for item in events]
    pending = missing_horizon = conflicting_horizon = confirmed = False
    for item in events:
        change = _parse_datetime(item.get("change_time"))
        handoff = _parse_datetime(item.get("handoff_time"))
        handover = _parse_datetime(item.get("handover_time"))
        # 已证实未按要求交班或接班超时，不能被另一尚未成熟事件覆盖。
        if change is not None and (handoff is None or handoff > change or (handover is not None and handover > change + timedelta(hours=24))):
            confirmed = True
        if handover is None:
            if change is None or horizon_error or horizon is None:
                missing_horizon = True
                if item.get("outcome") == "handover_missing":
                    item["outcome"] = "handover_window_unresolved"
            elif after_frozen_horizon(change, horizon):
                conflicting_horizon = True
            elif frozen_window_is_mature(horizon, change + timedelta(hours=24)):
                confirmed = True
            else:
                pending = True
                if item.get("outcome") == "handover_missing":
                    item["outcome"] = "handover_window_not_mature"
    if confirmed:
        return state, reason, {**facts, "events": events} if "events" in facts else facts
    if conflicting_horizon:
        return "data_gap", "authoritative_time_conflict", None
    if missing_horizon:
        return "data_gap", horizon_error or "authoritative_time_missing", None
    return ("not_applicable", "evaluation_window_not_mature", facts) if pending else (state, reason, facts)


def _is_effective_physician_change_order(row: Mapping[str, Any]) -> bool:
    if any(marker in _clean(row.get("order_status")) for marker in ("取消", "作废", "撤销", "未执行")):
        return False
    # 不将类别字段中的“变更”覆盖正文的拟行/取消语义。
    text = " ".join(_clean(row.get(field)) for field in ("order_name", "record_content"))
    if not text.strip():
        text = _clean(row.get("order_type"))
    # 按局部情态先后区分否定原因与实际变更；后续否定/计划优先于先前肯定。
    pending_action = re.compile(r"拟|计划|准备|考虑|建议|待|暂缓|未|不|取消|撤销|作废")
    # “已”后允许动作修饰；发现/出现等复合词尾字不属于独立现行事实。
    completed_action = re.compile(r"已经?|(?<![发出体实呈表再显])现(?:行)?\s*$")
    history = re.compile(r"既往|此前|曾经|曾")
    current_scope = re.compile(r"本次|此次|今日|目前|现在|现")
    for clause in re.split(r"[，,。；;\n]", text):
        for match in _PHYSICIAN_CHANGE_ORDER_PATTERN.finditer(clause):
            prefix = clause[:match.start()]
            pending = tuple(pending_action.finditer(prefix))
            completed = tuple(completed_action.finditer(prefix))
            if pending and (not completed or pending[-1].start() > completed[-1].start()):
                continue
            histories = tuple(history.finditer(prefix))
            currents = tuple(current_scope.finditer(prefix))
            if histories and (not currents or currents[-1].start() < histories[-1].start()):
                continue
            return True
    return False


def _physician_change_time(row: Mapping[str, Any]) -> datetime | None:
    return _parse_datetime(
        row.get("change_datetime")
        or row.get("handoff_datetime")
        or row.get("prescribed_datetime")
        or row.get("order_time")
    )


def evaluate_physician_handoff(
    *,
    physician_change_rows: Sequence[Mapping[str, Any]],
    physician_change_error: str,
    nondrug_order_rows: Sequence[Mapping[str, Any]],
    nondrug_order_error: str,
    daily_course_rows: Sequence[Mapping[str, Any]],
    daily_course_error: str,
    handoff_rows: Sequence[Mapping[str, Any]],
    handoff_error: str,
    handover_rows: Sequence[Mapping[str, Any]],
    handover_error: str,
    evaluation_horizon_datetime: datetime | date | None = None,
    evaluation_horizon_error: str = "",
    daily_scope_complete: bool = True,
) -> PhysicianHandoffOutcome:
    """逐次核对经治医师变更前交班与变更后24小时内接班记录。"""

    explicit_change_orders = tuple(
        row
        for row in nondrug_order_rows
        if _is_effective_physician_change_order(row)
    )
    change_source_key = "physician_change_event"
    effective_change_rows = physician_change_rows
    if not effective_change_rows and explicit_change_orders:
        change_source_key = "inpat_nondrug_order"
        effective_change_rows = explicit_change_orders

    if not effective_change_rows:
        change_source_key = "daily_course_record"
        if daily_course_error:
            return PhysicianHandoffOutcome(
                "data_gap", daily_course_error, change_source_key
            )
        if not daily_scope_complete:
            return PhysicianHandoffOutcome("data_gap", "source_unavailable", change_source_key)
        effective_change_rows, derivation_error, derivation_facts = (
            _derive_change_rows_from_daily_courses(daily_course_rows)
        )
        if derivation_error:
            return PhysicianHandoffOutcome(
                "data_gap",
                derivation_error,
                change_source_key,
                derivation_facts,
            )
    if not effective_change_rows:
        has_signature_material = any(
            not _is_blank_course(row)
            and not _NON_ROUTINE_COURSE_TITLE_PATTERN.search(_clean(row.get("document_title")))
            for row in daily_course_rows
        )
        if (physician_change_error or nondrug_order_error) and not has_signature_material:
            # 空或非常规病程不能替代不可读的变更来源证明“没有变更”；
            # 已核完整的普通病程签名序列仍可沿客户确认口径回退。
            return PhysicianHandoffOutcome(
                "data_gap", physician_change_error or nondrug_order_error, change_source_key,
            )
        return PhysicianHandoffOutcome(
            "not_applicable",
            "trigger_absent_complete",
            change_source_key,
        )
    source_error = handoff_error or handover_error
    if source_error:
        return PhysicianHandoffOutcome("data_gap", source_error, change_source_key)

    change_times = tuple(
        parsed
        for row in effective_change_rows
        if (parsed := _physician_change_time(row)) is not None
    )
    handoff_times = tuple(
        parsed
        for row in handoff_rows
        if (parsed := _handoff_record_time(row, field="handoff_time")) is not None
    )
    handover_times = tuple(
        parsed
        for row in handover_rows
        if (parsed := _handoff_record_time(row, field="handover_time")) is not None
    )
    all_document_refs = _document_refs(
        (
            ("handoff_record", handoff_rows),
            ("handover_record", handover_rows),
        )
    )

    if len(change_times) != len(effective_change_rows):
        if change_times and change_source_key in {"physician_change_event", "inpat_nondrug_order"}:
            # 缺变更时间的事件保持未决；其余有可靠时间的事件仍按原逐事件合同（含成熟判定）核对。
            # 只有这些事件自身已形成确定缺陷时才交付不合规，缺失清单不列入未决事件；
            # 否则沿用下方整体资料不足（不把未决事件写成缺失、超时或已完成）。
            timed_rows = tuple(
                row for row in effective_change_rows
                if _physician_change_time(row) is not None
            )
            def related_records(rows, record_fields, change_fields):
                # 仅隔离班次时间和人员均可证明不属于可靠事件的文书。
                # 缺班次、缺身份或可能相关的坏时间文书仍参与核对，保持未决。
                timed_physicians = set().union(*(
                    _identity_tokens(row, change_fields) for row in timed_rows
                ))
                return tuple(
                    row for row in rows
                    if not (
                        change_source_key == "physician_change_event"
                        and _shift_time(row) is not None
                        and _shift_time(row) not in change_times
                        and timed_physicians
                        and _identity_tokens(row, record_fields)
                        and not _identity_tokens(row, record_fields).intersection(timed_physicians)
                    )
                )

            timed_outcome = evaluate_physician_handoff(
                physician_change_rows=timed_rows if change_source_key == "physician_change_event" else (),
                physician_change_error=physician_change_error,
                nondrug_order_rows=timed_rows if change_source_key == "inpat_nondrug_order" else (),
                nondrug_order_error=nondrug_order_error,
                daily_course_rows=daily_course_rows,
                daily_course_error=daily_course_error,
                daily_scope_complete=daily_scope_complete,
                handoff_rows=related_records(handoff_rows, _HANDOFF_PHYSICIAN_FIELDS, _OLD_PHYSICIAN_FIELDS),
                handoff_error=handoff_error,
                handover_rows=related_records(handover_rows, _HANDOVER_PHYSICIAN_FIELDS, _NEW_PHYSICIAN_FIELDS),
                handover_error=handover_error,
                evaluation_horizon_datetime=evaluation_horizon_datetime,
                evaluation_horizon_error=evaluation_horizon_error,
            )
            if (timed_outcome.final_state == "non_compliant"
                    and timed_outcome.change_source_key == change_source_key):
                return timed_outcome
        return PhysicianHandoffOutcome(
            "data_gap",
            "authoritative_time_missing",
            change_source_key,
            {
                "failure_kind": "physician_change_time_missing",
                "change_event_count": len(effective_change_rows),
                "timed_change_event_count": len(change_times),
                "missing_change_time_count": len(effective_change_rows) - len(change_times),
                "change_times": [value.isoformat(sep=" ") for value in change_times],
                "handoff_record_count": len(handoff_rows),
                "handoff_times": [value.isoformat(sep=" ") for value in handoff_times],
                "handover_record_count": len(handover_rows),
                "handover_times": [value.isoformat(sep=" ") for value in handover_times],
                "handover_threshold_hours": 24,
                "source_document_refs": all_document_refs,
            },
        )
    if len(change_times) > 1 and (
        len(set(change_times)) != len(change_times) or len(change_times) > 4
    ):
        return PhysicianHandoffOutcome(
            "data_gap",
            "association_failed",
            change_source_key,
            {
                "failure_kind": "physician_handoff_association_failed",
                "change_event_count": len(effective_change_rows),
                "change_times": [value.isoformat(sep=" ") for value in change_times],
                "handoff_record_count": len(handoff_rows),
                "handoff_times": [value.isoformat(sep=" ") for value in handoff_times],
                "handover_record_count": len(handover_rows),
                "handover_times": [value.isoformat(sep=" ") for value in handover_times],
                "handover_threshold_hours": 24,
                "source_document_refs": all_document_refs,
            },
        )
    def window_outcome(
        final_state: str, reason_code: str, facts: Mapping[str, Any] | None,
    ) -> PhysicianHandoffOutcome:
        final_state, reason_code, facts = _mature_handoff_outcome(
            final_state, reason_code, facts, evaluation_horizon_datetime, evaluation_horizon_error,
        )
        if reason_code == "evaluation_window_not_mature":
            if change_source_key != "physician_change_event" and physician_change_error:
                return PhysicianHandoffOutcome("data_gap", physician_change_error, change_source_key)
            if change_source_key == "physician_change_event" and any(
                _physician_change_time(row) not in change_times for row in explicit_change_orders
            ):
                # 不同时间或没有时间的明确医嘱可能是另一变更，无法证明整例均未到期。
                return PhysicianHandoffOutcome("data_gap", "association_failed", change_source_key)
            # 只有权威事件可独立证明适用窗口；备选医嘱及签名链保留原有覆盖要求。
            verified_rows = tuple(effective_change_rows) if change_source_key == "physician_change_event" else ()
            return PhysicianHandoffOutcome(
                final_state, reason_code, change_source_key,
                pending_change_rows=verified_rows, pending_binding_facts=facts,
            )
        return PhysicianHandoffOutcome(final_state, reason_code, change_source_key, facts)

    if change_source_key == "inpat_nondrug_order":
        return window_outcome(*_evaluate_explicit_order_events(
            change_times=change_times,
            handoff_rows=handoff_rows,
            handover_rows=handover_rows,
        ))
    if change_source_key == "daily_course_record":
        return window_outcome(*_evaluate_derived_change_events(
            change_rows=effective_change_rows,
            handoff_rows=handoff_rows,
            handover_rows=handover_rows,
        ))
    return window_outcome(*_evaluate_structured_change_events(
        change_rows=effective_change_rows,
        handoff_rows=handoff_rows,
        handover_rows=handover_rows,
    ))
