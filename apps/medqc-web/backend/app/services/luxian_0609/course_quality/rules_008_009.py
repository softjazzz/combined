"""LX0609-02-01-04、LX0609-02-01-05 病重病危病程时限与变化事件核对。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import logging
import re
from typing import Any, Callable, Mapping, Protocol, Sequence

from ..llm_prompt_privacy import luxian_0609_llm_call_failure_reason
from ..course_row_material import course_row_has_material
from ..basic_timeliness_facts import parse_authoritative_datetime, parse_authoritative_date
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
_MAX_RULE_009_DISPLAY_EVENTS = 20
_RULE_009_TEMPLATE_VALUES = frozenset(
    {"", "模板", "空模板", "待补充", "暂无内容", "无内容", "未填写", "待完善", "null", "none"}
)
# 明确区分正常、阴性及异常方向；空白和未定义编码不能当成正常。
_RULE_009_LAB_STATES = {
    **dict.fromkeys(("N", "NORMAL", "正常"), "normal"),
    **dict.fromkeys(("NEG", "NEGATIVE", "阴性", "-"), "negative"),
    **dict.fromkeys(("H", "HIGH", "高", "偏高", "升高", "↑"), "high"),
    **dict.fromkeys(("L", "LOW", "低", "偏低", "降低", "↓"), "low"),
    **dict.fromkeys(("PH", "HH", "危急高"), "critical_high"),
    **dict.fromkeys(("PL", "LL", "危急低"), "critical_low"),
    **dict.fromkeys(("POS", "POSITIVE", "阳性", "+", "++", "+++", "++++"), "positive"),
    **dict.fromkeys(("A", "ABNORMAL", "异常"), "abnormal"),
    **dict.fromkeys(("CRITICAL", "危急", "危急值"), "critical"),
}
_RULE_009_LAB_CRITICAL_STATES = frozenset({"critical_high", "critical_low", "critical"})
_LOGGER = logging.getLogger(__name__)


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

    from ...discharge_time import hospital_business_time

    # 带时区的时刻先换算为医院本地时间再取自然日（与 02-01-05 一致）。
    if isinstance(value, datetime):
        return hospital_business_time(value).date() if value.tzinfo is not None else value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        return hospital_business_time(parsed).date() if parsed.tzinfo is not None else parsed.date()
    except ValueError:
        try:
            return date.fromisoformat(normalized)
        except ValueError:
            return None


def _severity_active_date_intervals(
    rows: Sequence[Mapping[str, Any]],
    *,
    horizon_date: date | None,
) -> tuple[tuple[date, date | None], ...] | None:
    """按权威时间顺序配对病重/病危开始与解除事件，保留再次下达区间。"""

    def local_datetime(value: Any) -> datetime | None:
        # 保留既有自然日口径的本地时钟；先按时分秒配对，再投影日期。带时区先换算为医院本地时间。
        from ...discharge_time import hospital_business_time

        if isinstance(value, datetime):
            return hospital_business_time(value) if value.tzinfo is not None else value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
            return hospital_business_time(parsed) if parsed.tzinfo is not None else parsed
        return None

    events: list[tuple[datetime, int, int, str]] = []
    for index, row in enumerate(rows):
        if row.get("status_state") not in {None, "effective"}:
            continue
        event_kind = row.get("event_kind") or "start"
        event_time = local_datetime(
            row.get("planned_start_datetime") or row.get("prescribed_datetime")
        )
        if event_time is None:
            return None
        events.append((event_time, 0 if event_kind == "start" else 1, index, event_kind))
        if event_kind == "start" and row.get("lifecycle_state") == "stopped":
            end_time = local_datetime(row.get("planned_end_datetime"))
            if end_time is None or end_time < event_time:
                return None
            events.append((end_time, 1, index, "end"))
    # 不同医嘱行在同一权威时刻解除和重开时，无法证明先后；不能让
    # start/end 类型排序把重开静默丢弃。复用既有时间资料不足合同。
    # 同一 stopped 行自身的开始/结束则有明确生命周期关系，仍可配对。
    simultaneous: dict[datetime, tuple[set[int], set[int]]] = {}
    for event_time, _kind_order, index, event_kind in events:
        if horizon_date is not None and event_time.date() > horizon_date:
            continue
        starts, ends = simultaneous.setdefault(event_time, (set(), set()))
        (starts if event_kind == "start" else ends).add(index)
        if starts and ends and len(starts | ends) > 1:
            return None

    active_start: date | None = None
    intervals: list[tuple[date, date | None]] = []
    for event_time, _kind_order, _index, event_kind in sorted(events):
        event_date = event_time.date()
        if horizon_date is not None and event_date > horizon_date:
            continue
        if event_kind == "start":
            if active_start is None:
                active_start = event_date
        elif active_start is not None:
            intervals.append((active_start, event_date))
            active_start = None
    if active_start is not None:
        intervals.append((active_start, horizon_date))
    return tuple(intervals)


def _date_in_active_intervals(
    value: date,
    intervals: Sequence[tuple[date, date | None]],
) -> bool:
    return any(
        start <= value and (end is None or value <= end)
        for start, end in intervals
    )


def _critical_date(value: Any) -> date | None:
    """病危频次按医院自然日投影，带时区的同一时刻不得落入不同日期。"""
    clock = parse_authoritative_datetime(value)
    return clock.date() if clock is not None else parse_authoritative_date(value)


def _critical_active_intervals(
    rows: Sequence[Mapping[str, Any]], *, horizon_date: date | None,
    horizon_time: datetime | None,
) -> tuple[tuple[datetime, datetime | None, bool], ...] | None:
    """逐医嘱维护生命周期后求并集；一条医嘱停止不关闭另一条有效医嘱。"""
    events: list[tuple[datetime, int, int, str]] = []
    for index, row in enumerate(rows):
        if row.get("status_state") not in {None, "effective"}:
            continue
        kind = row.get("event_kind") or "start"
        clock = parse_authoritative_datetime(
            row.get("planned_start_datetime") or row.get("prescribed_datetime")
        )
        if clock is None:
            return None
        if (horizon_time is not None and clock > horizon_time) or (
            horizon_time is None and horizon_date is not None and clock.date() > horizon_date
        ):
            continue
        events.append((clock, 0 if kind == "start" else 1, index, kind))
        if kind == "start" and row.get("lifecycle_state") == "stopped":
            end = parse_authoritative_datetime(row.get("planned_end_datetime"))
            if end is None or end < clock:
                return None
            events.append((end, 1, index, "own_end"))
    simultaneous: dict[datetime, tuple[set[int], set[int]]] = {}
    active: set[int] = set()
    start: datetime | None = None
    intervals: list[tuple[datetime, datetime | None, bool]] = []
    for clock, _priority, index, kind in sorted(events):
        if (horizon_time is not None and clock > horizon_time) or (
            horizon_time is None and horizon_date is not None and clock.date() > horizon_date
        ):
            continue
        starts, ends = simultaneous.setdefault(clock, (set(), set()))
        (starts if kind == "start" else ends).add(index)
        if starts and ends and len(starts | ends) > 1:
            # 不同医嘱同刻停止/重开，不能编造先后关系；保留已有资料不足合同。
            return None
        if kind == "start":
            if not active:
                start = clock
            active.add(index)
        elif kind == "own_end":
            active.discard(index)
        else:
            # 明确解除病危是等级事件，结束此前尚有效的同等级医嘱。
            active.clear()
        if not active and start is not None:
            intervals.append((start, clock, True))
            start = None
    if start is not None:
        intervals.append((start, horizon_time, horizon_time is not None))
    return tuple(intervals)


def _critical_interval_dates(intervals, horizon_date):
    return tuple((start.date(), end.date() if end else horizon_date)
                 for start, end, _closed in intervals)


def _material_document_refs_by_row(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    source_key: str,
) -> dict[int, str]:
    """返回同一材料仓内逐行、已绑定的文书引用。

    008/009 的 ``fact_refs`` 不能再以整个来源 observation 代替实际参与
    判定的医嘱、病程或检查检验行。``document_rows`` 与 ``rows`` 共用行实例，
    因而这里不需要第二套文书 ID 或摘要算法。
    """

    return {
        id(row): document_ref
        for document_ref, row in materials.document_rows(
            source_key,
            snapshot=snapshot,
        )
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
        rule_id not in {"LX0609-02-01-04", "LX0609-02-01-05"}
        or type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed severity evidence session mismatch")
    evaluator_version = "critical-lifecycle-natural-day-v3" if rule_id == "LX0609-02-01-05" else "course-severity-natural-day-v2"
    natural_date = _critical_date if rule_id == "LX0609-02-01-05" else _authoritative_natural_date
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
    refs: set[str] = set()

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
        order_document_refs = _material_document_refs_by_row(
            snapshot=snapshot,
            materials=materials,
            source_key=CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY,
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
    target = "serious" if rule_id == "LX0609-02-01-04" else "critical"
    target_rows = tuple(row for row in order_rows if row.get("severity") == target)
    if any(row.get("event_kind") not in {None, "start", "end"} for row in target_rows):
        return decision(
            applicability=ApplicabilityState.ERROR,
            evidence_state=EvidenceState.TECHNICAL_ERROR,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="snapshot_mismatch",
            refs=refs,
            confidence=None,
        )
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
        and row.get("event_kind") in {None, "start"}
    )
    if not relevant_orders:
        # 空的完整医嘱来源没有可投影文书；保留该来源 observation 作为“无
        # 触发事件”的受控否定事实，满足 Binding 的不适用证据合同。
        refs.add(order_observation.snapshot_ref.removeprefix("sha256:"))
        return decision(
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="trigger_absent_complete",
            refs=refs,
            confidence=1.0,
        )

    # 病重/病危期间由同一等级的开始、解除医嘱共同界定；不能只保留第一条
    # start，也不能把无关等级或已排除医嘱投影给客户。
    refs.update(
        order_document_refs[id(row)]
        for row in target_rows
        if row.get("status_state") in {None, "effective"}
        and id(row) in order_document_refs
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
        natural_date(
            row.get("planned_start_datetime") or row.get("prescribed_datetime")
        )
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
    horizon_time: datetime | None = None
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
        horizon_date = natural_date(horizon_rows[0].get("horizon_date"))
        if rule_id == "LX0609-02-01-05":
            horizon_time = parse_authoritative_datetime(horizon_rows[0].get("horizon_datetime"))
        if horizon_date is None or horizon_date < anchor_date:
            if rule_id == "LX0609-02-01-05" and horizon_date is not None:
                return decision(
                    applicability=ApplicabilityState.NOT_APPLICABLE,
                    evidence_state=EvidenceState.SUFFICIENT, qc_direction=QcDirection.UNKNOWN,
                    reason_code="evaluation_window_not_mature", refs=refs, confidence=1.0,
                )
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

    critical_intervals = ()
    if rule_id == "LX0609-02-01-05":
        critical_intervals = _critical_active_intervals(
            target_rows, horizon_date=horizon_date, horizon_time=horizon_time,
        )
        active_intervals = (None if critical_intervals is None else
                            _critical_interval_dates(critical_intervals, horizon_date))
    else:
        active_intervals = _severity_active_date_intervals(target_rows, horizon_date=horizon_date)
    if active_intervals is None:
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
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

    timed_record_points: list[tuple[date, str]] = []
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
            course_document_refs = _material_document_refs_by_row(
                snapshot=snapshot,
                materials=materials,
                source_key=source_key,
            )
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
            document_ref = course_document_refs.get(id(row))
            parsed_date = natural_date(
                authoritative_document_time_value(row)
            )
            if parsed_date is None:
                # 无正文、签名、标题或JSON的无时间行不构成待定病程。
                if not course_row_has_material(row):
                    continue
                if document_ref:
                    refs.add(document_ref)
                return decision(
                    applicability=ApplicabilityState.APPLICABLE,
                    evidence_state=EvidenceState.DATA_GAP,
                    qc_direction=QcDirection.UNKNOWN,
                    reason_code="authoritative_time_missing",
                    refs=refs,
                    confidence=None,
                )
            if rule_id == "LX0609-02-01-05":
                clock = parse_authoritative_datetime(authoritative_document_time_value(row))
                if clock is None and course_row_has_material(row):
                    if document_ref:
                        refs.add(document_ref)
                    return decision(
                        applicability=ApplicabilityState.APPLICABLE,
                        evidence_state=EvidenceState.DATA_GAP, qc_direction=QcDirection.UNKNOWN,
                        reason_code="authoritative_time_missing", refs=refs, confidence=None,
                    )
                # 每日频次沿用自然日覆盖；精确终点之后的记录不能倒填已结束窗口。
                if clock is not None and horizon_time is not None and clock > horizon_time:
                    continue
            # 008与009都必须有实际正文，时间戳/模板壳不能证明已写病程。
            if _date_in_active_intervals(parsed_date, active_intervals) and (
                bool(_rule_009_substantive_text(row))
            ):
                if document_ref:
                    timed_record_points.append((parsed_date, document_ref))

    timed_record_dates = {item[0] for item in timed_record_points}
    refs.update(document_ref for _record_date, document_ref in timed_record_points)
    ordered_dates = sorted(timed_record_dates)
    if rule_id == "LX0609-02-01-04":
        interval_candidates = []
        interval_gap_days: list[int] = []
        for start_date, end_date in active_intervals:
            dated_records = [
                item for item in ordered_dates
                if start_date <= item and (end_date is None or item <= end_date)
            ]
            interval_end = end_date or (dated_records[-1] if dated_records else start_date)
            dates_with_anchor = [start_date, *dated_records, interval_end]
            interval_gap_days.extend(
                (current - previous).days
                for previous, current in zip(
                    dates_with_anchor,
                    dates_with_anchor[1:],
                )
            )
            interval_candidates.extend(
                (previous, current)
                for previous, current in zip(
                    dates_with_anchor,
                    dates_with_anchor[1:],
                )
                if (current - previous).days > _RULE_008_MAX_GAP_DAYS
            )
        exceeded_interval = next(iter(interval_candidates), None)
        interval_exceeded = exceeded_interval is not None
        if interval_exceeded and not materials.permits_absence("daily_course_record"):
            return decision(applicability=ApplicabilityState.APPLICABLE,
                            evidence_state=EvidenceState.DATA_GAP, qc_direction=QcDirection.UNKNOWN,
                            reason_code="source_unavailable", refs=refs, confidence=None)
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
                    "maximum_gap_days": max(interval_gap_days, default=0),
                }
            ),
        )

    expected_dates: set[date] = set()
    pending_dates: set[date] = set()
    for start, end, closed in critical_intervals:
        last_date = end.date() if end else horizon_date
        if last_date is None:
            last_date = max((item for item in ordered_dates if item >= start.date()), default=start.date())
        dates = {start.date() + timedelta(days=offset)
                 for offset in range((last_date - start.date()).days + 1)}
        if not closed and horizon_date is not None and horizon_date in dates:
            # 运行任务仅冻结日期；当天尚未结束，不能提前判为缺失。
            pending_dates.add(horizon_date)
            dates.discard(horizon_date)
        expected_dates.update(dates)
    pending_dates.difference_update(expected_dates)
    expected_dates.update(pending_dates.intersection(timed_record_dates))
    missing_dates = tuple(sorted(expected_dates.difference(timed_record_dates)))
    if missing_dates and not materials.permits_absence("daily_course_record"):
        return decision(applicability=ApplicabilityState.APPLICABLE,
                        evidence_state=EvidenceState.DATA_GAP, qc_direction=QcDirection.UNKNOWN,
                        reason_code="source_unavailable", refs=refs, confidence=None)
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
                "horizon_date": max(expected_dates).isoformat(),
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
    if pending_dates.difference(timed_record_dates) or not expected_dates:
        return decision(
            applicability=ApplicabilityState.NOT_APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT, qc_direction=QcDirection.UNKNOWN,
            reason_code="evaluation_window_not_mature", refs=refs, confidence=1.0,
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
        if (parsed := parse_authoritative_datetime(row.get(field_name))) is not None:
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
        ):
            if (value := _clean(row.get(field_name))):
                parts.append(f"{label}={value}")
        if (flag := _rule_009_lab_flag(row)):
            parts.append(f"异常标志={flag}")
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


def _rule_009_lab_flag(row: Mapping[str, Any]) -> str:
    """兼容规则输入名和生产快照字段名，不推断数值编码含义。"""

    return _clean(row.get("abnormal_flag")) or _clean(row.get("abnormal_indicator"))


def _rule_009_filter_lab_candidates(
    *,
    grouped_external_events: Mapping[tuple[str, str], Mapping[str, Any]],
    lab_history_groups: Mapping[tuple[str, str], Mapping[str, Any]],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    """纯函数：检验只保留标为危急的项目，检查不筛。

    用户口径（2026-10-22）：普通检验异常（含新出现、由正常转异常）不算病情变化；
    检验只有危急值才作为候选。无明细或异常标志缺失的检验无法证明危急，不进候选
    （危急值另由危急值记录规则核对）。不改写输入，也不使用结果数值或正文判断异常。
    """

    del lab_history_groups  # 不再与既往结果比较
    selected: dict[tuple[str, str], Mapping[str, Any]] = {}
    for identity, group in grouped_external_events.items():
        if identity[0] != "lab":
            selected[identity] = group
            continue
        texts: list[str] = []
        for row in group["items"]:
            if _RULE_009_LAB_STATES.get(_rule_009_lab_flag(row).upper()) in _RULE_009_LAB_CRITICAL_STATES:
                content = _rule_009_external_event_text("labtest_item_report", row)
                if content and content not in texts:
                    texts.append(content)
        if texts:
            # 有明细时不附主记录正文，避免被排除的项目从主记录重新进入提示词。
            selected[identity] = {**group, "texts": texts}
    return selected


def _rule_009_group_event_document_refs(
    *,
    event_kind: str,
    event_time: datetime | None,
    rows_by_source: Mapping[str, Sequence[tuple[datetime, str]]],
) -> tuple[str, ...]:
    """选择实际提供事件权威时间的检查/检验文书，而不是整个来源集合。"""

    if event_time is None:
        return ()
    source_priority = (
        ("labtest_master", "labtest_item_report")
        if event_kind == "lab"
        else ("exam_item_report",)
    )
    for source_key in source_priority:
        candidates = tuple(
            document_ref
            for candidate_time, document_ref in rows_by_source.get(source_key, ())
            if candidate_time == event_time
        )
        if len(candidates) == 1:
            return candidates
        if candidates:
            return ()
    return ()


def _rule_009_baseline_course_ref(
    *,
    event_time: datetime,
    course_rows: Sequence[tuple[Any, ...]],
) -> str:
    """返回事件前最近基线；对应病程的24小时时限由Python最终校验。"""

    timed_rows = tuple(
        (item[0], item[1])
        for item in course_rows
        if item[0] is not None
    )
    prior = tuple(item for item in timed_rows if item[0] < event_time)
    return max(prior, default=(datetime.min, ""), key=lambda item: item[0])[1]


def _rule_009_semantic_context(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    allow_large_context: bool = False,
) -> tuple[
    str,
    bool,
    bool,
    Mapping[str, datetime | None],
    Mapping[str, datetime | None],
    Mapping[str, tuple[str, ...]],
    Mapping[str, str],
    datetime | date,
]:
    """返回完整语义投影及截断标记；不允许静默裁剪后交给模型。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        return "", False, False, {}, {}, {}, {}, date.min
    try:
        critical_rows = tuple(
            row
            for row in materials.rows(CURRENT_VISIT_SEVERITY_ORDER_SOURCE_KEY)
            if row.get("severity") == "critical"
        )
        critical_dates = tuple(
            _critical_date(
                row.get("planned_start_datetime") or row.get("prescribed_datetime")
            )
            for row in critical_rows
            if row.get("event_kind") in {None, "start"}
        )
        horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
    except Exception:
        return "", False, False, {}, {}, {}, {}, date.min
    if (
        not critical_dates
        or any(item is None for item in critical_dates)
        or len(horizon_rows) != 1
    ):
        return "", False, False, {}, {}, {}, {}, date.min
    anchor_date = min(item for item in critical_dates if item is not None)
    horizon_date = _critical_date(horizon_rows[0].get("horizon_date"))
    if horizon_date is None or horizon_date < anchor_date:
        return "", False, False, {}, {}, {}, {}, date.min
    horizon_datetime = parse_authoritative_datetime(horizon_rows[0].get("horizon_datetime"))
    critical_intervals = _critical_active_intervals(
        critical_rows, horizon_date=horizon_date, horizon_time=horizon_datetime,
    )
    if critical_intervals is None:
        return "", False, False, {}, {}, {}, {}, date.min
    active_intervals = _critical_interval_dates(critical_intervals, horizon_date)
    evaluation_horizon: datetime | date = horizon_datetime or horizon_date

    observation_by_source = {item.source_key: item for item in snapshot.observations}
    grouped_external_events: dict[tuple[str, str], dict[str, Any]] = {}
    lab_history_groups: dict[tuple[str, str], dict[str, Any]] = {}
    for source_key in _RULE_009_EXTERNAL_EVENT_SOURCES:
        observation = observation_by_source.get(source_key)
        if (
            observation is None
            or observation.query_state.value not in {"available", "empty"}
            or observation.completeness.value == "truncated"
        ):
            return "", False, False, {}, {}, {}, {}, evaluation_horizon
        try:
            source_rows = materials.rows(source_key)
            source_document_refs = _material_document_refs_by_row(
                snapshot=snapshot,
                materials=materials,
                source_key=source_key,
            )
        except Exception:
            return "", False, False, {}, {}, {}, {}, evaluation_horizon
        for index, row in enumerate(source_rows):
            event_kind, event_ref = _rule_009_external_event_identity(source_key, index, row)
            event_time = _rule_009_external_event_time(source_key, row)
            if event_time is not None and horizon_datetime is not None and event_time > horizon_datetime:
                continue
            if source_key in {"labtest_master", "labtest_item_report"}:
                history_group = lab_history_groups.setdefault(
                    (event_kind, event_ref), {"items": [], "times_by_source": {}},
                )
                if source_key == "labtest_item_report":
                    history_group["items"].append(row)
                if event_time is not None:
                    history_group["times_by_source"].setdefault(source_key, []).append(event_time)
            content = _rule_009_external_event_text(source_key, row)
            if not content:
                continue
            # 不能因为一条尚未被模型识别为病情变化的外部行缺时间，就把整条
            # 规则降级。只有模型明确引用的事件才进入后续权威时间校验。
            if event_time is not None and not _date_in_active_intervals(
                event_time.date(), active_intervals
            ):
                continue
            group = grouped_external_events.setdefault(
                (event_kind, event_ref),
                {"texts": [], "times_by_source": {}, "rows_by_source": {}, "items": []},
            )
            if source_key == "labtest_item_report":
                group["items"].append(row)
            if content not in group["texts"]:
                group["texts"].append(content)
            if event_time is not None:
                group["times_by_source"].setdefault(source_key, []).append(event_time)
                if (document_ref := source_document_refs.get(id(row))):
                    group["rows_by_source"].setdefault(source_key, []).append(
                        (event_time, document_ref)
                    )

    filtered_external_events = _rule_009_filter_lab_candidates(
        grouped_external_events=grouped_external_events, lab_history_groups=lab_history_groups,
    )
    candidate_diagnostics = {
        "candidates_before": len(grouped_external_events),
        "candidates_after": len(filtered_external_events),
    }
    _LOGGER.info(
        "02-01-05 检验候选筛选：筛前=%d，筛后=%d",
        candidate_diagnostics["candidates_before"], candidate_diagnostics["candidates_after"],
        extra={"rule_id": "LX0609-02-01-05", **candidate_diagnostics},
    )
    external_events: list[tuple[datetime | None, str, str, tuple[str, ...]]] = []
    for (event_kind, event_ref), group in filtered_external_events.items():
        event_time = _rule_009_group_event_time(
            event_kind=event_kind,
            times_by_source=group["times_by_source"],
        )
        external_events.append(
            (
                event_time,
                event_ref,
                "；".join(group["texts"]),
                _rule_009_group_event_document_refs(
                    event_kind=event_kind,
                    event_time=event_time,
                    rows_by_source=group["rows_by_source"],
                ),
            )
        )
    external_events.sort(
        key=lambda item: (item[0] is None, item[0] or datetime.max, item[1])
    )

    parts: list[str] = []
    course_times: dict[str, datetime | None] = {}
    course_document_refs: dict[str, str] = {}
    # 保留全部可投递事件引用。时间是否权威只能在模型明确引用该事件后
    # 校验，不能因无关外部行缺时间而提前降级整条规则。
    event_times: dict[str, datetime | None] = {}
    substantive_dates: set[date] = set()
    raw_course_rows: list[tuple[datetime | None, str, str, str]] = []
    for source_key in _RULE_007_RECORD_SOURCES:
        try:
            rows = materials.rows(source_key)
            source_document_refs = _material_document_refs_by_row(
                snapshot=snapshot,
                materials=materials,
                source_key=source_key,
            )
        except Exception:
            return "", False, False, {}, {}, {}, {}, evaluation_horizon
        for index, row in enumerate(rows):
            record_time = parse_authoritative_datetime(authoritative_document_time_value(row))
            if record_time is not None and horizon_datetime is not None and record_time > horizon_datetime:
                continue
            record_date = record_time.date() if record_time is not None else None
            content = _rule_009_substantive_text(row)
            if not content or (
                record_date is not None
                and not _date_in_active_intervals(record_date, active_intervals)
            ):
                continue
            internal_ref = _rule_009_row_ref(source_key, index, row)
            if record_date is not None:
                substantive_dates.add(record_date)
            raw_course_rows.append(
                (
                    record_time,
                    internal_ref,
                    content,
                    source_document_refs.get(id(row), ""),
                )
            )
    raw_course_rows.sort(
        key=lambda item: (item[0] is None, item[0] or datetime.max, item[1])
    )
    # 模型只看到本次请求内的临时引用。真实文书/检验标识仅用于上述稳定排序，
    # 不进入提示词，也不允许模型把内部标识带回客户事实。
    course_rows = [
        (record_time, f"C{index:02d}", content, document_ref)
        for index, (record_time, _internal_ref, content, document_ref) in enumerate(
            raw_course_rows,
            start=1,
        )
    ]
    for record_time, ref, _content, document_ref in course_rows:
        course_times[ref] = record_time
        if document_ref:
            course_document_refs[ref] = document_ref
    for record_time, ref, content, _document_ref in course_rows:
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
    event_document_refs: dict[str, tuple[str, ...]] = {}
    for index, (event_time, _internal_ref, content, document_refs) in enumerate(
        external_events,
        start=1,
    ):
        ref = f"E{index:02d}"
        event_times[ref] = event_time
        event_document_refs[ref] = document_refs
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
        start_date + timedelta(days=offset)
        for start_date, end_date in active_intervals
        for interval_end in (end_date or horizon_date,)
        for offset in range((interval_end - start_date).days + 1)
    }
    if expected_dates.difference(substantive_dates):
        return "", False, False, {}, {}, {}, {}, evaluation_horizon
    context = "\n".join(parts)
    return (
        ("", True, False, {}, {}, {}, {}, evaluation_horizon)
        if len(context) > _MAX_RULE_009_CONTEXT_CHARS and not allow_large_context
        else (
            context,
            False,
            True,
            event_times,
            course_times,
            event_document_refs,
            course_document_refs,
            evaluation_horizon,
        )
    )


