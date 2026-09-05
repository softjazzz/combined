"""LX0609 查房病程族原生执行：强事实门控、裁剪文书与确定性复制检测。"""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Mapping, Protocol, Sequence

from .decision_model import (
    ApplicabilityState,
    CriterionResult,
    CriterionStatus,
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
from .course_quality.rule_018 import (
    LX018_DIAGNOSIS_SOURCES as _LX018_DIAGNOSIS_SOURCES,
    LX018_DIAGNOSTIC_RELATION_STATES as _LX018_DIAGNOSTIC_RELATION_STATES,
    _lx018_length_criterion_result,
    _lx018_primary_diagnosis_available,
    _lx018_primary_diagnosis_resolution,
    _lx018_prompt,
    _lx018_semantic_criterion_result,
    _lx018_unknown_semantic_result,
    _parse_lx018_diagnostic_rationale_code,
    _parse_lx018_diagnostic_relation,
    _parse_lx018_medical_analysis,
)
from .course_quality.rule_007 import (
    RULE_007_RECORD_SOURCES as _RULE_007_RECORD_SOURCES,
    evaluate_rule_007_legacy,
    evaluate_rule_007_typed as _rule_007_decision,
    rule_007_customer_display_facts as _rule_007_customer_display_facts,
)
from .course_quality.rule_077 import evaluate_rule_077
from .course_quality.rules_008_009 import (
    RULE_008_009_TIMELINE_SOURCES as _TIMELINE_SOURCES,
    evaluate_rules_008_009_typed,
)
from .course_quality.rules_016_017 import (
    RULE_017_COPY_SOURCES as _COPY_SOURCES,
    _CopyRuleOutcome,
    _assess_copy,
    _copy_customer_display_facts,
    _normalized_for_similarity as _normalized_for_similarity,  # noqa: F401
    _review_copy_candidates,
    _RULE_016_EXACT_MATCH,
    _rule_016_comparison_material_state,
    _rule_016_copy_coverage,
    _rule_016_customer_display_facts,
    _rule_017_decision,
)
from .course_quality.shared import (
    DATE_PATTERN as _DATE_PATTERN,
    MAX_ROWS_PER_SOURCE as _MAX_ROWS_PER_SOURCE,
    clean_text as _clean,
    response_json_payload as _response_json_payload,
    row_text as _row_text,
    source_rows as _source_rows,
    substantive_rows as _substantive_rows,
)
from .source_evidence_reader import (
    authoritative_document_time_value,
    has_luxian_0609_current_visit_unstable_order,
    luxian_0609_native_source_row_limit,
    read_luxian_0609_native_source_rows,
)


COURSE_QUALITY_RULE_IDS = (
    "LX0609-007",
    "LX0609-008",
    "LX0609-009",
    "LX0609-016",
    "LX0609-017",
    "LX0609-018",
    "LX0609-077",
)
EXECUTOR_KEY = "course_quality"

_ROUND_SOURCES = (
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "first_course_record",
)
_FACT_SOURCE_KEYS = frozenset({"inpat_nondrug_order"})
_SERIOUS_FACT_TYPES = frozenset(
    {
        "current_visit_serious_order",
        "current_visit_serious_condition",
        "current_visit_severe_order",
    }
)
_CRITICAL_FACT_TYPES = frozenset(
    {
        "current_visit_critical_order",
        "current_visit_critical_condition",
    }
)
_COMPLAINT_FACT_TYPES = frozenset({"current_visit_chief_complaint"})
_PRIMARY_DIAGNOSIS_FACT_TYPES = frozenset(
    {"current_visit_primary_diagnosis", "current_visit_first_diagnosis"}
)
_PRESENT_FACT_STATES = frozenset(
    {"present", "active", "ordered", "available", "affirmed"}
)
_ABSENT_FACT_STATES = frozenset(
    {"absent", "not_present", "negative", "inactive", "not_ordered"}
)
_MAX_ROW_CHARS = 1400
_MAX_CONTEXT_CHARS = 18000
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_COMPLAINT_PATTERN = re.compile(r"主诉\s*[:：]\s*[^；;。]{2,}")
_DIAGNOSIS_PATTERN = re.compile(r"(?:第一诊断|主要诊断|初步诊断|入院诊断|首页第一诊断)\s*[:：]\s*[^；;。]{2,}")

_RULE_CONTEXT_SOURCES = {
    "LX0609-007": _RULE_007_RECORD_SOURCES,
    "LX0609-008": _TIMELINE_SOURCES,
    "LX0609-009": _TIMELINE_SOURCES,
    "LX0609-016": ("admission_record", "first_course_record"),
    "LX0609-018": ("admission_record", "diagnosis", "admission_record_diagnosis"),
}

_CONTROLLED_MESSAGES = {
    "compliant": ("查房病程相关记录满足该项要求。", ""),
    "non_compliant": (
        "查房病程相关记录未满足该项要求。",
        "请按该质控点补充或修正相关记录。",
    ),
    "not_applicable": ("当前就诊不满足该项查房病程规则的适用条件。", ""),
    "data_gap": (
        "当前查房病程资料不足，暂不能形成可靠结论。",
        "请补齐相关资料后重新质控。",
    ),
    "evaluation_unknown": (
        "当前查房病程证据尚不能形成稳定结论。",
        "请结合当日病情变化、客观检查和诊疗调整进行人工确认。",
    ),
    "technical_error": (
        "本次自动判定未完成，未形成临床质控结论。",
        "请稍后重新质控；若仍失败，请检查模型服务状态。",
    ),
}


class CourseQualityLLMClient(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class NativeCourseQualityExecutionResult:
    results: tuple[dict[str, Any], ...]
    planned_rule_ids: tuple[str, ...]
    decisions: tuple[RuleDecision, ...] = ()
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...] = ()
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


def _documents(
    evidence_payload: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if not isinstance(evidence_payload, Mapping):
        return None
    timeline = evidence_payload.get("programmatic_timeline")
    if not isinstance(timeline, Mapping):
        return None
    documents = timeline.get("documents")
    return documents if isinstance(documents, Mapping) else None


def _timeline_facts(
    evidence_payload: Mapping[str, Any] | None,
) -> tuple[Any, ...]:
    if not isinstance(evidence_payload, Mapping):
        return ()
    raw_facts = evidence_payload.get("timeline_facts")
    if not isinstance(raw_facts, list):
        timeline = evidence_payload.get("programmatic_timeline")
        raw_facts = (
            timeline.get("timeline_facts") if isinstance(timeline, Mapping) else None
        )
    return tuple(raw_facts) if isinstance(raw_facts, list) else ()




def _fact_state(
    facts: Sequence[Any], fact_types: frozenset[str], source_keys: frozenset[str]
) -> str:
    observed_absent = False
    for raw_fact in facts:
        if not isinstance(raw_fact, Mapping):
            continue
        fact_type = _clean(raw_fact.get("fact_type")).lower()
        state = _clean(raw_fact.get("state")).lower()
        source_key = _clean(raw_fact.get("source_key")).lower()
        if (
            fact_type not in fact_types
            or source_key not in source_keys
            or raw_fact.get("current_visit_bound") is not True
        ):
            continue
        if state in _PRESENT_FACT_STATES:
            return "present"
        if state in _ABSENT_FACT_STATES:
            observed_absent = True
    return "absent" if observed_absent else "unknown"


def _timeline_ready(documents: Mapping[str, Any]) -> bool:
    time_markers: set[str] = set()
    for _, row, content in _substantive_rows(documents, _TIMELINE_SOURCES):
        # 客户源库部分病程只回传 submit_datetime。演示阶段与 002/006
        # 统一：优先记录时间，缺失时使用提交时间，不从正文猜测时间。
        record_time = _clean(authoritative_document_time_value(row))
        if record_time:
            time_markers.add(record_time)
        time_markers.update(_DATE_PATTERN.findall(content))
    return len(time_markers) >= 2


def _context(
    rule_id: str,
    documents: Mapping[str, Any],
    *,
    controlled_fact: str = "",
) -> str:
    parts = [f"[受控事实] {controlled_fact}"] if controlled_fact else []
    context_rows = list(
        _substantive_rows(documents, _RULE_CONTEXT_SOURCES[rule_id])
    )
    if rule_id == "LX0609-018":
        # trigger 读取完整 bounded diagnosis；模型上下文只投影唯一解析出的第一入院诊断。
        context_rows = [
            item for item in context_rows if item[0] not in _LX018_DIAGNOSIS_SOURCES
        ]
        diagnosis_state, diagnosis_text = _lx018_primary_diagnosis_resolution(documents)
        selected_diagnosis_rows: list[tuple[str, Mapping[str, Any], str]] = []
        if diagnosis_state == "available":
            selected_diagnosis_rows.append(
                ("admission_primary_diagnosis", {}, diagnosis_text)
            )
        admission_rows = [item for item in context_rows if item[0] == "admission_record"]
        diagnosis_rows = [
            item for item in context_rows if item[0] in _LX018_DIAGNOSIS_SOURCES
        ]
        context_rows = (
            admission_rows[:_MAX_ROWS_PER_SOURCE]
            + diagnosis_rows[:_MAX_ROWS_PER_SOURCE]
            + selected_diagnosis_rows
        )
    for source_key, row, content in context_rows:
        record_time = _clean(row.get("record_time")) or "未提供"
        parts.append(f"[{source_key}] 记录时间={record_time}；内容={content[:_MAX_ROW_CHARS]}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _prompt(wrapper: Mapping[str, Any], *, context: str) -> str:
    custom_prompt = _MAPPING_LINE_PATTERN.sub(
        "", str(wrapper.get("custom_prompt") or "")
    )
    prompt = (
        custom_prompt.replace("{defect_level}", str(wrapper.get("defect_level") or ""))
        .replace("{medical_text}", context)
        .strip()
    )
    return prompt


def _parse_is_compliant(response: Mapping[str, Any]) -> bool | None:
    payload = _response_json_payload(response)
    value = payload.get("is_compliant") if payload is not None else None
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
    extra_metadata: Mapping[str, Any] | None = None,
    criterion_results: tuple[CriterionResult, ...] = (),
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
    metadata.update(dict(extra_metadata or {}))
    item["metadata"] = metadata
    if criterion_results:
        item["criterion_results"] = [
            criterion.to_safe_dict() for criterion in criterion_results
        ]
    return item


@dataclass(frozen=True)
class _CourseSemanticOutcome:
    rule_id: str
    status: str
    reason_code: str
    executor_type: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0
    customer_display_facts: Mapping[str, Any] | None = None
    criterion_results: tuple[CriterionResult, ...] = ()


def _lx018_pre_model_outcome(
    documents: Mapping[str, Any],
) -> _CourseSemanticOutcome | None:
    """在调用模型前核对主诉和第一诊断是否具备，避免用缺失材料做语义判断。"""

    length_result = _lx018_length_criterion_result(documents)
    if length_result.status is CriterionStatus.UNKNOWN:
        return _CourseSemanticOutcome(
            rule_id="LX0609-018",
            status="data_gap",
            reason_code="required_field_missing",
            executor_type="program",
            criterion_results=(
                length_result,
                _lx018_unknown_semantic_result("required_field_missing"),
            ),
        )
    if not _lx018_primary_diagnosis_available(documents):
        return _CourseSemanticOutcome(
            rule_id="LX0609-018",
            status=(
                "non_compliant"
                if length_result.status is CriterionStatus.FAILED
                else "data_gap"
            ),
            reason_code=(
                length_result.reason_code
                if length_result.status is CriterionStatus.FAILED
                else "required_field_missing"
            ),
            executor_type="program",
            criterion_results=(
                length_result,
                _lx018_unknown_semantic_result("required_field_missing"),
            ),
        )
    return None


def _render_copy_outcome(outcome: _CopyRuleOutcome) -> dict[str, Any]:
    item = _result(
        "LX0609-017",
        outcome.status,
        outcome.reason_code,
        executor_type=outcome.executor_type,
        prompt_tokens=outcome.prompt_tokens,
        completion_tokens=outcome.completion_tokens,
        total_tokens=outcome.total_tokens,
        api_time=outcome.api_time,
        extra_metadata=outcome.safe_metadata,
    )
    if outcome.findings:
        item["findings"] = outcome.findings
    if outcome.evidence:
        item["evidence"] = outcome.evidence
    if outcome.suggestion:
        item["suggestion"] = outcome.suggestion
    if outcome.confidence is not None:
        item["confidence"] = outcome.confidence
    return item


def _copy_result(
    documents: Mapping[str, Any], *, source_complete: bool = False
) -> dict[str, Any]:
    """017 只比较独立病程/查房文书的全文相似度，不调用模型。"""

    return _render_copy_outcome(
        _assess_copy(documents, source_complete=source_complete)
    )




def _typed_course_semantic_documents(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[Mapping[str, Any], _CourseSemanticOutcome | None]:
    """只从同一 evidence session 取得 016/018 裁剪材料。"""

    required_sources = {
        "LX0609-016": ("admission_record", "first_course_record"),
        "LX0609-018": (
            "admission_record",
            "diagnosis",
            "admission_record_diagnosis",
        ),
    }[rule_id]
    observations = {
        item.source_key: item
        for item in snapshot.observations
        if item.source_key in required_sources
    }
    if set(observations) != set(required_sources):
        return {}, _CourseSemanticOutcome(
            rule_id=rule_id,
            status="technical_error",
            reason_code="snapshot_mismatch",
            executor_type="program",
        )
    ordered_observations = tuple(observations[key] for key in required_sources)
    if any(item.query_state.value == "error" for item in ordered_observations):
        return {}, _CourseSemanticOutcome(
            rule_id=rule_id,
            status="technical_error",
            reason_code="source_query_error",
            executor_type="program",
        )
    if any(item.query_state.value == "unavailable" for item in ordered_observations):
        return {}, _CourseSemanticOutcome(
            rule_id=rule_id,
            status="data_gap",
            reason_code="source_unavailable",
            executor_type="program",
        )
    if any(item.completeness.value == "truncated" for item in ordered_observations):
        return {}, _CourseSemanticOutcome(
            rule_id=rule_id,
            status="data_gap",
            reason_code="source_truncated",
            executor_type="program",
        )
    try:
        documents = {
            source_key: [dict(row) for row in materials.rows(source_key)]
            for source_key in required_sources
        }
    except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
        return {}, _CourseSemanticOutcome(
            rule_id=rule_id,
            status="technical_error",
            reason_code="snapshot_mismatch",
            executor_type="program",
        )
    return documents, None


def _course_semantic_decision(
    *,
    outcome: _CourseSemanticOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> RuleDecision:
    """将同一材料仓上产生的 016/018 outcome 直接提交统一 reducer。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed course semantic evidence session mismatch")
    required_sources = {
        "LX0609-016": ("admission_record", "first_course_record"),
        "LX0609-018": (
            "admission_record",
            "diagnosis",
            "admission_record_diagnosis",
        ),
    }[outcome.rule_id]
    observations = tuple(
        item for item in snapshot.observations if item.source_key in required_sources
    )
    refs = tuple(item.snapshot_ref.removeprefix("sha256:") for item in observations)
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
    elif outcome.status == "evaluation_unknown":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "semantic_low_confidence",
        )
    elif outcome.status == "technical_error":
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            outcome.reason_code,
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            outcome.reason_code,
        )
    else:
        reason_code = (
            outcome.reason_code
            if outcome.reason_code in {"source_unavailable", "source_truncated"}
            else "required_field_missing"
        )
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            reason_code,
        )
    applicability, evidence_state, qc_direction, reason_code = dimensions
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version="course-semantic-v1",
        confidence=None,
        criterion_results=tuple(
            replace(item, fact_refs=refs) for item in outcome.criterion_results
        ),
    )


def _admission_material_ready(
    documents: Mapping[str, Any], facts: Sequence[Any]
) -> bool:
    complaint_fact = (
        _fact_state(facts, _COMPLAINT_FACT_TYPES, frozenset({"admission_record"}))
        == "present"
    )
    diagnosis_fact = (
        _fact_state(
            facts,
            _PRIMARY_DIAGNOSIS_FACT_TYPES,
            frozenset({"admission_record", *_LX018_DIAGNOSIS_SOURCES}),
        )
        == "present"
    )
    complaint_text = diagnosis_text = False
    for row in _source_rows(documents, "admission_record"):
        complaint_text = complaint_text or bool(
            _clean(row.get("chief_complaint") or row.get("complaint"))
            or _COMPLAINT_PATTERN.search(_row_text(row))
        )
        diagnosis_text = diagnosis_text or bool(
            _clean(
                row.get("first_diagnosis")
                or row.get("primary_diagnosis")
                or row.get("diagnosis")
            )
            or _DIAGNOSIS_PATTERN.search(_row_text(row))
        )
    # 只采信受控第一诊断：主要诊断，或入院/初步诊断中的编号首项。
    diagnosis_text = diagnosis_text or _lx018_primary_diagnosis_available(documents)
    return (complaint_fact or complaint_text) and (diagnosis_fact or diagnosis_text)


async def execute_luxian_0609_native_course_quality_rules(
    *,
    rule_ids: Sequence[str],
    wrapper_rules: Sequence[Mapping[str, Any]],
    evidence_payload: Mapping[str, Any] | None,
    institute_id: str = "",
    patient_id: str = "",
    visit_id: str = "",
    source_schema: str | None = None,
    llm_client: CourseQualityLLMClient | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
    decision_rule_ids: Sequence[str] = (),
) -> NativeCourseQualityExecutionResult:
    """按客户目录顺序执行；每条适用语义规则最多调用模型一次。"""

    requested = {str(rule_id or "").strip().upper() for rule_id in rule_ids}
    selected = tuple(
        rule_id for rule_id in COURSE_QUALITY_RULE_IDS if rule_id in requested
    )
    if not selected:
        return NativeCourseQualityExecutionResult((), ())

    typed_requested = {
        str(rule_id or "").strip().upper() for rule_id in decision_rule_ids
    }
    if any(
        rule_id not in {
            "LX0609-007",
            "LX0609-008",
            "LX0609-009",
            "LX0609-016",
            "LX0609-017",
            "LX0609-018",
            "LX0609-077",
        }
        for rule_id in typed_requested
    ) or not typed_requested.issubset(set(selected)):
        raise ValueError("unsupported typed course rule scope")
    typed_selected = tuple(
        rule_id for rule_id in selected if rule_id in typed_requested
    )
    if typed_selected and (
        type(evidence_snapshot) is not Luxian0609EvidenceSnapshot
        or type(evidence_materials) is not Luxian0609EvidenceMaterialStore
        or evidence_materials.snapshot_hash != evidence_snapshot.snapshot_hash
    ):
        raise ValueError("typed course rules require one evidence session")

    documents = _documents(evidence_payload)
    projection_gap_rule_ids = {
        rule_id for rule_id in selected if rule_id not in typed_requested
    } if documents is None else set()
    documents = documents or {}
    facts = _timeline_facts(evidence_payload)
    serious_state = _fact_state(facts, _SERIOUS_FACT_TYPES, _FACT_SOURCE_KEYS)
    critical_state = _fact_state(facts, _CRITICAL_FACT_TYPES, _FACT_SOURCE_KEYS)
    wrappers_by_id = {
        str(wrapper.get("rule_id") or wrapper.get("rule_code") or "")
        .strip()
        .upper(): wrapper
        for wrapper in wrapper_rules
        if isinstance(wrapper, Mapping)
    }

    copy_documents = documents
    copy_source_failure = ""
    coordinates = (institute_id, patient_id, visit_id)
    if "LX0609-017" in selected and "LX0609-017" not in projection_gap_rule_ids:
        if not all(str(value or "").strip() for value in coordinates):
            copy_source_failure = "course_comparison_source_unavailable"
        else:
            try:
                complete_documents: dict[str, list[dict[str, Any]]] = {}
                for source_key in _COPY_SOURCES:
                    source_rows = (
                        [dict(row) for row in evidence_materials.rows(source_key)]
                        if evidence_materials is not None
                        else read_luxian_0609_native_source_rows(
                            source_key=source_key,
                            institute_id=institute_id,
                            patient_id=patient_id,
                            visit_id=visit_id,
                            source_schema=source_schema,
                        )
                    )
                    if len(source_rows) >= luxian_0609_native_source_row_limit(
                        source_key
                    ):
                        copy_source_failure = "course_comparison_source_truncated"
                        break
                    complete_documents[source_key] = source_rows
                if not copy_source_failure:
                    copy_documents = complete_documents
            except EvidenceMaterialTruncated:
                copy_source_failure = "course_comparison_source_truncated"
            except Exception:
                copy_source_failure = "course_comparison_source_unavailable"

    results: list[dict[str, Any]] = [
        _result(
            rule_id,
            "data_gap",
            "course_projection_unavailable",
            executor_type="program",
        )
        for rule_id in selected
        if rule_id in projection_gap_rule_ids
    ]
    decisions: list[RuleDecision] = []
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] = []
    llm_call_count = prompt_tokens = completion_tokens = total_tokens = 0
    api_time = 0.0

    def emit_copy(outcome: _CopyRuleOutcome) -> None:
        if "LX0609-017" in typed_requested:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            decisions.append(
                _rule_017_decision(
                    outcome=outcome,
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                )
            )
            display_facts = _copy_customer_display_facts(outcome)
            if display_facts is not None:
                customer_display_facts.append(("LX0609-017", display_facts))
        else:
            results.append(_render_copy_outcome(outcome))

    def emit_course_semantic(outcome: _CourseSemanticOutcome) -> None:
        assert evidence_snapshot is not None
        assert evidence_materials is not None
        decisions.append(
            _course_semantic_decision(
                outcome=outcome,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
        )
        if outcome.customer_display_facts is not None:
            customer_display_facts.append(
                (outcome.rule_id, outcome.customer_display_facts)
            )

    for rule_id in selected:
        if rule_id in projection_gap_rule_ids:
            continue
        if rule_id == "LX0609-007" and rule_id in typed_requested:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            course_decision = _rule_007_decision(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
            decisions.append(course_decision)
            if (display_facts := _rule_007_customer_display_facts(
                materials=evidence_materials,
                decision=course_decision,
            )) is not None:
                customer_display_facts.append(("LX0609-007", display_facts))
            continue
        if rule_id in {"LX0609-008", "LX0609-009"} and rule_id in typed_requested:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            severity_execution = await evaluate_rules_008_009_typed(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                llm_client=llm_client,
                usage_parser=_usage,
            )
            decisions.append(severity_execution.decision)
            customer_display_facts.extend(severity_execution.customer_display_facts)
            llm_call_count += severity_execution.llm_call_count
            prompt_tokens += severity_execution.prompt_tokens
            completion_tokens += severity_execution.completion_tokens
            total_tokens += severity_execution.total_tokens
            api_time += severity_execution.api_time
            continue
        if rule_id == "LX0609-077" and rule_id in typed_requested:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            differential_execution = await evaluate_rule_077(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                llm_client=llm_client,
            )
            decisions.append(differential_execution.decision)
            llm_call_count += differential_execution.llm_call_count
            prompt_tokens += differential_execution.prompt_tokens
            completion_tokens += differential_execution.completion_tokens
            total_tokens += differential_execution.total_tokens
            api_time += differential_execution.api_time
            continue
        if rule_id in {"LX0609-016", "LX0609-018"} and rule_id in typed_requested:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            typed_documents, terminal_outcome = _typed_course_semantic_documents(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
            if terminal_outcome is not None:
                emit_course_semantic(terminal_outcome)
                continue
            if rule_id == "LX0609-016":
                comparison_material_state = _rule_016_comparison_material_state(
                    typed_documents
                )
                if comparison_material_state == "absent":
                    emit_course_semantic(
                        _CourseSemanticOutcome(
                            rule_id=rule_id,
                            status="not_applicable",
                            reason_code="trigger_absent_complete",
                            executor_type="program",
                        )
                    )
                    continue
                if comparison_material_state == "unavailable":
                    emit_course_semantic(
                        _CourseSemanticOutcome(
                            rule_id=rule_id,
                            status="data_gap",
                            reason_code="admission_or_first_course_unavailable",
                            executor_type="program",
                        )
                    )
                    continue
            if rule_id == "LX0609-016":
                copy_coverage = _rule_016_copy_coverage(typed_documents)
                if copy_coverage is not None:
                    exact_copy = copy_coverage >= _RULE_016_EXACT_MATCH
                    emit_course_semantic(
                        _CourseSemanticOutcome(
                            rule_id=rule_id,
                            status=(
                                "non_compliant" if exact_copy else "compliant"
                            ),
                            reason_code=(
                                "copy_sections_completely_identical"
                                if exact_copy
                                else "copy_sections_not_completely_identical"
                            ),
                            executor_type="program",
                            customer_display_facts=_rule_016_customer_display_facts(
                                typed_documents,
                                copy_coverage=copy_coverage,
                            ),
                        )
                    )
                    continue
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status="data_gap",
                        reason_code="copy_sections_unavailable",
                        executor_type="program",
                    )
                )
                continue
            if rule_id == "LX0609-018":
                terminal_outcome = _lx018_pre_model_outcome(typed_documents)
                if terminal_outcome is not None:
                    emit_course_semantic(terminal_outcome)
                    continue
            context = _context(rule_id, typed_documents)
            wrapper = wrappers_by_id.get(rule_id)
            if (
                not context
                or (
                    rule_id != "LX0609-018"
                    and (
                        wrapper is None
                        or not _clean(wrapper.get("custom_prompt"))
                    )
                )
            ):
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status="data_gap",
                        reason_code="course_prompt_input_unavailable",
                        executor_type="program",
                    )
                )
                continue
            length_result = (
                _lx018_length_criterion_result(typed_documents)
                if rule_id == "LX0609-018"
                else None
            )
            if llm_client is None:
                unresolved_semantic = (
                    _lx018_unknown_semantic_result("model_transport_error")
                    if rule_id == "LX0609-018"
                    else None
                )
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status=(
                            "non_compliant"
                            if length_result is not None
                            and length_result.status is CriterionStatus.FAILED
                            else "technical_error"
                            if rule_id == "LX0609-018"
                            else "data_gap"
                        ),
                        reason_code=(
                            "model_transport_error"
                            if rule_id == "LX0609-018"
                            else "course_llm_unavailable"
                        ),
                        executor_type="program",
                        criterion_results=(
                            (length_result, unresolved_semantic)
                            if length_result is not None
                            and unresolved_semantic is not None
                            else ()
                        ),
                    )
                )
                continue
            llm_call_count += 1
            try:
                response = await llm_client.generate(
                    _lx018_prompt(context=context)
                    if rule_id == "LX0609-018"
                    else _prompt(wrapper, context=context)
                )
            except Exception:
                unresolved_semantic = (
                    _lx018_unknown_semantic_result("model_transport_error")
                    if rule_id == "LX0609-018"
                    else None
                )
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status=(
                            "non_compliant"
                            if length_result is not None
                            and length_result.status is CriterionStatus.FAILED
                            else "technical_error"
                        ),
                        reason_code="model_transport_error",
                        executor_type="llm",
                        criterion_results=(
                            (length_result, unresolved_semantic)
                            if length_result is not None
                            and unresolved_semantic is not None
                            else ()
                        ),
                    )
                )
                continue
            prompt, completion, total, elapsed = _usage(response)
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total
            api_time += elapsed
            is_compliant = _parse_is_compliant(response)
            if rule_id == "LX0609-018":
                payload = _response_json_payload(response)
                raw_relation_state = (
                    _clean(payload.get("diagnostic_relation_state"))
                    if payload
                    else ""
                )
                if raw_relation_state not in _LX018_DIAGNOSTIC_RELATION_STATES:
                    unresolved_semantic = _lx018_unknown_semantic_result(
                        "model_invalid_output"
                    )
                    emit_course_semantic(
                        _CourseSemanticOutcome(
                            rule_id=rule_id,
                            status=(
                                "non_compliant"
                                if length_result is not None
                                and length_result.status is CriterionStatus.FAILED
                                else "technical_error"
                            ),
                            reason_code="model_invalid_output",
                            executor_type="llm",
                            prompt_tokens=prompt,
                            completion_tokens=completion,
                            total_tokens=total,
                            api_time=elapsed,
                            criterion_results=(
                                (length_result, unresolved_semantic)
                                if length_result is not None
                                else ()
                            ),
                        )
                    )
                    continue
                relation_state, reason_dimensions = _parse_lx018_diagnostic_relation(
                    response
                )
                rationale_code = _parse_lx018_diagnostic_rationale_code(
                    response,
                    relation_state=relation_state,
                    dimensions=reason_dimensions,
                )
                semantic_result = _lx018_semantic_criterion_result(
                    relation_state=relation_state,
                    reason_dimensions=reason_dimensions,
                    rationale_code=rationale_code,
                    medical_analysis=_parse_lx018_medical_analysis(response),
                )
                assert length_result is not None
                if semantic_result.status is CriterionStatus.FAILED:
                    status = "non_compliant"
                elif length_result.status is CriterionStatus.FAILED:
                    status = "non_compliant"
                elif (
                    length_result.status is CriterionStatus.PASSED
                    and semantic_result.status is CriterionStatus.PASSED
                ):
                    status = "compliant"
                else:
                    status = "evaluation_unknown"
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status=status,
                        reason_code=(
                            "semantic_low_confidence"
                            if status == "evaluation_unknown"
                            else "course_customer_prompt"
                        ),
                        executor_type="llm",
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                        total_tokens=total,
                        api_time=elapsed,
                        criterion_results=(length_result, semantic_result),
                    )
                )
                continue
            if is_compliant is None:
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status="technical_error",
                        reason_code="model_invalid_output",
                        executor_type="llm",
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                        total_tokens=total,
                        api_time=elapsed,
                    )
                )
                continue
            emit_course_semantic(
                _CourseSemanticOutcome(
                    rule_id=rule_id,
                    status="compliant" if is_compliant else "non_compliant",
                    reason_code="course_customer_prompt",
                    executor_type="llm",
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    api_time=elapsed,
                )
            )
            continue
        if rule_id == "LX0609-017":
            if copy_source_failure:
                emit_copy(
                    _CopyRuleOutcome(
                        status="data_gap",
                        reason_code=copy_source_failure,
                        executor_type="program",
                        safe_metadata={},
                    )
                )
                continue
            copy_outcome = _assess_copy(
                copy_documents,
                source_complete=copy_documents is not documents,
            )
            if copy_outcome.review_candidates:
                if llm_client is not None:
                    llm_call_count += 1
                copy_outcome = await _review_copy_candidates(
                    copy_outcome,
                    llm_client,
                    redaction_terms=(institute_id or "", patient_id or "", visit_id or ""),
                )
                prompt_tokens += copy_outcome.prompt_tokens
                completion_tokens += copy_outcome.completion_tokens
                total_tokens += copy_outcome.total_tokens
                api_time += copy_outcome.api_time
            emit_copy(copy_outcome)
            continue

        controlled_fact = ""
        if rule_id == "LX0609-007":
            outcome = evaluate_rule_007_legacy(
                serious_state=serious_state,
                critical_state=critical_state,
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
                unstable_order_reader=has_luxian_0609_current_visit_unstable_order,
                source_row_reader=read_luxian_0609_native_source_rows,
                source_row_limit=luxian_0609_native_source_row_limit,
                evidence_snapshot=evidence_snapshot,
                evidence_materials=evidence_materials,
            )
            results.append(
                _result(
                    rule_id,
                    outcome.status,
                    outcome.reason_code,
                    executor_type="program",
                )
            )
            continue
        elif rule_id == "LX0609-008":
            if serious_state == "absent":
                results.append(
                    _result(
                        rule_id,
                        "not_applicable",
                        "serious_order_fact_absent",
                        executor_type="program",
                    )
                )
                continue
            if serious_state != "present":
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "serious_order_fact_unavailable",
                        executor_type="program",
                    )
                )
                continue
            if not _timeline_ready(documents):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "course_timeline_unavailable",
                        executor_type="program",
                    )
                )
                continue
            controlled_fact = "当前就诊存在病重医嘱"
        elif rule_id == "LX0609-009":
            if critical_state == "absent":
                results.append(
                    _result(
                        rule_id,
                        "not_applicable",
                        "critical_order_fact_absent",
                        executor_type="program",
                    )
                )
                continue
            if critical_state != "present":
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "critical_order_fact_unavailable",
                        executor_type="program",
                    )
                )
                continue
            if not _timeline_ready(documents):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "course_timeline_unavailable",
                        executor_type="program",
                    )
                )
                continue
            controlled_fact = "当前就诊存在病危医嘱"
        elif rule_id == "LX0609-016":
            comparison_material_state = _rule_016_comparison_material_state(documents)
            if comparison_material_state == "absent":
                results.append(
                    _result(
                        rule_id,
                        "not_applicable",
                        "trigger_absent_complete",
                        executor_type="program",
                    )
                )
                continue
            if comparison_material_state == "unavailable":
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "admission_or_first_course_unavailable",
                        executor_type="program",
                    )
                )
                continue
            copy_coverage = _rule_016_copy_coverage(documents)
            if copy_coverage is None:
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "copy_sections_unavailable",
                        executor_type="program",
                    )
                )
                continue
            exact_copy = copy_coverage >= _RULE_016_EXACT_MATCH
            results.append(
                _result(
                    rule_id,
                    "non_compliant" if exact_copy else "compliant",
                    (
                        "copy_sections_completely_identical"
                        if exact_copy
                        else "copy_sections_not_completely_identical"
                    ),
                    executor_type="program",
                )
            )
            continue
        elif rule_id == "LX0609-018":
            terminal_outcome = _lx018_pre_model_outcome(documents)
            if terminal_outcome is not None:
                results.append(
                    _result(
                        rule_id,
                        terminal_outcome.status,
                        terminal_outcome.reason_code,
                        executor_type=terminal_outcome.executor_type,
                        criterion_results=terminal_outcome.criterion_results,
                    )
                )
                continue

        context = _context(rule_id, documents, controlled_fact=controlled_fact)
        wrapper = wrappers_by_id.get(rule_id)
        if (
            not context
            or (
                rule_id != "LX0609-018"
                and (
                    wrapper is None
                    or not _clean(wrapper.get("custom_prompt"))
                )
            )
        ):
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "course_prompt_input_unavailable",
                    executor_type="program",
                )
            )
            continue
        length_result = (
            _lx018_length_criterion_result(documents)
            if rule_id == "LX0609-018"
            else None
        )
        if llm_client is None:
            unresolved_semantic = (
                _lx018_unknown_semantic_result("model_transport_error")
                if rule_id == "LX0609-018"
                else None
            )
            results.append(
                _result(
                    rule_id,
                    (
                        "non_compliant"
                        if length_result is not None
                        and length_result.status is CriterionStatus.FAILED
                        else "technical_error"
                        if rule_id == "LX0609-018"
                        else "data_gap"
                    ),
                    (
                        "model_transport_error"
                        if rule_id == "LX0609-018"
                        else "course_llm_unavailable"
                    ),
                    executor_type="program",
                    criterion_results=(
                        (length_result, unresolved_semantic)
                        if length_result is not None
                        and unresolved_semantic is not None
                        else ()
                    ),
                )
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(
                _lx018_prompt(context=context)
                if rule_id == "LX0609-018"
                else _prompt(wrapper, context=context)
            )
        except Exception:
            unresolved_semantic = (
                _lx018_unknown_semantic_result("model_transport_error")
                if rule_id == "LX0609-018"
                else None
            )
            results.append(
                _result(
                    rule_id,
                    (
                        "non_compliant"
                        if length_result is not None
                        and length_result.status is CriterionStatus.FAILED
                        else "technical_error"
                        if rule_id == "LX0609-018"
                        else "data_gap"
                    ),
                    (
                        "model_transport_error"
                        if rule_id == "LX0609-018"
                        else "course_llm_failure"
                    ),
                    executor_type="llm",
                    criterion_results=(
                        (length_result, unresolved_semantic)
                        if length_result is not None
                        and unresolved_semantic is not None
                        else ()
                    ),
                )
            )
            continue
        prompt, completion, total, elapsed = _usage(response)
        prompt_tokens += prompt
        completion_tokens += completion
        total_tokens += total
        api_time += elapsed
        is_compliant = _parse_is_compliant(response)
        if rule_id != "LX0609-018" and is_compliant is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "course_llm_invalid_output",
                    executor_type="llm",
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    api_time=elapsed,
                )
            )
            continue
        if rule_id == "LX0609-018":
            payload = _response_json_payload(response)
            raw_relation_state = (
                _clean(payload.get("diagnostic_relation_state"))
                if payload
                else ""
            )
            if raw_relation_state not in _LX018_DIAGNOSTIC_RELATION_STATES:
                unresolved_semantic = _lx018_unknown_semantic_result(
                    "model_invalid_output"
                )
                results.append(
                    _result(
                        rule_id,
                        (
                            "non_compliant"
                            if length_result is not None
                            and length_result.status is CriterionStatus.FAILED
                            else "technical_error"
                        ),
                        "model_invalid_output",
                        executor_type="llm",
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                        total_tokens=total,
                        api_time=elapsed,
                        criterion_results=(
                            (length_result, unresolved_semantic)
                            if length_result is not None
                            else ()
                        ),
                    )
                )
                continue
            relation_state, reason_dimensions = _parse_lx018_diagnostic_relation(
                response
            )
            rationale_code = _parse_lx018_diagnostic_rationale_code(
                response,
                relation_state=relation_state,
                dimensions=reason_dimensions,
            )
            semantic_result = _lx018_semantic_criterion_result(
                relation_state=relation_state,
                reason_dimensions=reason_dimensions,
                rationale_code=rationale_code,
                medical_analysis=_parse_lx018_medical_analysis(response),
            )
            assert length_result is not None
            if semantic_result.status is CriterionStatus.FAILED:
                status = "non_compliant"
            elif length_result.status is CriterionStatus.FAILED:
                status = "non_compliant"
            elif (
                length_result.status is CriterionStatus.PASSED
                and semantic_result.status is CriterionStatus.PASSED
            ):
                status = "compliant"
            else:
                status = "evaluation_unknown"
            results.append(
                _result(
                    rule_id,
                    status,
                    (
                        "semantic_low_confidence"
                        if status == "evaluation_unknown"
                        else "course_customer_prompt"
                    ),
                    executor_type="llm",
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    api_time=elapsed,
                    criterion_results=(length_result, semantic_result),
                )
            )
            continue
        status = "compliant" if is_compliant else "non_compliant"
        extra_metadata: Mapping[str, Any] | None = None
        results.append(
            _result(
                rule_id,
                status,
                "course_customer_prompt",
                executor_type="llm",
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                api_time=elapsed,
                extra_metadata=extra_metadata,
            )
        )

    return NativeCourseQualityExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        customer_display_facts=tuple(customer_display_facts),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
