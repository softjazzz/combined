from __future__ import annotations

import pytest

from app.services.luxian_0916.first_course_rules import execute_first_course_rules


def _run(rule_id: str, context: dict) -> object:
    results = execute_first_course_rules(context, [rule_id])
    assert len(results) == 1
    return results[0]


def _document(**overrides: object) -> dict:
    row = {
        "document_id": "fc-1",
        "case_characteristic": "患者发热三日，查体及检查提示肺部感染。",
        "diagnose_based_on": "发热、咳嗽及胸片结果支持。",
        "differential_diagnosis": "与病毒性肺炎鉴别。",
        "treatment_plan": "抗感染治疗并复查血常规。",
        "semantic_facts": {
            "case_characteristic_quality": "adequate",
            "diagnosis_basis_quality": "adequate",
            "differential_diagnosis_quality": "adequate",
            "treatment_plan_quality": "adequate",
        },
    }
    row.update(overrides)
    return row


def _context(**row_overrides: object) -> dict:
    return {"documents": {"first_course_record": [_document(**row_overrides)]}}


def _context_without(*fields: str) -> dict:
    row = _document()
    for field in fields:
        del row[field]
    return {"documents": {"first_course_record": [row]}}


@pytest.mark.parametrize(
    ("rule_id", "row_overrides", "expected_status", "expected_reason"),
    [
        ("LX0916-010", {"case_characteristic": ""}, "non_compliant", "case_characteristic_missing"),
        ("LX0916-011", {"semantic_facts": {"case_characteristic_quality": "inadequate"}}, "non_compliant", "case_characteristic_inadequate"),
        ("LX0916-012", {"differential_diagnosis": ""}, "non_compliant", "first_course_required_section_missing"),
        ("LX0916-013", {"semantic_facts": {"diagnosis_basis_quality": "inadequate", "differential_diagnosis_quality": "adequate"}}, "non_compliant", "diagnostic_reasoning_inadequate"),
        ("LX0916-014", {"semantic_facts": {"treatment_plan_quality": "inadequate"}}, "non_compliant", "treatment_plan_inadequate"),
    ],
)
def test_first_course_rules_report_confirmed_defects(rule_id, row_overrides, expected_status, expected_reason):
    result = _run(rule_id, _context(**row_overrides))

    assert result.status == expected_status
    assert result.reason_code == expected_reason
    assert result.rule_id == rule_id
    assert result.document_anchors


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(10, 15)])
def test_first_course_rules_report_compliance_with_required_facts(rule_id):
    result = _run(rule_id, _context())

    assert result.status == "compliant"
    assert result.rule_id == rule_id


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(10, 15)])
def test_first_course_rules_do_not_evaluate_before_document_window(rule_id):
    result = _run(
        rule_id,
        {
            "documents": {"first_course_record": []},
            "first_course_evaluation_window_mature": False,
        },
    )

    assert result.status == "not_executed"
    assert result.reason_code == "evaluation_window_not_mature"


@pytest.mark.parametrize(
    ("rule_id", "context"),
    [
        ("LX0916-010", _context_without("case_characteristic")),
        ("LX0916-011", _context(semantic_facts={})),
        ("LX0916-012", _context_without("diagnose_based_on")),
        ("LX0916-013", _context(semantic_facts={"diagnosis_basis_quality": "adequate"})),
        ("LX0916-014", _context(semantic_facts={})),
    ],
)
def test_first_course_rules_return_data_gap_when_required_facts_are_missing(rule_id, context):
    result = _run(rule_id, context)

    assert result.status == "data_quality_gap"
    assert result.reason_code in {"first_course_structured_field_missing", "semantic_fact_unavailable"}


def test_first_course_document_absence_after_window_is_not_misclassified_as_content_defect():
    result = _run(
        "LX0916-010",
        {
            "documents": {"first_course_record": []},
            "first_course_evaluation_window_mature": True,
        },
    )

    assert result.status == "not_applicable"
    assert result.reason_code == "first_course_document_not_formed"


def test_first_course_can_use_controlled_semantic_presence_when_raw_row_has_no_sections():
    context = {
        "documents": {"first_course_record": [{"document_id": "fc-semantic"}]},
        "semantic_facts": {
            "case_characteristic_present": True,
            "diagnosis_basis_present": True,
            "differential_diagnosis_present": True,
            "treatment_plan_present": True,
            "case_characteristic_quality": "adequate",
            "diagnosis_basis_quality": "adequate",
            "differential_diagnosis_quality": "adequate",
            "treatment_plan_quality": "adequate",
        },
    }

    results = execute_first_course_rules(context)

    assert [result.status for result in results] == ["compliant"] * 5


@pytest.mark.parametrize(
    ("rule_id", "context", "expected_fields", "expected_quality"),
    (
        (
            "LX0916-010",
            _context(case_characteristic=""),
            {"case_characteristic": "empty"},
            None,
        ),
        (
            "LX0916-011",
            _context(semantic_facts={"case_characteristic_quality": "inadequate"}),
            {"case_characteristic": "present"},
            {"case_characteristic_quality": "inadequate"},
        ),
        (
            "LX0916-012",
            _context(differential_diagnosis=""),
            {
                "diagnose_based_on": "present",
                "differential_diagnosis": "empty",
                "treatment_plan": "present",
            },
            None,
        ),
        (
            "LX0916-013",
            _context(semantic_facts={"diagnosis_basis_quality": "inadequate", "differential_diagnosis_quality": "adequate"}),
            {"diagnose_based_on": "present", "differential_diagnosis": "present"},
            {"diagnosis_basis_quality": "inadequate", "differential_diagnosis_quality": "adequate"},
        ),
        (
            "LX0916-014",
            _context(semantic_facts={"treatment_plan_quality": "adequate"}),
            {"treatment_plan": "present"},
            {"treatment_plan_quality": "adequate"},
        ),
    ),
)
def test_first_course_rules_persist_structured_decision_facts(
    rule_id, context, expected_fields, expected_quality
):
    result = _run(rule_id, context)

    facts = result.decision_facts
    assert facts["source_type"] == "first_course_record"
    assert facts["document_id"] == "fc-1"
    assert facts["document_selected"] is True
    assert facts["candidate_document_count"] == 1
    assert facts["field_states"] == expected_fields
    if expected_quality is not None:
        assert facts["semantic_quality_states"] == expected_quality
    assert "content" not in facts
    assert "患者发热三日" not in str(facts)


def test_first_course_early_result_persists_window_and_source_facts():
    result = _run(
        "LX0916-010",
        {
            "documents": {"first_course_record": []},
            "first_course_evaluation_window_mature": False,
        },
    )

    assert result.decision_facts == {
        "source_type": "first_course_record",
        "target_document_available": False,
        "candidate_document_count": 0,
        "evaluation_window_mature": False,
    }
