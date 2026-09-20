from __future__ import annotations

import json

import pytest

from app.services.luxian_0916.course_event_rules import execute_course_event_rules
from app.services.luxian_0916 import disease_change_015016
from app.services.luxian_0916.disease_change_015016 import (
    build_disease_change_015016_facts,
    merge_disease_change_015016_facts,
)


def _order(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "order_id": "ORDER-1",
        "order_name": "下病危医嘱",
        "order_status": "新开",
        "prescribed_datetime": "2026-09-16 08:00:00",
        "planned_start_datetime": None,
    }
    row.update(overrides)
    return row


def _lab(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "item_document_id": "LAB-DOC-1",
        "item_test_id": "TEST-1",
        "item_test_no": "NO-1",
        "item_id": "ITEM-1",
        "item_name": "血钾",
        "result": "2.7",
        "unit": "mmol/L",
        "abnormal_indicator": "PL",
        "item_report_time": "2026-09-16 09:00:00",
        "master_test_id": "TEST-1",
        "master_report_datetime": "2026-09-16 09:00:00",
    }
    row.update(overrides)
    return row


def _result(rule_id: str, context: dict) -> object:
    results = execute_course_event_rules(context, [rule_id])
    assert len(results) == 1
    return results[0]


def test_no_event_requires_both_complete_sources_and_is_replayable() -> None:
    first = build_disease_change_015016_facts(order_rows=[], lab_rows=[])
    second = build_disease_change_015016_facts(order_rows=[], lab_rows=[])

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["event_facts"] == {"disease_changes": []}
    assert first["event_source_state_by_rule"] == {
        "LX0916-015": "structured_complete",
        "LX0916-016": "structured_complete",
    }
    for rule_id in ("LX0916-015", "LX0916-016"):
        result = _result(rule_id, first)
        assert (result.status, result.reason_code) == (
            "not_applicable",
            "trigger_event_absent",
        )


def test_single_and_dual_structured_trigger_keep_source_coordinates() -> None:
    only_order = build_disease_change_015016_facts(order_rows=[_order()], lab_rows=[])
    both_sources = build_disease_change_015016_facts(
        order_rows=[_order()], lab_rows=[_lab()]
    )

    assert [
        event["event_source_type"]
        for event in only_order["event_facts"]["disease_changes"]
    ] == ["inpat_nondrug_order"]
    events = both_sources["event_facts"]["disease_changes"]
    assert {event["event_source_type"] for event in events} == {
        "inpat_nondrug_order",
        "labtest_master",
    }
    lab_event = next(
        event for event in events if event["event_source_type"] == "labtest_master"
    )
    assert lab_event["event_source_type"] == "labtest_master"
    assert lab_event["event_source_id"] == "TEST-1"
    assert lab_event["related_source_type"] == "labtest_item_report"
    assert lab_event["related_source_ids"] == ["ITEM-1"]


@pytest.mark.parametrize("status", ("取消", "撤销", "作废"))
def test_cancelled_or_revoked_orders_are_not_triggers(status: str) -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[_order(order_status=status)], lab_rows=[]
    )

    assert facts["event_source_state_by_rule"]["LX0916-015"] == "structured_complete"
    assert facts["event_facts"]["disease_changes"] == []


def test_stopped_order_remains_historical_trigger() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[_order(order_status="停止")], lab_rows=[]
    )

    event = facts["event_facts"]["disease_changes"][0]
    assert event["lifecycle_state"] == "stopped"
    assert event["trigger_confirmed"] is True


def test_relief_order_is_not_a_new_severity_trigger() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[_order(order_name="解除病危医嘱")], lab_rows=[]
    )

    assert facts["event_facts"]["disease_changes"] == []


@pytest.mark.parametrize("flag", ("PL", "PH"))
def test_only_pl_or_ph_lab_flags_trigger(flag: str) -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[], lab_rows=[_lab(abnormal_indicator=flag)]
    )

    event = facts["event_facts"]["disease_changes"][0]
    assert event["event_kind"] == "critical_lab_report"
    assert event["critical_flags"] == [flag]


def test_multiple_critical_items_in_one_report_are_one_event() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[],
        lab_rows=[
            _lab(item_id="ITEM-1", abnormal_indicator="PL"),
            _lab(item_id="ITEM-2", abnormal_indicator="PH"),
        ],
    )

    events = facts["event_facts"]["disease_changes"]
    assert len(events) == 1
    assert events[0]["event_id"] == "critical-lab:TEST-1"
    assert events[0]["related_source_ids"] == ["ITEM-1", "ITEM-2"]
    assert events[0]["critical_flags"] == ["PH", "PL"]


def test_critical_event_keeps_minimal_stage2_binding_context_in_memory() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[],
        lab_rows=[
            _lab(
                item_id="ITEM-1",
                item_name="血钾",
                result="2.7",
                unit="mmol/L",
                abnormal_indicator="PL",
            )
        ],
    )

    event = facts["event_facts"]["disease_changes"][0]

    assert event["critical_items"] == [
        {
            "item_id": "ITEM-1",
            "item_name": "血钾",
            "result": "2.7",
            "unit": "mmol/L",
            "critical_flag": "PL",
        }
    ]


def test_missing_stage2_binding_context_does_not_change_stage1_trigger() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[],
        lab_rows=[_lab(item_name="", result="2.7", abnormal_indicator="PL")],
    )

    events = facts["event_facts"]["disease_changes"]

    assert len(events) == 1
    assert events[0]["event_id"] == "critical-lab:TEST-1"
    assert "critical_items" not in events[0]
    assert facts["event_source_state_by_rule"] == {
        "LX0916-015": "structured_complete",
        "LX0916-016": "structured_complete",
    }


