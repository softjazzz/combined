from __future__ import annotations

import pytest

from app.services.luxian_0916.admission_rules import execute_admission_rules


_RULE_IDS = tuple(f"LX0916-{number:03d}" for number in range(1, 10))


def _record(**overrides: object) -> dict[str, object]:
    return {
        "document_id": "admission-001",
        "content": "完整入院记录正文",
        **overrides,
    }


def _facts(**rule_states: str) -> dict[str, dict[str, str]]:
    return {
        rule_id: {"state": state}
        for rule_id, state in rule_states.items()
    }


def _context(
    record: dict[str, object] | None, facts: dict[str, dict[str, str]] | None = None
) -> dict[str, object]:
    context: dict[str, object] = {"documents": {}}
    if record is not None:
        context["documents"] = {"admission_record": record}
    if facts is not None:
        context["semantic_facts"] = facts
    return context


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_admission_rule_reports_compliant_from_explicit_complete_fact(rule_id: str) -> None:
    if rule_id == "LX0916-001":
        record = _record(patient={"prior_admission_count": 2})
        facts = _facts(**{rule_id: "complete"})
    elif rule_id == "LX0916-002":
        record = _record(
            patient={"civil_capacity": "limited"}, history_narrator="guardian"
        )
        facts = None
    elif rule_id == "LX0916-008":
        record = _record(patient={"age_years": 7})
        facts = _facts(**{rule_id: "complete"})
    else:
        record = _record()
        facts = _facts(**{rule_id: "complete"})

    result = execute_admission_rules(_context(record, facts), rule_ids=(rule_id,))[0]

    assert result.status == "compliant"
    assert result.reason_code == "requirement_satisfied"
    assert result.document_anchors[0]["document_id"] == "admission-001"


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_admission_rule_reports_explicit_defect(rule_id: str) -> None:
    if rule_id == "LX0916-001":
        record = _record(patient={"prior_admission_count": 2})
        facts = _facts(**{rule_id: "incomplete"})
    elif rule_id == "LX0916-002":
        record = _record(
            patient={"civil_capacity": "limited"},
            history_narrator="patient",
        )
        facts = None
    elif rule_id == "LX0916-008":
        record = _record(patient={"age_years": 7})
        facts = _facts(**{rule_id: "incomplete"})
    else:
        record = _record()
        facts = _facts(**{rule_id: "incomplete"})

    result = execute_admission_rules(_context(record, facts), rule_ids=(rule_id,))[0]

    assert result.status == "non_compliant"
    assert result.reason_code == "requirement_violated"
    assert result.evidence
    assert result.findings


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_admission_rule_boundary_is_not_misclassified(rule_id: str) -> None:
    if rule_id == "LX0916-001":
        record = _record(patient={"prior_admission_count": 1})
        facts = None
        expected_status = "not_applicable"
    elif rule_id == "LX0916-002":
        record = _record(
            patient={"civil_capacity": "limited"},
            history_narrator="guardian",
        )
        facts = None
        expected_status = "compliant"
    elif rule_id == "LX0916-008":
        record = _record(patient={"age_years": 18})
        facts = None
        expected_status = "not_applicable"
    else:
        record = _record()
        facts = _facts(**{rule_id: "not_applicable"})
        expected_status = "not_applicable"

    result = execute_admission_rules(_context(record, facts), rule_ids=(rule_id,))[0]

    assert result.status == expected_status


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_admission_rule_reports_data_gap_without_authoritative_fact(rule_id: str) -> None:
    if rule_id == "LX0916-001":
        record = _record(patient={"prior_admission_count": 2})
        facts = None
    elif rule_id == "LX0916-002":
        record = _record(patient={"civil_capacity": "limited"})
        facts = None
    elif rule_id == "LX0916-008":
        record = _record(patient={"age_years": 7})
        facts = None
    else:
        record = _record()
        facts = None

    result = execute_admission_rules(_context(record, facts), rule_ids=(rule_id,))[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code in {"semantic_fact_unavailable", "required_field_missing"}


def test_absent_target_document_is_data_gap_without_a_mature_window_fact() -> None:
    result = execute_admission_rules(_context(None), rule_ids=("LX0916-003",))[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "admission_document_source_unavailable"


def test_absent_target_document_is_not_executed_at_an_immature_window() -> None:
    context = _context(None)
    context["admission_evaluation_window_mature"] = False
    result = execute_admission_rules(context, rule_ids=("LX0916-003",))[0]

    assert result.status == "not_executed"
    assert result.reason_code == "evaluation_window_not_mature"


def test_result_contract_serializes_only_customer_deliverable_statuses() -> None:
    result = execute_admission_rules(
        _context(_record(), _facts(**{"LX0916-003": "complete"})),
        rule_ids=("LX0916-003",),
    )[0]

    assert result.to_dict()["status"] == "compliant"
    assert set(result.to_dict()) == {
        "rule_id",
        "status",
        "reason_code",
        "findings",
        "evidence",
        "suggestion",
        "document_anchors",
        "diagnostics",
    }


@pytest.mark.parametrize("rule_id", ("LX0916-001", "LX0916-002", "LX0916-008"))
def test_admission_applicability_can_fall_back_to_controlled_semantic_fact(
    rule_id: str,
) -> None:
    result = execute_admission_rules(
        _context(_record(), _facts(**{rule_id: "complete"})),
        rule_ids=(rule_id,),
    )[0]

    assert result.status == "compliant"
    assert result.reason_code == "requirement_satisfied"
