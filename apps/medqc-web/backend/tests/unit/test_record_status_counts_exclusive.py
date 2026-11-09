"""病历级统计按病历互斥分类，各类之和等于总数；批处理 Worker 与客户 DTO 共用同一合同。

用户口径（2026-11-08）：全部不适用 → 不适用；全部暂停或暂停与不适用混合 → 未执行，
均不计入合规；其他混合场景沿用既有合同。单条规则原始状态不变。
"""

import pytest

from app.services.custom_qc_workspace_service import (
    _compliant_record_refs,
    classify_neutral_records,
)
from app.services.luxian_0609.phase_scope import build_luxian_0609_pending_definition_result
from app.services.sichuan_workspace_batch_worker import _build_record_status_counts


def test_overlapping_categories_are_counted_once():
    counts = _build_record_status_counts(
        total_records=3, issue_record_ids={"R1"}, uncertain_record_ids={"R1"},
        data_gap_record_ids={"R1", "R2"}, failed_record_ids=set(), not_applicable_record_ids=set(),
    )
    assert counts == {"non_compliant": 1, "uncertain": 0, "data_gap": 1,
                      "not_applicable": 0, "not_executed": 0, "failed": 0, "compliant": 1}
    assert sum(counts.values()) == 3


def test_failed_takes_priority_and_sum_matches_total():
    counts = _build_record_status_counts(
        total_records=3, issue_record_ids={"R1"}, uncertain_record_ids={"R1"},
        data_gap_record_ids=set(), failed_record_ids={"R1"}, not_applicable_record_ids=set(),
    )
    assert counts["failed"] == 1 and counts["non_compliant"] == 0
    assert sum(counts.values()) == 3


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
    na_ids, paused_ids = classify_neutral_records(keyed)
    return _build_record_status_counts(
        total_records=len({i["record_ref"] for i in items}),
        issue_record_ids=by_status("non_compliant", "ai_suggested_non_compliant"),
        uncertain_record_ids=by_status("uncertain"), data_gap_record_ids=by_status("data_gap"),
        failed_record_ids=by_status("technical_error"),
        not_applicable_record_ids=na_ids, not_executed_record_ids=paused_ids,
    )


PAUSED = build_luxian_0609_pending_definition_result("LX0609-03-01-01")["status"]


@pytest.mark.parametrize("statuses,bucket", [
    (("not_applicable", "not_applicable"), "not_applicable"),
    ((PAUSED, PAUSED), "not_executed"),
    ((PAUSED, "not_applicable"), "not_executed"),
    (("compliant", PAUSED), "compliant"),
    (("compliant", "not_applicable"), "compliant"),
    (("data_gap", PAUSED), "data_gap"),
], ids=["all_na", "all_paused", "paused_and_na", "compliant_and_paused", "compliant_and_na", "gap_and_paused"])
def test_worker_and_customer_dto_classify_neutral_records_alike(statuses, bucket):
    assert PAUSED == "not_executed"
    items = [{"record_ref": "R1", "status": status} for status in statuses]
    counts = _worker_counts(items)
    assert counts[bucket] == 1 and sum(counts.values()) == 1
    na_ids, paused_ids = classify_neutral_records(items, ("record_ref",))
    dto = {"compliant": len(_compliant_record_refs(items)),
           "not_applicable": len(na_ids), "not_executed": len(paused_ids)}
    for key, value in dto.items():
        assert value == counts[key], (key, dto, counts)
    # 单条规则原始状态不因病历级分类改变。
    assert [item["status"] for item in items] == list(statuses)
