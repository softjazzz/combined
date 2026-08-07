"""LX0609 查房病程族原生执行：强事实门控、裁剪文书与确定性复制检测。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from functools import lru_cache
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
from .rule_contracts import RuleCriterionContract, load_luxian_0609_rule_contracts
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
_RULE_007_RECORD_SOURCES = (
    "daily_course_record",
    "senior_course_record",
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
_MAX_ROWS_PER_SOURCE = 8
_MAX_ROW_CHARS = 1400
_MAX_CONTEXT_CHARS = 18000
_MAX_RULE_009_EXTERNAL_EVENT_ROWS = 8
_MIN_COMPARABLE_CHARS = 24
_MIN_FIRST_COURSE_BODY_CHARS = 6
_COPY_SIMILARITY_THRESHOLD = 0.70
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
_COMPLAINT_VALUE_PATTERN = re.compile(r"主诉\s*[:：]\s*([^；;。\r\n]{1,160})")
_DIAGNOSIS_PATTERN = re.compile(r"(?:第一诊断|主要诊断|初步诊断|入院诊断|首页第一诊断)\s*[:：]\s*[^；;。]{2,}")
_PRIMARY_DIAGNOSIS_TYPES = frozenset({"主要诊断", "主诊断", "第一诊断"})
_ADMISSION_FIRST_DIAGNOSIS_TYPES = frozenset({"初步诊断", "入院诊断"})
_LX018_DIAGNOSIS_SOURCES = ("diagnosis", "admission_record_diagnosis")
_NUMBERED_DIAGNOSIS_ITEM_PATTERN = re.compile(
    r"(?:^|[，,；;\s]+)\d+\s*[、.．]\s*([^，,；;\n\r]+)"
)
_LX018_DIAGNOSTIC_RELATION_STATES = frozenset(
    {"supported", "unsupported", "mismatch", "unknown"}
)
_LX018_DIAGNOSTIC_REASON_DIMENSIONS = frozenset(
    {
        "anatomic_site",
        "laterality",
        "symptom_pattern",
        "disease_course",
        "disease_direction",
    }
)

_RULE_CONTEXT_SOURCES = {
    "LX0609-007": _RULE_007_RECORD_SOURCES,
    "LX0609-008": _TIMELINE_SOURCES,
    "LX0609-009": _TIMELINE_SOURCES,
    "LX0609-016": ("admission_record", "first_course_record"),
    "LX0609-018": ("admission_record", "diagnosis", "admission_record_diagnosis"),
}

_RULE_007_MAX_INTERVAL = timedelta(hours=72)
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
    async def generate(self, prompt: str) -> dict[str, Any]:
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


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


@lru_cache(maxsize=1)
def _lx018_criteria() -> tuple[RuleCriterionContract, RuleCriterionContract]:
    contract = next(
        item
        for item in load_luxian_0609_rule_contracts()
        if item.rule_id == "LX0609-018"
    )
    criteria = {item.criterion_id: item for item in contract.criteria}
    length = criteria.get("chief_complaint_length")
    relation = criteria.get("diagnostic_direction")
    if (
        length is None
        or length.kind != "text_length"
        or relation is None
        or relation.kind != "semantic_relation"
        or len(criteria) != 2
    ):
        raise ValueError("LX0609-018 criteria contract is incomplete")
    return length, relation


def _lx018_complaint_text(documents: Mapping[str, Any]) -> str:
    for row in _source_rows(documents, "admission_record"):
        complaint = _clean(row.get("chief_complaint") or row.get("complaint"))
        if complaint:
            return complaint
        match = _COMPLAINT_VALUE_PATTERN.search(_row_text(row))
        if match:
            return _clean(match.group(1))
    return ""


def _lx018_length_criterion_result(
    documents: Mapping[str, Any],
) -> CriterionResult:
    criterion, _ = _lx018_criteria()
    complaint = _lx018_complaint_text(documents)
    if not complaint:
        return CriterionResult(
            criterion_id=criterion.criterion_id,
            status=CriterionStatus.UNKNOWN,
            reason_code="required_field_missing",
            operator=criterion.operator,
            unit=criterion.unit,
            expected_value=criterion.expected,
        )
    # 客户已确认“≤20字”为长度合规边界；诊断指向由独立子判定负责。
    # 标点和内部空白均计入，避免长度计算与前端原文显示不一致。
    actual = len(complaint)
    passed = actual <= int(criterion.expected)
    return CriterionResult(
        criterion_id=criterion.criterion_id,
        status=CriterionStatus.PASSED if passed else CriterionStatus.FAILED,
        reason_code=(
            "requirement_satisfied" if passed else criterion.failure_reason_code
        ),
        actual_value=actual,
        expected_value=criterion.expected,
        operator=criterion.operator,
        unit=criterion.unit,
    )


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
        or row.get("chief_complaint")
        or row.get("complaint")
        or row.get("diagnosis_name")
        or row.get("diagnosis_code")
    )


def _split_numbered_diagnosis_items(value: Any) -> tuple[str, ...]:
    text = _clean(value)
    if not text:
        return ()
    items = tuple(
        item.strip()
        for item in _NUMBERED_DIAGNOSIS_ITEM_PATTERN.findall(text)
        if item.strip()
    )
    return items if len(items) >= 2 else ()


def _lx018_primary_diagnosis_text(row: Mapping[str, Any]) -> str:
    """返回 018 可采信的第一诊断文本；不把其他诊断补成第一诊断。"""

    diagnosis_type = _clean(row.get("diagnosis_type"))
    diagnosis_name = _clean(row.get("diagnosis_name") or row.get("diagnosis"))
    diagnosis_code = _clean(row.get("diagnosis_code"))
    label = diagnosis_name or diagnosis_code
    if not label:
        return ""
    if diagnosis_type in _PRIMARY_DIAGNOSIS_TYPES:
        return label
    if diagnosis_type not in _ADMISSION_FIRST_DIAGNOSIS_TYPES:
        return ""
    numbered_items = _split_numbered_diagnosis_items(label)
    if numbered_items:
        return numbered_items[0]
    # cdm.diagnosis 读取已按 diagnosis_id 等稳定字段升序；当初步诊断拆成多行时，
    # 第一行即为入院第一诊断。这里仅返回该行自身，不采信“其他诊断”类型。
    return label


def _lx018_primary_diagnosis_available(documents: Mapping[str, Any]) -> bool:
    for source_key in _LX018_DIAGNOSIS_SOURCES:
        for row in _source_rows(documents, source_key, limit=None):
            if _lx018_primary_diagnosis_text(row):
                return True
    return False


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


def _authoritative_course_time(value: Any) -> datetime | None:
    """007 只接受受控文书时间字段，不使用正文或更新时间。"""

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
                parsed = _authoritative_course_time(authoritative_document_time_value(row))
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
            parsed = _authoritative_course_time(authoritative_document_time_value(row))
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


def _rule_007_customer_display_facts(
    *,
    materials: Luxian0609EvidenceMaterialStore,
    decision: RuleDecision,
) -> Mapping[str, Any] | None:
    """为007输出实际查房间隔或不适用门控事实，不返回病历正文。"""

    if decision.rule_id != "LX0609-007":
        return None
    if (
        decision.applicability is ApplicabilityState.NOT_APPLICABLE
        and decision.reason_code == "eligibility_not_met"
    ):
        return {
            "failure_kind": "unstable_patient_order_present",
            "stable_course_rule_applicable": False,
        }
    if decision.evidence_state is not EvidenceState.SUFFICIENT:
        return None
    source_by_time: dict[datetime, str] = {}
    try:
        for source_key in _RULE_007_RECORD_SOURCES:
            for row in materials.rows(source_key):
                if (
                    record_time := _authoritative_course_time(
                        authoritative_document_time_value(row)
                    )
                ) is not None:
                    source_by_time.setdefault(record_time, source_key)
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return None
    ordered_times = sorted(source_by_time)
    intervals = tuple(
        (current - previous, previous, current)
        for previous, current in zip(ordered_times, ordered_times[1:])
    )
    if not intervals:
        return None
    interval, previous, current = max(intervals, key=lambda item: item[0])
    return {
        "failure_kind": (
            "course_record_interval_over_72h"
            if interval > _RULE_007_MAX_INTERVAL
            else "course_record_interval_within_72h"
        ),
        "interval_start_source": source_by_time[previous],
        "interval_end_source": source_by_time[current],
        "interval_start_time": previous.strftime("%Y-%m-%d %H:%M:%S"),
        "interval_end_time": current.strftime("%Y-%m-%d %H:%M:%S"),
        "interval_hours": round(interval.total_seconds() / 3600, 2),
        "threshold_hours": 72,
        "recorded_dates": [item.date().isoformat() for item in ordered_times],
    }


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


def _rule_009_external_event_date(
    source_key: str,
    row: Mapping[str, Any],
) -> date | None:
    """只取来源各自的临床事件日期，拒绝同步/修改时间。"""

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
        if (parsed := _authoritative_natural_date(row.get(field_name))) is not None:
            return parsed
    return None


def _rule_009_external_event_text(
    source_key: str,
    row: Mapping[str, Any],
) -> str:
    """为009语义分支取最小事件描述，不能投递整行或坐标。"""

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
        "labtest_item_report": ("result", "record_content", "item_name"),
        "inpat_drug_order": ("generic_name", "brand_name", "drug_type"),
        "surgery_record": ("surgery_process", "surgery_name", "record_content"),
        "mr_surgery": ("surgery_name", "surgery_code"),
    }
    for field_name in fields_by_source.get(source_key, ()):
        if (value := _clean(row.get(field_name))):
            return value
    return ""


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
    external_events: list[tuple[date, str, str]] = []
    observation_by_source = {item.source_key: item for item in snapshot.observations}
    for source_key in _RULE_009_EXTERNAL_EVENT_SOURCES:
        observation = observation_by_source.get(source_key)
        if (
            observation is None
            or observation.query_state.value not in {"available", "empty"}
            or observation.completeness.value == "truncated"
        ):
            return "", False, False
        try:
            source_rows = materials.rows(source_key)
        except Exception:
            return "", False, False
        for row in source_rows:
            content = _rule_009_external_event_text(source_key, row)
            if not content:
                continue
            event_date = _rule_009_external_event_date(source_key, row)
            if event_date is None:
                return "", False, False
            if anchor_date <= event_date <= horizon_date:
                external_events.append((event_date, source_key, content))
    external_events.sort(key=lambda item: (item[0], item[1], item[2]))
    if len(external_events) > _MAX_RULE_009_EXTERNAL_EVENT_ROWS:
        return "", True, False
    for event_date, source_key, content in external_events:
        if len(content) > _MAX_ROW_CHARS:
            return "", True, False
        parts.append(
            f"[外部事件/{source_key}] 事件日={event_date.isoformat()}；"
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

Python 已确认：从病危医嘱开立自然日至权威评价终点，每个自然日均存在日常病程或上级医师查房记录。不要重新判断每日频次。
你只判断已提供记录中出现的病情变化，是否有及时、对应的病情记录与处置说明：
- satisfied：记录明确显示病情稳定无变化，或出现的病情变化均有及时对应记录；
- defect：记录明确显示发生病情变化，但对应记录或处置明显不及时；
- unknown：材料不足以可靠判断，禁止猜测。

只能使用以下当前就诊、评价区间内的裁剪病程和最小外部事件：
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
        # v2 将同次就诊、同一快照的外部临床事件纳入 009 语义核对。
        evaluator_version="course-severity-semantic-v2",
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


def _lx018_prompt(*, context: str) -> str:
    """018 的模型只判断医学诊断指向，不接触字数阈值或最终质控状态。"""

    return (
        "你只核对本次入院记录主诉与入院第一诊断之间的医学诊断指向关系。"
        "不要评价主诉字数，不要输出整条质控规则是否合规，也不要引入出院诊断或后续病程诊断。\n"
        "diagnostic_relation_state只能取supported、unsupported、mismatch、unknown："
        "supported表示主诉的部位、症状特征或病程足以支持第一诊断方向；"
        "unsupported表示主诉信息存在但特异性不足；mismatch表示部位、侧别或症状方向冲突；"
        "unknown表示材料本身无法形成可靠医学判断。\n"
        "diagnostic_reason_dimensions只能从anatomic_site、laterality、symptom_pattern、"
        "disease_course、disease_direction中选择实际参与判断的维度。"
        "diagnostic_rationale_code只能取symptom_only、site_symptom_not_specific、"
        "diagnosis_mismatch、insufficient_information、supported。"
        "medical_analysis请用中文具体说明：主诉提供了哪些诊断线索、第一诊断需要哪些关键线索、"
        "两者为何支持、不足或冲突；不得复述姓名、住院号等身份信息，最长600字。\n"
        "严格输出JSON对象："
        '{"diagnostic_relation_state":"supported|unsupported|mismatch|unknown",'
        '"diagnostic_reason_dimensions":[],'
        '"diagnostic_rationale_code":"supported|symptom_only|site_symptom_not_specific|diagnosis_mismatch|insufficient_information",'
        '"medical_analysis":"..."}。\n'
        f"受控材料：\n{context}"
    )


def _response_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        message = choices[0].get("message")
        if isinstance(message, Mapping):
            return str(message.get("content") or "")
    return str(response.get("content") or response.get("text") or "")


def _response_json_payload(response: Mapping[str, Any]) -> Mapping[str, Any] | None:
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
    return payload if isinstance(payload, Mapping) else None


def _parse_is_compliant(response: Mapping[str, Any]) -> bool | None:
    payload = _response_json_payload(response)
    value = payload.get("is_compliant") if payload is not None else None
    return value if isinstance(value, bool) else None


def _parse_lx018_diagnostic_relation(
    response: Mapping[str, Any],
    *,
    is_compliant: bool | None = None,
) -> tuple[str, tuple[str, ...]]:
    payload = _response_json_payload(response)
    raw_state = _clean(payload.get("diagnostic_relation_state")) if payload else ""
    state = (
        raw_state
        if raw_state in _LX018_DIAGNOSTIC_RELATION_STATES
        else "unknown"
    )
    raw_dimensions = payload.get("diagnostic_reason_dimensions") if payload else None
    dimensions = (
        tuple(
            item
            for item in raw_dimensions
            if isinstance(item, str) and item in _LX018_DIAGNOSTIC_REASON_DIMENSIONS
        )
        if isinstance(raw_dimensions, list)
        else ()
    )
    return state, tuple(dict.fromkeys(dimensions))


_LX018_DIAGNOSTIC_RATIONALE_CODES = frozenset(
    {
        "symptom_only",
        "site_symptom_not_specific",
        "diagnosis_mismatch",
        "insufficient_information",
        "supported",
    }
)


def _parse_lx018_diagnostic_rationale_code(
    response: Mapping[str, Any],
    *,
    relation_state: str,
    dimensions: Sequence[str],
) -> str:
    """只接受受控原因码，绝不把模型自由文本带入客户结果。"""

    payload = _response_json_payload(response)
    value = _clean(payload.get("diagnostic_rationale_code")) if payload else ""
    if value in _LX018_DIAGNOSTIC_RATIONALE_CODES:
        # 原因码必须与同一响应中的关系状态、参与维度自洽；例如已识别
        # 部位/症状时不能再向客户说“仅描述症状”。
        if relation_state == "supported":
            return "supported"
        if relation_state == "mismatch":
            return "diagnosis_mismatch"
        if relation_state == "unsupported":
            if value == "symptom_only" and dimensions:
                return "site_symptom_not_specific"
            return value if value != "supported" else "site_symptom_not_specific"
        return "insufficient_information"
    if relation_state == "supported":
        return "supported"
    if relation_state == "mismatch":
        return "diagnosis_mismatch"
    if relation_state == "unsupported":
        return (
            "site_symptom_not_specific"
            if dimensions
            else "symptom_only"
        )
    return "insufficient_information"


def _parse_lx018_medical_analysis(response: Mapping[str, Any]) -> str:
    payload = _response_json_payload(response)
    if not payload:
        return ""
    value = str(payload.get("medical_analysis") or "").strip()
    return value[:2000] if value and "\x00" not in value else ""


def _lx018_semantic_criterion_result(
    *,
    relation_state: str,
    reason_dimensions: Sequence[str],
    rationale_code: str,
    medical_analysis: str,
) -> CriterionResult:
    _, criterion = _lx018_criteria()
    status = {
        "supported": CriterionStatus.PASSED,
        "unsupported": CriterionStatus.FAILED,
        "mismatch": CriterionStatus.FAILED,
        "unknown": CriterionStatus.UNKNOWN,
    }[relation_state]
    reason_code = (
        "requirement_satisfied"
        if status is CriterionStatus.PASSED
        else criterion.failure_reason_code
        if status is CriterionStatus.FAILED
        else "semantic_low_confidence"
    )
    return CriterionResult(
        criterion_id=criterion.criterion_id,
        status=status,
        reason_code=reason_code,
        actual_value=relation_state,
        rationale_code=rationale_code,
        dimensions=tuple(reason_dimensions),
        medical_analysis=medical_analysis,
    )


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


def _lx018_unknown_semantic_result(reason_code: str) -> CriterionResult:
    """为未能完成的诊断指向子判定生成受控未知结果。"""

    return _lx018_semantic_criterion_result(
        relation_state="unknown",
        reason_dimensions=(),
        rationale_code=reason_code,
        medical_analysis="",
    )


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
            )
        )

    safe_metadata: dict[str, Any] = {
        "comparable_document_count": len(comparable),
        "maximum_similarity": 0.0,
        "similarity_threshold": _COPY_SIMILARITY_THRESHOLD,
        "similarity_band": "unknown",
        "best_match_source_types": [],
        "best_match_record_times": [],
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
    pairs = [
        (left, right)
        for left, right in zip(ordered, ordered[1:])
        if left[0].date() < right[0].date()
    ]
    if not pairs:
        return _CopyRuleOutcome(
            status="not_applicable",
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
            "best_match_record_times": [
                best_pair[0][0].strftime("%Y-%m-%d %H:%M:%S"),
                best_pair[1][0].strftime("%Y-%m-%d %H:%M:%S"),
            ] if best_pair else [],
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
        )
    return _CopyRuleOutcome(
        status="non_compliant",
        reason_code="copy_similarity_threshold_exceeded",
        executor_type="program",
        safe_metadata=safe_metadata,
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
    return {
        "failure_kind": (
            "copy_similarity_threshold_exceeded"
            if outcome.status == "non_compliant"
            else "copy_similarity_within_threshold"
        ),
        "copy_similarity": round(float(maximum), 4),
        "copy_similarity_threshold": round(float(threshold), 4),
        "copy_document_sources": list(source_types),
        "copy_document_record_times": list(record_times),
    }


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
            base_decision = _rule_008_009_decision(
                rule_id=rule_id,
                snapshot=evidence_snapshot,
                materials=evidence_materials,
                customer_display_facts=customer_display_facts,
            )
            # 第一阶段只执行已确认的每日病危查房覆盖。病情变化事件尚无受控
            # 定义，不能再通过模型语义扩展或改变 Python 主判定。
            decisions.append(base_decision)
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
