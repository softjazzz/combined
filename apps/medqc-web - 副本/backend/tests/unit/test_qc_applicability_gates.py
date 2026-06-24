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


def _sc099_result(*, visit_id: str = "v-sc099") -> dict[str, Any]:
    return {
        "rule_id": "SC-099",
        "rule_name": "术中取材情况和病理结果未在手术记录中记录",
        "status": "non_compliant",
        "findings": "手术记录未记录术中取材情况和病理结果。",
        "evidence": "【当前文书】记录时间: 2026-01-01 10:00:00",
        "record_id": visit_id,
        "confidence": 0.8,
        "metadata": {},
    }


def _sc099_context(
    surgery_text: str = "",
    *,
    pathology_text: str = "",
    postsurg_text: str = "",
    surgery_count: int = 1,
) -> dict[str, Any]:
    source_counts: dict[str, int] = {"surgery_record": surgery_count}
    documents: list[dict[str, Any]] = []
    if surgery_count and surgery_text:
        documents.append({"source_table": "surgery_record", "text": surgery_text})
    if postsurg_text:
        source_counts["postsurg_firstcourse_record"] = 1
        documents.append({"source_table": "postsurg_firstcourse_record", "text": postsurg_text})
    if pathology_text:
        source_counts["pathology_exam_report"] = 1
        documents.append({"source_table": "pathology_exam_report", "text": pathology_text})
    return {
        "source_table_counts": source_counts,
        "source_documents": documents,
    }


def _sc083_result(*, visit_id: str = "v-sc083") -> dict[str, Any]:
    return {
        "rule_id": "SC-083",
        "rule_name": "四级手术术前讨论未多学科讨论",
        "status": "non_compliant",
        "findings": "四级手术术前讨论未体现 MDT。",
        "evidence": "术前讨论记录片段。",
        "record_id": visit_id,
        "confidence": 0.8,
        "metadata": {},
    }


def _sc083_code_context(*, level4: bool = True) -> dict[str, Any]:
    if level4:
        return {
            "visit_id": "v-sc083",
            "visit_max_level": "4",
            "visit_level4_evidence_code": "00.8000x001",
            "visit_level4_evidence_name": "四级测试手术",
            "visit_level4_evidence_source_table": "mr_surgery",
            "strong_match_type": "code_exact",
            "sc083_applicability": "applicable_level4_by_code",
        }
    return {
        "visit_id": "v-sc083",
        "visit_max_level": "<=3",
        "strong_match_type": "code_exact",
        "sc083_applicability": "not_applicable_level3_by_code",
    }


def _sc083_context(*, code_level4: bool = True, documents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "sc083_code_gate_context": _sc083_code_context(level4=code_level4),
        "source_documents": documents or [],
    }


def test_non_sc123_rule_should_return_no_action() -> None:
    gate = run_applicability_gate({"rule_id": "SC-036", "evidence": "异常结果已记录。"})

    assert gate.gate_decision == GateDecision.NO_ACTION
    assert gate.confirmed_allowed is False


def test_non_registered_rule_should_return_no_action() -> None:
    gate = run_applicability_gate({"rule_id": "SC-100", "evidence": "植入物条码缺失。"})

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
    assert gate.metadata["discharge_medication_matrix"]
    assert gate.metadata["discharge_medication_matrix"][0]["source_quote"]


def test_sc123_complete_discharge_medication_should_reject() -> None:
    gate = run_applicability_gate(_sc123_result("出院带药：神农镇痛膏 1贴 外用 bid*7天。"))

    assert gate.gate_decision == GateDecision.REJECTED_BY_SYSTEM
    assert gate.confirmed_allowed is False
    assert gate.applicability.value == "applicable"
    assert gate.metadata["applicability_status"] == "applicable_no_defect"
    assert gate.metadata["defect_absent"] is True
    assert gate.metadata["discharge_medication_matrix"][0]["missing_fields"] == []


def test_sc123_complete_core_fields_from_discharge_context_should_reject() -> None:
    context = {
        "source_documents": [
            {
                "source_table": "discharge_record",
                "document_type": "出院记录",
                "text": (
                    "出院医嘱：1、避免使用非甾体抗炎药，注意休息。"
                    "2、出院带药:替普瑞酮胶囊(50mg*36粒),剂量:1,剂量单位:粒,服用方法:口服,频率:Tid;"
                    "胶体果胶铋干混悬剂(0.15g*12袋) 每天4次 口服 每次1包。"
                ),
            }
        ]
    }

    gate = run_applicability_gate(_sc123_result("出院带药记录不详细。"), context)

    assert gate.gate_decision == GateDecision.REJECTED_BY_SYSTEM
    assert gate.metadata["medication_fields_complete"] is True
    assert gate.metadata["core_missing_medication_fields"] == []
    assert gate.confirmed_allowed is False


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


