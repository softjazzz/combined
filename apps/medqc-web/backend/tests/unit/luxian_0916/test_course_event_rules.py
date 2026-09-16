from __future__ import annotations

import pytest

from app.services.luxian_0916.course_event_rules import execute_course_event_rules


_EVENT_KEY_BY_RULE = {
    "LX0916-015": "disease_changes",
    "LX0916-016": "disease_changes",
    "LX0916-017": "exam_or_medication_orders",
    "LX0916-018": "critical_values",
    "LX0916-019": "important_operations",
    "LX0916-020": "diagnosis_changes",
}
_DOCUMENTATION_BY_RULE = {
    "LX0916-015": {"record_present": True, "complete": True},
    "LX0916-016": {"analysis_recorded": True, "specific_management_recorded": True},
    "LX0916-018": {"report_recorded": True, "disposition_recorded": True},
    "LX0916-019": {"record_present": True, "complete": True},
    "LX0916-020": {"reason_recorded": True, "basis_recorded": True},
}


def _run(rule_id: str, context: dict) -> object:
    results = execute_course_event_rules(context, [rule_id])
    assert len(results) == 1
    return results[0]


def _event(rule_id: str, **overrides: object) -> dict:
    event = {
        "event_id": f"event-{rule_id[-3:]}",
        "event_type": _EVENT_KEY_BY_RULE[rule_id],
        "document_id": f"document-{rule_id[-3:]}",
        "source_type": "daily_course_record",
        "trigger_confirmed": True,
        "evaluation_window_mature": True,
        "documentation": _DOCUMENTATION_BY_RULE.get(rule_id, {}),
        "appropriateness": "reasonable",
    }
    event.update(overrides)
    return event


def _context(rule_id: str, **event_overrides: object) -> dict:
    return {"event_facts": {_EVENT_KEY_BY_RULE[rule_id]: [_event(rule_id, **event_overrides)]}}


@pytest.mark.parametrize(
    ("rule_id", "event_overrides", "expected_reason"),
    [
        ("LX0916-015", {"documentation": {"record_present": False, "complete": True}}, "disease_change_documentation_incomplete"),
        ("LX0916-016", {"documentation": {"analysis_recorded": False, "specific_management_recorded": True}}, "disease_change_analysis_or_management_missing"),
        ("LX0916-017", {"appropriateness": "unreasonable"}, "exam_or_medication_unreasonable"),
        ("LX0916-018", {"documentation": {"report_recorded": True, "disposition_recorded": False}}, "critical_value_documentation_incomplete"),
        ("LX0916-019", {"documentation": {"record_present": False, "complete": True}}, "important_operation_documentation_incomplete"),
        ("LX0916-020", {"documentation": {"reason_recorded": True, "basis_recorded": False}}, "diagnosis_change_reason_or_basis_missing"),
    ],
)
def test_event_rules_report_confirmed_defects(rule_id, event_overrides, expected_reason):
    result = _run(rule_id, _context(rule_id, **event_overrides))

    assert result.status == "non_compliant"
    assert result.reason_code == expected_reason
    assert result.document_anchors
    assert result.document_anchors[0]["document_type"] == "daily_course_record"
    assert result.document_anchors[0]["document_id"] == f"document-{rule_id[-3:]}"


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(15, 21)])
def test_event_rules_report_compliance_with_confirmed_complete_facts(rule_id):
    result = _run(rule_id, _context(rule_id))

    assert result.status == "compliant"


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(15, 21)])
def test_event_rules_wait_for_mature_evaluation_window(rule_id):
    result = _run(rule_id, _context(rule_id, evaluation_window_mature=False))

    assert result.status == "not_executed"
    assert result.reason_code == "evaluation_window_not_mature"


@pytest.mark.parametrize(
    ("source_state", "expected_reason", "expected_findings"),
    (
        (
            "selected",
            "event_fact_unavailable",
            "该规则相关资料已纳入本次受控核对，但未形成可验证的事件事实，无法确认是否触发病程记录检查。",
        ),
        (
            "not_selected",
            "event_source_unavailable",
            "本次受控输入未选出可读取的目标文书，无法确认是否触发病程记录检查。",
        ),
        (
            None,
            "event_source_unverified",
            "未验证本次受控输入是否选出该规则的目标文书，无法确认是否触发病程记录检查。",
        ),
    ),
)
def test_event_rules_describe_missing_event_facts_by_source_state(
    source_state, expected_reason, expected_findings
):
    rule_id = "LX0916-015"
    context = {"event_facts": {}}
    if source_state is not None:
        context["event_source_state_by_rule"] = {rule_id: source_state}

    result = _run(rule_id, context)

    assert result.status == "data_quality_gap"
    assert result.reason_code == expected_reason
    assert result.findings == expected_findings
    assert result.diagnostics["event_source_state"] == source_state


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(15, 21)])
def test_event_rules_are_not_applicable_without_confirmed_trigger(rule_id):
    result = _run(rule_id, {"event_facts": {_EVENT_KEY_BY_RULE[rule_id]: []}})

    assert result.status == "not_applicable"
    assert result.reason_code == "trigger_event_absent"
