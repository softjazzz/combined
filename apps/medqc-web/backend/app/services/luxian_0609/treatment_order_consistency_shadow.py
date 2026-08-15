"""LX0609-059 影子运行适配层。

只把一次请求内的受控材料适配到既有事件级执行器，并返回不含原始标识、
文书正文或模型报文的安全统计摘要。影子结果永不参与正式规则结果和计费汇总。
"""

from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any, Mapping, Sequence

from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .native_treatment_order_consistency import (
    CourseNote,
    SourceReadiness,
    TreatmentEvent,
    TreatmentEventResult,
    TreatmentOrder,
    TreatmentOrderConsistencyResult,
    evaluate_lx0609_059_treatment_order_consistency,
)


LUXIAN_0609_059_SHADOW_CONTRACT_VERSION = "lx0609-059-shadow-v1"
_RULE_ID = "LX0609-059"
_EVENT_SOURCES = ("exam_master", "exam_item_report", "surgery_record")
_ORDER_SOURCES = ("inpat_drug_order", "inpat_nondrug_order")
_COURSE_SOURCES = ("daily_course_record", "senior_course_record")
_ALLOWED_STATES = {
    "compliant",
    "non_compliant",
    "data_gap",
    "not_applicable",
    "evaluation_unknown",
    "technical_error",
}
_ALLOWED_REASONS = {
    "trigger_absent_complete",
    "event_kind_unsupported",
    "event_id_missing",
    "event_id_duplicated",
    "event_source_ref_missing",
    "event_time_missing",
    "order_association_key_missing",
    "order_association_ambiguous",
    "order_association_conflict",
    "order_association_unresolved",
    "order_reused_across_events",
    "order_source_ref_missing",
    "order_time_missing",
    "order_action_unknown",
    "required_order_missing",
    "course_documentation_missing",
    "course_documentation_conflict",
    "course_source_ref_missing",
    "course_source_ref_conflict",
    "semantic_association_ambiguous",
    "requirement_satisfied",
    "llm_context_oversized",
    "llm_prompt_token_limit_exceeded",
    "llm_token_count_invalid",
    "redaction_terms_missing",
    "llm_transport_error",
    "llm_response_invalid",
    "llm_usage_invalid",
    "llm_usage_prompt_token_limit_exceeded",
    "llm_output_token_limit_exceeded",
    "events_source_unavailable",
    "events_source_truncated",
    "events_source_query_error",
    "events_source_state_invalid",
    "orders_source_unavailable",
    "orders_source_truncated",
    "orders_source_query_error",
    "orders_source_state_invalid",
    "course_notes_source_unavailable",
    "course_notes_source_truncated",
    "course_notes_source_query_error",
    "course_notes_source_state_invalid",
}
_ALLOWED_ORDER_STATES = {
    "unknown",
    "unresolved",
    "ambiguous",
    "conflict",
    "missing",
    "matched",
}


