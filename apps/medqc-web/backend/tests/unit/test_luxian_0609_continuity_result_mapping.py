from __future__ import annotations

import pytest

from app.services.luxian_0609.continuity_result_mapping import (
    is_continuity_customer_rule,
    safe_continuity_customer_display_facts,
)
from app.services.luxian_0609_result_aggregator import (
    safe_luxian_0609_customer_display_facts,
)


def _handoff_association(kind: str) -> dict[str, object]:
    raw: dict[str, object] = {
        "failure_kind": kind,
        "change_event_count": 1,
        "change_times": ["2026-07-01 08:00:00"],
        "handoff_record_count": 1,
        "handoff_times": ["2026-07-01 07:50:00"],
        "handover_record_count": 1,
        "handover_times": ["2026-07-01 14:00:00"],
        "handover_threshold_hours": 24,
    }
    if kind == "physician_change_time_missing":
        raw.update(change_event_count=2, timed_change_event_count=1, missing_change_time_count=1)
    return raw


@pytest.mark.parametrize(
    ("rule_id", "raw"),
    [
        ("LX0609-04-02-07", {
            "verification_kind": "consultation_timeliness_check", "threshold_hours": 24,
            "actual_interval_hours": [6.0], "request_times": ["2026-07-01 08:00:00"],
            "record_times": ["2026-07-01 14:00:00"],
            "event_results": [{"sequence": 1, "request_time": "2026-07-01 08:00:00", "completion_time": "2026-07-01 14:00:00", "interval_seconds": 21600, "outcome": "within_threshold"}],
        }),
        ("LX0609-04-02-07", {
            "verification_kind": "consultation_timeliness_check", "threshold_hours": 24,
            "actual_interval_hours": [0.0], "request_times": ["2026-07-01"],
            "record_times": ["2026-07-01"],
            "event_results": [{"sequence": 1, "request_time": "2026-07-01", "completion_time": "2026-07-01", "interval_seconds": 0, "outcome": "within_threshold"}],
        }),
        ("LX0609-10-01-01", {
            "verification_kind": "physician_handoff_timeliness_check", "change_time": "2026-07-01 08:00:00",
            "handoff_times": ["2026-07-01 07:50:00"], "handover_times": ["2026-07-01 14:00:00"], "handover_threshold_hours": 24,
        }),
        ("LX0609-10-01-01", {
            "verification_kind": "physician_handoff_multi_event_check", "change_event_count": 2, "handover_threshold_hours": 24,
            "events": [
                {"event_position": 1, "change_time": "变更甲", "handoff_time": "交班甲", "handover_time": "接班甲", "handover_interval_seconds": 1, "outcome": "completed_within_threshold"},
                {"event_position": 2, "change_time": "change-b", "handoff_time": "handoff-b", "handover_time": "handover-b", "handover_interval_seconds": 86401, "outcome": "handover_late"},
            ],
        }),
        ("LX0609-10-01-01", {
            "verification_kind": "physician_handoff_multi_event_check", "change_event_count": 2, "handover_threshold_hours": 24,
            "events": [
                {"event_position": 1, "change_time": "2026-07-01 08:00:00", "handoff_time": "2026-07-01 07:50:00", "handover_time": "2026-07-01 14:00:00", "handover_interval_seconds": 21600, "outcome": "completed_within_threshold"},
                {"event_position": 2, "change_time": "2026-07-02 08:00:00", "handoff_time": "2026-07-02 07:50:00", "handover_time": None, "handover_interval_seconds": None, "outcome": "handover_missing"},
            ],
        }),
        ("LX0609-10-01-01", _handoff_association("physician_handoff_association_failed")),
        ("LX0609-10-01-01", {
            "failure_kind": "physician_handoff_record_time_missing", "change_event_count": 2,
            "handoff_record_count": 2, "missing_handoff_time_count": 1,
            "handover_record_count": 2, "missing_handover_time_count": 0,
            "handover_threshold_hours": 24,
        }),
        ("LX0609-10-01-01", {**_handoff_association("physician_handoff_identity_missing"), "source_document_refs": []}),
        ("LX0609-10-01-01", {
            "failure_kind": "physician_signature_timeline_incomplete", "source_document_refs": [],
            "daily_course_record_count": 2, "eligible_daily_course_count": 1,
            "missing_title_count": 1, "missing_time_count": 1, "missing_signature_count": 0,
        }),
        ("LX0609-10-01-01", _handoff_association("physician_change_time_missing")),
        ("LX0609-10-02-01", {
            "verification_kind": "transfer_record_timeliness_check", "transfer_order_time": "2026-07-01 08:00:00",
            "transfer_in_time": "2026-07-01 09:00:00", "transfer_out_time": "2026-07-01 10:00:00",
            "threshold_hours": 24, "transfer_in_interval_hours": 1.0, "transfer_out_interval_hours": 2.0,
        }),
        ("LX0609-10-02-02", {
            "verification_kind": "transfer_record_presence_check", "transfer_order_time": "2026-07-01 08:00:00",
            "transfer_in_time": None, "transfer_out_time": "2026-07-01 10:00:00",
            "transfer_in_associated": False, "transfer_out_associated": True,
        }),
        ("LX0609-10-02-01", {"failure_kind": "transfer_records_missing", "transfer_order_count": 1, "transfer_in_count": 0, "transfer_out_count": 1}),
        ("LX0609-12-02-01", {"verification_kind": "diagnosis_change_documentation_check", "diagnosis_change_count": 1, "reason_recorded": True, "basis_recorded": True}),
        ("LX0609-12-02-01", {"failure_kind": "diagnosis_change_association_failed", "diagnosis_record_count": 3, "diagnosis_change_count": 2, "association_issue": "multiple_changes_unresolved"}),
        ("LX0609-12-02-01", {"failure_kind": "diagnosis_change_documentation_time_missing", "diagnosis_change_count": 1, "untimed_document_count": 1, "issue": "candidate_document_time_missing"}),
    ],
)
def test_continuity_mapping_freezes_all_reachable_fact_shapes(rule_id: str, raw: dict[str, object]) -> None:
    mapped = safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw)
    assert mapped is not None
    assert mapped == safe_luxian_0609_customer_display_facts(rule_id=rule_id, raw=raw)


