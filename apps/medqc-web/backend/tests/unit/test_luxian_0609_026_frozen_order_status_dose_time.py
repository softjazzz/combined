"""026 冻结预期中的确定性口径：医嘱状态、剂量单位别名、提交时间不代替临床时间。

输入与预期来自 .tmp/engine-audit-20261008/tumor-pathology/expectations.json（原始冻结）。
"""
from __future__ import annotations

import pytest

from test_luxian_0609_chemo_closure import ORDER, _course, _run


def _order(**overrides):
    return {**ORDER, **overrides}


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["取消", "撤销", "作废"])
async def test_void_chemotherapy_order_is_not_applicable(status):
    _execution, reduced, final = await _run(
        _course("2026-04-26 使用奥沙利铂130mg 静滴。"), order=_order(order_status=status),
    )
    assert reduced.final_state.value == final["status"] == "not_applicable"


@pytest.mark.asyncio
async def test_planned_chemotherapy_order_cannot_prove_administration():
    _execution, _reduced, final = await _run(
        _course("2026-04-26 未给予奥沙利铂130mg 静滴。"), order=_order(order_status="拟执行"),
    )
    assert final["status"] == "data_gap"


@pytest.mark.asyncio
async def test_void_order_does_not_hide_other_valid_order():
    valid = ORDER
    void = _order(document_id="void-order", order_status="取消", single_dose="200")
    _execution, _reduced, final = await _run(
        _course("2026-04-26 使用奥沙利铂130mg 静滴。"), orders=[valid, void],
    )
    assert final["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("dose", ["130毫克", "0.13g"])
async def test_equal_mass_in_other_unit_is_data_gap_not_mismatch(dose):
    execution, _reduced, final = await _run(_course(f"2026-04-26 使用奥沙利铂 {dose} 静滴。"))
    assert final["status"] == "data_gap"
    assert final["customer_display_facts"]["field_results"]["dose"] == "unknown"


@pytest.mark.asyncio
async def test_different_mass_in_other_unit_remains_mismatch():
    _execution, _reduced, final = await _run(_course("2026-04-26 使用奥沙利铂 0.12g 静滴。"))
    assert final["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_submit_time_cannot_bind_relative_date():
    rows = [{"document_id": "synthetic-chemo-course", "record_content": "今日使用奥沙利铂130mg 静滴。",
             "submit_datetime": "2026-04-26 16:00:00"}]
    _execution, _reduced, final = await _run(rows)
    assert final["status"] == "data_gap"
