from __future__ import annotations

import pytest

from app.services.luxian_0916.admission_rules import execute_admission_rules
from app.services.luxian_0916.contracts import Luxian0916RuleResult


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
        "decision_facts",
    }


@pytest.mark.parametrize(
    ("rule_id", "record", "facts", "expected"),
    (
        (
            "LX0916-001",
            _record(patient={"prior_admission_count": 1}),
            None,
            {"prior_admission_count": 1},
        ),
        (
            "LX0916-002",
            _record(patient={"civil_capacity": "limited", "age_years": 13}, history_narrator="guardian"),
            None,
            {"civil_capacity": "limited", "age_years": 13, "history_narrator": "guardian"},
        ),
        (
            "LX0916-008",
            _record(patient={"age_years": 7}),
            _facts(**{"LX0916-008": "complete"}),
            {"age_years": 7, "semantic_state": "complete"},
        ),
    ),
)
def test_admission_rule_persists_only_minimal_decision_facts(
    rule_id: str,
    record: dict[str, object],
    facts: dict[str, dict[str, str]] | None,
    expected: dict[str, object],
) -> None:
    result = execute_admission_rules(_context(record, facts), rule_ids=(rule_id,))[0]

    assert result.decision_facts
    assert result.decision_facts["source_type"] == "admission_record"
    assert result.decision_facts["document_id"] == "admission-001"
    assert expected.items() <= result.decision_facts.items()
    assert "content" not in result.decision_facts
    assert "完整入院记录正文" not in str(result.decision_facts)


def test_admission_early_result_keeps_a_nonempty_decision_snapshot() -> None:
    result = execute_admission_rules(_context(None), rule_ids=("LX0916-003",))[0]

    assert result.decision_facts == {
        "source_type": "admission_record",
        "target_document_available": False,
    }


def test_result_contract_rejects_raw_text_keys_but_keeps_controlled_context_keys() -> None:
    result = Luxian0916RuleResult(
        rule_id="LX0916-001",
        status="compliant",
        reason_code="requirement_satisfied",
        findings="ok",
        decision_facts={"context_available": True, "source_type": "admission_record"},
    )

    assert result.decision_facts["context_available"] is True
    with pytest.raises(ValueError, match="forbidden decision_facts key"):
        Luxian0916RuleResult(
            rule_id="LX0916-001",
            status="compliant",
            reason_code="requirement_satisfied",
            findings="ok",
            decision_facts={"content": "病历正文"},
        )


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


@pytest.mark.parametrize(
    ("age_years", "history_narrator", "expected_status"),
    (
        (13, "guardian", "compliant"),
        (13, "patient", "non_compliant"),
        (4, "guardian", "compliant"),
    ),
)
def test_002_treats_children_under_16_as_non_full_capacity_without_semantic_override(
    age_years: int, history_narrator: str, expected_status: str
) -> None:
    result = execute_admission_rules(
        _context(
            _record(patient={"age_years": age_years}, history_narrator=history_narrator),
        ),
        rule_ids=("LX0916-002",),
    )[0]

    assert result.status == expected_status


@pytest.mark.parametrize("age_years", (16, 17))
def test_002_keeps_16_to_17_year_old_without_explicit_capacity_as_data_gap(
    age_years: int,
) -> None:
    result = execute_admission_rules(
        _context(_record(patient={"age_years": age_years}, history_narrator="guardian")),
        rule_ids=("LX0916-002",),
    )[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "civil_capacity_fact_unavailable"


@pytest.mark.parametrize("age_years", (70, 76))
def test_008_makes_adults_not_applicable_even_when_semantic_fact_is_incomplete(
    age_years: int,
) -> None:
    result = execute_admission_rules(
        _context(
            _record(patient={"age_years": age_years}),
            _facts(**{"LX0916-008": "incomplete"}),
        ),
        rule_ids=("LX0916-008",),
    )[0]

    assert result.status == "not_applicable"
    assert result.reason_code == "eligibility_not_met"


@pytest.mark.parametrize("age_years", (4, 13))
def test_008_rejects_semantic_not_applicable_for_children(age_years: int) -> None:
    result = execute_admission_rules(
        _context(
            _record(patient={"age_years": age_years}),
            _facts(**{"LX0916-008": "not_applicable"}),
        ),
        rule_ids=("LX0916-008",),
    )[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "semantic_fact_conflicts_with_age"
