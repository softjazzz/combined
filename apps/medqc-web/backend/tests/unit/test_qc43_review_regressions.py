"""复用固定728453复审反例，并保护动作局部否定、独立肯定及历史边界。"""
from datetime import datetime

import pytest

from app.services.luxian_0609.extended_document.physician_handoff import evaluate_physician_handoff
from app.services.luxian_0609.native_extended_document_execution import _discharge_approval_path
from test_luxian_0609_native_extended_document_execution import _evaluate, _DischargeApprovalClient, _approval_item
from test_round2_tumor_dose_discharge_boundaries import execute


@pytest.mark.asyncio
@pytest.mark.parametrize("body,expected", [
    ("出院后不需要定期随访。", "non_compliant"),
    ("未制定出院后肿瘤随访计划。", "non_compliant"),
    ("未制定出院后乳腺专科门诊随访计划。", "non_compliant"),
    ("出院后肿瘤随访计划尚未制定。", "non_compliant"),
    ("既往曾随访，建议出院后定期随访。", "compliant"),
    ("出院后暂不化疗但定期复查。", "compliant"),
    ("出院后不需要定期随访但建议定期复查。", "compliant"),
    ("出院后不需要定期随访及定期复查。", "non_compliant"),
    ("因患者不愿继续住院建议出院后定期随访。", "compliant"),
])
async def test_follow_up_denial_scope(body, expected):
    result = await execute("LX0609-08-01-04", discharge=body)
    assert result["status"] == expected


@pytest.mark.parametrize("action,expected", [
    ("因患者不愿继续住院已请示上级医师", "automatic_discharge"),
    ("因患者未同意继续住院现已请示上级医师", "automatic_discharge"),
    ("未能及时请示上级医师", None),
    ("尚未正式请示上级医师", None),
    ("拟于明日请示上级医师", None),
    ("拟行请示上级医师", None),
    ("取消请示上级医师", None),
    ("取消了请示上级医师", None),
    ("既往已请示上级医师", None),
    ("曾经请示上级医师", None),
    ("既往未请示上级医师但本次已请示上级医师", "automatic_discharge"),
])
def test_automatic_discharge_action_scope(action, expected):
    body = f"患者要求自动出院，{action}，已签署自动出院告知书。"
    assert _discharge_approval_path({"record_content": body}, source_key="daily_course_record") == expected


@pytest.mark.parametrize("signed", ["未签署", "拟签署", "取消签署", "既往已签署"])
def test_automatic_discharge_requires_current_signature(signed):
    body = f"患者要求自动出院，已请示上级医师，{signed}自动出院告知书。"
    assert _discharge_approval_path({"record_content": body}, source_key="daily_course_record") is None


@pytest.mark.parametrize("name,status,expected", [
    ("因原医师未到岗现更换经治医师", "执行", "non_compliant"),
    ("因原医师不在岗已更换经治医师", "执行", "non_compliant"),
    ("未更换经治医师", "执行", "not_applicable"),
    ("拟于明日更换经治医师", "执行", "not_applicable"),
    ("拟明日更换经治医师", "执行", "not_applicable"),
    ("拟行更换经治医师", "执行", "not_applicable"),
    ("取消更换经治医师", "执行", "not_applicable"),
    ("取消了更换经治医师", "执行", "not_applicable"),
    ("既往已更换经治医师", "执行", "not_applicable"),
    ("曾经更换经治医师", "执行", "not_applicable"),
    ("更换经治医师", "作废", "not_applicable"),
    ("更换经治医师", "未执行", "not_applicable"),
    ("既往未更换经治医师但现更换经治医师", "执行", "non_compliant"),
])
def test_physician_change_action_scope(name, status, expected):
    result = evaluate_physician_handoff(
        physician_change_rows=(), physician_change_error="",
        nondrug_order_rows=({"order_name": name, "order_status": status, "prescribed_datetime": "2026-01-01 10:00:00"},),
        nondrug_order_error="", daily_course_rows=(), daily_course_error="",
        handoff_rows=(), handoff_error="", handover_rows=(), handover_error="",
        evaluation_horizon_datetime=datetime(2026, 1, 4),
    )
    assert result.final_state == expected


@pytest.mark.asyncio
async def test_automatic_discharge_actual_executor():
    body = "患者要求自动出院，因患者不愿继续住院已请示上级医师，已签署自动出院告知书。"
    client = _DischargeApprovalClient(_approval_item("doc_01", opinion="patient_request", quote="患者要求自动出院"))
    _, result = await _evaluate("LX0609-08-02-02", {
        "inpat_registration": ({"patient_status": "出院", "discharge_datetime": "2026-07-03 12:00:00"},),
        "discharge_record": ({"record_time": "2026-07-03 12:00:00"},),
        "daily_course_record": ({"document_id": "d1", "record_time": "2026-07-03 08:00:00", "record_content": body},),
    }, llm_client=client)
    assert (result.final_state, result.reason_code) == ("compliant", "requirement_satisfied")
    assert len(client.calls) == 0
