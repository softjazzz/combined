from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import json
from typing import Any

import pytest

from app.services.luxian_0609 import native_treatment_order_consistency as module
from app.services.luxian_0609.native_treatment_order_consistency import (
    CourseNote,
    SourceReadiness,
    TreatmentEvent,
    TreatmentOrder,
    evaluate_lx0609_059_treatment_order_consistency as _evaluate_raw,
)


_TEST_REDACTION_TERMS = ("TEST-HOSPITAL|TEST-PATIENT|TEST-VISIT",)


async def evaluate_lx0609_059_treatment_order_consistency(**kwargs: Any):
    kwargs.setdefault("redaction_terms", _TEST_REDACTION_TERMS)
    return await _evaluate_raw(**kwargs)


class _FakeLLM:
    def __init__(
        self,
        response: dict[str, Any] | Exception,
        *,
        prompt_tokens: Any = 120,
        completion_tokens: Any = 30,
        include_usage: bool = True,
    ) -> None:
        self.response = response
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.include_usage = include_usage
        self.prompts: list[str] = []
        self.request_options: list[dict[str, Any]] = []

    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool | None = None,
    ) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.request_options.append(
            {
                "max_completion_tokens": max_completion_tokens,
                "allow_length_retry": allow_length_retry,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        response = dict(self.response)
        raw_rows = response.get("events")
        if isinstance(raw_rows, list):
            prompt_payload = json.loads(prompt.rsplit("输入：", 1)[1])
            translated_rows: list[dict[str, Any]] = []
            for index, raw_row in enumerate(raw_rows):
                row = dict(raw_row)
                legacy_event_id = row.pop("event_id", None)
                if legacy_event_id == "other":
                    row["event_ref"] = "evt_not_from_this_request"
                elif legacy_event_id is not None:
                    row["event_ref"] = prompt_payload["events"][index]["event_ref"]
                refs: list[str] = []
                for legacy_ref in row.get("course_refs", []):
                    suffix = str(legacy_ref).rsplit("-", 1)[-1]
                    course_index = int(suffix) - 1 if suffix.isdigit() else index
                    refs.append(prompt_payload["course_notes"][course_index]["course_ref"])
                row["course_refs"] = refs
                translated_rows.append(row)
            response["events"] = translated_rows
        result = dict(response)
        if self.include_usage:
            result["usage"] = {
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
            }
        return result


def _event(
    event_id: str = "exam-1",
    *,
    order_id: str = "order-1",
    event_code: str = "CT-CHEST",
    description: str = "胸部CT检查已完成",
) -> TreatmentEvent:
    return TreatmentEvent(
        event_id=event_id,
        event_kind="performed_exam",
        event_time=datetime(2026, 8, 10, 9, 0),
        description=description,
        source_ref=f"exam_master:{event_id}",
        order_id=order_id,
        event_code=event_code,
        actual=True,
    )


def _order(
    order_id: str = "order-1",
    *,
    event_code: str = "CT-CHEST",
    description: str = "胸部CT检查",
    action: str = "performed",
) -> TreatmentOrder:
    return TreatmentOrder(
        order_id=order_id,
        application_id="",
        event_code=event_code,
        action=action,
        status="已执行",
        order_time=datetime(2026, 8, 10, 8, 30),
        description=description,
        source_ref=f"inpat_nondrug_order:{order_id}",
    )


def _course(note_id: str = "course-1", text: str = "今日已完成胸部CT检查。") -> CourseNote:
    return CourseNote(
        note_id=note_id,
        note_time=datetime(2026, 8, 10, 11, 0),
        text=text,
        source_ref=f"daily_course_record:{note_id}",
    )


def _ready() -> dict[str, SourceReadiness]:
    return {
        "events": SourceReadiness.COMPLETE,
        "orders": SourceReadiness.COMPLETE,
        "course_notes": SourceReadiness.COMPLETE,
    }


@pytest.mark.asyncio
async def test_complete_event_order_and_course_are_compliant_with_one_llm_call() -> None:
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "compliant"
    assert result.reason_code == "requirement_satisfied"
    assert result.llm_call_count == 1
    assert len(llm.prompts) == 1
    assert result.prompt_tokens == 120
    assert result.completion_tokens == 30
    assert result.total_tokens == 150
    assert result.event_results[0].course_refs == ("daily_course_record:course-1",)
    assert "exam-1" not in llm.prompts[0]
    assert "order-1" not in llm.prompts[0]
    assert "course-1" not in llm.prompts[0]
    assert "exam_master:exam-1" not in llm.prompts[0]
    assert llm.request_options == [
        {"max_completion_tokens": 512, "allow_length_retry": False}
    ]


@pytest.mark.asyncio
async def test_multiple_events_are_evaluated_in_one_batched_llm_call() -> None:
    second = TreatmentEvent(
        event_id="procedure-2",
        event_kind="performed_procedure",
        event_time=datetime(2026, 8, 10, 15, 0),
        description="胸腔穿刺已完成",
        source_ref="procedure:procedure-2",
        application_id="application-2",
        actual=True,
    )
    second_order = TreatmentOrder(
        order_id="order-2",
        application_id="application-2",
        event_code="",
        action="execute",
        status="已执行",
        order_time=datetime(2026, 8, 10, 14, 30),
        description="胸腔穿刺术",
        source_ref="inpat_nondrug_order:order-2",
    )
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                },
                {
                    "event_id": "procedure-2",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-2"],
                },
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event(), second],
        orders=[_order(), second_order],
        course_notes=[
            _course(),
            CourseNote(
                note_id="course-2",
                note_time=datetime(2026, 8, 10, 16, 0),
                text="今日已完成胸腔穿刺。",
                source_ref="daily_course_record:course-2",
            ),
        ],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "compliant"
    assert result.llm_call_count == 1
    assert len(result.event_results) == 2
    assert len(llm.prompts) == 1


