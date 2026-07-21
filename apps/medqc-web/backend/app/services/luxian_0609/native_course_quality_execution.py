"""LX0609 查房病程族原生执行：强事实门控、裁剪文书与确定性复制检测。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
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
    build_material_document_refs,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .native_execution import build_luxian_0609_native_result
from .source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
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
_RULE_007_RECORD_SOURCES = (
    "daily_course_record",
    "senior_course_record",
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
_COPY_SUPPORT_SOURCES = (
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
    "inpat_drug_order",
    "surgery_record",
    "mr_surgery",
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
_MAX_ROWS_PER_SOURCE = 8
_MAX_ROW_CHARS = 1400
_MAX_CONTEXT_CHARS = 18000
_MIN_COMPARABLE_CHARS = 24
_MIN_FIRST_COURSE_BODY_CHARS = 6
_COPY_SIMILARITY_THRESHOLD = 0.70
_COPY_AUTO_NONCOMPLIANT_MIN = 0.95
_COPY_STRONG_COVERAGE_MIN = 0.90
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
_DIAGNOSIS_PATTERN = re.compile(r"(?:第一诊断|主要诊断|入院诊断|首页第一诊断)\s*[:：]\s*[^；;。]{2,}")

_RULE_CONTEXT_SOURCES = {
    "LX0609-007": _RULE_007_RECORD_SOURCES,
    "LX0609-008": _TIMELINE_SOURCES,
    "LX0609-009": _TIMELINE_SOURCES,
    "LX0609-016": ("admission_record", "first_course_record"),
    "LX0609-018": ("admission_record", "diagnosis"),
}

_RULE_007_MAX_INTERVAL = timedelta(hours=72)
_RULE_008_MAX_GAP_DAYS = 2
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
}


class CourseQualityLLMClient(Protocol):
    async def generate(self, prompt: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class NativeCourseQualityExecutionResult:
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


def _row_text(row: Mapping[str, Any]) -> str:
    return _clean(
        row.get("record_content")
        or row.get("content")
        or row.get("assembled_text")
        or row.get("raw_text")
        or row.get("content_preview")
        or row.get("text_preview")
        or row.get("diagnosis_name")
        or row.get("diagnosis_code")
    )


def _rule_009_substantive_text(row: Mapping[str, Any]) -> str:
    """拒绝空正文和固定模板壳，避免把只有时间的壳记录当作每日病程。"""

    content = _row_text(row)
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE).lower()
    return content if normalized not in _RULE_009_TEMPLATE_VALUES else ""


def _first_course_body_text(row: Mapping[str, Any]) -> str:
    """只返回首次病程实质正文，不把界面预览当作正文。"""

    content = _clean(
        row.get("record_content")
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
        row.get("record_content")
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


def _source_rows(
    documents: Mapping[str, Any],
    source_key: str,
    *,
    limit: int | None = _MAX_ROWS_PER_SOURCE,
) -> tuple[Mapping[str, Any], ...]:
    raw_rows = documents.get(source_key)
    if not isinstance(raw_rows, list):
        return ()
    selected_rows = raw_rows if limit is None else raw_rows[:limit]
    return tuple(
        row for row in selected_rows if isinstance(row, Mapping)
    )


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
        record_time = _clean(row.get("record_time"))
        if record_time:
            time_markers.add(record_time)
        time_markers.update(_DATE_PATTERN.findall(content))
    return len(time_markers) >= 2


def _authoritative_course_time(value: Any) -> datetime | None:
    """007 只接受两类病程表的 record_time，不使用正文或更新时间。"""

    if isinstance(value, datetime):
        return value if value.tzinfo is None else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo is None else None


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


def _rule_007_result(
    *,
    serious_state: str,
    critical_state: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
) -> dict[str, Any]:
    if serious_state == "present" or critical_state == "present":
        return _result(
            "LX0609-007",
            "not_applicable",
            "unstable_patient_fact_present",
            executor_type="program",
        )

    coordinates = (institute_id, patient_id, visit_id)
    if not all(str(value or "").strip() for value in coordinates):
        return _result(
            "LX0609-007",
            "data_gap",
            "course_time_source_unavailable",
            executor_type="program",
        )

    try:
        if evidence_snapshot is not None:
            unstable_order_state = _snapshot_unstable_order_state(evidence_snapshot)
            if unstable_order_state == "unavailable":
                raise ValueError("controlled fact unavailable")
            unstable_order_present = unstable_order_state == "present"
        else:
            unstable_order_present = has_luxian_0609_current_visit_unstable_order(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
            )
        if unstable_order_present:
            return _result(
                "LX0609-007",
                "not_applicable",
                "unstable_patient_order_present",
                executor_type="program",
            )

        record_times: set[datetime] = set()
        substantive_record_without_time = False
        for source_key in _RULE_007_RECORD_SOURCES:
            rows = (
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
            if len(rows) >= luxian_0609_native_source_row_limit(source_key):
                return _result(
                    "LX0609-007",
                    "data_gap",
                    "course_time_source_truncated",
                    executor_type="program",
                )
            for row in rows:
                parsed = _authoritative_course_time(row.get("record_time"))
                if parsed is not None:
                    record_times.add(parsed)
                elif _row_text(row):
                    substantive_record_without_time = True
    except EvidenceMaterialTruncated:
        return _result(
            "LX0609-007",
            "data_gap",
            "course_time_source_truncated",
            executor_type="program",
        )
    except Exception:
        return _result(
            "LX0609-007",
            "data_gap",
            "course_time_source_unavailable",
            executor_type="program",
        )

    ordered_times = sorted(record_times)
    if len(ordered_times) < 2:
        return _result(
            "LX0609-007",
            "data_gap",
            "authoritative_course_time_unavailable",
            executor_type="program",
        )
    interval_over_72h = any(
        current - previous > _RULE_007_MAX_INTERVAL
        for previous, current in zip(ordered_times, ordered_times[1:])
    )
    if interval_over_72h and substantive_record_without_time:
        return _result(
            "LX0609-007",
            "data_gap",
            "authoritative_course_time_incomplete",
            executor_type="program",
        )
    if interval_over_72h:
        return _result(
            "LX0609-007",
            "non_compliant",
            "course_record_interval_over_72h",
            executor_type="program",
        )
    return _result(
        "LX0609-007",
        "compliant",
        "course_record_interval_within_72h",
        executor_type="program",
    )


def _snapshot_unstable_order_state(
    snapshot: Luxian0609EvidenceSnapshot,
) -> str:
    source_key = "inpat_nondrug_order.unstable_order"
    observations = tuple(
        item for item in snapshot.observations if item.source_key == source_key
    )
    facts = tuple(
        item
        for item in snapshot.facts
        if item.source_key == source_key
        and item.fact_type == "current_visit_unstable_order"
    )
    if len(observations) != 1 or len(facts) != 1:
        return "unavailable"
    observation = observations[0]
    fact = facts[0]
    normalized_value = fact.normalized_value
    if not isinstance(normalized_value, Mapping):
        return "unavailable"
    present = normalized_value.get("present")
    if (
        observation.query_state.value == "available"
        and fact.assertion.value == "affirmed"
        and present is True
    ):
        return "present"
    if (
        observation.query_state.value == "empty"
        and fact.assertion.value == "negated"
        and present is False
    ):
        return "absent"
    return "unavailable"


def _rule_007_decision(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> RuleDecision:
    """只用同一 snapshot 的不稳定医嘱事实和两类病程权威时间裁决007。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed 007 evidence session mismatch")

    evaluator_version = "rule007-authoritative-time-v1"
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
    ) -> RuleDecision:
        return RuleDecision(
            rule_id="LX0609-007",
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
        "inpat_nondrug_order.unstable_order",
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

    unstable_source = "inpat_nondrug_order.unstable_order"
    unstable_observation = observations[unstable_source]
    assert unstable_observation is not None
    if unstable_observation.query_state.value == "error":
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_query_error",
            refs=refs,
            confidence=None,
        )
    if unstable_observation.query_state.value == "unavailable":
        return decision(
            applicability=ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="applicability_source_gap",
            refs=refs,
            confidence=None,
        )
    unstable_facts = tuple(
        item
        for item in snapshot.facts
        if item.source_key == unstable_source
        and item.fact_type == "current_visit_unstable_order"
    )
    if len(unstable_facts) != 1:
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            refs=refs,
            confidence=None,
        )
    unstable_fact = unstable_facts[0]
    refs.add(unstable_fact.fact_id)
    unstable_value = unstable_fact.normalized_value
    unstable_present = (
        isinstance(unstable_value, Mapping)
        and unstable_value.get("present") is True
        and unstable_fact.assertion.value == "affirmed"
    )
    unstable_absent = (
        isinstance(unstable_value, Mapping)
        and unstable_value.get("present") is False
        and unstable_fact.assertion.value == "negated"
    )
    if unstable_present:
        return decision(
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="eligibility_not_met",
            refs=refs,
            confidence=1.0,
        )
    if not unstable_absent:
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            refs=refs,
            confidence=None,
        )

    record_times: set[datetime] = set()
    substantive_record_without_time = False
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
        if observation.query_state.value == "unavailable":
            return decision(
                applicability=ApplicabilityState.APPLICABLE,
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="source_unavailable",
                refs=refs,
                confidence=None,
            )
        if observation.completeness.value == "truncated":
            return decision(
                applicability=ApplicabilityState.APPLICABLE,
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="source_truncated",
                refs=refs,
                confidence=None,
            )
        try:
            rows = materials.rows(source_key)
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
            parsed = _authoritative_course_time(row.get("record_time"))
            if parsed is not None:
                record_times.add(parsed)
            elif _row_text(row):
                substantive_record_without_time = True

    ordered_times = sorted(record_times)
    if len(ordered_times) < 2:
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            refs=refs,
            confidence=None,
        )
    interval_over_72h = any(
        current - previous > _RULE_007_MAX_INTERVAL
        for previous, current in zip(ordered_times, ordered_times[1:])
    )
    if interval_over_72h and substantive_record_without_time:
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
            QcDirection.DEFECT if interval_over_72h else QcDirection.SATISFIED
        ),
        reason_code=(
            "threshold_exceeded"
            if interval_over_72h
            else "requirement_within_threshold"
        ),
        refs=refs,
        confidence=1.0,
    )


