"""把 LX0609 结构化规则决策归约为唯一客户六态。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .decision_model import (
    ALLOWED_REASON_CODES_BY_FINAL_STATE,
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)


_REDUCER_ATTESTATION = object()


class CustomerFinalState(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    DATA_GAP = "data_gap"
    TECHNICAL_ERROR = "technical_error"
    EVALUATION_UNKNOWN = "evaluation_unknown"


@dataclass(frozen=True, init=False)
class ReducedRuleDecision:
    rule_id: str
    snapshot_hash: str
    final_state: CustomerFinalState
    reason_code: str
    fact_refs: tuple[str, ...]
    evaluator_version: str
    confidence: float | None
    decision_fingerprint: str

    def __init__(
        self,
        *,
        rule_id: str,
        snapshot_hash: str,
        final_state: CustomerFinalState,
        reason_code: str,
        fact_refs: tuple[str, ...],
        evaluator_version: str,
        confidence: float | None,
        decision_fingerprint: str,
        _attestation: object | None = None,
    ) -> None:
        if _attestation is not _REDUCER_ATTESTATION:
            raise TypeError("ReducedRuleDecision is reducer-owned")
        if not isinstance(final_state, CustomerFinalState):
            raise TypeError("invalid reduced final_state")
        for name, value in (
            ("rule_id", rule_id),
            ("snapshot_hash", snapshot_hash),
            ("final_state", final_state),
            ("reason_code", reason_code),
            ("fact_refs", fact_refs),
            ("evaluator_version", evaluator_version),
            ("confidence", confidence),
            ("decision_fingerprint", decision_fingerprint),
        ):
            object.__setattr__(self, name, value)

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "snapshot_hash": self.snapshot_hash,
            "final_state": self.final_state.value,
            "reason_code": self.reason_code,
            "fact_refs": list(self.fact_refs),
            "evaluator_version": self.evaluator_version,
            "confidence": self.confidence,
            "decision_fingerprint": self.decision_fingerprint,
        }


def reduce_luxian_0609_rule_decision(
    decision: RuleDecision,
) -> ReducedRuleDecision:
    """按固定优先级归约，任何文本字段均不参与状态判断。"""

    if not isinstance(decision, RuleDecision):
        raise TypeError("decision must be RuleDecision")

    if (
        decision.applicability is ApplicabilityState.ERROR
        or decision.evidence_state is EvidenceState.TECHNICAL_ERROR
    ):
        final_state = CustomerFinalState.TECHNICAL_ERROR
    elif decision.applicability is ApplicabilityState.NOT_APPLICABLE:
        final_state = CustomerFinalState.NOT_APPLICABLE
    elif decision.evidence_state is EvidenceState.DATA_GAP:
        final_state = CustomerFinalState.DATA_GAP
    elif decision.evidence_state is EvidenceState.CONFLICT:
        final_state = CustomerFinalState.EVALUATION_UNKNOWN
    elif decision.applicability is ApplicabilityState.UNKNOWN:
        final_state = CustomerFinalState.EVALUATION_UNKNOWN
    elif decision.qc_direction is QcDirection.UNKNOWN:
        final_state = CustomerFinalState.EVALUATION_UNKNOWN
    elif decision.qc_direction is QcDirection.DEFECT:
        final_state = CustomerFinalState.NON_COMPLIANT
    else:
        final_state = CustomerFinalState.COMPLIANT

    if decision.reason_code not in ALLOWED_REASON_CODES_BY_FINAL_STATE[
        final_state.value
    ]:
        raise ValueError("reason_code does not match reduced final_state")

    return ReducedRuleDecision(
        rule_id=decision.rule_id,
        snapshot_hash=decision.snapshot_hash,
        final_state=final_state,
        reason_code=decision.reason_code,
        fact_refs=decision.fact_refs,
        evaluator_version=decision.evaluator_version,
        confidence=decision.confidence,
        decision_fingerprint=decision.fingerprint(),
        _attestation=_REDUCER_ATTESTATION,
    )
