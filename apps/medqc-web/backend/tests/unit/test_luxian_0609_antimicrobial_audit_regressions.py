"""抗菌药独立审查的合成反例；不调用真实模型。"""
import pytest

from test_luxian_0609_native_extended_document_execution import _evaluate


def _rows(content, *, status="已执行"):
    return {
        "inpat_drug_order": ({
            "order_id": "syn-1", "generic_name": "美罗培南",
            "drug_apply_method": "静脉滴注", "order_status": status,
            "planned_start_datetime": "2026-04-01 08:00:00",
        },),
        "daily_course_record": ({
            "document_id": "syn-doc", "record_time": "2026-04-01 09:00:00",
            "record_content": content,
        },),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ("03", "05", "06"))
async def test_explicitly_cancelled_never_administered_is_not_applicable(suffix):
    rows = _rows(
        "拟使用美罗培南经验性抗感染治疗，患者拒绝，未实际给药。",
        status="已取消",
    )
    execution, decision = await _evaluate("LX0609-05-01-" + suffix, rows)
    assert decision.final_state.value == "not_applicable"
    assert execution.llm_call_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ("03", "06"))
async def test_no_adverse_reaction_does_not_cancel_actual_treatment(suffix):
    _, decision = await _evaluate(
        "LX0609-05-01-" + suffix,
        _rows("已给予美罗培南抗感染，未出现不良反应。"),
    )
    assert decision.final_state.value == "non_compliant"


@pytest.mark.asyncio
async def test_cancelled_order_does_not_remove_another_actual_order():
    rows = _rows("美罗培南医嘱取消，未实际给药。", status="已取消")
    rows["daily_course_record"][0]["related_order_id"] = "syn-1"
    rows["inpat_drug_order"] += ({
        "order_id": "syn-2", "generic_name": "美罗培南",
        "planned_start_datetime": "2026-04-02 08:00:00", "order_status": "已执行",
    },)
    _, decision = await _evaluate("LX0609-05-01-06", rows)
    assert decision.final_state.value == "non_compliant"


@pytest.mark.asyncio
async def test_explicit_never_used_is_not_an_affirmative_actual_use():
    _, decision = await _evaluate(
        "LX0609-05-01-03", _rows("美罗培南未实际使用。", status="新开")
    )
    assert decision.final_state.value == "not_applicable"


@pytest.mark.asyncio
async def test_cancelled_status_cannot_erase_explicit_actual_use():
    rows = _rows("已给予美罗培南抗感染治疗。", status="已取消")
    rows["senior_course_record"] = rows.pop("daily_course_record")
    _, decision = await _evaluate("LX0609-05-01-06", rows)
    assert decision.final_state.value == "non_compliant"


@pytest.mark.asyncio
async def test_stopped_order_is_not_never_administered():
    _, decision = await _evaluate(
        "LX0609-05-01-06", _rows("美罗培南现已停用。", status="已停止")
    )
    assert decision.final_state.value == "non_compliant"
