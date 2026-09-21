from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from app.services.luxian_0916.critical_value_018_stage2 import (
    FACT_KINDS,
    FORMAL_COURSE_SOURCES,
    extract_critical_value_018_stage2_facts,
)


def _event(
    *,
    event_id: str = "critical-value:REPORT-1",
    event_time: str = "2026-09-16 08:00:00",
) -> dict[str, Any]:
    return {
        "event_type": "critical_values",
        "event_id": event_id,
        "trigger_confirmed": True,
        "evaluation_window_mature": None,
        "event_source_type": "labtest_item_report",
        "event_source_id": event_id.removeprefix("critical-value:"),
        "event_time": event_time,
        "event_kind": "critical_lab_report",
        "related_source_type": "labtest_item_report",
        "related_source_ids": [f"{event_id}:ITEM-1"],
        "critical_flags": ["PH"],
        "critical_items": [
            {
                "item_id": f"{event_id}:ITEM-1",
                "item_name": "血钾",
                "result": "6.8",
                "unit": "mmol/L",
                "critical_flag": "PH",
            }
        ],
    }


def _structured(
    *,
    events: list[Mapping[str, Any]] | None = None,
    state: str = "critical_value_source_complete",
) -> dict[str, Any]:
    return {
        "event_facts": {"critical_values": [dict(event) for event in (events or [])]},
        "event_source_state_by_rule": {"LX0916-018": state},
    }


def _document(
    *,
    document_id: str = "COURSE-1",
    authored_at: str = "2026-09-16 08:30:00",
    content: str = "接获血钾危急值6.8 mmol/L报告。立即停用补钾并复查电解质。",
    **extra: Any,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "authored_at": authored_at,
        "content": content,
        **extra,
    }


def _evidence(
    *,
    documents: Mapping[str, list[Mapping[str, Any]]] | None = None,
    readiness: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source_documents = {source: [] for source in FORMAL_COURSE_SOURCES}
    source_documents["daily_course_record"] = [_document()]
    source_documents.update(documents or {})
    source_readiness = {source: "complete" for source in FORMAL_COURSE_SOURCES}
    source_readiness.update(readiness or {})
    return {
        "programmatic_timeline": {
            "documents": source_documents,
            "source_readiness": source_readiness,
        }
    }


def _fact(
    kind: str,
    *,
    event_id: str = "critical-value:REPORT-1",
    state: str = "present",
    coordinate: tuple[str, str, str] | None = (
        "daily_course_record",
        "COURSE-1",
        "COURSE-1:1",
    ),
) -> dict[str, Any]:
    source_type, document_id, clause_id = coordinate or (None, None, None)
    return {
        "fact_kind": kind,
        "state": state,
        "event_id": event_id,
        "source_type": source_type,
        "document_id": document_id,
        "clause_id": clause_id,
    }


def _response(
    *,
    event_ids: tuple[str, ...] = ("critical-value:REPORT-1",),
    facts_by_event: Mapping[str, list[dict[str, Any]]] | None = None,
    include_usage: bool = True,
) -> dict[str, Any]:
    events = []
    for event_id in event_ids:
        facts = (
            facts_by_event[event_id]
            if facts_by_event and event_id in facts_by_event
            else [_fact(kind, event_id=event_id) for kind in FACT_KINDS]
        )
        events.append({"event_id": event_id, "facts": facts})
    result: dict[str, Any] = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": json.dumps({"events": events})},
            }
        ],
        "_api_time": 0.123,
    }
    if include_usage:
        result["usage"] = {
            "prompt_tokens": 101,
            "completion_tokens": 19,
            "total_tokens": 120,
        }
    return result


