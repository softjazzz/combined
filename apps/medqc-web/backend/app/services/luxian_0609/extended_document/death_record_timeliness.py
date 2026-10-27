"""客户09659：死亡终末记录按权威完成时刻核对24小时期限。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping, Sequence

from ..source_evidence_reader import authoritative_document_time_value
from .rule_076 import death_time_from_body
from .shared import _parse_datetime

RULE_ID = "LX0609-04-02-09"


@dataclass(frozen=True)
class DeathRecordTimelinessOutcome:
    final_state: str
    reason_code: str
    display_facts: Mapping[str, Any] | None = None
    document_refs: tuple[Mapping[str, str], ...] = ()
    consumed_rows: tuple[tuple[str, Mapping[str, Any]], ...] = ()


def _terminal_kind(row: Mapping[str, Any]) -> str:
    title = re.sub(r"\s+", "", str(row.get("document_title") or ""))
    if row.get("validation_material_state") in {"held", "version_review"}:
        return ""
    if not str(row.get("record_content") or row.get("treatment_course") or "").strip():
        return ""
    if title == "死亡记录":
        return "death"
    if title in {"出院记录", "出院小结"}:
        return "discharge"
    return ""


def _clock(value: Any) -> datetime | None:
    # datetime.fromisoformat会把纯日期解释成零点；本规则不能伪造这种精度。
    if not isinstance(value, datetime) and not re.match(
        r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", str(value or "").strip()
    ):
        return None
    return _parse_datetime(value)


def evaluate_death_record_timeliness(
    *, death_rows: Sequence[Mapping[str, Any]],
    discharge_rows: Sequence[Mapping[str, Any]] = (),
    registration_rows: Sequence[Mapping[str, Any]] = (), source_error: str = "",
    frozen_at: Any = None,
) -> DeathRecordTimelinessOutcome:
    """只裁定本次冻结材料，不读取数据库或机器时间，不调用模型。"""
    if source_error:
        return DeathRecordTimelinessOutcome("data_gap", source_error)
    if frozen_at is not None:
        boundary = _clock(frozen_at)
        if boundary is None:
            return DeathRecordTimelinessOutcome("data_gap", "authoritative_time_missing")
        # 先固定可见范围，再识别终末类型、死亡锚点及最后版本；未知时间不能当未来排除。
        death_rows, discharge_rows = tuple(
            tuple(row for row in rows
                  if (clock := _clock(authoritative_document_time_value(row))) is None
                  or clock <= boundary)
            for rows in (death_rows, discharge_rows)
        )
    records = tuple(
        (source, row)
        for source, rows in (("death_record", death_rows), ("discharge_record", discharge_rows))
        for row in rows if _terminal_kind(row) == "death"
    )
    ordinary = any(_terminal_kind(row) == "discharge" for row in (*death_rows, *discharge_rows))
    if records and ordinary:
        return DeathRecordTimelinessOutcome("data_gap", "authoritative_time_conflict")
    if not records:
        if ordinary:
            return DeathRecordTimelinessOutcome("not_applicable", "trigger_absent_complete")
        return DeathRecordTimelinessOutcome("data_gap", "source_empty")
    # 在精度丢失前核原值；旧死亡上下文会将纯日期解析成午夜，不能用于本规则。
    raw_death_times = [
        value for row in (*[row for _, row in records], *registration_rows)
        if (value := row.get("death_datetime") or row.get("death_time")) is not None
        and str(value).strip()
    ]
    if not raw_death_times:
        raw_death_times = [
            value for _, row in records if (value := death_time_from_body(row))
        ]
    clocks = tuple(_clock(value) for value in raw_death_times)
    if not clocks or any(clock is None for clock in clocks):
        return DeathRecordTimelinessOutcome("data_gap", "authoritative_time_missing")
    if len(set(clocks)) != 1:
        return DeathRecordTimelinessOutcome("data_gap", "authoritative_time_conflict")
    death_clock = clocks[0]
    timed = tuple((_clock(authoritative_document_time_value(row)), source, row) for source, row in records)
    if any(clock is None for clock, _, _ in timed):
        return DeathRecordTimelinessOutcome("data_gap", "authoritative_time_missing")
    # 与既有出院记录一致取最后权威时间，同一时刻以文书ID固定顺序。
    completed, source, selected = max(
        timed, key=lambda item: (item[0], str(item[2].get("document_id") or ""), item[1])
    )
    seconds = (completed - death_clock).total_seconds()
    if seconds < 0:
        return DeathRecordTimelinessOutcome("data_gap", "authoritative_time_conflict")
    document_id = str(selected.get("document_id") or "").strip()
    if not document_id:
        return DeathRecordTimelinessOutcome("data_gap", "required_field_missing")
    # 公共定位只有来源及文书ID；同来源同ID的不同内容不能冒充可精确定位的版本。
    source_rows = death_rows if source == "death_record" else discharge_rows
    if any(str(row.get("document_id") or "").strip() == document_id and dict(row) != dict(selected)
           for row in source_rows):
        return DeathRecordTimelinessOutcome("data_gap", "authoritative_time_conflict")
    return DeathRecordTimelinessOutcome(
        "compliant" if seconds <= 86400 else "non_compliant",
        "requirement_within_threshold" if seconds <= 86400 else "threshold_exceeded",
        {"verification_kind": "death_record_timeliness_check",
         "death_time": death_clock.isoformat(sep=" "), "record_time": completed.isoformat(sep=" "),
         "threshold_hours": 24, "elapsed_seconds": seconds},
        ({"source_type": source, "source_document_id": document_id},),
        ((source, selected),),
    )