@pytest.mark.asyncio
async def test_complete_order_source_with_missing_order_is_non_compliant_without_llm() -> None:
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "non_compliant"
    assert result.reason_code == "required_order_missing"
    assert result.event_results[0].order_state == "missing"
    assert result.llm_call_count == 0
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_unavailable_or_truncated_sources_fail_closed_as_data_gap() -> None:
    for source_name, state in (
        ("orders", SourceReadiness.UNAVAILABLE),
        ("course_notes", SourceReadiness.TRUNCATED),
    ):
        readiness = _ready()
        readiness[source_name] = state
        llm = _FakeLLM({"events": []})

        result = await evaluate_lx0609_059_treatment_order_consistency(
            events=[_event()],
            orders=[_order()],
            course_notes=[_course()],
            source_readiness=readiness,
            llm_client=llm,
        )

        assert result.final_state == "data_gap"
        assert result.reason_code == f"{source_name}_source_{state.value}"
        assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_query_error_fails_closed_as_technical_error() -> None:
    readiness = _ready()
    readiness["orders"] = SourceReadiness.ERROR

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=readiness,
        llm_client=_FakeLLM({"events": []}),
    )

    assert result.final_state == "technical_error"
    assert result.reason_code == "orders_source_query_error"


@pytest.mark.asyncio
async def test_ambiguous_code_association_is_data_gap_and_does_not_call_llm() -> None:
    event = _event(order_id="")
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[event],
        orders=[_order("order-1"), _order("order-2")],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "data_gap"
    assert result.reason_code == "order_association_ambiguous"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_multiple_business_keys_must_resolve_to_the_same_unique_order() -> None:
    event = TreatmentEvent(
        event_id="exam-1",
        event_kind="performed_exam",
        event_time=datetime(2026, 8, 10, 9, 0),
        description="胸部CT检查已完成",
        source_ref="exam_master:exam-1",
        order_id="order-1",
        application_id="application-2",
        event_code="CT-CHEST",
        actual=True,
    )
    first = _order("order-1")
    second = TreatmentOrder(
        order_id="order-2",
        application_id="application-2",
        event_code="OTHER",
        action="performed",
        status="已执行",
        order_time=datetime(2026, 8, 10, 8, 40),
        description="另一项检查",
        source_ref="inpat_nondrug_order:order-2",
    )
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[event],
        orders=[first, second],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "data_gap",
        "order_association_conflict",
    )
    assert result.event_results[0].order_state == "conflict"
    assert result.llm_call_count == 0
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_multiple_business_keys_resolving_same_order_can_continue() -> None:
    event = TreatmentEvent(
        event_id="exam-1",
        event_kind="performed_exam",
        event_time=datetime(2026, 8, 10, 9, 0),
        description="胸部CT检查已完成",
        source_ref="exam_master:exam-1",
        order_id="order-1",
        application_id="application-1",
        event_code="CT-CHEST",
        actual=True,
    )
    order = TreatmentOrder(
        order_id="order-1",
        application_id="application-1",
        event_code="CT-CHEST",
        action="performed",
        status="已执行",
        order_time=datetime(2026, 8, 10, 8, 30),
        description="胸部CT检查",
        source_ref="inpat_nondrug_order:order-1",
    )
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[event],
        orders=[order],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "compliant"
    assert result.event_results[0].order_state == "matched"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_unique_order_id_can_narrow_a_reused_event_code_to_one_order() -> None:
    event = TreatmentEvent(
        event_id="exam-1",
        event_kind="performed_exam",
        event_time=datetime(2026, 8, 10, 9, 0),
        description="胸部CT检查已完成",
        source_ref="exam_master:exam-1",
        order_id="order-1",
        event_code="CT-CHEST",
        actual=True,
    )
    repeated_code_order = TreatmentOrder(
        order_id="order-older",
        application_id="",
        event_code="CT-CHEST",
        action="performed",
        status="已执行",
        order_time=datetime(2026, 8, 8, 8, 30),
        description="前次胸部CT检查",
        source_ref="inpat_nondrug_order:order-older",
    )
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[event],
        orders=[_order(), repeated_code_order],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "compliant"
    assert result.event_results[0].order_id == "order-1"
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_identical_physical_duplicate_rows_count_as_one_logical_order() -> None:
    logical_order = _order()
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[logical_order, logical_order],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "compliant"
    assert result.event_results[0].order_state == "matched"


