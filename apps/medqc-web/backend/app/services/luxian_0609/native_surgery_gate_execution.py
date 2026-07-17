"""LX0609 手术高风险门控族原生执行。

只消费当前就诊的受控强事实和裁剪文书；事实沉默不等于明确否定。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import (
    has_strict_performed_time,
    parse_strict_performed_time,
    read_luxian_0609_native_source_rows,
    read_luxian_0609_runtime_source_rows,
)


SURGERY_GATE_RULE_IDS = (
    "LX0609-003",
    "LX0609-024",
    "LX0609-025",
    "LX0609-028",
    "LX0609-031",
    "LX0609-033",
)
EXECUTOR_KEY = "surgery_gate"

_PRESENT_STATES = frozenset({"present", "performed", "positive", "complete"})
_NEGATIVE_STATES = frozenset({"explicit_negative", "absent", "not_present"})
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_MAX_ROWS_PER_SOURCE = 6
_MAX_ROW_CHARS = 1000
_MAX_CONTEXT_CHARS = 12000
_TYPED_003_EVALUATOR_VERSION = "surgery-timeliness-003-ruledecision-v1"
_AUTHORITATIVE_RECORD_TIME_PATTERN = re.compile(
    r"^\d{4}-\d{1,2}-\d{1,2}[T ]\d{1,2}:\d{2}"
    r"(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:?\d{2})?$"
)

_RULE_SOURCES = {
    "LX0609-003": ("surgery_record", "anesthesia_record"),
    "LX0609-024": ("surgery_record", "pathology_exam_report"),
    "LX0609-025": ("surgery_record", "implant_usage"),
    "LX0609-028": ("surgery_record", "inpat_drug_order", "daily_course_record"),
    "LX0609-031": ("surgery_record", "presurg_summary", "presurg_discussion"),
    "LX0609-033": ("surgery_record", "surgery_inform_consent", "consent_form"),
}

_CONTROLLED_MESSAGES = {
    "compliant": ("手术相关记录满足该项要求。", ""),
    "non_compliant": ("手术相关记录未满足该项要求。", "请按该质控点补充或修正相关记录。"),
    "not_applicable": ("当前就诊不符合该项手术规则的适用条件。", ""),
    "data_gap": ("当前手术资料不足，暂不能形成可靠结论。", "请补齐相关资料后重新质控。"),
}


class SurgeryGateLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class NativeSurgeryGateExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


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


def _facts(evidence_payload: Mapping[str, Any] | None) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(evidence_payload, Mapping):
        return ()
    raw = evidence_payload.get("timeline_facts")
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, Mapping))


def _matching_facts(
    facts: Sequence[Mapping[str, Any]], fact_type: str
) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        item
        for item in facts
        if item.get("current_visit_bound") is True
        and _clean(item.get("fact_type")).lower() == fact_type
    )


def _fact_state(facts: Sequence[Mapping[str, Any]], fact_type: str) -> str:
    matched = _matching_facts(facts, fact_type)
    states = {_clean(item.get("state")).lower() for item in matched}
    if states.intersection(_PRESENT_STATES):
        return "present"
    if states.intersection(_NEGATIVE_STATES):
        return "negative"
    return "unknown"


def _fact_value(facts: Sequence[Mapping[str, Any]], fact_type: str) -> str:
    for item in _matching_facts(facts, fact_type):
        value = item.get("value")
        if isinstance(value, Mapping):
            value = value.get("value") or value.get("class")
        if _clean(value):
            return _clean(value).upper()
    return ""


def _source_rows(
    documents: Mapping[str, Any], source_key: str
) -> tuple[Mapping[str, Any], ...]:
    rows = documents.get(source_key)
    if not isinstance(rows, list):
        return ()
    return tuple(
        item for item in rows[:_MAX_ROWS_PER_SOURCE] if isinstance(item, Mapping)
    )


def _row_text(row: Mapping[str, Any]) -> str:
    approved_keys = (
        "content",
        "record_content",
        "assembled_text",
        "record_time",
        "surgery_name",
        "surgeon",
        "recorder",
        "signer",
        "report_status",
        "device_code",
        "usage_status",
        "drug_code",
        "order_status",
    )
    return _clean(
        " ".join(_clean(row.get(key)) for key in approved_keys if _clean(row.get(key)))
    )


def _context(rule_id: str, documents: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for source_key in _RULE_SOURCES[rule_id]:
        for index, row in enumerate(_source_rows(documents, source_key), start=1):
            if text := _row_text(row):
                parts.append(f"[{source_key}-{index}] {text[:_MAX_ROW_CHARS]}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _prompt(wrapper: Mapping[str, Any], context: str) -> str:
    custom = _MAPPING_LINE_PATTERN.sub("", str(wrapper.get("custom_prompt") or ""))
    return (
        custom.replace("{defect_level}", str(wrapper.get("defect_level") or ""))
        .replace("{medical_text}", context)
        .strip()
    )


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


def _result(
    rule_id: str,
    status: str,
    reason_code: str,
    *,
    executor_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_time: float = 0.0,
) -> dict[str, Any]:
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
    metadata.update(
        {
            "executor_type": executor_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "api_time": api_time,
        }
    )
    item["metadata"] = metadata
    return item


def _has_exact_time(rows: Sequence[Mapping[str, Any]]) -> bool:
    return any(has_strict_performed_time(row) for row in rows)


def _has_signature(rows: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        _clean(row.get("surgeon")) and _clean(row.get("signer") or row.get("recorder"))
        for row in rows
    )


def _authoritative_record_time(value: Any) -> datetime | None:
    """只接受 record_time 整值；不从正文、标题或局部文本提取时间。"""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        candidate = value.strip()
        if not _AUTHORITATIVE_RECORD_TIME_PATTERN.fullmatch(candidate):
            return None
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return parsed
    offset = parsed.utcoffset()
    if offset != timedelta(hours=8):
        return None
    return parsed.replace(tzinfo=None)


def _authoritative_surgery_end_time(
    *, source_key: str, row: Mapping[str, Any]
) -> datetime | None:
    """003 只以受控手术结束时间为锚，不用开始时间替代。"""

    if source_key == "surgery_record":
        parsed = tuple(
            value
            for field in ("surgery_end_time", "surgery_end_datetime")
            if (value := parse_strict_performed_time(row.get(field))) is not None
        )
        return max(parsed) if parsed else None
    if source_key == "mr_surgery":
        value = row.get("surgery_end_datetime")
        return value if isinstance(value, datetime) and value.tzinfo is None else None
    return None


def _typed_003_decision(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> RuleDecision:
    """用同一 Evidence Session 的权威时间完成 003 判定。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed 003 requires one evidence session")
    source_keys = ("surgery_record", "mr_surgery")
    observations = {
        item.source_key: item
        for item in snapshot.observations
        if item.source_key in source_keys
    }
    refs = tuple(
        observations[key].snapshot_ref.removeprefix("sha256:")
        for key in source_keys
        if key in observations
    )

    def decision(final_state: str, reason_code: str) -> RuleDecision:
        applicability, evidence_state, qc_direction = {
            "compliant": (
                ApplicabilityState.APPLICABLE,
                EvidenceState.SUFFICIENT,
                QcDirection.SATISFIED,
            ),
            "non_compliant": (
                ApplicabilityState.APPLICABLE,
                EvidenceState.SUFFICIENT,
                QcDirection.DEFECT,
            ),
            "not_applicable": (
                ApplicabilityState.NOT_APPLICABLE,
                EvidenceState.SUFFICIENT,
                QcDirection.UNKNOWN,
            ),
            "data_gap": (
                ApplicabilityState.UNKNOWN,
                EvidenceState.DATA_GAP,
                QcDirection.UNKNOWN,
            ),
            "technical_error": (
                ApplicabilityState.ERROR,
                EvidenceState.TECHNICAL_ERROR,
                QcDirection.UNKNOWN,
            ),
        }[final_state]
        return RuleDecision(
            rule_id="LX0609-003",
            snapshot_hash=snapshot.snapshot_hash,
            applicability=applicability,
            evidence_state=evidence_state,
            qc_direction=qc_direction,
            reason_code=reason_code,
            fact_refs=refs,
            evaluator_version=_TYPED_003_EVALUATOR_VERSION,
            confidence=None,
        )

    if set(observations) != set(source_keys):
        return decision("technical_error", "snapshot_mismatch")
    ordered = tuple(observations[key] for key in source_keys)
    if any(item.query_state.value == "error" for item in ordered):
        return decision("technical_error", "source_query_error")
    if any(item.query_state.value == "unavailable" for item in ordered):
        return decision("data_gap", "source_unavailable")
    if any(item.completeness.value == "truncated" for item in ordered):
        return decision("data_gap", "source_truncated")
    try:
        surgery_rows = tuple(materials.rows("surgery_record"))
        mr_rows = tuple(materials.rows("mr_surgery"))
    except EvidenceMaterialTruncated:
        return decision("data_gap", "source_truncated")
    except EvidenceMaterialUnavailable:
        return decision("technical_error", "snapshot_mismatch")

    if not surgery_rows and not mr_rows:
        return decision("not_applicable", "performed_event_absent")

    intervals: list[timedelta] = []
    incomplete_performed_row = False
    fallback_resolved = False
    for row in surgery_rows:
        surgery_end_time = _authoritative_surgery_end_time(
            source_key="surgery_record", row=row
        )
        record_time = _authoritative_record_time(row.get("record_time"))
        if surgery_end_time is None or record_time is None:
            incomplete_performed_row = True
            continue
        interval = record_time - surgery_end_time
        if interval.total_seconds() < 0:
            incomplete_performed_row = True
            continue
        intervals.append(interval)

    # 当 surgery_record 自身没有批准手术时间时，仅允许唯一 mr_surgery 时间
    # 与唯一手术记录时间配对；多记录无关联键时必须保守为数据不足。
    if not intervals:
        mr_end_times = tuple(
            sorted({
                time
                for row in mr_rows
                if (time := _authoritative_surgery_end_time(
                    source_key="mr_surgery", row=row
                )) is not None
            })
        )
        record_times = tuple(
            sorted({
                parsed
                for row in surgery_rows
                if (parsed := _authoritative_record_time(row.get("record_time")))
                is not None
            })
        )
        if (
            len(mr_rows) == 1
            and len(surgery_rows) == 1
            and len(mr_end_times) == 1
            and len(record_times) == 1
        ):
            interval = record_times[0] - mr_end_times[0]
            if interval.total_seconds() >= 0:
                intervals.append(interval)
                fallback_resolved = True

    if any(interval > timedelta(hours=24) for interval in intervals):
        return decision("non_compliant", "threshold_exceeded")
    if intervals and (not incomplete_performed_row or fallback_resolved):
        return decision("compliant", "requirement_within_threshold")
    return decision("data_gap", "authoritative_time_missing")


