"""测试病例评价时间点固定，以及样本列表不外露历史验收数据。"""
import json

import pytest


def test_record_frozen_dates_override_only_matching_running_records():
    from app.services.case_identity import CaseRef
    from app.services.luxian_0609.evaluation_horizon import build_record_evaluation_horizon_snapshot
    base = {"admission_datetime": "2026-07-01T08:00:00", "institute_id": "CUSTOMER_TEST", "patient_id": "P"}
    records = [
        {**base, "record_id": "V1", "visit_id": "V1", "scope": "running"},
        {**base, "record_id": "V2", "visit_id": "V2", "scope": "running"},
        {**base, "record_id": "V3", "visit_id": "V3", "scope": "final", "discharge_datetime": "2026-07-03T10:00:00"},
    ]
    pinned = {CaseRef("CUSTOMER_TEST", "P", v).as_key(): "2026-07-05" for v in ("V1", "V3")}
    for task_date in ("2026-09-29", "2026-10-06"):
        by_id = {s["record_id"]: s for s in build_record_evaluation_horizon_snapshot(
            records, task_frozen_date=task_date, record_frozen_dates=pinned)}
        assert by_id["V1"]["evaluation_horizon"] == "2026-07-05"  # 固定：不随运行日期变化
        assert by_id["V2"]["evaluation_horizon"] == task_date  # 未固定：沿用任务当天
        assert by_id["V3"]["evaluation_horizon"] == "2026-07-03"  # 终末病历仍以出院为终点


def test_create_rejects_evaluation_date_before_admission():
    from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
    service = object.__new__(CustomQCSamplePoolService)
    payload = {"basic_info": {"admission_time": "2026-07-01 08:00:00"}, "evaluation_as_of_date": "2026-06-30",
               "documents": [{"document_type": "admission_record", "title": "入院记录", "content": "测试"}]}
    with pytest.raises(ValueError, match="不能早于入院日期"):
        service.create_customer_test_record(payload=payload, created_by="u")


def test_sample_list_does_not_publish_legacy_validation_data():
    from app.services.custom_qc_sample_pool_service import CustomQCSamplePoolService
    answer = {"qc_point_id": "LX0609-01-01-01", "expected_status": "non_compliant"}
    row = {"raw_payload_json": json.dumps({"golden_answers": [answer],
        "rule_validation_materials": {"private": "原文"}, "rule_validation_sessions": {"source": "原文"},
        "rule_validation": {"runs": [{"created_by": "other"}]}})}
    item = CustomQCSamplePoolService._row_to_item(None, row)
    assert item["raw_payload"] == {"golden_answers": [answer]}


def test_snapshot_carries_task_frozen_date_without_changing_discharge_horizon():
    # 用户决定（2026-10-20）：死后文书时限要用任务冻结日，出院病例终点仍是出院日。
    from app.services.luxian_0609.evaluation_horizon import (
        build_record_evaluation_horizon_snapshot,
        resolve_snapshot_task_frozen_date,
    )
    record = {"record_id": "V9", "visit_id": "V9", "institute_id": "H", "patient_id": "P", "scope": "final",
              "admission_datetime": "2026-07-01T08:00:00", "discharge_datetime": "2026-07-03T10:00:00"}
    (snapshot,) = build_record_evaluation_horizon_snapshot([record], task_frozen_date="2026-10-18")
    assert snapshot["evaluation_horizon"] == "2026-07-03"
    assert snapshot["task_frozen_date"] == "2026-10-18"
    assert resolve_snapshot_task_frozen_date(snapshot).isoformat() == "2026-10-18"
    assert resolve_snapshot_task_frozen_date({"evaluation_horizon": "2026-07-03"}) is None


@pytest.mark.parametrize("admission,discharge", [
    ("2026-07-01T08:00:00", "2026-07-03T10:00:00+08:00"),
    ("2026-07-01T08:00:00+08:00", "2026-07-03T10:00:00"),
])
def test_batch_snapshot_handles_mixed_timezone_awareness_without_aborting(admission, discharge):
    from app.services.luxian_0609.evaluation_horizon import (
        build_record_evaluation_horizon_snapshot,
        resolve_record_evaluation_horizon_policy,
        resolve_record_evaluation_horizon_unavailable_reason,
    )
    base = {"institute_id": "H", "patient_id": "P", "scope": "final"}
    records = [
        {**base, "visit_id": "V1", "admission_datetime": admission, "discharge_datetime": discharge},
        {**base, "visit_id": "V2", "admission_datetime": "2026-07-01T08:00:00",
         "discharge_datetime": "2026-07-03T10:00:00"},
    ]

    snapshots = build_record_evaluation_horizon_snapshot(records, task_frozen_date="2026-10-23")
    by_id = {item["record_id"]: item for item in snapshots}
    mixed = by_id["V1"]
    assert mixed["resolution_status"] == "time_conflict"
    assert mixed["evaluation_horizon"] == mixed["evaluation_basis"] == ""
    assert mixed["admission_datetime"] == admission
    assert mixed["discharge_datetime"] == discharge
    assert resolve_record_evaluation_horizon_policy(mixed) == "disabled"
    assert resolve_record_evaluation_horizon_unavailable_reason(mixed) == "authoritative_time_conflict"
    assert by_id["V2"]["resolution_status"] == "resolved"
    assert by_id["V2"]["evaluation_horizon"] == "2026-07-03"
