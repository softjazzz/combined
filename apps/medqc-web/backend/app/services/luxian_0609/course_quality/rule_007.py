"""LX0609-007 稳定患者病程记录间隔判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Mapping

from ..decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from ..evidence_material import (
    EvidenceMaterialTruncated,
    EvidenceMaterialUnavailable,
    Luxian0609EvidenceMaterialStore,
)
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from ..source_evidence_reader import (
    EVALUATION_HORIZON_SOURCE_KEY,
    authoritative_document_time_value,
)
from .shared import authoritative_course_time, row_text


RULE_007_RECORD_SOURCES = ("daily_course_record", "senior_course_record")
_RULE_007_ADMISSION_SOURCE = "inpat_registration"
_MAX_INTERVAL = timedelta(hours=72)


@dataclass(frozen=True)
class Rule007LegacyOutcome:
    status: str
    reason_code: str


def _evaluation_horizon_date(value: Any) -> date | None:
    """只接受 Provider 冻结的 ISO 日期，不能把创建时间伪装成评价终点。"""

    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def evaluate_rule_007_legacy(
    *,
    serious_state: str,
    critical_state: str,
    institute_id: str,
    patient_id: str,
    visit_id: str,
    source_schema: str | None,
    unstable_order_reader: Callable[..., bool],
    source_row_reader: Callable[..., list[dict[str, Any]]],
    source_row_limit: Callable[[str], int],
    evidence_snapshot: Luxian0609EvidenceSnapshot | None = None,
    evidence_materials: Luxian0609EvidenceMaterialStore | None = None,
) -> Rule007LegacyOutcome:
    """保持历史入口的失败语义，但只返回受控判定 outcome。"""

    if serious_state == "present" or critical_state == "present":
        return Rule007LegacyOutcome(
            status="not_applicable",
            reason_code="unstable_patient_fact_present",
        )

    coordinates = (institute_id, patient_id, visit_id)
    if not all(str(value or "").strip() for value in coordinates):
        return Rule007LegacyOutcome(
            status="data_gap",
            reason_code="course_time_source_unavailable",
        )

    try:
        if evidence_snapshot is not None:
            unstable_order_state = _snapshot_unstable_order_state(evidence_snapshot)
            if unstable_order_state == "unavailable":
                raise ValueError("controlled fact unavailable")
            unstable_order_present = unstable_order_state == "present"
        else:
            unstable_order_present = unstable_order_reader(
                institute_id=institute_id,
                patient_id=patient_id,
                visit_id=visit_id,
                source_schema=source_schema,
            )
        if unstable_order_present:
            return Rule007LegacyOutcome(
                status="not_applicable",
                reason_code="unstable_patient_order_present",
            )

        record_times: set[datetime] = set()
        substantive_record_without_time = False
        for source_key in RULE_007_RECORD_SOURCES:
            rows = (
                [dict(row) for row in evidence_materials.rows(source_key)]
                if evidence_materials is not None
                else source_row_reader(
                    source_key=source_key,
                    institute_id=institute_id,
                    patient_id=patient_id,
                    visit_id=visit_id,
                    source_schema=source_schema,
                )
            )
            if len(rows) >= source_row_limit(source_key):
                return Rule007LegacyOutcome(
                    status="data_gap",
                    reason_code="course_time_source_truncated",
                )
            for row in rows:
                parsed = authoritative_course_time(
                    authoritative_document_time_value(row)
                )
                if parsed is not None:
                    record_times.add(parsed)
                elif row_text(row):
                    substantive_record_without_time = True
    except EvidenceMaterialTruncated:
        return Rule007LegacyOutcome(
            status="data_gap",
            reason_code="course_time_source_truncated",
        )
    except Exception:
        return Rule007LegacyOutcome(
            status="data_gap",
            reason_code="course_time_source_unavailable",
        )

    ordered_times = sorted(record_times)
    if len(ordered_times) < 2:
        return Rule007LegacyOutcome(
            status="data_gap",
            reason_code="authoritative_course_time_unavailable",
        )
    interval_over_72h = any(
        current - previous > _MAX_INTERVAL
        for previous, current in zip(ordered_times, ordered_times[1:])
    )
    if interval_over_72h and substantive_record_without_time:
        return Rule007LegacyOutcome(
            status="data_gap",
            reason_code="authoritative_course_time_incomplete",
        )
    if interval_over_72h:
        return Rule007LegacyOutcome(
            status="non_compliant",
            reason_code="course_record_interval_over_72h",
        )
    return Rule007LegacyOutcome(
        status="compliant",
        reason_code="course_record_interval_within_72h",
    )


def _snapshot_unstable_order_state(snapshot: Luxian0609EvidenceSnapshot) -> str:
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


def evaluate_rule_007_typed(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
) -> RuleDecision:
    """用同一快照的入院、病程与评价终点核对完整稳定期区间。"""

    if (
        type(snapshot) is not Luxian0609EvidenceSnapshot
        or type(materials) is not Luxian0609EvidenceMaterialStore
        or materials.snapshot_hash != snapshot.snapshot_hash
    ):
        raise ValueError("typed 007 evidence session mismatch")

    evaluator_version = "rule007-authoritative-time-v2"
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
        _RULE_007_ADMISSION_SOURCE,
        EVALUATION_HORIZON_SOURCE_KEY,
        *RULE_007_RECORD_SOURCES,
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

    for source_key in (_RULE_007_ADMISSION_SOURCE, EVALUATION_HORIZON_SOURCE_KEY):
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
        if observation.query_state.value != "available":
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
        admission_rows = tuple(materials.rows(_RULE_007_ADMISSION_SOURCE))
        horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
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
    if len(admission_rows) != 1 or len(horizon_rows) != 1:
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
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
    admission_time = authoritative_course_time(admission_rows[0].get("admission_datetime"))
    horizon_time = authoritative_course_time(horizon_rows[0].get("horizon_datetime"))
    horizon_date = _evaluation_horizon_date(horizon_rows[0].get("horizon_date"))
    if (
        admission_time is None
        or (horizon_time is None and horizon_date is None)
        or (horizon_time is not None and horizon_time < admission_time)
        or (horizon_time is None and horizon_date is not None and horizon_date < admission_time.date())
    ):
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            refs=refs,
            confidence=None,
        )

    record_times: set[datetime] = set()
    substantive_record_without_time = False
    for source_key in RULE_007_RECORD_SOURCES:
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
            parsed = authoritative_course_time(
                authoritative_document_time_value(row)
            )
            if parsed is not None:
                record_times.add(parsed)
            elif row_text(row):
                substantive_record_without_time = True

    ordered_times = sorted(
        record_time
        for record_time in record_times
        if admission_time <= record_time
        and (
            (
                horizon_time is None
                and horizon_date is not None
                and record_time.date() < horizon_date
            )
            or (horizon_time is not None and record_time <= horizon_time)
        )
    )
    # 评价窗口已超过成熟期但完全没有可定位病程记录时，不能输出无证据的
    # 确定问题；72 小时内仍按边界合规处理。
    if not ordered_times and horizon_time is not None:
        elapsed = (
            horizon_time - admission_time
            if horizon_time is not None
            else datetime.combine(horizon_date, datetime.min.time()) - admission_time
        )
        if elapsed <= _MAX_INTERVAL:
            return decision(
                applicability=ApplicabilityState.APPLICABLE,
                evidence_state=EvidenceState.SUFFICIENT,
                qc_direction=QcDirection.SATISFIED,
                reason_code="requirement_within_threshold",
                refs=refs,
                confidence=1.0,
            )
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            refs=refs,
            confidence=None,
        )
    exact_boundary_times = (admission_time, *ordered_times)
    interval_over_72h = any(
        current - previous > _MAX_INTERVAL
        for previous, current in zip(exact_boundary_times, exact_boundary_times[1:])
    )
    same_day_horizon_candidate = (
        horizon_time is None
        and horizon_date is not None
        and any(
            admission_time <= record_time and record_time.date() == horizon_date
            for record_time in record_times
        )
    )
    tail_start = exact_boundary_times[-1]
    if horizon_time is not None:
        interval_over_72h = interval_over_72h or horizon_time - tail_start > _MAX_INTERVAL
    else:
        assert horizon_date is not None
        deadline_date = (tail_start + _MAX_INTERVAL).date()
        tail_time_ambiguous = horizon_date == deadline_date
        if not same_day_horizon_candidate:
            interval_over_72h = interval_over_72h or horizon_date > deadline_date
    if not ordered_times and horizon_time is None and interval_over_72h:
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_missing",
            refs=refs,
            confidence=None,
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
    if (
        horizon_time is None
        and (tail_time_ambiguous or same_day_horizon_candidate)
        and not interval_over_72h
    ):
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


def rule_007_customer_display_facts(
    *,
    materials: Luxian0609EvidenceMaterialStore,
    decision: RuleDecision,
) -> Mapping[str, Any] | None:
    """输出实际查房间隔或不适用门控事实，不返回病历正文。"""

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
    record_points: list[tuple[datetime, str, str]] = []
    try:
        admission_rows = tuple(materials.rows(_RULE_007_ADMISSION_SOURCE))
        horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
        if len(admission_rows) != 1 or len(horizon_rows) != 1:
            return None
        admission_time = authoritative_course_time(
            admission_rows[0].get("admission_datetime")
        )
        horizon_time = authoritative_course_time(
            horizon_rows[0].get("horizon_datetime")
        )
        horizon_date = _evaluation_horizon_date(horizon_rows[0].get("horizon_date"))
        if (
            admission_time is None
            or (horizon_time is None and horizon_date is None)
            or (horizon_time is not None and horizon_time < admission_time)
            or (
                horizon_time is None
                and horizon_date is not None
                and horizon_date < admission_time.date()
            )
        ):
            return None
        same_day_horizon_candidate = False
        for source_key in RULE_007_RECORD_SOURCES:
            for row in materials.rows(source_key):
                record_time = authoritative_course_time(
                    authoritative_document_time_value(row)
                )
                if record_time is None or record_time < admission_time:
                    continue
                if horizon_time is not None and record_time <= horizon_time:
                    document_id = str(
                        row.get("document_id") or row.get("id") or ""
                    ).strip()
                    record_points.append((record_time, source_key, document_id))
                elif horizon_time is None and horizon_date is not None:
                    if record_time.date() < horizon_date:
                        document_id = str(
                            row.get("document_id") or row.get("id") or ""
                        ).strip()
                        record_points.append((record_time, source_key, document_id))
                    elif record_time.date() == horizon_date:
                        same_day_horizon_candidate = True
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return None
    ordered_records = sorted(
        record_points,
        key=lambda item: (item[0], item[1], item[2]),
    )
    ordered_points = [
        (admission_time, _RULE_007_ADMISSION_SOURCE, ""),
        *ordered_records,
    ]
    if horizon_time is None:
        assert horizon_date is not None
        tail_start = ordered_points[-1]
        tail_deadline = (tail_start[0] + _MAX_INTERVAL).date()
        if horizon_date > tail_deadline and not same_day_horizon_candidate:
            previous_time, previous_source, _previous_document_id = tail_start
            previous_position = (
                ordered_records.index(tail_start) + 1
                if tail_start in ordered_records
                else 0
            )
            return {
                "failure_kind": "course_record_interval_over_72h",
                "interval_start_source": previous_source,
                "interval_end_source": EVALUATION_HORIZON_SOURCE_KEY,
                "interval_start_time": previous_time.strftime("%Y-%m-%d %H:%M:%S"),
                "interval_end_date": horizon_date.isoformat(),
                "interval_end_precision": "date",
                "interval_start_position": previous_position,
                "interval_end_position": len(ordered_records) + 1,
                "record_count": len(ordered_records),
                "threshold_hours": 72,
                "recorded_dates": [item[0].date().isoformat() for item in ordered_records],
            }
        exact_intervals = tuple(
            current[0] - previous[0]
            for previous, current in zip(ordered_points, ordered_points[1:])
        )
        if not any(interval > _MAX_INTERVAL for interval in exact_intervals):
            # 日期终点不足以展示精确的末段间隔；合规时不产生展示事实。
            return None
        # 下方仅展示已确定的内部超时区间。
    else:
        ordered_points.append((horizon_time, EVALUATION_HORIZON_SOURCE_KEY, ""))
    intervals = tuple(
        (current[0] - previous[0], previous, current)
        for previous, current in zip(ordered_points, ordered_points[1:])
    )
    if not intervals:
        return None
    interval, previous, current = max(intervals, key=lambda item: item[0])
    interval_seconds = round(interval.total_seconds())
    threshold_seconds = round(_MAX_INTERVAL.total_seconds())
    previous_position = (
        ordered_records.index(previous) + 1
        if previous in ordered_records
        else 0
    )
    current_position = (
        ordered_records.index(current) + 1
        if current in ordered_records
        else len(ordered_records) + 1
    )
    previous_time, previous_source, previous_document_id = previous
    current_time, current_source, current_document_id = current
    facts: dict[str, Any] = {
        "failure_kind": (
            "course_record_interval_over_72h"
            if interval > _MAX_INTERVAL
            else "course_record_interval_within_72h"
        ),
        "interval_start_source": previous_source,
        "interval_end_source": current_source,
        "interval_start_time": previous_time.strftime("%Y-%m-%d %H:%M:%S"),
        "interval_end_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
        "interval_start_position": previous_position,
        "interval_end_position": current_position,
        "record_count": len(ordered_records),
        "interval_seconds": interval_seconds,
        "overdue_seconds": max(0, interval_seconds - threshold_seconds),
        "interval_hours": round(interval_seconds / 3600, 2),
        "threshold_hours": 72,
        "recorded_dates": [item[0].date().isoformat() for item in ordered_records],
    }
    # 文书 ID 仅供 Aggregator 生成不可逆客户证据引用，不进入安全展示事实。
    # 入院/评价终点本身没有文书 ID；边界区间仍保留另一端的真实病程定位。
    if previous_document_id:
        facts["interval_start_document_id"] = previous_document_id
    if current_document_id:
        facts["interval_end_document_id"] = current_document_id
    return facts