@pytest.mark.asyncio
async def test_all_missing_orders_are_returned_for_customer_event_level_display() -> None:
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event("exam-1", order_id="missing-1"), _event("exam-2", order_id="missing-2")],
        orders=[],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "non_compliant",
        "required_order_missing",
    )
    assert [(item.event_id, item.order_state) for item in result.event_results] == [
        ("exam-1", "missing"),
        ("exam-2", "missing"),
    ]
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_data_gap_dominates_missing_order_without_false_definite_problem() -> None:
    missing = _event("exam-missing", order_id="missing-order")
    unresolved = TreatmentEvent(
        event_id="exam-unresolved",
        event_kind="performed_exam",
        event_time=datetime(2026, 8, 10, 10, 0),
        description="另一项检查已完成",
        source_ref="exam_master:exam-unresolved",
        actual=True,
    )
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[missing, unresolved],
        orders=[],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "data_gap",
        "order_association_key_missing",
    )
    assert [(item.event_id, item.order_state) for item in result.event_results] == [
        ("exam-missing", "missing"),
        ("exam-unresolved", "unresolved"),
    ]
    assert result.llm_call_count == 0
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_key_conflict_dominates_other_definite_missing_events() -> None:
    conflict = TreatmentEvent(
        event_id="exam-conflict",
        event_kind="performed_exam",
        event_time=datetime(2026, 8, 10, 10, 0),
        description="另一项检查已完成",
        source_ref="exam_master:exam-conflict",
        order_id="order-1",
        application_id="application-2",
        actual=True,
    )
    orders = [
        _order("order-1", event_code="FIRST"),
        TreatmentOrder(
            order_id="order-2",
            application_id="application-2",
            event_code="SECOND",
            action="performed",
            status="已执行",
            order_time=datetime(2026, 8, 10, 8, 40),
            description="另一项检查",
            source_ref="inpat_nondrug_order:order-2",
        ),
    ]
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event("exam-missing", order_id="missing-order"), conflict],
        orders=orders,
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "data_gap",
        "order_association_conflict",
    )
    assert [(item.event_id, item.order_state) for item in result.event_results] == [
        ("exam-missing", "missing"),
        ("exam-conflict", "conflict"),
    ]
    assert all(not item.semantic_verdict for item in result.event_results)
    assert result.llm_call_count == 0
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_one_order_cannot_be_borrowed_by_two_events() -> None:
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event("exam-1"), _event("exam-2")],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "data_gap"
    assert result.reason_code == "order_reused_across_events"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_course_name_cooccurrence_cannot_replace_event_level_semantic_result() -> None:
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "not_documented",
                    "course_refs": [],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event(description="头孢呋辛治疗事件")],
        orders=[_order(description="头孢呋辛")],
        course_notes=[_course(text="三日前曾使用头孢呋辛，本次未记录诊疗事件。")],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "non_compliant"
    assert result.reason_code == "course_documentation_missing"


