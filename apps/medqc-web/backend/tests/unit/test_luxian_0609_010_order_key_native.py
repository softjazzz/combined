"""010 缺医嘱键边界必须贯穿真实执行、绑定与最终客户结果。"""
import pytest

from test_luxian_0609_native_exam_lab_execution import _run_010_public_native


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("has_report", [False, True])
async def test_unidentified_order_preserves_proven_defect_or_gap(monkeypatch, reverse, has_report):
    orders = [
        {"order_id": "O1", "order_name": "CT", "prescribed_datetime": "2026-01-01 10:00:00"},
        {"order_name": "MRI", "prescribed_datetime": "2026-01-01 10:00:00"},
    ]
    if reverse:
        orders.reverse()
    result, decision, canonical, client = await _run_010_public_native(
        monkeypatch,
        order_rows=tuple(orders),
        exam_rows=({"order_id": "O1", "exam_id": "E1", "exam_type": "CT"},),
        exam_report_rows=({"exam_id": "E1"},) if has_report else (),
    )
    assert canonical["status"] == ("data_gap" if has_report else "non_compliant")
    assert decision.reason_code == ("association_failed" if has_report else "requirement_violated")
    assert canonical["reason_code"] == decision.reason_code
    assert not client.prompts
    assert result.llm_call_count == 0
    if not has_report:
        assert canonical["customer_display_facts"]["failure_kind"] == "exam_report_missing"
