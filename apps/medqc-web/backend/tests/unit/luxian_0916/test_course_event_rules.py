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
    "LX0916-018": {"report_recorded": True, "disposition_recorded": True},
    "LX0916-019": {"record_present": True, "complete": True},
    "LX0916-020": {"reason_recorded": True, "basis_recorded": True},
}
_STAGE2_FACT_KINDS_BY_RULE = {
    "LX0916-015": ("record_present", "time_recorded", "content_recorded"),
    "LX0916-016": ("analysis_present", "management_present"),
    "LX0916-018": ("report_recorded", "disposition_recorded"),
}


def _run(rule_id: str, context: dict) -> object:
    results = execute_course_event_rules(context, [rule_id])
    assert len(results) == 1
    return results[0]


def _stage2_fact(
    event_id: str,
    fact_kind: str,
    state: str = "present",
    *,
    document_id: str = "COURSE-1",
) -> dict:
    source_type = "daily_course_record" if state == "present" else None
    coordinate_document_id = document_id if state == "present" else None
    clause_id = f"{document_id}:{fact_kind}" if state == "present" else None
    return {
        "fact_kind": fact_kind,
        "state": state,
        "event_id": event_id,
        "source_type": source_type,
        "document_id": coordinate_document_id,
        "clause_id": clause_id,
    }


def _stage2_facts(
    event_id: str,
    *,
    states: dict[str, str] | None = None,
) -> list[dict]:
    states = states or {}
    return [
        _stage2_fact(event_id, fact_kind, states.get(fact_kind, "present"))
        for fact_kinds in _STAGE2_FACT_KINDS_BY_RULE.values()
        for fact_kind in fact_kinds
    ]


def _event(rule_id: str, **overrides: object) -> dict:
    event_id = f"event-{rule_id[-3:]}"
    event = {
        "event_id": event_id,
        "event_type": _EVENT_KEY_BY_RULE[rule_id],
        "document_id": f"document-{rule_id[-3:]}",
        "source_type": "daily_course_record",
        "trigger_confirmed": True,
        "evaluation_window_mature": True,
        "documentation": _DOCUMENTATION_BY_RULE.get(rule_id, {}),
        "appropriateness": "reasonable",
    }
    if rule_id in _STAGE2_FACT_KINDS_BY_RULE:
        event.update(
            {
                "event_source_type": "inpat_nondrug_order",
                "event_source_id": f"ORDER-{rule_id[-3:]}",
                "event_time": "2026-09-16 08:00:00",
                "stage2_state_by_rule": {
                    "LX0916-015": "ready",
                    "LX0916-016": "ready",
                    "LX0916-018": "ready",
                },
                "stage2_facts": _stage2_facts(event_id),
            }
        )
    event.update(overrides)
    return event


def _context(rule_id: str, **event_overrides: object) -> dict:
    return {
        "event_facts": {
            _EVENT_KEY_BY_RULE[rule_id]: [_event(rule_id, **event_overrides)]
        },
        "event_source_state_by_rule": {
            rule_id: (
                "critical_value_source_complete"
                if rule_id == "LX0916-018"
                else "selected"
            )
        },
    }


@pytest.mark.parametrize(
    ("fact_kind", "rule_id", "expected_reason"),
    [
        (
            "record_present",
            "LX0916-015",
            "disease_change_documentation_incomplete",
        ),
        (
            "time_recorded",
            "LX0916-015",
            "disease_change_documentation_incomplete",
        ),
        (
            "content_recorded",
            "LX0916-015",
            "disease_change_documentation_incomplete",
        ),
        (
            "analysis_present",
            "LX0916-016",
            "disease_change_analysis_or_management_missing",
        ),
        (
            "management_present",
            "LX0916-016",
            "disease_change_analysis_or_management_missing",
        ),
    ],
)
def test_disease_change_rules_report_each_confirmed_stage2_defect(
    fact_kind, rule_id, expected_reason
):
    event_id = f"event-{rule_id[-3:]}"
    result = _run(
        rule_id,
        _context(
            rule_id,
            stage2_facts=_stage2_facts(event_id, states={fact_kind: "absent"}),
        ),
    )

    assert result.status == "non_compliant"
    assert result.reason_code == expected_reason
    assert result.diagnostics["failed_facts"] == [fact_kind]
    assert result.document_anchors == (
        {
            "event_type": "disease_changes",
            "event_id": event_id,
            "document_type": "daily_course_record",
            "document_id": f"document-{rule_id[-3:]}",
            "fields": [fact_kind],
            "event_source_type": "inpat_nondrug_order",
            "event_source_id": f"ORDER-{rule_id[-3:]}",
            "event_time": "2026-09-16 08:00:00",
        },
    )