def _resolve_performed_state(
    *,
    facts: Sequence[Mapping[str, Any]],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
) -> str:
    state = _fact_state(facts, "current_visit_surgery_confirmed")
    if state != "unknown":
        return state
    if evidence_snapshot is not None:
        return _snapshot_performed_surgery_state(evidence_snapshot)
    if not all((institute_id, patient_id, visit_id)):
        return state
    try:
        rows = read_luxian_0609_runtime_source_rows(
            source_key="surgery_record",
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
        )
    except Exception:
        return "unknown"
    if any(has_strict_performed_time(row) for row in rows):
        return "present"
    return "negative" if not rows else "unknown"


def _snapshot_performed_surgery_state(
    snapshot: Luxian0609EvidenceSnapshot,
) -> str:
    observations = tuple(
        item for item in snapshot.observations if item.source_key == "surgery_record"
    )
    facts = tuple(
        item
        for item in snapshot.facts
        if item.source_key == "surgery_record"
        and item.fact_type == "current_visit_surgery_confirmed"
    )
    if len(observations) != 1 or len(facts) != 1:
        return "unknown"
    observation = observations[0]
    fact = facts[0]
    normalized_value = fact.normalized_value
    if not isinstance(normalized_value, Mapping):
        return "unknown"
    performed = normalized_value.get("performed")
    if (
        observation.query_state.value == "available"
        and fact.assertion.value == "affirmed"
        and performed is True
    ):
        return "present"
    if (
        observation.query_state.value == "empty"
        and fact.assertion.value == "negated"
        and performed is False
    ):
        return "negative"
    return "unknown"


