"""LX0609 查房病程族原生执行：强事实门控、裁剪文书与确定性复制检测。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import heapq
import json
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
    _lx018_primary_diagnosis_text,
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
from .course_quality.rules_008_009 import (
    RULE_008_009_TIMELINE_SOURCES as _TIMELINE_SOURCES,
    evaluate_rules_008_009_typed,
)
from .course_quality.shared import (
    MAX_ROWS_PER_SOURCE as _MAX_ROWS_PER_SOURCE,
    authoritative_course_time as _authoritative_course_time,
    clean_text as _clean,
    response_json_payload as _response_json_payload,
    row_text as _row_text,
    source_rows as _source_rows,
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
)
EXECUTOR_KEY = "course_quality"

_ROUND_SOURCES = (
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "first_course_record",
)
_COPY_SOURCES = (
    "daily_course_record",
    "senior_course_record",
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
_MIN_COMPARABLE_CHARS = 24
_MIN_FIRST_COURSE_BODY_CHARS = 6
_COPY_SIMILARITY_THRESHOLD = 0.70
_COPY_FAST_SHINGLE_CHARS = 5
_COPY_PRECISE_CANDIDATE_LIMIT = 20
_COPY_DISPLAY_PAIR_LIMIT = 4
_COPY_REVIEW_SCHEMA_VERSION = "lx0609_017_v1"
_COPY_REVIEW_MAX_PROMPT_TOKENS = 4096
_COPY_REVIEW_MAX_COMPLETION_TOKENS = 512
_COPY_REVIEW_DOCUMENT_CHARS = 1200
_COPY_REVIEW_VERDICTS = frozenset(
    {"substantial_copy", "template_only", "uncertain"}
)
# 017 仅允许排除这一组人工确认的通用模板壳。归一后仍有任何字符，
# 都必须保留为病历特异内容，不能豁免复制判定。
_COPY_TEMPLATE_SHELL_PHRASES = (
    "患者病情稳定",
    "病情稳定",
    "患者病情平稳",
    "病情平稳",
    "一般情况良好",
    "一般情况可",
    "生命体征平稳",
    "生命体征稳定",
    "查体无明显异常",
    "无明显异常查体",
    "继续当前治疗",
    "继续原治疗",
    "观察病情",
)
_MAPPING_LINE_PATTERN = re.compile(r"^.*(?:主执行规则|映射执行规则).*$", re.MULTILINE)
_DATE_PATTERN = re.compile(r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?")
_TIME_PATTERN = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?")
_COMPLAINT_PATTERN = re.compile(r"主诉\s*[:：]\s*[^；;。]{2,}")
_DIAGNOSIS_PATTERN = re.compile(r"(?:第一诊断|主要诊断|初步诊断|入院诊断|首页第一诊断)\s*[:：]\s*[^；;。]{2,}")

_RULE_CONTEXT_SOURCES = {
    "LX0609-007": _RULE_007_RECORD_SOURCES,
    "LX0609-008": _TIMELINE_SOURCES,
    "LX0609-009": _TIMELINE_SOURCES,
    "LX0609-016": ("admission_record", "first_course_record"),
    "LX0609-018": ("admission_record", "diagnosis", "admission_record_diagnosis"),
}

_RULE_016_EXACT_MATCH = 1.0

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


def _first_course_body_text(row: Mapping[str, Any]) -> str:
    """只返回首次病程实质正文，不把界面预览当作正文。"""

    content = _clean(
        row.get("case_characteristic")
        or row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
    )
    if not content:
        return ""
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE)
    shell_remainder = re.sub(
        r"(?:首次病程记录|首次病程|记录时间|提交时间|文书类型|文书编号|正文|"
        r"sourcetable|firstcourserecord|assemblystatus|partial|"
        r"年|月|日|时|分|秒|\d+)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return content if len(shell_remainder) >= _MIN_FIRST_COURSE_BODY_CHARS else ""


def _admission_body_text(row: Mapping[str, Any]) -> str:
    """只接受入院记录正文承载字段，拒绝标题、时间和预览壳。"""

    content = _clean(
        row.get("history_of_present_illness")
        or row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
    )
    if not content:
        return ""
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE)
    shell_remainder = re.sub(
        r"(?:入院记录|记录时间|提交时间|文书类型|文书编号|正文|"
        r"sourcetable|admissionrecord|assemblystatus|partial|"
        r"年|月|日|时|分|秒|\d+)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return content if len(shell_remainder) >= _MIN_FIRST_COURSE_BODY_CHARS else ""


def _substantive_rows(
    documents: Mapping[str, Any],
    source_keys: Sequence[str],
    *,
    limit_per_source: int | None = _MAX_ROWS_PER_SOURCE,
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    rows: list[tuple[str, Mapping[str, Any], str]] = []
    for source_key in source_keys:
        for row in _source_rows(documents, source_key, limit=limit_per_source):
            content = _row_text(row)
            if content:
                rows.append((source_key, row, content))
    return tuple(rows)


def _substantive_first_course_rows(
    documents: Mapping[str, Any],
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    return tuple(
        ("first_course_record", row, content)
        for row in _source_rows(documents, "first_course_record")
        if (content := _first_course_body_text(row))
    )


def _substantive_admission_rows(
    documents: Mapping[str, Any],
) -> tuple[tuple[str, Mapping[str, Any], str], ...]:
    return tuple(
        ("admission_record", row, content)
        for row in _source_rows(documents, "admission_record")
        if (content := _admission_body_text(row))
    )


def _rule_016_comparison_material_state(documents: Mapping[str, Any]) -> str:
    """区分 016 的“无可比文书”与“文书存在但正文不可用”。"""

    admission_rows = _source_rows(documents, "admission_record")
    first_course_rows = _source_rows(documents, "first_course_record")
    # 任一端完全没有文书时都无法构成“入院记录 vs 首次病程”的比较对象，
    # 属于规则不适用；只有文书行存在但正文不可比时才是资料不足。
    if not admission_rows or not first_course_rows:
        return "absent"
    if (
        not _substantive_admission_rows(documents)
        or not _substantive_first_course_rows(documents)
    ):
        return "unavailable"
    return "ready"


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
        # trigger 读取完整 bounded diagnosis，模型上下文只保留最多8条受控第一诊断。
        context_rows = [
            item for item in context_rows if item[0] not in _LX018_DIAGNOSIS_SOURCES
        ]
        for source_key in _LX018_DIAGNOSIS_SOURCES:
            context_rows.extend(
                (
                    source_key,
                    row,
                    content,
                )
                for row in _source_rows(documents, source_key, limit=None)
                if (content := _lx018_primary_diagnosis_text(row))
            )
        admission_rows = [item for item in context_rows if item[0] == "admission_record"]
        diagnosis_rows = [
            item for item in context_rows if item[0] in _LX018_DIAGNOSIS_SOURCES
        ]
        context_rows = admission_rows[:_MAX_ROWS_PER_SOURCE] + diagnosis_rows[:_MAX_ROWS_PER_SOURCE]
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


def _normalized_for_similarity(content: str) -> str:
    value = _DATE_PATTERN.sub("", content)
    value = _TIME_PATTERN.sub("", value)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", value).lower()


def _rule_016_copy_coverage(documents: Mapping[str, Any]) -> float | None:
    """只比较结构化现病史与病例特点；1.0仅表示规范化后完全相同。"""

    admission_texts = tuple(
        _clean(row.get("history_of_present_illness"))
        for row in _source_rows(documents, "admission_record")
        if _clean(row.get("history_of_present_illness"))
    )
    first_course_texts = tuple(
        _clean(row.get("case_characteristic"))
        for row in _source_rows(documents, "first_course_record")
        if _clean(row.get("case_characteristic"))
    )
    if not admission_texts or not first_course_texts:
        return None
    maximum = 0.0
    for admission_text in admission_texts:
        normalized_admission = _normalized_for_similarity(admission_text)
        if not normalized_admission:
            continue
        for first_course_text in first_course_texts:
            normalized_first = _normalized_for_similarity(first_course_text)
            if not normalized_first:
                continue
            maximum = max(
                maximum,
                SequenceMatcher(
                    None, normalized_admission, normalized_first, autojunk=False
                ).ratio(),
            )
    return maximum


def _rule_016_customer_display_facts(
    documents: Mapping[str, Any],
    *,
    copy_coverage: float,
) -> Mapping[str, Any]:
    """仅投影比对范围、完全相同结论和可定位文书 ID，不返回正文。"""

    source_document_ids = [
        document_id
        for source_key in ("admission_record", "first_course_record")
        for row in _source_rows(documents, source_key)
        if (document_id := _clean(row.get("document_id")))
    ]
    return {
        "failure_kind": (
            "admission_first_course_copy_detected"
            if copy_coverage >= _RULE_016_EXACT_MATCH
            else "admission_first_course_not_identical"
        ),
        "copy_similarity": round(copy_coverage, 4),
        "copy_relation": (
            "completely_identical"
            if copy_coverage >= _RULE_016_EXACT_MATCH
            else "not_completely_identical"
        ),
        "compared_sections": ["入院记录现病史", "首次病程记录病例特点"],
        "source_document_ids": list(dict.fromkeys(source_document_ids)),
    }


def _is_copy_template_shell(normalized_content: str) -> bool:
    """只识别经人工确认的通用模板壳，未知内容一律不作豁免。"""

    remaining = normalized_content
    for phrase in _COPY_TEMPLATE_SHELL_PHRASES:
        remaining = remaining.replace(phrase, "")
    return not remaining


def _material_for_copy_coverage(normalized_content: str) -> str:
    """从相似度中排除已确认的模板壳，避免模板重复掩盖实质变化。"""

    remaining = normalized_content
    for phrase in _COPY_TEMPLATE_SHELL_PHRASES:
        remaining = remaining.replace(phrase, "")
    return remaining


@dataclass(frozen=True)
class _CopyReviewCandidate:
    pair_ref: str
    left_ref: str
    right_ref: str
    similarity: float
    left_source: str
    right_source: str
    left_time: str
    right_time: str
    left_content: str = field(repr=False)
    right_content: str = field(repr=False)
    document_fingerprints: tuple[str, str] = ("", "")
    redaction_terms: tuple[str, ...] = field(default=(), repr=False)


@dataclass(frozen=True)
class _CopyRuleOutcome:
    status: str
    reason_code: str
    executor_type: str
    safe_metadata: Mapping[str, Any]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0
    findings: str = ""
    evidence: str = ""
    suggestion: str = ""
    confidence: float | None = None
    copy_match_document_fingerprints: tuple[tuple[str, str], ...] = ()
    review_candidates: tuple[_CopyReviewCandidate, ...] = field(default=(), repr=False)


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


def _copy_similarity_band(value: float) -> str:
    return "threshold_exceeded" if value >= _COPY_SIMILARITY_THRESHOLD else "within_threshold"


def _copy_fast_signature(normalized_content: str) -> frozenset[str]:
    """生成轻量字符指纹；只用于候选排序，不参与最终质控结论。"""

    material = _material_for_copy_coverage(normalized_content)
    if len(material) <= _COPY_FAST_SHINGLE_CHARS:
        return frozenset({material}) if material else frozenset()
    return frozenset(
        material[index : index + _COPY_FAST_SHINGLE_CHARS]
        for index in range(len(material) - _COPY_FAST_SHINGLE_CHARS + 1)
    )


def _copy_fast_similarity(left: frozenset[str], right: frozenset[str]) -> float:
    """以 Dice 系数筛出疑似重复组合；精确相似度仍由 SequenceMatcher 裁决。"""

    if not left or not right:
        return 0.0
    return (2.0 * len(left.intersection(right))) / (len(left) + len(right))


def _assess_copy(
    documents: Mapping[str, Any],
    *,
    source_complete: bool = False,
) -> _CopyRuleOutcome:
    """先全组合轻量筛选，再对最高疑似组合执行受控精确比较。"""

    rows = _substantive_rows(
        documents,
        _COPY_SOURCES,
        limit_per_source=None if source_complete else _MAX_ROWS_PER_SOURCE,
    )
    comparable: list[tuple[datetime, str, str, bool, str, str]] = []
    seen_document_ids: set[str] = set()
    for source_key, row, content in rows:
        if _clean(row.get("document_title")) == "长期医嘱":
            continue
        normalized = _normalized_for_similarity(content)
        if len(normalized) < _MIN_COMPARABLE_CHARS:
            continue
        record_time = _authoritative_course_time(
            authoritative_document_time_value(row)
        )
        if record_time is None:
            return _CopyRuleOutcome(
                status="data_gap",
                reason_code="copy_authoritative_time_missing",
                executor_type="program",
                safe_metadata={
                    "comparable_document_count": len(comparable),
                    "similarity_band": "unknown",
                },
            )
        document_id = _clean(row.get("document_id"))
        if document_id and document_id in seen_document_ids:
            continue
        if document_id:
            seen_document_ids.add(document_id)
        comparable.append(
            (
                record_time,
                source_key,
                normalized,
                _is_copy_template_shell(normalized),
                content,
                document_id,
            )
        )

    safe_metadata: dict[str, Any] = {
        "comparable_document_count": len(comparable),
        "maximum_similarity": 0.0,
        "similarity_threshold": _COPY_SIMILARITY_THRESHOLD,
        "similarity_band": "unknown",
        "best_match_source_types": [],
        "best_match_record_times": [],
        "best_match_pairs": [],
        "screened_pair_count": 0,
        "precise_pair_count": 0,
        "template_shell_only": False,
    }
    if len(comparable) < 2:
        return _CopyRuleOutcome(
            status="not_applicable",
            reason_code="insufficient_independent_course_records",
            executor_type="program",
            safe_metadata=safe_metadata,
        )

    ordered = sorted(comparable, key=lambda item: (item[0], item[1], item[2]))
    signatures = [_copy_fast_signature(item[2]) for item in ordered]
    candidate_heap: list[tuple[float, int, int, int, int]] = []
    screened_pair_count = 0
    for left_index in range(len(ordered) - 1):
        for right_index in range(left_index + 1, len(ordered)):
            if ordered[left_index][0].date() >= ordered[right_index][0].date():
                continue
            screened_pair_count += 1
            fast_score = _copy_fast_similarity(
                signatures[left_index], signatures[right_index]
            )
            candidate = (
                fast_score,
                -left_index,
                -right_index,
                left_index,
                right_index,
            )
            if len(candidate_heap) < _COPY_PRECISE_CANDIDATE_LIMIT:
                heapq.heappush(candidate_heap, candidate)
            elif candidate[:3] > candidate_heap[0][:3]:
                heapq.heapreplace(candidate_heap, candidate)

    if not candidate_heap:
        return _CopyRuleOutcome(
            status="not_applicable",
            reason_code="copy_adjacent_day_pair_unavailable",
            executor_type="program",
            safe_metadata=safe_metadata,
        )

    precise_pairs: list[
        tuple[
            float,
            tuple[datetime, str, str, bool, str, str],
            tuple[datetime, str, str, bool, str, str],
        ]
    ] = []
    for _, _, _, left_index, right_index in candidate_heap:
        left = ordered[left_index]
        right = ordered[right_index]
        similarity = SequenceMatcher(None, left[2], right[2], autojunk=False).ratio()
        precise_pairs.append((similarity, left, right))
    precise_pairs.sort(
        key=lambda item: (
            -item[0],
            item[1][0],
            item[2][0],
            item[1][1],
            item[2][1],
        )
    )

    maximum = -1.0
    best_pair: tuple[
        tuple[datetime, str, str, bool, str, str],
        tuple[datetime, str, str, bool, str, str],
    ] | None = None
    longest_block = 0
    substantial_coverage = 0.0
    template_shell_only = False
    for similarity, left, right in precise_pairs:
        matcher = SequenceMatcher(None, left[2], right[2], autojunk=False)
        if similarity <= maximum:
            continue
        maximum = similarity
        best_pair = (left, right)
        template_shell_only = left[3] and right[3]
        blocks = [block.size for block in matcher.get_matching_blocks() if block.size]
        longest_block = max(blocks, default=0)
        material_matcher = SequenceMatcher(
            None,
            _material_for_copy_coverage(left[2]),
            _material_for_copy_coverage(right[2]),
            autojunk=False,
        )
        material_chars = sum(
            block.size for block in material_matcher.get_matching_blocks() if block.size
        )
        material_min_length = min(
            len(_material_for_copy_coverage(left[2])),
            len(_material_for_copy_coverage(right[2])),
        )
        substantial_coverage = material_chars / max(1, material_min_length)

    maximum = max(maximum, 0.0)
    best_match_pairs = [
        {
            "source_types": [left[1], right[1]],
            "record_times": [
                left[0].strftime("%Y-%m-%d %H:%M:%S"),
                right[0].strftime("%Y-%m-%d %H:%M:%S"),
            ],
            "similarity": round(similarity, 4),
        }
        for similarity, left, right in precise_pairs
        if similarity >= _COPY_SIMILARITY_THRESHOLD
    ][:_COPY_DISPLAY_PAIR_LIMIT]
    evidence_pairs = [
        (left, right)
        for similarity, left, right in precise_pairs
        if similarity >= _COPY_SIMILARITY_THRESHOLD
    ][:_COPY_DISPLAY_PAIR_LIMIT]
    if not evidence_pairs and best_pair is not None:
        evidence_pairs = [best_pair]
    occurrence_counts: dict[tuple[str, datetime], int] = {}
    for item in comparable:
        key = (item[1], item[0])
        occurrence_counts[key] = occurrence_counts.get(key, 0) + 1
    ambiguous_selected_time = any(
        occurrence_counts.get((item[1], item[0]), 0) > 1
        for pair in evidence_pairs
        for item in pair
    )
    copy_match_document_fingerprints = (
        tuple(
            tuple(
                "sha256:"
                + hashlib.sha256(
                    f"{item[1]}\0{item[5]}".encode("utf-8")
                ).hexdigest()
                if item[5]
                else ""
                for item in pair
            )
            for pair in evidence_pairs
        )
        if ambiguous_selected_time
        else ()
    )
    safe_metadata.update(
        {
            "maximum_similarity": round(maximum, 4),
            "similarity_band": _copy_similarity_band(maximum),
            "best_match_source_types": [best_pair[0][1], best_pair[1][1]] if best_pair else [],
            "best_match_record_times": [
                best_pair[0][0].strftime("%Y-%m-%d %H:%M:%S"),
                best_pair[1][0].strftime("%Y-%m-%d %H:%M:%S"),
            ] if best_pair else [],
            "best_match_pairs": best_match_pairs,
            "screened_pair_count": screened_pair_count,
            "precise_pair_count": len(precise_pairs),
            "longest_matching_block_chars": longest_block,
            "substantial_matching_coverage": round(substantial_coverage, 4),
            "template_shell_only": template_shell_only,
        }
    )
    if maximum < _COPY_SIMILARITY_THRESHOLD:
        return _CopyRuleOutcome(
            status="compliant",
            reason_code="copy_similarity_within_threshold",
            executor_type="program",
            safe_metadata=safe_metadata,
            copy_match_document_fingerprints=copy_match_document_fingerprints,
        )
    threshold_pairs = [
        (similarity, left, right)
        for similarity, left, right in precise_pairs
        if similarity >= _COPY_SIMILARITY_THRESHOLD
    ]
    if threshold_pairs and all(left[3] and right[3] for _, left, right in threshold_pairs):
        return _CopyRuleOutcome(
            status="compliant",
            reason_code="copy_similarity_within_threshold",
            executor_type="program",
            safe_metadata=safe_metadata,
        )

    assert best_pair is not None
    left_material = _material_for_copy_coverage(best_pair[0][2])
    right_material = _material_for_copy_coverage(best_pair[1][2])
    if (
        maximum == 1.0
        and len(left_material) >= _MIN_COMPARABLE_CHARS
        and left_material == right_material
    ):
        return _CopyRuleOutcome(
            status="non_compliant",
            reason_code="copy_similarity_threshold_exceeded",
            executor_type="program",
            safe_metadata=safe_metadata,
            copy_match_document_fingerprints=copy_match_document_fingerprints,
        )

    review_pairs = [
        (similarity, left, right)
        for similarity, left, right in threshold_pairs
        if not (left[3] and right[3])
    ][:_COPY_DISPLAY_PAIR_LIMIT]
    document_refs: dict[tuple[str, datetime, str, str], str] = {}
    review_candidates: list[_CopyReviewCandidate] = []
    for pair_index, (similarity, left, right) in enumerate(review_pairs, start=1):
        pair_refs: list[str] = []
        fingerprints: list[str] = []
        for item in (left, right):
            identity = (item[1], item[0], item[2], item[5])
            if identity not in document_refs:
                document_refs[identity] = f"D{len(document_refs) + 1:02d}"
            pair_refs.append(document_refs[identity])
            fingerprints.append(
                "sha256:"
                + hashlib.sha256(f"{item[1]}\0{item[5]}".encode("utf-8")).hexdigest()
                if item[5]
                else ""
            )
        review_candidates.append(
            _CopyReviewCandidate(
                pair_ref=f"P{pair_index:02d}",
                left_ref=pair_refs[0],
                right_ref=pair_refs[1],
                similarity=round(similarity, 4),
                left_source=left[1],
                right_source=right[1],
                left_time=left[0].strftime("%Y-%m-%d %H:%M:%S"),
                right_time=right[0].strftime("%Y-%m-%d %H:%M:%S"),
                left_content=left[4][:_COPY_REVIEW_DOCUMENT_CHARS],
                right_content=right[4][:_COPY_REVIEW_DOCUMENT_CHARS],
                document_fingerprints=(fingerprints[0], fingerprints[1]),
                redaction_terms=tuple(
                    value for value in (left[5], right[5]) if value
                ),
            )
        )
    return _CopyRuleOutcome(
        status="evaluation_unknown",
        reason_code="semantic_low_confidence",
        executor_type="program",
        safe_metadata=safe_metadata,
        review_candidates=tuple(review_candidates),
    )


def _redact_copy_review_text(text: str, terms: Sequence[str]) -> str:
    redacted = text
    for term in sorted(
        {str(value).strip() for value in terms if len(str(value).strip()) >= 4},
        key=len,
        reverse=True,
    ):
        redacted = redacted.replace(term, "[已脱敏]")
    return redacted


def _copy_review_prompt(
    candidates: Sequence[_CopyReviewCandidate],
    redaction_terms: Sequence[str] = (),
) -> str:
    documents: dict[str, dict[str, Any]] = {}
    pairs: list[dict[str, Any]] = []
    for candidate in candidates:
        documents.setdefault(
            candidate.left_ref,
            {
                "document_ref": candidate.left_ref,
                "source_type": candidate.left_source,
                "record_time": candidate.left_time,
                "content": _redact_copy_review_text(
                    candidate.left_content,
                    (*candidate.redaction_terms, *redaction_terms),
                ),
            },
        )
        documents.setdefault(
            candidate.right_ref,
            {
                "document_ref": candidate.right_ref,
                "source_type": candidate.right_source,
                "record_time": candidate.right_time,
                "content": _redact_copy_review_text(
                    candidate.right_content,
                    (*candidate.redaction_terms, *redaction_terms),
                ),
            },
        )
        pairs.append(
            {
                "pair_ref": candidate.pair_ref,
                "left_ref": candidate.left_ref,
                "right_ref": candidate.right_ref,
                "similarity": candidate.similarity,
            }
        )
    payload = {
        "schema_version": _COPY_REVIEW_SCHEMA_VERSION,
        "documents": list(documents.values()),
        "candidate_pairs": pairs,
    }
    return (
        "你只核对候选病程对是否属于实质内容复制，不输出质控状态。"
        "逐个pair_ref返回substantial_copy、template_only或uncertain；"
        "document_refs必须原样返回该候选的两个临时文书引用。\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _strict_copy_review_usage(
    response: Mapping[str, Any],
) -> tuple[int, int, int, float] | None:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return None
    values = tuple(
        usage.get(key)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    )
    if any(type(value) is not int or value < 0 for value in values):
        return None
    prompt_tokens, completion_tokens, total_tokens = values
    if (
        total_tokens != prompt_tokens + completion_tokens
        or prompt_tokens > _COPY_REVIEW_MAX_PROMPT_TOKENS
        or completion_tokens > _COPY_REVIEW_MAX_COMPLETION_TOKENS
    ):
        return None
    api_time = response.get("_api_time", 0.0)
    if (
        isinstance(api_time, bool)
        or not isinstance(api_time, (int, float))
        or api_time < 0
    ):
        return None
    return prompt_tokens, completion_tokens, total_tokens, float(api_time)


def _technical_copy_review_outcome(
    outcome: _CopyRuleOutcome,
    reason_code: str,
    *,
    usage: tuple[int, int, int, float] = (0, 0, 0, 0.0),
) -> _CopyRuleOutcome:
    return replace(
        outcome,
        status="technical_error",
        reason_code=reason_code,
        executor_type="llm",
        prompt_tokens=usage[0],
        completion_tokens=usage[1],
        total_tokens=usage[2],
        api_time=usage[3],
        copy_match_document_fingerprints=(),
        review_candidates=(),
    )


async def _review_copy_candidates(
    outcome: _CopyRuleOutcome,
    llm_client: CourseQualityLLMClient | None,
    *,
    redaction_terms: Sequence[str] = (),
) -> _CopyRuleOutcome:
    candidates = outcome.review_candidates
    if not candidates:
        return outcome
    if llm_client is None:
        return _technical_copy_review_outcome(outcome, "model_transport_error")
    try:
        response = await llm_client.generate(
            _copy_review_prompt(candidates, redaction_terms),
            max_completion_tokens=_COPY_REVIEW_MAX_COMPLETION_TOKENS,
            allow_length_retry=False,
        )
    except Exception:
        return _technical_copy_review_outcome(outcome, "model_transport_error")
    if not isinstance(response, Mapping):
        return _technical_copy_review_outcome(outcome, "model_invalid_output")

    usage = _strict_copy_review_usage(response)
    if usage is None:
        return _technical_copy_review_outcome(outcome, "model_invalid_output")
    payload = _response_json_payload(response)
    if (
        not isinstance(payload, Mapping)
        or set(payload) != {"schema_version", "pair_results"}
        or payload.get("schema_version") != _COPY_REVIEW_SCHEMA_VERSION
        or not isinstance(payload.get("pair_results"), list)
    ):
        return _technical_copy_review_outcome(
            outcome, "model_invalid_output", usage=usage
        )
    expected = {candidate.pair_ref: candidate for candidate in candidates}
    parsed: dict[str, str] = {}
    for item in payload["pair_results"]:
        if not isinstance(item, Mapping) or set(item) != {
            "pair_ref",
            "verdict",
            "document_refs",
        }:
            return _technical_copy_review_outcome(
                outcome, "model_invalid_output", usage=usage
            )
        pair_ref = item.get("pair_ref")
        verdict = item.get("verdict")
        document_refs = item.get("document_refs")
        candidate = expected.get(pair_ref) if isinstance(pair_ref, str) else None
        if (
            candidate is None
            or pair_ref in parsed
            or verdict not in _COPY_REVIEW_VERDICTS
            or document_refs != [candidate.left_ref, candidate.right_ref]
        ):
            return _technical_copy_review_outcome(
                outcome, "model_invalid_output", usage=usage
            )
        parsed[pair_ref] = verdict
    if set(parsed) != set(expected):
        return _technical_copy_review_outcome(
            outcome, "model_invalid_output", usage=usage
        )

    if "uncertain" in parsed.values():
        final_status = "evaluation_unknown"
        final_reason = "semantic_low_confidence"
        selected: tuple[_CopyReviewCandidate, ...] = ()
    elif "substantial_copy" in parsed.values():
        final_status = "non_compliant"
        final_reason = "copy_similarity_threshold_exceeded"
        selected = tuple(
            expected[pair_ref]
            for pair_ref, verdict in parsed.items()
            if verdict == "substantial_copy"
        )
    else:
        final_status = "compliant"
        final_reason = "copy_similarity_within_threshold"
        selected = ()

    safe_metadata = dict(outcome.safe_metadata)
    if selected:
        first = selected[0]
        safe_metadata.update(
            {
                "maximum_similarity": first.similarity,
                "best_match_source_types": [first.left_source, first.right_source],
                "best_match_record_times": [first.left_time, first.right_time],
                "best_match_pairs": [
                    {
                        "source_types": [item.left_source, item.right_source],
                        "record_times": [item.left_time, item.right_time],
                        "similarity": item.similarity,
                    }
                    for item in selected
                ],
            }
        )
    elif final_status == "compliant":
        safe_metadata["best_match_pairs"] = []
    return replace(
        outcome,
        status=final_status,
        reason_code=final_reason,
        executor_type="llm",
        safe_metadata=safe_metadata,
        prompt_tokens=usage[0],
        completion_tokens=usage[1],
        total_tokens=usage[2],
        api_time=usage[3],
        copy_match_document_fingerprints=tuple(
            item.document_fingerprints
            for item in selected
            if all(item.document_fingerprints)
        ),
        review_candidates=(),
    )


def _copy_customer_display_facts(outcome: _CopyRuleOutcome) -> Mapping[str, Any] | None:
    """017 仅投影可复核的比较对象和阈值，正文始终留在请求内材料仓。"""

    metadata = outcome.safe_metadata
    source_types = metadata.get("best_match_source_types")
    record_times = metadata.get("best_match_record_times")
    maximum = metadata.get("maximum_similarity")
    threshold = metadata.get("similarity_threshold")
    if (
        outcome.status not in {"compliant", "non_compliant"}
        or not isinstance(source_types, list)
        or len(source_types) != 2
        or any(value not in _COPY_SOURCES for value in source_types)
        or not isinstance(record_times, list)
        or len(record_times) != 2
        or not all(isinstance(value, str) and value for value in record_times)
        or not isinstance(maximum, (int, float))
        or not isinstance(threshold, (int, float))
    ):
        return None
    facts = {
        "failure_kind": (
            "copy_similarity_threshold_exceeded"
            if outcome.status == "non_compliant"
            else "copy_similarity_within_threshold"
        ),
        "copy_similarity": round(float(maximum), 4),
        "copy_similarity_threshold": round(float(threshold), 4),
        "copy_document_sources": list(source_types),
        "copy_document_record_times": list(record_times),
        "copy_match_pairs": [dict(item) for item in metadata.get("best_match_pairs", [])],
    }
    if outcome.copy_match_document_fingerprints:
        facts["copy_match_document_fingerprints"] = [
            list(pair) for pair in outcome.copy_match_document_fingerprints
        ]
    return facts


def _copy_result(
    documents: Mapping[str, Any], *, source_complete: bool = False
) -> dict[str, Any]:
    """017 只比较独立病程/查房文书的全文相似度，不调用模型。"""

    return _render_copy_outcome(
        _assess_copy(documents, source_complete=source_complete)
    )


def _rule_017_decision(
    *,
    outcome: _CopyRuleOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> RuleDecision:
    """从同一材料仓计算出的复制 outcome 直接构造决策。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed 017 evidence session mismatch")
    required_copy_sources = {"daily_course_record", "senior_course_record"}
    observations = tuple(
        item
        for item in snapshot.observations
        if item.source_key in required_copy_sources
    )
    if not required_copy_sources.issubset({item.source_key for item in observations}):
        return RuleDecision(
            rule_id="LX0609-017",
            snapshot_hash=snapshot.snapshot_hash,
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            fact_refs=(),
            evaluator_version="rule017-copy-similarity-v2",
            confidence=None,
        )
    refs = tuple(item.snapshot_ref.removeprefix("sha256:") for item in observations)
    if any(item.query_state.value == "error" for item in observations):
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            "source_query_error",
        )
    elif any(item.query_state.value == "unavailable" for item in observations):
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_unavailable",
        )
    elif any(item.completeness.value == "truncated" for item in observations):
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "source_truncated",
        )
    elif outcome.status == "compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_within_threshold",
        )
    elif outcome.status == "non_compliant":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "threshold_exceeded",
        )
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "eligibility_not_met",
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
    else:
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            "required_field_missing",
        )
    applicability, evidence_state, qc_direction, reason_code = dimensions
    return RuleDecision(
        rule_id="LX0609-017",
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version="rule017-copy-similarity-v2",
        confidence=outcome.confidence,
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
