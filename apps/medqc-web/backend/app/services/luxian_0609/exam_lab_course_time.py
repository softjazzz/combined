"""CT/MRI 与培养报告后病程的时间来源判定（纯函数，不读库、不调模型）。

职责边界：只回答“某份病程相对报告时间能否证明在 24 小时内/之外”。
- 记录时间（record_time/record_datetime）是文书自身声明的书写时间；
- 提交时间（submit_time/submit_datetime）是文书入库提交时间，只可作为书写时间的上界，
  不得直接认定为临床记录时间，也不设置任何时间容差；
- 记录时间早于报告时间、提交时间不早于报告时间、正文确有该事件结果的文书，
  是时间冲突，既不能计入响应，也不能静默丢弃后声称未记录。
提交时间作上界的适用前提（缺一不可）：
1. 该文书没有记录时间；
2. 报告时间 ≤ 提交时间 ≤ 报告后 24 小时；
3. 正文已被确认承载本事件的结果（整段逐字复述，或事件身份文本可核验的提及）。
提交时间落在 24 小时内本身不证明已及时记录：前提 3 不满足时只能是资料不足。
整段逐字匹配只用于“确认时间冲突/确认承载结果”；匹配不到不得据此认定未记录。

状态映射仍由 ``native_exam_lab_execution`` 负责，本模块不判定规则状态。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Any, Callable, Sequence

WINDOW = timedelta(hours=24)

# 同一事件结果文本的最小可核验长度（整段逐字复述）。复查报告常与既往报告共用
# 单句（如“主动脉壁钙化”），逐句匹配会把前次检查的复述误认作本次结果，
# 因此只接受整段结果文本；过短的结果无法唯一确认归属，不据此认定。
# 这是文本一致性判据，不是时间容差。
_MIN_RESULT_CHARS = 10


def _normalize(value: Any) -> str:
    return re.sub(r"[\s，,。；;：:、]+", "", str(value or ""))


def course_restates_event_result(result_texts: Sequence[str], course_text: str) -> bool:
    """病程正文是否逐字包含该事件的某一整段报告结果文本。"""

    text = _normalize(course_text)
    if not text:
        return False
    return any(
        len(whole) >= _MIN_RESULT_CHARS and whole in text
        for whole in (_normalize(raw) for raw in result_texts)
    )


# 每个事件最多额外开放的“记录时间早于报告、提交时间不早于报告”候选病程数。
# 取提交时间最接近报告者，避免补交滞后很常见的病程把模型上下文撑爆。
MAX_TIME_CONFLICT_CANDIDATES = 4


def is_time_conflict_candidate(
    record: datetime | None, submit: datetime | None, report_time: datetime
) -> bool:
    return (
        record is not None
        and submit is not None
        and record < report_time
        and submit >= report_time
    )


def limit_conflict_candidates(
    candidates: Sequence[tuple[str, datetime]],
) -> tuple[str, ...]:
    """candidates: (引用, 提交时间)。按提交时间升序取前 N 个，稳定且确定。"""

    ordered = sorted(candidates, key=lambda item: (item[1], item[0]))
    return tuple(ref for ref, _ in ordered[:MAX_TIME_CONFLICT_CANDIDATES])


@dataclass(frozen=True)
class CourseResponse:
    ref: str
    basis: str  # record | submit | none
    effective: datetime | None
    kind: str  # in_window | late | before | conflict | unknown
    interval: timedelta | None


def has_time_sources(projection: Any) -> bool:
    """旧式手工构造的投影没有记录/提交时间拆分，按旧语义处理。"""

    return (
        getattr(projection, "course_record_times", None) is not None
        and getattr(projection, "course_submit_times", None) is not None
    )


def assess_course_response(
    *,
    ref: str,
    projection: Any,
    report_time: datetime,
    result_texts: Sequence[str],
    course_text: str | None = None,
    carries_result: Callable[[str], bool] | None = None,
) -> CourseResponse:
    """kind：in_window | late | before | conflict | unreconciled | submit_unconfirmed | unknown。

    - conflict：记录时间早于报告、提交时间不早于报告，且正文整段逐字含本事件结果（已确认）；
    - unreconciled：同样的时间关系但未能逐字确认，只是无法对账，不能据此认定未记录；
    - submit_unconfirmed：仅有提交时间且在 24 小时内，但正文未确认承载本事件结果，
      不能自动证明已及时记录。
    """

    effective = projection.course_times.get(ref)
    if not has_time_sources(projection):
        if effective is None:
            return CourseResponse(ref, "none", None, "unknown", None)
        interval = effective - report_time
        kind = "before" if interval < timedelta(0) else "in_window" if interval <= WINDOW else "late"
        return CourseResponse(ref, "record", effective, kind, interval)
    record = projection.course_record_times.get(ref)
    submit = projection.course_submit_times.get(ref)
    text = course_text if course_text is not None else (projection.course_texts or {}).get(ref, "")
    if record is not None:
        interval = record - report_time
        if interval >= timedelta(0):
            kind = "in_window" if interval <= WINDOW else "late"
            return CourseResponse(ref, "record", record, kind, interval)
        if is_time_conflict_candidate(record, submit, report_time):
            kind = (
                "conflict"
                if course_restates_event_result(result_texts, text)
                else "unreconciled"
            )
            return CourseResponse(ref, "record", record, kind, interval)
        return CourseResponse(ref, "record", record, "before", interval)
    if submit is not None:
        interval = submit - report_time
        if interval < timedelta(0):
            return CourseResponse(ref, "submit", submit, "before", interval)
        if interval > WINDOW:
            return CourseResponse(ref, "submit", submit, "late", interval)
        carries = course_restates_event_result(result_texts, text) or bool(
            carries_result is not None and carries_result(text)
        )
        return CourseResponse(
            ref, "submit", submit, "in_window" if carries else "submit_unconfirmed", interval
        )
    return CourseResponse(ref, "none", None, "unknown", None)


def assess_fact_responses(
    *,
    projection: Any,
    event: Any,
    refs: Sequence[str],
    carries_result: Callable[[Any, str], bool] | None = None,
) -> tuple[CourseResponse, ...]:
    if event is None or event.report_time is None:
        return ()
    return tuple(
        assess_course_response(
            ref=ref,
            projection=projection,
            report_time=event.report_time,
            result_texts=event.result_texts,
            carries_result=(
                (lambda text: carries_result(event, text)) if carries_result else None
            ),
        )
        for ref in refs
    )


def scan_unplaced_time_state(*, projection: Any, event: Any) -> str | None:
    """在“未记录/仅报告前病程”结论前，检查全部候选病程正文。

    被时间筛选排除的文书不能当作“全部病程均无记录”的依据：
    - ``record_time_conflict``：存在记录时间早于报告、提交时间不早于报告且正文含该结果的文书；
    - ``submit_only``：存在无记录时间、正文含该结果，但提交时间不能证明其在窗口内的文书。
    """

    candidates = getattr(projection, "course_candidates", None)
    if (
        candidates is None
        or event is None
        or event.report_time is None
        or not event.result_texts
    ):
        return None
    state: str | None = None
    for ref, (text, record, submit) in candidates.items():
        if not course_restates_event_result(event.result_texts, text):
            continue
        if record is not None:
            if record < event.report_time and submit is not None and submit >= event.report_time:
                return "record_time_conflict"
            continue
        if submit is None or not (
            timedelta(0) <= submit - event.report_time <= WINDOW
        ):
            state = state or "submit_only"
    return state
