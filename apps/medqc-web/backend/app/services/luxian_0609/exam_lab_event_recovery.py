"""检查检验事实抽取的事件级受控恢复。

仅在共享多事件抽取发生可归属的跨事件病程引用时使用。恢复调用一次只看到
一个目标事件及其 Python 白名单内病程；Python 仍严格校验引用，任何事件失败
都会使该规则保持模型执行失败，不生成临床结论。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Awaitable, Callable, Mapping, Sequence

from .llm_prompt_privacy import luxian_0609_llm_call_failure_reason
from .exam_lab_fact_extraction import (
    CULTURE_RULE_IDS,
    EXAM_RULE_IDS,
    ExamLabEventFact,
    ExamLabTextProjection,
    _course_refs_for_rule_event,
    events_for_family,
    parse_exam_lab_fact_response_isolated,
)


_EVENT_HEADER = re.compile(
    r"^\[(?:EVENT_DOC|CANDIDATE_DOC)=([^|\]]+)\|FAMILY=(?:exam|culture)\|"
    r"EVENT_POSITION=\d+\|"
)
_COURSE_HEADER = re.compile(
    r"^\[COURSE_DOC_POSITION=(\d+)\|COURSE_DOC=([^|\]]+)\|"
)


@dataclass(frozen=True)
class ExamLabEventRecoveryResult:
    facts: tuple[ExamLabEventFact, ...]
    responses: tuple[Mapping[str, Any], ...]
    attempted_call_count: int
    failure_kind: str | None = None

    @property
    def call_count(self) -> int:
        return self.attempted_call_count


def _family_for_rule(rule_id: str) -> str:
    if rule_id in EXAM_RULE_IDS:
        return "exam"
    if rule_id in CULTURE_RULE_IDS:
        return "culture"
    raise ValueError("unsupported exam lab recovery rule")


def _event_projection(
    projection: ExamLabTextProjection,
    *,
    rule_id: str,
    event_position: int,
) -> ExamLabTextProjection:
    """生成只含一个事件及其合法病程的投影，并重新编号位置。"""

    family = _family_for_rule(rule_id)
    events = events_for_family(projection, family)
    if event_position < 1 or event_position > len(events):
        raise ValueError("exam lab recovery event out of range")
    event = events[event_position - 1]
    event_refs = frozenset(event.document_refs)
    course_refs = tuple(_course_refs_for_rule_event(
        projection,
        rule_id=rule_id,
        event_position=event_position,
    ))
    course_ref_set = frozenset(course_refs)
    course_position_by_ref = {
        ref: position for position, ref in enumerate(sorted(course_refs), start=1)
    }

    context_lines: list[str] = []
    for line in projection.context.splitlines():
        event_match = _EVENT_HEADER.match(line)
        if event_match is not None:
            if event_match.group(1) in event_refs:
                context_lines.append(re.sub(
                    r"\|EVENT_POSITION=\d+\|",
                    "|EVENT_POSITION=1|",
                    line,
                    count=1,
                ))
            continue
        course_match = _COURSE_HEADER.match(line)
        if course_match is not None:
            course_ref = course_match.group(2)
            if course_ref in course_ref_set:
                context_lines.append(re.sub(
                    r"^\[COURSE_DOC_POSITION=\d+\|",
                    f"[COURSE_DOC_POSITION={course_position_by_ref[course_ref]}|",
                    line,
                    count=1,
                ))
            continue
        context_lines.append(line)

    permitted_refs = event_refs | course_ref_set
    safe_refs = projection.safe_refs or {}
    source_document_refs = projection.source_document_refs or {}
    course_texts = projection.course_texts or {}
    return ExamLabTextProjection(
        context="\n".join(context_lines),
        document_refs=permitted_refs,
        course_times={
            ref: projection.course_times[ref]
            for ref in course_refs
            if ref in projection.course_times
        },
        imaging_event=event if family == "exam" else None,
        culture_event=event if family == "culture" else None,
        imaging_events=(event,) if family == "exam" else (),
        culture_events=(event,) if family == "culture" else (),
        event_course_refs={(family, 1): course_refs},
        safe_refs={ref: safe_refs[ref] for ref in permitted_refs if ref in safe_refs},
        precise_horizon=projection.precise_horizon,
        horizon_date=projection.horizon_date,
        horizon_conflict=projection.horizon_conflict,
        horizon_unavailable_reason=projection.horizon_unavailable_reason,
        course_time_incomplete=projection.course_time_incomplete,
        course_projection_truncated=projection.course_projection_truncated,
        course_scope_complete=projection.course_scope_complete,
        course_texts={
            ref: course_texts[ref] for ref in course_refs if ref in course_texts
        },
        source_document_refs={
            ref: source_document_refs[ref]
            for ref in permitted_refs
            if ref in source_document_refs
        },
        course_record_times=(
            None
            if projection.course_record_times is None
            else {
                ref: projection.course_record_times[ref]
                for ref in course_refs
                if ref in projection.course_record_times
            }
        ),
        course_submit_times=(
            None
            if projection.course_submit_times is None
            else {
                ref: projection.course_submit_times[ref]
                for ref in course_refs
                if ref in projection.course_submit_times
            }
        ),
        course_candidates=projection.course_candidates,
    )


async def recover_exam_lab_rule_by_event(
    *,
    rule_id: str,
    projection: ExamLabTextProjection,
    generate_response: Callable[
        [Sequence[str], ExamLabTextProjection], Awaitable[Mapping[str, Any]]
    ],
    strict_parser: Callable[..., tuple[ExamLabEventFact, ...]],
) -> ExamLabEventRecoveryResult:
    """逐事件做一次恢复调用；不对任何事件重复重试。"""

    family = _family_for_rule(rule_id)
    events = events_for_family(projection, family)
    if len(events) <= 1:
        raise ValueError("event recovery requires multiple events")

    facts: list[ExamLabEventFact] = []
    responses: list[Mapping[str, Any]] = []
    attempted_call_count = 0
    for original_position in range(1, len(events) + 1):
        event_projection = _event_projection(
            projection,
            rule_id=rule_id,
            event_position=original_position,
        )
        try:
            attempted_call_count += 1
            response = await generate_response((rule_id,), event_projection)
            responses.append(response)
            partition = parse_exam_lab_fact_response_isolated(
                response=response,
                selected_rule_ids=(rule_id,),
                projection=event_projection,
                _strict_parser=strict_parser,
            )
        except Exception as exc:  # noqa: BLE001
            return ExamLabEventRecoveryResult(
                facts=(),
                responses=tuple(responses),
                attempted_call_count=attempted_call_count,
                failure_kind=luxian_0609_llm_call_failure_reason(
                    exc, fallback=getattr(exc, "failure_kind", "value")
                ),
            )
        if partition.rule_failures or len(partition.facts) != 1:
            return ExamLabEventRecoveryResult(
                facts=(),
                responses=tuple(responses),
                attempted_call_count=attempted_call_count,
                failure_kind=(
                    partition.rule_failures.get(rule_id, "value")
                    if partition.rule_failures
                    else "value"
                ),
            )
        facts.append(replace(partition.facts[0], event_position=original_position))

    return ExamLabEventRecoveryResult(
        facts=tuple(facts),
        responses=tuple(responses),
        attempted_call_count=attempted_call_count,
    )
