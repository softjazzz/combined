from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class GateDecision(str, Enum):
    PASS_TO_SECOND_GATE = "pass_to_second_gate"
    DATA_QUALITY_GAP = "data_quality_gap"
    REJECTED_BY_SYSTEM = "rejected_by_system"
    NO_ACTION = "no_action"


class GateApplicability(str, Enum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class GateCoverage(str, Enum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ApplicabilityGateResult:
    rule_id: str
    gate_name: str
    applicability: GateApplicability
    coverage: GateCoverage
    gate_decision: GateDecision
    confirmed_allowed: bool = False
    needs_second_pass_gate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence_quote: str = ""
    reason: str = ""

    def to_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["applicability"] = self.applicability.value
        payload["coverage"] = self.coverage.value
        payload["gate_decision"] = self.gate_decision.value
        return payload


def no_action(rule_id: str = "") -> ApplicabilityGateResult:
    return ApplicabilityGateResult(
        rule_id=rule_id,
        gate_name="",
        applicability=GateApplicability.UNKNOWN,
        coverage=GateCoverage.UNKNOWN,
        gate_decision=GateDecision.NO_ACTION,
        confirmed_allowed=False,
        needs_second_pass_gate=False,
        metadata={},
        evidence_quote="",
        reason="未注册适用性门控。",
    )
