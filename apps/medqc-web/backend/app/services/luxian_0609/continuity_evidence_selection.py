"""连续性与会诊规则已消费文书的精确证据坐标绑定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .extended_document.shared import _parse_datetime
from .source_evidence_reader import authoritative_document_time_value


@dataclass(frozen=True)
class ContinuityEvidenceBinding:
    """已消费文书的绑定结果；失败由调用方关闭为技术异常。"""

    document_refs: tuple[str, ...]
    binding_failed: bool = False


def bind_consumed_continuity_document_rows(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    consumed_rows: Sequence[tuple[str, Mapping[str, Any]]],
) -> ContinuityEvidenceBinding:
    """按显式来源唯一绑定执行器已经消费的文书行。

    本函数不判断任何业务状态，也不选择候选文书。调用方必须同时提供来源和已经
    消费的原始行；缺失来源、来源不可用、或同一来源中不能唯一回定位时均失败关闭。
    """

    refs: list[str] = []
    for source_key, consumed_row in consumed_rows:
        if not isinstance(source_key, str) or not source_key or not isinstance(
            consumed_row, Mapping
        ):
            return ContinuityEvidenceBinding((), binding_failed=True)
        try:
            matches = tuple(
                document_ref
                for document_ref, material_row in materials.document_rows(
                    source_key, snapshot=snapshot
                )
                if material_row == consumed_row
            )
        except (
            EvidenceMaterialUnavailable,
            EvidenceMaterialTruncated,
            TypeError,
            ValueError,
        ):
            return ContinuityEvidenceBinding((), binding_failed=True)
        if len(matches) != 1:
            return ContinuityEvidenceBinding((), binding_failed=True)
        refs.append(matches[0])
    return ContinuityEvidenceBinding(tuple(dict.fromkeys(refs)))


def bind_consultation_evidence(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    consultation_rows: Sequence[Mapping[str, Any]],
    display_facts: Mapping[str, Any] | None,
) -> ContinuityEvidenceBinding:
    """按既有会诊判定器交付的申请/记录时间回定位直接配对文书。"""

    if not isinstance(display_facts, Mapping):
        return ContinuityEvidenceBinding(())
    request_times = {
        value for value in display_facts.get("request_times", ()) if isinstance(value, str)
    }
    record_times = {
        value for value in display_facts.get("record_times", ()) if isinstance(value, str)
    }
    consumed = []
    for row in consultation_rows:
        request_time = _row_time(
            row,
            (
                "consult_apply_time", "request_time", "request_datetime",
                "application_time", "application_datetime", "record_time",
            ),
        )
        record_time = _row_time(
            row,
            (
                "consultation_time", "consultation_datetime", "completion_time",
                "completion_datetime", "record_time",
            ),
        )
        if (
            request_time is not None and request_time.isoformat(sep=" ") in request_times
        ) or (
            record_time is not None and record_time.isoformat(sep=" ") in record_times
        ):
            consumed.append(("consultation_record", row))
    return bind_consumed_continuity_document_rows(
        snapshot=snapshot, materials=materials, consumed_rows=consumed
    )


def bind_handoff_evidence(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    handoff_rows: Sequence[Mapping[str, Any]],
    handover_rows: Sequence[Mapping[str, Any]],
    display_facts: Mapping[str, Any] | None,
) -> ContinuityEvidenceBinding:
    """按每次医师变更冻结事实回定位实际交班、接班文书。"""

    if not isinstance(display_facts, Mapping):
        return ContinuityEvidenceBinding(())
    events = display_facts.get("events", ())
    handoff_times = set(display_facts.get("handoff_times", ()))
    handover_times = set(display_facts.get("handover_times", ()))
    if isinstance(events, Sequence):
        handoff_times.update(
            item.get("handoff_time")
            for item in events
            if isinstance(item, Mapping) and item.get("handoff_time")
        )
        handover_times.update(
            item.get("handover_time")
            for item in events
            if isinstance(item, Mapping) and item.get("handover_time")
        )
    selected_handoff = [
        row for row in handoff_rows
        if (value := _row_time(row, ("handoff_time", "record_time"))) is not None
        and value.isoformat(sep=" ") in handoff_times
    ]
    selected_handover = [
        row for row in handover_rows
        if (value := _row_time(row, ("handover_time", "record_time"))) is not None
        and value.isoformat(sep=" ") in handover_times
    ]
    consumed: list[tuple[str, Mapping[str, Any]]] = []
    if isinstance(events, Sequence) and events:
        for event in events:
            if not isinstance(event, Mapping):
                continue
            consumed.extend(
                ("handoff_record", row) for row in selected_handoff
                if (value := _row_time(row, ("handoff_time", "record_time"))) is not None
                and value.isoformat(sep=" ") == event.get("handoff_time")
            )
            consumed.extend(
                ("handover_record", row) for row in selected_handover
                if (value := _row_time(row, ("handover_time", "record_time"))) is not None
                and value.isoformat(sep=" ") == event.get("handover_time")
            )
    else:
        consumed = [
            *(("handoff_record", row) for row in selected_handoff),
            *(("handover_record", row) for row in selected_handover),
        ]
    return bind_consumed_continuity_document_rows(
        snapshot=snapshot, materials=materials, consumed_rows=consumed
    )


def bind_transfer_evidence(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    nondrug_order_rows: Sequence[Mapping[str, Any]],
    transfer_in_rows: Sequence[Mapping[str, Any]],
    transfer_out_rows: Sequence[Mapping[str, Any]],
    display_facts: Mapping[str, Any] | None,
) -> ContinuityEvidenceBinding:
    """绑定唯一转科医嘱及既有判定器实际匹配的转入、转出文书。"""

    orders = tuple(
        row for row in nondrug_order_rows
        if "转科" in _clean(row.get("order_name") or row.get("record_content"))
        and not any(marker in _clean(row.get("order_status")) for marker in ("取消", "作废", "撤销"))
    )
    if len(orders) != 1:
        return ContinuityEvidenceBinding(())
    consumed: list[tuple[str, Mapping[str, Any]]] = [("inpat_nondrug_order", orders[0])]
    if isinstance(display_facts, Mapping):
        for source_key, rows, fact_key in (
            ("transfer_in_record", transfer_in_rows, "transfer_in_time"),
            ("transfer_out_record", transfer_out_rows, "transfer_out_time"),
        ):
            expected_time = display_facts.get(fact_key)
            if not isinstance(expected_time, str):
                continue
            consumed.extend(
                (source_key, row)
                for row in rows
                if (value := _parse_datetime(authoritative_document_time_value(row)))
                is not None and value.isoformat(sep=" ") == expected_time
            )
    return bind_consumed_continuity_document_rows(
        snapshot=snapshot, materials=materials, consumed_rows=consumed
    )


def bind_diagnosis_change_evidence(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    change_events: Sequence[tuple[datetime, str, Mapping[str, Any]]],
    candidate_rows: Sequence[tuple[datetime | None, str, str, Mapping[str, Any]]],
    matching_course_indexes: Sequence[Sequence[int]] = (),
    uniquely_matched: bool = False,
) -> ContinuityEvidenceBinding:
    """绑定实际发生变化的诊断行及已匹配的理由/依据病程。"""

    if len(change_events) == 1:
        change_time, diagnosis_name, diagnosis_row = change_events[0]
        consumed = [("diagnosis", diagnosis_row)]
        consumed.extend(
            (source_key, row)
            for record_time, text, source_key, row in candidate_rows
            if diagnosis_name in text
            and (record_time is None or record_time >= change_time)
        )
    elif len(change_events) > 1 and uniquely_matched:
        consumed = [
            ("diagnosis", row)
            for _change_time, _diagnosis_name, row in change_events
        ]
        consumed.extend(
            candidate_rows[indexes[0]][2:]
            for indexes in matching_course_indexes
        )
    else:
        consumed = []
    return bind_consumed_continuity_document_rows(
        snapshot=snapshot, materials=materials, consumed_rows=consumed
    )


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _row_time(row: Mapping[str, Any], fields: Sequence[str]) -> datetime | None:
    for field in fields:
        if (parsed := _parse_datetime(row.get(field))) is not None:
            return parsed
    return None


__all__ = [
    "ContinuityEvidenceBinding",
    "bind_consultation_evidence",
    "bind_consumed_continuity_document_rows",
    "bind_diagnosis_change_evidence",
    "bind_handoff_evidence",
    "bind_transfer_evidence",
]