@pytest.mark.asyncio
async def test_unknown_llm_event_or_invalid_enum_is_technical_error() -> None:
    for payload in (
        {
            "events": [
                {"event_id": "other", "verdict": "consistent", "course_refs": []}
            ]
        },
        {
            "events": [
                {"event_id": "exam-1", "verdict": "maybe", "course_refs": []}
            ]
        },
    ):
        result = await evaluate_lx0609_059_treatment_order_consistency(
            events=[_event()],
            orders=[_order()],
            course_notes=[_course()],
            source_readiness=_ready(),
            llm_client=_FakeLLM(payload),
        )

        assert result.final_state == "technical_error"
        assert result.reason_code == "llm_response_invalid"
        assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_llm_prompt_uses_request_local_hash_refs_not_business_coordinates() -> None:
    coordinate = "HOSP-0609|VISIT-208790|MR-359787"
    event = TreatmentEvent(
        event_id=coordinate,
        event_kind="performed_exam",
        event_time=datetime(2026, 8, 10, 9, 0),
        description="胸部CT检查已完成",
        source_ref=f"exam_master:{coordinate}",
        order_id=f"ORDER-{coordinate}",
        event_code="CT-CHEST",
        actual=True,
    )
    order = _order(order_id=f"ORDER-{coordinate}")
    note = CourseNote(
        note_id=f"NOTE-{coordinate}",
        note_time=datetime(2026, 8, 10, 11, 0),
        text="今日已完成胸部CT检查。",
        source_ref=f"daily_course_record:{coordinate}",
    )
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[event],
        orders=[order],
        course_notes=[note],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "compliant"
    assert coordinate not in llm.prompts[0]
    assert f"ORDER-{coordinate}" not in llm.prompts[0]
    assert f"NOTE-{coordinate}" not in llm.prompts[0]
    assert '"event_ref":"evt_' in llm.prompts[0]
    assert '"order_ref":"ord_' in llm.prompts[0]
    assert '"course_ref":"course_' in llm.prompts[0]


@pytest.mark.asyncio
async def test_raw_identifiers_and_explicit_coordinates_are_redacted_from_all_text() -> None:
    coordinate = "HOSP-0609|PATIENT-208790|VISIT-359787"
    event = TreatmentEvent(
        event_id="event-sensitive-id",
        event_kind="performed_exam",
        event_time=datetime(2026, 8, 10, 9, 0),
        description=f"检查描述含 {coordinate} event-sensitive-id exam_master:sensitive",
        source_ref="exam_master:sensitive",
        order_id="order-sensitive-id",
        application_id="application-sensitive-id",
        event_code="CT-CHEST",
        actual=True,
    )
    order = TreatmentOrder(
        order_id="order-sensitive-id",
        application_id="application-sensitive-id",
        event_code="CT-CHEST",
        action="performed",
        status="已执行",
        order_time=datetime(2026, 8, 10, 8, 30),
        description=f"医嘱描述含 {coordinate} inpat_nondrug_order:sensitive",
        source_ref="inpat_nondrug_order:sensitive",
    )
    note = CourseNote(
        note_id="course-sensitive-id",
        note_time=datetime(2026, 8, 10, 11, 0),
        text=(
            f"病程含 {coordinate} event-sensitive-id order-sensitive-id "
            "course-sensitive-id daily_course_record:sensitive"
        ),
        source_ref="daily_course_record:sensitive",
    )
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[event],
        orders=[order],
        course_notes=[note],
        source_readiness=_ready(),
        llm_client=llm,
        redaction_terms=[coordinate],
    )

    assert result.final_state == "compliant"
    for sensitive in (
        coordinate,
        "event-sensitive-id",
        "exam_master:sensitive",
        "order-sensitive-id",
        "application-sensitive-id",
        "inpat_nondrug_order:sensitive",
        "course-sensitive-id",
        "daily_course_record:sensitive",
    ):
        assert sensitive not in llm.prompts[0]