@pytest.mark.parametrize(
    ("rule_id", "event_overrides", "expected_reason"),
    [
        (
            "LX0916-017",
            {"appropriateness": "unreasonable"},
            "exam_or_medication_unreasonable",
        ),
        (
            "LX0916-018",
            {
                "stage2_facts": _stage2_facts(
                    "event-018", states={"disposition_recorded": "absent"}
                ),
            },
            "critical_value_documentation_incomplete",
        ),
        (
            "LX0916-019",
            {"documentation": {"record_present": False, "complete": True}},
            "important_operation_documentation_incomplete",
        ),
        (
            "LX0916-020",
            {"documentation": {"reason_recorded": True, "basis_recorded": False}},
            "diagnosis_change_reason_or_basis_missing",
        ),
    ],
)
def test_existing_event_rules_report_confirmed_defects(
    rule_id, event_overrides, expected_reason
):
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


@pytest.mark.parametrize(
    ("rule_id", "event_overrides", "expected_reason"),
    [
        (
            "LX0916-017",
            {"appropriateness": "unreasonable"},
            "exam_or_medication_unreasonable",
        ),
        (
            "LX0916-018",
            {
                "stage2_facts": _stage2_facts(
                    "event-018", states={"report_recorded": "absent"}
                ),
            },
            "critical_value_documentation_incomplete",
        ),
        (
            "LX0916-019",
            {"documentation": {"record_present": True, "complete": False}},
            "important_operation_documentation_incomplete",
        ),
        (
            "LX0916-020",
            {"documentation": {"reason_recorded": False, "basis_recorded": True}},
            "diagnosis_change_reason_or_basis_missing",
        ),
    ],
)
def test_existing_event_rules_preserve_confirmed_defects_with_partial_coverage(
    rule_id, event_overrides, expected_reason
):
    context = _context(rule_id, **event_overrides)
    context["event_source_state_by_rule"] = {rule_id: "partial"}

    result = _run(rule_id, context)

    assert result.status == "non_compliant"
    assert result.reason_code == expected_reason
    assert result.decision_facts["source_state"] == "partial"


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(17, 21)])
def test_existing_event_rules_do_not_report_compliant_from_partial_coverage(rule_id):
    context = _context(rule_id)
    context["event_source_state_by_rule"] = {rule_id: "partial"}

    result = _run(rule_id, context)

    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_source_partial"
    assert result.decision_facts["source_state"] == "partial"


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(15, 21)])
def test_event_rules_report_compliance_with_confirmed_complete_facts(rule_id):
    result = _run(rule_id, _context(rule_id))

    assert result.status == "compliant"


@pytest.mark.parametrize("rule_id", ("LX0916-017", "LX0916-019", "LX0916-020"))
def test_existing_event_rules_wait_for_mature_evaluation_window(rule_id):
    result = _run(rule_id, _context(rule_id, evaluation_window_mature=False))

    assert result.status == "not_executed"
    assert result.reason_code == "evaluation_window_not_mature"


@pytest.mark.parametrize(
    ("states", "expected_status", "expected_reason"),
    (
        ({}, "compliant", "critical_value_documentation_complete"),
        (
            {"disposition_recorded": "absent"},
            "non_compliant",
            "critical_value_documentation_incomplete",
        ),
    ),
)
def test_critical_value_rule_delivers_running_results_without_maturity_wait(
    states, expected_status, expected_reason
):
    result = _run(
        "LX0916-018",
        _context(
            "LX0916-018",
            evaluation_window_mature=False,
            stage2_facts=_stage2_facts("event-018", states=states),
        ),
    )

    assert result.status == expected_status
    assert result.reason_code == expected_reason


@pytest.mark.parametrize("fact_kind", _STAGE2_FACT_KINDS_BY_RULE["LX0916-018"])
def test_critical_value_rule_reports_each_confirmed_stage2_defect(fact_kind):
    result = _run(
        "LX0916-018",
        _context(
            "LX0916-018",
            stage2_facts=_stage2_facts(
                "event-018", states={fact_kind: "absent"}
            ),
        ),
    )

    assert result.status == "non_compliant"
    assert result.reason_code == "critical_value_documentation_incomplete"
    assert result.diagnostics["failed_facts"] == [fact_kind]
    assert result.decision_facts["events"][0]["stage2_state"] == "ready"


