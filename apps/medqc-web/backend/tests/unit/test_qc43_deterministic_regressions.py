"""固定9872审查反例：纯合成输入，不读取临床库或调用模型。"""
from datetime import date, datetime

import pytest

from app.services.luxian_0609.course_quality.rules_008_009 import _severity_active_date_intervals
from app.services.luxian_0609.extended_document.transfer_documentation import evaluate_transfer_documentation
from app.services.luxian_0609.extended_document.rule_076 import death_time_from_body
from app.services.luxian_0609.extended_document.physician_handoff import evaluate_physician_handoff
from app.services.luxian_0609.native_extended_document_execution import _discharge_approval_path


def test_overlapping_severity_stop_does_not_end_other_order():
    rows = (
        {"planned_start_datetime": "2026-01-01 09:00:00", "lifecycle_state": "ongoing"},
        {"planned_start_datetime": "2026-01-02 09:00:00", "lifecycle_state": "stopped",
         "planned_end_datetime": "2026-01-03 09:00:00"},
    )
    assert _severity_active_date_intervals(rows, horizon_date=date(2026, 1, 8)) == ((date(2026, 1, 1), date(2026, 1, 8)),)


@pytest.mark.parametrize("rule", ("LX0609-10-02-01", "LX0609-10-02-02"))
def test_current_transfer_record_department_conflict_is_not_matched(rule):
    outcome = evaluate_transfer_documentation(
        rule_id=rule, nondrug_order_error="", transfer_in_error="", transfer_out_error="",
        nondrug_order_rows=({"order_name": "转入心内科", "prescribed_datetime": "2026-01-01 10:00:00"},),
        transfer_in_rows=({"record_time": "2026-01-01 11:00:00", "transferin_department": "骨科"},),
        transfer_out_rows=({"record_time": "2026-01-01 12:00:00", "transferin_department": "骨科"},),
    )
    assert (outcome.final_state, outcome.reason_code) == ("data_gap", "association_failed")


def test_chinese_death_datetime_without_space_is_valid():
    assert death_time_from_body({"record_content": "死亡时间：2026年01月01日10时30分。"}) == datetime(2026, 1, 1, 10, 30)


@pytest.mark.parametrize("body", (
    "患者要求自动出院，未请示上级医师，已签署自动出院告知书。",
    "患者要求自动出院，拟请示上级医师，已签署自动出院告知书。",
))
def test_automatic_discharge_requires_affirmative_consult(body):
    assert _discharge_approval_path({"record_content": body}, source_key="daily_course_record") is None


@pytest.mark.parametrize("name,status", (("更换经治医师", "取消"), ("拟更换经治医师", "")))
def test_cancelled_or_planned_physician_change_is_not_an_actual_event(name, status):
    result = evaluate_physician_handoff(
        physician_change_rows=(), physician_change_error="",
        nondrug_order_rows=({"order_name": name, "order_status": status, "prescribed_datetime": "2026-01-01 10:00:00"},),
        nondrug_order_error="", daily_course_rows=(), daily_course_error="",
        handoff_rows=(), handoff_error="", handover_rows=(), handover_error="",
        evaluation_horizon_datetime=datetime(2026, 1, 4),
    )
    assert result.final_state == "not_applicable"
