from __future__ import annotations

import json

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
    assert result.decision_facts["event_key"] == _EVENT_KEY_BY_RULE[rule_id]
    assert result.decision_facts["source_state"] == "available"
    assert result.decision_facts["events"]
    if rule_id == "LX0916-017":
        assert result.decision_facts["events"][0]["appropriateness"] == "unreasonable"


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(15, 21)])
def test_event_rules_report_compliance_with_confirmed_complete_facts(rule_id):
    result = _run(rule_id, _context(rule_id))

    assert result.status == "compliant"


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(15, 21)])
def test_event_rules_wait_for_mature_evaluation_window(rule_id):
    result = _run(rule_id, _context(rule_id, evaluation_window_mature=False))

    assert result.status == "not_executed"
    assert result.reason_code == "evaluation_window_not_mature"


@pytest.mark.parametrize("other_maturity", [False, None])
@pytest.mark.parametrize(
    ("rule_id", "defect_documentation", "expected_reason"),
    (
        (
            "LX0916-015",
            {"record_present": False, "complete": True},
            "disease_change_documentation_incomplete",
        ),
        (
            "LX0916-016",
            {"analysis_recorded": False, "specific_management_recorded": True},
            "disease_change_analysis_or_management_missing",
        ),
    ),
)
def test_confirmed_mature_defect_is_not_hidden_by_later_immature_event(
    rule_id, defect_documentation, expected_reason, other_maturity
):
    first = _event(rule_id, event_id="mature-defect", document_id="D-defect", documentation=defect_documentation)
    second = _event(
        rule_id,
        event_id="immature",
        document_id="D-immature",
        evaluation_window_mature=other_maturity,
        documentation={},
    )
    context = {"event_facts": {"disease_changes": [first, second]}}

    result = _run(rule_id, context)

    assert result.status == "non_compliant"
    assert result.reason_code == expected_reason
    assert [anchor["document_id"] for anchor in result.document_anchors] == ["D-defect"]
    assert len(result.decision_facts["events"]) == 2


@pytest.mark.parametrize("rule_id", ("LX0916-015", "LX0916-016"))
@pytest.mark.parametrize("event_kind", ("none", "complete", "defect"))
def test_partial_course_coverage_preserves_only_confirmed_defects(rule_id, event_kind):
    key = _EVENT_KEY_BY_RULE[rule_id]
    events = []
    if event_kind != "none":
        documentation = dict(_DOCUMENTATION_BY_RULE[rule_id])
        if event_kind == "defect":
            first_field = next(iter(documentation))
            documentation[first_field] = False
        events.append(_event(rule_id, document_id="selected-document", documentation=documentation))
    result = _run(
        rule_id,
        {
            "event_facts": {key: events},
            "event_source_state_by_rule": {rule_id: "partial"},
        },
    )

    if event_kind == "defect":
        assert result.status == "non_compliant"
        assert [anchor["document_id"] for anchor in result.document_anchors] == ["selected-document"]
    else:
        assert result.status == "data_quality_gap"
        assert result.reason_code == "event_source_partial"
    assert result.decision_facts["source_state"] == "partial"


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
    assert result.decision_facts == {
        "event_key": _EVENT_KEY_BY_RULE[rule_id],
        "source_state": source_state or "unverified",
        "events": [],
    }


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(15, 21)])
def test_event_rules_are_not_applicable_without_confirmed_trigger(rule_id):
    result = _run(rule_id, {"event_facts": {_EVENT_KEY_BY_RULE[rule_id]: []}})

    assert result.status == "not_applicable"
    assert result.reason_code == "trigger_event_absent"
    assert result.decision_facts == {
        "event_key": _EVENT_KEY_BY_RULE[rule_id],
        "source_state": "available",
        "events": [],
    }


def test_event_rules_persist_only_controlled_event_facts_for_final_decision():
    rule_id = "LX0916-015"
    result = _run(
        rule_id,
        _context(
            rule_id,
            documentation={"record_present": False, "complete": True, "note": "不应持久化"},
            content="病历正文不应持久化",
            raw_output="模型原始输出不应持久化",
        ),
    )

    assert result.status == "non_compliant"
    assert result.decision_facts == {
        "event_key": "disease_changes",
        "source_state": "available",
        "events": [
            {
                "event_type": "disease_changes",
                "event_id": "event-015",
                "document_id": "document-015",
                "source_type": "daily_course_record",
                "trigger_confirmed": True,
                "evaluation_window_mature": True,
                "documentation": {"record_present": False, "complete": True},
            }
        ],
    }
    serialized = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "病历正文不应持久化" not in serialized
    assert "模型原始输出不应持久化" not in serialized
    assert "不应持久化" not in serialized


def test_event_rules_persist_trigger_facts_for_early_data_gap():
    rule_id = "LX0916-018"
    result = _run(rule_id, _context(rule_id, trigger_confirmed=None))

    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_trigger_unavailable"
    assert result.decision_facts["event_key"] == "critical_values"
    assert result.decision_facts["source_state"] == "available"
    assert result.decision_facts["events"] == [
        {
            "event_type": "critical_values",
            "event_id": "event-018",
            "document_id": "document-018",
            "source_type": "daily_course_record",
            "trigger_confirmed": None,
            "evaluation_window_mature": True,
            "documentation": {"report_recorded": True, "disposition_recorded": True},
        }
    ]


def test_event_rules_omit_optional_empty_identifiers_from_decision_facts():
    rule_id = "LX0916-015"
    result = _run(
        rule_id,
        _context(rule_id, event_id="", document_id=None, source_type=""),
    )

    event = result.decision_facts["events"][0]
    assert "event_id" not in event
    assert "document_id" not in event
    assert "source_type" not in event
