from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from app.services.luxian_0916 import disease_change_stage2
from app.services.luxian_0916.disease_change_stage2 import (
    extract_disease_change_stage2_facts,
)


RULE_015 = "LX0916-015"
RULE_016 = "LX0916-016"
MODEL_FACT_KINDS = (
    "record_present",
    "content_recorded",
    "analysis_present",
    "management_present",
)


def _event(**overrides: Any) -> dict[str, Any]:
    event = {
        "event_type": "disease_changes",
        "event_id": "severity-order:ORDER-1",
        "trigger_confirmed": True,
        "event_time": "2026-09-16 08:00:00",
        "event_source_type": "inpat_nondrug_order",
        "event_source_id": "ORDER-1",
        "event_kind": "severity_critical",
    }
    event.update(overrides)
    return event


def _critical_event(**overrides: Any) -> dict[str, Any]:
    event = _event(
        event_id="critical-lab:TEST-1",
        event_time="2026-09-16 09:00:00",
        event_source_type="labtest_master",
        event_source_id="TEST-1",
        event_kind="critical_lab_report",
        related_source_type="labtest_item_report",
        related_source_ids=["ITEM-1", "ITEM-2"],
        critical_flags=["PH", "PL"],
        critical_items=[
            {
                "item_id": "ITEM-1",
                "item_name": "血钾",
                "result": "2.7",
                "unit": "mmol/L",
                "critical_flag": "PL",
            },
            {
                "item_id": "ITEM-2",
                "item_name": "肌钙蛋白",
                "result": "1.2",
                "unit": "ng/mL",
                "critical_flag": "PH",
            },
        ],
    )
    event.update(overrides)
    return event


def _structured(
    events: list[dict[str, Any]],
    *,
    source_state_015: str = "structured_complete",
    source_state_016: str = "structured_complete",
) -> dict[str, Any]:
    return {
        "event_facts": {"disease_changes": events, "critical_values": []},
        "event_source_state_by_rule": {
            RULE_015: source_state_015,
            RULE_016: source_state_016,
        },
        "diagnostic": {"code": "structured_disease_change_trigger_ready"},
    }


def _document(**overrides: Any) -> dict[str, Any]:
    document = {
        "document_id": "COURSE-1",
        "authored_at": "2026-09-16 10:00:00",
        "content": "患者病情变化时间为09:00，考虑低钾血症，立即补钾并复查电解质。",
    }
    document.update(overrides)
    return document


def _evidence(
    *,
    documents: Mapping[str, list[dict[str, Any]]] | None = None,
    readiness: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source_documents = {
        source: [] for source in disease_change_stage2.FORMAL_COURSE_SOURCES
    }
    if documents is None:
        source_documents["daily_course_record"] = [_document()]
    else:
        source_documents.update(
            {source: list(rows) for source, rows in documents.items()}
        )
    source_readiness = {
        source: "complete" for source in disease_change_stage2.FORMAL_COURSE_SOURCES
    }
    if readiness is not None:
        source_readiness.update(readiness)
    return {
        "programmatic_timeline": {
            "documents": source_documents,
            "source_readiness": source_readiness,
        }
    }


def _fact(
    fact_kind: str,
    event_id: str,
    *,
    state: str = "present",
    coordinate: tuple[str, str, str] = (
        "daily_course_record",
        "COURSE-1",
        "COURSE-1:1",
    ),
) -> dict[str, Any]:
    present = state == "present"
    return {
        "fact_kind": fact_kind,
        "state": state,
        "event_id": event_id,
        "source_type": coordinate[0] if present else None,
        "document_id": coordinate[1] if present else None,
        "clause_id": coordinate[2] if present else None,
    }


def _response(
    event_ids: tuple[str, ...] = ("severity-order:ORDER-1",),
    *,
    facts_by_event: Mapping[str, list[dict[str, Any]]] | None = None,
    finish_reason: str = "stop",
    include_usage: bool = True,
) -> dict[str, Any]:
    events = [
        {
            "event_id": event_id,
            "facts": (
                facts_by_event[event_id]
                if facts_by_event is not None
                else [_fact(kind, event_id) for kind in MODEL_FACT_KINDS]
            ),
        }
        for event_id in event_ids
    ]
    response: dict[str, Any] = {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {
                    "content": json.dumps({"events": events}, ensure_ascii=False)
                },
            }
        ],
        "_api_time": 0.25,
    }
    if include_usage:
        response["usage"] = {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        }
    return response


