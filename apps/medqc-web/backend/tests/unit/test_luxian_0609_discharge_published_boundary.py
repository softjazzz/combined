"""出院文书族已发布事实只读校验，保留负时间差和全部公开值。"""

from __future__ import annotations

import pytest

from app.services.luxian_0609.discharge_result_mapping import (
    safe_discharge_customer_display_facts,
    validate_published_discharge_facts,
)


R061 = "LX0609-08-01-01"
R062 = "LX0609-08-01-02"
R063 = "LX0609-08-01-03"
R067 = "LX0609-08-02-01"
R068 = "LX0609-08-02-02"
BASE_061 = {"verification_kind": "discharge_record_timeliness_check", "discharge_time": "2026-09-01 01:00:00",
            "record_time": "2026-09-01 02:00:00", "threshold_hours": 24, "actual_interval_hours": 1.23456}
WINDOW = {"discharge_date": "2026-09-02", "checked_dates": ["2026-09-01", "2026-09-02"]}


@pytest.mark.parametrize("rid", [R061, R062, R063, R067, R068])
@pytest.mark.parametrize("raw", [None, {}])
def test_published_discharge_missing_facts_stay_missing(rid, raw):
    assert validate_published_discharge_facts(rule_id=rid, raw=raw) is None


@pytest.mark.parametrize("rid,raw", [
    (R061, BASE_061),
    (R061, {**BASE_061, "record_time": "2026-09-01 00:59:59", "actual_interval_hours": -1 / 3600}),
    (R061, {**BASE_061, "record_time": None, "actual_interval_hours": None}),
    (R061, {"verification_kind": "discharge_record_timeliness_check", "discharge_time": None,
            "record_time": None, "threshold_hours": 24, "actual_interval_hours": None,
            "conflicting_discharge_times": ["2026-09-01 01:00:00", "2026-09-01 02:00:00"]}),
    (R062, {"verification_kind": "discharge_medication_extraction_pending", "extraction_state": "data_gap"}),
    (R062, {"verification_kind": "discharge_medication_completeness_check", "medication_count": 1,
            "required_fields": ["drug_name", "dose", "route", "duration"], "missing_fields": ["dose"]}),
    (R063, {"verification_kind": "discharge_diagnosis_data_gap", "authoritative_gap": "diagnoses_missing", "written_gap": None}),
    (R063, {"verification_kind": "discharge_diagnosis_consistency_check", "authoritative_diagnoses": ["肺炎"],
            "written_diagnoses": ["高血压"], "diagnoses_consistent": False, "order_comparable": False}),
    (R067, {"failure_kind": "predischarge_course_time_missing", **WINDOW, "missing_time_count": 1}),
    (R067, {"failure_kind": "predischarge_course_body_missing", **WINDOW, "missing_body_count": 1}),
    (R067, {"verification_kind": "predischarge_course_presence_check", **WINDOW, "course_present": True}),
    (R068, {"failure_kind": "senior_discharge_approval_time_missing", **WINDOW, "missing_time_count": 1}),
    (R068, {"failure_kind": "senior_discharge_approval_missing", **WINDOW,
            "checked_source": "daily_course_record,senior_course_record", "approval_present": False}),
    (R068, {"verification_kind": "senior_discharge_approval_present", **WINDOW,
            "checked_source": "senior_course_record", "approval_present": True, "approval_path": "senior_approval"}),
])
def test_published_discharge_forms_read_exactly(rid, raw):
    published = safe_discharge_customer_display_facts(rule_id=rid, raw=raw)
    assert published is not None
    assert validate_published_discharge_facts(rule_id=rid, raw=published) == published
    if rid == R061 and raw.get("actual_interval_hours") == -1 / 3600:
        assert published["actual_interval_hours"] == -1 / 3600


@pytest.mark.parametrize("rid,raw", [
    (R061, {**BASE_061, "source_document_id": "SYNTHETIC"}),
    (R061, {**BASE_061, "actual_interval_hours": 1.23456}),
    (R061, {**BASE_061, "actual_interval_hours": float("inf")}),
    (R061, {**BASE_061, "actual_interval_hours": True}),
    (R061, {**BASE_061, "actual_interval_hours": 10**400}),
    (R061, {**BASE_061, "discharge_time_source": []}),
    (R062, {"verification_kind": "discharge_medication_extraction_pending", "extraction_state": []}),
    (R063, {"verification_kind": "discharge_diagnosis_data_gap", "authoritative_gap": [], "written_gap": None}),
    (R067, {"verification_kind": "predischarge_course_presence_check", **WINDOW, "course_present": 1}),
    (R068, {"verification_kind": "senior_discharge_approval_present", **WINDOW,
            "checked_source": [], "approval_present": True, "approval_path": "senior_approval"}),
])
def test_published_discharge_pollution_rejected(rid, raw):
    assert validate_published_discharge_facts(rule_id=rid, raw=raw) is None
