"""LX0916-018 危急值报告及处置原子事实提取。

Stage 1 已用共享 Bundle 的 PL/PH 检验原始行确认危急值事件。本模块只把已确认
事件的报告信息和事件后正式病程分句投影给一次受控模型调用，模型只能返回
``report_recorded`` 与 ``disposition_recorded`` 两个原子事实及坐标。最终规则
状态仍由 Python 执行器形成。
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .critical_value_018 import RULE_ID


FORMAL_COURSE_SOURCES = (
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "postsurg_firstcourse_record",
    "rescue_record",
)
FACT_KINDS = ("report_recorded", "disposition_recorded")
_FACT_FIELDS = frozenset(
    {"fact_kind", "state", "event_id", "source_type", "document_id", "clause_id"}
)
_FACT_STATES = frozenset({"present", "absent", "unknown"})
_EVENT_RESPONSE_FIELDS = frozenset({"event_id", "facts"})
_MAX_TOTAL_CHARS = 20_000
_MAX_CLAUSES = 256
_MAX_EVENTS = 20
_MAX_COMPLETION_TOKENS = 2_048
_CLAUSE_BOUNDARY = re.compile(r"(?<=[。！？!?；;\n])")
_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_FIRST_COURSE_SECTION_LABELS = (
    ("case_characteristic", "病例特点"),
    ("diagnose_based_on", "诊断依据"),
    ("differential_diagnosis", "鉴别诊断"),
    ("treatment_plan", "诊疗计划"),
)

Generate = Callable[..., Awaitable[dict[str, Any]]]
Coordinate = tuple[str, str, str]


@dataclass(frozen=True)
class _Clause:
    source_type: str
    document_id: str
    authored_at: datetime
    authored_at_text: str
    clause_id: str
    text: str

    @property
    def coordinate(self) -> Coordinate:
        return self.source_type, self.document_id, self.clause_id


@dataclass(frozen=True)
class _EventInput:
    index: int
    event_id: str
    prompt_event: Mapping[str, Any]
    allowed_coordinates: frozenset[Coordinate]


@dataclass(frozen=True)
class _Outcome:
    state: str
    facts: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    incomplete: bool = False


async def extract_critical_value_018_stage2_facts(
    *,
    evidence_payload: Mapping[str, Any],
    structured_facts: Mapping[str, Any],
    scene: str,
    generate: Generate,
    model_parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """补充每个已确认危急值事件的两个受控病程事实。"""

    resolved_parameters = _model_parameters(generate, model_parameters)
    try:
        return await _extract(
            evidence_payload=evidence_payload,
            structured_facts=structured_facts,
            scene=scene,
            generate=generate,
            model_parameters=resolved_parameters,
        )
    except Exception:  # noqa: BLE001 - 单病例 Stage2 异常不得扩散到批次。
        return _internal_failure_output(
            structured_facts,
            scene=scene,
            model_parameters=resolved_parameters,
        )


async def _extract(
    *,
    evidence_payload: Mapping[str, Any],
    structured_facts: Mapping[str, Any],
    scene: str,
    generate: Generate,
    model_parameters: Mapping[str, Any],
) -> dict[str, Any]:
    output, events = _copy_structured_facts(structured_facts)
    indices = [
        index
        for index, event in enumerate(events)
        if event.get("trigger_confirmed") is True
    ]
    for index in indices:
        events[index]["evaluation_window_mature"] = scene == "final"

    stage1_gap = _stage1_gap_state(structured_facts)
    if stage1_gap is not None:
        return _gap_output(
            output=output,
            events=events,
            indices=indices,
            state=stage1_gap,
            code="critical_value_018_stage2_source_gap",
            model_parameters=model_parameters,
        )
    if not indices:
        output["diagnostic"] = _diagnostic(
            code="critical_value_018_stage2_no_trigger",
            event_count=0,
            model_parameters=model_parameters,
        )
        return output
    if len(indices) > _MAX_EVENTS:
        return _gap_output(
            output=output,
            events=events,
            indices=indices,
            state="window_unavailable",
            code="critical_value_018_stage2_budget_gap",
            model_parameters=model_parameters,
        )

    event_state, earliest = _event_gate(events=events, indices=indices)
    if event_state != "ready" or earliest is None:
        return _gap_output(
            output=output,
            events=events,
            indices=indices,
            state=event_state,
            code="critical_value_018_stage2_event_gap",
            model_parameters=model_parameters,
        )

    source_state, clauses = _build_clause_catalog(
        evidence_payload,
        not_before=earliest,
    )
    if source_state != "ready":
        return _gap_output(
            output=output,
            events=events,
            indices=indices,
            state=source_state,
            code=(
                "critical_value_018_stage2_budget_gap"
                if source_state == "window_unavailable"
                else "critical_value_018_stage2_source_gap"
            ),
            model_parameters=model_parameters,
        )

    input_state, event_inputs = _build_event_inputs(
        events=events,
        indices=indices,
        clauses=clauses,
    )
    if input_state != "ready":
        return _gap_output(
            output=output,
            events=events,
            indices=indices,
            state=input_state,
            code="critical_value_018_stage2_event_gap",
            model_parameters=model_parameters,
        )

    prompt = _prompt(event_inputs=event_inputs, clauses=clauses)
    started = time.perf_counter()
    try:
        response = await generate(
            prompt,
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
            allow_length_retry=False,
            response_format={"type": "json_object"},
            enable_thinking=False,
        )
    except Exception:  # noqa: BLE001 - provider 失败收敛为明确 Stage2 失败。
        outcomes = {index: _Outcome("generation_failed") for index in indices}
        _apply_outcomes(events, outcomes)
        output["diagnostic"] = _diagnostic_from_outcomes(
            code="critical_value_018_stage2_partial",
            event_count=len(indices),
            outcomes=outcomes,
            llm_call_count=1,
            attempt_count=1,
            model_elapsed_ms=_elapsed_ms(started),
            usage_incomplete=True,
            model_parameters=model_parameters,
        )
        return output

    usage = _usage(response)
    response_state, payload = _response_payload(response)
    outcomes = (
        {index: _Outcome(response_state) for index in indices}
        if response_state != "ready"
        else _validate_response_contract(
            payload,
            event_inputs=event_inputs,
            clauses=clauses,
        )
    )
    _apply_outcomes(events, outcomes)
    output["diagnostic"] = _diagnostic_from_outcomes(
        code=(
            "critical_value_018_stage2_ready"
            if all(outcome.state == "ready" for outcome in outcomes.values())
            else "critical_value_018_stage2_partial"
        ),
        event_count=len(indices),
        outcomes=outcomes,
        llm_call_count=1,
        attempt_count=1,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        model_elapsed_ms=_response_elapsed_ms(response, started=started),
        usage_incomplete=usage.incomplete,
        model_parameters=model_parameters,
    )
    return output


def _copy_structured_facts(
    structured_facts: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output = dict(structured_facts)
    event_facts = dict(_mapping(structured_facts.get("event_facts")))
    events = [
        dict(event)
        for event in _sequence(event_facts.get("critical_values"))
        if isinstance(event, Mapping)
    ]
    event_facts["critical_values"] = events
    output["event_facts"] = event_facts
    return output, events


def _stage1_gap_state(structured_facts: Mapping[str, Any]) -> str | None:
    states = _mapping(structured_facts.get("event_source_state_by_rule"))
    state = _clean(states.get(RULE_ID))
    if state == "critical_value_source_complete":
        return None
    if "unavailable" in state:
        return "source_unavailable"
    if "invalid" in state:
        return "source_invalid"
    return "source_partial"


def _build_clause_catalog(
    evidence_payload: Mapping[str, Any],
    *,
    not_before: datetime,
) -> tuple[str, tuple[_Clause, ...]]:
    timeline = _mapping(evidence_payload.get("programmatic_timeline"))
    readiness = _mapping(timeline.get("source_readiness"))
    statuses = tuple(
        _clean(readiness.get(source_type)).lower()
        for source_type in FORMAL_COURSE_SOURCES
    )
    if any(status == "unavailable" for status in statuses):
        return "source_unavailable", ()
    if not all(status == "complete" for status in statuses):
        return "source_partial", ()

    documents = _mapping(timeline.get("documents"))
    clauses: list[_Clause] = []
    document_coordinates: set[tuple[str, str]] = set()
    total_chars = 0
    for source_type in FORMAL_COURSE_SOURCES:
        raw_rows = documents.get(source_type)
        if not isinstance(raw_rows, Sequence) or isinstance(
            raw_rows, (str, bytes, bytearray)
        ):
            return "source_partial", ()
        for raw_row in raw_rows:
            if not isinstance(raw_row, Mapping):
                return "source_partial", ()
            document_id = _controlled_text(raw_row.get("document_id"))
            authored_at = _parse_time(raw_row.get("authored_at"))
            declared_source = _clean(
                raw_row.get("source_type") or raw_row.get("source_table")
            ).lower()
            if declared_source and declared_source != source_type:
                return "source_partial", ()
            if document_id is None or authored_at is None:
                return "source_partial", ()
            if authored_at < not_before:
                continue
            if any(
                raw_row.get(field) is True
                for field in ("truncated", "content_truncated", "projection_incomplete")
            ):
                return "source_partial", ()
            content = _document_text(raw_row, source_type=source_type)
            if content is None:
                return "source_partial", ()
            document_coordinate = source_type, document_id
            if document_coordinate in document_coordinates:
                return "source_partial", ()
            document_coordinates.add(document_coordinate)
            total_chars += len(content)
            if total_chars > _MAX_TOTAL_CHARS:
                return "window_unavailable", ()
            parts = [
                part.strip()
                for part in _CLAUSE_BOUNDARY.split(content)
                if part.strip()
            ]
            if not parts:
                return "source_partial", ()
            authored_at_text = authored_at.isoformat(sep=" ", timespec="seconds")
            for ordinal, clause_text in enumerate(parts, start=1):
                clause_id = f"{document_id}:{ordinal}"
                if _controlled_text(clause_id) is None:
                    return "source_partial", ()
                clauses.append(
                    _Clause(
                        source_type=source_type,
                        document_id=document_id,
                        authored_at=authored_at,
                        authored_at_text=authored_at_text,
                        clause_id=clause_id,
                        text=clause_text,
                    )
                )
                if len(clauses) > _MAX_CLAUSES:
                    return "window_unavailable", ()
    clauses.sort(
        key=lambda clause: (
            clause.authored_at,
            FORMAL_COURSE_SOURCES.index(clause.source_type),
            clause.document_id,
            clause.clause_id,
        )
    )
    coordinates = tuple(clause.coordinate for clause in clauses)
    if len(coordinates) != len(set(coordinates)):
        return "source_partial", ()
    return "ready", tuple(clauses)


def _event_gate(
    *,
    events: Sequence[Mapping[str, Any]],
    indices: Sequence[int],
) -> tuple[str, datetime | None]:
    event_ids: set[str] = set()
    event_times: list[datetime] = []
    for index in indices:
        event = events[index]
        event_id = _controlled_text(event.get("event_id"))
        event_time = _parse_time(event.get("event_time"))
        if (
            event_id is None
            or event_id in event_ids
            or event_time is None
            or not _event_context_is_complete(event)
        ):
            return "event_context_unavailable", None
        event_ids.add(event_id)
        event_times.append(event_time)
    return "ready", min(event_times) if event_times else None


def _event_context_is_complete(event: Mapping[str, Any]) -> bool:
    if (
        _clean(event.get("event_type")) != "critical_values"
        or _clean(event.get("event_kind")) != "critical_lab_report"
        or _clean(event.get("event_source_type")) != "labtest_item_report"
        or _controlled_text(event.get("event_source_id")) is None
        or _clean(event.get("related_source_type")) != "labtest_item_report"
    ):
        return False
    related_ids = {
        value
        for raw_value in _sequence(event.get("related_source_ids"))
        if (value := _controlled_text(raw_value)) is not None
    }
    items = _sequence(event.get("critical_items"))
    if not related_ids or not items:
        return False
    item_ids: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            return False
        item_id = _controlled_text(item.get("item_id"))
        if (
            item_id is None
            or _controlled_text(item.get("item_name")) is None
            or _controlled_text(item.get("result")) is None
            or _clean(item.get("critical_flag")).upper() not in {"PL", "PH"}
        ):
            return False
        item_ids.add(item_id)
    return item_ids == related_ids


def _build_event_inputs(
    *,
    events: Sequence[Mapping[str, Any]],
    indices: Sequence[int],
    clauses: Sequence[_Clause],
) -> tuple[str, tuple[_EventInput, ...]]:
    inputs: list[_EventInput] = []
    for index in indices:
        event = events[index]
        event_id = _controlled_text(event.get("event_id"))
        event_time = _parse_time(event.get("event_time"))
        if event_id is None or event_time is None or not _event_context_is_complete(event):
            return "event_context_unavailable", ()
        inputs.append(
            _EventInput(
                index=index,
                event_id=event_id,
                prompt_event=_prompt_event(event, event_time=event_time),
                allowed_coordinates=frozenset(
                    clause.coordinate
                    for clause in clauses
                    if clause.authored_at >= event_time
                ),
            )
        )
    return "ready", tuple(inputs)


def _prompt_event(event: Mapping[str, Any], *, event_time: datetime) -> dict[str, Any]:
    critical_items = []
    for raw_item in _sequence(event.get("critical_items")):
        if not isinstance(raw_item, Mapping):
            continue
        item = {
            field: value
            for field in ("item_id", "item_name", "result", "unit", "critical_flag")
            if (
                value := _controlled_text(
                    raw_item.get(field),
                    allow_empty=field == "unit",
                )
            )
            is not None
        }
        critical_items.append(item)
    return {
        "event_id": _clean(event.get("event_id")),
        "event_time": event_time.isoformat(sep=" ", timespec="seconds"),
        "report_id": _clean(event.get("event_source_id")),
        "critical_items": critical_items,
    }


def _document_text(row: Mapping[str, Any], *, source_type: str) -> str | None:
    direct_text = next(
        (
            value.strip()
            for field in ("content", "raw_text")
            if isinstance((value := row.get(field)), str) and value.strip()
        ),
        "",
    )
    if source_type != "first_course_record":
        return direct_text or None
    sections = _mapping(row.get("structured_sections"))
    section_lines = [
        f"{label}：{text_value}"
        for key, label in _FIRST_COURSE_SECTION_LABELS
        if (text_value := _clean(sections.get(key)))
    ]
    if section_lines:
        return "\n".join(dict.fromkeys([*section_lines, direct_text]))
    return direct_text or None


def _prompt(*, event_inputs: Sequence[_EventInput], clauses: Sequence[_Clause]) -> str:
    contract = {
        "events": [
            {
                "event_id": item.event_id,
                "facts": [
                    {
                        "fact_kind": fact_kind,
                        "state": "present|absent|unknown",
                        "event_id": item.event_id,
                        "source_type": "present 时为允许坐标来源，否则 null",
                        "document_id": "present 时为允许坐标文书 ID，否则 null",
                        "clause_id": "present 时为允许坐标分句 ID，否则 null",
                    }
                    for fact_kind in FACT_KINDS
                ],
            }
            for item in event_inputs
        ]
    }
    payload = {
        "definitions": {
            "report_recorded": (
                "事件后的正式病程明确记录当前危急值报告、危急值通知，或可由项目名称、"
                "结果和报告时点唯一关联到该危急值事件。"
            ),
            "disposition_recorded": (
                "事件后的正式病程明确记录针对当前危急值的具体处置、治疗调整、复查、"
                "监测或向上级医师报告；泛泛的继续观察不成立。"
            ),
        },
        "events": [
            {
                **dict(item.prompt_event),
                "allowed_clause_coordinates": [
                    {
                        "source_type": coordinate[0],
                        "document_id": coordinate[1],
                        "clause_id": coordinate[2],
                    }
                    for coordinate in sorted(item.allowed_coordinates)
                ],
            }
            for item in event_inputs
        ],
        "clause_catalog": [
            {
                "source_type": clause.source_type,
                "document_id": clause.document_id,
                "authored_at": clause.authored_at_text,
                "clause_id": clause.clause_id,
                "text": clause.text,
            }
            for clause in clauses
        ],
    }
    return (
        "你是病历原子事实提取器。危急值事件已由 PL/PH 结构化检验事实确认，不得"
        "重新判断或排除触发。一次处理全部事件，每个输入事件恰好返回一项，每项恰好"
        "返回 report_recorded、disposition_recorded 两个事实。只能使用该事件的"
        "allowed_clause_coordinates。state 只可为 present、absent、unknown；present"
        "必须绑定一条允许分句的三个坐标，absent/unknown 的坐标必须全部为 null。"
        "不得跨事件或跨分句拼接。若多处分句可支持，选择 authored_at 最早者，同一"
        "时刻按 source_type、document_id、clause_id 字典序选择。你只提取事实，不得"
        "输出质控结论、合规状态、建议、理由、quote、原文摘录或合同外字段。"
        f"\n严格 JSON 合同：{json.dumps(contract, ensure_ascii=False)}"
        f"\n输入：{json.dumps(payload, ensure_ascii=False)}"
    )


def _response_payload(response: Any) -> tuple[str, Any]:
    try:
        if not isinstance(response, Mapping):
            return "response_invalid", None
        choices = response.get("choices")
        if not isinstance(choices, Sequence) or isinstance(
            choices, (str, bytes, bytearray)
        ):
            return "response_invalid", None
        choice = choices[0]
        if not isinstance(choice, Mapping) or choice.get("finish_reason") == "length":
            return "response_invalid", None
        message = choice.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            return "response_invalid", None
        return "ready", json.loads(message["content"])
    except (IndexError, json.JSONDecodeError, TypeError, ValueError):
        return "response_invalid", None


def _validate_response_contract(
    payload: Any,
    *,
    event_inputs: Sequence[_EventInput],
    clauses: Sequence[_Clause],
) -> dict[int, _Outcome]:
    indices = tuple(item.index for item in event_inputs)
    if not isinstance(payload, Mapping) or set(payload) != {"events"}:
        return {index: _Outcome("contract_invalid") for index in indices}
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        return {index: _Outcome("contract_invalid") for index in indices}
    expected_ids = {item.event_id for item in event_inputs}
    events_by_id: dict[str, list[Mapping[str, Any]]] = {}
    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping):
            return {index: _Outcome("contract_invalid") for index in indices}
        event_id = _controlled_text(raw_event.get("event_id"))
        if event_id is None or event_id not in expected_ids:
            return {index: _Outcome("contract_invalid") for index in indices}
        events_by_id.setdefault(event_id, []).append(raw_event)

    clauses_by_coordinate = {clause.coordinate: clause for clause in clauses}
    outcomes: dict[int, _Outcome] = {}
    for event_input in event_inputs:
        candidates = events_by_id.get(event_input.event_id, [])
        if len(candidates) != 1 or set(candidates[0]) != _EVENT_RESPONSE_FIELDS:
            outcomes[event_input.index] = _Outcome("contract_invalid")
            continue
        raw_facts = candidates[0].get("facts")
        outcomes[event_input.index] = _validate_facts(
            raw_facts,
            event_input=event_input,
            clauses_by_coordinate=clauses_by_coordinate,
        )
    return outcomes


def _validate_facts(
    raw_facts: Any,
    *,
    event_input: _EventInput,
    clauses_by_coordinate: Mapping[Coordinate, _Clause],
) -> _Outcome:
    if not isinstance(raw_facts, list) or any(
        not isinstance(fact, Mapping) for fact in raw_facts
    ):
        return _Outcome("contract_invalid")
    counts = Counter(fact.get("fact_kind") for fact in raw_facts)
    if len(raw_facts) != len(FACT_KINDS) or any(
        counts[fact_kind] != 1 for fact_kind in FACT_KINDS
    ):
        return _Outcome("contract_invalid")

    facts: list[dict[str, Any]] = []
    for fact_kind in FACT_KINDS:
        raw_fact = next(fact for fact in raw_facts if fact.get("fact_kind") == fact_kind)
        if set(raw_fact) != _FACT_FIELDS:
            return _Outcome("contract_invalid")
        state = raw_fact.get("state")
        if state not in _FACT_STATES or raw_fact.get("event_id") != event_input.event_id:
            return _Outcome("contract_invalid")
        raw_coordinate = tuple(
            raw_fact.get(field) for field in ("source_type", "document_id", "clause_id")
        )
        if state == "present":
            coordinate_values = tuple(_controlled_text(value) for value in raw_coordinate)
            if any(value is None for value in coordinate_values):
                return _Outcome("contract_invalid")
            coordinate = (
                str(coordinate_values[0]),
                str(coordinate_values[1]),
                str(coordinate_values[2]),
            )
            if (
                coordinate not in clauses_by_coordinate
                or coordinate not in event_input.allowed_coordinates
            ):
                return _Outcome("grounding_invalid")
            source_type, document_id, clause_id = coordinate
        else:
            if any(value is not None for value in raw_coordinate):
                return _Outcome("contract_invalid")
            source_type = document_id = clause_id = None
        facts.append(
            {
                "fact_kind": fact_kind,
                "state": state,
                "event_id": event_input.event_id,
                "source_type": source_type,
                "document_id": document_id,
                "clause_id": clause_id,
            }
        )
    return _Outcome("ready", tuple(facts))


def _apply_outcomes(
    events: list[dict[str, Any]], outcomes: Mapping[int, _Outcome]
) -> None:
    for index, outcome in outcomes.items():
        events[index]["stage2_state_by_rule"] = {RULE_ID: outcome.state}
        events[index]["stage2_facts"] = [dict(fact) for fact in outcome.facts]


def _gap_output(
    *,
    output: dict[str, Any],
    events: list[dict[str, Any]],
    indices: Sequence[int],
    state: str,
    code: str,
    model_parameters: Mapping[str, Any],
) -> dict[str, Any]:
    outcomes = {index: _Outcome(state) for index in indices}
    _apply_outcomes(events, outcomes)
    output["diagnostic"] = _diagnostic_from_outcomes(
        code=code,
        event_count=len(indices),
        outcomes=outcomes,
        model_parameters=model_parameters,
    )
    return output


def _usage(response: Any) -> _Usage:
    raw_usage = response.get("usage") if isinstance(response, Mapping) else None
    if not isinstance(raw_usage, Mapping) and isinstance(response, Mapping):
        raw_usage = response.get("_usage_breakdown")
    if not isinstance(raw_usage, Mapping):
        return _Usage(incomplete=True)
    prompt = _optional_nonnegative_int(
        raw_usage.get("prompt_tokens", raw_usage.get("input_tokens"))
    )
    completion = _optional_nonnegative_int(
        raw_usage.get("completion_tokens", raw_usage.get("output_tokens"))
    )
    total = _optional_nonnegative_int(raw_usage.get("total_tokens"))
    safe_prompt = prompt or 0
    safe_completion = completion or 0
    return _Usage(
        prompt_tokens=safe_prompt,
        completion_tokens=safe_completion,
        total_tokens=max(total or 0, safe_prompt + safe_completion),
        incomplete=prompt is None or completion is None,
    )


def _model_parameters(
    generate: Generate, explicit: Mapping[str, Any] | None
) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    owner = getattr(generate, "__self__", None)
    for name in ("provider_code", "model", "temperature", "top_p"):
        value = getattr(owner, name, None)
        if isinstance(value, (str, int, float, bool)) and value != "":
            parameters[name] = value
    for key, value in _mapping(explicit).items():
        if isinstance(key, str) and isinstance(value, (str, int, float, bool)):
            parameters[key] = value
    parameters.update(
        {
            "enable_thinking": False,
            "max_completion_tokens": _MAX_COMPLETION_TOKENS,
            "allow_length_retry": False,
            "response_format": "json_object",
        }
    )
    return parameters


def _diagnostic_from_outcomes(
    *,
    code: str,
    event_count: int,
    outcomes: Mapping[int, _Outcome],
    model_parameters: Mapping[str, Any],
    llm_call_count: int = 0,
    attempt_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model_elapsed_ms: int = 0,
    usage_incomplete: bool = False,
) -> dict[str, Any]:
    return _diagnostic(
        code=code,
        event_count=event_count,
        llm_call_count=llm_call_count,
        attempt_count=attempt_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model_elapsed_ms=model_elapsed_ms,
        failure_count=sum(outcome.state != "ready" for outcome in outcomes.values()),
        usage_incomplete=usage_incomplete,
        model_parameters=model_parameters,
    )


def _diagnostic(
    *,
    code: str,
    event_count: int,
    model_parameters: Mapping[str, Any],
    llm_call_count: int = 0,
    attempt_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model_elapsed_ms: int = 0,
    failure_count: int = 0,
    usage_incomplete: bool = False,
) -> dict[str, Any]:
    return {
        "code": code,
        "event_count": max(0, event_count),
        "llm_call_count": max(0, llm_call_count),
        "attempt_count": max(0, attempt_count),
        "prompt_tokens": max(0, prompt_tokens),
        "completion_tokens": max(0, completion_tokens),
        "total_tokens": max(0, total_tokens),
        "model_elapsed_ms": max(0, model_elapsed_ms),
        "failure_count": max(0, failure_count),
        "usage_incomplete": usage_incomplete,
        "model_parameters": dict(model_parameters),
    }


def _internal_failure_output(
    structured_facts: Mapping[str, Any],
    *,
    scene: str,
    model_parameters: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        output, events = _copy_structured_facts(structured_facts)
    except Exception:  # noqa: BLE001 - 最后一道失败壳不得再次抛错。
        output, events = {"event_facts": {"critical_values": []}}, []
    indices = [
        index
        for index, event in enumerate(events)
        if event.get("trigger_confirmed") is True
    ]
    for index in indices:
        events[index]["evaluation_window_mature"] = scene == "final"
    outcomes = {index: _Outcome("internal_failure") for index in indices}
    _apply_outcomes(events, outcomes)
    output["diagnostic"] = _diagnostic_from_outcomes(
        code="critical_value_018_stage2_internal_failure",
        event_count=len(indices),
        outcomes=outcomes,
        usage_incomplete=True,
        model_parameters=model_parameters,
    )
    return output


def _parse_time(value: Any) -> datetime | None:
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip()
        if not normalized or len(normalized) > 40 or "\n" in normalized or "\r" in normalized:
            return None
        try:
            parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(_HOSPITAL_TIMEZONE).replace(tzinfo=None)
    return parsed


def _response_elapsed_ms(response: Any, *, started: float) -> int:
    api_time = response.get("_api_time") if isinstance(response, Mapping) else None
    if (
        isinstance(api_time, (int, float))
        and not isinstance(api_time, bool)
        and api_time >= 0
    ):
        return round(float(api_time) * 1_000)
    return _elapsed_ms(started)


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1_000))


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _controlled_text(value: Any, *, allow_empty: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized and allow_empty:
        return ""
    if not normalized or len(normalized) > 160 or "\n" in normalized or "\r" in normalized:
        return None
    return normalized


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


__all__ = [
    "FACT_KINDS",
    "FORMAL_COURSE_SOURCES",
    "extract_critical_value_018_stage2_facts",
]
