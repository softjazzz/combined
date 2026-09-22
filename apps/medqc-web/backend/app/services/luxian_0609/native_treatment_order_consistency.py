"""LX0609-05-03-01 诊疗事件、医嘱与病程一致性的事件级事实执行器。

本模块只负责一个冻结的小闭环：先用结构化业务键将实际发生的诊疗事件
与医嘱一一关联，再用至多一次受控模型调用判断病程是否记录了同一事件。
禁止用疾病推导应有医嘱、关键词共现或最近时间替代事件关联。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import hashlib
import json
import math
import re
import secrets
from typing import Any, Callable, Mapping, Protocol, Sequence


_MAX_CONTEXT_CHARS = 12_000
_MAX_PROMPT_TOKENS = 4_096
_MAX_COMPLETION_TOKENS = 512
_ALLOWED_EVENT_KINDS = frozenset(
    {
        "performed_exam",
        "performed_procedure",
        "performed_surgery",
        "drug_order_action",
        "nondrug_order_action",
    }
)
_DETERMINISTIC_ORDER_ACTIONS = frozenset(
    {
        "performed",
        "execute",
        "executed",
        "start",
        "started",
        "stop",
        "stopped",
        "adjust",
        "adjusted",
        "administer",
        "administered",
        "执行",
        "已执行",
        "开始",
        "已开始",
        "停止",
        "已停止",
        "调整",
        "已调整",
        "给药",
        "已给药",
    }
)
_SEMANTIC_VERDICTS = frozenset(
    {"consistent", "conflict", "not_documented", "ambiguous"}
)
_DATA_GAP_REASON_PRIORITY = (
    "event_source_ref_missing",
    "order_source_ref_missing",
    "order_association_conflict",
    "order_association_ambiguous",
    "order_reused_across_events",
    "order_association_key_missing",
    "order_association_unresolved",
    "event_time_missing",
    "order_time_missing",
    "order_action_unknown",
)


class TreatmentOrderConsistencyLLM(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]: ...


class SourceReadiness(str, Enum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    TRUNCATED = "truncated"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TreatmentEvent:
    event_id: str
    event_kind: str
    event_time: datetime | None
    description: str
    source_ref: str
    order_id: str = ""
    application_id: str = ""
    event_code: str = ""
    actual: bool = True


@dataclass(frozen=True, slots=True)
class TreatmentOrder:
    order_id: str
    application_id: str
    event_code: str
    action: str
    status: str
    order_time: datetime | None
    description: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class CourseNote:
    note_id: str
    note_time: datetime | None
    text: str
    source_ref: str


@dataclass(frozen=True, slots=True)
class TreatmentEventResult:
    event_id: str
    event_ref: str
    order_id: str = ""
    order_ref: str = ""
    order_state: str = "unknown"
    semantic_verdict: str = ""
    course_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TreatmentOrderConsistencyResult:
    final_state: str
    reason_code: str
    event_results: tuple[TreatmentEventResult, ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def _result(
    final_state: str,
    reason_code: str,
    *,
    event_results: Sequence[TreatmentEventResult] = (),
    llm_call_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> TreatmentOrderConsistencyResult:
    return TreatmentOrderConsistencyResult(
        final_state=final_state,
        reason_code=reason_code,
        event_results=tuple(event_results),
        llm_call_count=llm_call_count,
        prompt_tokens=max(0, prompt_tokens),
        completion_tokens=max(0, completion_tokens),
    )


def _readiness_failure(
    readiness: Mapping[str, SourceReadiness],
) -> tuple[str, str] | None:
    for source_name in ("events", "orders", "course_notes"):
        state = readiness.get(source_name, SourceReadiness.UNAVAILABLE)
        try:
            normalized = SourceReadiness(state)
        except ValueError:
            return "technical_error", f"{source_name}_source_state_invalid"
        if normalized is SourceReadiness.ERROR:
            return "technical_error", f"{source_name}_source_query_error"
        if normalized in {SourceReadiness.UNAVAILABLE, SourceReadiness.TRUNCATED}:
            return "data_gap", f"{source_name}_source_{normalized.value}"
    return None


def _primary_data_gap_reason(reasons: Sequence[str]) -> str:
    reason_set = frozenset(reasons)
    for reason in _DATA_GAP_REASON_PRIORITY:
        if reason in reason_set:
            return reason
    return min(reason_set)


def _datetime_sort_value(value: datetime | None) -> str:
    return value.isoformat() if value is not None else "\uffff"


def _event_sort_key(event: TreatmentEvent) -> tuple[str, ...]:
    return (
        _datetime_sort_value(event.event_time),
        event.event_kind.strip(),
        event.order_id.strip(),
        event.application_id.strip(),
        event.event_code.strip(),
        event.event_id.strip(),
        event.source_ref.strip(),
    )


def _normalize_course_notes(
    notes: Sequence[CourseNote],
) -> tuple[str | None, tuple[CourseNote, ...]]:
    by_source_ref: dict[str, CourseNote] = {}
    for note in notes:
        source_ref = note.source_ref.strip()
        existing = by_source_ref.get(source_ref)
        if existing is None:
            by_source_ref[source_ref] = note
            continue
        if (existing.note_time, existing.text) != (note.note_time, note.text):
            return "course_source_ref_conflict", ()
        by_source_ref[source_ref] = min(
            (existing, note), key=lambda item: item.note_id.strip()
        )
    normalized = tuple(
        sorted(
            by_source_ref.values(),
            key=lambda note: (
                _datetime_sort_value(note.note_time),
                note.source_ref.strip(),
                note.note_id.strip(),
            ),
        )
    )
    return None, normalized


def _order_identity(order: TreatmentOrder) -> tuple[str, str, str]:
    return (
        order.order_id.strip(),
        order.application_id.strip(),
        order.event_code.strip(),
    )


def _order_semantics(
    order: TreatmentOrder,
) -> tuple[str, str, datetime | None, str]:
    return (
        order.action.strip(),
        order.status.strip(),
        order.order_time,
        order.description.strip(),
    )


def _resolve_order_association(
    event: TreatmentEvent,
    orders: Sequence[TreatmentOrder],
) -> tuple[str, TreatmentOrder | None]:
    """使用全部非空业务键解析一个唯一医嘱，禁止优先级掩盖键冲突。"""

    selectors: list[tuple[str, str]] = []
    if event.order_id.strip():
        selectors.append(("order_id", event.order_id.strip()))
    if event.application_id.strip():
        selectors.append(("application_id", event.application_id.strip()))
    if event.event_code.strip():
        selectors.append(("event_code", event.event_code.strip()))
    if not selectors:
        return "unresolved", None

    unique_by_selector: list[dict[tuple[str, str, str], TreatmentOrder]] = []
    for field_name, expected in selectors:
        candidates: dict[tuple[str, str, str], TreatmentOrder] = {}
        duplicate_conflict = False
        for order in orders:
            if str(getattr(order, field_name) or "").strip() != expected:
                continue
            identity = _order_identity(order)
            existing = candidates.get(identity)
            if existing is not None:
                if _order_semantics(existing) != _order_semantics(order):
                    duplicate_conflict = True
                    continue
                # 同一业务医嘱可能由多张来源表提供。语义完全一致时只稳定折叠，
                # source_ref 不参与业务身份，也不得让输入顺序改变结果。
                candidates[identity] = min(
                    (existing, order), key=lambda item: item.source_ref.strip()
                )
                continue
            candidates[identity] = order
        if duplicate_conflict:
            return "conflict", None
        unique_by_selector.append(candidates)

    nonempty = [candidates for candidates in unique_by_selector if candidates]
    if not nonempty:
        return "missing", None
    # 一个非空键能命中而另一个非空键不能命中，也是不一致的业务身份。
    if len(nonempty) != len(unique_by_selector):
        return "conflict", None
    identities = set.intersection(*(set(candidates) for candidates in nonempty))
    if not identities:
        return "conflict", None
    if len(identities) > 1:
        return "ambiguous", None
    identity = next(iter(identities))
    return "matched", nonempty[0][identity]


def _default_token_counter(text: str) -> int:
    # 这里只是调用前的防御预算，不替代模型供应方返回的真实 usage。
    return math.ceil(len(text) / 2)


def _prompt_for(
    event_payloads: Sequence[Mapping[str, Any]],
    course_payloads: Sequence[Mapping[str, Any]],
) -> str:
    payload = {
        "events": list(event_payloads),
        "course_notes": list(course_payloads),
    }
    return (
        "你是病历事实提取器。逐个判断每个已发生诊疗事件及其已关联医嘱，"
        "是否在给定病程中记录为同一次事件。不得用疾病、药名共现或时间接近猜测关联。\n"
        "只返回 JSON：{\"events\":[{\"event_ref\":给定的不透明引用,"
        "\"verdict\":\"consistent|conflict|not_documented|ambiguous\","
        "\"course_refs\":[给定的不透明course_ref]}]}。每个 event_ref 必须且只能出现一次；"
        f"输出不得超过 {_MAX_COMPLETION_TOKENS} tokens。\n输入："
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _usage(response: Mapping[str, Any]) -> tuple[int, int] | None:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return None
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if (
        isinstance(prompt_tokens, bool)
        or not isinstance(prompt_tokens, int)
        or prompt_tokens < 0
        or isinstance(completion_tokens, bool)
        or not isinstance(completion_tokens, int)
        or completion_tokens < 0
    ):
        return None
    return prompt_tokens, completion_tokens


def _collect_redaction_terms(
    *,
    events: Sequence[TreatmentEvent],
    orders: Sequence[TreatmentOrder],
    course_notes: Sequence[CourseNote],
    explicit_terms: Sequence[str] | str,
) -> tuple[str, ...]:
    raw_terms: list[str] = []
    if isinstance(explicit_terms, str):
        raw_terms.append(explicit_terms)
    else:
        raw_terms.extend(term for term in explicit_terms if isinstance(term, str))
    for event in events:
        raw_terms.extend(
            (
                event.event_id,
                event.source_ref,
                event.order_id,
                event.application_id,
                event.event_code,
            )
        )
    for order in orders:
        raw_terms.extend(
            (
                order.order_id,
                order.application_id,
                order.event_code,
                order.source_ref,
            )
        )
    for note in course_notes:
        raw_terms.extend((note.note_id, note.source_ref))
    # 先替换长串，避免短ID破坏三坐标后留下可识别残片。
    return tuple(
        sorted({term.strip() for term in raw_terms if term.strip()}, key=len, reverse=True)
    )


def _explicit_redaction_terms(
    terms: Sequence[str] | str,
) -> tuple[str, ...] | None:
    if isinstance(terms, str):
        normalized = (terms.strip(),) if terms.strip() else ()
    else:
        normalized = tuple(
            term.strip()
            for term in terms
            if isinstance(term, str) and term.strip()
        )
    return normalized or None


def _redact(text: str, terms: Sequence[str]) -> str:
    redacted = text
    for term in terms:
        redacted = redacted.replace(term, "[已脱敏]")
    return redacted


def _semantic_payload(response: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """兼容系统 LLM 客户端的 OpenAI 响应壳，但只接受单个 JSON 对象。"""

    if isinstance(response.get("events"), list):
        return response
    text = ""
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            text = str(message.get("content") or "")
    if not text:
        text = str(response.get("content") or response.get("text") or "")
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE
    ).strip()
    match = re.fullmatch(r"(?:```json\s*)?(\{[\s\S]*\})(?:\s*```)?", cleaned)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(1))
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _validate_semantic_response(
    response: Mapping[str, Any],
    *,
    expected_event_refs: frozenset[str],
    allowed_course_refs: frozenset[str],
) -> dict[str, tuple[str, tuple[str, ...]]] | None:
    rows = response.get("events")
    if not isinstance(rows, list) or len(rows) != len(expected_event_refs):
        return None
    parsed: dict[str, tuple[str, tuple[str, ...]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        event_ref = row.get("event_ref")
        verdict = row.get("verdict")
        refs = row.get("course_refs")
        if (
            not isinstance(event_ref, str)
            or event_ref not in expected_event_refs
            or event_ref in parsed
            or verdict not in _SEMANTIC_VERDICTS
            or not isinstance(refs, list)
            or any(not isinstance(ref, str) for ref in refs)
            or len(refs) != len(set(refs))
            or any(ref not in allowed_course_refs for ref in refs)
        ):
            return None
        if verdict in {"consistent", "conflict"} and not refs:
            return None
        if verdict == "not_documented" and refs:
            return None
        parsed[event_ref] = (verdict, tuple(refs))
    return parsed if frozenset(parsed) == expected_event_refs else None


def _opaque_ref(kind: str, index: int, raw_identity: str, request_salt: bytes) -> str:
    """生成仅在本次请求内可关联、不能还原业务主键的不透明引用。"""

    digest = hashlib.sha256(
        request_salt + b"\0" + kind.encode("ascii") + b"\0"
        + str(index).encode("ascii") + b"\0" + raw_identity.encode("utf-8")
    ).hexdigest()[:24]
    return f"{kind}_{digest}"


async def evaluate_lx0609_059_treatment_order_consistency(
    *,
    events: Sequence[TreatmentEvent],
    orders: Sequence[TreatmentOrder],
    course_notes: Sequence[CourseNote],
    source_readiness: Mapping[str, SourceReadiness],
    llm_client: TreatmentOrderConsistencyLLM,
    token_counter: Callable[[str], int] | None = None,
    redaction_terms: Sequence[str] | str = (),
) -> TreatmentOrderConsistencyResult:
    """计算 LX0609-05-03-01 的事件级事实，调用模型不超过一次。"""

    readiness_failure = _readiness_failure(source_readiness)
    if readiness_failure is not None:
        return _result(*readiness_failure)

    actual_candidates = sorted(
        (event for event in events if event.actual), key=_event_sort_key
    )
    unsupported_events = [
        event
        for event in actual_candidates
        if event.event_kind not in _ALLOWED_EVENT_KINDS
    ]
    if unsupported_events:
        return _result(
            "data_gap",
            "event_kind_unsupported",
            event_results=[
                TreatmentEventResult(
                    event_id=event.event_id,
                    event_ref=event.source_ref,
                    order_state="unresolved",
                )
                for event in unsupported_events
            ],
        )
    actual_events = actual_candidates
    if not actual_events:
        return _result("not_applicable", "trigger_absent_complete")
    if any(not event.event_id.strip() for event in actual_events):
        return _result("data_gap", "event_id_missing")
    if len({event.event_id for event in actual_events}) != len(actual_events):
        return _result("data_gap", "event_id_duplicated")
    pairs: list[tuple[TreatmentEvent, TreatmentOrder]] = []
    event_results: list[TreatmentEventResult] = []
    claimed_order_keys: set[str] = set()
    data_gap_reasons: list[str] = []
    has_missing_order = False
    for event in actual_events:
        if not event.source_ref.strip():
            data_gap_reasons.append("event_source_ref_missing")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_state="unresolved",
            ))
            continue
        if event.event_time is None:
            data_gap_reasons.append("event_time_missing")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_state="unresolved",
            ))
            continue
        association_state, order = _resolve_order_association(event, orders)
        if association_state == "unresolved":
            data_gap_reasons.append("order_association_key_missing")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_state="unresolved",
            ))
            continue
        if association_state == "ambiguous":
            data_gap_reasons.append("order_association_ambiguous")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_state="ambiguous",
            ))
            continue
        if association_state == "conflict":
            data_gap_reasons.append("order_association_conflict")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_state="conflict",
            ))
            continue
        if association_state == "missing":
            has_missing_order = True
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_state="missing",
            ))
            continue
        if order is None:
            data_gap_reasons.append("order_association_unresolved")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_state="unresolved",
            ))
            continue
        if not order.source_ref.strip():
            data_gap_reasons.append("order_source_ref_missing")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_id=order.order_id,
                order_state="unresolved",
            ))
            continue
        stable_order_key = "\0".join(_order_identity(order))
        if not stable_order_key or stable_order_key in claimed_order_keys:
            data_gap_reasons.append("order_reused_across_events")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_id=order.order_id,
                order_ref=order.source_ref,
                order_state="conflict",
            ))
            continue
        claimed_order_keys.add(stable_order_key)
        if order.order_time is None:
            data_gap_reasons.append("order_time_missing")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_id=order.order_id,
                order_ref=order.source_ref,
                order_state="unresolved",
            ))
            continue
        if order.action.strip().lower() not in _DETERMINISTIC_ORDER_ACTIONS:
            data_gap_reasons.append("order_action_unknown")
            event_results.append(TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_id=order.order_id,
                order_ref=order.source_ref,
                order_state="unresolved",
            ))
            continue
        pairs.append((event, order))
        event_results.append(
            TreatmentEventResult(
                event_id=event.event_id,
                event_ref=event.source_ref,
                order_id=order.order_id,
                order_ref=order.source_ref,
                order_state="matched",
            )
        )

    if data_gap_reasons:
        return _result(
            "data_gap",
            _primary_data_gap_reason(data_gap_reasons),
            event_results=event_results,
        )
    if has_missing_order:
        return _result(
            "non_compliant",
            "required_order_missing",
            event_results=event_results,
        )

    substantive_course_notes = [note for note in course_notes if note.text.strip()]
    if not substantive_course_notes:
        return _result(
            "non_compliant",
            "course_documentation_missing",
            event_results=event_results,
        )
    if any(not note.source_ref.strip() for note in substantive_course_notes):
        return _result("data_gap", "course_source_ref_missing")
    course_failure, normalized_course_notes = _normalize_course_notes(
        substantive_course_notes
    )
    if course_failure is not None:
        return _result(
            "data_gap",
            course_failure,
            event_results=event_results,
        )
    substantive_course_notes = list(normalized_course_notes)
    context_chars = sum(len(note.text) for note in substantive_course_notes)
    if context_chars > _MAX_CONTEXT_CHARS:
        return _result("data_gap", "llm_context_oversized")

    explicit_redaction_terms = _explicit_redaction_terms(redaction_terms)
    if explicit_redaction_terms is None:
        return _result("technical_error", "redaction_terms_missing")

    request_salt = secrets.token_bytes(32)
    prompt_redaction_terms = _collect_redaction_terms(
        events=actual_events,
        orders=orders,
        course_notes=substantive_course_notes,
        explicit_terms=explicit_redaction_terms,
    )
    opaque_event_by_id: dict[str, str] = {}
    original_event_id_by_opaque: dict[str, str] = {}
    event_payloads: list[dict[str, Any]] = []
    for index, (event, order) in enumerate(pairs):
        event_ref = _opaque_ref(
            "evt", index, f"{event.event_id}\0{event.source_ref}", request_salt
        )
        order_ref = _opaque_ref(
            "ord", index, f"{order.order_id}\0{order.source_ref}", request_salt
        )
        opaque_event_by_id[event.event_id] = event_ref
        original_event_id_by_opaque[event_ref] = event.event_id
        event_payloads.append(
            {
                "event_ref": event_ref,
                "event_kind": event.event_kind,
                "event_time": event.event_time.isoformat() if event.event_time else None,
                "event_description": _redact(
                    event.description, prompt_redaction_terms
                ),
                "order_ref": order_ref,
                "order_time": order.order_time.isoformat() if order.order_time else None,
                "order_action": order.action,
                "order_description": _redact(
                    order.description, prompt_redaction_terms
                ),
            }
        )
    original_course_by_opaque: dict[str, str] = {}
    course_payloads: list[dict[str, Any]] = []
    for index, note in enumerate(substantive_course_notes):
        course_ref = _opaque_ref(
            "course", index, f"{note.note_id}\0{note.source_ref.strip()}", request_salt
        )
        original_course_by_opaque[course_ref] = note.source_ref.strip()
        course_payloads.append(
            {
                "course_ref": course_ref,
                "note_time": note.note_time.isoformat() if note.note_time else None,
                "text": _redact(note.text, prompt_redaction_terms),
            }
        )
    prompt = _prompt_for(event_payloads, course_payloads)
    count_tokens = token_counter or _default_token_counter
    try:
        estimated_prompt_tokens = count_tokens(prompt)
    except (TypeError, ValueError, OverflowError):
        return _result("technical_error", "llm_token_count_invalid")
    if (
        isinstance(estimated_prompt_tokens, bool)
        or not isinstance(estimated_prompt_tokens, int)
        or estimated_prompt_tokens < 0
    ):
        return _result("technical_error", "llm_token_count_invalid")
    if estimated_prompt_tokens > _MAX_PROMPT_TOKENS:
        return _result("data_gap", "llm_prompt_token_limit_exceeded")

    try:
        response = await llm_client.generate(
            prompt,
            max_completion_tokens=_MAX_COMPLETION_TOKENS,
            allow_length_retry=False,
        )
    except Exception:
        return _result("technical_error", "llm_transport_error", llm_call_count=1)
    if not isinstance(response, Mapping):
        return _result("technical_error", "llm_response_invalid", llm_call_count=1)

    usage = _usage(response)
    if usage is None:
        return _result("technical_error", "llm_usage_invalid", llm_call_count=1)
    prompt_tokens, completion_tokens = usage
    if prompt_tokens > _MAX_PROMPT_TOKENS:
        return _result(
            "technical_error",
            "llm_usage_prompt_token_limit_exceeded",
            llm_call_count=1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    if completion_tokens > _MAX_COMPLETION_TOKENS:
        return _result(
            "technical_error",
            "llm_output_token_limit_exceeded",
            llm_call_count=1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    response_payload = _semantic_payload(response)
    semantic = _validate_semantic_response(
        response_payload or {},
        expected_event_refs=frozenset(original_event_id_by_opaque),
        allowed_course_refs=frozenset(original_course_by_opaque),
    )
    if semantic is None:
        return _result(
            "technical_error",
            "llm_response_invalid",
            llm_call_count=1,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    resolved_results: list[TreatmentEventResult] = []
    verdicts: list[str] = []
    for base in event_results:
        verdict, opaque_refs = semantic[opaque_event_by_id[base.event_id]]
        refs = tuple(original_course_by_opaque[ref] for ref in opaque_refs)
        verdicts.append(verdict)
        resolved_results.append(
            TreatmentEventResult(
                event_id=base.event_id,
                event_ref=base.event_ref,
                order_id=base.order_id,
                order_ref=base.order_ref,
                order_state=base.order_state,
                semantic_verdict=verdict,
                course_refs=refs,
            )
        )

    common = {
        "event_results": resolved_results,
        "llm_call_count": 1,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if "conflict" in verdicts:
        return _result("non_compliant", "course_documentation_conflict", **common)
    if "not_documented" in verdicts:
        return _result("non_compliant", "course_documentation_missing", **common)
    if "ambiguous" in verdicts:
        return _result("evaluation_unknown", "semantic_association_ambiguous", **common)
    return _result("compliant", "requirement_satisfied", **common)


__all__ = [
    "CourseNote",
    "SourceReadiness",
    "TreatmentEvent",
    "TreatmentEventResult",
    "TreatmentOrder",
    "TreatmentOrderConsistencyResult",
    "evaluate_lx0609_059_treatment_order_consistency",
]
