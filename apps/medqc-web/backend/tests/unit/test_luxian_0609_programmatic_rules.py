from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.services.luxian_0609.deterministic_gate import GateDecision, GateFactRef, GateReport
from app.services.luxian_0609.programmatic_rules import FindingKind, ProgrammaticFinding, ProgrammaticFindingReport, build_luxian_0609_programmatic_findings_shadow

CREATED = "2026-07-12T14:00:00+08:00"


def _decision(trigger, target=None):
    ref = GateFactRef("a" * 64, "current_visit_surgery_order_confirmed", "inpat_nondrug_order")
    if trigger == "matched": return GateDecision("LX0609-030", trigger, "surgery_record", target, "ready" if target in ("present", "empty") else "blocked", (ref,), (), ())
    return GateDecision("LX0609-030", trigger, "surgery_record", None, "not_triggered" if trigger == "absent_complete" else "blocked", (), (), ())


def _gate(*, decision=None):
    return GateReport("gate-v1", "policy-v1", "visit-prog-001", "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, ("LX0609-030",), (_decision("absent_complete") if decision is None else decision,), CREATED)


@pytest.mark.parametrize(("trigger", "target", "kind"), [
    ("matched", "present", FindingKind.REQUIREMENT_SATISFIED), ("matched", "empty", FindingKind.REQUIRED_DOCUMENT_MISSING),
    ("absent_complete", None, FindingKind.TRIGGER_ABSENT), ("semantic_conflict", None, FindingKind.EVIDENCE_CONFLICT),
    ("source_unavailable", None, FindingKind.SOURCE_INCOMPLETE), ("coverage_partial", None, FindingKind.SOURCE_INCOMPLETE),
    ("coverage_not_run", None, FindingKind.SOURCE_INCOMPLETE), ("source_error", None, FindingKind.TECHNICAL_FAILURE),
    ("coverage_error", None, FindingKind.TECHNICAL_FAILURE), ("matched", "unavailable", FindingKind.SOURCE_INCOMPLETE),
    ("matched", "error", FindingKind.TECHNICAL_FAILURE),
])
def test_full_gate_matrix_maps_to_exact_internal_finding(trigger, target, kind):
    report = build_luxian_0609_programmatic_findings_shadow(gate_report=_gate(decision=_decision(trigger, target)), finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at=CREATED)
    assert report.findings[0].finding_kind is kind
    assert report.summary_dict()["expected_llm_call_count"] == 0


def test_zero_safe_output_identity_and_constructor_guards():
    zero = GateReport("gate-v1", "policy-v1", "visit-prog-001", "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, (), (), CREATED)
    report = build_luxian_0609_programmatic_findings_shadow(gate_report=zero, finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at=CREATED)
    assert report.findings == () and report.fingerprint() == replace(report, created_at="2026-07-13T14:00:00+08:00").fingerprint()
    assert not any(name in vars(report) for name in ("gate", "gate_report", "fact", "manifest", "bundle", "coverage"))
    assert "quote" not in repr(report) + str(asdict(report)) + report.canonical_json()
    with pytest.raises(TypeError): build_luxian_0609_programmatic_findings_shadow(gate_report=object(), finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at=CREATED)
    with pytest.raises(ValueError): ProgrammaticFinding("LX0609-030", "trigger_absent", "surgery_record", (), (), ("a" * 64,))


def test_032_stays_in_order_and_parent_is_only_safe_metadata():
    decision = GateDecision("LX0609-032", "matched", "surgery_safecheck_record", "empty", "ready", (GateFactRef("b" * 64, "current_visit_surgery_confirmed", "surgery_record"),), ("LX0609-030",), ("informational_parent_only",))
    gate = GateReport("gate-v1", "policy-v1", "visit-prog-001", "a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, ("LX0609-032",), (decision,), CREATED)
    report = build_luxian_0609_programmatic_findings_shadow(gate_report=gate, finding_schema_version="finding-v1", finding_policy_version="policy-v1", created_at=CREATED)
    assert report.findings[0].finding_kind is FindingKind.REQUIRED_DOCUMENT_MISSING
    assert report.findings[0].parent_rule_ids == ("LX0609-030",)
