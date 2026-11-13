"""LX0609-02-01-03 稳定患者病程记录间隔判定。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable, Mapping

from ..basic_timeliness_facts import CourseRoundRole, classify_course_round_role, extract_admission_anchor, AdmissionAnchorState
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
    build_material_document_refs,
)
from ... import daily_material_projection
from ..evidence_snapshot import Luxian0609EvidenceSnapshot
from ..source_evidence_reader import (
    EVALUATION_HORIZON_SOURCE_KEY,
    authoritative_document_time_value,
)
from .shared import authoritative_course_time, row_text
from ..basic_timeliness_facts import parse_authoritative_datetime as _typed_course_time


RULE_007_RECORD_SOURCES = ("daily_course_record", "senior_course_record")
_RULE_007_ADMISSION_SOURCE = "inpat_registration"
_MAX_INTERVAL = timedelta(hours=72)
_DAILY_ROUND_CONTENT_PREFIX = re.compile(
    r"^查房内容\s*[：:]+\s*(?P<content>.+)$"
)
_NON_PERFORMED_ROUND_PREFIXES = ("未进行", "未完成", "取消", "未查房", "计划", "暂缓")
_NON_CURRENT_ROUND_PREFIXES = ("昨日查房", "明日查房")


def _missing_time_capacity_exceeded(
    *, admission_time: datetime, record_times: list[datetime],
    horizon_time: datetime | None, horizon_date: date | None,
    missing_time_count: int,
) -> dict[str, Any] | None:
    """按缺时记录最有利放置计算下界，只有仍不足时输出可证明的缺陷事实。"""

    if not missing_time_count or (horizon_time is None and horizon_date is None):
        return None
    lower_bound = horizon_time if horizon_time is not None else datetime.combine(horizon_date, datetime.min.time())
    known_times = sorted(set(record_times))
    boundaries = (admission_time, *known_times, lower_bound)
    required = 0
    for start, end in zip(boundaries, boundaries[1:]):
        quotient, remainder = divmod(end - start, _MAX_INTERVAL)
        required += max(0, quotient + bool(remainder) - 1)
    if required <= missing_time_count:
        return None
    return {
        "failure_kind": "course_interval_capacity_exceeded",
        "admission_time": admission_time.isoformat(sep=" "),
        "horizon_lower_bound_time": lower_bound.isoformat(sep=" "),
        "horizon_precision": "datetime" if horizon_time is not None else "date",
        "known_record_count": len(known_times), "missing_time_count": missing_time_count,
        "minimum_required_records": required, "threshold_hours": 72,
    }


def _admission_for_007(materials):
    """复用现有入院锚点优先级，不以文书时间替代入院时间。"""
    registration = tuple(materials.rows("inpat_registration"))
    anchor = extract_admission_anchor(registration_rows=registration, admission_rows=(), discharge_rows=(), allow_date_fallback=False)
    if anchor.state is not AdmissionAnchorState.MISSING:
        selected = tuple(row for row in registration if _typed_course_time(row.get("admission_datetime") or row.get("admission_time")) == anchor.anchor_time)
        return anchor, selected if anchor.state is AdmissionAnchorState.EXACT else registration
    admission = tuple(materials.rows("admission_record"))
    anchor = extract_admission_anchor(registration_rows=registration, admission_rows=admission, discharge_rows=(), allow_date_fallback=False)
    selected = tuple(row for row in admission if _typed_course_time(row.get("admission_datetime") or row.get("admission_time")) == anchor.anchor_time)
    return anchor, selected if anchor.state is AdmissionAnchorState.EXACT else admission


def _daily_round_content_is_substantive(content: str) -> bool:
    """确认查房前缀后的正文确实记录了本次查房，而非空壳或未执行说明。"""

    normalized = content.lstrip("：:，, ").strip()
    if normalized.startswith("今日查房"):
        nested = re.match(r"^今日查房\s*[：:,，]\s*(.+)$", normalized)
        if nested is None:
            return False
        normalized = nested.group(1).lstrip("：:，, ").strip()
    if normalized.startswith(_NON_CURRENT_ROUND_PREFIXES):
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", normalized)) and not normalized.startswith(
        _NON_PERFORMED_ROUND_PREFIXES
    )


def _is_round_record(row: Mapping[str, Any], *, source_key: str) -> bool:
    """排除明确标成其他用途的病程；标题缺失时保留来源表既有语义。"""

    title = "".join(
        "".join(str(row.get(field) or "").split())
        for field in ("document_title", "title")
    )
    if not title:
        return True
    if source_key == "daily_course_record" and title == "日常病程记录":
        # 日常病程的固定“查房内容”前缀后可能直接进入术后天数/病情，
        # 不能只要求出现“今日查房”，否则会漏掉有权威时间的明确查房记录。
        body = str(row.get("record_content") or row.get("content") or "").strip()
        current = re.match(r"^(?:查房内容\s*[：:]+\s*)?今日查房\s*[：:,，]\s*(.+)", body)
        if current:
            return _daily_round_content_is_substantive(current.group(1))
        prefixed = _DAILY_ROUND_CONTENT_PREFIX.match(body)
        if prefixed:
            return _daily_round_content_is_substantive(prefixed.group("content"))
    role = classify_course_round_role(row, source_key=source_key)
    return "查房" in title and role is not CourseRoundRole.NONE


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

        daily_scope_complete = (
            evidence_materials.permits_absence("daily_course_record")
            if evidence_materials is not None
            else daily_material_projection.permits_absence("daily_course_record")
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
    if interval_over_72h and not daily_scope_complete:
        return Rule007LegacyOutcome(
            status="data_gap",
            reason_code="course_time_source_unavailable",
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


def _material_document_refs_by_row(
    *,
    snapshot: Luxian0609EvidenceSnapshot,
    materials: Luxian0609EvidenceMaterialStore,
    source_key: str,
) -> dict[int, str]:
    """返回本次材料仓中每行对应的已绑定文书引用。

    规则只保存真正参与判定的行引用；不能再把整个来源 observation 当作
    客户证据的替代品。材料仓和 ``document_rows`` 共享同一行实例，因此以
    对象身份配对不会引入第二套文书 ID 或摘要算法。
    """

    return {
        id(row): document_ref
        for document_ref, row in materials.document_rows(
            source_key,
            snapshot=snapshot,
        )
    }


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

    evaluator_version = "rule007-authoritative-time-v3"
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
            rule_id="LX0609-02-01-03",
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
    # ``fact_refs`` 只保留参与该次判定的受控事实和实际文书行；来源级
    # observation 不再被当作“全来源证据”塞进每个结论。
    refs: set[str] = set()

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
            if source_key == _RULE_007_ADMISSION_SOURCE and observation.query_state.value == "empty":
                continue
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
        admission_anchor, admission_rows = _admission_for_007(materials)
        admission_source = admission_anchor.source_key or _RULE_007_ADMISSION_SOURCE
        horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
        admission_document_refs = _material_document_refs_by_row(
            snapshot=snapshot,
            materials=materials,
            source_key=admission_source,
        )
    except EvidenceMaterialUnavailable:
        fallback_observation = observation_by_source.get("admission_record")
        query_failed = fallback_observation is not None and fallback_observation.query_state.value == "error"
        return decision(
            applicability=ApplicabilityState.ERROR if query_failed else ApplicabilityState.UNKNOWN,
            evidence_state=EvidenceState.TECHNICAL_ERROR if query_failed else EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="source_query_error" if query_failed else "source_unavailable",
            refs=refs, confidence=None,
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
    if admission_anchor.state is not AdmissionAnchorState.EXACT or len(horizon_rows) != 1:
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.DATA_GAP,
            qc_direction=QcDirection.UNKNOWN,
            reason_code="authoritative_time_conflict" if admission_anchor.state is AdmissionAnchorState.CONFLICT else "authoritative_time_missing",
            refs=refs,
            confidence=None,
        )
    admission_document_ref = admission_document_refs.get(id(admission_rows[0]))
    if admission_document_ref:
        refs.add(admission_document_ref)
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
    admission_time = admission_anchor.anchor_time
    horizon_time = _typed_course_time(horizon_rows[0].get("horizon_datetime"))
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

    record_refs_by_time: dict[datetime, set[str]] = {}
    missing_time_refs: set[str] = set()
    missing_time_count = 0
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
            document_refs_by_row = _material_document_refs_by_row(
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
            if not _is_round_record(row, source_key=source_key):
                continue
            parsed = _typed_course_time(
                authoritative_document_time_value(row)
            )
            if parsed is not None:
                document_ref = document_refs_by_row.get(id(row))
                if document_ref:
                    record_refs_by_time.setdefault(parsed, set()).add(document_ref)
            elif row_text(row):
                substantive_record_without_time = True
                missing_time_count += 1
                document_ref = document_refs_by_row.get(id(row))
                if document_ref:
                    missing_time_refs.add(document_ref)

    bounded_record_refs_by_time = {
        record_time: document_refs
        for record_time, document_refs in record_refs_by_time.items()
        if admission_time <= record_time
        and (
            (
                horizon_time is None
                and horizon_date is not None
                and record_time.date() < horizon_date
            )
            or (horizon_time is not None and record_time <= horizon_time)
        )
    }
    # 保持既有“同一权威时间只算一条查房记录”的时限语义；若同刻多份文书
    # 都参与了这个时间点的判定，仍将其全部作为客户可定位证据投影。
    ordered_times = sorted(bounded_record_refs_by_time)
    refs.update(
        document_ref
        for document_refs in bounded_record_refs_by_time.values()
        for document_ref in document_refs
    )
    def missing_scope_decision():
        return decision(applicability=ApplicabilityState.APPLICABLE,
                        evidence_state=EvidenceState.DATA_GAP, qc_direction=QcDirection.UNKNOWN,
                        reason_code="source_unavailable", refs=refs, confidence=None)

    capacity_facts = _missing_time_capacity_exceeded(
        admission_time=admission_time, record_times=ordered_times,
        horizon_time=horizon_time, horizon_date=horizon_date,
        missing_time_count=missing_time_count,
    )
    if capacity_facts is not None:
        if not materials.permits_absence("daily_course_record"):
            return missing_scope_decision()
        refs.update(missing_time_refs)
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT, qc_direction=QcDirection.DEFECT,
            reason_code="threshold_exceeded", refs=refs, confidence=1.0,
        )
    # 完整来源没有任何可定位病程记录时，先区分规则是否成熟，再区分
    # “记录不存在”和“候选记录存在但时间缺失”。空来源本身不是时间缺口。
    if not ordered_times and horizon_time is not None:
        elapsed = horizon_time - admission_time
        if elapsed < _MAX_INTERVAL:
            return decision(
                applicability=ApplicabilityState.NOT_APPLICABLE,
                evidence_state=EvidenceState.SUFFICIENT,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="evaluation_window_not_mature",
                refs=refs,
                confidence=1.0,
            )
        if substantive_record_without_time:
            refs.update(missing_time_refs)
            return decision(
                applicability=ApplicabilityState.APPLICABLE,
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="authoritative_time_missing",
                refs=refs,
                confidence=None,
            )
        if not materials.permits_absence("daily_course_record"):
            return missing_scope_decision()
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="threshold_exceeded",
            refs=refs,
            confidence=1.0,
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
            for record_time in record_refs_by_time
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
    if not ordered_times and horizon_time is None:
        assert horizon_date is not None
        deadline_date = (admission_time + _MAX_INTERVAL).date()
        if horizon_date < deadline_date:
            return decision(
                applicability=ApplicabilityState.NOT_APPLICABLE,
                evidence_state=EvidenceState.SUFFICIENT,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="evaluation_window_not_mature",
                refs=refs,
                confidence=1.0,
            )
        if horizon_date == deadline_date or substantive_record_without_time:
            if substantive_record_without_time:
                refs.update(missing_time_refs)
            return decision(
                applicability=ApplicabilityState.APPLICABLE,
                evidence_state=EvidenceState.DATA_GAP,
                qc_direction=QcDirection.UNKNOWN,
                reason_code="authoritative_time_missing",
                refs=refs,
                confidence=None,
            )
        if not materials.permits_absence("daily_course_record"):
            return missing_scope_decision()
        return decision(
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="threshold_exceeded",
            refs=refs,
            confidence=1.0,
        )
    if interval_over_72h and substantive_record_without_time:
        refs.update(missing_time_refs)
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

    if decision.rule_id != "LX0609-02-01-03":
        return None
    if (
        decision.applicability is ApplicabilityState.NOT_APPLICABLE
        and decision.reason_code == "eligibility_not_met"
    ):
        return {
            "failure_kind": "unstable_patient_order_present",
            "stable_course_rule_applicable": False,
        }
    if decision.reason_code == "evaluation_window_not_mature":
        return None
    if decision.evidence_state is EvidenceState.DATA_GAP and decision.reason_code in {
        "source_unavailable", "authoritative_time_missing", "source_truncated"
    }:
        # 与执行器相同的资料顺序，记录阻止本次核对的实际来源；空病程表不是缺源。
        try:
            resolved_anchor, _ = _admission_for_007(materials)
        except (EvidenceMaterialUnavailable, EvidenceMaterialTruncated):
            resolved_anchor = None
        for source in (_RULE_007_ADMISSION_SOURCE, EVALUATION_HORIZON_SOURCE_KEY, *RULE_007_RECORD_SOURCES):
            if source == _RULE_007_ADMISSION_SOURCE and resolved_anchor is not None and resolved_anchor.state is AdmissionAnchorState.EXACT:
                continue
            try:
                rows = tuple(materials.rows(source))
            except EvidenceMaterialTruncated:
                return {"failure_kind": "course_interval_source_gap", "gap_source": source, "gap_kind": "truncated"}
            except EvidenceMaterialUnavailable:
                return {"failure_kind": "course_interval_source_gap", "gap_source": source, "gap_kind": "unavailable"}
            if source in {_RULE_007_ADMISSION_SOURCE, EVALUATION_HORIZON_SOURCE_KEY}:
                if not rows or (len(rows) != 1 and decision.reason_code == "authoritative_time_missing"):
                    return {"failure_kind": "course_interval_source_gap", "gap_source": source, "gap_kind": "empty" if not rows else "ambiguous"}
                if decision.reason_code != "authoritative_time_missing":
                    continue
                valid = (
                    _typed_course_time(rows[0].get("admission_datetime")) is not None
                    if source == _RULE_007_ADMISSION_SOURCE else
                    _typed_course_time(rows[0].get("horizon_datetime")) is not None
                    or _evaluation_horizon_date(rows[0].get("horizon_date")) is not None
                )
                if not valid:
                    return {"failure_kind": "course_interval_source_gap", "gap_source": source, "gap_kind": "time_missing"}
            elif decision.reason_code == "authoritative_time_missing":
                # 只展示执行器选中的缺时文书；无关的无时间记录不能解释其他边界缺口。
                round_rows = [
                    row for row in rows
                    if _is_round_record(row, source_key=source)
                ]
                missing_refs = build_material_document_refs(
                    source_key=source, rows=tuple(
                        row for row in round_rows
                        if _typed_course_time(authoritative_document_time_value(row)) is None
                        and row_text(row)
                    ),
                )
                missing_count = len(set(missing_refs).intersection(decision.fact_refs))
                if missing_count:
                    return {
                        "failure_kind": "course_interval_source_gap", "gap_source": source,
                        "gap_kind": "time_missing", "record_count": len(round_rows),
                        "missing_time_count": missing_count,
                    }
    if decision.evidence_state is not EvidenceState.SUFFICIENT:
        return None
    record_points: list[tuple[datetime, str, str]] = []
    missing_time_count = 0
    try:
        admission_anchor, admission_rows = _admission_for_007(materials)
        admission_source = admission_anchor.source_key or _RULE_007_ADMISSION_SOURCE
        horizon_rows = tuple(materials.rows(EVALUATION_HORIZON_SOURCE_KEY))
        if admission_anchor.state is not AdmissionAnchorState.EXACT or len(horizon_rows) != 1:
            return None
        admission_time = admission_anchor.anchor_time
        horizon_time = _typed_course_time(
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
                if not _is_round_record(row, source_key=source_key):
                    continue
                record_time = _typed_course_time(
                    authoritative_document_time_value(row)
                )
                if record_time is None and row_text(row):
                    missing_time_count += 1
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
    if decision.qc_direction is QcDirection.DEFECT and decision.reason_code == "threshold_exceeded":
        capacity_facts = _missing_time_capacity_exceeded(
            admission_time=admission_time, record_times=[item[0] for item in record_points],
            horizon_time=horizon_time, horizon_date=horizon_date,
            missing_time_count=missing_time_count,
        )
        if capacity_facts is not None:
            return capacity_facts
    ordered_records = sorted(
        record_points,
        key=lambda item: (item[0], item[1], item[2]),
    )
    ordered_points = [
        (admission_time, admission_source, ""),
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
                "interval_start_time": previous_time.isoformat(sep=" "),
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
    interval_seconds = interval.total_seconds()
    if interval_seconds.is_integer():
        interval_seconds = int(interval_seconds)
    threshold_seconds = round(_MAX_INTERVAL.total_seconds())
    if (
        decision.qc_direction is QcDirection.DEFECT
        and interval_seconds <= threshold_seconds
    ):
        # 到达 72 小时仍完全没有记录属于缺失，但“恰好 72 小时”不是一个
        # 超时区间，不能伪造超过阈值的展示事实。
        return None
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
        "interval_start_time": previous_time.isoformat(sep=" "),
        "interval_end_time": current_time.isoformat(sep=" "),
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
