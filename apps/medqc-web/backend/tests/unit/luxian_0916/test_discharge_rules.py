from __future__ import annotations

import pytest

from app.services.luxian_0916.discharge_rules import execute_discharge_rules


_RULE_IDS = ("LX0916-031", "LX0916-032")
_DOCUMENT_FOR_RULE = {
    "LX0916-031": "discharge_record",
    "LX0916-032": "discharge_orders",
}


def _context(rule_id: str, document_fact: dict[str, object] | None) -> dict[str, object]:
    document_facts = (
        {_DOCUMENT_FOR_RULE[rule_id]: document_fact} if document_fact is not None else {}
    )
    return {
        "discharge_facts": {"discharge_arranged": True, "discharge_record_formed": False},
        "document_facts": document_facts,
    }


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_discharge_rules_report_compliant_from_complete_authoritative_fact(
    rule_id: str,
) -> None:
    result = execute_discharge_rules(
        _context(
            rule_id,
            {
                "presence": "present",
                "completeness": "complete",
                "document_id": "D-1",
                "source_type": "discharge_record",
            },
        ),
        (rule_id,),
    )[0]

    assert result.status == "compliant"
    assert result.reason_code == "required_document_complete"
    assert result.decision_facts == {
        "discharge_gate": "discharge_arranged_or_record_formed",
        "discharge_arranged": True,
        "discharge_record_formed": False,
        "discharge_window_ready": True,
        "document_fact_key": _DOCUMENT_FOR_RULE[rule_id],
        "document_presence": "present",
        "document_completeness": "complete",
        "document_id": "D-1",
        "source_type": "discharge_record",
    }


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_discharge_rules_report_explicit_incomplete_document(rule_id: str) -> None:
    result = execute_discharge_rules(
        _context(rule_id, {"presence": "present", "completeness": "incomplete"}),
        (rule_id,),
    )[0]

    assert result.status == "non_compliant"
    assert result.reason_code == "required_document_incomplete"


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_discharge_rules_wait_during_ordinary_inpatient_window(rule_id: str) -> None:
    context = _context(rule_id, {"presence": "present", "completeness": "complete"})
    context["discharge_facts"] = {"discharge_arranged": False, "discharge_record_formed": False}

    result = execute_discharge_rules(context, (rule_id,))[0]

    assert result.status == "not_executed"
    assert result.reason_code == "evaluation_window_not_mature"
    assert result.decision_facts == {
        "discharge_gate": "discharge_arranged_or_record_formed",
        "discharge_arranged": False,
        "discharge_record_formed": False,
        "discharge_window_ready": False,
        "document_fact_key": _DOCUMENT_FOR_RULE[rule_id],
    }


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_discharge_rules_preserve_data_gap_without_authoritative_document_fact(
    rule_id: str,
) -> None:
    result = execute_discharge_rules(_context(rule_id, None), (rule_id,))[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "semantic_fact_unavailable"


@pytest.mark.parametrize("rule_id", _RULE_IDS)
def test_discharge_rules_report_missing_document_after_window_is_open(rule_id: str) -> None:
    result = execute_discharge_rules(_context(rule_id, {"presence": "missing"}), (rule_id,))[0]

    assert result.status == "non_compliant"
    assert result.reason_code == "required_document_missing"


def test_discharge_rules_reject_unknown_rule_id() -> None:
    with pytest.raises(ValueError, match="unsupported Luxian0916 discharge rule ids"):
        execute_discharge_rules({}, ("LX0916-099",))
