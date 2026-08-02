"""把规则决策绑定到本次 EvidenceSnapshot，并统一归约客户六态。"""

from __future__ import annotations

import re

from .decision_model import (
    ApplicabilityState,
    CriterionStatus,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from .decision_reducer import (
    ReducedRuleDecision,
    reduce_luxian_0609_rule_decision,
)
from .evidence_snapshot import Luxian0609EvidenceSnapshot
from .rule_contracts import load_luxian_0609_rule_contracts
from .source_registry import (
    resolve_luxian_0609_controlled_fact_source_keys,
    resolve_luxian_0609_decision_support_source_keys,
    resolve_luxian_0609_rule_sources,
)


_BINDING_EVALUATOR_VERSION = "decision-binding-v1"
_RULE_ID_PATTERN = re.compile(r"^LX0609-\d{3}$")


def _technical_decision(
    *,
    rule_id: str,
    snapshot_hash: str,
    reason_code: str,
) -> RuleDecision:
    return RuleDecision(
        rule_id=rule_id,
        snapshot_hash=snapshot_hash,
        applicability=ApplicabilityState.ERROR,
        evidence_state=EvidenceState.TECHNICAL_ERROR,
        qc_direction=QcDirection.UNKNOWN,
        reason_code=reason_code,
        fact_refs=(),
        evaluator_version=_BINDING_EVALUATOR_VERSION,
        confidence=None,
    )


def _allowed_source_keys(rule_id: str) -> frozenset[str]:
    entries = resolve_luxian_0609_rule_sources((rule_id,))[rule_id]
    return frozenset(
        {
            *(entry.document_type for entry in entries),
            *(source_key for entry in entries for source_key in entry.source_keys),
            *resolve_luxian_0609_controlled_fact_source_keys((rule_id,)),
            *resolve_luxian_0609_decision_support_source_keys((rule_id,)),
        }
    )


def _allowed_snapshot_refs(
    *, rule_id: str, snapshot: Luxian0609EvidenceSnapshot
) -> frozenset[str]:
    allowed_sources = _allowed_source_keys(rule_id)
    return frozenset(
        {
            *(
                fact.fact_id
                for fact in snapshot.facts
                if fact.source_key in allowed_sources
            ),
            *(
                observation.snapshot_ref.removeprefix("sha256:")
                for observation in snapshot.observations
                if observation.source_key in allowed_sources
            ),
        }
    )


def _requires_evidence_ref(decision: RuleDecision) -> bool:
    return (
        decision.applicability is ApplicabilityState.NOT_APPLICABLE
        or (
            decision.applicability is ApplicabilityState.APPLICABLE
            and decision.evidence_state is EvidenceState.SUFFICIENT
            and decision.qc_direction
            in {QcDirection.SATISFIED, QcDirection.DEFECT}
        )
    )


def _criterion_results_match_decision(decision: RuleDecision) -> bool:
    contract = next(
        (
            item
            for item in load_luxian_0609_rule_contracts()
            if item.rule_id == decision.rule_id
        ),
        None,
    )
    if contract is None:
        return False
    expected_ids = tuple(item.criterion_id for item in contract.criteria)
    actual_ids = tuple(item.criterion_id for item in decision.criterion_results)
    if not expected_ids:
        return not actual_ids
    # 规则族按批迁移到子判定合同：绑定层先验证已经输出的子判定，是否为
    # 可信目录中的有序前缀；是否覆盖全部子项由对应规则族验收负责。这样既
    # 不允许执行器伪造/乱序子项，也不会在迁移窗口把旧的有效结论整体打成
    # 技术异常。
    if not actual_ids:
        return True
    if actual_ids != expected_ids[: len(actual_ids)]:
        return False
    statuses = tuple(item.status for item in decision.criterion_results)
    if decision.applicability in {
        ApplicabilityState.ERROR,
        ApplicabilityState.NOT_APPLICABLE,
    }:
        return True
    if decision.evidence_state is EvidenceState.SUFFICIENT:
        if decision.qc_direction is QcDirection.SATISFIED:
            return all(status is CriterionStatus.PASSED for status in statuses)
        if decision.qc_direction is QcDirection.DEFECT:
            return (
                CriterionStatus.FAILED in statuses
                and CriterionStatus.UNKNOWN not in statuses
            )
    if decision.evidence_state in {EvidenceState.DATA_GAP, EvidenceState.CONFLICT}:
        return (
            CriterionStatus.FAILED not in statuses
            and (
                CriterionStatus.UNKNOWN in statuses
                or len(actual_ids) < len(expected_ids)
            )
        )
    return False


def bind_and_reduce_luxian_0609_rule_decisions(
    *,
    decisions: tuple[RuleDecision, ...],
    expected_rule_ids: tuple[str, ...],
    snapshot: Luxian0609EvidenceSnapshot,
) -> tuple[ReducedRuleDecision, ...]:
    """逐规则校验 snapshot/ref；伪绑定只污染该规则，不回退旧链。"""

    if type(decisions) is not tuple or any(
        type(item) is not RuleDecision for item in decisions
    ):
        raise TypeError("decisions must be an exact tuple of RuleDecision")
    if (
        type(expected_rule_ids) is not tuple
        or not expected_rule_ids
        or len(expected_rule_ids) != len(set(expected_rule_ids))
        or any(
            not isinstance(rule_id, str)
            or not _RULE_ID_PATTERN.fullmatch(rule_id)
            for rule_id in expected_rule_ids
        )
    ):
        raise ValueError("invalid expected decision scope")
    try:
        resolve_luxian_0609_rule_sources(expected_rule_ids)
    except ValueError as exc:
        raise ValueError("invalid expected decision scope") from exc
    if not isinstance(snapshot, Luxian0609EvidenceSnapshot):
        raise TypeError("snapshot must be Luxian0609EvidenceSnapshot")

    actual_rule_ids = tuple(item.rule_id for item in decisions)
    if actual_rule_ids != expected_rule_ids:
        decisions = tuple(
            _technical_decision(
                rule_id=rule_id,
                snapshot_hash=snapshot.snapshot_hash,
                reason_code="decision_contract_violation",
            )
            for rule_id in expected_rule_ids
        )

    reduced: list[ReducedRuleDecision] = []
    for decision in decisions:
        allowed_refs = _allowed_snapshot_refs(
            rule_id=decision.rule_id,
            snapshot=snapshot,
        )
        snapshot_binding_valid = (
            decision.snapshot_hash == snapshot.snapshot_hash
            and set(decision.fact_refs).issubset(allowed_refs)
            and (not _requires_evidence_ref(decision) or bool(decision.fact_refs))
        )
        if not snapshot_binding_valid:
            bound = _technical_decision(
                rule_id=decision.rule_id,
                snapshot_hash=snapshot.snapshot_hash,
                reason_code="snapshot_mismatch",
            )
        elif not _criterion_results_match_decision(decision):
            bound = _technical_decision(
                rule_id=decision.rule_id,
                snapshot_hash=snapshot.snapshot_hash,
                reason_code="decision_contract_violation",
            )
        else:
            bound = decision
        try:
            reduced.append(reduce_luxian_0609_rule_decision(bound))
        except (TypeError, ValueError):
            reduced.append(
                reduce_luxian_0609_rule_decision(
                    _technical_decision(
                        rule_id=decision.rule_id,
                        snapshot_hash=snapshot.snapshot_hash,
                        reason_code="decision_contract_violation",
                    )
                )
            )
    return tuple(reduced)


__all__ = ["bind_and_reduce_luxian_0609_rule_decisions"]