def test_critical_value_rule_does_not_hide_a_defect_behind_an_unknown_event():
    defect = _event(
        "LX0916-018",
        event_id="critical-value:defect",
        stage2_facts=_stage2_facts(
            "critical-value:defect", states={"report_recorded": "absent"}
        ),
    )
    unknown = _event(
        "LX0916-018",
        event_id="critical-value:unknown",
        stage2_facts=_stage2_facts(
            "critical-value:unknown", states={"disposition_recorded": "unknown"}
        ),
    )

    result = _run(
        "LX0916-018",
        {
            "event_facts": {"critical_values": [defect, unknown]},
            "event_source_state_by_rule": {
                "LX0916-018": "critical_value_source_complete"
            },
        },
    )

    assert result.status == "non_compliant"
    assert result.reason_code == "critical_value_documentation_incomplete"
    assert [anchor["event_id"] for anchor in result.document_anchors] == [
        "critical-value:defect"
    ]


@pytest.mark.parametrize(
    ("source_state", "expected_reason"),
    (
        (
            "critical_value_source_unavailable",
            "critical_value_source_unavailable",
        ),
        ("critical_value_source_partial", "critical_value_source_partial"),
        ("critical_value_source_invalid", "critical_value_source_invalid"),
    ),
)
def test_critical_value_rule_rejects_incomplete_stage1_coverage(
    source_state, expected_reason
):
    result = _run(
        "LX0916-018",
        {
            "event_facts": {"critical_values": []},
            "event_source_state_by_rule": {"LX0916-018": source_state},
        },
    )

    assert result.status == "data_quality_gap"
    assert result.reason_code == expected_reason


def test_critical_value_rule_accepts_empty_complete_stage1_as_no_trigger():
    result = _run(
        "LX0916-018",
        {
            "event_facts": {"critical_values": []},
            "event_source_state_by_rule": {
                "LX0916-018": "critical_value_source_complete"
            },
        },
    )

    assert result.status == "not_applicable"
    assert result.reason_code == "trigger_event_absent"
    assert result.decision_facts["source_state"] == "available"


@pytest.mark.parametrize("rule_id", ("LX0916-015", "LX0916-016"))
def test_disease_change_rules_do_not_deliver_running_negative_results(rule_id):
    result = _run(
        rule_id,
        _context(
            rule_id,
            evaluation_window_mature=False,
            documentation={"record_present": False, "analysis_recorded": False},
        ),
    )

    assert result.status == "not_executed"
    assert result.reason_code == "evaluation_window_not_mature"


@pytest.mark.parametrize("rule_id", ("LX0916-015", "LX0916-016"))
def test_disease_change_rules_require_explicit_maturity_before_negative_delivery(
    rule_id,
):
    event_id = f"event-{rule_id[-3:]}"
    defect_kind = _STAGE2_FACT_KINDS_BY_RULE[rule_id][0]
    result = _run(
        rule_id,
        _context(
            rule_id,
            evaluation_window_mature=None,
            stage2_facts=_stage2_facts(
                event_id,
                states={defect_kind: "absent"},
            ),
        ),
    )

    assert result.status == "data_quality_gap"
    assert result.reason_code == "disease_change_stage2_fact_unavailable"


@pytest.mark.parametrize(
    ("rule_id", "defect_kind", "expected_reason"),
    (
        (
            "LX0916-015",
            "time_recorded",
            "disease_change_documentation_incomplete",
        ),
        (
            "LX0916-016",
            "management_present",
            "disease_change_analysis_or_management_missing",
        ),
    ),
)
def test_confirmed_stage2_defect_is_not_hidden_by_unknown_event(
    rule_id, defect_kind, expected_reason
):
    first_id = "confirmed-defect"
    first = _event(
        rule_id,
        event_id=first_id,
        stage2_facts=_stage2_facts(first_id, states={defect_kind: "absent"}),
    )
    second_id = "unknown-event"
    second = _event(
        rule_id,
        event_id=second_id,
        stage2_facts=_stage2_facts(second_id, states={defect_kind: "unknown"}),
    )

    result = _run(rule_id, {"event_facts": {"disease_changes": [first, second]}})

    assert result.status == "non_compliant"
    assert result.reason_code == expected_reason
    assert [anchor["event_id"] for anchor in result.document_anchors] == [first_id]
    assert len(result.decision_facts["events"]) == 2


