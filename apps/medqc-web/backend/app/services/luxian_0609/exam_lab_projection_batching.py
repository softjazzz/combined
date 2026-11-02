"""并集超限时按完整事件窗口分批；全局投影只供程序归并，不发送给模型。"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Mapping, Sequence

from .exam_lab_fact_extraction import (
    ExamLabTextProjection,
    build_exam_lab_text_projection,
    events_for_family,
)


@dataclass(frozen=True)
class ExamLabProjectionBatch:
    projection: ExamLabTextProjection
    # (族, 批内事件位置) -> 全局事件位置；文书引用直接沿用全局引用。
    event_positions: Mapping[tuple[str, int], int]


@dataclass(frozen=True)
class ExamLabProjectionPlan:
    projection: ExamLabTextProjection
    batches: tuple[ExamLabProjectionBatch, ...]


def select_exam_lab_projection_batch(
    projection: ExamLabTextProjection,
    event_keys: Sequence[tuple[str, int]],
) -> ExamLabProjectionBatch:
    """只重排位置，不改变任一事件的病程白名单或正文。"""

    positions: dict[tuple[str, int], int] = {}
    local_by_global: dict[tuple[str, int], int] = {}
    selected = {family: [] for family in ("exam", "culture")}
    course_refs: set[str] = set()
    event_refs: set[str] = set()
    event_course_refs: dict[tuple[str, int], tuple[str, ...]] = {}
    for family, global_position in event_keys:
        event = events_for_family(projection, family)[global_position - 1]
        selected[family].append(event)
        local = len(selected[family])
        positions[(family, local)] = global_position
        local_by_global[(family, global_position)] = local
        refs = (projection.event_course_refs or {})[(family, global_position)]
        event_course_refs[(family, local)] = refs
        course_refs.update(refs)
        event_refs.update(event.document_refs)
    course_positions = {ref: i for i, ref in enumerate(sorted(course_refs), start=1)}
    lines = []
    for line in projection.context.splitlines():
        event_match = re.match(
            r"^\[(?:EVENT_DOC|CANDIDATE_DOC)=([^|]+)\|FAMILY=(exam|culture)\|EVENT_POSITION=(\d+)\|",
            line,
        )
        if event_match:
            ref, family, position = event_match.groups()
            if ref in event_refs:
                local = local_by_global[(family, int(position))]
                lines.append(
                    re.sub(
                        r"\|EVENT_POSITION=\d+\|",
                        f"|EVENT_POSITION={local}|",
                        line,
                        count=1,
                    )
                )
            continue
        course_match = re.match(
            r"^\[COURSE_DOC_POSITION=\d+\|COURSE_DOC=([^|]+)\|", line
        )
        if course_match and course_match[1] in course_refs:
            local = course_positions[course_match[1]]
            lines.append(
                re.sub(
                    r"^\[COURSE_DOC_POSITION=\d+\|",
                    f"[COURSE_DOC_POSITION={local}|",
                    line,
                    count=1,
                )
            )
    refs = course_refs | event_refs

    def subset(values):
        return (
            None
            if values is None
            else {ref: value for ref, value in values.items() if ref in refs}
        )

    return ExamLabProjectionBatch(
        projection=replace(
            projection,
            context="\n".join(lines),
            document_refs=frozenset(refs),
            course_times=subset(projection.course_times),
            imaging_event=selected["exam"][0] if len(selected["exam"]) == 1 else None,
            culture_event=selected["culture"][0]
            if len(selected["culture"]) == 1
            else None,
            imaging_events=tuple(selected["exam"]),
            culture_events=tuple(selected["culture"]),
            comparison_events=(projection.comparison_events if projection.comparison_events is not None
                               else events_for_family(projection, 'exam')),
            event_course_refs=event_course_refs,
            safe_refs=subset(projection.safe_refs),
            course_texts=subset(projection.course_texts),
            source_document_refs=subset(projection.source_document_refs),
            course_record_times=subset(projection.course_record_times),
            course_submit_times=subset(projection.course_submit_times),
        ),
        event_positions=positions,
    )


def build_exam_lab_projection_batches(
    *,
    rows_by_source: Mapping[str, Sequence[Mapping[str, Any]]],
    horizon_unavailable_reason: str | None = None,
    max_course_rows: int = 32,
    max_context_chars: int = 32000,
) -> ExamLabProjectionPlan:
    """在未裁剪的全局投影上贪心装入完整事件，单事件超限仍失败关闭。"""

    projection = build_exam_lab_text_projection(
        rows_by_source=rows_by_source,
        horizon_unavailable_reason=horizon_unavailable_reason,
        max_course_rows=None,
        max_row_chars=None,
        max_context_chars=None,
    )
    batches: list[ExamLabProjectionBatch] = []
    pending: list[tuple[str, int]] = []

    def fits(batch: ExamLabProjectionBatch) -> bool:
        return (
            len(batch.projection.course_times) <= max_course_rows
            and len(batch.projection.context) <= max_context_chars
        )

    for family in ("exam", "culture"):
        for position in range(1, len(events_for_family(projection, family)) + 1):
            key = (family, position)
            candidate = select_exam_lab_projection_batch(projection, (*pending, key))
            if not fits(candidate):
                if pending:
                    batches.append(
                        select_exam_lab_projection_batch(projection, pending)
                    )
                pending = []
                if not fits(select_exam_lab_projection_batch(projection, (key,))):
                    raise ValueError("exam lab text projection truncated")
            pending.append(key)
    if pending:
        batches.append(select_exam_lab_projection_batch(projection, pending))
    return ExamLabProjectionPlan(projection, tuple(batches))