def _rule_008_009_decision(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
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
    ) -> RuleDecision:
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
            parsed_date = _authoritative_natural_date(row.get("record_time"))
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
            ):
                timed_record_dates.add(parsed_date)

    ordered_dates = sorted(timed_record_dates)
    if rule_id == "LX0609-008":
        dates_with_anchor = [anchor_date, *ordered_dates]
        if horizon_date is not None:
            dates_with_anchor.append(horizon_date)
        interval_exceeded = any(
            (current - previous).days > _RULE_008_MAX_GAP_DAYS
            for previous, current in zip(
                dates_with_anchor,
                dates_with_anchor[1:],
            )
        )
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
        )

    prefix_end = horizon_date or (ordered_dates[-1] if ordered_dates else anchor_date)
    expected_dates = {
        anchor_date + timedelta(days=offset)
        for offset in range((prefix_end - anchor_date).days + 1)
    }
    if expected_dates.difference(timed_record_dates):
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="requirement_violated",
            refs=refs,
            confidence=1.0,
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
    # 逐日记录已满足；“病情变化时是否记录”仍需 Phase 5 裁剪语义判断。
    return decision(
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.DATA_GAP,
        qc_direction=QcDirection.UNKNOWN,
        reason_code="required_field_missing",
        refs=refs,
        confidence=None,
    )