@pytest.mark.asyncio
async def test_redaction_terms_are_mandatory_before_any_http_request() -> None:
    for missing_terms in ((), [], "", ["", "   "]):
        llm = _FakeLLM({"events": []})

        result = await _evaluate_raw(
            events=[_event()],
            orders=[_order()],
            course_notes=[_course()],
            source_readiness=_ready(),
            llm_client=llm,
            redaction_terms=missing_terms,
        )

        assert (result.final_state, result.reason_code) == (
            "technical_error",
            "redaction_terms_missing",
        )
        assert result.llm_call_count == 0
        assert llm.prompts == []


@pytest.mark.asyncio
async def test_event_code_and_coordinate_only_embedded_in_text_are_redacted() -> None:
    coordinate = "HOSP-TEXT|PATIENT-TEXT|VISIT-TEXT"
    event_code = "EXAM-CODE-SENSITIVE"
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )

    result = await _evaluate_raw(
        events=[
            _event(
                event_code=event_code,
                description=f"完成检查 {coordinate} {event_code}",
            )
        ],
        orders=[
            _order(
                event_code=event_code,
                description=f"执行医嘱 {coordinate} {event_code}",
            )
        ],
        course_notes=[
            _course(text=f"病程记录 {coordinate} {event_code}")
        ],
        source_readiness=_ready(),
        llm_client=llm,
        redaction_terms=[coordinate],
    )

    assert result.final_state == "compliant"
    assert coordinate not in llm.prompts[0]
    assert event_code not in llm.prompts[0]


@pytest.mark.asyncio
async def test_openai_response_envelope_is_parsed_without_relaxing_hash_contract() -> None:
    class _OpenAIEnvelopeLLM:
        async def generate(
            self,
            prompt: str,
            *,
            max_completion_tokens: int | None = None,
            allow_length_retry: bool | None = None,
        ) -> dict[str, Any]:
            assert max_completion_tokens == 512
            assert allow_length_retry is False
            payload = json.loads(prompt.rsplit("输入：", 1)[1])
            content = json.dumps(
                {
                    "events": [
                        {
                            "event_ref": payload["events"][0]["event_ref"],
                            "verdict": "consistent",
                            "course_refs": [
                                payload["course_notes"][0]["course_ref"]
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            )
            return {
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 20},
            }

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=_OpenAIEnvelopeLLM(),
    )

    assert result.final_state == "compliant"
    assert result.total_tokens == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("llm", "expected_reason"),
    [
        (_FakeLLM({"events": []}, include_usage=False), "llm_usage_invalid"),
        (_FakeLLM({"events": []}, prompt_tokens=-1), "llm_usage_invalid"),
        (_FakeLLM({"events": []}, completion_tokens=-1), "llm_usage_invalid"),
        (_FakeLLM({"events": []}, prompt_tokens=True), "llm_usage_invalid"),
        (_FakeLLM({"events": []}, completion_tokens=False), "llm_usage_invalid"),
        (_FakeLLM({"events": []}, prompt_tokens="120"), "llm_usage_invalid"),
    ],
)
async def test_usage_must_contain_two_non_negative_real_integers(
    llm: _FakeLLM,
    expected_reason: str,
) -> None:
    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "technical_error",
        expected_reason,
    )
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_actual_usage_over_prompt_budget_cannot_produce_compliance() -> None:
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        },
        prompt_tokens=4_097,
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "technical_error",
        "llm_usage_prompt_token_limit_exceeded",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field_name", "conflicting_value"),
    [
        ("action", "待确认"),
        ("status", "已撤回"),
        ("order_time", datetime(2026, 8, 10, 8, 30) + timedelta(minutes=1)),
        ("description", "另一项检查"),
    ],
)
async def test_conflicting_duplicate_order_rows_fail_closed_independent_of_input_order(
    field_name: str,
    conflicting_value: Any,
) -> None:
    first = _order()
    conflicting = replace(
        first,
        **{field_name: conflicting_value},
        source_ref="medical_order:order-1",
    )

    for rows in ([first, conflicting], [conflicting, first]):
        result = await evaluate_lx0609_059_treatment_order_consistency(
            events=[_event()],
            orders=rows,
            course_notes=[_course()],
            source_readiness=_ready(),
            llm_client=_FakeLLM({"events": []}),
        )

        assert (result.final_state, result.reason_code) == (
            "data_gap",
            "order_association_conflict",
        )
        assert result.event_results[0].order_state == "conflict"
        assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_same_business_order_across_sources_folds_only_when_semantics_match() -> None:
    first = _order()
    same_semantics_other_source = TreatmentOrder(
        order_id=first.order_id,
        application_id=first.application_id,
        event_code=first.event_code,
        action=first.action,
        status=first.status,
        order_time=first.order_time,
        description=first.description,
        source_ref="medical_order:order-1",
    )
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[same_semantics_other_source, first],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "compliant"
    assert result.event_results[0].order_ref == "inpat_nondrug_order:order-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_count", [True, 1.0, "1", -1])