def _event_result(result: Mapping[str, Any], index: int = 0) -> Mapping[str, Any]:
    return result["event_facts"]["disease_changes"][index]


def _prompt_payload(prompt: str) -> Mapping[str, Any]:
    return json.loads(prompt.split("\n输入：", 1)[1])


def _prompt_contract(prompt: str) -> Mapping[str, Any]:
    contract = prompt.split("\n严格 JSON 合同：", 1)[1].split("\n输入：", 1)[0]
    return json.loads(contract)


@pytest.mark.asyncio
async def test_no_trigger_returns_zero_call_without_touching_evidence() -> None:
    calls = 0

    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError("无触发事件不得调用模型")

    result = await extract_disease_change_stage2_facts(
        evidence_payload={"programmatic_timeline": "invalid but unused"},
        structured_facts=_structured([]),
        scene="final",
        generate=generate,
    )

    assert calls == 0
    assert result["diagnostic"] == {
        "code": "disease_change_stage2_no_trigger",
        "event_count": 0,
        "llm_call_count": 0,
        "attempt_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model_elapsed_ms": 0,
        "failure_count": 0,
        "rule_failure_counts": {RULE_015: 0, RULE_016: 0},
        "usage_incomplete": False,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("readiness", "expected_state"),
    [
        ({"rescue_record": "partial"}, "source_partial"),
        ({"senior_course_record": "unavailable"}, "source_unavailable"),
        ({"first_course_record": ""}, "source_partial"),
    ],
)
async def test_all_five_sources_must_be_complete_before_call(
    readiness: Mapping[str, str], expected_state: str
) -> None:
    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("来源不完整不得调用模型")

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(readiness=readiness),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: expected_state,
        RULE_016: expected_state,
    }
    assert result["diagnostic"]["llm_call_count"] == 0


@pytest.mark.asyncio
async def test_incomplete_stage1_source_is_also_zero_call() -> None:
    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("Stage1 来源不完整不得调用模型")

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured(
            [_event()], source_state_016="structured_trigger_source_partial"
        ),
        scene="final",
        generate=generate,
    )

    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: "source_partial",
        RULE_016: "source_partial",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_event",
    [
        _event(event_source_id=""),
        _event(event_kind="unexpected"),
        _critical_event(related_source_type=""),
        _critical_event(critical_items=[]),
    ],
)
async def test_incomplete_or_uncontrolled_event_context_is_zero_call(
    invalid_event: dict[str, Any],
) -> None:
    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("事件上下文不受控时不得调用模型")

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured([invalid_event]),
        scene="final",
        generate=generate,
    )

    assert result["diagnostic"]["llm_call_count"] == 0
    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: "event_context_unavailable",
        RULE_016: "event_context_unavailable",
    }


