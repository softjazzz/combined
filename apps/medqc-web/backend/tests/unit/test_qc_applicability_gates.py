from __future__ import annotations

from typing import Any

import pytest

from app.services.qc_applicability_gates import GateDecision, run_applicability_gate
from app.services.qc_result_adjudicator import adjudicate_postprocessed_qc_results
from app.services.qc_result_postprocessor import postprocess_qc_result


def _sc123_result(evidence: str, *, findings: str = "出院带药信息不完整。") -> dict[str, Any]:
    return {
        "rule_id": "SC-123",
        "rule_name": "出院带药信息不完整",
        "status": "non_compliant",
        "findings": findings,
        "evidence": evidence,
        "supporting_quote": evidence,
        "confidence": 0.8,
        "metadata": {},
    }


def test_non_sc123_rule_should_return_no_action() -> None:
    gate = run_applicability_gate({"rule_id": "SC-036", "evidence": "异常结果已记录。"})

    assert gate.gate_decision == GateDecision.NO_ACTION
    assert gate.confirmed_allowed is False


def test_sc123_without_discharge_medication_should_reject() -> None:
    gate = run_applicability_gate(
        _sc123_result("1、合理饮食，注意休养；2、出院后定期复查；3、若有不适，及时就诊。")
    )

    assert gate.gate_decision == GateDecision.REJECTED_BY_SYSTEM
    assert gate.confirmed_allowed is False
    assert gate.metadata["discharge_medication_trigger_status"] == "absent"


def test_sc123_short_or_admission_fragment_should_be_data_gap() -> None:
    gate = run_applicability_gate(_sc123_result("患者李某，性别女，以腹痛5小时余为主诉入院。"))

    assert gate.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert gate.confirmed_allowed is False


def test_sc123_explicit_discharge_medication_missing_route_should_pass_to_second_gate() -> None:
    gate = run_applicability_gate(_sc123_result("出院带药:大活络1天3次,1次4粒;云南白药胶囊1天3次,1次2粒。"))

    assert gate.gate_decision == GateDecision.PASS_TO_SECOND_GATE
    assert gate.needs_second_pass_gate is True
    assert gate.confirmed_allowed is False
    assert "用法/途径" in gate.metadata["missing_medication_fields"]


def test_sc123_complete_discharge_medication_should_reject() -> None:
    gate = run_applicability_gate(_sc123_result("出院带药：神农镇痛膏 1贴 外用 bid*7天。"))

    assert gate.gate_decision == GateDecision.REJECTED_BY_SYSTEM
    assert gate.confirmed_allowed is False
    assert gate.applicability.value == "applicable"
    assert gate.metadata["applicability_status"] == "applicable_no_defect"
    assert gate.metadata["defect_absent"] is True


def test_sc123_contextual_weak_medication_should_not_confirm_directly() -> None:
    gate = run_applicability_gate(
        _sc123_result("1.继续局部用药：妥布霉素地塞米松眼液、左氧氟沙星滴眼液、普拉洛芬滴眼（一天三次）。")
    )

    assert gate.gate_decision == GateDecision.PASS_TO_SECOND_GATE
    assert gate.metadata["trigger_strength"] == "contextual_weak"
    assert gate.confirmed_allowed is False


def test_sc123_gate_should_never_allow_direct_confirmed() -> None:
    samples = [
        "1、合理饮食，注意休养，定期复查。",
        "患者李某，性别女，以腹痛5小时余为主诉入院。",
        "出院带药:大活络1天3次,1次4粒。",
        "出院带药：神农镇痛膏 1贴 外用 bid*7天。",
    ]

    for evidence in samples:
        gate = run_applicability_gate(_sc123_result(evidence))
        assert gate.gate_decision.value != "confirmed_defect"
        assert gate.confirmed_allowed is False


@pytest.mark.asyncio
async def test_terminal_gate_result_should_not_be_promoted_by_adjudicator() -> None:
    processed = postprocess_qc_result(
        _sc123_result("1、合理饮食，注意休养；2、出院后定期复查；3、若有不适，及时就诊。"),
        mode="formal_final_online",
    )
    called = False

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        nonlocal called
        called = True
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"items":[{"index":0,"rule_id":"SC-123",'
                            '"adjudicated_display_status":"confirmed_defect",'
                            '"adjudicator_reason":"伪造确认",'
                            '"adjudicator_supporting_quote":"伪造引用足够长",'
                            '"adjudicator_confidence":0.9,'
                            '"rule_requirement_match":"matched"}]}'
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results([processed], llm_generate=_fake_generate)

    assert called is False
    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_pass_to_second_gate_can_still_be_adjudicated_without_direct_gate_confirm() -> None:
    processed = postprocess_qc_result(
        _sc123_result("出院带药:大活络1天3次,1次4粒;云南白药胶囊1天3次,1次2粒。"),
        mode="formal_final_online",
    )
    assert processed["display_status"] == "qc_review_candidate"
    assert processed["applicability_gate_confirmed_allowed"] is False

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"items":[{"index":0,"rule_id":"SC-123",'
                            '"adjudicated_display_status":"data_quality_gap",'
                            '"adjudicator_reason":"缺完整出院带药上下文",'
                            '"adjudicator_supporting_quote":"出院带药:大活络1天3次",'
                            '"adjudicator_confidence":0.7,'
                            '"rule_requirement_match":"data_gap"}]}'
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results([processed], llm_generate=_fake_generate)

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["can_show_as_defect"] is False