async def test_preflight_token_counter_requires_non_bool_non_negative_int(
    invalid_count: Any,
) -> None:
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
        token_counter=lambda _: invalid_count,
    )

    assert (result.final_state, result.reason_code) == (
        "technical_error",
        "llm_token_count_invalid",
    )
    assert result.llm_call_count == 0
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_duplicate_course_refs_in_model_output_invalidate_entire_response() -> None:
    llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": [
                        "daily_course_record:course-1",
                        "daily_course_record:course-1",
                    ],
                }
            ]
        }
    )

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "technical_error",
        "llm_response_invalid",
    )
    assert result.llm_call_count == 1


@pytest.mark.asyncio
async def test_llm_transport_failure_and_ambiguous_semantics_have_distinct_states() -> None:
    technical = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=_FakeLLM(RuntimeError("provider unavailable")),
    )
    ambiguous = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=_FakeLLM(
            {
                "events": [
                    {"event_id": "exam-1", "verdict": "ambiguous", "course_refs": []}
                ]
            }
        ),
    )

    assert (technical.final_state, technical.reason_code) == (
        "technical_error",
        "llm_transport_error",
    )
    assert (ambiguous.final_state, ambiguous.reason_code) == (
        "evaluation_unknown",
        "semantic_association_ambiguous",
    )


@pytest.mark.asyncio
async def test_context_and_prompt_token_limits_block_the_llm_call() -> None:
    llm = _FakeLLM({"events": []})
    oversized_context = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course(text="病" * 12_001)],
        source_readiness=_ready(),
        llm_client=llm,
    )
    oversized_tokens = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
        token_counter=lambda _: 4_097,
    )

    assert (oversized_context.final_state, oversized_context.reason_code) == (
        "data_gap",
        "llm_context_oversized",
    )
    assert (oversized_tokens.final_state, oversized_tokens.reason_code) == (
        "data_gap",
        "llm_prompt_token_limit_exceeded",
    )
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_no_actual_event_is_not_applicable_and_planned_event_is_ignored() -> None:
    planned = TreatmentEvent(
        event_id="planned-1",
        event_kind="planned_exam",
        event_time=datetime(2026, 8, 11, 9, 0),
        description="拟行胸部CT",
        source_ref="course:planned-1",
        order_id="order-1",
        actual=False,
    )
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[planned],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert result.final_state == "not_applicable"
    assert result.reason_code == "trigger_absent_complete"
    assert result.llm_call_count == 0


@pytest.mark.asyncio
async def test_unknown_action_or_missing_authoritative_time_is_data_gap() -> None:
    unknown_action = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order(action="待确认")],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=_FakeLLM({"events": []}),
    )
    event_without_time = TreatmentEvent(
        event_id="exam-1",
        event_kind="performed_exam",
        event_time=None,
        description="胸部CT检查已完成",
        source_ref="exam_master:exam-1",
        order_id="order-1",
        actual=True,
    )
    missing_time = await evaluate_lx0609_059_treatment_order_consistency(
        events=[event_without_time],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=_FakeLLM({"events": []}),
    )

    assert (unknown_action.final_state, unknown_action.reason_code) == (
        "data_gap",
        "order_action_unknown",
    )
    assert (missing_time.final_state, missing_time.reason_code) == (
        "data_gap",
        "event_time_missing",
    )


