"""LX0609-10-02-01、LX0609-10-02-02 转科文书按单次转科事件关联的确定性判定。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Mapping, Sequence

from ..basic_timeliness_facts import parse_authoritative_datetime, parse_authoritative_date
from ..source_evidence_reader import authoritative_document_time_value
from .shared import _clean


@dataclass(frozen=True)
class TransferDocumentationOutcome:
    final_state: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None
    consumed_rows: tuple[tuple[str, Mapping[str, Any]], ...] = ()


@dataclass(frozen=True)
class _TransferRecordCandidate:
    state: str
    record_time: datetime | None = None
    row: Mapping[str, Any] | None = None


_TRANSFER_IN_DESTINATION_PATTERN = re.compile(
    r"转入(?:ICU|[\u4e00-\u9fffA-Za-z0-9]+科)",
    re.IGNORECASE,
)
_NON_CLINICAL_TRANSFER_MARKERS = ("药品", "病案")
_NON_CURRENT_TRANSFER_PREFIX = re.compile(
    r"拟|计划|准备|考虑|建议|暂不|暂缓|不予|无需|未予|取消|拒绝|"
    r"(?:待|等|若|如|如果).*(?:再|后)|(?:稳定|好转)后再"
)
# 多次转科且转出记录未填科室字段时，医师常在提交转科医嘱前数分钟至2小时内先写转出记录；
# 仅当距离上一转科已超24小时（不与上一次24小时窗口冲突）时，允许归属到紧随其后的本次转科事件。
_MULTI_EVENT_UNLABELLED_EARLY_OUT_TOLERANCE = timedelta(hours=2)


def _has_current_transfer_clause(text: str) -> bool:
    """逐分句识别正式转科；计划或否定不得遮蔽另一句已发生转科。"""
    for clause in re.split(r"[，,。；;\n]", text):
        normalized = re.sub(r"\s+", "", clause).strip("：:")
        match = re.search(r"转科", normalized)
        if match is None:
            match = _TRANSFER_IN_DESTINATION_PATTERN.fullmatch(normalized)
        if match is not None and not _NON_CURRENT_TRANSFER_PREFIX.search(
            normalized[:match.start()]
        ):
            return True
    return False


def select_transfer_order_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    """选择已正式下达且指向临床科室的转科医嘱。"""

    selected = []
    for row in rows:
        text = _clean(row.get("order_name") or row.get("record_content"))
        if not _has_current_transfer_clause(text):
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

    return parse_authoritative_datetime(value)


def _date_value(value: Any) -> date | None:
    moment = _precise_datetime(value)
    return moment.date() if moment is not None else parse_authoritative_date(value)


def _candidate_for_order(
    row: Mapping[str, Any], *, order_time: datetime
) -> _TransferRecordCandidate:
    # transfer_date 描述转科事件发生日期，优先用于排除既往住院转科。
    # 即使文书后来补录、record_time 较新，也不能让历史事件满足本次医嘱。
    transfer_date_value = row.get("transfer_date")
    transfer_date = _date_value(transfer_date_value)
    if transfer_date is not None and transfer_date < order_time.date():
        return _TransferRecordCandidate("historical", row=row)

    document_value = authoritative_document_time_value(row)
    document_time = _precise_datetime(document_value)
    if document_time is not None:
        return _TransferRecordCandidate(
            "historical" if document_time < order_time else "current",
            document_time,
            row,
        )
    if document_value is not None and str(document_value).strip():
        return _TransferRecordCandidate("time_unknown", row=row)

    # transfer_date 是兼容字段。仅日期不能证明同日先后及24小时边界；
    # 但明确早于医嘱日期的记录可排除为历史记录。
    transfer_date_time = _precise_datetime(transfer_date_value)
    if transfer_date_time is not None:
        return _TransferRecordCandidate(
            "historical" if transfer_date_time < order_time else "current",
            transfer_date_time,
            row,
        )
    return _TransferRecordCandidate("time_unknown", row=row)


def _record_state(
    *,
    records: Sequence[Mapping[str, Any]],
    order_time: datetime,
    early_out_order: Mapping[str, Any] | None = None,
    order: Mapping[str, Any] | None = None,
) -> tuple[str, datetime | None, tuple[Mapping[str, Any], ...]]:
    """返回单类文书与唯一转科医嘱的关联状态及唯一时间。"""

    if not records:
        return "missing", None, ()
    candidates = tuple(_candidate_for_order(row, order_time=order_time) for row in records)
    current = tuple(item for item in candidates if item.state == "current")
    if order is not None and any(_departments_conflict(item.row, order) for item in current):
        return "multiple", None, tuple(item.row for item in current)
    has_unknown = any(item.state == "time_unknown" for item in candidates)
    # 主控代定口径（2026-10-18，待客户复核），基线072/073：
    # 提前不超过24小时的转出须科室对应且为唯一候选，不能只凭时间接受。
    early = tuple((row, moment) for row in records
                  if (moment := _precise_datetime(authoritative_document_time_value(row))) is not None
                  and order_time - timedelta(hours=24) <= moment < order_time
                  and (_date_value(row.get("transfer_date")) is None
                       or _date_value(row.get("transfer_date")) >= order_time.date()))
    if current and early_out_order is not None:
        # 已有当前记录时，不把科室不对应的历史文书新增为本次候选。
        early = tuple(item for item in early if _departments_correspond(item[0], early_out_order))
    if early_out_order is not None and early:
        if current or len(early) > 1 or not _departments_compatible(early[0][0], early_out_order):
            return "multiple", None, tuple(records)
        if has_unknown:
            return "time_unknown", None, tuple(records)
        return "matched", early[0][1], (early[0][0],)
    if len(current) > 1:
        return "multiple", None, tuple(item.row for item in current)
    if current and has_unknown:
        return "time_unknown", None, tuple(item.row for item in candidates if item.state != "historical")
    if current:
        return "matched", current[0].record_time, (current[0].row,)
    if has_unknown:
        return "time_unknown", None, tuple(item.row for item in candidates if item.state == "time_unknown")
    return "historical", None, ()


def _unique_order_time(row: Mapping[str, Any]) -> tuple[datetime | None, bool]:
    """同一医嘱的多个正式时间必须一致，不能按字段顺序静默择一。"""

    raw_values = tuple(row[field] for field in ("start_time", "order_time", "prescribed_datetime")
                       if row.get(field) is not None and str(row[field]).strip())
    values = tuple(_precise_datetime(value) for value in raw_values)
    if any(value is None for value in values):
        return None, False
    unique_values = tuple(dict.fromkeys(values))
    if len(unique_values) > 1:
        return None, True
    return (unique_values[0] if unique_values else None), False


def _target_department(order: Mapping[str, Any]) -> str:
    value = order.get("transferin_department") or order.get("target_department")
    if value:
        return re.sub(r"\s+", "", _clean(value)).upper()
    text = re.sub(r"\s+", "", _clean(order.get("order_name") or order.get("record_content")))
    match = re.search(r"(?:转科至|转科到|转入|转往|转至)[:：]?([\u4e00-\u9fffA-Za-z0-9]+?科|ICU)(?=$|[，,。；;（(])", text, re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _departments_correspond(record: Mapping[str, Any], order: Mapping[str, Any]) -> bool:
    if _departments_conflict(record, order):
        return False
    target = _target_department(order)
    record_target = re.sub(r"\s+", "", _clean(record.get("transferin_department"))).upper()
    current = _clean(order.get("current_department") or order.get("transferout_department"))
    record_source = _clean(record.get("transferout_department"))
    return bool((target and record_target == target) or (current and record_source == current))


def _departments_conflict(record: Mapping[str, Any], order: Mapping[str, Any]) -> bool:
    """已提供的科室身份必须一致，不能以时间接近或另一端匹配掩盖冲突。"""
    normalize = lambda value: re.sub(r"\s+", "", _clean(value)).upper()
    pairs = (
        (_target_department(order), normalize(record.get("transferin_department"))),
        (normalize(order.get("current_department") or order.get("transferout_department")),
         normalize(record.get("transferout_department"))),
    )
    return any(left and right and left != right for left, right in pairs)


def _departments_compatible(record: Mapping[str, Any], order: Mapping[str, Any]) -> bool:
    """单次转科、唯一提前转出记录时的科室核对：科室对应，或记录未填任何科室字段。

    Claude 代定口径（2026-10-22，用户授权，C03/C09）：转出记录比转科医嘱早几分钟书写且未填科室，
    科室无从矛盾；住院内仅一次转科医嘱、仅此一份提前转出记录时关联唯一，按时间接受。
    记录填了科室但与医嘱不对应时仍不接受。
    """
    if _departments_correspond(record, order):
        return True
    return not any(_clean(record.get(field)) for field in ("transferin_department", "transferout_department"))


def _group_transfer_orders(
    ordered: Sequence[tuple[datetime, Mapping[str, Any]]],
    transfer_in_rows: Sequence[Mapping[str, Any]],
) -> tuple[tuple[datetime, Mapping[str, Any]], ...]:
    """主控代定口径（2026-10-18，待客户复核），基线072/073：相邻同目标合并。"""
    groups = []
    previous_time = None
    previous_target = ""
    in_times = tuple(_precise_datetime(authoritative_document_time_value(row)) for row in transfer_in_rows)
    for moment, order in ordered:
        target = _target_department(order)
        merge = (previous_time is not None and target and target == previous_target
                 and moment - previous_time <= timedelta(hours=24)
                 and all(value is not None and not previous_time <= value <= moment for value in in_times))
        if not merge:
            groups.append((moment, order))
        previous_time, previous_target = moment, target
    return tuple(groups)


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
            if rule_id == "LX0609-10-02-01"
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
    if rule_id == "LX0609-10-02-01" and order_time is not None:
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
    if rule_id == "LX0609-10-02-02":
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
    evaluation_visibility_date: date | None = None,
) -> TransferDocumentationOutcome:
    """逐次关联转科记录；不同事件不能复用同一份文书。"""

    consumed: list[tuple[str, Mapping[str, Any]]] = []

    def outcome(state, reason, facts=None):
        return TransferDocumentationOutcome(state, reason, facts, tuple(consumed))

    source_error = nondrug_order_error or transfer_in_error or transfer_out_error
    if source_error:
        return outcome("data_gap", source_error)
    orders = select_transfer_order_rows(nondrug_order_rows)
    if not orders:
        return outcome("not_applicable", "trigger_absent_complete")
    consumed.extend(("inpat_nondrug_order", row) for row in orders)
    if rule_id == "LX0609-10-02-01":
        def visible(row):
            if evaluation_horizon_error or (evaluation_horizon_date is None and evaluation_horizon_datetime is None):
                return True
            clock = _precise_datetime(authoritative_document_time_value(row))
            if clock is None and not _clean(authoritative_document_time_value(row)):
                clock = _precise_datetime(row.get("transfer_date"))
            if clock is None:
                return True
            if evaluation_visibility_date is not None:
                # 终末病例的出院是观察终点，补写文书按既有任务冻结日判断可见性。
                return clock.date() <= evaluation_visibility_date
            return (clock <= evaluation_horizon_datetime if evaluation_horizon_datetime is not None
                    else clock.date() <= evaluation_horizon_date)

        transfer_in_rows = tuple(row for row in transfer_in_rows if visible(row))
        transfer_out_rows = tuple(row for row in transfer_out_rows if visible(row))
    if len(orders) != 1:
        times = [_unique_order_time(order) for order in orders]
        if any(conflict for _, conflict in times):
            return outcome("data_gap", "authoritative_time_conflict")
        if any(value is None for value, _ in times):
            return outcome("data_gap", "authoritative_time_missing")
        ordered = sorted(zip((value for value, _ in times), orders), key=lambda item: item[0])
        grouped = _group_transfer_orders(ordered, transfer_in_rows)
        if len(grouped) == 1:
            merged_outcome = evaluate_transfer_documentation(
                rule_id=rule_id, nondrug_order_error="", transfer_in_error="", transfer_out_error="",
                nondrug_order_rows=(grouped[0][1],), transfer_in_rows=transfer_in_rows,
                transfer_out_rows=transfer_out_rows, evaluation_horizon_date=evaluation_horizon_date,
                evaluation_horizon_datetime=evaluation_horizon_datetime,
                evaluation_horizon_error=evaluation_horizon_error,
                evaluation_visibility_date=evaluation_visibility_date,
            )
            consumed.extend(merged_outcome.consumed_rows)
            return outcome(merged_outcome.final_state, merged_outcome.reason_code, merged_outcome.display_facts)
        # 不同目标或有中间转入记录均保留多次转科；缺时间时不能任意拆分近邻事件。
        department_ownership = (
            all(_target_department(order) for _, order in grouped)
            and all(_precise_datetime(authoritative_document_time_value(row)) is not None
                    for row in (*transfer_in_rows, *transfer_out_rows))
            and all(sum(_departments_correspond(row, order) for _, order in grouped) == 1
                    for row in (*transfer_in_rows, *transfer_out_rows))
        )
        if len({value for value, _ in grouped}) == len(grouped) and (
            all(later[0] > earlier[0] + timedelta(hours=24)
                for earlier, later in zip(grouped, grouped[1:])) or department_ownership
        ):
            outcomes = []
            out_records_by_event: list[list[Mapping[str, Any]]] = [[] for _ in grouped]
            for row in transfer_out_rows:
                if department_ownership:
                    owner = next(index for index, (_start, order) in enumerate(grouped)
                                 if _departments_correspond(row, order))
                    out_records_by_event[owner].append(row)
                    continue
                moment = _precise_datetime(authoritative_document_time_value(row))
                if moment is None:
                    for selected_rows in out_records_by_event:
                        selected_rows.append(row)
                    continue
                normal = next((index for index in reversed(range(len(grouped)))
                               if _candidate_for_order(row, order_time=grouped[index][0]).state == "current"), None)
                early_indexes = [index for index, (start, order) in enumerate(grouped)
                                 if start - timedelta(hours=24) <= moment < start
                                 and _departments_correspond(row, order)]
                if len(early_indexes) > 1 or (early_indexes and normal is not None
                        and _departments_correspond(row, grouped[normal][1])):
                    return outcome("data_gap", "association_failed", {
                        "failure_kind": "transfer_event_association_gap", "transfer_order_count": len(orders),
                        "transfer_in_count": len(transfer_in_rows), "transfer_out_count": len(transfer_out_rows),
                    })
                owner = early_indexes[0] if early_indexes else normal
                if (
                    not early_indexes
                    and not any(_clean(row.get(field)) for field in ("transferin_department", "transferout_department"))
                    and (normal is None or moment > grouped[normal][0] + timedelta(hours=24))
                ):
                    row_transfer_date = _date_value(row.get("transfer_date"))
                    near_early_indexes = [
                        index
                        for index, (start, _order) in enumerate(grouped)
                        if start - _MULTI_EVENT_UNLABELLED_EARLY_OUT_TOLERANCE <= moment < start
                        and (row_transfer_date is None or row_transfer_date >= start.date())
                    ]
                    if len(near_early_indexes) == 1:
                        owner = near_early_indexes[0]
                if owner is None and grouped[0][0] - timedelta(hours=24) <= moment < grouped[0][0]:
                    owner = 0
                if owner is not None:
                    out_records_by_event[owner].append(row)
            for index, (start, order) in enumerate(grouped):
                end = grouped[index + 1][0] if index + 1 < len(grouped) else None

                def event_records(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
                    if department_ownership:
                        return tuple(row for row in rows if _departments_correspond(row, order))
                    selected = []
                    for row in rows:
                        candidate = _candidate_for_order(row, order_time=start)
                        if candidate.state == "time_unknown" or (
                            candidate.state == "current"
                            and (end is None or candidate.record_time < end)
                        ):
                            selected.append(row)
                    return tuple(selected)

                outcomes.append(evaluate_transfer_documentation(
                    rule_id=rule_id, nondrug_order_error="", transfer_in_error="", transfer_out_error="",
                    nondrug_order_rows=(order,),
                    transfer_in_rows=event_records(transfer_in_rows),
                    transfer_out_rows=tuple(out_records_by_event[index]),
                    evaluation_horizon_date=evaluation_horizon_date,
                    evaluation_horizon_datetime=evaluation_horizon_datetime,
                    evaluation_horizon_error=evaluation_horizon_error,
                    evaluation_visibility_date=evaluation_visibility_date,
                ))
            for event_outcome in outcomes:
                consumed.extend(event_outcome.consumed_rows)
            # 已明确的一次缺文书/超时足以证明不合规；其余事件仍逐项保留。
            priority = {"non_compliant": 0, "data_gap": 1, "not_applicable": 2, "compliant": 3}
            selected = min(outcomes, key=lambda outcome: priority[outcome.final_state])
            return outcome(
                selected.final_state, selected.reason_code,
                {**(selected.display_facts or {}), "transfer_order_count": len(orders),
                 "event_checks": [{"status": outcome.final_state, "reason_code": outcome.reason_code,
                                   **(outcome.display_facts or {})} for outcome in outcomes]},
            )
        consumed.extend(("transfer_in_record", row) for row in transfer_in_rows)
        consumed.extend(("transfer_out_record", row) for row in transfer_out_rows)
        return outcome(
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
        return outcome("data_gap", "authoritative_time_conflict")
    if order_time is None:
        return outcome("data_gap", "authoritative_time_missing")

    transfer_in_state, transfer_in_time, selected_in = _record_state(
        records=transfer_in_rows, order_time=order_time, order=orders[0]
    )
    transfer_out_state, transfer_out_time, selected_out = _record_state(
        records=transfer_out_rows, order_time=order_time, early_out_order=orders[0], order=orders[0]
    )
    consumed.extend(("transfer_in_record", row) for row in selected_in)
    consumed.extend(("transfer_out_record", row) for row in selected_out)
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
        return outcome("data_gap", "association_failed", facts)
    if "missing" in states or "historical" in states:
        if rule_id == "LX0609-10-02-01":
            window_mature, window_error = _transfer_window_state(
                order_time=order_time,
                evaluation_horizon_date=evaluation_horizon_date,
                evaluation_horizon_datetime=evaluation_horizon_datetime,
                evaluation_horizon_error=evaluation_horizon_error,
            )
            if window_error:
                return outcome("data_gap", window_error, facts)
            if not window_mature:
                return outcome(
                    "not_applicable", "evaluation_window_not_mature", facts
                )
        return outcome(
            "non_compliant", "required_document_missing", facts
        )
    if "time_unknown" in states:
        return outcome(
            "data_gap", "authoritative_time_missing", facts
        )
    if rule_id == "LX0609-10-02-01" and (
        evaluation_horizon_error or (evaluation_horizon_date is None and evaluation_horizon_datetime is None)
    ):
        return outcome("data_gap", evaluation_horizon_error or "authoritative_time_missing", facts)
    if rule_id == "LX0609-10-02-02":
        return outcome("compliant", "requirement_satisfied", facts)

    intervals = (
        (transfer_in_time - order_time).total_seconds() / 3600,
        (transfer_out_time - order_time).total_seconds() / 3600,
    )
    compliant = 0 <= intervals[0] <= 24 and -24 <= intervals[1] <= 24
    return outcome(
        "compliant" if compliant else "non_compliant",
        "requirement_within_threshold" if compliant else "threshold_exceeded",
        facts,
    )