def test_sc099_without_surgery_record_should_be_data_gap() -> None:
    gate = run_applicability_gate(_sc099_result(), _sc099_context(surgery_count=0))

    assert gate.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert gate.confirmed_allowed is False
    assert gate.metadata["data_gap_reason"] == "surgery_record_missing"


def test_sc099_without_pathology_trigger_should_reject() -> None:
    gate = run_applicability_gate(
        _sc099_result(),
        _sc099_context(
            "手术经过: 麻醉成功后常规消毒铺巾，完成脑血管造影，术中生命体征平稳，术毕安返病房。"
            "穿刺右侧股动脉后置入动脉鞘，导管在导丝引导下完成造影检查，观察血管显影情况，"
            "撤出导管后压迫止血，术中未出现特殊情况，术后返回病房继续观察。"
            "手术记录完整描述麻醉、消毒、穿刺、造影、压迫止血和安返病房过程。"
        ),
    )

    assert gate.gate_decision == GateDecision.REJECTED_BY_SYSTEM
    assert gate.confirmed_allowed is False
    assert gate.metadata["trigger_status"] == "absent"


def test_sc099_short_surgery_fragment_should_be_data_gap() -> None:
    gate = run_applicability_gate(_sc099_result(), _sc099_context("记录时间: 2026-01-01 手术项目: 肿物切除术"))

    assert gate.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert gate.confirmed_allowed is False


def test_sc099_pathology_source_should_pass_to_second_gate() -> None:
    gate = run_applicability_gate(
        _sc099_result(),
        _sc099_context(
            "手术经过: 常规消毒铺巾后完成手术，术中生命体征平稳，术毕安返病房。",
            pathology_text="病理诊断: 胃黏膜慢性炎，标本名称: 胃黏膜。",
        ),
    )

    assert gate.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert gate.needs_second_pass_gate is False
    assert gate.confirmed_allowed is False
    assert gate.metadata["trigger_strength"] == "strong"
    assert gate.metadata["pathology_linkage_context"]["linkage_status"] == "pathology_only"


def test_sc099_linked_surgery_and_pathology_should_pass_to_second_gate() -> None:
    gate = run_applicability_gate(
        _sc099_result(),
        _sc099_context(
            "手术经过: 切除标本向家属展示后送病检，术中生命体征平稳。",
            pathology_text="标本名称: 阑尾。病理诊断: 急性阑尾炎。",
        ),
    )

    assert gate.gate_decision == GateDecision.PASS_TO_SECOND_GATE
    assert gate.needs_second_pass_gate is True
    assert gate.confirmed_allowed is False
    linkage = gate.metadata["pathology_linkage_context"]
    assert linkage["linkage_status"] == "linked"
    assert linkage["surgery_specimen_quote"]
    assert linkage["pathology_diagnosis_quote"]


def test_sc099_specimen_trigger_should_pass_to_second_gate() -> None:
    gate = run_applicability_gate(
        _sc099_result(),
        _sc099_context("手术经过: 切除标本向家属展示后送病检，术中生命体征平稳，术毕安返病房。"),
    )

    assert gate.gate_decision == GateDecision.PASS_TO_SECOND_GATE
    assert gate.needs_second_pass_gate is True
    assert gate.confirmed_allowed is False
    assert gate.metadata["pathology_linkage_context"]["linkage_status"] == "surgery_trigger_only"


def test_sc099_weak_surgery_name_only_should_not_be_strong_trigger() -> None:
    gate = run_applicability_gate(
        _sc099_result(),
        _sc099_context(
            "手术项目: 肿物切除术。手术经过: 麻醉成功后常规消毒铺巾，显露术野后完成操作，止血后缝合。"
        ),
    )

    assert gate.gate_decision == GateDecision.DATA_QUALITY_GAP
    assert gate.confirmed_allowed is False
    assert gate.metadata["trigger_strength"] == "contextual_weak"


def test_sc099_gate_should_never_allow_direct_confirmed() -> None:
    samples = [
        _sc099_context("手术经过: 常规操作后结束手术，术后安返病房。"),
        _sc099_context("手术项目: 肿物切除术。手术经过: 常规消毒后切开、止血、缝合。"),
        _sc099_context("手术经过: 切除标本向家属展示后送病检。"),
        _sc099_context("手术经过: 常规操作。", pathology_text="病理诊断: 炎症。"),
    ]

    for context in samples:
        gate = run_applicability_gate(_sc099_result(), context)
        assert gate.gate_decision.value != "confirmed_defect"
        assert gate.confirmed_allowed is False


