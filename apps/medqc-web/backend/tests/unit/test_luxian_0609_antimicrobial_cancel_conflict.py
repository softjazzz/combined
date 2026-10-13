"""N-05 取消医嘱与明确实际给药冲突：合成正式链，仅用人工语义替身，不调用真实模型。"""
import pytest
from antimicrobial_effect_test_support import FrozenAntimicrobialEffectClient

from test_luxian_0609_antimicrobial_audit_regressions import _rows
from test_luxian_0609_native_extended_document_execution import (
    _session,
    _canonical_extended_result,
    execute_luxian_0609_native_extended_document_rules,
    bind_and_reduce_luxian_0609_rule_decisions,
)


async def _final(suffix, content, *, senior=False):
    rule = "LX0609-05-01-" + suffix
    rows = _rows(content, status="已取消")
    rows["daily_course_record"][0]["related_order_id"] = "syn-1"
    if senior:
        rows["senior_course_record"] = rows.pop("daily_course_record")
    rows["evaluation_context.horizon"] = ({
        "horizon_date": "2099-01-01", "basis": "evaluation_as_of",
    },)
    snapshot, materials = _session(rows)
    client = FrozenAntimicrobialEffectClient() if suffix == "03" else None
    result = await execute_luxian_0609_native_extended_document_rules(
        rule_ids=(rule,), evidence_snapshot=snapshot,
        evidence_materials=materials, decision_rule_ids=(rule,), llm_client=client,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=result.decisions, expected_rule_ids=(rule,),
        snapshot=snapshot, evidence_materials=materials,
    )
    final = _canonical_extended_result(
        rule_id=rule, snapshot=snapshot, materials=materials,
        result=result, reduced=reduced,
    )
    if client is not None:
        assert client.fixture_error is None, client.fixture_error
        assert result.llm_call_count == len(client.calls)
        assert result.prompt_tokens == len(client.calls) * 10
        assert result.completion_tokens == len(client.calls) * 5
        assert result.total_tokens == len(client.calls) * 15
    else:
        assert result.llm_call_count == 0
    return final


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix,content,senior", [
    ("06", "给予美罗培南抗感染治疗。", True),
    ("03", "已予美罗培南静滴抗感染。", False),
])
async def test_am3b_am3c_actual_administration_survives_cancel(suffix, content, senior):
    final = await _final(suffix, content, senior=senior)
    assert final["status"] == "non_compliant"
    assert final["reason_code"] != "trigger_absent_complete"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [
    "拟给予美罗培南抗感染治疗。",
    "计划给予美罗培南抗感染治疗。",
    "建议给予美罗培南抗感染治疗。",
    "应给予美罗培南抗感染治疗。",
    "需给予美罗培南抗感染治疗。",
    "准备给予美罗培南抗感染治疗。",
    "待给予美罗培南抗感染治疗。",
    "计划今日给予美罗培南抗感染治疗。",
    "未给予美罗培南抗感染治疗。",
    "尚未实际给予美罗培南。",
    "并非已予美罗培南静滴。",
    "美罗培南医嘱取消，未实际给药。",
    "既往给予美罗培南抗感染治疗。",
])
@pytest.mark.parametrize("suffix", ["03", "05", "06"])
async def test_cancelled_plan_or_negative_stays_not_applicable(content, suffix):
    final = await _final(suffix, content, senior=True)
    assert final["status"] == "not_applicable"


@pytest.mark.asyncio
async def test_actual_empiric_treatment_keeps_normal_compliant_decision():
    final = await _final(
        "05", "已予美罗培南经验性抗感染治疗，考虑感染。",
    )
    assert final["status"] == "compliant"


@pytest.mark.asyncio
async def test_plan_clause_does_not_hide_later_actual_administration():
    final = await _final(
        "03", "拟给予美罗培南，随后已予美罗培南静滴抗感染。",
    )
    assert final["status"] == "non_compliant"


@pytest.mark.asyncio
async def test_current_infection_assessment_is_not_a_plan_marker():
    final = await _final("05", "考虑感染已予美罗培南经验性抗感染治疗。")
    assert final["status"] == "compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [
    "予以美罗培南静滴抗感染。",
    "予以美罗培南输注抗感染。",
    "已予以美罗培南静滴抗感染。",
])
async def test_yuyi_actual_administration_survives_cancel(content):
    final = await _final("03", content)
    assert final["status"] == "non_compliant"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [
    "未予以美罗培南静滴。",
    "拟予以美罗培南输注。",
    "未曾给予美罗培南。",
    "美罗培南取消，已使用阿莫西林抗感染。",
    "美罗培南取消后已使用阿莫西林抗感染。",
])
async def test_yuyi_plan_negative_and_other_drug_do_not_prove_target_use(content):
    final = await _final("03", content)
    assert final["status"] == "not_applicable"