@pytest.mark.parametrize("rule_id", ("LX0916-015", "LX0916-016"))
@pytest.mark.parametrize("event_kind", ("none", "complete", "defect"))
def test_partial_course_coverage_preserves_only_confirmed_defects(rule_id, event_kind):
    events = []
    if event_kind != "none":
        event_id = "selected-event"
        states = {}
        if event_kind == "defect":
            states[_STAGE2_FACT_KINDS_BY_RULE[rule_id][0]] = "absent"
        events.append(
            _event(
                rule_id,
                event_id=event_id,
                stage2_facts=_stage2_facts(event_id, states=states),
            )
        )
    result = _run(
        rule_id,
        {
            "event_facts": {"disease_changes": events},
            "event_source_state_by_rule": {rule_id: "partial"},
        },
    )

    if event_kind == "defect":
        assert result.status == "non_compliant"
        assert [anchor["event_id"] for anchor in result.document_anchors] == [
            "selected-event"
        ]
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
    result = _run(
        rule_id,
        {
            "event_facts": {_EVENT_KEY_BY_RULE[rule_id]: []},
            "event_source_state_by_rule": {rule_id: "selected"},
        },
    )

    assert result.status == "not_applicable"
    assert result.reason_code == "trigger_event_absent"
    assert result.decision_facts == {
        "event_key": _EVENT_KEY_BY_RULE[rule_id],
        "source_state": "available",
        "events": [],
    }


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(17, 21)])
def test_existing_event_rules_do_not_treat_empty_partial_extraction_as_no_trigger(
    rule_id,
):
    result = _run(
        rule_id,
        {
            "event_facts": {_EVENT_KEY_BY_RULE[rule_id]: []},
            "event_source_state_by_rule": {rule_id: "partial"},
        },
    )

    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_source_partial"
    assert result.decision_facts == {
        "event_key": _EVENT_KEY_BY_RULE[rule_id],
        "source_state": "partial",
        "events": [],
    }


@pytest.mark.parametrize("rule_id", [f"LX0916-0{number}" for number in range(17, 21)])
@pytest.mark.parametrize("event_shape", ("missing", "empty"))
@pytest.mark.parametrize(
    ("source_state", "expected_reason"),
    (
        ("not_selected", "event_source_unavailable"),
        (None, "event_source_unverified"),
    ),
)
def test_existing_event_rules_apply_the_same_coverage_gate_to_missing_and_empty_facts(
    rule_id, event_shape, source_state, expected_reason
):
    context = {
        "event_facts": (
            {} if event_shape == "missing" else {_EVENT_KEY_BY_RULE[rule_id]: []}
        )
    }
    if source_state is not None:
        context["event_source_state_by_rule"] = {rule_id: source_state}

    result = _run(rule_id, context)

    assert result.status == "data_quality_gap"
    assert result.reason_code == expected_reason


@pytest.mark.parametrize(
    "mutation",
    (
        "missing",
        "duplicate",
        "illegal_state",
        "wrong_event",
        "extra_field",
        "negative_coordinate",
        "present_coordinate_missing",
    ),
)
def test_stage2_invalid_fact_contract_is_a_data_quality_gap(mutation):
    rule_id = "LX0916-015"
    event_id = "event-015"
    facts = _stage2_facts(event_id)
    target_index = next(
        index
        for index, fact in enumerate(facts)
        if fact["fact_kind"] == "time_recorded"
    )
    if mutation == "missing":
        facts.pop(target_index)
    elif mutation == "duplicate":
        facts.append(dict(facts[target_index]))
    elif mutation == "illegal_state":
        facts[target_index]["state"] = "yes"
    elif mutation == "wrong_event":
        facts[target_index]["event_id"] = "another-event"
    elif mutation == "extra_field":
        facts[target_index]["quote"] = "不应由规则层接收的正文"
    elif mutation == "negative_coordinate":
        facts[target_index] = _stage2_fact(event_id, "time_recorded", "absent")
        facts[target_index]["document_id"] = "FAKE-COURSE"
    else:
        facts[target_index]["document_id"] = None

    result = _run(rule_id, _context(rule_id, stage2_facts=facts))

    assert result.status == "data_quality_gap"
    assert result.reason_code == "disease_change_stage2_fact_unavailable"


def test_stage2_non_ready_state_is_a_data_quality_gap():
    result = _run(
        "LX0916-015",
        _context(
            "LX0916-015",
            stage2_state_by_rule={
                "LX0916-015": "contract_invalid",
                "LX0916-016": "ready",
            },
        ),
    )

    assert result.status == "data_quality_gap"
    assert result.reason_code == "disease_change_stage2_fact_unavailable"


