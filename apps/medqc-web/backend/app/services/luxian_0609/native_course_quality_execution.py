"""LX0609 查房病程族原生执行：强事实门控、裁剪文书与确定性复制检测。"""

from __future__ import annotations

from dataclasses import dataclass
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
_COPY_STRONG_EXACT_THRESHOLD = 0.95
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
    "LX0609-018": ("admission_record",),
}

_RULE_007_MAX_INTERVAL = timedelta(hours=72)
_RULE_008_MAX_GAP_DAYS = 2

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
    )


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
    relevant_orders = tuple(row for row in order_rows if row.get("severity") == target)
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
    if (
        discharge_observation.query_state.value == "unavailable"
        or discharge_observation.completeness.value == "truncated"
    ):
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

    record_dates: set[date] = set()
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
                record_dates.add(parsed_date)

    ordered_dates = sorted(record_dates)
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
    if expected_dates.difference(record_dates):
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


def _context(
    rule_id: str,
    documents: Mapping[str, Any],
    *,
    controlled_fact: str = "",
) -> str:
    parts = [f"[受控事实] {controlled_fact}"] if controlled_fact else []
    for source_key, row, content in _substantive_rows(
        documents, _RULE_CONTEXT_SOURCES[rule_id]
    ):
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


@dataclass(frozen=True)
class _CopyAssessment:
    terminal_outcome: _CopyRuleOutcome | None
    gray_context: str
    safe_metadata: Mapping[str, Any]


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
    return item


def _copy_gray_context(
    *, left_source: str, left_content: str, right_source: str, right_content: str,
    maximum_similarity: float,
) -> str:
    return (
        f"[Python候选] 全文相似度={maximum_similarity * 100:.2f}%，"
        "但未达到强复制证据标准。只比较以下两份当前就诊病程，不得引用其他病历。\n"
        f"[文书A:{left_source}]\n{left_content[:_MAX_ROW_CHARS]}\n"
        f"[文书B:{right_source}]\n{right_content[:_MAX_ROW_CHARS]}"
    )[:_MAX_CONTEXT_CHARS]


def _copy_gray_prompt(*, context: str) -> str:
    return f"""你是病历复制质控裁决器，只判断 LX0609-017：两份病程是否属于不合理复制。

判定约束：
1. Python 已发现全文相似度略高于70%，但这本身不能直接判缺陷。
2. 常规查体模板、共同诊断背景和固定格式重复，不等于不合理复制。
3. 如果症状变化、客观检查数值、病情评估或治疗计划存在明确实质更新，应判合规。
4. 只有核心临床内容大段复用，且缺少针对当日病情的实质变化和处置更新，才判不合规。
5. 不得推测未提供的病历内容。

{context}

只输出JSON：{{"is_compliant": true/false}}"""


def _assess_copy(
    documents: Mapping[str, Any], *, source_complete: bool = False
) -> _CopyAssessment:
    rows = _substantive_rows(
        documents,
        _ROUND_SOURCES,
        limit_per_source=None if source_complete else _MAX_ROWS_PER_SOURCE,
    )
    comparable: list[tuple[str, str, str]] = []
    seen_documents: set[tuple[str, str, str]] = set()
    for source_key, row, content in rows:
        normalized = _normalized_for_similarity(content)
        if len(normalized) < _MIN_COMPARABLE_CHARS:
            continue
        document_id = _clean(row.get("document_id"))
        identity = (
            source_key,
            "document_id" if document_id else _clean(row.get("record_time")),
            document_id or normalized,
        )
        if identity in seen_documents:
            continue
        seen_documents.add(identity)
        comparable.append((source_key, normalized, content))
    safe_metadata: dict[str, Any] = {
        "comparable_document_count": len(comparable),
        "maximum_similarity": 0.0,
        "similarity_threshold": _COPY_SIMILARITY_THRESHOLD,
        "best_match_source_types": [],
    }
    if not rows:
        return _CopyAssessment(
            terminal_outcome=_CopyRuleOutcome(
                status="not_applicable" if source_complete else "data_gap",
                reason_code=(
                    "insufficient_comparable_course_records"
                    if source_complete
                    else "course_comparison_material_unavailable"
                ),
                executor_type="program",
                safe_metadata=safe_metadata,
            ),
            gray_context="",
            safe_metadata=safe_metadata,
        )
    if len(comparable) < 2:
        return _CopyAssessment(
            terminal_outcome=_CopyRuleOutcome(
                status="not_applicable",
                reason_code="insufficient_comparable_course_records",
                executor_type="program",
                safe_metadata=safe_metadata,
            ),
            gray_context="",
            safe_metadata=safe_metadata,
        )
    maximum = -1.0
    best_source_types: list[str] = []
    best_pair: tuple[str, str, str, str] | None = None
    longest_block = 0
    substantial_coverage = 0.0
    for index, (left_source, left, left_content) in enumerate(comparable):
        for right_source, right, right_content in comparable[index + 1 :]:
            matcher = SequenceMatcher(None, left, right, autojunk=False)
            similarity = matcher.ratio()
            if similarity > maximum:
                maximum = similarity
                best_source_types = [left_source, right_source]
                best_pair = (left_source, left_content, right_source, right_content)
                blocks = [block.size for block in matcher.get_matching_blocks() if block.size]
                longest_block = max(blocks, default=0)
                substantial_chars = sum(size for size in blocks if size >= 40)
                substantial_coverage = substantial_chars / max(1, min(len(left), len(right)))
    maximum = max(maximum, 0.0)
    safe_metadata.update(
        {
            "maximum_similarity": round(maximum, 4),
            "best_match_source_types": best_source_types,
            "longest_matching_block_chars": longest_block,
            "substantial_matching_coverage": round(substantial_coverage, 4),
        }
    )
    evidence = (
        f"已比较 {len(comparable)} 份病程/查房记录，最高全文相似度 "
            f"{maximum * 100:.4f}%，判定阈值 {_COPY_SIMILARITY_THRESHOLD * 100:.0f}%。"
    )
    # 长模板块会显著抬高匹配长度和覆盖率，但不能证明动态临床内容被复制。
    # Python 只强判近乎全文复制；70%～95%统一交给一次裁剪语义判断。
    strong_copy = maximum >= _COPY_STRONG_EXACT_THRESHOLD
    if maximum > _COPY_SIMILARITY_THRESHOLD and strong_copy:
        return _CopyAssessment(
            _CopyRuleOutcome(
                status="non_compliant",
                reason_code="strong_copy_evidence",
                executor_type="program",
                safe_metadata=safe_metadata,
                findings="发现两份病程/查房记录全文相似度超过70%，存在高度重复。",
                evidence=evidence,
                suggestion="请核对重复记录，补充本次病情变化、诊疗调整和查房意见。",
            ),
            "",
            safe_metadata,
        )
    if maximum > _COPY_SIMILARITY_THRESHOLD and best_pair is not None:
        left_source, left_content, right_source, right_content = best_pair
        return _CopyAssessment(
            terminal_outcome=None,
            gray_context=_copy_gray_context(
                left_source=left_source,
                left_content=left_content,
                right_source=right_source,
                right_content=right_content,
                maximum_similarity=maximum,
            ),
            safe_metadata=safe_metadata,
        )
    return _CopyAssessment(
        _CopyRuleOutcome(
            status="compliant",
            reason_code="course_similarity_within_threshold",
            executor_type="program",
            safe_metadata=safe_metadata,
            evidence=evidence,
        ),
        "",
        safe_metadata,
    )


