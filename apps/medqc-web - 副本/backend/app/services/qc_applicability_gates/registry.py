from __future__ import annotations

from typing import Any, Callable

from .models import ApplicabilityGateResult, no_action
from .sc099_pathology_specimen_gate import run_sc099_gate
from .sc083_mdt_evidence_aggregator import run_sc083_gate
from .sc123_discharge_medication_gate import run_sc123_gate


GateRunner = Callable[[dict[str, Any], dict[str, Any] | None], ApplicabilityGateResult]

_GATES: dict[str, GateRunner] = {
    "SC-083": run_sc083_gate,
    "SC-099": run_sc099_gate,
    "SC-123": run_sc123_gate,
}


def _rule_id(result: dict[str, Any]) -> str:
    return str(result.get("rule_id") or result.get("rule_code") or "").strip().upper()


def run_applicability_gate(
    result: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> ApplicabilityGateResult:
    rule_id = _rule_id(result)
    runner = _GATES.get(rule_id)
    if not runner:
        return no_action(rule_id)
    return runner(result, context)