def _snapshot_source_failed(
    snapshot: Luxian0609EvidenceSnapshot,
    source_key: str,
) -> bool:
    observation = next(
        (item for item in snapshot.observations if item.source_key == source_key),
        None,
    )
    return bool(
        observation is None
        or observation.query_state.value in {"unavailable", "error"}
    )


def _terminal_status(
    rule_id: str,
    *,
    facts: Sequence[Mapping[str, Any]],
    performed_state: str,
    documents: Mapping[str, Any],
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
) -> tuple[str, str] | None:
    if performed_state == "negative":
        return "not_applicable", "performed_surgery_explicitly_absent"
    if performed_state != "present":
        return "data_gap", "performed_surgery_fact_unavailable"

    if rule_id == "LX0609-024":
        state = _fact_state(facts, "current_visit_malignant_surgery_confirmed")
        if state == "negative":
            return "not_applicable", "malignant_surgery_explicitly_absent"
        if state != "present":
            return "data_gap", "malignant_surgery_fact_unavailable"
    elif rule_id == "LX0609-025":
        state = _fact_state(facts, "current_visit_surgical_implant_used")
        if state == "negative":
            return "not_applicable", "implant_explicitly_absent"
        if state != "present":
            return "data_gap", "implant_use_fact_unavailable"
    elif rule_id == "LX0609-028":
        incision = _fact_value(facts, "current_visit_surgical_incision_class")
        if incision and incision not in {"I", "II", "Ⅰ", "Ⅱ"}:
            return "not_applicable", "incision_class_outside_scope"
        if incision not in {"I", "II", "Ⅰ", "Ⅱ"}:
            return "data_gap", "incision_class_unavailable"
        if _fact_state(facts, "current_visit_prophylactic_antimicrobial") != "present":
            return "data_gap", "prophylaxis_fact_unavailable"
        if (
            _fact_state(facts, "current_visit_prophylactic_antimicrobial_interval")
            != "present"
        ):
            return "data_gap", "actual_interval_unavailable"
    elif rule_id == "LX0609-003":
        rows = _source_rows(documents, "surgery_record") + _source_rows(
            documents, "anesthesia_record"
        )
        if (
            not _has_exact_time(rows)
            and evidence_snapshot is None
            and institute_id
            and patient_id
            and visit_id
        ):
            try:
                rows = tuple(
                    read_luxian_0609_native_source_rows(
                        source_key="mr_surgery",
                        institute_id=institute_id,
                        patient_id=patient_id,
                        visit_id=visit_id,
                        source_schema=source_schema,
                    )
                )
            except Exception:
                return "data_gap", "surgery_time_source_error"
        if not _has_exact_time(rows):
            if evidence_snapshot is not None and _snapshot_source_failed(
                evidence_snapshot, "mr_surgery"
            ):
                return "data_gap", "surgery_time_source_error"
            return "data_gap", "surgery_time_unavailable"
    elif rule_id == "LX0609-031":
        if not _has_signature(_source_rows(documents, "surgery_record")):
            return "data_gap", "surgery_signature_source_unavailable"
    elif rule_id == "LX0609-033":
        readiness = _fact_state(facts, "current_visit_surgery_consent_source_readiness")
        if readiness != "present":
            return "data_gap", "surgery_consent_source_unproven"
        if not (
            _source_rows(documents, "surgery_inform_consent")
            or _source_rows(documents, "consent_form")
        ):
            return "data_gap", "surgery_consent_document_unavailable"
    return None