def test_conflicting_item_and_master_report_times_are_source_invalid() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[],
        lab_rows=[_lab(master_report_datetime="2026-09-16 09:01:00")],
    )

    result = _result("LX0916-015", facts)
    assert (result.status, result.reason_code) == (
        "data_quality_gap",
        "structured_trigger_source_invalid",
    )


def test_invalid_source_state_is_preserved_with_partial_valid_events() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[_order()],
        lab_rows=[_lab(master_report_datetime="2026-09-16 09:01:00")],
    )

    result = _result("LX0916-015", facts)

    assert result.reason_code == "structured_trigger_source_invalid"
    assert result.decision_facts["source_state"] == "structured_trigger_source_invalid"
    assert result.decision_facts["events"][0]["event_source_id"] == "ORDER-1"


@pytest.mark.parametrize("flag", ("HI", "LI"))
def test_hi_or_li_do_not_trigger_luxian_critical_value(flag: str) -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[], lab_rows=[_lab(abnormal_indicator=flag)]
    )

    assert facts["event_source_state_by_rule"]["LX0916-015"] == "structured_complete"
    assert facts["event_facts"]["disease_changes"] == []


def test_source_partial_or_invalid_never_becomes_no_trigger() -> None:
    partial = build_disease_change_015016_facts(
        order_rows=[_order(order_id=f"ORDER-{index}") for index in range(201)],
        lab_rows=[],
    )
    invalid = build_disease_change_015016_facts(
        order_rows=[_order(order_status="未知")],
        lab_rows=[],
    )

    for facts, reason in (
        (partial, "structured_trigger_source_partial"),
        (invalid, "structured_trigger_source_invalid"),
    ):
        result = _result("LX0916-015", facts)
        assert (result.status, result.reason_code) == ("data_quality_gap", reason)


def test_trigger_without_stage2_facts_is_data_gap_not_not_executed() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[_order(prescribed_datetime=None, planned_start_datetime=None)],
        lab_rows=[],
    )

    result = _result("LX0916-016", facts)

    assert (result.status, result.reason_code) == (
        "data_quality_gap",
        "disease_change_stage2_fact_unavailable",
    )
    assert result.status != "not_executed"


def test_invalid_timestamp_is_not_treated_as_a_trusted_event_time() -> None:
    facts = build_disease_change_015016_facts(
        order_rows=[_order(prescribed_datetime="not-a-time")], lab_rows=[]
    )

    event = facts["event_facts"]["disease_changes"][0]
    assert "event_time" not in event


def test_unavailable_database_source_is_a_data_gap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(disease_change_015016, "engine", None)

    facts = disease_change_015016.load_disease_change_015016_facts(
        institute_id="i", patient_id="p", visit_id="v"
    )

    result = _result("LX0916-015", facts)
    assert (result.status, result.reason_code) == (
        "data_quality_gap",
        "structured_trigger_source_unavailable",
    )


def test_structured_facts_override_shared_model_disease_changes() -> None:
    structured = build_disease_change_015016_facts(order_rows=[], lab_rows=[])
    merged = merge_disease_change_015016_facts(
        context={
            "event_facts": {
                "disease_changes": [{"event_id": "model-event"}],
                "critical_values": [],
            },
            "event_source_state_by_rule": {
                "LX0916-015": "selected",
                "LX0916-016": "selected",
            },
        },
        structured_facts=structured,
    )

    assert merged["event_facts"]["disease_changes"] == []
    assert merged["event_facts"]["critical_values"] == []
    assert merged["event_source_state_by_rule"]["LX0916-015"] == "structured_complete"


def test_result_anchor_and_decision_facts_preserve_event_and_document_coordinates() -> (
    None
):
    context = {
        "event_source_state_by_rule": {"LX0916-015": "structured_complete"},
        "event_facts": {
            "disease_changes": [
                {
                    "event_type": "disease_changes",
                    "event_id": "severity-order:ORDER-1",
                    "event_source_type": "inpat_nondrug_order",
                    "event_source_id": "ORDER-1",
                    "event_time": "2026-09-16 08:00:00",
                    "trigger_confirmed": True,
                    "evaluation_window_mature": True,
                    "stage2_state_by_rule": {"LX0916-015": "ready"},
                    "stage2_facts": [
                        {
                            "fact_kind": fact_kind,
                            "state": "absent"
                            if fact_kind == "record_present"
                            else "present",
                            "event_id": "severity-order:ORDER-1",
                            "source_type": (
                                None
                                if fact_kind == "record_present"
                                else "daily_course_record"
                            ),
                            "document_id": (
                                None if fact_kind == "record_present" else "COURSE-1"
                            ),
                            "clause_id": (
                                None if fact_kind == "record_present" else "COURSE-1:1"
                            ),
                        }
                        for fact_kind in (
                            "record_present",
                            "time_recorded",
                            "content_recorded",
                        )
                    ],
                }
            ]
        },
    }

    result = _result("LX0916-015", context)

    assert result.status == "non_compliant"
    assert result.document_anchors[0]["event_id"] == "severity-order:ORDER-1"
    assert result.document_anchors[0]["fields"] == ["record_present"]
    assert result.document_anchors[0]["document_type"] == ""
    assert result.document_anchors[0]["document_id"] == ""
    assert result.decision_facts["events"][0]["event_source_id"] == "ORDER-1"
    decision_facts = result.decision_facts["events"][0]["stage2_facts"]
    assert decision_facts[0]["document_id"] is None
    assert decision_facts[1]["document_id"] == "COURSE-1"
