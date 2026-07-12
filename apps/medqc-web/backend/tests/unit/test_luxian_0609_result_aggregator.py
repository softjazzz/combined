from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from app.services.luxian_0609.programmatic_rules import FindingKind, ProgrammaticFinding, ProgrammaticFindingReport
from app.services.luxian_0609.result_aggregator import FinalState, AggregatedRuleResult, aggregate_luxian_0609_programmatic_findings_shadow

CREATED = "2026-07-12T14:00:00+08:00"
EXPECTED = {FindingKind.REQUIREMENT_SATISFIED: FinalState.COMPLIANT, FindingKind.REQUIRED_DOCUMENT_MISSING: FinalState.NON_COMPLIANT, FindingKind.TRIGGER_ABSENT: FinalState.NOT_APPLICABLE, FindingKind.SOURCE_INCOMPLETE: FinalState.DATA_GAP, FindingKind.TECHNICAL_FAILURE: FinalState.TECHNICAL_ERROR, FindingKind.EVIDENCE_CONFLICT: FinalState.EVALUATION_UNKNOWN}


def _report(kind):
    finding = ProgrammaticFinding("LX0609-030", kind, "surgery_record", (), (), ())
    return ProgrammaticFindingReport("finding-v1", "policy-v1", "visit-prog-001", "a" * 64, (finding,), CREATED)


@pytest.mark.parametrize("kind", list(EXPECTED))
def test_all_findings_have_exact_aggregator_owned_final_state(kind):
    result = aggregate_luxian_0609_programmatic_findings_shadow(finding_report=_report(kind), aggregation_schema_version="aggregation-v1", aggregation_policy_version="policy-v1", created_at=CREATED)
    assert result.results[0].final_state is EXPECTED[kind]
    assert result.summary_dict()["shadow_only"] is True and result.summary_dict()["release_eligible"] is False
    assert "ai_suggested" not in result.canonical_json()


def test_032_is_independent_and_zero_is_valid_safe_only():
    finding = ProgrammaticFinding("LX0609-032", FindingKind.REQUIREMENT_SATISFIED, "surgery_safecheck_record", ("LX0609-030",), ("informational_parent_only",), ())
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
