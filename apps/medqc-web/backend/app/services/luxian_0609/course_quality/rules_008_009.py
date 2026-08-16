"""LX0609-008/009 病重病危病程时限与变化事件核对。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import re
from typing import Any, Callable, Mapping, Protocol, Sequence

from ..decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from ..evidence_material import (
    EvidenceMaterialTruncated,
    Luxian0609EvidenceMaterialStore,
)
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from ..source_evidence_reader import (
    CURRENT_VISIT_DISCHARGE_HORIZON_SOURCE_KEY,
    CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
    EVALUATION_HORIZON_SOURCE_KEY,
    authoritative_document_time_value,
)
from .rule_007 import RULE_007_RECORD_SOURCES as _RULE_007_RECORD_SOURCES
from .shared import (
    authoritative_course_time as _authoritative_course_time,
    clean_text as _clean,
    response_json_payload as _response_json_payload,
    row_text as _row_text,
)


RULE_008_009_TIMELINE_SOURCES = (
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    "exam_attention_report",
    "lab_attention_report",
)
_RULE_009_EXTERNAL_EVENT_SOURCES = (
    "exam_item_report",
    "labtest_master",
    "labtest_item_report",
)
_RULE_008_MAX_GAP_DAYS = 2
_MAX_RULE_009_CONTEXT_CHARS = 32000
_RULE_009_CHANGE_CATEGORIES = frozenset(
    {"subjective", "objective", "exam_lab", "complication", "special_state"}
)
_RULE_009_CHANGE_WINDOW = timedelta(hours=24)
_MAX_RULE_009_CHANGE_EVENTS = 20
_RULE_009_TEMPLATE_VALUES = frozenset(
    {"", "模板", "空模板", "待补充", "暂无内容", "无内容", "未填写", "待完善", "null", "none"}
)


class Rule008009LLMClient(Protocol):
    async def generate(
        self,
        prompt: str,
        *,
        max_completion_tokens: int | None = None,
        allow_length_retry: bool = True,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class Rule008009TypedExecution:
    decision: RuleDecision
    customer_display_facts: tuple[tuple[str, Mapping[str, Any]], ...]
    llm_call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    api_time: float = 0.0


def _rule_009_substantive_text(row: Mapping[str, Any]) -> str:
    """拒绝空正文和固定模板壳，避免把只有时间的壳记录当作每日病程。"""

    content = _row_text(row)
    normalized = re.sub(r"[\W_]+", "", content, flags=re.UNICODE).lower()
    return content if normalized not in _RULE_009_TEMPLATE_VALUES else ""

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
    raw_course_rows: list[tuple[datetime | None, str, str]] = []
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
            internal_ref = _rule_009_row_ref(source_key, index, row)
            if record_date is not None:
                substantive_dates.add(record_date)
            raw_course_rows.append((record_time, internal_ref, content))
    raw_course_rows.sort(
        key=lambda item: (item[0] is None, item[0] or datetime.max, item[1])
    )
    # 模型只看到本次请求内的临时引用。真实文书/检验标识仅用于上述稳定排序，
    # 不进入提示词，也不允许模型把内部标识带回客户事实。
    course_rows = [
        (record_time, f"C{index:02d}", content)
        for index, (record_time, _internal_ref, content) in enumerate(
            raw_course_rows,
            start=1,
        )
    ]
    for record_time, ref, _content in course_rows:
        course_times[ref] = record_time
        event_times[ref] = record_time
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
    for index, (event_time, _internal_ref, content) in enumerate(
        external_events,
        start=1,
    ):
        ref = f"E{index:02d}"
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


def _rule_009_semantic_prompt(
    *,
    context: str,
    event_refs: Sequence[str],
    course_refs: Sequence[str],
) -> str:
    allowed_event_refs = json.dumps(
        list(event_refs),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    allowed_course_refs = json.dumps(
        list(course_refs),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    external_ref_constraint = (
        "本次没有E开头的外部事件引用，禁止创建或返回任何E引用。"
        if not any(ref.startswith("E") for ref in event_refs)
        else "E开头引用只能从允许event_ref列表中原样选择。"
    )
    return f"""你是 LX0609-009 病危病程语义核对器。

Python 已确认病危期间每日病程覆盖。不要判定整条规则状态、不要重判每日频次。
只抽取“相对既往基线发生明确改变”的事件：主观症状(subjective)、客观体征(objective)、检查检验(exam_lab)、并发症/合并症(complication)、特殊状态(special_state)。
"病情稳定”“继续观察”、可能/考虑/待排等不构成明确变化。只能引用材料中给出的 event_ref 和 course_ref，不得编造引用；事件发生时间由 Python 根据受控 event_ref 唯一确定。
若同一病程已经明确记录变化及处置，可把该病程作为对应病程。

只能使用以下当前就诊、评价区间内的病程事件和临床事件。external_event_ref 仅用于检查检验变化；
course_event_ref 可用于主观症状、客观体征、并发症/合并症和特殊状态变化，也可作为对应病程。
对应病程只能引用下列 course_event_ref；Python 会按权威时间严格校验它是否位于事件发生后 24 小时内：
{context}