@pytest.mark.asyncio
async def test_no_trigger_is_zero_call() -> None:
    calls: list[object] = []

    async def generate(*args: object, **kwargs: object) -> dict[str, Any]:
        calls.append((args, kwargs))
        return _response()

    result = await extract_critical_value_018_stage2_facts(
        evidence_payload={"invalid": "unused"},
        structured_facts=_structured(),
        scene="final",
        generate=generate,
    )

    assert calls == []
    assert result["diagnostic"]["code"] == "critical_value_018_stage2_no_trigger"
    assert result["diagnostic"]["llm_call_count"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("scene", ("running", "final"))
async def test_one_event_uses_one_controlled_call_and_grounded_facts(scene) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def generate(prompt: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((prompt, kwargs))
        return _response()

    result = await extract_critical_value_018_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured(events=[_event()]),
        scene=scene,
        generate=generate,
        model_parameters={
            "provider_code": "aliyun_bailian",
            "model": "qwen3.8-flash",
            "temperature": 0,
            "top_p": 1,
        },
    )

    assert len(calls) == 1
    prompt, kwargs = calls[0]
    assert "质控结论" in prompt
    assert kwargs == {
        "max_completion_tokens": 2048,
        "allow_length_retry": False,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }
    event = result["event_facts"]["critical_values"][0]
    assert event["evaluation_window_mature"] is True
    assert event["stage2_state_by_rule"] == {"LX0916-018": "ready"}
    assert [fact["fact_kind"] for fact in event["stage2_facts"]] == list(FACT_KINDS)
    diagnostic = result["diagnostic"]
    assert diagnostic["code"] == "critical_value_018_stage2_ready"
    assert diagnostic["llm_call_count"] == 1
    assert diagnostic["attempt_count"] == 1
    assert diagnostic["prompt_tokens"] == 101
    assert diagnostic["completion_tokens"] == 19
    assert diagnostic["total_tokens"] == 120
    assert diagnostic["model_elapsed_ms"] == 123
    assert diagnostic["usage_incomplete"] is False
    assert diagnostic["model_parameters"] == {
        "provider_code": "aliyun_bailian",
        "model": "qwen3.8-flash",
        "temperature": 0,
        "top_p": 1,
        "enable_thinking": False,
        "max_completion_tokens": 2048,
        "allow_length_retry": False,
        "response_format": "json_object",
    }


@pytest.mark.asyncio
async def test_multiple_events_share_one_call() -> None:
    calls = 0
    second_id = "critical-value:REPORT-2"

    async def generate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return _response(
            event_ids=("critical-value:REPORT-1", second_id),
            facts_by_event={
                "critical-value:REPORT-1": [_fact(kind) for kind in FACT_KINDS],
                second_id: [
                    _fact(
                        kind,
                        event_id=second_id,
                        coordinate=("daily_course_record", "COURSE-2", "COURSE-2:1"),
                    )
                    for kind in FACT_KINDS
                ],
            },
        )

    result = await extract_critical_value_018_stage2_facts(
        evidence_payload=_evidence(
            documents={
                "daily_course_record": [
                    _document(),
                    _document(
                        document_id="COURSE-2",
                        authored_at="2026-09-16 09:30:00",
                    ),
                ]
            }
        ),
        structured_facts=_structured(
            events=[
                _event(),
                _event(event_id=second_id, event_time="2026-09-16 09:00:00"),
            ]
        ),
        scene="final",
        generate=generate,
    )

    assert calls == 1
    assert result["diagnostic"]["event_count"] == 2
    assert all(
        event["stage2_state_by_rule"]["LX0916-018"] == "ready"
        for event in result["event_facts"]["critical_values"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("critical_value_source_unavailable", "source_unavailable"),
        ("critical_value_source_partial", "source_partial"),
        ("critical_value_source_invalid", "source_invalid"),
    ],
)
async def test_stage1_gap_is_zero_call(state: str, expected: str) -> None:
    called = False

    async def generate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        nonlocal called
        called = True
        return _response()

    result = await extract_critical_value_018_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured(events=[_event()], state=state),
        scene="final",
        generate=generate,
    )

    assert called is False
    event = result["event_facts"]["critical_values"][0]
    assert event["stage2_state_by_rule"]["LX0916-018"] == expected


