from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.services.luxian_0609.deterministic_gate import GateDecision, GateFactRef, GateReport
from app.services.luxian_0609.programmatic_rules import FindingKind, ProgrammaticFinding, ProgrammaticFindingReport, build_luxian_0609_programmatic_findings_shadow
from app.services.luxian_0609.result_aggregator import FinalState, AggregatedRuleResult, aggregate_luxian_0609_programmatic_findings_shadow

CREATED = "2026-07-12T14:00:00+08:00"
EXPECTED = {FindingKind.REQUIREMENT_SATISFIED: FinalState.COMPLIANT, FindingKind.REQUIRED_DOCUMENT_MISSING: FinalState.NON_COMPLIANT, FindingKind.TRIGGER_ABSENT: FinalState.NOT_APPLICABLE, FindingKind.SOURCE_INCOMPLETE: FinalState.DATA_GAP, FindingKind.TECHNICAL_FAILURE: FinalState.TECHNICAL_ERROR, FindingKind.EVIDENCE_CONFLICT: FinalState.EVALUATION_UNKNOWN}


def _gate(kind):
    if kind is FindingKind.REQUIREMENT_SATISFIED: decision = GateDecision("LX0609-030", "matched", "surgery_record", "present", "ready", (GateFactRef("a" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order"),), (), ())
    elif kind is FindingKind.REQUIRED_DOCUMENT_MISSING: decision = GateDecision("LX0609-030", "matched", "surgery_record", "empty", "ready", (GateFactRef("a" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order"),), (), ())
    elif kind is FindingKind.TRIGGER_ABSENT: decision = GateDecision("LX0609-030", "absent_complete", "surgery_record", None, "not_triggered", (), (), ())
    elif kind is FindingKind.EVIDENCE_CONFLICT: decision = GateDecision("LX0609-030", "semantic_conflict", "surgery_record", None, "blocked", (), (), ())
    elif kind is FindingKind.SOURCE_INCOMPLETE: decision = GateDecision("LX0609-030", "coverage_partial", "surgery_record", None, "blocked", (), (), ())
    else: decision = GateDecision("LX0609-030", "coverage_error", "surgery_record", None, "blocked", (), (), ())
    return GateReport("gate-v1", "policy-v1", "visit-prog-001", "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, ("LX0609-030",), (decision,), CREATED)


def _pair(kind):
    gate = _gate(kind)
    finding = build_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at=CREATED)
    return gate, finding


@pytest.mark.parametrize("kind", list(EXPECTED))
def test_all_attested_findings_have_exact_aggregator_owned_final_state(kind):
    gate, finding = _pair(kind)
    result = aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=finding, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert result.results[0].final_state is EXPECTED[kind]
    assert result.summary_dict()["shadow_only"] is True and result.summary_dict()["release_eligible"] is False
    assert "ai_suggested" not in result.canonical_json()


def test_only_gate_attested_report_can_reach_final_mapping():
    gate, valid = _pair(FindingKind.REQUIREMENT_SATISFIED)
    forged = ProgrammaticFindingReport("finding-v1", "policy-v1", "visit-prog-001", "a" * 64, (ProgrammaticFinding("LX0609-030", "requirement_satisfied", "surgery_record", "matched", "present", "ready", (), (), ("a" * 64,)),), CREATED)
    with pytest.raises(TypeError): aggregate_luxian_0609_programmatic_findings_shadow(finding_report=forged, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="attest"):
        aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=forged, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=valid, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED).results


@pytest.mark.parametrize("field", ["visit_ref", "gate_fingerprint", "finding_schema_version", "finding_policy_version", "created_at", "findings"])
def test_attestation_rejects_every_safe_provenance_tamper(field):
    gate, finding = _pair(FindingKind.REQUIREMENT_SATISFIED)
    replacement = ("other-visit" if field == "visit_ref" else ("b" * 64 if field == "gate_fingerprint" else ("finding-v2" if field.endswith("version") else ("2026-07-13T14:00:00+08:00" if field == "created_at" else ()))))
    with pytest.raises(ValueError, match="attest"):
        aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=replace(finding, **{field: replacement}), aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)


def test_032_is_independent_and_return_is_safe_only():
    decision = GateDecision("LX0609-032", "matched", "surgery_safecheck_record", "present", "ready", (GateFactRef("a" * 64, "current_visit_surgery_confirmed", "surgery_record"),), ("LX0609-030",), ("informational_parent_only",))
    gate = GateReport("gate-v1", "policy-v1", "visit-prog-001", "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, ("LX0609-032",), (decision,), CREATED)
    finding = build_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at=CREATED)
    result = aggregate_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_report=finding, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert result.results[0].final_state is FinalState.COMPLIANT
    assert not any(name in vars(result) for name in ("gate", "gate_report", "finding", "finding_report", "fact"))
    assert "quote" not in repr(result) + str(asdict(result)) + result.canonical_json()


def test_constructor_mapping_and_real_type_boundary_fail_closed():
    with pytest.raises(ValueError): AggregatedRuleResult("LX0609-030", FindingKind.REQUIRED_DOCUMENT_MISSING, FinalState.COMPLIANT)
    with pytest.raises(TypeError): aggregate_luxian_0609_programmatic_findings_shadow(gate_report=object(), finding_report=object(), aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