def _copy_result(
    documents: Mapping[str, Any], *, source_complete: bool = False
) -> dict[str, Any]:
    """兼容纯函数测试；灰区必须由正式执行入口调用裁剪模型。"""

    assessment = _assess_copy(documents, source_complete=source_complete)
    if assessment.terminal_outcome is not None:
        return _render_copy_outcome(assessment.terminal_outcome)
    return _result(
        "LX0609-017",
        "data_gap",
        "copy_semantic_review_required",
        executor_type="program",
        extra_metadata=assessment.safe_metadata,
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
    source_keys = {"daily_course_record", "senior_course_record"}
    observations = tuple(
        item for item in snapshot.observations if item.source_key in source_keys
    )
    if {item.source_key for item in observations} != source_keys:
        return RuleDecision(
            rule_id="LX0609-017",
            snapshot_hash=snapshot.snapshot_hash,
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            fact_refs=(),
            evaluator_version="rule017-copy-v1",
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
        evaluator_version="rule017-copy-v1",
        confidence=None,
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
        "LX0609-018": ("admission_record",),
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
        "LX0609-018": ("admission_record",),
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
                for source_key in (
                    "daily_course_record",
                    "senior_course_record",
                ):
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
            decisions.append(
                _rule_008_009_decision(
                    rule_id=rule_id,
                    snapshot=evidence_snapshot,
                    materials=evidence_materials,
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
                        status="data_gap",
                        reason_code="course_llm_failure",
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
                        status="data_gap",
                        reason_code="course_llm_invalid_output",
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
            assessment = _assess_copy(
                copy_documents,
                source_complete=copy_documents is not documents,
            )
            if assessment.terminal_outcome is not None:
                emit_copy(assessment.terminal_outcome)
                continue
            wrapper = wrappers_by_id.get(rule_id)
            if (
                wrapper is None
                or not _clean(wrapper.get("custom_prompt"))
                or not assessment.gray_context
            ):
                emit_copy(
                    _CopyRuleOutcome(
                        status="data_gap",
                        reason_code="copy_prompt_input_unavailable",
                        executor_type="program",
                        safe_metadata=assessment.safe_metadata,
                    )
                )
                continue
            if llm_client is None:
                emit_copy(
                    _CopyRuleOutcome(
                        status="data_gap",
                        reason_code="copy_llm_unavailable",
                        executor_type="program",
                        safe_metadata=assessment.safe_metadata,
                    )
                )
                continue
            llm_call_count += 1
            try:
                response = await llm_client.generate(
                    _copy_gray_prompt(context=assessment.gray_context)
                )
            except Exception:
                emit_copy(
                    _CopyRuleOutcome(
                        status="data_gap",
                        reason_code="copy_llm_failure",
                        executor_type="llm",
                        safe_metadata=assessment.safe_metadata,
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
                emit_copy(
                    _CopyRuleOutcome(
                        status="data_gap",
                        reason_code="copy_llm_invalid_output",
                        executor_type="llm",
                        safe_metadata=assessment.safe_metadata,
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                        total_tokens=total,
                        api_time=elapsed,
                    )
                )
                continue
            emit_copy(
                _CopyRuleOutcome(
                    status="compliant" if is_compliant else "non_compliant",
                    reason_code="copy_gray_llm",
                    executor_type="llm",
                    safe_metadata=assessment.safe_metadata,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    api_time=elapsed,
                )
            )
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
