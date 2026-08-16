"""LX0609 查房病程族原生执行：强事实门控、裁剪文书与确定性复制检测。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
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
from .course_quality.shared import (
    MAX_ROWS_PER_SOURCE as _MAX_ROWS_PER_SOURCE,
    authoritative_course_time as _authoritative_course_time,
    clean_text as _clean,
    response_json_payload as _response_json_payload,
    row_text as _row_text,
    source_rows as _source_rows,
)
from .source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
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

_COURSE_SOURCES = (
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
)
_RULE_009_EXTERNAL_EVENT_SOURCES = (
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
)
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
_TIMELINE_SOURCES = (
    *_COURSE_SOURCES,
    "exam_attention_report",
    "lab_attention_report",
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
_MAX_RULE_009_CONTEXT_CHARS = 32000
_RULE_009_CHANGE_CATEGORIES = frozenset(
    {"subjective", "objective", "exam_lab", "complication", "special_state"}
)
_RULE_009_CHANGE_WINDOW = timedelta(hours=24)
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

_RULE_008_MAX_GAP_DAYS = 2
_RULE_016_EXACT_MATCH = 1.0
_RULE_009_TEMPLATE_VALUES = frozenset(
    {"", "模板", "空模板", "待补充", "暂无内容", "无内容", "未填写", "待完善", "null", "none"}
)

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


def _rule_009_substantive_text(row: Mapping[str, Any]) -> str:
    """拒绝空正文和固定模板壳，避免把只有时间的壳记录当作每日病程。"""

    content = _row_text(row)
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE).lower()
    return content if normalized not in _RULE_009_TEMPLATE_VALUES else ""


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


def _authoritative_natural_date(value: Any) -> date | None:
    """把权威时间字段收敛为自然日；不读取正文，也不比较时分秒。"""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        try:
            return date.fromisoformat(normalized)
        except ValueError:
            return None


def _rule_008_009_decision(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    customer_display_facts: list[tuple[str, Mapping[str, Any]]] | None = None,
) -> RuleDecision:
    """按医嘱开立日及病程权威记录日裁决病重/病危查房时限。"""

    if (
        rule_id not in {"LX0609-008", "LX0609-009"}
        or type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed severity evidence session mismatch")
    evaluator_version = "course-severity-natural-day-v1"
    observation_by_source = {
        item.source_key: item for item in snapshot.observations
    }

    def decision(
        *,
        applicability: ApplicabilityState,
        evidence_state: EvidenceState,
        qc_direction: QcDirection,
        reason_code: str,
        refs: set[str],
        confidence: float | None,
        display_facts: Mapping[str, Any] | None = None,
    ) -> RuleDecision:
        if display_facts is not None and customer_display_facts is not None:
            customer_display_facts.append((rule_id, display_facts))
        return RuleDecision(
            rule_id=rule_id,
            snapshot_hash=snapshot.snapshot_hash,
            applicability=applicability,
            evidence_state=evidence_state,
            qc_direction=qc_direction,
            reason_code=reason_code,
            fact_refs=tuple(refs),
            evaluator_version=evaluator_version,
            confidence=confidence,
        )

    required_sources = (
        CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
        CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
        EVALUATION_HORIZON_SOURCE_KEY,
        *_RULE_007_RECORD_SOURCES,
    )
    observations = {
        source_key: observation_by_source.get(source_key)
        for source_key in required_sources
    }
    if any(item is None for item in observations.values()):
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            refs=set(),
            confidence=None,
        )
    refs = {
        item.snapshot_ref.removeprefix("sha256:")
        for item in observations.values()
        if item is not None
    }

    order_observation = observations[CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY]
    assert order_observation is not None
    if order_observation.query_state.value == "error":
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_query_error",
            refs=refs,
            confidence=None,
        )
    if (
        order_observation.query_state.value == "unavailable"
        or order_observation.completeness.value == "truncated"
    ):
        return decision(
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=(
                "source_truncated"
                if order_observation.completeness.value == "truncated"
                else "source_unavailable"
            ),
            refs=refs,
            confidence=None,
        )
    try:
        order_rows = tuple(
            materials.rows(CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY)
        )
    except EvidenceMaterialTruncated:
        return decision(
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_truncated",
            refs=refs,
            confidence=None,
        )
    except Exception:
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            refs=refs,
            confidence=None,
        )
    if any(row.get("severity") not in {"serious", "critical"} for row in order_rows):
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            refs=refs,
            confidence=None,
        )
    target = "serious" if rule_id == "LX0609-008" else "critical"
    target_rows = tuple(row for row in order_rows if row.get("severity") == target)
    if any(
        row.get("status_state") == "unresolved"
        for row in target_rows
    ):
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_unavailable",
            refs=refs,
            confidence=None,
        )
    if any(
        row.get("status_state") not in {None, "effective", "excluded", "unresolved"}
        for row in target_rows
    ):
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            refs=refs,
            confidence=None,
        )
    relevant_orders = tuple(
        row
        for row in target_rows
        if row.get("status_state") in {None, "effective"}
    )
    if not relevant_orders:
        return decision(
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="trigger_absent_complete",
            refs=refs,
            confidence=1.0,
        )

    discharge_observation = observations[CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY]
    horizon_observation = observations[EVALUATION_HORIZON_SOURCE_KEY]
    assert discharge_observation is not None
    assert horizon_observation is not None
    if discharge_observation.query_state.value == "error":
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_query_error",
            refs=refs,
            confidence=None,
        )
    order_dates = tuple(
        _authoritative_natural_date(row.get("prescribed_datetime"))
        for row in relevant_orders
    )
    if any(item is None for item in order_dates):
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            refs=refs,
            confidence=None,
        )
    anchor_date = min(item for item in order_dates if item is not None)

    horizon_date: date | None = None
    if horizon_observation.query_state.value == "available":
        try:
            horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
        except Exception:
            return decision(
                applicability=ApplicabilityState.ERROR,
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="snapshot_mismatch",
                refs=refs,
                confidence=None,
            )
        if len(horizon_rows) != 1:
            return decision(
                applicability=ApplicabilityState.ERROR,
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="snapshot_mismatch",
                refs=refs,
                confidence=None,
            )
        horizon_date = _authoritative_natural_date(horizon_rows[0].get("horizon_date"))
        if horizon_date is None or horizon_date < anchor_date:
            return decision(
                applicability=ApplicabilityState.ERROR,
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="snapshot_mismatch",
                refs=refs,
                confidence=None,
            )
        horizon_fact = next(
            (
                fact
                for fact in snapshot.facts
                if fact.fact_type == "evaluation_horizon"
                and fact.source_key == EVALUATION_HORIZON_SOURCE_KEY
            ),
            None,
        )
        if horizon_fact is None:
            return decision(
                applicability=ApplicabilityState.ERROR,
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="snapshot_mismatch",
                refs=refs,
                confidence=None,
            )
        refs.add(horizon_fact.fact_id)
    elif horizon_observation.query_state.value != "empty":
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            refs=refs,
            confidence=None,
        )

    if (
        discharge_observation.query_state.value == "unavailable"
        or discharge_observation.completeness.value == "truncated"
    ) and horizon_date is None:
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code=(
                "source_truncated"
                if discharge_observation.completeness.value == "truncated"
                else "source_unavailable"
            ),
            refs=refs,
            confidence=None,
        )

    timed_record_dates: set[date] = set()
    for source_key in _RULE_007_RECORD_SOURCES:
        observation = observations[source_key]
        assert observation is not None
        if observation.query_state.value == "error":
            return decision(
                applicability=ApplicabilityState.ERROR,
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="source_query_error",
                refs=refs,
                confidence=None,
            )
        if (
            observation.query_state.value == "unavailable"
            or observation.completeness.value == "truncated"
        ):
            return decision(
                applicability=ApplicabilityState.APPLICABLE,
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code=(
                    "source_truncated"
                    if observation.completeness.value == "truncated"
                    else "source_unavailable"
                ),
                refs=refs,
                confidence=None,
            )
        try:
            rows = tuple(materials.rows(source_key))
        except EvidenceMaterialTruncated:
            return decision(
                applicability=ApplicabilityState.APPLICABLE,
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="source_truncated",
                refs=refs,
                confidence=None,
            )
        except Exception:
            return decision(
                applicability=ApplicabilityState.ERROR,
                evidence_state=EvidenceState.TECHNICAL_ERROR,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="snapshot_mismatch",
                refs=refs,
                confidence=None,
            )
        for row in rows:
            parsed_date = _authoritative_natural_date(
                authoritative_document_time_value(row)
            )
            if parsed_date is None:
                return decision(
                    applicability=ApplicabilityState.APPLICABLE,
                    evidence_state=EvidenceState.DATA_GAP,
                    qc_direction=QcDirection.UNKNOWN,
                    reason_code="authoritative_time_missing",
                    refs=refs,
                    confidence=None,
                )
            if parsed_date >= anchor_date and (
                horizon_date is None or parsed_date <= horizon_date
            ) and (
                rule_id != "LX0609-009"
                or bool(_rule_009_substantive_text(row))
            ):
                timed_record_dates.add(parsed_date)

    ordered_dates = sorted(timed_record_dates)
    if rule_id == "LX0609-008":
        dates_with_anchor = [anchor_date, *ordered_dates]
        if horizon_date is not None:
            dates_with_anchor.append(horizon_date)
        exceeded_interval = next(
            (
                (previous, current)
                for previous, current in zip(
                    dates_with_anchor,
                    dates_with_anchor[1:],
                )
                if (current - previous).days > _RULE_008_MAX_GAP_DAYS
            ),
            None,
        )
        interval_exceeded = exceeded_interval is not None
        if not interval_exceeded and horizon_date is None:
            return decision(
                applicability=ApplicabilityState.APPLICABLE,
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="authoritative_time_missing",
                refs=refs,
                confidence=None,
            )
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=(
                QcDirection.DEFECT
                if interval_exceeded
                else QcDirection.SATISFIED
            ),
            reason_code=(
                "threshold_exceeded"
                if interval_exceeded
                else "requirement_within_threshold"
            ),
            refs=refs,
            confidence=1.0,
            display_facts=(
                {
                    "failure_kind": "severity_course_gap_exceeded",
                    "severity": "serious",
                    "anchor_date": anchor_date.isoformat(),
                    "horizon_date": horizon_date.isoformat() if horizon_date else "",
                    "gap_start_date": exceeded_interval[0].isoformat(),
                    "gap_end_date": exceeded_interval[1].isoformat(),
                    "gap_days": (exceeded_interval[1] - exceeded_interval[0]).days,
                    "threshold_days": _RULE_008_MAX_GAP_DAYS,
                    "recorded_dates": [item.isoformat() for item in ordered_dates],
                }
                if exceeded_interval is not None
                else {
                    "failure_kind": "severity_course_interval_satisfied",
                    "severity": "serious",
                    "anchor_date": anchor_date.isoformat(),
                    "horizon_date": horizon_date.isoformat() if horizon_date else "",
                    "threshold_days": _RULE_008_MAX_GAP_DAYS,
                    "recorded_dates": [item.isoformat() for item in ordered_dates],
                    "maximum_gap_days": max(
                        (
                            (current - previous).days
                            for previous, current in zip(
                                dates_with_anchor,
                                dates_with_anchor[1:],
                            )
                        ),
                        default=0,
                    ),
                }
            ),
        )

    prefix_end = horizon_date or (ordered_dates[-1] if ordered_dates else anchor_date)
    expected_dates = {
        anchor_date + timedelta(days=offset)
        for offset in range((prefix_end - anchor_date).days + 1)
    }
    missing_dates = tuple(sorted(expected_dates.difference(timed_record_dates)))
    if missing_dates:
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="requirement_violated",
            refs=refs,
            confidence=1.0,
            display_facts={
                "failure_kind": "critical_daily_record_missing",
                "severity": "critical",
                "evaluated_scope": "critical_daily_course_coverage",
                "pending_scope": ["condition_change_course_documentation"],
                "anchor_date": anchor_date.isoformat(),
                "horizon_date": prefix_end.isoformat(),
                "required_dates": [
                    item.isoformat() for item in sorted(expected_dates)
                ],
                "covered_dates": [
                    item.isoformat()
                    for item in sorted(expected_dates.intersection(timed_record_dates))
                ],
                "missing_dates": [item.isoformat() for item in missing_dates[:7]],
                "missing_count": len(missing_dates),
                "missing_first_date": missing_dates[0].isoformat(),
                "missing_last_date": missing_dates[-1].isoformat(),
            },
        )
    if horizon_date is None:
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            refs=refs,
            confidence=None,
        )
    # 逐日记录已满足即完成本规则的确定性主判定。后续语义核对只允许在
    # 同一快照内发现明确反证时升级为缺陷，不能因模型未知或可选来源不足
    # 把已经通过的每日频次检查降成“数据不足”。
    return decision(
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied",
        refs=refs,
        confidence=1.0,
        display_facts={
            "failure_kind": "critical_daily_record_coverage_satisfied",
            "severity": "critical",
            "evaluated_scope": "critical_daily_course_coverage",
            "pending_scope": ["condition_change_course_documentation"],
            "anchor_date": anchor_date.isoformat(),
            "horizon_date": horizon_date.isoformat(),
            "required_dates": [item.isoformat() for item in sorted(expected_dates)],
            "covered_dates": [
                item.isoformat()
                for item in sorted(expected_dates.intersection(timed_record_dates))
            ],
            "missing_count": 0,
        },
    )


def _rule_009_external_event_time(
    source_key: str,
    row: Mapping[str, Any],
) -> datetime | None:
    """只取来源各自的临床事件时间，拒绝同步/修改时间。"""

    fields_by_source = {
        "exam_item_report": ("report_time",),
        "labtest_master": ("report_datetime",),
        "labtest_item_report": ("report_time",),
        "inpat_drug_order": ("prescribed_datetime",),
        "surgery_record": (
            "surgery_begin_time",
            "surgery_end_time",
            "record_time",
        ),
        "mr_surgery": ("surgery_begin_datetime", "surgery_end_datetime"),
    }
    for field_name in fields_by_source.get(source_key, ()):
        if (parsed := _authoritative_course_time(row.get(field_name))) is not None:
            return parsed
    return None


def _rule_009_row_ref(source_key: str, index: int, row: Mapping[str, Any]) -> str:
    """提示词只使用受控、可回查的行标识；没有业务ID时使用快照内序号。"""

    for field_name in ("document_id", "report_id", "test_id", "order_id", "row_ref"):
        value = _clean(row.get(field_name))
        if value:
            return f"{source_key}:{value}"
    return f"{source_key}:row-{index + 1}"


def _rule_009_external_event_text(
    source_key: str,
    row: Mapping[str, Any],
) -> str:
    """为009语义分支取最小事件描述，不能投递整行或坐标。"""

    if source_key == "labtest_item_report":
        parts = []
        for field_name, label in (
            ("item_name", "项目"),
            ("result", "结果"),
            ("abnormal_flag", "异常标志"),
        ):
            if (value := _clean(row.get(field_name))):
                parts.append(f"{label}={value}")
        if parts:
            return "；".join(parts)

    fields_by_source = {
        "exam_item_report": (
            "exam_impression",
            "exam_conclusion",
            "impression",
            "conclusion",
            "exam_result",
            "record_content",
        ),
        "labtest_master": ("record_content", "labtest_subject"),
        "labtest_item_report": ("record_content",),
        "inpat_drug_order": ("generic_name", "brand_name", "drug_type"),
        "surgery_record": ("surgery_process", "surgery_name", "record_content"),
        "mr_surgery": ("surgery_name", "surgery_code"),
    }
    for field_name in fields_by_source.get(source_key, ()):
        if (value := _clean(row.get(field_name))):
            return value
    return ""


def _rule_009_external_event_identity(
    source_key: str,
    index: int,
    row: Mapping[str, Any],
) -> tuple[str, str]:
    """按临床事件身份归并；同一检验的 master/item 只能形成一个事件。"""

    if source_key == "exam_item_report":
        exam_id = _clean(row.get("exam_id"))
        if exam_id:
            return "exam", f"exam_item_report:{exam_id}"
    if source_key in {"labtest_master", "labtest_item_report"}:
        test_id = _clean(row.get("test_id"))
        if test_id:
            return "lab", f"labtest:{test_id}"
    return source_key, _rule_009_row_ref(source_key, index, row)


def _rule_009_group_event_time(
    *,
    event_kind: str,
    times_by_source: Mapping[str, Sequence[datetime]],
) -> datetime | None:
    """优先采用检验主记录时间；同一权威层冲突时不猜测。"""

    source_priority = (
        ("labtest_master", "labtest_item_report")
        if event_kind == "lab"
        else ("exam_item_report",)
    )
    for source_key in source_priority:
        unique_times = tuple(dict.fromkeys(times_by_source.get(source_key, ())))
        if unique_times:
            return unique_times[0] if len(unique_times) == 1 else None
    return None


def _rule_009_baseline_course_ref(
    *,
    event_time: datetime,
    course_rows: Sequence[tuple[datetime | None, str, str]],
) -> str:
    """返回事件前最近基线；对应病程的24小时时限由Python最终校验。"""

    timed_rows = tuple(
        (course_time, ref)
        for course_time, ref, _content in course_rows
        if course_time is not None
    )
    prior = tuple(item for item in timed_rows if item[0] < event_time)
    return max(prior, default=(datetime.min, ""), key=lambda item: item[0])[1]


def _rule_009_semantic_context(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[
    str,
    bool,
    bool,
    Mapping[str, datetime | None],
    Mapping[str, datetime | None],
    datetime | date,
]:
    """返回完整语义投影及截断标记；不允许静默裁剪后交给模型。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        return "", False, False, {}, {}, date.min
    try:
        critical_dates = tuple(
            _authoritative_natural_date(row.get("prescribed_datetime"))
            for row in materials.rows(CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY)
            if row.get("severity") == "critical"
        )
        horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
    except Exception:
        return "", False, False, {}, {}, date.min
    if (
        not critical_dates
        or any(item is None for item in critical_dates)
        or len(horizon_rows) != 1
    ):
        return "", False, False, {}, {}, date.min
    anchor_date = min(item for item in critical_dates if item is not None)
    horizon_date = _authoritative_natural_date(horizon_rows[0].get("horizon_date"))
    if horizon_date is None or horizon_date < anchor_date:
        return "", False, False, {}, {}, date.min
    horizon_datetime = _authoritative_course_time(
        horizon_rows[0].get("horizon_datetime")
    )
    evaluation_horizon: datetime | date = horizon_datetime or horizon_date

    observation_by_source = {item.source_key: item for item in snapshot.observations}
    grouped_external_events: dict[tuple[str, str], dict[str, Any]] = {}
    for source_key in _RULE_009_EXTERNAL_EVENT_SOURCES:
        observation = observation_by_source.get(source_key)
        if (
            observation is None
            or observation.query_state.value not in {"available", "empty"}
            or observation.completeness.value == "truncated"
        ):
            return "", False, False, {}, {}, evaluation_horizon
        try:
            source_rows = materials.rows(source_key)
        except Exception:
            return "", False, False, {}, {}, evaluation_horizon
        for index, row in enumerate(source_rows):
            content = _rule_009_external_event_text(source_key, row)
            if not content:
                continue
            event_time = _rule_009_external_event_time(source_key, row)
            # 不能因为一条尚未被模型识别为病情变化的外部行缺时间，就把整条
            # 规则降级。只有模型明确引用的事件才进入后续权威时间校验。
            if event_time is not None and not (
                anchor_date <= event_time.date() <= horizon_date
            ):
                continue
            event_kind, event_ref = _rule_009_external_event_identity(
                source_key, index, row
            )
            group = grouped_external_events.setdefault(
                (event_kind, event_ref),
                {"texts": [], "times_by_source": {}},
            )
            if content not in group["texts"]:
                group["texts"].append(content)
            if event_time is not None:
                group["times_by_source"].setdefault(source_key, []).append(event_time)

    external_events: list[tuple[datetime | None, str, str]] = []
    for (event_kind, event_ref), group in grouped_external_events.items():
        external_events.append(
            (
                _rule_009_group_event_time(
                    event_kind=event_kind,
                    times_by_source=group["times_by_source"],
                ),
                event_ref,
                "；".join(group["texts"]),
            )
        )
    external_events.sort(
        key=lambda item: (item[0] is None, item[0] or datetime.max, item[1])
    )

    parts: list[str] = []
    course_times: dict[str, datetime | None] = {}
    # 保留全部可投递事件引用。时间是否权威只能在模型明确引用该事件后
    # 校验，不能因无关外部行缺时间而提前降级整条规则。
    event_times: dict[str, datetime | None] = {}
    substantive_dates: set[date] = set()
    course_rows: list[tuple[datetime | None, str, str]] = []
    for source_key in _RULE_007_RECORD_SOURCES:
        try:
            rows = materials.rows(source_key)
        except Exception:
            return "", False, False, {}, {}, evaluation_horizon
        for index, row in enumerate(rows):
            record_time = _authoritative_course_time(authoritative_document_time_value(row))
            record_date = record_time.date() if record_time is not None else None
            content = _rule_009_substantive_text(row)
            if not content or (
                record_date is not None
                and not anchor_date <= record_date <= horizon_date
            ):
                continue
            ref = _rule_009_row_ref(source_key, index, row)
            if record_date is not None:
                substantive_dates.add(record_date)
            course_times[ref] = record_time
            event_times[ref] = record_time
            course_rows.append((record_time, ref, content))
    course_rows.sort(key=lambda item: (item[0] is None, item[0] or datetime.max, item[1]))
    for record_time, ref, content in course_rows:
        if record_time is not None:
            baseline_ref = _rule_009_baseline_course_ref(
                event_time=record_time,
                course_rows=course_rows,
            )
        else:
            baseline_ref = ""
        parts.append(
            f"[course_event_ref={ref}] 事件/记录时间="
            f"{record_time.strftime('%Y-%m-%d %H:%M:%S') if record_time else '待核验'}；"
            f"baseline_course_ref={baseline_ref or '无'}；"
            f"内容={content}"
        )
    for event_time, ref, content in external_events:
        event_times[ref] = event_time
        if event_time is not None:
            baseline_ref = _rule_009_baseline_course_ref(
                event_time=event_time,
                course_rows=course_rows,
            )
        else:
            baseline_ref = ""
        parts.append(
            f"[external_event_ref={ref}] 事件时间="
            f"{event_time.strftime('%Y-%m-%d %H:%M:%S') if event_time else '待核验'}；"
            f"baseline_course_ref={baseline_ref or '无'}；"
            f"内容={content}"
        )
    expected_dates = {
        anchor_date + timedelta(days=offset)
        for offset in range((horizon_date - anchor_date).days + 1)
    }
    if expected_dates.difference(substantive_dates):
        return "", False, False, {}, {}, evaluation_horizon
    context = "\n".join(parts)
    return (
        ("", True, False, {}, {}, evaluation_horizon)
        if len(context) > _MAX_RULE_009_CONTEXT_CHARS
        else (context, False, True, event_times, course_times, evaluation_horizon)
    )


