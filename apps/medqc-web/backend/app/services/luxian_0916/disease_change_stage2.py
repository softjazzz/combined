"""LX0916-015/016 触发事件后的共享病程事实提取。

Stage 1 独占病危/病重医嘱和 PL/PH 危急值触发事实。本模块只消费已经形成的
``programmatic_timeline``，在五类正式病程来源完整时，以单次模型调用提取 015
与 016 的四个语义原子事实；记录时间由 Python 根据已定位文书确定性派生。模型
不形成规则结论；资料、响应、合同或坐标失败均在本模块内收敛为安全缺口。
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


RULE_015 = "LX0916-015"
RULE_016 = "LX0916-016"
_RULE_IDS = (RULE_015, RULE_016)
FORMAL_COURSE_SOURCES = (
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "postsurg_firstcourse_record",
    "rescue_record",
)
_FACT_FIELD_ORDER = (
    "fact_kind",
    "state",
    "event_id",
    "source_type",
    "document_id",
    "clause_id",
)
FACT_FIELDS = frozenset(_FACT_FIELD_ORDER)
_EVENT_RESPONSE_FIELDS = frozenset({"event_id", "facts"})
_FACT_KINDS_BY_RULE = {
    RULE_015: ("record_present", "time_recorded", "content_recorded"),
    RULE_016: ("analysis_present", "management_present"),
}
_MODEL_FACT_KINDS_BY_RULE = {
    RULE_015: ("record_present", "content_recorded"),
    RULE_016: _FACT_KINDS_BY_RULE[RULE_016],
}
_FACT_STATES = frozenset({"present", "absent", "unknown"})
_MAX_TOTAL_CHARS = 20_000
_MAX_CLAUSES = 256
_MAX_EVENTS = 20
_MAX_COMPLETION_TOKENS = 4_096
_HOSPITAL_TIMEZONE = ZoneInfo("Asia/Shanghai")
_CLAUSE_BOUNDARY = re.compile(r"(?<=[。！？!?；;\n])")
_GENERIC_IMPROVEMENT = frozenset(
    {"好转", "病情好转", "患者好转", "患者病情好转", "病情较前好转", "患者病情较前好转"}
)
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
        return (self.source_type, self.document_id, self.clause_id)


@dataclass(frozen=True)
class _EventInput:
    index: int
    event_id: str
    prompt_event: Mapping[str, Any]
    allowed_coordinates: frozenset[Coordinate]


@dataclass(frozen=True)
class _RuleOutcome:
    state: str
    facts: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class _Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    incomplete: bool = False


async def extract_disease_change_stage2_facts(
    *,
    evidence_payload: Mapping[str, Any],
    structured_facts: Mapping[str, Any],
    scene: str,
    generate: Generate,
) -> dict[str, Any]:
    """为每个已确认触发事件补充 015/016 原子事实与安全阶段状态。"""

    try:
        return await _extract(
            evidence_payload=evidence_payload,
            structured_facts=structured_facts,
            scene=scene,
            generate=generate,
        )
    except Exception:  # noqa: BLE001 - Stage2 不得把单病例异常泄漏到批次。
        return _internal_failure_output(structured_facts, scene=scene)


async def _extract(
    *,
    evidence_payload: Mapping[str, Any],
    structured_facts: Mapping[str, Any],
    scene: str,
    generate: Generate,
) -> dict[str, Any]:
    output, events = _copy_structured_facts(structured_facts)
    triggered_indices = [
        index
        for index, event in enumerate(events)
        if event.get("trigger_confirmed") is True
    ]
    for index in triggered_indices:
        events[index]["evaluation_window_mature"] = scene == "final"
    if not triggered_indices:
        output["diagnostic"] = _diagnostic(
            code="disease_change_stage2_no_trigger", event_count=0
        )
        return output

    gap = _stage1_gap_state(structured_facts) or _readiness_gap_state(evidence_payload)
    if gap is not None:
        return _gap_output(
            output=output,
            events=events,
            indices=triggered_indices,
            state=gap,
            code="disease_change_stage2_source_gap",
        )
    if len(triggered_indices) > _MAX_EVENTS:
        return _gap_output(
            output=output,
            events=events,
            indices=triggered_indices,
            state="window_unavailable",
            code="disease_change_stage2_budget_gap",
        )

    event_gate_state, earliest_event_time = _event_gate(
        events=events,
        triggered_indices=triggered_indices,
    )
    if event_gate_state != "ready" or earliest_event_time is None:
        return _gap_output(
            output=output,
            events=events,
            indices=triggered_indices,
            state=event_gate_state,
            code="disease_change_stage2_event_gap",
        )

    catalog_state, clauses = _build_clause_catalog(
        evidence_payload,
        not_before=earliest_event_time,
    )
    if catalog_state != "ready":
        return _gap_output(
            output=output,
            events=events,
            indices=triggered_indices,
            state=catalog_state,
            code=(
                "disease_change_stage2_budget_gap"
                if catalog_state == "window_unavailable"
                else "disease_change_stage2_source_gap"
            ),
        )
    event_state, event_inputs = _build_event_inputs(
        events=events, triggered_indices=triggered_indices, clauses=clauses
    )
    if event_state != "ready":
        return _gap_output(
            output=output,
            events=events,
            indices=triggered_indices,
            state=event_state,
            code="disease_change_stage2_event_gap",
        )
    try:
        prompt = _prompt(event_inputs=event_inputs, clauses=clauses)
    except Exception:  # noqa: BLE001 - 非法事件上下文不得触发模型调用。
        return _gap_output(
            output=output,
            events=events,
            indices=triggered_indices,
            state="event_context_unavailable",
            code="disease_change_stage2_event_gap",
        )

    started = time.perf_counter()
    try:
        response = await generate(
            prompt,
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
            allow_length_retry=False,
            response_format={"type": "json_object"},
            enable_thinking=False,
        )
    except Exception:  # noqa: BLE001 - provider 失败统一收敛，不重试。
        outcomes = _uniform_outcomes(triggered_indices, "generation_failed")
        _apply_outcomes(events, outcomes)
        output["diagnostic"] = _diagnostic_from_outcomes(
            code="disease_change_stage2_partial",
            event_count=len(triggered_indices),
            outcomes=outcomes,
            llm_call_count=1,
            attempt_count=1,
            model_elapsed_ms=_elapsed_ms(started),
            usage_incomplete=True,
        )
        return output

    usage = _usage(response)
    response_state, payload = _response_payload(response)
    outcomes = (
        _uniform_outcomes(triggered_indices, response_state)
        if response_state != "ready"
        else _validate_response_contract(
            payload, event_inputs=event_inputs, clauses=clauses
        )
    )
    _apply_outcomes(events, outcomes)
    output["diagnostic"] = _diagnostic_from_outcomes(
        code=(
            "disease_change_stage2_ready"
            if all(outcome.state == "ready" for outcome in outcomes.values())
            else "disease_change_stage2_partial"
        ),
        event_count=len(triggered_indices),
        outcomes=outcomes,
        llm_call_count=1,
        attempt_count=1,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        model_elapsed_ms=_response_elapsed_ms(response, started=started),
        usage_incomplete=usage.incomplete,
    )
    return output


def _gap_output(
    *,
    output: dict[str, Any],
    events: list[dict[str, Any]],
    indices: Sequence[int],
    state: str,
    code: str,
) -> dict[str, Any]:
    outcomes = _uniform_outcomes(indices, state)
    _apply_outcomes(events, outcomes)
    output["diagnostic"] = _diagnostic_from_outcomes(
        code=code, event_count=len(indices), outcomes=outcomes
    )
    return output


def _copy_structured_facts(
    structured_facts: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    output = dict(structured_facts)
    event_facts = dict(_mapping(structured_facts.get("event_facts")))
    events = [
        dict(event)
        for event in _sequence(event_facts.get("disease_changes"))
        if isinstance(event, Mapping)
    ]
    event_facts["disease_changes"] = events
    output["event_facts"] = event_facts
    return output, events


def _stage1_gap_state(structured_facts: Mapping[str, Any]) -> str | None:
    states = _mapping(structured_facts.get("event_source_state_by_rule"))
    selected = tuple(_clean(states.get(rule_id)) for rule_id in _RULE_IDS)
    if all(state == "structured_complete" for state in selected):
        return None
    if any("unavailable" in state for state in selected):
        return "source_unavailable"
    return "source_partial"


def _readiness_gap_state(evidence_payload: Mapping[str, Any]) -> str | None:
    timeline = _mapping(evidence_payload.get("programmatic_timeline"))
    readiness = _mapping(timeline.get("source_readiness"))
    statuses = tuple(
        _clean(readiness.get(source)).lower() for source in FORMAL_COURSE_SOURCES
    )
    if all(status == "complete" for status in statuses):
        return None
    if any(status == "unavailable" for status in statuses):
        return "source_unavailable"
    return "source_partial"


def _build_clause_catalog(
    evidence_payload: Mapping[str, Any],
    *,
    not_before: datetime,
) -> tuple[str, tuple[_Clause, ...]]:
    timeline = _mapping(evidence_payload.get("programmatic_timeline"))
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
            content = _document_text(raw_row, source_type=source_type)
            if content is None:
                return "source_partial", ()
            coordinate = (source_type, document_id)
            if coordinate in document_coordinates:
                return "source_partial", ()
            document_coordinates.add(coordinate)
            total_chars += len(content)
            if total_chars > _MAX_TOTAL_CHARS:
                return "window_unavailable", ()
            parts = [
                part.strip() for part in _CLAUSE_BOUNDARY.split(content) if part.strip()
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
    coordinates = [clause.coordinate for clause in clauses]
    if len(coordinates) != len(set(coordinates)):
        return "source_partial", ()
    return "ready", tuple(clauses)


def _event_gate(
    *,
    events: Sequence[Mapping[str, Any]],
    triggered_indices: Sequence[int],
) -> tuple[str, datetime | None]:
    event_ids: set[str] = set()
    event_times: list[datetime] = []
    for index in triggered_indices:
        event = events[index]
        event_id = _controlled_text(event.get("event_id"))
        if (
            event_id is None
            or event_id in event_ids
            or not _event_context_is_complete(event)
        ):
            return "event_context_unavailable", None
        event_time = _parse_time(event.get("event_time"))
        if event_time is None:
            return "event_time_unavailable", None
        event_ids.add(event_id)
        event_times.append(event_time)
    return "ready", min(event_times) if event_times else None


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
        f"{label}：{text}"
        for key, label in _FIRST_COURSE_SECTION_LABELS
        if (text := _clean(sections.get(key)))
    ]
    if section_lines:
        parts = [*section_lines, direct_text]
        return "\n".join(dict.fromkeys(part for part in parts if part))
    return direct_text or None


def _build_event_inputs(
    *,
    events: Sequence[Mapping[str, Any]],
    triggered_indices: Sequence[int],
    clauses: Sequence[_Clause],
) -> tuple[str, tuple[_EventInput, ...]]:
    event_ids: set[str] = set()
    inputs: list[_EventInput] = []
    for index in triggered_indices:
        event = events[index]
        event_id = _controlled_text(event.get("event_id"))
        event_time = _parse_time(event.get("event_time"))
        if (
            event_id is None
            or event_id in event_ids
            or not _event_context_is_complete(event)
        ):
            return "event_context_unavailable", ()
        if event_time is None:
            return "event_time_unavailable", ()
        event_ids.add(event_id)
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


def _event_context_is_complete(event: Mapping[str, Any]) -> bool:
    event_kind = _clean(event.get("event_kind"))
    expected_source_type = {
        "severity_critical": "inpat_nondrug_order",
        "severity_serious": "inpat_nondrug_order",
        "critical_lab_report": "labtest_master",
    }.get(event_kind)
    if (
        expected_source_type is None
        or _clean(event.get("event_source_type")) != expected_source_type
        or _controlled_text(event.get("event_source_id")) is None
    ):
        return False
    if event_kind != "critical_lab_report":
        return True
    if _clean(event.get("related_source_type")) != "labtest_item_report":
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
    for raw_item in items:
        if not isinstance(raw_item, Mapping):
            return False
        item_id = _controlled_text(raw_item.get("item_id"))
        if (
            item_id is None
            or _controlled_text(raw_item.get("item_name")) is None
            or _controlled_text(raw_item.get("result")) is None
            or _clean(raw_item.get("critical_flag")) not in {"PL", "PH"}
        ):
            return False
        item_ids.add(item_id)
    return item_ids == related_ids


def _prompt_event(event: Mapping[str, Any], *, event_time: datetime) -> dict[str, Any]:
    result: dict[str, Any] = {
        "event_id": _clean(event.get("event_id")),
        "event_time": event_time.isoformat(sep=" ", timespec="seconds"),
    }
    for field in (
        "event_kind",
        "event_source_type",
        "event_source_id",
        "related_source_type",
    ):
        value = _controlled_text(event.get(field))
        if value is not None:
            result[field] = value
    for field in ("related_source_ids", "critical_flags"):
        values = [
            value
            for raw_value in _sequence(event.get(field))
            if (value := _controlled_text(raw_value)) is not None
        ]
        if values:
            result[field] = values
    critical_items: list[dict[str, str]] = []
    for raw_item in _sequence(event.get("critical_items")):
        if not isinstance(raw_item, Mapping):
            continue
        item: dict[str, str] = {}
        for field in ("item_id", "item_name", "result", "unit", "critical_flag"):
            value = _controlled_text(raw_item.get(field), allow_empty=field == "unit")
            if value is not None:
                item[field] = value
        if item:
            critical_items.append(item)
    if critical_items:
        result["critical_items"] = critical_items
    return result


def _prompt(*, event_inputs: Sequence[_EventInput], clauses: Sequence[_Clause]) -> str:
    definitions = {
        "record_present": "事件发生后形成的正式病程明确记录了同一病情变化事件，而非仅存在一份文书。",
        "content_recorded": "病程正文明确记录该事件的具体病情变化表现或内容。",
        "analysis_present": "病程正文针对该事件给出独立分析或判断；仅复述症状、数值或普通‘好转’不成立。",
        "management_present": "病程正文针对该事件给出具体处置、治疗调整或复查措施；泛泛观察不成立。",
    }
    contract = {
        "events": [
            {
                "event_id": item.event_id,
                "facts": [
                    {
                        "fact_kind": fact_kind,
                        "state": "present|absent|unknown",
                        "event_id": item.event_id,
                        "source_type": "present 时为可用坐标来源，否则 null",
                        "document_id": "present 时为可用坐标文书 ID，否则 null",
                        "clause_id": "present 时为可用坐标分句 ID，否则 null",
                    }
                    for rule_id in _RULE_IDS
                    for fact_kind in _MODEL_FACT_KINDS_BY_RULE[rule_id]
                ],
            }
            for item in event_inputs
        ]
    }
    payload = {
        "definitions": definitions,
        "event_matching_rules": {
            "severity_critical|severity_serious": (
                "病危/病重医嘱已证明严重程度触发。关联记录无需逐字重复病危/病重；"
                "只要明确记录该时点后与严重程度相关的症状、体征、意识、生命体征、"
                "氧合或整体病情演变，即可视为同一事件记录。"
            ),
            "critical_lab_report": (
                "必须能由项目名称、结果或针对该异常的分析处置关联到当前危急值报告。"
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
        "你是病历原子事实提取器。触发事件已经由结构化数据确认，不得重新判断或排除触发。"
        "一次处理全部事件，并为每个输入事件恰好返回一项、每项恰好返回指定的四个事实。"
        "只能使用该事件 allowed_clause_coordinates 中的分句；分句目录是全局共享目录。"
        "state 只可为 present、absent、unknown。present 必须绑定同一条可用分句的三个坐标；"
        "absent 或 unknown 的三个坐标必须全部为 null。不得跨事件、跨分句拼接。"
        "time_recorded 由 Python 根据已 grounding 文书的 authored_at 确定，不得输出。"
        "若多个分句都能支持同一事实，必须选择 authored_at 最早者；同一时刻再按"
        "source_type、document_id、clause_id 字典序选择。"
        "普通‘好转’不能支持 analysis_present。你只提取事实，不得输出质控结论、合规状态、"
        "建议、理由、quote、原文摘录或合同外字段。"
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
        if not isinstance(message, Mapping) or not isinstance(
            message.get("content"), str
        ):
            return "response_invalid", None
        return "ready", json.loads(message["content"])
    except (IndexError, json.JSONDecodeError, TypeError, ValueError):
        return "response_invalid", None


def _validate_response_contract(
    payload: Any,
    *,
    event_inputs: Sequence[_EventInput],
    clauses: Sequence[_Clause],
) -> dict[tuple[int, str], _RuleOutcome]:
    indices = tuple(item.index for item in event_inputs)
    if not isinstance(payload, Mapping) or set(payload) != {"events"}:
        return _uniform_outcomes(indices, "contract_invalid")
    raw_events = payload.get("events")
    if not isinstance(raw_events, list):
        return _uniform_outcomes(indices, "contract_invalid")
    expected_ids = {item.event_id for item in event_inputs}
    events_by_id: dict[str, list[Mapping[str, Any]]] = {}
    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping):
            return _uniform_outcomes(indices, "contract_invalid")
        event_id = _controlled_text(raw_event.get("event_id"))
        if event_id is None or event_id not in expected_ids:
            return _uniform_outcomes(indices, "contract_invalid")
        events_by_id.setdefault(event_id, []).append(raw_event)

    clauses_by_coordinate = {clause.coordinate: clause for clause in clauses}
    outcomes: dict[tuple[int, str], _RuleOutcome] = {}
    for event_input in event_inputs:
        candidates = events_by_id.get(event_input.event_id, [])
        if len(candidates) != 1 or set(candidates[0]) != _EVENT_RESPONSE_FIELDS:
            outcomes.update(_uniform_outcomes((event_input.index,), "contract_invalid"))
            continue
        raw_facts = candidates[0].get("facts")
        if not isinstance(raw_facts, list) or any(
            not isinstance(raw_fact, Mapping) for raw_fact in raw_facts
        ):
            outcomes.update(_uniform_outcomes((event_input.index,), "contract_invalid"))
            continue
        event_outcomes = {
            rule_id: _validate_rule_facts(
                raw_facts,
                rule_id=rule_id,
                event_input=event_input,
                clauses_by_coordinate=clauses_by_coordinate,
            )
            for rule_id in _RULE_IDS
        }
        if len(raw_facts) != 4 and all(
            outcome.state == "ready" for outcome in event_outcomes.values()
        ):
            event_outcomes = {
                rule_id: _RuleOutcome(state="contract_invalid") for rule_id in _RULE_IDS
            }
        outcomes.update(
            {
                (event_input.index, rule_id): outcome
                for rule_id, outcome in event_outcomes.items()
            }
        )
    return outcomes


def _validate_rule_facts(
    raw_facts: Sequence[Mapping[str, Any]],
    *,
    rule_id: str,
    event_input: _EventInput,
    clauses_by_coordinate: Mapping[Coordinate, _Clause],
) -> _RuleOutcome:
    expected_kinds = _MODEL_FACT_KINDS_BY_RULE[rule_id]
    selected = [fact for fact in raw_facts if fact.get("fact_kind") in expected_kinds]
    counts = Counter(fact.get("fact_kind") for fact in selected)
    if len(selected) != len(expected_kinds) or any(
        counts[fact_kind] != 1 for fact_kind in expected_kinds
    ):
        return _RuleOutcome(state="contract_invalid")

    facts: list[dict[str, Any]] = []
    for fact_kind in expected_kinds:
        raw_fact = next(fact for fact in selected if fact.get("fact_kind") == fact_kind)
        if set(raw_fact) != FACT_FIELDS:
            return _RuleOutcome(state="contract_invalid")
        state = raw_fact.get("state")
        if (
            state not in _FACT_STATES
            or raw_fact.get("event_id") != event_input.event_id
        ):
            return _RuleOutcome(state="contract_invalid")
        coordinate_values = tuple(
            raw_fact.get(field) for field in _FACT_FIELD_ORDER[-3:]
        )
        if state == "present":
            coordinate = tuple(_controlled_text(value) for value in coordinate_values)
            if any(value is None for value in coordinate):
                return _RuleOutcome(state="contract_invalid")
            grounded_coordinate = (
                str(coordinate[0]),
                str(coordinate[1]),
                str(coordinate[2]),
            )
            clause = clauses_by_coordinate.get(grounded_coordinate)
            if (
                clause is None
                or grounded_coordinate not in event_input.allowed_coordinates
                or (
                    fact_kind == "analysis_present"
                    and _is_generic_improvement(clause.text)
                )
            ):
                return _RuleOutcome(state="grounding_invalid")
            source_type, document_id, clause_id = grounded_coordinate
        else:
            if any(value is not None for value in coordinate_values):
                return _RuleOutcome(state="contract_invalid")
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
    if rule_id == RULE_015:
        record_fact = next(
            fact for fact in facts if fact["fact_kind"] == "record_present"
        )
        time_fact = {
            **record_fact,
            "fact_kind": "time_recorded",
        }
        fact_by_kind = {fact["fact_kind"]: fact for fact in facts}
        facts = [
            fact_by_kind["record_present"],
            time_fact,
            fact_by_kind["content_recorded"],
        ]
    return _RuleOutcome(state="ready", facts=tuple(facts))


def _is_generic_improvement(text_value: str) -> bool:
    return re.sub(r"[\s，,。；;：:！!？?]", "", text_value) in _GENERIC_IMPROVEMENT


def _uniform_outcomes(
    indices: Iterable[int], state: str
) -> dict[tuple[int, str], _RuleOutcome]:
    return {
        (index, rule_id): _RuleOutcome(state=state)
        for index in indices
        for rule_id in _RULE_IDS
    }


def _apply_outcomes(
    events: list[dict[str, Any]], outcomes: Mapping[tuple[int, str], _RuleOutcome]
) -> None:
    for index in sorted({index for index, _ in outcomes}):
        events[index]["stage2_state_by_rule"] = {
            rule_id: outcomes[(index, rule_id)].state for rule_id in _RULE_IDS
        }
        events[index]["stage2_facts"] = [
            dict(fact)
            for rule_id in _RULE_IDS
            for fact in outcomes[(index, rule_id)].facts
        ]


def _usage(response: Any) -> _Usage:
    raw_usage = response.get("usage") if isinstance(response, Mapping) else None
    if not isinstance(raw_usage, Mapping):
        return _Usage(incomplete=True)
    prompt_tokens = _optional_nonnegative_int(
        raw_usage.get("prompt_tokens", raw_usage.get("input_tokens"))
    )
    completion_tokens = _optional_nonnegative_int(
        raw_usage.get("completion_tokens", raw_usage.get("output_tokens"))
    )
    total_tokens = _optional_nonnegative_int(raw_usage.get("total_tokens"))
    safe_prompt = prompt_tokens or 0
    safe_completion = completion_tokens or 0
    return _Usage(
        prompt_tokens=safe_prompt,
        completion_tokens=safe_completion,
        total_tokens=max(total_tokens or 0, safe_prompt + safe_completion),
        incomplete=prompt_tokens is None or completion_tokens is None,
    )


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


def _diagnostic_from_outcomes(
    *,
    code: str,
    event_count: int,
    outcomes: Mapping[tuple[int, str], _RuleOutcome],
    llm_call_count: int = 0,
    attempt_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model_elapsed_ms: int = 0,
    usage_incomplete: bool = False,
) -> dict[str, Any]:
    rule_failure_counts = {
        rule_id: sum(
            outcome.state != "ready"
            for (_, outcome_rule_id), outcome in outcomes.items()
            if outcome_rule_id == rule_id
        )
        for rule_id in _RULE_IDS
    }
    return _diagnostic(
        code=code,
        event_count=event_count,
        llm_call_count=llm_call_count,
        attempt_count=attempt_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model_elapsed_ms=model_elapsed_ms,
        failure_count=sum(rule_failure_counts.values()),
        rule_failure_counts=rule_failure_counts,
        usage_incomplete=usage_incomplete,
    )


def _diagnostic(
    *,
    code: str,
    event_count: int,
    llm_call_count: int = 0,
    attempt_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model_elapsed_ms: int = 0,
    failure_count: int = 0,
    rule_failure_counts: Mapping[str, int] | None = None,
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
        "rule_failure_counts": dict(
            rule_failure_counts or {rule_id: 0 for rule_id in _RULE_IDS}
        ),
        "usage_incomplete": usage_incomplete,
    }


def _internal_failure_output(
    structured_facts: Mapping[str, Any], *, scene: str
) -> dict[str, Any]:
    try:
        output, events = _copy_structured_facts(structured_facts)
    except Exception:  # noqa: BLE001 - 最后一道失败壳不得再次抛错。
        output, events = {"event_facts": {"disease_changes": []}}, []
    indices = [
        index
        for index, event in enumerate(events)
        if event.get("trigger_confirmed") is True
    ]
    for index in indices:
        events[index]["evaluation_window_mature"] = scene == "final"
    outcomes = _uniform_outcomes(indices, "internal_failure")
    _apply_outcomes(events, outcomes)
    output["diagnostic"] = _diagnostic_from_outcomes(
        code="disease_change_stage2_internal_failure",
        event_count=len(indices),
        outcomes=outcomes,
        usage_incomplete=True,
    )
    return output


def _parse_time(value: Any) -> datetime | None:
    parsed: datetime | None = None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip()
        if (
            not normalized
            or "\n" in normalized
            or "\r" in normalized
            or len(normalized) > 40
        ):
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
    if (
        not normalized
        or len(normalized) > 160
        or "\n" in normalized
        or "\r" in normalized
    ):
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


__all__ = ["extract_disease_change_stage2_facts"]
