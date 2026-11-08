"""病历级统计按病历互斥分类，各类之和等于总数；合规病历不含缺陷、资料不足或失败。"""

from app.services.custom_qc_workspace_service import (
    _compliant_record_refs,
    records_with_only_neutral_statuses,
)
from app.services.luxian_0609.phase_scope import build_luxian_0609_pending_definition_result
from app.services.sichuan_workspace_batch_worker import _build_record_status_counts


def test_overlapping_categories_are_counted_once():
    counts = _build_record_status_counts(
        total_records=3, issue_record_ids={"R1"}, uncertain_record_ids={"R1"},
        data_gap_record_ids={"R1", "R2"}, failed_record_ids=set(), not_applicable_record_ids=set(),
    )
    assert counts == {"non_compliant": 1, "uncertain": 0, "data_gap": 1,
                      "not_applicable": 0, "failed": 0, "compliant": 1}
    assert sum(counts.values()) == 3


def test_failed_takes_priority_and_sum_matches_total():
    counts = _build_record_status_counts(
        total_records=3, issue_record_ids={"R1"}, uncertain_record_ids={"R1"},
        data_gap_record_ids=set(), failed_record_ids={"R1"}, not_applicable_record_ids=set(),
    )
    assert counts["failed"] == 1 and counts["non_compliant"] == 0
    assert sum(counts.values()) == 3


def test_partial_not_applicable_record_stays_compliant():
    items = [
        {"record_key": "R1", "status": "compliant"},
        {"record_key": "R1", "status": "not_applicable"},
        {"record_key": "R2", "status": "not_applicable"},
    ]
    only_na = records_with_only_neutral_statuses(items)
    assert only_na == {"R2"}
    counts = _build_record_status_counts(
        total_records=2, issue_record_ids=set(), uncertain_record_ids=set(),
        data_gap_record_ids=set(), failed_record_ids=set(), not_applicable_record_ids=only_na,
    )
    assert (counts["compliant"], counts["not_applicable"]) == (1, 1)


def test_customer_compliant_records_exclude_records_with_defects():
    items = [
        {"record_ref": "A", "status": "compliant"},
        {"record_ref": "A", "status": "non_compliant"},
        {"record_ref": "B", "status": "compliant"},
        {"record_ref": "B", "status": "not_applicable"},
        {"record_ref": "C", "status": "compliant"},
        {"record_ref": "C", "status": "data_gap"},
        {"record_ref": "D", "status": "not_applicable"},
    ]
    assert _compliant_record_refs(items) == {"B"}


def _worker_counts(items):
    keyed = [{**item, "record_key": item["record_ref"]} for item in items]
    by_status = lambda *values: {i["record_ref"] for i in items if i["status"] in values}
    return _build_record_status_counts(
        total_records=len({i["record_ref"] for i in items}),
        issue_record_ids=by_status("non_compliant", "ai_suggested_non_compliant"),
        uncertain_record_ids=by_status("uncertain"), data_gap_record_ids=by_status("data_gap"),
        failed_record_ids=by_status("technical_error"),
        not_applicable_record_ids=records_with_only_neutral_statuses(keyed),
    )


def test_worker_and_customer_dto_agree_on_paused_rule():
    paused = build_luxian_0609_pending_definition_result("LX0609-03-01-01")
    assert paused["status"] == "not_executed"
    items = [
        {"record_ref": "R1", "status": "compliant"},
        {"record_ref": "R1", "status": paused["status"]},
        {"record_ref": "R2", "status": paused["status"]},
        {"record_ref": "R2", "status": "not_applicable"},
        {"record_ref": "R3", "status": "compliant"},
        {"record_ref": "R3", "status": "data_gap"},
    ]
    counts = _worker_counts(items)
    assert counts["compliant"] == len(_compliant_record_refs(items)) == 1
    assert (counts["not_applicable"], counts["data_gap"]) == (1, 1)