def _rule_009_external_source_terminal_decision(
    *,
    base_decision: RuleDecision,
    snapshot: Luxian0609EvidenceSnapshot,
) -> RuleDecision | None:
    """009 的外部语义来源失败不能伪装成资料不足。"""

    observations = {item.source_key: item for item in snapshot.observations}
    for source_key in _RULE_009_EXTERNAL_EVENT_SOURCES:
        observation = observations.get(source_key)
        if observation is None or observation.query_state.value not in {
            "available", "empty", "unavailable", "error"
        }:
            return _rule_009_semantic_decision(
                base_decision=base_decision,
                error_reason="snapshot_mismatch",
            )
        if observation.query_state.value == "error":
            return _rule_009_semantic_decision(
                base_decision=base_decision,
                error_reason="source_query_error",
            )
        if observation.query_state.value == "unavailable":
            return _rule_009_semantic_decision(
                base_decision=base_decision,
                data_gap_reason="source_unavailable",
            )
        if observation.completeness.value == "truncated":
            return _rule_009_semantic_decision(
                base_decision=base_decision,
                data_gap_reason="source_truncated",
            )
    return None


def _rule_009_semantic_prompt(*, context: str) -> str:
    return f"""你是 LX0609-009 病危病程语义核对器。

Python 已确认病危期间每日病程覆盖。不要判定整条规则状态、不要重判每日频次。
只抽取“相对既往基线发生明确改变”的事件：主观症状(subjective)、客观体征(objective)、检查检验(exam_lab)、并发症/合并症(complication)、特殊状态(special_state)。
"病情稳定”“继续观察”、可能/考虑/待排等不构成明确变化。只能引用材料中给出的 event_ref 和 course_ref，不得编造引用；事件发生时间由 Python 根据受控 event_ref 唯一确定。
若同一病程已经明确记录变化及处置，可把该病程作为对应病程。

只能使用以下当前就诊、评价区间内的病程事件和临床事件。external_event_ref 仅用于检查检验变化；
course_event_ref 可用于主观症状、客观体征、并发症/合并症和特殊状态变化，也可作为对应病程。
对应病程只能引用下列 course_event_ref；Python 会按权威时间严格校验它是否位于事件发生后 24 小时内：
{context}

只输出 JSON：{{"events":[{{"event_ref":"...","change_category":"subjective|objective|exam_lab|complication|special_state","is_explicit_change":true,"corresponding_course_ref":"...或空字符串"}}]}}。没有明确变化时events为空数组。"""


