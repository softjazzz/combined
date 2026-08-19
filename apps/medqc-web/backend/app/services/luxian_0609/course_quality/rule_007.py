"""LX0609-007 稳定患者病程记录间隔判定。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
    authoritative_document_time_value,
)
from .shared import authoritative_course_time, row_text


RULE_007_RECORD_SOURCES = ("daily_course_record", "senior_course_record")
_MAX_INTERVAL = timedelta(hours=72)


@dataclass(frozen=True)
class Rule007LegacyOutcome:
    status: str
    reason_code: str


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
    """只用同一snapshot的不稳定医嘱事实和两类病程权威时间裁决。"""

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
        current - previous > _MAX_INTERVAL
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
    record_by_time: dict[datetime, tuple[str, str]] = {}
    try:
        for source_key in RULE_007_RECORD_SOURCES:
            for row in materials.rows(source_key):
                if (
                    record_time := authoritative_course_time(
                        authoritative_document_time_value(row)
                    )
                ) is not None:
                    document_id = str(
                        row.get("document_id") or row.get("id") or ""
                    ).strip()
                    record_by_time.setdefault(
                        record_time,
                        (source_key, document_id),
                    )
    except (EvidenceMaterialTruncated, EvidenceMaterialUnavailable):
        return None
    ordered_times = sorted(record_by_time)
    intervals = tuple(
        (current - previous, previous, current)
        for previous, current in zip(ordered_times, ordered_times[1:])
    )
    if not intervals:
        return None
    interval, previous, current = max(intervals, key=lambda item: item[0])
    interval_seconds = round(interval.total_seconds())
    threshold_seconds = round(_MAX_INTERVAL.total_seconds())
    previous_position = ordered_times.index(previous) + 1
    current_position = ordered_times.index(current) + 1
    previous_source, previous_document_id = record_by_time[previous]
    current_source, current_document_id = record_by_time[current]
    facts: dict[str, Any] = {
        "failure_kind": (
            "course_record_interval_over_72h"
            if interval > _MAX_INTERVAL
            else "course_record_interval_within_72h"
        ),
        "interval_start_source": previous_source,
        "interval_end_source": current_source,
        "interval_start_time": previous.strftime("%Y-%m-%d %H:%M:%S"),
        "interval_end_time": current.strftime("%Y-%m-%d %H:%M:%S"),
        "interval_start_position": previous_position,
        "interval_end_position": current_position,
        "record_count": len(ordered_times),
        "interval_seconds": interval_seconds,
        "overdue_seconds": max(0, interval_seconds - threshold_seconds),
        "interval_hours": round(interval_seconds / 3600, 2),
        "threshold_hours": 72,
        "recorded_dates": [item.date().isoformat() for item in ordered_times],
    }
    # 文书 ID 仅供 Aggregator 生成不可逆客户证据引用，不进入安全展示事实。
    # 两端必须同时可定位，避免只展示半个超时区间。
    if previous_document_id and current_document_id:
        facts["interval_start_document_id"] = previous_document_id
        facts["interval_end_document_id"] = current_document_id
    return facts
