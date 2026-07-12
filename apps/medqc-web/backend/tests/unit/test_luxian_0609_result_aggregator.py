from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.services.luxian_0609.programmatic_rules import FindingKind, ProgrammaticFinding, ProgrammaticFindingReport
from app.services.luxian_0609.result_aggregator import FinalState, AggregatedRuleResult, aggregate_luxian_0609_programmatic_findings_shadow

CREATED = "2026-07-12T14:00:00+08:00"
EXPECTED = {FindingKind.REQUIREMENT_SATISFIED: FinalState.COMPLIANT, FindingKind.REQUIRED_DOCUMENT_MISSING: FinalState.NON_COMPLIANT, FindingKind.TRIGGER_ABSENT: FinalState.NOT_APPLICABLE, FindingKind.SOURCE_INCOMPLETE: FinalState.DATA_GAP, FindingKind.TECHNICAL_FAILURE: FinalState.TECHNICAL_ERROR, FindingKind.EVIDENCE_CONFLICT: FinalState.EVALUATION_UNKNOWN}


def _report(kind):
    trigger = "matched" if kind in (FindingKind.REQUIREMENT_SATISFIED, FindingKind.REQUIRED_DOCUMENT_MISSING) else ("absent_complete" if kind is FindingKind.TRIGGER_ABSENT else ("semantic_conflict" if kind is FindingKind.EVIDENCE_CONFLICT else ("source_unavailable" if kind is FindingKind.SOURCE_INCOMPLETE else "source_error")))
    target = "present" if kind is FindingKind.REQUIREMENT_SATISFIED else ("empty" if kind is FindingKind.REQUIRED_DOCUMENT_MISSING else None)
    readiness = "ready" if target else ("not_triggered" if trigger == "absent_complete" else "blocked")
    facts = ("a" * 64,) if target else ()
    finding = ProgrammaticFinding("LX0609-030", kind, "surgery_record", trigger, target, readiness, (), (), facts)
    return ProgrammaticFindingReport("finding-v1", "policy-v1", "visit-prog-001", "a" * 64, (finding,), CREATED)


@pytest.mark.parametrize("kind", list(EXPECTED))
def test_all_findings_have_exact_aggregator_owned_final_state(kind):
    result = aggregate_luxian_0609_programmatic_findings_shadow(finding_report=_report(kind), aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert result.results[0].final_state is EXPECTED[kind]
    assert result.summary_dict()["shadow_only"] is True and result.summary_dict()["release_eligible"] is False
    assert "ai_suggested" not in result.canonical_json()


def test_032_is_independent_and_zero_is_valid_safe_only():
    finding = ProgrammaticFinding("LX0609-032", FindingKind.REQUIREMENT_SATISFIED, "surgery_safecheck_record", "matched", "present", "ready", ("LX0609-030",), ("informational_parent_only",), ("a" * 64,))
    report = ProgrammaticFindingReport("finding-v1", "policy-v1", "visit-prog-001", "a" * 64, (finding,), CREATED)
    result = aggregate_luxian_0609_programmatic_findings_shadow(finding_report=report, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert result.results[0].final_state is FinalState.COMPLIANT
    zero = ProgrammaticFindingReport("finding-v1", "policy-v1", "visit-prog-001", "a" * 64, (), CREATED)
    empty = aggregate_luxian_0609_programmatic_findings_shadow(finding_report=zero, aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert empty.results == () and empty.fingerprint() == replace(empty, created_at="2026-07-13T14:00:00+08:00").fingerprint()
    assert not any(name in vars(empty) for name in ("finding_report", "gate", "fact", "manifest", "bundle"))
    assert "quote" not in repr(empty) + str(asdict(empty)) + empty.canonical_json()


def test_constructor_mapping_and_real_type_boundary_fail_closed():
    with pytest.raises(ValueError): AggregatedRuleResult("LX0609-030", FindingKind.REQUIRED_DOCUMENT_MISSING, FinalState.COMPLIANT)
    with pytest.raises(TypeError): aggregate_luxian_0609_programmatic_findings_shadow(finding_report=object(), aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)


@pytest.mark.parametrize("marker", ["Bearer_secret", "sk-secret", "full_text", "13800138000", "prompt_text"])
def test_aggregation_metadata_and_enum_errors_are_private(marker):
    with pytest.raises(ValueError) as error:
        AggregatedRuleResult("LX0609-030", marker, "compliant")
    assert marker not in str(error.value)
    report = _report(FindingKind.TRIGGER_ABSENT)
    with pytest.raises(ValueError) as metadata_error:
        aggregate_luxian_0609_programmatic_findings_shadow(finding_report=report, aggregation_schema_version=marker, aggregation_policy_version="policy-v1", created_at=CREATED)
    assert marker not in str(metadata_error.value)
