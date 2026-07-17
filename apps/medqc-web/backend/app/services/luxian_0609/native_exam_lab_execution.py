"""LX0609 检查检验族原生执行：事实门控后逐规则使用客户提示词。"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Protocol, Sequence

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot, SourceCompleteness
from .native_execution import build_luxian_0609_native_result


EXAM_LAB_RULE_IDS = (
    "LX0609-010",
    "LX0609-011",
    "LX0609-012",
    "LX0609-014",
    "LX0609-015",
)
EXAM_RULE_IDS = frozenset({"LX0609-010", "LX0609-011", "LX0609-012"})
CULTURE_RULE_IDS = frozenset({"LX0609-014", "LX0609-015"})
EXECUTOR_KEY = "exam_lab"
_TYPED_DECISION_RULE_IDS = frozenset(EXAM_LAB_RULE_IDS)
_TYPED_EVALUATOR_VERSION = "exam-lab-ruledecision-shadow-v1"

_EXAM_SOURCE_KEYS = ("exam_master", "exam_item_report")
_CULTURE_SOURCE_KEYS = ("labtest_master", "labtest_item_report")
_COURSE_SOURCE_KEYS = (
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
)
_MAX_ROWS_PER_SOURCE = 6
_MAX_ROW_CHARS = 1200
_MAX_CONTEXT_CHARS = 12000
_EXAM_FACT_TYPE = "current_visit_ct_mri_exam"
_CULTURE_FACT_TYPE = "current_visit_culture_or_ast"
_PRESENT_FACT_STATES = frozenset({"present", "performed", "available", "positive"})
_ABSENT_FACT_STATES = frozenset({"explicit_negative", "absent", "not_present"})
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)

_TYPED_TRIGGER_SOURCES = {
    "exam": ("exam_master", "exam_item_report"),
    "culture": ("labtest_master", "labtest_item_report"),
}
_TYPED_RULE_SOURCE_KEYS = {
    "LX0609-010": (*_TYPED_TRIGGER_SOURCES["exam"], *_COURSE_SOURCE_KEYS),
    "LX0609-011": (*_TYPED_TRIGGER_SOURCES["exam"], *_COURSE_SOURCE_KEYS),
    "LX0609-012": (*_TYPED_TRIGGER_SOURCES["exam"], *_COURSE_SOURCE_KEYS),
    "LX0609-014": (*_TYPED_TRIGGER_SOURCES["culture"], *_COURSE_SOURCE_KEYS),
    "LX0609-015": (*_TYPED_TRIGGER_SOURCES["culture"], *_COURSE_SOURCE_KEYS),
}
_EXAM_CONTROLLED_FIELDS = (
    "exam_type",
    "modality",
    "exam_name",
    "item_name",
    "exam_item_name",
    "exam_result",
    "exam_impression",
    "exam_conclusion",
)
_CULTURE_CONTROLLED_FIELDS = (
    "lab_type",
    "test_type",
    "subject",
    "labtest_subject",
    "item_name",
    "lab_item_name",
)
_EXAM_TRIGGER_PATTERN = re.compile(
    r"(?:^|[^A-Z])(?:CT|MRI)(?:$|[^A-Z])|计算机断层|磁共振",
    flags=re.IGNORECASE,
)
_CULTURE_TRIGGER_PATTERN = re.compile(r"(?:细菌|真菌|血|痰|尿|分泌物)?培养|药敏")

_CONTROLLED_MESSAGES = {
    "compliant": ("检查检验相关记录满足该项要求。", ""),
    "non_compliant": ("检查检验相关记录未满足该项要求。", "请按该质控点要求补充或修正相关记录。"),
    "not_applicable": ("当前就诊未发现该项适用的检查检验事实。", ""),
    "data_gap": ("当前检查检验资料不足，暂不能形成可靠结论。", "请补齐相关检查检验资料后重新质控。"),
}


class ExamLabLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class NativeExamLabExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


@dataclass(frozen=True)
class _TypedSource:
    state: str
    rows: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class _ExamLabOutcome:
    rule_id: str
    status: str
    reason_code: str


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _documents(evidence_payload: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, Mapping):
        return None
    documents = timeline.get("documents")
    return documents if isinstance(documents, Mapping) else None


def _timeline_facts(evidence_payload: Mapping[str, Any] | None) -> Sequence[Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    facts = evidence_payload.get("timeline_facts")
    return facts if isinstance(facts, list) else None


def _row_text(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("content")
        or row.get("record_content")
        or row.get("raw_text")
        or row.get("content_preview")
        or row.get("text_preview")
    )


def _source_rows(
    documents: Mapping[str, Any], source_keys: Sequence[str]
) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    for source_key in source_keys:
        raw_rows = documents.get(source_key)
        if not isinstance(raw_rows, list):
            continue
        for index, raw_row in enumerate(raw_rows[:_MAX_ROWS_PER_SOURCE], start=1):
            if not isinstance(raw_row, Mapping):
                continue
            content = _row_text(raw_row)
            if content:
                rows.append((source_key, index, content[:_MAX_ROW_CHARS]))
    return rows


def _fact_state(
    facts: Sequence[Any], fact_type: str, source_keys: Sequence[str]
) -> str:
    approved_sources = frozenset(source_keys)
    observed_present = False
    observed_absent = False
    for raw_fact in facts:
        if not isinstance(raw_fact, Mapping):
            continue
        actual_type = str(raw_fact.get("fact_type") or "").strip().lower()
        state = str(raw_fact.get("state") or "").strip().lower()
        source_key = str(raw_fact.get("source_key") or "").strip().lower()
        if (
            actual_type != fact_type
            or source_key not in approved_sources
            or raw_fact.get("current_visit_bound") is not True
        ):
            continue
        if state in _PRESENT_FACT_STATES:
            observed_present = True
        elif state in _ABSENT_FACT_STATES:
            observed_absent = True
    if observed_present and not observed_absent:
        return "present"
    if observed_present and observed_absent:
        return "unknown"
    return "absent" if observed_absent else "unknown"


def _typed_source(
    *,
    source_key: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> _TypedSource:
    observation = next(
        (item for item in snapshot.observations if item.source_key == source_key),
        None,
    )
    if observation is None:
        return _TypedSource("missing")
    if observation.query_state.value in {"unavailable", "error"}:
        return _TypedSource(observation.query_state.value)
    if observation.completeness is SourceCompleteness.TRUNCATED:
        return _TypedSource("truncated")
    try:
        rows = materials.rows(source_key)
    except EvidenceMaterialTruncated:
        return _TypedSource("truncated")
    except EvidenceMaterialUnavailable:
        return _TypedSource("error")
    selected = tuple(row for row in rows if isinstance(row, Mapping))
    return _TypedSource("present" if selected else "empty", selected)


def _snapshot_fact_state(
    snapshot: Luxian0609EvidenceSnapshot,
    *,
    fact_type: str,
    source_keys: Sequence[str],
) -> str:
    approved_sources = frozenset(source_keys)
    states: set[str] = set()
    for fact in snapshot.facts:
        if fact.fact_type != fact_type or fact.source_key not in approved_sources:
            continue
        if fact.current_visit_relevance.value != "relevant":
            continue
        if fact.assertion.value == "affirmed":
            states.add("present")
        elif fact.assertion.value == "negated":
            states.add("absent")
    if states == {"present"}:
        return "present"
    if states == {"absent"}:
        return "absent"
    return "unknown"


def _controlled_trigger_from_rows(
    *,
    fact_kind: str,
    sources: Sequence[_TypedSource],
) -> bool:
    fields = _EXAM_CONTROLLED_FIELDS if fact_kind == "exam" else _CULTURE_CONTROLLED_FIELDS
    pattern = _EXAM_TRIGGER_PATTERN if fact_kind == "exam" else _CULTURE_TRIGGER_PATTERN
    for source in sources:
        for row in source.rows:
            for field in fields:
                value = _clean(row.get(field))
                if value and pattern.search(value):
                    return True
    return False


def _typed_trigger_state(
    *,
    fact_kind: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, dict[str, _TypedSource]]:
    source_keys = _TYPED_TRIGGER_SOURCES[fact_kind]
    fact_type = _EXAM_FACT_TYPE if fact_kind == "exam" else _CULTURE_FACT_TYPE
    loaded = {
        source_key: _typed_source(
            source_key=source_key,
            snapshot=snapshot,
            materials=materials,
        )
        for source_key in source_keys
    }
    if any(source.state == "error" for source in loaded.values()):
        return "error", loaded
    if any(
        source.state in {"unavailable", "truncated", "missing"}
        for source in loaded.values()
    ):
        source_gap = True
    else:
        source_gap = False

    fact_state = _snapshot_fact_state(
        snapshot,
        fact_type=fact_type,
        source_keys=source_keys,
    )
    row_trigger = _controlled_trigger_from_rows(
        fact_kind=fact_kind,
        sources=tuple(loaded.values()),
    )
    if fact_state == "present":
        return "present", loaded
    if fact_state == "absent":
        return ("unknown" if row_trigger else "absent"), loaded
    if row_trigger:
        return "present", loaded
    if source_gap:
        return "unavailable", loaded
    if all(source.state == "empty" for source in loaded.values()):
        return "absent", loaded
    # 有通用检查/检验行但没有受控 CT/MRI 或培养/药敏触发，不得把沉默当临床否定。
    return "unknown", loaded


def _typed_context(
    *,
    fact_kind: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, str]:
    source_keys = (*_TYPED_TRIGGER_SOURCES[fact_kind], *_COURSE_SOURCE_KEYS)
    parts: list[str] = []
    for source_key in source_keys:
        material = _typed_source(
            source_key=source_key,
            snapshot=snapshot,
            materials=materials,
        )
        if material.state == "error":
            return "", "error"
        if material.state in {"unavailable", "truncated", "missing"}:
            return "", "unavailable"
        for index, row in enumerate(material.rows[:_MAX_ROWS_PER_SOURCE], start=1):
            if source_key in _TYPED_TRIGGER_SOURCES[fact_kind]:
                fields = (
                    _EXAM_CONTROLLED_FIELDS
                    if fact_kind == "exam"
                    else _CULTURE_CONTROLLED_FIELDS
                )
                # 报告结果与时间只在受控键白名单内进入裁剪上下文。
                fields = (*fields, "report_time", "report_datetime", "result", "conclusion", "impression")
                text = _clean(" ".join(_clean(row.get(key)) for key in fields if _clean(row.get(key))))
            else:
                text = _row_text(row)
                record_time = _clean(row.get("record_time"))
                if record_time:
                    text = f"记录时间={record_time} {text}".strip()
            if text:
                parts.append(f"[{source_key}-{index}] {text[:_MAX_ROW_CHARS]}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS], "present"


def _decision_from_outcome(
    *,
    outcome: _ExamLabOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision:
    refs = tuple(
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in _TYPED_RULE_SOURCE_KEYS[outcome.rule_id]
    )
    if outcome.status == "compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
        )
    elif outcome.status == "non_compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        )
    elif outcome.status == "data_gap":
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_unavailable"
            if "unavailable" in outcome.reason_code
            else "required_field_missing",
        )
    elif outcome.status == "evaluation_unknown":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "semantic_output_unknown",
        )
    elif outcome.status == "technical_error":
        reason_code = (
            "source_query_error"
            if outcome.reason_code == "source_query_error"
            else "model_invalid_output"
            if outcome.reason_code == "exam_lab_llm_invalid_output"
            else "model_transport_error"
            if outcome.reason_code == "exam_lab_llm_failure"
            else "executor_exception"
        )
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            reason_code,
        )
    else:
        raise ValueError("unsupported exam lab outcome")
    applicability, evidence_state, qc_direction, reason_code = dimensions
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=_TYPED_EVALUATOR_VERSION,
        confidence=None,
    )


def _context(documents: Mapping[str, Any], *, fact_kind: str) -> str:
    trigger_sources = _EXAM_SOURCE_KEYS if fact_kind == "exam" else _CULTURE_SOURCE_KEYS
    parts: list[str] = []
    for source_key, index, content in _source_rows(documents, trigger_sources):
        parts.append(f"[{source_key}-{index}] {content}")
    for source_key, index, content in _source_rows(documents, _COURSE_SOURCE_KEYS):
        parts.append(f"[{source_key}-{index}] {content}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _prompt(wrapper: Mapping[str, Any], *, context: str) -> str:
    custom_prompt = str(wrapper.get("custom_prompt") or "")
    custom_prompt = _MAPPING_LINE_PATTERN.sub("", custom_prompt)
    custom_prompt = custom_prompt.replace(
        "{defect_level}", str(wrapper.get("defect_level") or "")
    ).replace("{medical_text}", context)
    return custom_prompt.strip()


def _response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _parse_is_compliant(response: Mapping[str, Any]) -> bool | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>", "", _response_text(response), flags=re.IGNORECASE
    ).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    value = payload.get("is_compliant") if isinstance(payload, Mapping) else None
    return value if isinstance(value, bool) else None


def _usage(response: Mapping[str, Any]) -> tuple[int, int, int, float]:
    usage = response.get("usage")
    usage = usage if isinstance(usage, Mapping) else {}
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or prompt + completion)
    return prompt, completion, total, float(response.get("_api_time") or 0.0)


def _result(rule_id: str, status: str, reason_code: str, *, executor_type: str) -> dict[str, Any]:
    item = build_luxian_0609_native_result(
        rule_id=rule_id,
        final_state=status,
        finding_kind="requirement_satisfied" if status == "compliant" else status,
        reason_code=reason_code,
    )
    findings, suggestion = _CONTROLLED_MESSAGES[status]
    item["findings"] = findings
    item["suggestion"] = suggestion
    metadata = dict(item.get("metadata") or {})
    metadata["executor_type"] = executor_type
    item["metadata"] = metadata
    return item


async def execute_luxian_0609_native_exam_lab_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    llm_client: ExamLabLLMClient | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeExamLabExecutionResult:
    """按客户目录顺序执行；未通过事实门控的规则不调用模型。"""

    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(rule_id for rule_id in EXAM_LAB_RULE_IDS if rule_id in requested)
    normalized_decision_ids = tuple(
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    )
    if len(normalized_decision_ids) != len(set(normalized_decision_ids)):
        raise ValueError("duplicate typed exam lab rule scope")
    typed_requested = set(normalized_decision_ids)
    if (
        not typed_requested.issubset(_TYPED_DECISION_RULE_IDS)
        or not typed_requested.issubset(set(selected))
    ):
        raise ValueError("unsupported typed exam lab rule scope")
    if typed_requested and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed exam lab rules require one evidence session")
    if not selected:
        return NativeExamLabExecutionResult((), ())

    documents = _documents(evidence_payload)
    timeline_facts = _timeline_facts(evidence_payload)
    exam_state = _fact_state(timeline_facts or (), _EXAM_FACT_TYPE, _EXAM_SOURCE_KEYS)
    culture_state = _fact_state(
        timeline_facts or (), _CULTURE_FACT_TYPE, _CULTURE_SOURCE_KEYS
    )
    wrappers_by_id: dict[str, Mapping[str, Any]] = {}
    for wrapper in wrapper_rules:
        if not isinstance(wrapper, Mapping):
            continue
        wrapper_id = str(wrapper.get("rule_id") or wrapper.get("rule_code") or "").strip().upper()
        if wrapper_id in wrappers_by_id and wrapper_id in typed_requested:
            raise ValueError("duplicate typed exam lab wrapper")
        wrappers_by_id[wrapper_id] = wrapper

    results: list[dict[str, Any]] = []
    decisions: list[RuleDecision] = []
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0

    def emit_typed(
        rule_id: str,
        status: str,
        reason_code: str,
    ) -> None:
        assert evidence_snapshot is not None
        decisions.append(
            _decision_from_outcome(
                outcome=_ExamLabOutcome(rule_id, status, reason_code),
                snapshot=evidence_snapshot,
            )
        )

    for rule_id in selected:
        fact_kind = "exam" if rule_id in EXAM_RULE_IDS else "culture"
        if rule_id in typed_requested:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            typed_state, _ = _typed_trigger_state(
                fact_kind=fact_kind,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
            if typed_state == "error":
                emit_typed(rule_id, "technical_error", "source_query_error")
                continue
            if typed_state == "unavailable":
                emit_typed(rule_id, "data_gap", f"{fact_kind}_source_unavailable")
                continue
            if typed_state == "absent":
                emit_typed(rule_id, "not_applicable", f"{fact_kind}_fact_absent")
                continue
            if typed_state != "present":
                emit_typed(rule_id, "data_gap", f"{fact_kind}_fact_unknown")
                continue
            context, context_state = _typed_context(
                fact_kind=fact_kind,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
            if context_state == "error":
                emit_typed(rule_id, "technical_error", "source_query_error")
                continue
            if context_state == "unavailable":
                emit_typed(rule_id, "data_gap", "exam_lab_projection_unavailable")
                continue
            wrapper = wrappers_by_id.get(rule_id)
            if wrapper is None or not str(wrapper.get("custom_prompt") or "").strip() or not context:
                emit_typed(rule_id, "data_gap", "exam_lab_prompt_input_unavailable")
                continue
            if llm_client is None:
                emit_typed(rule_id, "technical_error", "exam_lab_llm_failure")
                continue
            llm_call_count += 1
            try:
                response = await llm_client.generate(_prompt(wrapper, context=context))
            except Exception:
                emit_typed(rule_id, "technical_error", "exam_lab_llm_failure")
                continue
            prompt, completion, total, elapsed = _usage(response)
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total
            api_time += elapsed
            is_compliant = _parse_is_compliant(response)
            if is_compliant is None:
                emit_typed(rule_id, "technical_error", "exam_lab_llm_invalid_output")
                continue
            emit_typed(
                rule_id,
                "compliant" if is_compliant else "non_compliant",
                "exam_lab_customer_prompt",
            )
            continue

        if documents is None or timeline_facts is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "exam_lab_projection_unavailable",
                    executor_type="program",
                )
            )
            continue
        fact_state = exam_state if fact_kind == "exam" else culture_state
        if fact_state == "absent":
            results.append(
                _result(
                    rule_id,
                    "not_applicable",
                    f"{fact_kind}_fact_absent",
                    executor_type="program",
                )
            )
            continue
        if fact_state != "present":
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    f"{fact_kind}_fact_unknown",
                    executor_type="program",
                )
            )
            continue
        wrapper = wrappers_by_id.get(rule_id)
        context = _context(documents, fact_kind=fact_kind)
        if wrapper is None or not str(wrapper.get("custom_prompt") or "").strip() or not context:
            results.append(
                _result(rule_id, "data_gap", "exam_lab_prompt_input_unavailable", executor_type="program")
            )
            continue
        if llm_client is None:
            results.append(
                _result(rule_id, "data_gap", "exam_lab_llm_unavailable", executor_type="program")
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context=context))
        except Exception:
            results.append(
                _result(rule_id, "data_gap", "exam_lab_llm_failure", executor_type="llm")
            )
            continue
        prompt, completion, total, elapsed = _usage(response)
        prompt_tokens += prompt
        completion_tokens += completion
        total_tokens += total
        api_time += elapsed
        is_compliant = _parse_is_compliant(response)
        if is_compliant is None:
            results.append(
                _result(rule_id, "data_gap", "exam_lab_llm_invalid_output", executor_type="llm")
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        results.append(
            _result(rule_id, status, "exam_lab_customer_prompt", executor_type="llm")
        )

    return NativeExamLabExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(
            sorted(
                decisions,
                key=lambda item: normalized_decision_ids.index(item.rule_id),
            )
        ),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