@pytest.mark.asyncio
async def test_actual_unsupported_event_kind_is_data_gap_but_planned_is_ignored() -> None:
    unsupported = replace(_event(), event_kind="performed_other", actual=True)
    planned = replace(_event("planned-1"), event_kind="planned_exam", actual=False)
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[planned, unsupported],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "data_gap",
        "event_kind_unsupported",
    )
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_actual_event_and_matched_order_require_source_refs_before_llm() -> None:
    cases = (
        (
            [replace(_event(), source_ref="")],
            [_order()],
            "event_source_ref_missing",
        ),
        (
            [_event()],
            [replace(_order(), source_ref="")],
            "order_source_ref_missing",
        ),
    )
    for events, orders, expected_reason in cases:
        llm = _FakeLLM({"events": []})
        result = await evaluate_lx0609_059_treatment_order_consistency(
            events=events,
            orders=orders,
            course_notes=[_course()],
            source_readiness=_ready(),
            llm_client=llm,
        )

        assert (result.final_state, result.reason_code) == (
            "data_gap",
            expected_reason,
        )
        assert llm.prompts == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("verdict", "course_refs"),
    [
        ("consistent", []),
        ("conflict", []),
        ("not_documented", ["daily_course_record:course-1"]),
    ],
)
async def test_semantic_verdict_requires_a_consistent_course_evidence_cardinality(
    verdict: str,
    course_refs: list[str],
) -> None:
    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[_course()],
        source_readiness=_ready(),
        llm_client=_FakeLLM(
            {
                "events": [
                    {
                        "event_id": "exam-1",
                        "verdict": verdict,
                        "course_refs": course_refs,
                    }
                ]
            }
        ),
    )

    assert (result.final_state, result.reason_code) == (
        "technical_error",
        "llm_response_invalid",
    )


@pytest.mark.asyncio
async def test_multi_event_data_gap_primary_reason_is_input_order_independent() -> None:
    missing_event_time = replace(
        _event("exam-time", order_id="order-time", event_code="TIME"),
        event_time=None,
    )
    unknown_action = _event(
        "exam-action", order_id="order-action", event_code="ACTION"
    )
    orders = [
        _order("order-time", event_code="TIME"),
        _order("order-action", event_code="ACTION", action="待确认"),
    ]

    results = []
    for events in (
        [missing_event_time, unknown_action],
        [unknown_action, missing_event_time],
    ):
        results.append(
            await evaluate_lx0609_059_treatment_order_consistency(
                events=events,
                orders=orders,
                course_notes=[_course()],
                source_readiness=_ready(),
                llm_client=_FakeLLM({"events": []}),
            )
        )

    assert [result.reason_code for result in results] == [
        "event_time_missing",
        "event_time_missing",
    ]
    assert [len(result.event_results) for result in results] == [2, 2]


@pytest.mark.asyncio
async def test_blank_course_notes_do_not_become_evidence_or_llm_context() -> None:
    all_blank_llm = _FakeLLM({"events": []})
    all_blank = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[
            CourseNote(
                note_id="blank-1",
                note_time=datetime(2026, 8, 10, 11, 0),
                text=" \n\t ",
                source_ref="",
            )
        ],
        source_readiness=_ready(),
        llm_client=all_blank_llm,
    )
    assert (all_blank.final_state, all_blank.reason_code) == (
        "non_compliant",
        "course_documentation_missing",
    )
    assert all_blank_llm.prompts == []

    partial_llm = _FakeLLM(
        {
            "events": [
                {
                    "event_id": "exam-1",
                    "verdict": "consistent",
                    "course_refs": ["daily_course_record:course-1"],
                }
            ]
        }
    )
    partial = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[
            CourseNote(
                note_id="blank-ignored",
                note_time=datetime(2026, 8, 10, 10, 0),
                text="   ",
                source_ref="daily_course_record:blank-ignored",
            ),
            _course(),
        ],
        source_readiness=_ready(),
        llm_client=partial_llm,
    )

    assert partial.final_state == "compliant"
    prompt_payload = json.loads(partial_llm.prompts[0].rsplit("输入：", 1)[1])
    assert len(prompt_payload["course_notes"]) == 1
    assert prompt_payload["course_notes"][0]["text"] == "今日已完成胸部CT检查。"
    assert "blank-ignored" not in partial_llm.prompts[0]