@pytest.mark.asyncio
async def test_course_source_failure_missing_document_and_truncation_are_zero_call() -> None:
    calls = 0

    async def generate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return _response()

    evidence_cases = (
        _evidence(readiness={"daily_course_record": "unavailable"}),
        _evidence(documents={"daily_course_record": "invalid"}),
        _evidence(
            documents={
                "daily_course_record": [_document(content_truncated=True)]
            }
        ),
    )
    states = []
    for evidence in evidence_cases:
        result = await extract_critical_value_018_stage2_facts(
            evidence_payload=evidence,
            structured_facts=_structured(events=[_event()]),
            scene="final",
            generate=generate,
        )
        states.append(
            result["event_facts"]["critical_values"][0]["stage2_state_by_rule"][
                "LX0916-018"
            ]
        )

    assert calls == 0
    assert states == ["source_unavailable", "source_partial", "source_partial"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            _response(event_ids=("critical-value:WRONG",)),
            "contract_invalid",
        ),
        (
            _response(
                facts_by_event={
                    "critical-value:REPORT-1": [
                        _fact(
                            "report_recorded",
                            coordinate=("daily_course_record", "MISSING", "MISSING:1"),
                        ),
                        _fact("disposition_recorded"),
                    ]
                }
            ),
            "grounding_invalid",
        ),
        (
            _response(
                facts_by_event={
                    "critical-value:REPORT-1": [
                        _fact("report_recorded"),
                        _fact("report_recorded"),
                    ]
                }
            ),
            "contract_invalid",
        ),
    ],
)
async def test_wrong_event_coordinate_or_contract_is_rejected(
    response: dict[str, Any], expected: str
) -> None:
    async def generate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return response

    result = await extract_critical_value_018_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured(events=[_event()]),
        scene="final",
        generate=generate,
    )

    event = result["event_facts"]["critical_values"][0]
    assert event["stage2_state_by_rule"]["LX0916-018"] == expected
    assert event["stage2_facts"] == []


@pytest.mark.asyncio
async def test_negative_facts_require_null_coordinates() -> None:
    bad_response = _response(
        facts_by_event={
            "critical-value:REPORT-1": [
                _fact("report_recorded", state="absent"),
                _fact("disposition_recorded"),
            ]
        }
    )

    async def generate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return bad_response

    result = await extract_critical_value_018_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured(events=[_event()]),
        scene="final",
        generate=generate,
    )

    assert result["event_facts"]["critical_values"][0]["stage2_state_by_rule"] == {
        "LX0916-018": "contract_invalid"
    }


@pytest.mark.asyncio
async def test_model_exception_is_one_attempt_and_usage_incomplete() -> None:
    calls = 0

    async def generate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider unavailable")

    result = await extract_critical_value_018_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured(events=[_event()]),
        scene="final",
        generate=generate,
    )

    assert calls == 1
    event = result["event_facts"]["critical_values"][0]
    assert event["stage2_state_by_rule"] == {"LX0916-018": "generation_failed"}
    assert result["diagnostic"]["llm_call_count"] == 1
    assert result["diagnostic"]["attempt_count"] == 1
    assert result["diagnostic"]["usage_incomplete"] is True


@pytest.mark.asyncio
async def test_missing_usage_is_reported_without_raw_response() -> None:
    async def generate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        return _response(include_usage=False)

    result = await extract_critical_value_018_stage2_facts(
        evidence_payload=_evidence(),
        structured_facts=_structured(events=[_event()]),
        scene="running",
        generate=generate,
    )

    assert result["diagnostic"]["usage_incomplete"] is True
    assert result["diagnostic"]["prompt_tokens"] == 0
    assert result["diagnostic"]["completion_tokens"] == 0
    assert result["event_facts"]["critical_values"][0][
        "evaluation_window_mature"
    ] is True