def test_stage2_non_ready_state_cannot_turn_stale_absent_fact_into_defect():
    event_id = "event-015"
    result = _run(
        "LX0916-015",
        _context(
            "LX0916-015",
            stage2_state_by_rule={
                "LX0916-015": "contract_invalid",
                "LX0916-016": "ready",
            },
            stage2_facts=_stage2_facts(event_id, states={"record_present": "absent"}),
        ),
    )

    assert result.status == "data_quality_gap"
    assert result.reason_code == "disease_change_stage2_fact_unavailable"


def test_stage2_failure_for_015_does_not_contaminate_016():
    event_id = "event-015"
    event = _event(
        "LX0916-015",
        stage2_state_by_rule={
            "LX0916-015": "contract_invalid",
            "LX0916-016": "ready",
        },
        stage2_facts=[
            fact
            for fact in _stage2_facts(event_id)
            if fact["fact_kind"] in _STAGE2_FACT_KINDS_BY_RULE["LX0916-016"]
        ],
    )

    results = {
        result.rule_id: result
        for result in execute_course_event_rules(
            {"event_facts": {"disease_changes": [event]}},
            ["LX0916-015", "LX0916-016"],
        )
    }

    assert results["LX0916-015"].status == "data_quality_gap"
    assert results["LX0916-016"].status == "compliant"


def test_plain_improvement_text_cannot_substitute_for_analysis_fact():
    event_id = "event-016"
    facts = [
        fact
        for fact in _stage2_facts(event_id)
        if fact["fact_kind"] != "analysis_present"
    ]
    result = _run(
        "LX0916-016",
        _context(
            "LX0916-016",
            stage2_facts=facts,
            content="患者病情好转",
            analysis="病情好转",
        ),
    )

    assert result.status == "data_quality_gap"
    assert result.reason_code == "disease_change_stage2_fact_unavailable"


def test_disease_change_decision_facts_and_anchors_keep_only_controlled_facts():
    rule_id = "LX0916-015"
    event_id = "event-015"
    facts = _stage2_facts(event_id, states={"record_present": "absent"})
    result = _run(
        rule_id,
        _context(
            rule_id,
            stage2_facts=facts,
            content="病历正文不应持久化",
            raw_output="模型原始输出不应持久化",
            prompt="提示词不应持久化",
        ),
    )

    assert result.status == "non_compliant"
    assert result.decision_facts == {
        "event_key": "disease_changes",
        "source_state": "available",
        "events": [
            {
                "trigger_confirmed": True,
                "event_type": "disease_changes",
                "event_id": event_id,
                "event_source_type": "inpat_nondrug_order",
                "event_source_id": "ORDER-015",
                "event_time": "2026-09-16 08:00:00",
                "stage2_state": "ready",
                "evaluation_window_mature": True,
                "stage2_facts": [
                    _stage2_fact(event_id, "record_present", "absent"),
                    _stage2_fact(event_id, "time_recorded"),
                    _stage2_fact(event_id, "content_recorded"),
                ],
            }
        ],
    }
    assert result.document_anchors == (
        {
            "event_type": "disease_changes",
            "event_id": event_id,
            "document_type": "daily_course_record",
            "document_id": "document-015",
            "fields": ["record_present"],
            "event_source_type": "inpat_nondrug_order",
            "event_source_id": "ORDER-015",
            "event_time": "2026-09-16 08:00:00",
        },
    )
    serialized = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "病历正文不应持久化" not in serialized
    assert "模型原始输出不应持久化" not in serialized
    assert "提示词不应持久化" not in serialized


def test_existing_rule_persists_trigger_facts_for_early_data_gap():
    rule_id = "LX0916-018"
    result = _run(rule_id, _context(rule_id, trigger_confirmed=None))

    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_trigger_unavailable"
    assert result.decision_facts["event_key"] == "critical_values"
    assert result.decision_facts["source_state"] == "available"
    assert result.decision_facts["events"] == [
        {
            "trigger_confirmed": None,
            "event_type": "critical_values",
            "event_id": "event-018",
            "event_source_type": "inpat_nondrug_order",
            "event_source_id": "ORDER-018",
            "event_time": "2026-09-16 08:00:00",
            "stage2_state": "ready",
            "evaluation_window_mature": True,
            "stage2_facts": [
                _stage2_fact("event-018", "report_recorded"),
                _stage2_fact("event-018", "disposition_recorded"),
            ],
        }
    ]


def test_existing_rule_omits_optional_empty_identifiers_from_decision_facts():
    rule_id = "LX0916-018"
    result = _run(
        rule_id,
        _context(rule_id, event_id="", document_id=None, source_type=""),
    )

    event = result.decision_facts["events"][0]
    assert "event_id" not in event
    assert "document_id" not in event
    assert "source_type" not in event