def _parse_rule_009_change_events(response: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...] | None:
    payload = _response_json_payload(response)
    raw_events = payload.get("events") if payload else None
    if not isinstance(raw_events, list):
        return None
    parsed: list[Mapping[str, Any]] = []
    for item in raw_events:
        if not isinstance(item, Mapping):
            return None
        category = _clean(item.get("change_category"))
        if category not in _RULE_009_CHANGE_CATEGORIES or item.get("is_explicit_change") is not True:
            return None
        event_ref = _clean(item.get("event_ref"))
        if not event_ref:
            return None
        parsed.append({
            "event_ref": event_ref,
            "change_category": category,
            "corresponding_course_ref": _clean(item.get("corresponding_course_ref")),
        })
    return tuple(parsed)


def _rule_009_semantic_decision(
    *,
    base_decision: RuleDecision,
    semantic_state: str | None = None,
    error_reason: str = "",
    data_gap_reason: str = "required_field_missing",
) -> RuleDecision:
    """将009的三态语义结果与已通过的Python频次判断合成。"""

    if base_decision.rule_id != "LX0609-009":
        raise ValueError("009 semantic decision requires LX0609-009")
    if error_reason:
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            error_reason,
            None,
        )
    elif semantic_state == "satisfied":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.SATISFIED,
            "requirement_satisfied",
            1.0,
        )
    elif semantic_state == "defect":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.DEFECT,
            "requirement_violated",
            1.0,
        )
    elif data_gap_reason != "required_field_missing":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            data_gap_reason,
            None,
        )
    else:
        dimensions = (
            base_decision.applicability,
            base_decision.evidence_state,
            base_decision.qc_direction,
            base_decision.reason_code,
            base_decision.confidence,
        )
    applicability, evidence_state, qc_direction, reason_code, confidence = dimensions
    return RuleDecision(
        rule_id=base_decision.rule_id,
        snapshot_hash=base_decision.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=base_decision.fact_refs,
        # v3 仅由受控 event_ref 解析权威时间，模型不再复述或改写时间。
        evaluator_version="course-severity-semantic-v3",
        confidence=confidence,
    )


