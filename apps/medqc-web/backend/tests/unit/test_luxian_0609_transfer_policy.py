"""基线072/073：重复转科医嘱与提前转出记录的合成边界。"""

import pytest

from test_luxian_0609_native_extended_document_execution import (
    _evaluate_selected, _canonical_extended_result,
)


def order(moment, target="外科", identifier="O1"):
    return {"document_id": identifier, "order_name": f"转入{target}",
            "prescribed_datetime": moment}


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ("LX0609-10-02-01", "LX0609-10-02-02"))
async def test_duplicate_transfer_orders_merge_and_bind_all_source_rows(rule):
    rows = {
        "inpat_nondrug_order": (order("2026-06-01 08:00:00"), order("2026-06-02 08:00:00", identifier="O2")),
        "transfer_in_record": ({"document_id": "IN", "record_time": "2026-06-02 08:30:00"},),
        "transfer_out_record": ({"document_id": "OUT", "record_time": "2026-06-01 09:00:00"},),
    }
    snapshot, materials, execution, reduced = await _evaluate_selected((rule,), rows)
    expected = ("non_compliant", "threshold_exceeded") if rule.endswith("01") else ("compliant", "requirement_satisfied")
    assert (reduced[0].final_state.value, reduced[0].reason_code) == expected
    assert dict(execution.customer_display_facts)[rule]["transfer_order_time"] == "2026-06-01 08:00:00"
    refs = {ref for source in rows for ref, _ in materials.document_rows(source, snapshot=snapshot)}
    assert refs == set(execution.decisions[0].fact_refs)
    result = _canonical_extended_result(rule_id=rule, snapshot=snapshot, materials=materials,
                                        result=execution, reduced=reduced)
    assert (result["status"], result["reason_code"]) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", ("LX0609-10-02-01", "LX0609-10-02-02"))
@pytest.mark.parametrize("hours", (1, 24))
async def test_unique_early_transfer_out_with_matching_department_is_compliant(rule, hours):
    moment = "2026-05-31 08:00:00" if hours == 24 else "2026-06-01 07:00:00"
    snapshot, materials, execution, reduced = await _evaluate_selected((rule,), {
        "inpat_nondrug_order": (order("2026-06-01 08:00:00"),),
        "transfer_in_record": ({"document_id": "IN", "record_time": "2026-06-01 09:00:00"},),
        "transfer_out_record": ({"document_id": "OUT", "record_time": moment, "transferin_department": "外科"},),
    })
    assert reduced[0].final_state.value == "compliant"
    result = _canonical_extended_result(rule_id=rule, snapshot=snapshot, materials=materials,
                                        result=execution, reduced=reduced)
    assert result["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("out_rows", (
    ({"record_time": "2026-06-01 07:00:00", "transferin_department": "内科"},),
    ({"record_time": "2026-06-01 07:00:00", "transferin_department": "外科"},
     {"record_time": "2026-06-01 06:00:00", "transferin_department": "外科"}),
))
async def test_early_transfer_out_department_mismatch_or_multiple_candidates_remain_gap(out_rows):
    _, _, _, reduced = await _evaluate_selected(("LX0609-10-02-01",), {
        "inpat_nondrug_order": (order("2026-06-01 08:00:00"),),
        "transfer_in_record": ({"record_time": "2026-06-01 09:00:00"},),
        "transfer_out_record": out_rows,
    })
    assert (reduced[0].final_state.value, reduced[0].reason_code) == ("data_gap", "association_failed")


@pytest.mark.asyncio
@pytest.mark.parametrize("second_target,second_time", (("内科", "2026-06-02 08:00:00"), ("外科", "2026-06-02 08:00:01")))
async def test_distinct_target_or_gap_over_24_hours_keeps_two_transfers(second_target, second_time):
    _, _, execution, reduced = await _evaluate_selected(("LX0609-10-02-02",), {
        "inpat_nondrug_order": (order("2026-06-01 08:00:00"), order(second_time, second_target, "O2")),
        # 窗口相接（恰好 24 小时）时，记录须按科室唯一对应其中一次转科才能逐次核对。
        "transfer_in_record": ({"record_time": "2026-06-02 09:00:00", "transferin_department": second_target},),
        "transfer_out_record": ({"record_time": "2026-06-02 08:30:00", "transferin_department": second_target},),
    })
    assert reduced[0].final_state.value == "non_compliant"
    assert len(dict(execution.customer_display_facts)["LX0609-10-02-02"]["event_checks"]) == 2


@pytest.mark.asyncio
async def test_intervening_transfer_in_prevents_same_target_order_merge():
    _, _, execution, reduced = await _evaluate_selected(("LX0609-10-02-02",), {
        "inpat_nondrug_order": (order("2026-06-01 08:00:00"), order("2026-06-01 20:00:00", identifier="O2")),
        "transfer_in_record": ({"record_time": "2026-06-01 09:00:00"},),
        "transfer_out_record": ({"record_time": "2026-06-01 08:30:00"},),
    })
    # 中间有转入记录不合并；两次同目标、窗口重叠且记录无法按科室唯一对应，不拆分判缺文书。
    assert (reduced[0].final_state.value, reduced[0].reason_code) == ("data_gap", "association_failed")