@pytest.mark.asyncio
async def test_two_events_share_one_catalog_and_one_fixed_budget_call() -> None:
    documents = {
        "daily_course_record": [
            _document(
                document_id="BETWEEN",
                authored_at="2026-09-16 08:30:00",
                content="首次变化后记录。",
            ),
            _document(
                document_id="LATER",
                authored_at="2026-09-16 10:30:00",
                content="两个事件后的后续记录。",
            ),
        ]
    }
    calls: list[tuple[str, dict[str, Any]]] = []
    event_ids = ("severity-order:ORDER-1", "critical-lab:TEST-1")
    facts_by_event = {
        event_ids[0]: [
            _fact(
                kind,
                event_ids[0],
                coordinate=("daily_course_record", "BETWEEN", "BETWEEN:1"),
            )
            for kind in MODEL_FACT_KINDS
        ],
        event_ids[1]: [
            _fact(
                kind,
                event_ids[1],
                coordinate=("daily_course_record", "LATER", "LATER:1"),
            )
            for kind in MODEL_FACT_KINDS
        ],
    }

    async def generate(prompt: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((prompt, kwargs))
        return _response(event_ids, facts_by_event=facts_by_event)

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(documents=documents),
        structured_facts=_structured([_event(), _critical_event()]),
        scene="final",
        generate=generate,
    )

    assert len(calls) == 1
    prompt, kwargs = calls[0]
    assert kwargs == {
        "max_completion_tokens": 4096,
        "allow_length_retry": False,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }
    payload = _prompt_payload(prompt)
    assert [item["document_id"] for item in payload["clause_catalog"]] == [
        "BETWEEN",
        "LATER",
    ]
    allowed = {
        event["event_id"]: {
            item["document_id"] for item in event["allowed_clause_coordinates"]
        }
        for event in payload["events"]
    }
    assert allowed[event_ids[0]] == {"BETWEEN", "LATER"}
    assert allowed[event_ids[1]] == {"LATER"}
    assert "血钾" in prompt and "肌钙蛋白" in prompt
    assert "指定的四个事实" in prompt
    assert "time_recorded 由 Python" in prompt
    assert "authored_at 最早者" in prompt
    contract_fact_kinds = {
        fact["fact_kind"]
        for event in _prompt_contract(prompt)["events"]
        for fact in event["facts"]
    }
    assert contract_fact_kinds == set(MODEL_FACT_KINDS)
    assert all(
        event["stage2_state_by_rule"] == {RULE_015: "ready", RULE_016: "ready"}
        and len(event["stage2_facts"]) == 5
        for event in result["event_facts"]["disease_changes"]
    )
    assert result["diagnostic"]["llm_call_count"] == 1
    assert result["diagnostic"]["attempt_count"] == 1


@pytest.mark.asyncio
async def test_negative_facts_require_null_coordinates() -> None:
    event_id = "severity-order:ORDER-1"
    facts = [
        _fact("record_present", event_id, state="absent"),
        _fact("content_recorded", event_id, state="unknown"),
        _fact("analysis_present", event_id),
        _fact("management_present", event_id),
    ]

    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        return _response(facts_by_event={event_id: facts})

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    returned = {
        fact["fact_kind"]: fact for fact in _event_result(result)["stage2_facts"]
    }
    assert returned["record_present"]["state"] == "absent"
    assert returned["time_recorded"]["state"] == "absent"
    assert returned["content_recorded"]["state"] == "unknown"
    for fact_kind in ("record_present", "time_recorded", "content_recorded"):
        assert returned[fact_kind]["source_type"] is None
        assert returned[fact_kind]["document_id"] is None
        assert returned[fact_kind]["clause_id"] is None


@pytest.mark.asyncio
async def test_time_recorded_is_derived_from_grounded_record() -> None:
    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        return _response()

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    returned = {
        fact["fact_kind"]: fact for fact in _event_result(result)["stage2_facts"]
    }
    assert returned["time_recorded"] == {
        **returned["record_present"],
        "fact_kind": "time_recorded",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("broken_kind", ["record_present", "analysis_present"])
async def test_contract_failure_is_isolated_to_own_rule(broken_kind: str) -> None:
    event_id = "severity-order:ORDER-1"
    facts = [_fact(kind, event_id) for kind in MODEL_FACT_KINDS]
    next(fact for fact in facts if fact["fact_kind"] == broken_kind)["quote"] = (
        "禁止字段"
    )

    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        return _response(facts_by_event={event_id: facts})

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    failed_rule = RULE_015 if broken_kind == "record_present" else RULE_016
    ready_rule = RULE_016 if failed_rule == RULE_015 else RULE_015
    event = _event_result(result)
    assert event["stage2_state_by_rule"] == {
        failed_rule: "contract_invalid",
        ready_rule: "ready",
    }
    expected_kinds = (
        {"analysis_present", "management_present"}
        if ready_rule == RULE_016
        else {"record_present", "time_recorded", "content_recorded"}
    )
    assert {fact["fact_kind"] for fact in event["stage2_facts"]} == expected_kinds


@pytest.mark.asyncio
async def test_plain_improvement_cannot_ground_analysis_but_does_not_pollute_015() -> (
    None
):
    event_id = "severity-order:ORDER-1"

    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        return _response(
            facts_by_event={
                event_id: [_fact(kind, event_id) for kind in MODEL_FACT_KINDS]
            }
        )

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(
            documents={"daily_course_record": [_document(content="患者病情好转。")]}
        ),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    event = _event_result(result)
    assert event["stage2_state_by_rule"] == {
        RULE_015: "ready",
        RULE_016: "grounding_invalid",
    }
    assert {fact["fact_kind"] for fact in event["stage2_facts"]} == {
        "record_present",
        "time_recorded",
        "content_recorded",
    }


@pytest.mark.asyncio
async def test_present_coordinate_must_be_in_that_events_time_window() -> None:
    event_id = "severity-order:ORDER-1"
    facts = [_fact(kind, event_id) for kind in MODEL_FACT_KINDS]
    for fact in facts:
        if fact["fact_kind"] not in {"record_present", "content_recorded"}:
            continue
        fact.update(
            source_type="daily_course_record",
            document_id="OLD",
            clause_id="OLD:1",
        )

    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        return _response(facts_by_event={event_id: facts})

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(
            documents={
                "daily_course_record": [
                    _document(
                        document_id="OLD",
                        authored_at="2026-09-16 07:59:59",
                        content="事件前病程。",
                    ),
                    _document(),
                ]
            }
        ),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: "grounding_invalid",
        RULE_016: "ready",
    }