@pytest.mark.parametrize("rule_id", ("LX0609-04-02-07", "LX0609-10-01-01", "LX0609-10-02-01", "LX0609-10-02-02", "LX0609-12-02-01"))
def test_continuity_mapping_recognizes_only_its_rules(rule_id: str) -> None:
    assert is_continuity_customer_rule(rule_id)
    assert not is_continuity_customer_rule("LX0609-07-01-03")


@pytest.mark.parametrize(
    ("rule_id", "raw"),
    [
        ("LX0609-04-02-07", {"verification_kind": "consultation_timeliness_check", "threshold_hours": 24, "actual_interval_hours": [6], "request_times": ["2026-07-01 08:00:00"], "record_times": ["2026-07-01 14:00:00"], "event_results": [{"sequence": 2, "request_time": "2026-07-01 08:00:00", "completion_time": "2026-07-01 14:00:00", "interval_seconds": 21600, "outcome": "within_threshold"}]}),
        ("LX0609-04-02-07", {"verification_kind": "consultation_timeliness_check", "threshold_hours": 24, "actual_interval_hours": [6], "request_times": ["2026-02-30 08:00:00"], "record_times": ["2026-07-01 14:00:00"], "event_results": [{"sequence": 1, "request_time": "2026-02-30 08:00:00", "completion_time": "2026-07-01 14:00:00", "interval_seconds": 21600, "outcome": "within_threshold"}]}),
        ("LX0609-10-02-01", {"verification_kind": "transfer_record_timeliness_check", "transfer_order_time": "not-a-time", "transfer_in_time": None, "transfer_out_time": None, "threshold_hours": 24, "transfer_in_interval_hours": None, "transfer_out_interval_hours": None}),
        ("LX0609-12-02-01", {"failure_kind": "diagnosis_change_association_failed", "diagnosis_record_count": 1, "diagnosis_change_count": 1, "association_issue": "invented"}),
        ("LX0609-10-01-01", {"failure_kind": "physician_signature_timeline_incomplete", "source_document_refs": [], "daily_course_record_count": 1, "eligible_daily_course_count": 0, "missing_title_count": 0, "missing_time_count": 0, "missing_signature_count": 0}),
    ],
)
def test_continuity_mapping_rejects_illegal_or_incoherent_shapes(rule_id: str, raw: dict[str, object]) -> None:
    assert safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw) is None