def _rule_009_semantic_context(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> tuple[str, bool, bool]:
    """返回完整语义投影及截断标记；不允许静默裁剪后交给模型。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        return "", False, False
    try:
        critical_dates = tuple(
            _authoritative_natural_date(row.get("prescribed_datetime"))
            for row in materials.rows(CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY)
            if row.get("severity") == "critical"
        )
        horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
    except Exception:
        return "", False, False
    if (
        not critical_dates
        or any(item is None for item in critical_dates)
        or len(horizon_rows) != 1
    ):
        return "", False, False
    anchor_date = min(item for item in critical_dates if item is not None)
    horizon_date = _authoritative_natural_date(horizon_rows[0].get("horizon_date"))
    if horizon_date is None or horizon_date < anchor_date:
        return "", False, False

    parts: list[str] = []
    substantive_dates: set[date] = set()
    for source_key in _RULE_007_RECORD_SOURCES:
        try:
            rows = materials.rows(source_key)
        except Exception:
            return "", False, False
        eligible: list[tuple[date, str]] = []
        for row in rows:
            record_date = _authoritative_natural_date(row.get("record_time"))
            content = _rule_009_substantive_text(row)
            if (
                record_date is None
                or not anchor_date <= record_date <= horizon_date
                or not content
            ):
                continue
            eligible.append((record_date, content))
            substantive_dates.add(record_date)
        if len(eligible) > _MAX_ROWS_PER_SOURCE:
            return "", True, False
        for record_date, content in eligible:
            if len(content) > _MAX_ROW_CHARS:
                return "", True, False
            parts.append(
                f"[{source_key}] 记录日={record_date.isoformat()}；"
                f"内容={content}"
            )
    expected_dates = {
        anchor_date + timedelta(days=offset)
        for offset in range((horizon_date - anchor_date).days + 1)
    }
    if expected_dates.difference(substantive_dates):
        return "", False, False
    context = "\n".join(parts)
    return (
        ("", True, False)
        if len(context) > _MAX_CONTEXT_CHARS
        else (context, False, True)
    )


def _rule_009_semantic_prompt(*, context: str) -> str:
    return f"""你是 LX0609-009 病危病程语义核对器。

Python 已确认：从病危医嘱开立自然日至权威评价终点，每个自然日均存在日常病程或上级医师查房记录。不要重新判断每日频次。
你只判断已提供记录中出现的病情变化，是否有及时、对应的病情记录与处置说明：
- satisfied：记录明确显示病情稳定无变化，或出现的病情变化均有及时对应记录；
- defect：记录明确显示发生病情变化，但对应记录或处置明显不及时；
- unknown：材料不足以可靠判断，禁止猜测。

只能使用以下当前就诊、评价区间内的裁剪记录：
{context}

只输出 JSON：{{"semantic_state":"satisfied|defect|unknown"}}"""


def _parse_rule_009_semantic_state(response: Mapping[str, Any]) -> str | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>",
        "",
        _response_text(response),
        flags=re.IGNORECASE,
    ).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    state = payload.get("semantic_state") if isinstance(payload, Mapping) else None
    return state if state in {"satisfied", "defect", "unknown"} else None


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
    else:
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            data_gap_reason,
            None,
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
        evaluator_version="course-severity-semantic-v1",
        confidence=confidence,
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
        # trigger 读取完整 bounded diagnosis，模型上下文只保留最多8条受控主要诊断。
        context_rows = [item for item in context_rows if item[0] != "diagnosis"]
        context_rows.extend(
            (
                "diagnosis",
                row,
                content,
            )
            for row in _source_rows(documents, "diagnosis", limit=None)
            if _clean(row.get("diagnosis_type")) == "主要诊断"
            and (content := _row_text(row))
        )
        admission_rows = [item for item in context_rows if item[0] == "admission_record"]
        diagnosis_rows = [item for item in context_rows if item[0] == "diagnosis"]
        context_rows = admission_rows[:_MAX_ROWS_PER_SOURCE] + diagnosis_rows[:_MAX_ROWS_PER_SOURCE]
    for source_key, row, content in context_rows:
        record_time = _clean(row.get("record_time")) or "未提供"
        parts.append(f"[{source_key}] 记录时间={record_time}；内容={content[:_MAX_ROW_CHARS]}")
    return "\n".join(parts)[:_MAX_CONTEXT_CHARS]


def _prompt(wrapper: Mapping[str, Any], *, context: str) -> str:
    custom_prompt = _MAPPING_LINE_PATTERN.sub(
        "", str(wrapper.get("custom_prompt") or "")
    )
    return (
        custom_prompt.replace("{defect_level}", str(wrapper.get("defect_level") or ""))
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
        r"<think>[\s\S]*?</think>",
        "",
        _response_text(response),
        flags=re.IGNORECASE,
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
    extra_metadata: Mapping[str, Any] | None = None,
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
    return item


def _normalized_for_similarity(content: str) -> str:
    value = _DATE_PATTERN.sub("", content)
    value = _TIME_PATTERN.sub("", value)
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", value).lower()


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
    support_source_keys: tuple[str, ...] = ()
    # 仅在同一次执行中传给裁剪 LLM；绝不能进入结果或安全 metadata。
    semantic_input: "_CopySemanticInput | None" = field(
        default=None, repr=False, compare=False
    )


@dataclass(frozen=True, repr=False)
class _CopySemanticInput:
    left: str
    right: str
    event_rows: tuple[tuple[str, str, str], ...]
    support_source_keys: tuple[str, ...]


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


def _copy_support_event_time(
    source_key: str, row: Mapping[str, Any]
) -> datetime | None:
    """017 只认可各来源的临床事件时间，不把同步/修改时间伪装成新事实。"""

    fields_by_source = {
        "exam_item_report": ("report_time",),
        "labtest_master": ("report_time",),
        "labtest_item_report": ("report_time",),
        "inpat_drug_order": ("prescribed_datetime",),
        "surgery_record": (
            "surgery_begin_time",
            "surgery_end_time",
            "record_time",
        ),
        "mr_surgery": ("surgery_begin_datetime", "surgery_end_datetime"),
    }
    for key in fields_by_source.get(source_key, ()):
        value = row.get(key)
        parsed = _authoritative_course_time(value)
        if parsed is not None:
            return parsed
        # surgery_record 的 ETL 原值允许严格的 +08 整值格式；其他来源不得
        # 用字符串猜时间，更不能回退到 update_time/last_modified_datetime。
        if (
            source_key == "surgery_record"
            and key in {"surgery_begin_time", "surgery_end_time"}
            and isinstance(value, str)
        ):
            try:
                return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S+08")
            except ValueError:
                continue
    return None


def _copy_event_rows(
    support_documents: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    left_time: datetime,
    right_time: datetime,
) -> tuple[tuple[str, str, str], ...]:
    """返回相邻病程区间内的最小事件上下文：hash ref、来源类型、裁剪正文。"""

    events: list[tuple[str, str, str]] = []
    for source_key in _COPY_SUPPORT_SOURCES:
        rows = tuple(support_documents.get(source_key, ()))
        refs = build_material_document_refs(source_key, rows)
        for row, event_ref in zip(rows, refs):
            event_time = _copy_support_event_time(source_key, row)
            content = _row_text(row)
            if (
                event_time is None
                or not content
                or event_time <= left_time
                or event_time > right_time
            ):
                continue
            events.append((event_ref, source_key, content[:_MAX_ROW_CHARS]))
    return tuple(events)


def _copy_similarity_band(value: float) -> str:
    if value < _COPY_SIMILARITY_THRESHOLD:
        return "low"
    if value >= _COPY_AUTO_NONCOMPLIANT_MIN:
        return "strong"
    return "gray"


def _assess_copy(
    documents: Mapping[str, Any],
    *,
    source_complete: bool = False,
) -> _CopyRuleOutcome:
    """只按相邻、不同日期且带 record_time 的病程对做 017 初筛。"""

    rows = _substantive_rows(
        documents,
        _COPY_SOURCES,
        limit_per_source=None if source_complete else _MAX_ROWS_PER_SOURCE,
    )
    comparable: list[tuple[datetime, str, str, bool, str]] = []
    seen_document_ids: set[str] = set()
    for source_key, row, content in rows:
        if _clean(row.get("document_title")) == "长期医嘱":
            continue
        normalized = _normalized_for_similarity(content)
        if len(normalized) < _MIN_COMPARABLE_CHARS:
            continue
        record_time = _authoritative_course_time(row.get("record_time"))
        if record_time is None:
            return _CopyRuleOutcome(
                status="data_gap",
                reason_code="copy_authoritative_time_missing",
                executor_type="program",
                safe_metadata={
                    "comparable_document_count": len(comparable),
                    "similarity_band": "unknown",
                    "update_adequacy": "unknown",
                    "event_types": [],
                    "event_refs": [],
                    "event_ref_count": 0,
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
            )
        )

    safe_metadata: dict[str, Any] = {
        "comparable_document_count": len(comparable),
        "maximum_similarity": 0.0,
        "similarity_threshold": _COPY_SIMILARITY_THRESHOLD,
        "similarity_band": "unknown",
        "best_match_source_types": [],
        "template_shell_only": False,
        "update_adequacy": "unknown",
        "event_types": [],
        "event_refs": [],
        "event_ref_count": 0,
    }
    if len(comparable) < 2:
        return _CopyRuleOutcome(
            status="not_applicable",
            reason_code="insufficient_independent_course_records",
            executor_type="program",
            safe_metadata=safe_metadata,
        )

    ordered = sorted(comparable, key=lambda item: (item[0], item[1], item[2]))
    pairs = [
        (left, right)
        for left, right in zip(ordered, ordered[1:])
        if left[0].date() < right[0].date()
    ]
    if not pairs:
        return _CopyRuleOutcome(
            status="data_gap",
            reason_code="copy_adjacent_day_pair_unavailable",
            executor_type="program",
            safe_metadata=safe_metadata,
        )

    maximum = -1.0
    best_pair: tuple[tuple[datetime, str, str, bool, str], tuple[datetime, str, str, bool, str]] | None = None
    longest_block = 0
    substantial_coverage = 0.0
    template_shell_only = False
    for left, right in pairs:
        matcher = SequenceMatcher(None, left[2], right[2], autojunk=False)
        similarity = matcher.ratio()
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
    safe_metadata.update(
        {
            "maximum_similarity": round(maximum, 4),
            "similarity_band": _copy_similarity_band(maximum),
            "best_match_source_types": [best_pair[0][1], best_pair[1][1]] if best_pair else [],
            "longest_matching_block_chars": longest_block,
            "substantial_matching_coverage": round(substantial_coverage, 4),
            "template_shell_only": template_shell_only,
        }
    )
    if maximum <= _COPY_SIMILARITY_THRESHOLD:
        return _CopyRuleOutcome(
            status="compliant",
            reason_code="copy_similarity_within_threshold",
            executor_type="program",
            safe_metadata=safe_metadata,
        )
    return _CopyRuleOutcome(
        status="non_compliant",
        reason_code="copy_similarity_threshold_exceeded",
        executor_type="program",
        safe_metadata=safe_metadata,
    )


def _copy_result(
    documents: Mapping[str, Any], *, source_complete: bool = False
) -> dict[str, Any]:
    """017 只比较独立病程/查房文书的全文相似度，不调用模型。"""

    return _render_copy_outcome(
        _assess_copy(documents, source_complete=source_complete)
    )


def _copy_semantic_prompt(*, semantic_input: _CopySemanticInput) -> str:
    """017 仅比较相邻病程及该区间内经白名单绑定的事件。"""

    events = "\n".join(
        f"[事件 ref={event_ref} type={source_key}] {content}"
        for event_ref, source_key, content in semantic_input.event_rows
    ) or "[无已绑定的区间事件]"
    return f"""你是 LX0609-017 病程动态更新核对器。只根据两份相邻病程和给出的区间事件判断，禁止猜测。
- true_copy：当前病程实质复制且没有体现已给出的新事件；
- reasonable_continuation：病情稳定下的合理延续；
- unknown：无法可靠判断。
- updated：当前病程已体现新增临床事实；
- missing：已给出的新事件没有在当前病程体现；
- reasonable_continuation：没有需要补写的新变化；
- unknown：无法可靠判断。

[前一份病程]
{semantic_input.left[:_MAX_ROW_CHARS]}

[当前病程]
{semantic_input.right[:_MAX_ROW_CHARS]}

[区间事件]
{events}

只输出 JSON：{{"copy_state":"true_copy|reasonable_continuation|unknown","update_adequacy":"updated|reasonable_continuation|missing|unknown","event_refs":["仅可填写给出的 ref"]}}"""


def _parse_copy_semantic_fact(
    response: Mapping[str, Any], *, allowed_event_refs: frozenset[str]
) -> tuple[str, str, tuple[str, ...]] | None:
    cleaned = re.sub(
        r"<think>[\s\S]*?</think>",
        "",
        _response_text(response),
        flags=re.IGNORECASE,
    ).strip()
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, Mapping):
        return None
    copy_state = payload.get("copy_state")
    update_adequacy = payload.get("update_adequacy")
    event_refs = payload.get("event_refs")
    if (
        copy_state not in {"true_copy", "reasonable_continuation", "unknown"}
        or update_adequacy not in {
            "updated",
            "reasonable_continuation",
            "missing",
            "unknown",
        }
        or not isinstance(event_refs, list)
        or not all(isinstance(item, str) for item in event_refs)
    ):
        return None
    normalized_refs = tuple(event_refs)
    if len(normalized_refs) != len(set(normalized_refs)) or not set(normalized_refs).issubset(allowed_event_refs):
        return None
    return copy_state, update_adequacy, normalized_refs


async def _resolve_copy_semantic(
    outcome: _CopyRuleOutcome,
    llm_client: CourseQualityLLMClient | None,
) -> _CopyRuleOutcome:
    """将017灰区安全映射为一次受控 LLM 事实；任一失败均不得硬判复制。"""

    if outcome.status != "evaluation_unknown":
        return outcome
    if outcome.semantic_input is None:
        return _CopyRuleOutcome(
            status="data_gap",
            reason_code="copy_semantic_input_unavailable",
            executor_type="program",
            safe_metadata=outcome.safe_metadata,
            support_source_keys=(),
        )
    if llm_client is None:
        return _CopyRuleOutcome(
            status="data_gap",
            reason_code="copy_semantic_llm_unavailable",
            executor_type="program",
            safe_metadata=outcome.safe_metadata,
            support_source_keys=(),
        )
    try:
        response = await llm_client.generate(
            _copy_semantic_prompt(semantic_input=outcome.semantic_input)
        )
    except Exception:
        return _CopyRuleOutcome(
            status="data_gap",
            reason_code="copy_semantic_model_error",
            executor_type="llm",
            safe_metadata=outcome.safe_metadata,
            support_source_keys=(),
        )
    prompt, completion, total, elapsed = _usage(response)
    parsed = _parse_copy_semantic_fact(
        response,
        allowed_event_refs=frozenset(
            event_ref for event_ref, _, _ in outcome.semantic_input.event_rows
        ),
    )
    if parsed is None:
        status, reason_code = "data_gap", "copy_semantic_invalid_output"
        safe_metadata = dict(outcome.safe_metadata)
        used_support_source_keys: tuple[str, ...] = ()
    else:
        copy_state, update_adequacy, event_refs = parsed
        safe_metadata = dict(outcome.safe_metadata)
        safe_metadata.update(
            {
                "update_adequacy": update_adequacy,
                "event_refs": list(event_refs),
                "event_ref_count": len(event_refs),
                "event_types": sorted(
                    {
                        source_key
                        for event_ref, source_key, _ in outcome.semantic_input.event_rows
                        if event_ref in set(event_refs)
                    }
                ),
            }
        )
        if copy_state == "reasonable_continuation" and update_adequacy in {
            "updated",
            "reasonable_continuation",
        }:
            status, reason_code = "compliant", "copy_clinical_update_adequate"
        elif (
            copy_state == "true_copy"
            and update_adequacy == "missing"
            and event_refs
        ):
            status, reason_code = "non_compliant", "copy_clinical_update_missing"
        else:
            status, reason_code = "data_gap", "copy_semantic_unknown"
        used_support_source_keys = tuple(safe_metadata["event_types"])
    return _CopyRuleOutcome(
        status=status,
        reason_code=reason_code,
        executor_type="llm",
        safe_metadata=safe_metadata,
        support_source_keys=used_support_source_keys,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
        api_time=elapsed,
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
    source_keys = required_copy_sources | set(outcome.support_source_keys)
    observations = tuple(
        item for item in snapshot.observations if item.source_key in source_keys
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
        "LX0609-018": ("admission_record", "diagnosis"),
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
        "LX0609-018": ("admission_record", "diagnosis"),
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
    elif outcome.status == "technical_error":
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
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
            frozenset({"admission_record", "diagnosis"}),
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
    # 只采信受控类型“主要诊断”；其他诊断、诊断史或任意文本都不能补齐018。
    for row in _source_rows(documents, "diagnosis", limit=None):
        if _clean(row.get("diagnosis_type")) != "主要诊断":
            continue
        diagnosis_text = diagnosis_text or bool(
            _clean(row.get("diagnosis_name") or row.get("diagnosis_code"))
        )
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

    for rule_id in selected:
        if rule_id in projection_gap_rule_ids:
            continue
        if rule_id == "LX0609-007" and rule_id in typed_requested:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            decisions.append(
                _rule_007_decision(
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
                )
            )
            continue
        if rule_id in {"LX0609-008", "LX0609-009"} and rule_id in typed_requested:
            assert evidence_snapshot is not None
            assert evidence_materials is not None
            base_decision = _rule_008_009_decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
            # 008 是纯日期规则。009 也先由 Python 判定每日频次；仅频次完整
            # 且具有权威终点时，才允许一次受控语义调用补“病情变化是否及时记录”。
            if (
                rule_id != "LX0609-009"
                or base_decision.reason_code != "required_field_missing"
            ):
                decisions.append(base_decision)
                continue
            context, overflow, ready = _rule_009_semantic_context(
                snapshot=evidence_snapshot,
                materials=evidence_materials,
            )
            if overflow or not ready or llm_client is None:
                decisions.append(
                    _rule_009_semantic_decision(base_decision=base_decision)
                )
                continue
            llm_call_count += 1
            try:
                response = await llm_client.generate(
                    _rule_009_semantic_prompt(context=context)
                )
            except Exception:
                # 语义调用失败不是“无病危医嘱”；频次事实仍在，但语义无法确认。
                decisions.append(
                    _rule_009_semantic_decision(base_decision=base_decision)
                )
                continue
            prompt, completion, total, elapsed = _usage(response)
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total
            api_time += elapsed
            decisions.append(
                _rule_009_semantic_decision(
                    base_decision=base_decision,
                    semantic_state=_parse_rule_009_semantic_state(response),
                )
            )
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
            if rule_id == "LX0609-016" and (
                not _substantive_admission_rows(typed_documents)
                or not _substantive_first_course_rows(typed_documents)
            ):
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status="data_gap",
                        reason_code="admission_or_first_course_unavailable",
                        executor_type="program",
                    )
                )
                continue
            if rule_id == "LX0609-018" and (
                not _substantive_admission_rows(typed_documents)
                or not _admission_material_ready(typed_documents, ())
            ):
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status="data_gap",
                        reason_code="complaint_or_primary_diagnosis_unavailable",
                        executor_type="program",
                    )
                )
                continue
            context = _context(rule_id, typed_documents)
            wrapper = wrappers_by_id.get(rule_id)
            if wrapper is None or not _clean(wrapper.get("custom_prompt")) or not context:
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status="data_gap",
                        reason_code="course_prompt_input_unavailable",
                        executor_type="program",
                    )
                )
                continue
            if llm_client is None:
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status="data_gap",
                        reason_code="course_llm_unavailable",
                        executor_type="program",
                    )
                )
                continue
            llm_call_count += 1
            try:
                response = await llm_client.generate(
                    _prompt(wrapper, context=context)
                )
            except Exception:
                emit_course_semantic(
                    _CourseSemanticOutcome(
                        rule_id=rule_id,
                        status="technical_error",
                        reason_code="model_transport_error",
                        executor_type="llm",
                    )
                )
                continue
            prompt, completion, total, elapsed = _usage(response)
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total
            api_time += elapsed
            is_compliant = _parse_is_compliant(response)
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
            emit_copy(copy_outcome)
            continue

        controlled_fact = ""
        if rule_id == "LX0609-007":
            results.append(
                _rule_007_result(
                    serious_state=serious_state,
                    critical_state=critical_state,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    source_schema=source_schema,
                    evidence_snapshot=evidence_snapshot,
                    evidence_materials=evidence_materials,
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
            if not _substantive_admission_rows(
                documents
            ) or not _substantive_first_course_rows(documents):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "admission_or_first_course_unavailable",
                        executor_type="program",
                    )
                )
                continue
        elif rule_id == "LX0609-018":
            if not _substantive_rows(
                documents, ("admission_record",)
            ) or not _admission_material_ready(documents, facts):
                results.append(
                    _result(
                        rule_id,
                        "data_gap",
                        "complaint_or_primary_diagnosis_unavailable",
                        executor_type="program",
                    )
                )
                continue

        context = _context(rule_id, documents, controlled_fact=controlled_fact)
        wrapper = wrappers_by_id.get(rule_id)
        if wrapper is None or not _clean(wrapper.get("custom_prompt")) or not context:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "course_prompt_input_unavailable",
                    executor_type="program",
                )
            )
            continue
        if llm_client is None:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "course_llm_unavailable",
                    executor_type="program",
                )
            )
            continue
        llm_call_count += 1
        try:
            response = await llm_client.generate(_prompt(wrapper, context=context))
        except Exception:
            results.append(
                _result(
                    rule_id,
                    "data_gap",
                    "course_llm_failure",
                    executor_type="llm",
                )
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
        status = "compliant" if is_compliant else "non_compliant"
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
            )
        )

    return NativeCourseQualityExecutionResult(
        results=tuple(results),
        planned_rule_ids=selected,
        decisions=tuple(decisions),
        llm_call_count=llm_call_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        api_time=api_time,
    )
