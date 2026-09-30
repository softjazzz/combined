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
