from __future__ import annotations

import pytest
from app.services.luxian_0916.surgery_consent_rules import (
    execute_surgery_consent_rules,
)


_RULE_IDS = tuple(f"LX0916-{number:03d}" for number in range(21, 31))

_EVENT_FOR_RULE = {
    "LX0916-021": "surgery_arranged",
    "LX0916-022": "anesthesia_arranged",
    "LX0916-023": "anesthesia_performed",
    "LX0916-024": "anesthesia_record_formed",
    "LX0916-025": "surgery_performed",
    "LX0916-026": "surgery_performed",
    "LX0916-027": "emergency_surgery",
    "LX0916-028": "unplanned_reoperation",
    "LX0916-029": "special_treatment",
    "LX0916-030": "critical_or_serious_condition",
}

_DOCUMENT_FOR_RULE = {
    "LX0916-021": "surgery_consent",
    "LX0916-022": "anesthesia_consent",
    "LX0916-023": "anesthesia_record",
    "LX0916-024": "anesthesia_record",
    "LX0916-025": "surgery_record",
    "LX0916-026": "surgery_safety_check",
    "LX0916-027": "emergency_surgery_instruction",
    "LX0916-028": "unplanned_reoperation_explanation",
    "LX0916-029": "special_treatment_consent",
    "LX0916-030": "critical_condition_notice",
}

_COMPLETENESS_RULE_IDS = ("LX0916-024", "LX0916-025", "LX0916-026")


def _context(rule_id: str, document_fact: dict[str, object] | None) -> dict[str, object]:
    event_facts = {event: False for event in set(_EVENT_FOR_RULE.values())}
    event_facts.update({"surgery_arranged": False, "anesthesia_arranged": False})
    event_facts[_EVENT_FOR_RULE[rule_id]] = True
    document_facts = (
        {_DOCUMENT_FOR_RULE[rule_id]: document_fact} if document_fact is not None else {}
    )
    return {"event_facts": event_facts, "document_facts": document_facts}


@pytest.mark.parametrize("rule_id", tuple(rule_id for rule_id in _RULE_IDS if rule_id not in _COMPLETENESS_RULE_IDS))
def test_surgery_rules_report_compliant_from_complete_authoritative_fact(
    rule_id: str,
) -> None:
    fact = {"presence": "present", "completeness": "complete", "evidence": ["文书已核验"]}

    result = execute_surgery_consent_rules(_context(rule_id, fact), (rule_id,))[0]

    assert result.status == "compliant"
    assert result.evidence == ("文书已核验",)


@pytest.mark.parametrize("rule_id", _COMPLETENESS_RULE_IDS)
def test_024_to_026_reject_legacy_complete_fact_without_required_items(rule_id: str) -> None:
    fact = {"presence": "present", "completeness": "complete"}

    result = execute_surgery_consent_rules(_context(rule_id, fact), (rule_id,))[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "semantic_fact_unavailable"


@pytest.mark.parametrize("rule_id", _COMPLETENESS_RULE_IDS)
def test_024_to_026_reject_direct_executor_marker_without_complete_contract(rule_id: str) -> None:
    fact = {
        "presence": "present",
        "completeness": "complete",
        "completeness_basis": "grounded_required_items",
        "missing_items": (),
    }

    result = execute_surgery_consent_rules(_context(rule_id, fact), (rule_id,))[0]

    assert result.status == "data_quality_gap"


@pytest.mark.parametrize(
    ("rule_id", "missing_item"),
    (
        ("LX0916-024", "麻醉医师签名"),
        ("LX0916-025", "出血量"),
        ("LX0916-026", "患者离开手术室前三方逐次确认签字"),
    ),
)
def test_024_to_026_name_the_specific_missing_required_item(
    rule_id: str, missing_item: str
) -> None:
    fact = {
        "presence": "present",
        "completeness": "incomplete",
        "completeness_basis": "grounded_required_items",
        "missing_items": (missing_item,),
    }

    result = execute_surgery_consent_rules(_context(rule_id, fact), (rule_id,))[0]

    assert result.status == "data_quality_gap"


@pytest.mark.parametrize("rule_id", tuple(rule_id for rule_id in _RULE_IDS if rule_id not in _COMPLETENESS_RULE_IDS))
def test_surgery_rules_report_explicit_defect_from_authoritative_fact(
    rule_id: str,
) -> None:
    fact = (
        {"presence": "missing"}
        if rule_id == "LX0916-023"
        else {"presence": "present", "completeness": "incomplete", "evidence": ["缺项"]}
    )

    result = execute_surgery_consent_rules(_context(rule_id, fact), (rule_id,))[0]

    assert result.status == "non_compliant"
    assert result.findings
    assert result.suggestion


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_surgery_rules_do_not_apply_without_explicit_trigger_event(rule_id: str) -> None:
    context = _context(rule_id, {"presence": "present", "completeness": "complete"})
    event_facts = context["event_facts"]
    assert isinstance(event_facts, dict)
    event_facts[_EVENT_FOR_RULE[rule_id]] = False

    result = execute_surgery_consent_rules(context, (rule_id,))[0]

    assert result.status == "not_applicable"
    assert result.reason_code == "trigger_event_not_present"


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_surgery_rules_wait_when_upstream_marks_evaluation_window_immature(
    rule_id: str,
) -> None:
    context = _context(rule_id, {"presence": "present", "completeness": "complete"})
    event_facts = context["event_facts"]
    assert isinstance(event_facts, dict)
    event_facts["evaluation_window_mature"] = False

    result = execute_surgery_consent_rules(context, (rule_id,))[0]

    assert result.status == "not_executed"
    assert result.reason_code == "evaluation_window_not_mature"


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_surgery_rules_preserve_data_gap_without_authoritative_document_fact(
    rule_id: str,
) -> None:
    result = execute_surgery_consent_rules(_context(rule_id, None), (rule_id,))[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "semantic_fact_unavailable"


def test_anesthesia_record_content_rule_reports_conflicting_authoritative_facts() -> None:
    result = execute_surgery_consent_rules(
        _context("LX0916-024", {"presence": "missing"}), ("LX0916-024",)
    )[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_document_fact_conflict"


@pytest.mark.parametrize(
    ("rule_id", "required_item"),
    (
        ("LX0916-021", "术前诊断"),
        ("LX0916-021", "经治医师和术者签名"),
        ("LX0916-022", "拟施手术及麻醉方式"),
        ("LX0916-022", "患者及麻醉医师签名和日期"),
    ),
)
def test_surgery_document_content_findings_keep_required_item_scope(
    rule_id: str, required_item: str
) -> None:
    result = execute_surgery_consent_rules(
        _context(
            rule_id,
            {
                "presence": "present",
                "completeness": "incomplete",
                "completeness_basis": "grounded_required_items",
                "missing_items": (required_item,),
            },
        ),
        (rule_id,),
    )[0]

    assert result.status == "non_compliant"
    assert required_item in result.findings
    assert required_item in result.suggestion


def test_surgery_rules_reject_unknown_rule_id() -> None:
    with pytest.raises(ValueError, match="unsupported Luxian0916 surgery rule ids"):
        execute_surgery_consent_rules({}, ("LX0916-099",))