def _rule_009_context_batches(
    *,
    context: str,
    event_times: Mapping[str, datetime | None],
    course_times: Mapping[str, datetime | None],
) -> tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]:
    """只在整体超限时按事件窗口分批，保留基线和后续24小时完整病程。

    单条正文或单个完整窗口仍超限时失败关闭；未知时间不能参与窗口裁剪。
    外部事件恰好投递一次，文书引用仍使用同一快照内的全局引用。
    """
    if len(context) <= _MAX_RULE_009_CONTEXT_CHARS:
        return ((context, tuple(event_times), tuple(course_times)),)
    blocks = re.split(r"(?m)(?=^\[(?:course|external)_event_ref=)", context)
    courses: dict[str, str] = {}
    events: dict[str, str] = {}
    for block in blocks:
        match = re.match(r"\[(course|external)_event_ref=([^\]]+)\]", block)
        if match:
            (courses if match[1] == "course" else events)[match[2]] = block.rstrip("\n")
    if (
        set(courses) != set(course_times)
        or set(events) != set(event_times)
        or len([block for block in blocks if block]) != len(courses) + len(events)
    ):
        return ()
    # 单条材料不能被截短，也不能因没有外部事件而绕过既有容量合同。
    if not events or any(len(block) > _MAX_RULE_009_CONTEXT_CHARS for block in (*courses.values(), *events.values())):
        return ()

    def course_refs_for(ref: str) -> set[str]:
        event_time = event_times[ref]
        if event_time is None or any(value is None for value in course_times.values()):
            return set(courses)
        selected = {
            key for key, value in course_times.items()
            if event_time <= value <= event_time + _RULE_009_CHANGE_WINDOW
        }
        # 保留事件及所选病程各自的最近基线；不依靠模型猜测窗口外内容。
        for block in (events[ref], *(courses[key] for key in tuple(selected))):
            baseline = re.search(r"baseline_course_ref=(C\d+)", block)
            if baseline and baseline[1] in courses:
                selected.add(baseline[1])
        return selected

    batches: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    batch_events: list[str] = []
    batch_courses: set[str] = set()

    def render(refs: Sequence[str], selected_courses: set[str]) -> str:
        return "\n".join([
            *(block for ref, block in courses.items() if ref in selected_courses),
            *(events[ref] for ref in refs),
        ])

    for ref in event_times:
        selected_courses = course_refs_for(ref)
        proposed = render([*batch_events, ref], batch_courses | selected_courses)
        if len(proposed) > _MAX_RULE_009_CONTEXT_CHARS and batch_events:
            batches.append((render(batch_events, batch_courses), tuple(batch_events),
                            tuple(key for key in courses if key in batch_courses)))
            batch_events, batch_courses = [], set()
        batch_events.append(ref)
        batch_courses.update(selected_courses)
        if len(render(batch_events, batch_courses)) > _MAX_RULE_009_CONTEXT_CHARS:
            return ()
    if batch_events:
        batches.append((render(batch_events, batch_courses), tuple(batch_events),
                        tuple(key for key in courses if key in batch_courses)))
    return tuple(batches)


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
    event_course_refs: Mapping[str, Sequence[str]],
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
    allowed_by_event = json.dumps(
        {ref: list(event_course_refs[ref]) for ref in event_refs},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    external_ref_constraint = (
        "本次没有E开头的外部事件引用，禁止创建或返回任何E引用。"
        if not any(ref.startswith("E") for ref in event_refs)
        else "E开头引用只能从允许event_ref列表中原样选择。"
    )
    return f"""你是 LX0609-02-01-05 病危病程语义核对器。

Python 已确认病危期间每日病程覆盖。不要判定整条规则状态、不要重判每日频次。
只判断每个受控外部检查/检验候选是否显示“相对既往基线发生明确改变”。“病情稳定”“继续观察”、可能/考虑/待排等不构成明确变化。
只能引用材料中给出的 event_ref 和 course_ref，不得编造引用；事件发生时间由 Python 根据受控 event_ref 唯一确定。
病程记录用于既往基线比较及变化后的对应记录候选，不是待分类事件；病程内已经记录的变化视为已由该病程同期记录，无需模型重复抽取为事件。

只能使用以下当前就诊、评价区间内的外部检查/检验候选与病程记录。event_ref 只能引用 external_event_ref，change_category 只能返回 exam_lab。
对应病程只能引用下列 course_event_ref；Python 会按权威时间严格校验它是否位于事件发生后 24 小时内：
{context}

本次允许event_ref={allowed_event_refs}。
本批可见病程引用={allowed_course_refs}，其中事件前病程仅供基线比较。
本次逐事件允许corresponding_course_ref={allowed_by_event}。
每个事件只能从自己的允许列表中选择对应病程，或返回空字符串；不得借用其他事件的列表。
各列表仅包含本批权威时间不早于该事件的病程及时间待核验的病程；时间待核验仍由Python沿用既有规则校验。
{external_ref_constraint}
不得创建、改写或猜测列表以外的引用。
必须对允许event_ref列表中的每个候选恰好返回一次，顺序与允许列表一致；明确变化返回is_explicit_change=true，非明确变化也必须返回is_explicit_change=false且corresponding_course_ref为空。不得遗漏候选。
若同一事件涉及多个类别，只选择最主要的一个类别，禁止重复event_ref。
明确变化事件无数量截断，必须全部返回，由Python合并全部批次后判定，禁止静默省略。
只输出 JSON：{{"events":[{{"event_ref":"...","change_category":"subjective|objective|exam_lab|complication|special_state","is_explicit_change":true或false,"corresponding_course_ref":"...或空字符串"}}]}}。"""


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
        parsed.append({
            "event_ref": event_ref,
            "change_category": category,
            "is_explicit_change": is_explicit_change,
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

    if base_decision.rule_id != "LX0609-02-01-05":
        raise ValueError("009 semantic decision requires LX0609-02-01-05")
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
    elif semantic_state == "window_not_mature":
        # 触发事件与评价终点均已确认，只是事件后的24小时观察窗尚未结束。
        # 这不是资料缺失，不能落入 data_gap。
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "evaluation_window_not_mature",
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
        evaluator_version="course-severity-semantic-v4",
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
    pending_window: dict[str, Any] | None = None
    unresolved: list[dict[str, Any]] = []
    for event in events:
        event_ref = str(event["event_ref"])
        event_time = event_times.get(event_ref)
        course_ref = str(event.get("corresponding_course_ref") or "")
        if event_time is None:
            unresolved.append({"event_ref": event_ref, "reason_code": "authoritative_time_missing"})
            continue
        deadline = event_time + _RULE_009_CHANGE_WINDOW
        if course_ref and course_ref not in course_times:
            unresolved.append({"event_ref": event_ref, "corresponding_course_ref": course_ref,
                               "reason_code": "association_failed"})
            continue
        course_time = course_times.get(course_ref) if course_ref else None
        if course_ref and course_time is None:
            unresolved.append({"event_ref": event_ref, "corresponding_course_ref": course_ref,
                               "reason_code": "authoritative_time_missing"})
            continue
        timely = course_time is not None and event_time <= course_time <= deadline
        if not timely:
            if isinstance(evaluation_horizon, datetime):
                window_mature = evaluation_horizon >= deadline
            else:
                window_mature = evaluation_horizon > deadline.date()
            if not window_mature:
                # 主控代定口径（2026-10-18，用户授权，待客户复核）：
                # 未成熟事件不能掩盖已成熟事件缺陷，完成成熟事件汇总后再返回。
                if pending_window is None:
                    pending_window = {
                        "failure_kind": "critical_change_window_not_mature",
                        "event_ref": event_ref,
                        "event_time": event_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "deadline_time": deadline.strftime("%Y-%m-%d %H:%M:%S"),
                        "threshold_hours": 24,
                    }
                continue
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
    # 主控代定口径（2026-10-18，用户授权，待客户复核）：全部明确变化参与判定；
    # 客户合同仍最多展示20条，优先保留不合规事件，不向客户增加字段。
    unmet = [item for item in facts if not item["timely"]]
    if unmet:
        return (
            _rule_009_semantic_decision(base_decision=base_decision, semantic_state="defect"),
            {
                "failure_kind": "critical_change_course_not_timely",
                "change_events": sorted(facts, key=lambda item: item["timely"])[:_MAX_RULE_009_DISPLAY_EVENTS],
                "unmet_events": unmet[:_MAX_RULE_009_DISPLAY_EVENTS],
                **({"unresolved_events": sorted(unresolved, key=lambda item: item["event_ref"])[:_MAX_RULE_009_DISPLAY_EVENTS]} if unresolved else {}),
                "threshold_hours": 24,
            },
        )
    if unresolved:
        unresolved.sort(key=lambda item: item["event_ref"])
        association = next((item for item in unresolved if item["reason_code"] == "association_failed"), None)
        reason = "association_failed" if association else "authoritative_time_missing"
        return (
            _rule_009_semantic_decision(base_decision=base_decision, data_gap_reason=reason),
            {
                "failure_kind": "critical_change_course_association_failed" if association else "critical_change_time_unavailable",
                **({"event_ref": association["event_ref"], "corresponding_course_ref": association["corresponding_course_ref"]} if association else {}),
                "unresolved_events": unresolved[:_MAX_RULE_009_DISPLAY_EVENTS],
                "threshold_hours": 24,
            },
        )
    if pending_window is not None:
        return (
            _rule_009_semantic_decision(
                base_decision=base_decision, semantic_state="window_not_mature",
            ),
            pending_window,
        )
    return (
        base_decision,
        {
            "failure_kind": "critical_change_course_timely",
            "change_events": facts[:_MAX_RULE_009_DISPLAY_EVENTS],
            "threshold_hours": 24,
        },
    )


def _rule_009_with_selected_event_document_refs(
    *,
    decision: RuleDecision,
    events: Sequence[Mapping[str, Any]],
    event_document_refs: Mapping[str, Sequence[str]],
    course_document_refs: Mapping[str, str],
) -> RuleDecision:
    """将模型已完成语义核对的事件映射回对应的真实材料文书。

    E/C 是仅用于受控提示词和模型返回校验的临时引用；它们不能继续留给
    聚合器按日期反查。全部候选已在调用前完成判定，此处仅绑定客户展示的
    事件文书，避免把展示之外的全部候选塞入有界的证据合同。病程只保留确实
    作为对应记录的 ``C``；每日覆盖所需病程已由基础确定性判定加入。
    """

    selected = list(decision.fact_refs)
    for event in events:
        event_ref = str(event.get("event_ref") or "")
        selected.extend(event_document_refs.get(event_ref, ()))
        course_ref = str(event.get("corresponding_course_ref") or "")
        if (document_ref := course_document_refs.get(course_ref)):
            selected.append(document_ref)
    return RuleDecision(
        rule_id=decision.rule_id,
        snapshot_hash=decision.snapshot_hash,
        applicability=decision.applicability,
        evidence_state=decision.evidence_state,
        qc_direction=decision.qc_direction,
        reason_code=decision.reason_code,
        fact_refs=tuple(dict.fromkeys(selected)),
        evaluator_version=decision.evaluator_version,
        confidence=decision.confidence,
        criterion_results=decision.criterion_results,
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
        rule_id != "LX0609-02-01-05"
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
        event_document_refs,
        course_document_refs,
        evaluation_horizon,
    ) = _rule_009_semantic_context(
        snapshot=snapshot, materials=materials, allow_large_context=True
    )
    batches = _rule_009_context_batches(
        context=context, event_times=event_times, course_times=course_times
    ) if context_ready else ()
    context_capacity_exceeded = context_capacity_exceeded or (context_ready and not batches)
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

    usage = {
        "llm_call_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "api_time": 0.0,
    }
    all_events: list[Mapping[str, Any]] = []
    for batch_context, batch_event_refs, batch_course_refs in batches:
        # 基线病程仍供语义比较；对应记录候选则逐事件按既有时间校验条件投影。
        event_course_refs = {
            event_ref: tuple(
                course_ref for course_ref in batch_course_refs
                if event_times[event_ref] is None or course_times[course_ref] is None
                or course_times[course_ref] >= event_times[event_ref]
            )
            for event_ref in batch_event_refs
        }
        pending_refs = batch_event_refs
        verified: dict[str, Mapping[str, Any]] = {}
        invalid_events: dict[str, Mapping[str, Any]] = {}
        for attempt in range(2):
            # 每批最多补核一次：解析失败重试本批，非法引用只补核对应事件；
            # 已完整核验的事件和已通过的批次不重问、不覆盖。
            active_context = "\n".join(
                block.rstrip("\n")
                for block in re.split(r"(?m)(?=^\[(?:course|external)_event_ref=)", batch_context)
                if block and (
                    not block.startswith("[external_event_ref=")
                    or any(block.startswith(f"[external_event_ref={ref}]") for ref in pending_refs)
                )
            )
            usage["llm_call_count"] += 1
            try:
                allowed_courses = batch_course_refs
                if attempt and invalid_events:
                    allowed_courses = tuple(
                        ref for ref in batch_course_refs
                        if course_times[ref] is None or any(
                            event_times[event_ref] is None
                            or course_times[ref] >= event_times[event_ref]
                            for event_ref in pending_refs
                        )
                    )
                semantic_prompt = _rule_009_semantic_prompt(
                    context=active_context, event_refs=pending_refs, course_refs=allowed_courses,
                    event_course_refs=event_course_refs,
                )
                if attempt and invalid_events:
                    semantic_prompt += (
                        "\n本次为唯一一次引用补核：上次对应病程不在允许范围或早于事件。"
                        "请按原文时间重新核对，只能选事件发生后的对应病程；没有则返回空引用。"
                        "这些事件已经判为明确变化，is_explicit_change必须保持true；本次只修正对应引用。"
                        "不得为规避引用校验而省略事件或改判非明确变化。"
                    )
                    semantic_prompt += "\n" + "\n".join(
                        f"event_ref={ref}：上次corresponding_course_ref="
                        f"{invalid_events[ref]['corresponding_course_ref']}不在该事件允许列表。"
                        for ref in pending_refs
                    )
                elif attempt:
                    semantic_prompt += (
                        "\n本次为唯一一次JSON解析补核：上次应答无法解析为JSON对象。"
                        "请重新核对本批全部候选，仅按约定结构返回完整JSON对象，不得遗漏候选。"
                    )
                response = await llm_client.generate(semantic_prompt)
            except Exception as error:
                return Rule008009TypedExecution(
                    decision=_rule_009_semantic_decision(
                        base_decision=base_decision,
                        error_reason=luxian_0609_llm_call_failure_reason(
                            error,
                            "model_invalid_output" if attempt else "model_transport_error",
                        ),
                    ),
                    customer_display_facts=tuple(base_display_facts), **usage,
                )
            prompt, completion, total, elapsed = usage_parser(response)
            usage["prompt_tokens"] += prompt
            usage["completion_tokens"] += completion
            usage["total_tokens"] += total
            usage["api_time"] += elapsed
            if not attempt and _response_json_payload(response) is None:
                continue
            batch_events = _parse_rule_009_change_events(response)
            if (
                batch_events is None
                or tuple(str(event["event_ref"]) for event in batch_events) != pending_refs
                or any(
                    event["change_category"] != "exam_lab"
                    or (not event["is_explicit_change"] and event["corresponding_course_ref"])
                    or (str(event["event_ref"]) in invalid_events
                        and event["is_explicit_change"] != invalid_events[str(event["event_ref"])]["is_explicit_change"])
                    for event in batch_events
                )
            ):
                return Rule008009TypedExecution(
                    decision=_rule_009_semantic_decision(
                        base_decision=base_decision, error_reason="model_invalid_output",
                    ),
                    customer_display_facts=tuple(base_display_facts), **usage,
                )
            invalid_refs = []
            for event in batch_events:
                ref = str(event["event_ref"])
                course_ref = str(event["corresponding_course_ref"])
                if course_ref and (
                    course_ref not in batch_course_refs
                    or (course_times[course_ref] is not None and event_times[ref] is not None
                        and course_times[course_ref] < event_times[ref])
                ):
                    invalid_refs.append(ref)
                    invalid_events[ref] = event
                else:
                    verified[ref] = event
            if not invalid_refs:
                break
            if attempt == 1:
                return Rule008009TypedExecution(
                    decision=_rule_009_semantic_decision(
                        base_decision=base_decision, error_reason="model_invalid_output",
                    ),
                    customer_display_facts=tuple(base_display_facts), **usage,
                )
            pending_refs = tuple(invalid_refs)
        all_events.extend(verified[ref] for ref in batch_event_refs)
    events = tuple(all_events)
    returned_event_refs = tuple(str(event["event_ref"]) for event in events)
    if (
        len(set(returned_event_refs)) != len(events)
        or returned_event_refs != tuple(event_times)
        or any(
            str(event.get("change_category") or "") != "exam_lab"
            or (
                not event["is_explicit_change"]
                and str(event.get("corresponding_course_ref") or "")
            )
            for event in events
        )
    ):
        return Rule008009TypedExecution(
            decision=_rule_009_semantic_decision(
                base_decision=base_decision,
                error_reason="model_invalid_output",
            ),
            customer_display_facts=tuple(base_display_facts),
            **usage,
        )
    explicit_events = tuple(event for event in events if event["is_explicit_change"])
    if not explicit_events:
        return Rule008009TypedExecution(
            decision=_rule_009_with_selected_event_document_refs(
                decision=base_decision,
                events=events[:_MAX_RULE_009_DISPLAY_EVENTS],
                event_document_refs=event_document_refs,
                course_document_refs=course_document_refs,
            ),
            customer_display_facts=tuple(base_display_facts),
            **usage,
        )
    if any(
        str(event["event_ref"]) not in event_times
        or (
            (course_ref := str(event.get("corresponding_course_ref") or ""))
            and (
                course_ref not in course_times
                or (
                    course_times[course_ref] is not None
                    and event_times[str(event["event_ref"])] is not None
                    and course_times[course_ref]
                    < event_times[str(event["event_ref"])]
                )
            )
        )
        for event in explicit_events
    ):
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
        events=explicit_events,
        event_times=event_times,
        course_times=course_times,
        evaluation_horizon=evaluation_horizon,
    )
    display_event_refs = {
        str(item["event_ref"]) for item in change_facts.get("change_events", ())
    }
    if change_facts.get("event_ref"):
        display_event_refs.add(str(change_facts["event_ref"]))
    display_events = (
        tuple(event for event in events if event["event_ref"] in display_event_refs)
        if display_event_refs else events[:_MAX_RULE_009_DISPLAY_EVENTS]
    )
    semantic_decision = _rule_009_with_selected_event_document_refs(
        decision=semantic_decision,
        events=display_events,
        event_document_refs=event_document_refs,
        course_document_refs=course_document_refs,
    )
    daily_facts = dict(base_display_facts[0][1]) if base_display_facts else {}
    daily_facts.update(change_facts)
    return Rule008009TypedExecution(
        decision=semantic_decision,
        customer_display_facts=(("LX0609-02-01-05", daily_facts),),
        **usage,
    )