@pytest.mark.asyncio
async def test_actual_events_have_stable_prompt_and_result_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module.secrets, "token_bytes", lambda _: b"s" * 32)
    later_event = TreatmentEvent(
        event_id="procedure-2",
        event_kind="performed_procedure",
        event_time=datetime(2026, 8, 10, 15, 0),
        description="胸腔穿刺已完成",
        source_ref="procedure:procedure-2",
        application_id="application-2",
        actual=True,
    )
    later_order = TreatmentOrder(
        order_id="order-2",
        application_id="application-2",
        event_code="",
        action="execute",
        status="已执行",
        order_time=datetime(2026, 8, 10, 14, 30),
        description="胸腔穿刺术",
        source_ref="inpat_nondrug_order:order-2",
    )
    response = {
        "events": [
            {
                "event_id": "exam-1",
                "verdict": "consistent",
                "course_refs": ["daily_course_record:course-1"],
            },
            {
                "event_id": "procedure-2",
                "verdict": "consistent",
                "course_refs": ["daily_course_record:course-2"],
            },
        ]
    }
    notes = [
        _course(),
        CourseNote(
            note_id="course-2",
            note_time=datetime(2026, 8, 10, 16, 0),
            text="今日已完成胸腔穿刺。",
            source_ref="daily_course_record:course-2",
        ),
    ]
    outcomes = []
    prompts = []
    for events in ([_event(), later_event], [later_event, _event()]):
        llm = _FakeLLM(response)
        outcomes.append(
            await evaluate_lx0609_059_treatment_order_consistency(
                events=events,
                orders=[_order(), later_order],
                course_notes=notes,
                source_readiness=_ready(),
                llm_client=llm,
            )
        )
        prompts.append(llm.prompts[0])

    assert prompts[0] == prompts[1]
    assert [item.event_id for item in outcomes[0].event_results] == [
        "exam-1",
        "procedure-2",
    ]
    assert outcomes[0].event_results == outcomes[1].event_results


@pytest.mark.asyncio
async def test_duplicate_course_source_ref_folds_only_identical_content_and_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module.secrets, "token_bytes", lambda _: b"c" * 32)
    first = CourseNote(
        note_id="note-z",
        note_time=datetime(2026, 8, 10, 11, 0),
        text="今日已完成胸部CT检查。",
        source_ref="daily_course_record:shared",
    )
    duplicate = replace(first, note_id="note-a")
    response = {
        "events": [
            {
                "event_id": "exam-1",
                "verdict": "consistent",
                "course_refs": ["daily_course_record:course-1"],
            }
        ]
    }
    outcomes = []
    prompts = []
    for notes in ([first, duplicate], [duplicate, first]):
        llm = _FakeLLM(response)
        outcomes.append(
            await evaluate_lx0609_059_treatment_order_consistency(
                events=[_event()],
                orders=[_order()],
                course_notes=notes,
                source_readiness=_ready(),
                llm_client=llm,
            )
        )
        prompts.append(llm.prompts[0])

    assert prompts[0] == prompts[1]
    assert outcomes[0].final_state == outcomes[1].final_state == "compliant"
    assert outcomes[0].event_results[0].course_refs == (
        "daily_course_record:shared",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("conflicting_field", ["text", "note_time"])
async def test_duplicate_course_source_ref_with_conflicting_semantics_is_data_gap(
    conflicting_field: str,
) -> None:
    first = _course()
    conflicting_value: Any = (
        "另一条病程正文"
        if conflicting_field == "text"
        else datetime(2026, 8, 10, 11, 1)
    )
    conflicting = replace(first, **{conflicting_field: conflicting_value})
    llm = _FakeLLM({"events": []})

    result = await evaluate_lx0609_059_treatment_order_consistency(
        events=[_event()],
        orders=[_order()],
        course_notes=[first, conflicting],
        source_readiness=_ready(),
        llm_client=llm,
    )

    assert (result.final_state, result.reason_code) == (
        "data_gap",
        "course_source_ref_conflict",
    )
    assert llm.prompts == []