def test_sc083_level3_code_should_reject() -> None:
    gate = run_applicability_gate(
        _sc083_result(),
        _sc083_context(code_level4=False, documents=[]),
    )

    assert gate.gate_decision == GateDecision.REJECTED_BY_SYSTEM
    assert gate.confirmed_allowed is False
    assert gate.metadata["mdt_evidence_status"] == "level4_not_applicable_by_code"


def test_sc083_level4_with_multidisciplinary_consult_should_reject_not_confirm() -> None:
    gate = run_applicability_gate(
        _sc083_result(),
        _sc083_context(
            documents=[
                {
                    "source_table": "consultation_record",
                    "document_title": "多学科会诊记录",
                    "text": "主持人：张主任。会诊原因：四级手术术前评估。讨论结论：完善准备后手术。",
                }
            ]
        ),
    )

    assert gate.gate_decision == GateDecision.REJECTED_BY_SYSTEM
    assert gate.confirmed_allowed is False
    assert gate.metadata["mdt_equivalent_by_customer_policy"] is True


def test_sc083_level4_with_multi_department_consults_should_reject_not_confirm() -> None:
    gate = run_applicability_gate(
        _sc083_result(),
        _sc083_context(
            documents=[
                {"source_table": "consultation_record", "text": "麻醉科意见：完善术前麻醉评估。"},
                {"source_table": "consultation_record", "text": "呼吸内科意见：加强肺功能评估。"},
            ]
        ),
    )

    assert gate.gate_decision == GateDecision.REJECTED_BY_SYSTEM
    assert gate.confirmed_allowed is False
    assert set(gate.metadata["departments_detected"]) >= {"麻醉科", "呼吸内科"}


def test_sc083_level4_with_single_department_consult_should_pass_to_second_gate() -> None:
    gate = run_applicability_gate(
        _sc083_result(),
        _sc083_context(
            documents=[
                {"source_table": "consultation_record", "text": "麻醉科意见：完善术前麻醉评估。"},
            ]
        ),
    )

    assert gate.gate_decision == GateDecision.PASS_TO_SECOND_GATE
    assert gate.needs_second_pass_gate is True
    assert gate.confirmed_allowed is False


def test_sc083_level4_without_mdt_documents_should_be_data_gap() -> None:
    gate = run_applicability_gate(_sc083_result(), _sc083_context(documents=[]))

    assert gate.gate_decision == GateDecision.DATA_QUALITY_GAP
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
async def test_sc099_terminal_gate_result_should_not_be_promoted_by_adjudicator() -> None:
    processed = postprocess_qc_result(
        _sc099_result(),
        bundle_metadata=_sc099_context(
            "手术经过: 麻醉成功后常规消毒铺巾，完成脑血管造影，术中生命体征平稳，术毕安返病房。"
            "穿刺右侧股动脉后置入动脉鞘，导管在导丝引导下完成造影检查，撤出导管后压迫止血，"
            "术中未出现特殊情况，术后返回病房继续观察。手术记录完整描述麻醉、消毒、穿刺、"
            "造影、压迫止血和安返病房过程。"
        ),
        mode="formal_final_online",
    )
    called = False

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"choices": [{"message": {"content": '{"items":[]}'}}]}

    rows = await adjudicate_postprocessed_qc_results([processed], llm_generate=_fake_generate)

    assert called is False
    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_sc083_mdt_equivalent_terminal_result_should_not_be_promoted_by_adjudicator() -> None:
    processed = postprocess_qc_result(
        _sc083_result(),
        bundle_metadata=_sc083_context(
            documents=[
                {
                    "source_table": "consultation_record",
                    "document_title": "多科会诊记录",
                    "text": "麻醉科意见：评估麻醉风险。心血管内科意见：控制血压后手术。",
                }
            ]
        ),
        mode="formal_final_online",
    )
    called = False

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"choices": [{"message": {"content": '{"items":[]}'}}]}

    rows = await adjudicate_postprocessed_qc_results([processed], llm_generate=_fake_generate)

    assert called is False
    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["can_show_as_defect"] is False
    assert rows[0]["applicability_gate_confirmed_allowed"] is False


@pytest.mark.asyncio
async def test_sc099_pass_to_second_gate_can_still_be_adjudicated() -> None:
    processed = postprocess_qc_result(
        _sc099_result(),
        bundle_metadata=_sc099_context("手术经过: 切除标本向家属展示后送病检。"),
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
                            '{"items":[{"index":0,"rule_id":"SC-099",'
                            '"adjudicated_display_status":"data_quality_gap",'
                            '"adjudicator_reason":"缺完整手术记录与病理报告对照",'
                            '"adjudicator_supporting_quote":"切除标本向家属展示后送病检",'
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