async def execute_luxian_0609_native_surgery_gate_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    llm_client: SurgeryGateLLMClient | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeSurgeryGateExecutionResult:
    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(
        rule_id for rule_id in SURGERY_GATE_RULE_IDS if rule_id in requested
    )
    if not selected:
        return NativeSurgeryGateExecutionResult((), ())

    typed_requested = {
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    }
    if not typed_requested.issubset({"LX0609-003"}) or not typed_requested.issubset(
        set(selected)
    ):
        raise ValueError("unsupported typed surgery gate rule scope")
    if typed_requested and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed 003 requires one evidence session")
    decisions = (
        (
            _typed_003_decision(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            ),
        )
        if "LX0609-003" in typed_requested
        else ()
    )
    legacy_selected = tuple(
        rule_id for rule_id in selected if rule_id not in typed_requested
    )
    if not legacy_selected:
        return NativeSurgeryGateExecutionResult(
            results=(),
            planned_rule_ids=selected,
            decisions=decisions,
        )

    documents = _documents(evidence_payload)
    if documents is None:
        return NativeSurgeryGateExecutionResult(
            tuple(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_projection_unavailable",
                    executor_type="program",
                )
                for rule_id in legacy_selected
            ),
            selected,
            decisions,
        )
    facts = _facts(evidence_payload)
    performed_state = _resolve_performed_state(
        facts=facts,
        institute_id=institute_id,
        patient_id=patient_id,
        visit_id=visit_id,
        source_schema=source_schema,
        evidence_snapshot=evidence_snapshot,
    )
    wrappers = {
        str(item.get("rule_id") or item.get("rule_code") or "").strip().upper(): item
        for item in wrapper_rules
        if isinstance(item, Mapping)
    }
    results: list[dict[str, Any]] = []
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0

    for rule_id in legacy_selected:
        terminal = _terminal_status(
            rule_id,
            facts=facts,
            performed_state=performed_state,
            documents=documents,
            institute_id=institute_id,
            patient_id=patient_id,
            visit_id=visit_id,
            source_schema=source_schema,
            evidence_snapshot=evidence_snapshot,
        )
        if terminal:
            status, reason = terminal
            results.append(_result(rule_id, status, reason, executor_type="program"))
            continue
        wrapper = wrappers.get(rule_id)
        context = _context(rule_id, documents)
        if wrapper is None or not context or llm_client is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_prompt_input_unavailable",
                    executor_type="program",
                )
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context))
        except Exception:
            results.append(
                _result(rule_id, "data_gap", "surgery_llm_failure", executor_type="llm")
            )
            continue
        prompt_count, completion_count, total_count, elapsed = _usage(response)
        prompt_tokens += prompt_count
        completion_tokens += completion_count
        total_tokens += total_count
        api_time += elapsed
        is_compliant = _parse_is_compliant(response)
        if is_compliant is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "surgery_llm_invalid_output",
                    executor_type="llm",
                    prompt_tokens=prompt_count,
                    completion_tokens=completion_count,
                    total_tokens=total_count,
                    api_time=elapsed,
                )
            )
            continue
        results.append(
            _result(
                rule_id,
                "compliant" if is_compliant else "non_compliant",
                "surgery_customer_prompt",
                executor_type="llm",
                prompt_tokens=prompt_count,
                completion_tokens=completion_count,
                total_tokens=total_count,
                api_time=elapsed,
            )
        )

    return NativeSurgeryGateExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=decisions,
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