def _text(row: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _time(row: Mapping[str, object], *keys: str) -> datetime | None:
    raw = _text(row, *keys)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _source_ref(source_key: str, identity: str) -> str:
    normalized = identity.strip()
    return f"{source_key}:{normalized}" if normalized else ""


def _read_group(
    materials: Luxian0609EvidenceMaterialStore,
    source_keys: Sequence[str],
) -> tuple[SourceReadiness, dict[str, tuple[Mapping[str, object], ...]]]:
    rows_by_source: dict[str, tuple[Mapping[str, object], ...]] = {}
    readiness = SourceReadiness.COMPLETE
    for source_key in source_keys:
        try:
            rows_by_source[source_key] = materials.rows(source_key)
        except EvidenceMaterialTruncated:
            readiness = SourceReadiness.TRUNCATED
        except EvidenceMaterialUnavailable:
            if readiness is SourceReadiness.COMPLETE:
                readiness = SourceReadiness.UNAVAILABLE
        except Exception:
            readiness = SourceReadiness.ERROR
    return readiness, rows_by_source


def _adapt_materials(
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[
    tuple[TreatmentEvent, ...],
    tuple[TreatmentOrder, ...],
    tuple[CourseNote, ...],
    dict[str, SourceReadiness],
]:
    event_state, event_rows = _read_group(materials, _EVENT_SOURCES)
    order_state, order_rows = _read_group(materials, _ORDER_SOURCES)
    course_state, course_rows = _read_group(materials, _COURSE_SOURCES)

    events: list[TreatmentEvent] = []
    seen_exam_ids: set[str] = set()
    for index, row in enumerate(event_rows.get("exam_master", ())):
        exam_id = _text(row, "exam_id")
        if exam_id:
            seen_exam_ids.add(exam_id)
        events.append(TreatmentEvent(
            event_id=exam_id,
            event_kind="performed_exam",
            event_time=_time(
                row, "exam_time", "exam_datetime", "report_time",
                "report_datetime", "request_time",
            ),
            description=_text(
                row, "exam_name", "exam_item_name", "item_name", "exam_type",
            ),
            source_ref=_source_ref("exam_master", exam_id),
            order_id=_text(row, "order_id"),
        ))
    for index, row in enumerate(event_rows.get("exam_item_report", ())):
        exam_id = _text(row, "exam_id")
        if exam_id and exam_id in seen_exam_ids:
            continue
        events.append(TreatmentEvent(
            event_id=exam_id,
            event_kind="performed_exam",
            event_time=_time(row, "report_time", "report_datetime"),
            description=_text(
                row, "exam_name", "exam_item_name", "item_name", "exam_type",
            ),
            source_ref=_source_ref(
                "exam_item_report", _text(row, "document_id", "exam_id"),
            ),
        ))
    for index, row in enumerate(event_rows.get("surgery_record", ())):
        document_id = _text(row, "document_id")
        events.append(TreatmentEvent(
            event_id=document_id,
            event_kind="performed_surgery",
            event_time=_time(
                row, "surgery_begin_time", "surgery_end_time", "record_time",
            ),
            description=_text(row, "surgery_name", "surgery_code"),
            source_ref=_source_ref("surgery_record", document_id),
            event_code=_text(row, "surgery_code"),
        ))

    orders: list[TreatmentOrder] = []
    for source_key in _ORDER_SOURCES:
        for index, row in enumerate(order_rows.get(source_key, ())):
            order_id = _text(row, "order_id")
            orders.append(TreatmentOrder(
                order_id=order_id,
                application_id=_text(row, "application_id"),
                event_code=_text(row, "drug_code", "order_type"),
                action=_text(row, "order_status"),
                status=_text(row, "order_status"),
                order_time=_time(
                    row, "order_time", "prescribed_datetime", "start_time", "update_time",
                ),
                description=_text(
                    row, "order_name", "generic_name", "brand_name", "drug_type",
                ),
                source_ref=_source_ref(source_key, order_id),
            ))

    notes: list[CourseNote] = []
    for source_key in _COURSE_SOURCES:
        for index, row in enumerate(course_rows.get(source_key, ())):
            document_id = _text(row, "document_id")
            notes.append(CourseNote(
                note_id=document_id,
                note_time=_time(
                    row, "record_time", "record_datetime", "document_time",
                    "submit_time", "submitted_at", "update_time",
                ),
                text=_text(row, "record_content"),
                source_ref=_source_ref(source_key, document_id),
            ))
    return (
        tuple(events),
        tuple(orders),
        tuple(notes),
        {"events": event_state, "orders": order_state, "course_notes": course_state},
    )


def _safe_error(reason_code: str, *, elapsed_ms: int) -> dict[str, Any]:
    return {
        "shadow_only": True,
        "release_eligible": False,
        "status": "shadow_error",
        "reason_code": reason_code,
        "event_count": 0,
        "matched_order_count": 0,
        "missing_order_count": 0,
        "conflict_order_count": 0,
        "llm_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "elapsed_ms": max(0, elapsed_ms),
        "contract_version": LUXIAN_0609_059_SHADOW_CONTRACT_VERSION,
    }


def _safe_summary(
    result: TreatmentOrderConsistencyResult,
    *,
    event_count: int,
    elapsed_ms: int,
) -> dict[str, Any]:
    if not isinstance(result, TreatmentOrderConsistencyResult):
        raise ValueError("invalid 059 shadow result")
    if result.final_state not in _ALLOWED_STATES or result.reason_code not in _ALLOWED_REASONS:
        raise ValueError("invalid 059 shadow result")
    numbers = (
        result.llm_call_count,
        result.prompt_tokens,
        result.completion_tokens,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in numbers):
        raise ValueError("invalid 059 shadow result")
    if result.llm_call_count > 1:
        raise ValueError("invalid 059 shadow result")
    if not all(isinstance(item, TreatmentEventResult) for item in result.event_results):
        raise ValueError("invalid 059 shadow result")
    order_states = [item.order_state for item in result.event_results]
    if any(state not in _ALLOWED_ORDER_STATES for state in order_states):
        raise ValueError("invalid 059 shadow result")
    status = "shadow_error" if result.final_state == "technical_error" else result.final_state
    return {
        "shadow_only": True,
        "release_eligible": False,
        "status": status,
        "reason_code": result.reason_code,
        "event_count": event_count,
        "matched_order_count": order_states.count("matched"),
        "missing_order_count": order_states.count("missing"),
        "conflict_order_count": order_states.count("conflict"),
        "llm_calls": result.llm_call_count,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "elapsed_ms": max(0, elapsed_ms),
        "contract_version": LUXIAN_0609_059_SHADOW_CONTRACT_VERSION,
    }


async def run_luxian_0609_059_shadow(
    *,
    enabled: bool,
    selected_rule_ids: Sequence[str],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    evidence_materials: Luxian0609EvidenceMaterialStore | None,
    llm_client: Any,
) -> dict[str, Any] | None:
    normalized_rule_ids = {
        str(rule_id or "").strip().upper() for rule_id in selected_rule_ids
    }
    coordinates = (institute_id, patient_id, visit_id)
    if (
        not enabled
        or _RULE_ID not in normalized_rule_ids
        or not all(isinstance(value, str) and value.strip() for value in coordinates)
        or evidence_materials is None
    ):
        return None
    started = perf_counter()
    try:
        events, orders, course_notes, source_readiness = _adapt_materials(
            evidence_materials
        )
    except Exception:
        return _safe_error(
            "adapter_failed", elapsed_ms=round((perf_counter() - started) * 1000)
        )
    try:
        result = await evaluate_lx0609_059_treatment_order_consistency(
            events=events,
            orders=orders,
            course_notes=course_notes,
            source_readiness=source_readiness,
            llm_client=llm_client,
            redaction_terms=coordinates,
        )
    except Exception:
        return _safe_error(
            "evaluation_failed", elapsed_ms=round((perf_counter() - started) * 1000)
        )
    elapsed_ms = round((perf_counter() - started) * 1000)
    try:
        return _safe_summary(result, event_count=len(events), elapsed_ms=elapsed_ms)
    except (TypeError, ValueError):
        return _safe_error("result_contract_invalid", elapsed_ms=elapsed_ms)


__all__ = [
    "LUXIAN_0609_059_SHADOW_CONTRACT_VERSION",
    "run_luxian_0609_059_shadow",
]