本次允许event_ref={allowed_event_refs}。
本次允许corresponding_course_ref={allowed_course_refs}，也可以返回空字符串。
{external_ref_constraint}
不得创建、改写或猜测列表以外的引用。
只返回is_explicit_change=true的事件；不要返回false候选。每个event_ref最多返回一次；
若同一事件涉及多个类别，只选择最主要的一个类别，禁止重复event_ref。
若明确变化事件超过{_MAX_RULE_009_CHANGE_EVENTS}个，仍须全部返回，由Python失败关闭，禁止静默省略。
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
        is_explicit_change = item.get("is_explicit_change")
        if (
            category not in _RULE_009_CHANGE_CATEGORIES
            or type(is_explicit_change) is not bool
        ):
            return None
        event_ref = _clean(item.get("event_ref"))
        if not event_ref:
            return None
        if not is_explicit_change:
            continue
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

async def evaluate_rules_008_009_typed(
    *,
    rule_id: str,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    llm_client: Rule008009LLMClient | None,
    usage_parser: Callable[[Mapping[str, Any]], tuple[int, int, int, float]],
) -> Rule008009TypedExecution:
    """执行008/009 typed闭环；调用方只负责累计结果与模型用量。"""

    base_display_facts: list[tuple[str, Mapping[str, Any]]] = []
    base_decision = _rule_008_009_decision(
        rule_id=rule_id,
        snapshot=snapshot,
        materials=materials,
        customer_display_facts=base_display_facts,
    )
    if (
        rule_id != "LX0609-009"
        or base_decision.applicability is not ApplicabilityState.APPLICABLE
        or base_decision.evidence_state is not EvidenceState.SUFFICIENT
        or base_decision.qc_direction is not QcDirection.SATISFIED
    ):
        return Rule008009TypedExecution(
            decision=base_decision,
            customer_display_facts=tuple(base_display_facts),
        )

    terminal_decision = _rule_009_external_source_terminal_decision(
        base_decision=base_decision,
        snapshot=snapshot,
    )
    if terminal_decision is not None:
        return Rule008009TypedExecution(
            decision=terminal_decision,
            customer_display_facts=tuple(base_display_facts),
        )

    (
        context,
        context_capacity_exceeded,
        context_ready,
        event_times,
        course_times,
        evaluation_horizon,
    ) = _rule_009_semantic_context(snapshot=snapshot, materials=materials)
    if context_capacity_exceeded:
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                data_gap_reason="candidate_scope_incomplete",
            ),
            customer_display_facts=(),
        )
    if not context_ready:
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                data_gap_reason="authoritative_time_missing",
            ),
            customer_display_facts=tuple(base_display_facts),
        )
    if not event_times:
        return Rule008009TypedExecution(
            decision=base_decision,
            customer_display_facts=tuple(base_display_facts),
        )
    if llm_client is None:
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                error_reason="model_transport_error",
            ),
            customer_display_facts=tuple(base_display_facts),
        )

    try:
        response = await llm_client.generate(
            _rule_009_semantic_prompt(
                context=context,
                event_refs=tuple(event_times),
                course_refs=tuple(course_times),
            )
        )
    except Exception:
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                error_reason="model_transport_error",
            ),
            customer_display_facts=tuple(base_display_facts),
            llm_call_count=1,
        )

    prompt, completion, total, elapsed = usage_parser(response)
    usage = {
        "llm_call_count": 1,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "api_time": elapsed,
    }
    events = _parse_rule_009_change_events(response)
    if events is None:
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                error_reason="model_invalid_output",
            ),
            customer_display_facts=tuple(base_display_facts),
            **usage,
        )
    if len({str(event["event_ref"]) for event in events}) != len(events):
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                error_reason="model_invalid_output",
            ),
            customer_display_facts=tuple(base_display_facts),
            **usage,
        )
    if len(events) > _MAX_RULE_009_CHANGE_EVENTS:
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                data_gap_reason="candidate_scope_incomplete",
            ),
            customer_display_facts=(),
            **usage,
        )
    if not events:
        return Rule008009TypedExecution(
            decision=base_decision,
            customer_display_facts=tuple(base_display_facts),
            **usage,
        )
    if any(str(event["event_ref"]) not in event_times for event in events):
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                error_reason="model_invalid_output",
            ),
            customer_display_facts=tuple(base_display_facts),
            **usage,
        )

    semantic_decision, change_facts = _rule_009_change_event_decision(
        base_decision=base_decision,
        events=events,
        event_times=event_times,
        course_times=course_times,
        evaluation_horizon=evaluation_horizon,
    )
    daily_facts = dict(base_display_facts[0][1]) if base_display_facts else {}
    daily_facts.update(change_facts)
    return Rule008009TypedExecution(
        decision=semantic_decision,
        customer_display_facts=(("LX0609-009", daily_facts),),
        **usage,
    )