def _rule_009_change_event_decision(
    *,
    base_decision: RuleDecision,
    events: Sequence[Mapping[str, Any]],
    event_times: Mapping[str, datetime | None],
    course_times: Mapping[str, datetime | None],
    evaluation_horizon: datetime | date,
) -> tuple[RuleDecision, Mapping[str, Any]]:
    """模型仅抽取事件，逐事件24小时及时性由Python唯一裁决。"""

    facts: list[dict[str, Any]] = []
    for event in events:
        event_ref = str(event["event_ref"])
        event_time = event_times.get(event_ref)
        course_ref = str(event.get("corresponding_course_ref") or "")
        if event_time is None:
            return (
                _rule_009_semantic_decision(
                    base_decision=base_decision,
                    data_gap_reason="authoritative_time_missing",
                ),
                {
                    "failure_kind": "critical_change_time_unavailable",
                    "threshold_hours": 24,
                },
            )
        deadline = event_time + _RULE_009_CHANGE_WINDOW
        if course_ref and course_ref not in course_times:
            return (
                _rule_009_semantic_decision(
                    base_decision=base_decision,
                    data_gap_reason="association_failed",
                ),
                {
                    "failure_kind": "critical_change_course_association_failed",
                    "event_ref": event_ref,
                    "corresponding_course_ref": course_ref,
                    "threshold_hours": 24,
                },
            )
        course_time = course_times.get(course_ref) if course_ref else None
        if course_ref and course_time is None:
            return (
                _rule_009_semantic_decision(
                    base_decision=base_decision,
                    data_gap_reason="authoritative_time_missing",
                ),
                {
                    "failure_kind": "critical_change_time_unavailable",
                    "threshold_hours": 24,
                },
            )
        timely = course_time is not None and event_time <= course_time <= deadline
        if not timely:
            if isinstance(evaluation_horizon, datetime):
                window_mature = evaluation_horizon >= deadline
            else:
                window_mature = evaluation_horizon > deadline.date()
            if not window_mature:
                return (
                    _rule_009_semantic_decision(
                        base_decision=base_decision,
                        data_gap_reason="evaluation_window_not_mature",
                    ),
                    {
                        "failure_kind": "critical_change_window_not_mature",
                        "event_ref": event_ref,
                        "event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "deadline_time": deadline.strftime("%Y-%m-%d %H:%M:%S"),
                        "threshold_hours": 24,
                    },
                )
        facts.append(
            {
                "event_ref": event_ref,
                "change_category": str(event["change_category"]),
                "event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
                "corresponding_course_ref": course_ref,
                "corresponding_course_time": (
                    course_time.strftime("%Y-%m-%d %H:%M:%S") if course_time else ""
                ),
                "deadline_time": deadline.strftime("%Y-%m-%d %H:%M:%S"),
                "threshold_hours": 24,
                "timely": timely,
            }
        )
    unmet = [item for item in facts if not item["timely"]]
    if unmet:
        return (
            _rule_009_semantic_decision(base_decision=base_decision, semantic_state="defect"),
            {
                "failure_kind": "critical_change_course_not_timely",
                "change_events": facts,
                "unmet_events": unmet,
                "threshold_hours": 24,
            },
        )
    return (
        base_decision,
        {
            "failure_kind": "critical_change_course_timely",
            "change_events": facts,
            "threshold_hours": 24,
        },
    )


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
            base_display_facts: list[tuple[str, Mapping[str, Any]]] = []
            base_decision = _rule_008_009_decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                customer_display_facts=base_display_facts,
            )
            if (
                rule_id != "LX0609-009"
                or base_decision.applicability is not ApplicabilityState.APPLICABLE
                or base_decision.evidence_state is not EvidenceState.SUFFICIENT
                or base_decision.qc_direction is not QcDirection.SATISFIED
            ):
                customer_display_facts.extend(base_display_facts)
                decisions.append(base_decision)
                continue
            terminal_decision = _rule_009_external_source_terminal_decision(
                base_decision=base_decision,
                snapshot=evidence_snapshot,
            )
            if terminal_decision is not None:
                customer_display_facts.extend(base_display_facts)
                decisions.append(terminal_decision)
                continue
            (
                context,
                context_capacity_exceeded,
                context_ready,
                event_times,
                course_times,
                evaluation_horizon,
            ) = (
                _rule_009_semantic_context(
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                )
            )
            if context_capacity_exceeded:
                decisions.append(
                    _rule_009_semantic_decision(
                        base_decision=base_decision,
                        data_gap_reason="candidate_scope_incomplete",
                    )
                )
                continue
            # 不完整的事件/文书时间不允许交由模型猜测，也不回退到每日覆盖结论。
            if not context_ready:
                customer_display_facts.extend(base_display_facts)
                decisions.append(
                    _rule_009_semantic_decision(
                        base_decision=base_decision,
                        data_gap_reason="authoritative_time_missing",
                    )
                )
                continue
            if not event_times:
                customer_display_facts.extend(base_display_facts)
                decisions.append(base_decision)
                continue
            if llm_client is None:
                customer_display_facts.extend(base_display_facts)
                decisions.append(
                    _rule_009_semantic_decision(
                        base_decision=base_decision,
                        error_reason="model_transport_error",
                    )
                )
                continue
            llm_call_count += 1
            try:
                response = await llm_client.generate(_rule_009_semantic_prompt(context=context))
            except Exception:
                # 每日覆盖不能替代病情变化语义核对；模型不可用时不能交付“合规”。
                customer_display_facts.extend(base_display_facts)
                decisions.append(
                    _rule_009_semantic_decision(
                        base_decision=base_decision,
                        error_reason="model_transport_error",
                    )
                )
                continue
            prompt, completion, total, elapsed = _usage(response)
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total
            api_time += elapsed
            events = _parse_rule_009_change_events(response)
            if events is None:
                customer_display_facts.extend(base_display_facts)
                decisions.append(
                    _rule_009_semantic_decision(
                        base_decision=base_decision,
                        error_reason="model_invalid_output",
                    )
                )
                continue
            if not events:
                customer_display_facts.extend(base_display_facts)
                decisions.append(base_decision)
                continue
            # 模型只能引用当前安全投影中实际存在的事件。不存在的 event_ref
            # 属于模型合同失败，不能伪装成病历“权威时间缺失”或每日覆盖合规。
            if any(str(event["event_ref"]) not in event_times for event in events):
                customer_display_facts.extend(base_display_facts)
                decisions.append(
                    _rule_009_semantic_decision(
                        base_decision=base_decision,
                        error_reason="model_invalid_output",
                    )
                )
                continue
            semantic_decision, change_facts = _rule_009_change_event_decision(
                base_decision=base_decision,
                events=events,
                event_times=event_times,
                course_times=course_times,
                evaluation_horizon=evaluation_horizon,
            )
            daily_facts = dict(base_display_facts[0][1]) if base_display_facts else {}
            daily_facts.update(change_facts)
            customer_display_facts.append(("LX0609-009", daily_facts))
            decisions.append(semantic_decision)
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