@pytest.mark.asyncio
async def test_first_course_structured_sections_are_usable_formal_content() -> None:
    event_id = "severity-order:ORDER-1"
    coordinate = ("first_course_record", "FIRST-1", "FIRST-1:1")
    prompts: list[str] = []

    async def generate(prompt: str, **_: Any) -> dict[str, Any]:
        prompts.append(prompt)
        return _response(
            facts_by_event={
                event_id: [
                    _fact(kind, event_id, coordinate=coordinate)
                    for kind in MODEL_FACT_KINDS
                ]
            }
        )

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(
            documents={
                "daily_course_record": [],
                "first_course_record": [
                    _document(
                        document_id="FIRST-1",
                        content="共享回退合成正文。",
                        structured_sections={
                            "case_characteristic": "病例特点内容",
                            "diagnose_based_on": "诊断依据内容",
                            "differential_diagnosis": "鉴别诊断内容",
                            "treatment_plan": "诊疗计划内容",
                        },
                    )
                ],
            }
        ),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    assert len(prompts) == 1
    assert "病例特点：病例特点内容" in prompts[0]
    assert "诊疗计划：诊疗计划内容" in prompts[0]
    assert "共享回退合成正文" in prompts[0]
    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: "ready",
        RULE_016: "ready",
    }


@pytest.mark.asyncio
async def test_final_scene_can_return_absent_when_no_clause_is_after_event() -> None:
    event_id = "severity-order:ORDER-1"
    facts = [_fact(kind, event_id, state="absent") for kind in MODEL_FACT_KINDS]

    async def generate(prompt: str, **_: Any) -> dict[str, Any]:
        assert _prompt_payload(prompt)["events"][0]["allowed_clause_coordinates"] == []
        return _response(facts_by_event={event_id: facts})

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(
            documents={
                "daily_course_record": [_document(authored_at="2026-09-16 07:59:59")]
            }
        ),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    event = _event_result(result)
    assert event["evaluation_window_mature"] is True
    assert event["stage2_state_by_rule"] == {RULE_015: "ready", RULE_016: "ready"}
    assert all(
        fact["source_type"] is None
        and fact["document_id"] is None
        and fact["clause_id"] is None
        for fact in event["stage2_facts"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(("scene", "expected"), [("final", True), ("running", False)])
async def test_scene_controls_evaluation_window_without_changing_extraction(
    scene: str, expected: bool
) -> None:
    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        return _response()

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured([_event(evaluation_window_mature=None)]),
        scene=scene,
        generate=generate,
    )

    assert _event_result(result)["evaluation_window_mature"] is expected
    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: "ready",
        RULE_016: "ready",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("evidence_payload", "events"),
    [
        (
            _evidence(
                documents={"daily_course_record": [_document(content="甲" * 20_001)]}
            ),
            [_event()],
        ),
        (
            _evidence(
                documents={"daily_course_record": [_document(content="甲。" * 257)]}
            ),
            [_event()],
        ),
        (_evidence(), [_event(event_id=f"event-{index}") for index in range(21)]),
    ],
)
async def test_budget_overflow_is_zero_call_without_truncation(
    evidence_payload: Mapping[str, Any], events: list[dict[str, Any]]
) -> None:
    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("预算超限不得裁剪后调用")

    result = await extract_disease_change_stage2_facts(
        evidence_payload=evidence_payload,
        structured_facts=_structured(events),
        scene="final",
        generate=generate,
    )

    assert result["diagnostic"]["code"] == "disease_change_stage2_budget_gap"
    assert result["diagnostic"]["llm_call_count"] == 0
    assert result["diagnostic"]["event_count"] == len(events)


