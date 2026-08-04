"""检查检验规则的结果映射与可展示事实投影。"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Collection, Mapping, Sequence

from .decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .exam_lab_fact_extraction import ExamLabEventFact, ExamLabTextProjection


@dataclass(frozen=True)
class ExamLabOutcome:
    rule_id: str
    status: str
    reason_code: str
    fact_refs: tuple[str, ...] = ()


def build_exam_lab_rule_decision(
    *,
    outcome: ExamLabOutcome,
    snapshot: Luxian0609EvidenceSnapshot,
    allowed_source_keys: Collection[str],
    evaluator_version: str,
) -> RuleDecision:
    """将受控结果映射为 RuleDecision；来源白名单必须由调用方显式提供。"""

    allowed_keys = set(allowed_source_keys)
    refs = tuple(dict.fromkeys((
        observation.snapshot_ref.removeprefix("sha256:")
        for observation in snapshot.observations
        if observation.source_key in allowed_keys
    )))
    # 模型选择的行级引用已在 projection parser 内严格校验，但它们不是
    # EvidenceSnapshot 中可独立见证的 FactV2。RuleDecision 只能提交已绑定的
    # 来源快照/FactV2 引用，否则统一 reducer 会按 snapshot_mismatch 拒绝。
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
    elif outcome.status == "not_applicable":
        dimensions = (
            ApplicabilityState.NOT_APPLICABLE,
            EvidenceState.SUFFICIENT,
            QcDirection.UNKNOWN,
            "trigger_absent_complete",
        )
    elif outcome.status == "data_gap":
        preserved_gap_reasons = {
            "authoritative_time_missing",
            "authoritative_time_conflict",
            "evaluation_window_not_mature",
            "positive_assertion_not_explicit",
        }
        dimensions = (
            ApplicabilityState.UNKNOWN,
            EvidenceState.DATA_GAP,
            QcDirection.UNKNOWN,
            outcome.reason_code
            if outcome.reason_code in preserved_gap_reasons
            else "source_unavailable"
            if "unavailable" in outcome.reason_code
            else "required_field_missing",
        )
    elif outcome.status == "evaluation_unknown":
        dimensions = (
            ApplicabilityState.APPLICABLE,
            EvidenceState.CONFLICT,
            QcDirection.UNKNOWN,
            "semantic_output_unknown",
        )
    elif outcome.status == "technical_error":
        reason_code = (
            "source_query_error"
            if outcome.reason_code == "source_query_error"
            else "model_invalid_output"
            if outcome.reason_code == "exam_lab_llm_invalid_output"
            else "model_transport_error"
            if outcome.reason_code == "exam_lab_llm_failure"
            else "executor_exception"
        )
        dimensions = (
            ApplicabilityState.ERROR,
            EvidenceState.TECHNICAL_ERROR,
            QcDirection.UNKNOWN,
            reason_code,
        )
    else:
        raise ValueError("unsupported exam lab outcome")
    applicability, evidence_state, qc_direction, reason_code = dimensions
    return RuleDecision(
        rule_id=outcome.rule_id,
        snapshot_hash=snapshot.snapshot_hash,
        applicability=applicability,
        evidence_state=evidence_state,
        qc_direction=qc_direction,
        reason_code=reason_code,
        fact_refs=refs,
        evaluator_version=evaluator_version,
        confidence=None,
    )


def build_default_display_facts(
    *,
    rule_id: str,
    status: str,
    reason_code: str,
    source_document_ids: Sequence[str] = (),
) -> Mapping[str, Any] | None:
    """仅为可确定的不合规输出可展示的检查/检验事实，不携带正文或模型输出。"""

    if status != "non_compliant":
        return None
    if reason_code not in {"exam_order_reason_missing", "exam_lab_text_fact"}:
        return None

    def with_document_ids(facts: dict[str, Any]) -> dict[str, Any]:
        # document_id 仅在来源行显式提供时才写入内部事实。后续聚合器须将其
        # 转为 HMAC evidence_ref；这里绝不根据 order_id、行号或正文猜测文书。
        ids = tuple(
            dict.fromkeys(
                value
                for raw in source_document_ids
                if (value := _clean(raw))
            )
        )
        if ids:
            facts["source_document_ids"] = list(ids)
        return facts

    if rule_id == "LX0609-010":
        return with_document_ids({
            "failure_kind": "exam_lab_requirement_not_documented",
            "subject": "ct_mri",
            "requirement": "reason_before_order",
            "event_phase": "order",
            "checked_sources": ["exam_lab_order", "course_record"],
        })
    if rule_id in {"LX0609-011", "LX0609-014"}:
        return with_document_ids({
            "failure_kind": "exam_lab_requirement_not_documented",
            "subject": "ct_mri" if rule_id == "LX0609-011" else "culture_susceptibility",
            "requirement": "result_recording_within_24h",
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
        })
    if rule_id in {"LX0609-012", "LX0609-015"}:
        return with_document_ids({
            "failure_kind": "exam_lab_requirement_not_documented",
            "subject": "ct_mri" if rule_id == "LX0609-012" else "culture_susceptibility",
            "requirement": "positive_result_analysis_within_24h",
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
        })
    return None


def build_text_outcome_display_facts(
    *,
    rule_id: str,
    status: str,
    fact: ExamLabEventFact,
    projection: ExamLabTextProjection,
) -> Mapping[str, Any] | None:
    """输出报告事件、响应病程和24小时计算事实，不暴露正文。"""

    if (
        rule_id not in {"LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"}
        or status not in {"compliant", "non_compliant", "not_applicable"}
    ):
        return None
    is_exam_rule = rule_id in {"LX0609-011", "LX0609-012"}
    event = projection.imaging_event if is_exam_rule else projection.culture_event
    if event is None:
        return None
    subject = "ct_mri" if is_exam_rule else "culture_susceptibility"
    analysis_rule = rule_id in {"LX0609-012", "LX0609-015"}
    requirement = (
        "positive_result_analysis_within_24h"
        if analysis_rule
        else "result_recording_within_24h"
    )
    response_times = sorted(
        value
        for ref in fact.course_doc_refs
        if (value := projection.course_times.get(ref)) is not None
        and event.report_time is not None
        and value >= event.report_time
    )
    first_response = response_times[0] if response_times else None
    facts: dict[str, Any] = {
        (
            "failure_kind"
            if status == "non_compliant"
            else "verification_kind"
        ): (
            "exam_lab_requirement_not_documented"
            if status == "non_compliant"
            else "exam_lab_requirement_checked"
        ),
        "subject": subject,
        "requirement": requirement,
        "event_phase": "report",
        "checked_sources": ["exam_lab_report", "course_record"],
        "applicable": status != "not_applicable",
        "positive_state": fact.positive_state,
        "threshold_hours": 24,
        "response_record_count": len(response_times),
    }
    if status != "not_applicable":
        facts["requirement_met"] = status == "compliant"
    if event.report_time is not None:
        facts["report_time"] = event.report_time.strftime("%Y-%m-%d %H:%M:%S")
    if first_response is not None and event.report_time is not None:
        facts["response_record_time"] = first_response.strftime("%Y-%m-%d %H:%M:%S")
        facts["interval_hours"] = round(
            (first_response - event.report_time).total_seconds() / 3600,
            2,
        )
    return facts


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


__all__ = [
    "ExamLabOutcome",
    "build_default_display_facts",
    "build_exam_lab_rule_decision",
    "build_text_outcome_display_facts",
]