@pytest.mark.asyncio
async def test_documents_before_earliest_event_do_not_consume_catalog_budget() -> None:
    prompts: list[str] = []

    async def generate(prompt: str, **_: Any) -> dict[str, Any]:
        prompts.append(prompt)
        return _response()

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(
            documents={
                "daily_course_record": [
                    _document(
                        document_id="OLD",
                        authored_at="2026-09-16 07:59:59",
                        content="甲" * 20_001,
                    ),
                    _document(),
                ]
            }
        ),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    assert result["diagnostic"]["llm_call_count"] == 1
    assert len(prompts) == 1
    payload = _prompt_payload(prompts[0])
    assert [item["document_id"] for item in payload["clause_catalog"]] == ["COURSE-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_document",
    [
        _document(document_id=""),
        _document(authored_at="not-a-time"),
        _document(content=""),
        _document(source_table="rescue_record"),
    ],
)
async def test_invalid_document_coordinate_time_or_content_is_zero_call(
    invalid_document: dict[str, Any],
) -> None:
    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        raise AssertionError("无效文书不得调用模型")

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(
            documents={"daily_course_record": [invalid_document]}
        ),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    assert result["diagnostic"]["llm_call_count"] == 0
    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: "source_partial",
        RULE_016: "source_partial",
    }


@pytest.mark.asyncio
async def test_provider_failure_is_one_attempt_and_usage_incomplete() -> None:
    calls = 0

    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider failed with private material")

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    assert calls == 1
    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: "generation_failed",
        RULE_016: "generation_failed",
    }
    diagnostic = result["diagnostic"]
    assert diagnostic["llm_call_count"] == 1
    assert diagnostic["attempt_count"] == 1
    assert diagnostic["usage_incomplete"] is True
    assert "private material" not in json.dumps(diagnostic)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected_state"),
    [
        (_response(finish_reason="length"), "response_invalid"),
        (
            {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "not-json"}}
                ],
                "usage": {},
            },
            "response_invalid",
        ),
        (
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps({"items": []})},
                    }
                ],
                "usage": {},
            },
            "contract_invalid",
        ),
    ],
)
async def test_length_json_and_top_level_contract_fail_without_retry(
    response: dict[str, Any], expected_state: str
) -> None:
    calls = 0

    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return response

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    assert calls == 1
    assert _event_result(result)["stage2_state_by_rule"] == {
        RULE_015: expected_state,
        RULE_016: expected_state,
    }
    assert result["diagnostic"]["attempt_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("include_usage", "expected"), [(True, False), (False, True)])
async def test_usage_completeness_is_reported_without_raw_response(
    include_usage: bool, expected: bool
) -> None:
    async def generate(*_: Any, **__: Any) -> dict[str, Any]:
        return _response(include_usage=include_usage)

    result = await extract_disease_change_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured([_event()]),
        scene="final",
        generate=generate,
    )

    diagnostic = result["diagnostic"]
    assert diagnostic["usage_incomplete"] is expected
    if include_usage:
        assert diagnostic["prompt_tokens"] == 100
        assert diagnostic["completion_tokens"] == 20
        assert diagnostic["total_tokens"] == 120
        assert diagnostic["model_elapsed_ms"] == 250
    assert set(diagnostic) == {
        "code",
        "event_count",
        "llm_call_count",
        "attempt_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "model_elapsed_ms",
        "failure_count",
        "rule_failure_counts",
        "usage_incomplete",
    }
