from __future__ import annotations

import json
from typing import Any

import pytest

from app.services.qc_result_adjudicator import adjudicate_postprocessed_qc_results


@pytest.mark.asyncio
async def test_adjudicator_should_remove_qc_review_candidate_terminal_state():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        assert "待人工确认" in prompt
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-036",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "异常检验结果和后续未分析证据均成立。",
                                        "adjudicator_supporting_quote": "血钾2.9mmol/L；后续病程未见低钾处理。",
                                        "adjudicator_confidence": 0.86,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-036",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "异常检验未分析。",
                "evidence": "血钾2.9mmol/L；后续病程未见低钾处理。",
                "can_show_as_defect": False,
                "metadata": _daily_context("病程记录：患者一般情况可。", report_text="检验报告：血钾2.9mmol/L 降低。"),
            }
        ],
        llm_generate=_fake_generate,
        adjudicator_model_metadata={
            "first_pass_model": "qwen3.5-35b-a3b",
            "adjudicator_model": "qwen3.6-35b-a3b",
            "model_role": "adjudicator",
            "adjudicator_model_source": "env_adjudicator_model",
        },
    )

    assert rows[0]["first_pass_display_status"] == "qc_review_candidate"
    assert rows[0]["adjudicated_display_status"] == "confirmed_defect"
    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["can_show_as_defect"] is True
    assert rows[0]["display_bucket"] == "确认缺陷"
    assert rows[0]["first_pass_model"] == "qwen3.5-35b-a3b"
    assert rows[0]["adjudicator_model"] == "qwen3.6-35b-a3b"
    assert rows[0]["metadata"]["adjudicator_model"] == "qwen3.6-35b-a3b"


@pytest.mark.asyncio
async def test_adjudicator_should_not_leave_boundary_state_when_llm_unavailable():
    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-123",
                "status": "uncertain",
                "display_status": "qc_review_candidate",
                "findings": "证据不足。",
                "evidence": "当前病程记录仅见相关描述。",
            }
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "technical_error_internal"
    assert rows[0]["adjudicated_display_status"] == "technical_error_internal"
    assert rows[0]["can_show_as_defect"] is False
    assert rows[0]["internal_only"] is True


@pytest.mark.asyncio
async def test_adjudicator_should_convert_semantic_mapping_error_to_rejected():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-143",
                                        "adjudicated_display_status": "technical_error_internal",
                                        "adjudicator_reason": "第一轮LLM将病程记录内容错误匹配至长期医嘱单规则，属于逻辑映射错误。",
                                        "adjudicator_supporting_quote": "【当前文书】查房内容：今术后第三天。",
                                        "adjudicator_confidence": 1.0,
                                        "rule_requirement_match": "technical_error",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-143",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "长期医嘱单描述不清。",
                "evidence": "【当前文书】查房内容：今术后第三天。",
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["adjudicated_display_status"] == "rejected_by_system"
    assert rows[0]["rule_requirement_match"] == "not_matched"
    assert rows[0].get("technical_error_internal") is not True


@pytest.mark.asyncio
async def test_adjudicator_should_convert_unrelated_quote_technical_to_rejected():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-143",
                                        "adjudicated_display_status": "technical_error_internal",
                                        "adjudicator_reason": "第一轮输出引用的证据片段与长期医嘱单内容完全无关，属于解析或引用错误。",
                                        "adjudicator_supporting_quote": "【当前文书】今日查房:患者精神食欲一般。",
                                        "adjudicator_confidence": 1.0,
                                        "rule_requirement_match": "technical_error",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-143",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "长期医嘱单描述不清。",
                "evidence": "【当前文书】今日查房:患者精神食欲一般。",
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["adjudicated_display_status"] == "rejected_by_system"
    assert rows[0].get("technical_error_internal") is not True


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_downgrade_first_pass_confirmed_without_reason_quote():
    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-083",
                "status": "non_compliant",
                "display_status": "confirmed_defect",
                "findings": "四级手术术前讨论未体现多学科参与。",
                "evidence": "参与人员: 胡定祥主任医师 马晨曦副主任医师 黄河副主任医师",
                "can_show_as_defect": True,
            }
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["can_show_as_defect"] is False
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["original_adjudicated_display_status"] == "confirmed_defect"


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_keep_confirmed_with_reason_and_direct_quote():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-097",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "手术记录椎体深度出现明显异常数值，能够直接支撑描述不清。",
                                        "adjudicator_supporting_quote": "T12椎体深度分别为405mm、直径为6.5mm",
                                        "adjudicator_confidence": 0.92,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-097",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "手术记录存在明显数据错误。",
                "evidence": "T12椎体深度分别为405mm、直径为6.5mm",
                "can_show_as_defect": False,
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["can_show_as_defect"] is True
    assert rows[0].get("adjudicator_guardrail_failed") is not True


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_downgrade_sc019_without_outside_exam_trigger():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-019",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "辅助检查为空，怀疑未记录。",
                                        "adjudicator_supporting_quote": "辅助检查：",
                                        "adjudicator_confidence": 0.9,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-019",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "入院记录辅助检查未记录。",
                "evidence": "辅助检查：",
                "can_show_as_defect": False,
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_admission_record_source": True,
                        "has_source_report": False,
                        "has_admission_assist_exam_text": True,
                    }
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_downgrade_sc100_without_barcode_domain():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-100",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "手术记录存在植入物但未见条形码。",
                                        "adjudicator_supporting_quote": "植入椎弓根螺钉及连接棒内固定材料",
                                        "adjudicator_confidence": 0.9,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-100",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "植入物条形码不齐全。",
                "evidence": "植入椎弓根螺钉及连接棒内固定材料",
                "can_show_as_defect": False,
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_surgery_record": True,
                        "has_consumable_cross_source": True,
                        "has_barcode_source": False,
                        "has_implant_trigger": True,
                        "has_implant_barcode_source": False,
                    }
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_reject_sc099_without_specimen_trigger():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-099",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "手术记录未见病理结果。",
                                        "adjudicator_supporting_quote": "手术记录：胸椎骨折切开复位内固定术",
                                        "adjudicator_confidence": 0.9,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-099",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "术中取材和病理结果未记录。",
                "evidence": "手术记录：胸椎骨折切开复位内固定术",
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_specimen_or_pathology_trigger": False,
                        "has_pathology_source": False,
                        "specimen_pathology_coverage": "not_applicable",
                    }
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_reject_sc099_when_adjudicator_says_pathology_recorded():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-099",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "手术记录已记录术中取材及冰冻病理结果。",
                                        "adjudicator_supporting_quote": "手术记录：送检肿物及第7组淋巴结，冰冻病理提示恶性。",
                                        "adjudicator_confidence": 0.9,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-099",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "术中取材和病理结果未记录。",
                "evidence": "手术记录：送检肿物及第7组淋巴结，冰冻病理提示恶性。",
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_specimen_or_pathology_trigger": True,
                        "has_pathology_source": True,
                        "specimen_pathology_coverage": "documented",
                    },
                    "applicability_gate_metadata": {
                        "pathology_linkage_context": {
                            "linkage_status": "linked",
                            "surgery_specimen_quote": "手术记录：送检肿物及第7组淋巴结，冰冻病理提示恶性。",
                            "pathology_specimen_quote": "病理报告：第7组淋巴结见癌转移。",
                            "pathology_diagnosis_quote": "病理诊断：肺腺癌，淋巴结转移。",
                        }
                    },
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["adjudicated_display_status"] == "rejected_by_system"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False
    assert "已说明手术记录中存在取材" in rows[0]["adjudicator_guardrail_reason"]


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_reject_sc099_when_quote_records_specimen_and_frozen_pathology():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-099",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "手术记录记录了术中冰冻病理结果，但未记录术后石蜡病理最终结果。",
                                        "adjudicator_supporting_quote": (
                                            "手术记录：楔形切除左肺上叶结节，检查切缘无出血，"
                                            "家属看过标本后送检。术中冰冻病理提示浸润性腺癌。"
                                        ),
                                        "adjudicator_confidence": 0.91,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-099",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "术中取材和病理结果未记录。",
                "evidence": (
                    "手术记录：楔形切除左肺上叶结节，检查切缘无出血，家属看过标本后送检。"
                    "术中冰冻病理提示浸润性腺癌。"
                ),
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_specimen_or_pathology_trigger": True,
                        "has_pathology_source": True,
                        "specimen_pathology_coverage": "documented",
                    },
                    "applicability_gate_metadata": {
                        "pathology_linkage_context": {
                            "linkage_status": "linked",
                            "surgery_specimen_quote": (
                                "楔形切除左肺上叶结节，家属看过标本后送检。术中冰冻病理提示浸润性腺癌。"
                            ),
                            "pathology_specimen_quote": "术中冰冻病理提示浸润性腺癌。",
                            "pathology_diagnosis_quote": "病理诊断：浸润性腺癌。",
                        }
                    },
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["adjudicated_display_status"] == "rejected_by_system"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_mark_sc099_pathology_source_gap():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-099",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "骨髓穿刺存在取材线索但未见病理结果。",
                                        "adjudicator_supporting_quote": "骨髓穿刺术",
                                        "adjudicator_confidence": 0.9,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-099",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "术中取材和病理结果未记录。",
                "evidence": "骨髓穿刺术",
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_specimen_or_pathology_trigger": True,
                        "has_pathology_source": False,
                        "specimen_pathology_coverage": "source_missing",
                    }
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_downgrade_header_only_quote():
    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-105",
                "status": "non_compliant",
                "display_status": "confirmed_defect",
                "findings": "手术记录术后处理措施缺失。",
                "evidence": "手术简要经过(术中所见):;术后处理措施:。术后注意事项:。",
                "adjudicator_reason": "仅见空字段。",
                "adjudicator_supporting_quote": "手术简要经过(术中所见):;术后处理措施:。术后注意事项:。",
            }
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_downgrade_sc099_without_linked_pathology_quote():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-099",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "手术记录提到送病检，但缺病理结果对照。",
                                        "adjudicator_supporting_quote": "切除标本向家属展示后送病检，术毕安返病房。",
                                        "adjudicator_confidence": 0.9,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-099",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "术中取材和病理结果未记录。",
                "evidence": "切除标本向家属展示后送病检。",
                "metadata": {
                    "applicability_gate_metadata": {
                        "pathology_linkage_context": {
                            "linkage_status": "surgery_trigger_only",
                            "surgery_specimen_quote": "切除标本向家属展示后送病检。",
                            "pathology_specimen_quote": "",
                            "pathology_diagnosis_quote": "",
                        }
                    }
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_downgrade_sc123_without_drug_matrix_missing_field():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-123",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "出院带药缺少字段。",
                                        "adjudicator_supporting_quote": "出院带药：神农镇痛膏 1贴 外用 bid*7天。",
                                        "adjudicator_confidence": 0.9,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-123",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "出院带药不完整。",
                "evidence": "出院带药：神农镇痛膏 1贴 外用 bid*7天。",
                "metadata": {
                    "applicability_gate_metadata": {
                        "discharge_medication_matrix": [
                            {
                                "drug_name": "神农镇痛膏",
                                "dosage": "1贴",
                                "frequency": "bid",
                                "route_or_usage": "外用",
                                "quantity_or_days": "7天",
                                "missing_fields": [],
                                "source_quote": "神农镇痛膏 1贴 外用 bid*7天",
                            }
                        ]
                    }
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_downgrade_sc101_partial_implant_details():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-101",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "植入物数量记录不完整。",
                                        "adjudicator_supporting_quote": "置入椎弓根螺钉6枚，连接棒2根，骨水泥5ml",
                                        "adjudicator_confidence": 0.9,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-101",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "植入物种类和数量未在记录中体现。",
                "evidence": "置入椎弓根螺钉6枚，连接棒2根，骨水泥5ml",
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_implant_trigger": True,
                        "has_implant_material_record": True,
                        "has_implant_barcode_source": False,
                        "implant_detail_completeness": "partial",
                    }
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_confirmed_guardrail_should_reject_sc101_without_implant_trigger():
    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-101",
                "status": "non_compliant",
                "display_status": "confirmed_defect",
                "findings": "植入物种类和数量未记录。",
                "evidence": "记录时间: 2025-08-12 19:29:40",
                "adjudicator_reason": "未见植入物信息。",
                "adjudicator_supporting_quote": "记录时间: 2025-08-12 19:29:40",
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_implant_trigger": False,
                        "implant_detail_completeness": "none",
                    }
                },
            }
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["can_show_as_defect"] is False


@pytest.mark.asyncio
async def test_adjudicator_prompt_should_include_targeted_evidence_context():
    captured_prompt = ""

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        nonlocal captured_prompt
        captured_prompt = prompt
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-036",
                                        "adjudicated_display_status": "data_quality_gap",
                                        "adjudicator_reason": "缺少后续病程对异常检验的对照证据。",
                                        "adjudicator_supporting_quote": "",
                                        "adjudicator_confidence": 0.7,
                                        "rule_requirement_match": "data_gap",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-036",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "异常检验未分析。",
                "evidence": "炎症指标稍高。",
                "metadata": {
                    "formal_evidence_coverage": {
                        "has_daily_course_source": True,
                        "has_report_source": True,
                    },
                    "targeted_evidence_context": {
                        "rule_id": "DAILY-CROSS-DOC-CONTEXT",
                        "supporting_quote": "CRP 80mg/L",
                        "contrast_quote": "后续病程仅写继续观察",
                        "coverage_flags": {
                            "has_daily_course_source": True,
                            "has_report_source": True,
                        },
                    },
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert "targeted_evidence_context" in captured_prompt
    assert "CRP 80mg/L" in captured_prompt
    assert "formal_evidence_coverage" in captured_prompt


def _llm_response(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"items": items}, ensure_ascii=False),
                }
            }
        ]
    }


def _candidate(rule_id: str) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "rule_name": f"{rule_id} 测试规则",
        "status": "non_compliant",
        "display_status": "qc_review_candidate",
        "findings": f"{rule_id} 一审候选问题。",
        "evidence": f"{rule_id} 可审计证据片段，长度足够用于二审裁决。",
    }


def _adjudication(index: int, rule_id: str, status: str = "rejected_by_system") -> dict[str, Any]:
    return {
        "index": index,
        "rule_id": rule_id,
        "adjudicated_display_status": status,
        "adjudicator_reason": f"{rule_id} 二审裁决。",
        "adjudicator_supporting_quote": f"{rule_id} 原文证据足够支持裁决。",
        "adjudicator_confidence": 0.8,
        "rule_requirement_match": "not_matched" if status == "rejected_by_system" else "data_gap",
    }


@pytest.mark.asyncio
async def test_adjudicator_should_not_retry_when_all_expected_rules_returned():
    call_count = 0

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        assert "expected_rule_ids" in prompt
        return _llm_response([_adjudication(0, "SC-010"), _adjudication(1, "SC-013")])

    rows = await adjudicate_postprocessed_qc_results(
        [_candidate("SC-010"), _candidate("SC-013")],
        llm_generate=_fake_generate,
    )

    assert call_count == 1
    assert [row["display_status"] for row in rows] == ["rejected_by_system", "rejected_by_system"]
    assert rows[0]["adjudicator_expected_rule_count"] == 2
    assert rows[0]["adjudicator_missing_rule_count"] == 0
    assert rows[0]["adjudicator_retry_attempted"] is False


@pytest.mark.asyncio
async def test_adjudicator_should_retry_only_missing_rules_and_merge_recovered_outputs():
    prompts: list[str] = []

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        prompts.append(prompt)
        if len(prompts) == 1:
            return _llm_response([_adjudication(0, "SC-010"), _adjudication(99, "SC-999")])
        assert "缺失补裁请求" in prompt
        assert "SC-013" in prompt and "SC-015" in prompt
        assert "SC-010" not in prompt
        return _llm_response([_adjudication(0, "SC-013"), _adjudication(1, "SC-015")])

    rows = await adjudicate_postprocessed_qc_results(
        [_candidate("SC-010"), _candidate("SC-013"), _candidate("SC-015")],
        llm_generate=_fake_generate,
    )

    assert len(prompts) == 2
    assert [row["display_status"] for row in rows] == [
        "rejected_by_system",
        "rejected_by_system",
        "rejected_by_system",
    ]
    assert rows[0]["adjudicator_initial_missing_rule_count"] == 2
    assert rows[0]["adjudicator_missing_rule_count"] == 0
    assert rows[0]["adjudicator_retry_recovered_count"] == 2
    assert rows[0]["adjudicator_retry_failed_count"] == 0
    assert rows[1]["recovered_by_adjudicator_missing_rule_retry"] is True
    assert "SC-999" in rows[0]["adjudicator_extra_rule_codes"]


@pytest.mark.asyncio
async def test_adjudicator_should_retry_missing_rules_in_small_chunks():
    prompts: list[str] = []
    rule_ids = [f"SC-{index:03d}" for index in range(1, 14)]

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        prompts.append(prompt)
        if len(prompts) == 1:
            return _llm_response([])
        chunk_start = (len(prompts) - 2) * 5
        chunk_rule_ids = rule_ids[chunk_start : chunk_start + 5]
        assert "缺失补裁请求" in prompt
        return _llm_response([_adjudication(index, rule_id) for index, rule_id in enumerate(chunk_rule_ids)])

    rows = await adjudicate_postprocessed_qc_results(
        [_candidate(rule_id) for rule_id in rule_ids],
        llm_generate=_fake_generate,
    )

    assert len(prompts) == 4
    assert {row["display_status"] for row in rows} == {"rejected_by_system"}
    assert rows[0]["adjudicator_initial_missing_rule_count"] == 13
    assert rows[0]["adjudicator_missing_rule_count"] == 0
    assert rows[0]["adjudicator_retry_recovered_count"] == 13
    assert rows[0]["adjudicator_retry_failed_count"] == 0
    assert rows[-1]["recovered_by_adjudicator_missing_rule_retry"] is True


@pytest.mark.asyncio
async def test_adjudicator_should_chunk_retry_when_initial_response_is_unparseable():
    prompts: list[str] = []
    rule_ids = [f"SC-{index:03d}" for index in range(1, 8)]

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        prompts.append(prompt)
        if len(prompts) == 1:
            return {"choices": [{"message": {"content": "不是 JSON"}}]}
        chunk_start = (len(prompts) - 2) * 5
        chunk_rule_ids = rule_ids[chunk_start : chunk_start + 5]
        assert "缺失补裁请求" in prompt
        return _llm_response([_adjudication(index, rule_id) for index, rule_id in enumerate(chunk_rule_ids)])

    rows = await adjudicate_postprocessed_qc_results(
        [_candidate(rule_id) for rule_id in rule_ids],
        llm_generate=_fake_generate,
    )

    assert len(prompts) == 3
    assert {row["display_status"] for row in rows} == {"rejected_by_system"}
    assert rows[0]["adjudicator_initial_missing_rule_count"] == 7
    assert rows[0]["adjudicator_missing_rule_count"] == 0
    assert rows[0]["adjudicator_retry_recovered_count"] == 7
    assert rows[0]["adjudicator_retry_failed_count"] == 0


@pytest.mark.asyncio
async def test_adjudicator_should_mark_only_still_missing_rules_as_technical_after_retry():
    prompts: list[str] = []

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        prompts.append(prompt)
        if len(prompts) == 1:
            return _llm_response([])
        return _llm_response([_adjudication(0, "SC-010")])

    rows = await adjudicate_postprocessed_qc_results(
        [_candidate("SC-010"), _candidate("SC-013")],
        llm_generate=_fake_generate,
    )

    assert len(prompts) == 2
    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[1]["display_status"] == "technical_error_internal"
    assert rows[1]["adjudicator_missing_rule_count"] == 1
    assert rows[1]["adjudicator_retry_recovered_count"] == 1
    assert rows[1]["adjudicator_retry_failed_count"] == 1
    assert rows[1]["adjudicator_missing_rule_output_count"] == 1
    assert rows[1]["can_show_as_defect"] is False
    assert "adjudicator_missing_rule_output_after_retry" in rows[1]["adjudicator_reason"]


@pytest.mark.asyncio
async def test_gate_terminal_results_should_not_enter_adjudicator_retry():
    async def _fake_generate(prompt: str) -> dict[str, Any]:
        raise AssertionError("gate terminal result should not call adjudicator")

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                **_candidate("SC-123"),
                "display_status": "qc_review_candidate",
                "applicability_gate_decision": "data_quality_gap",
                "applicability_gate_terminal": True,
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "qc_review_candidate"
    assert "adjudicator_retry_attempted" not in rows[0]


def _confirmed_item(
    rule_id: str,
    *,
    quote: str,
    reason: str = "二审认为规则核心要件成立。",
    evidence: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "status": "non_compliant",
        "display_status": "confirmed_defect",
        "adjudicated_display_status": "confirmed_defect",
        "adjudicator_reason": reason,
        "adjudicator_supporting_quote": quote,
        "findings": reason,
        "evidence": evidence or quote,
        "can_show_as_defect": True,
        "metadata": metadata or {},
    }


def _admission_context(text: str) -> dict[str, Any]:
    return {
        "targeted_evidence_context": {
            "rule_id": "ADMISSION-STRUCTURED-CONTEXT",
            "admission_record_evidence": [
                {
                    "source_table": "admission_record",
                    "document_type": "入院记录",
                    "evidence_text": text,
                }
            ],
            "coverage_flags": {"has_admission_record_source": True, "has_history_sections_text": True},
        }
    }


def _discharge_context(
    text: str,
    *,
    contrast_quote: str = "",
    sc118_matrix: dict[str, Any] | None = None,
    sc121_matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "targeted_evidence_context": {
            "rule_id": "DISCHARGE-STRUCTURED-CONTEXT",
            "discharge_record_evidence": [
                {
                    "source_table": "discharge_record",
                    "document_type": "出院记录",
                    "evidence_text": text,
                }
            ],
            "contrast_quote": contrast_quote,
            "sc118_discharge_record_matrix": sc118_matrix or {},
            "sc121_treatment_course_matrix": sc121_matrix or {},
            "coverage_flags": {"has_discharge_record_source": True},
        }
    }


def _course_order_context(
    course_text: str,
    *,
    order_text: str = "",
    contrast_quote: str = "",
) -> dict[str, Any]:
    return {
        "targeted_evidence_context": {
            "rule_id": "DAILY-ORDER-CHANGE-CONTEXT",
            "daily_course_evidence": [
                {
                    "source_table": "daily_course_record",
                    "document_type": "日常病程记录",
                    "evidence_text": course_text,
                }
            ],
            "order_or_consult_evidence": [
                {
                    "source_table": "inpat_drug_order",
                    "document_type": "医嘱",
                    "evidence_text": order_text,
                }
            ]
            if order_text
            else [],
            "contrast_quote": contrast_quote,
        }
    }


def _daily_context(
    course_text: str,
    *,
    report_text: str = "",
    order_text: str = "",
) -> dict[str, Any]:
    return {
        "targeted_evidence_context": {
            "rule_id": "DAILY-CROSS-DOC-CONTEXT",
            "daily_course_evidence": [
                {
                    "source_table": "daily_course_record",
                    "document_type": "病程记录",
                    "evidence_text": course_text,
                }
            ]
            if course_text
            else [],
            "abnormal_report_evidence": [
                {
                    "source_table": "labtest_item_report",
                    "document_type": "检验报告",
                    "evidence_text": report_text,
                }
            ]
            if report_text
            else [],
            "order_or_consult_evidence": [
                {
                    "source_table": "inpat_drug_order",
                    "document_type": "医嘱",
                    "evidence_text": order_text,
                }
            ]
            if order_text
            else [],
        }
    }


def _surgery_context(
    *,
    postsurg_text: str = "",
    surgery_text: str = "",
) -> dict[str, Any]:
    return {
        "targeted_evidence_context": {
            "rule_id": "SURGERY-STRUCTURED-CONTEXT",
            "postsurg_firstcourse_evidence": [
                {
                    "source_table": "postsurg_firstcourse_record",
                    "document_type": "术后首次病程记录",
                    "evidence_text": postsurg_text,
                }
            ]
            if postsurg_text
            else [],
            "surgery_record_evidence": [
                {
                    "source_table": "surgery_record",
                    "document_type": "手术记录",
                    "evidence_text": surgery_text,
                }
            ]
            if surgery_text
            else [],
        }
    }


def _discharge_diagnosis_context(discharge_text: str, diagnosis_text: str) -> dict[str, Any]:
    return {
        "targeted_evidence_context": {
            "rule_id": "DISCHARGE-STRUCTURED-CONTEXT",
            "discharge_record_evidence": [
                {
                    "source_table": "discharge_record",
                    "document_type": "出院记录",
                    "evidence_text": discharge_text,
                }
            ],
            "diagnosis_reference": [
                {
                    "source_table": "admission_record_diagnosis",
                    "document_type": "诊断",
                    "evidence_text": diagnosis_text,
                }
            ],
        }
    }


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc012_short_quote_from_present_illness():
    admission_text = (
        "患者于10小时前晕厥，醒后于玉蟾社区卫生院输液治疗（具体不详）。"
        "3小时前解黑便，为进一步检查及治疗至我院急诊，发病以来精神一般。"
    )

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-012",
                quote="于玉蟾社区卫生院输液治疗（具体不详）。",
                reason="现病史明确记载院外治疗具体不详，缺治疗细节和效果。",
                metadata=_admission_context(admission_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-012"
    assert rows[0]["confirmed_context_document_type"] == "admission_record"
    assert rows[0].get("adjudicator_guardrail_failed") is not True


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc012_short_quote_without_admission_context():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-012",
                quote="于玉蟾社区卫生院输液治疗（具体不详）。",
                reason="治疗具体不详。",
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-012"


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc013_when_complete_past_history_missing_required_field():
    admission_text = (
        "一般情况良好。既往有高血压病史。否认传染病史。否认手术史，否认外伤史，"
        "否认过敏史。否认特殊病史。"
    )

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-013",
                quote="既往有高血压病史。否认传染病史。否认手术史，否认外伤史，否认过敏史。",
                reason="既往史段落缺输血史和预防接种史。",
                metadata=_admission_context(admission_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    matrix = rows[0]["confirmed_context_matrix"]
    assert matrix["transfusion_history"] is False
    assert matrix["vaccination_history"] is False


@pytest.mark.asyncio
async def test_context_matrix_should_mark_sc013_vaccination_unknown_as_policy_pending():
    admission_text = (
        "一般情况良好。否认慢病病史。否认传染病史。否认外伤史，否认手术史，"
        "否认输血史，不详预防接种史，否认过敏史。"
    )

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-013",
                quote="否认输血史，不详预防接种史，否认过敏史。",
                reason="预防接种史不详。",
                metadata=_admission_context(admission_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["policy_pending_flags"] == ["policy_pending_vaccination_unknown"]


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc118_when_full_discharge_matrix_has_missing_fields():
    discharge_text = (
        "患者以左膝关节反复疼痛10+年为主诉于入院。入院查体左膝关节压痛明显。"
        "入院完善相关辅助检查MRI提示左膝关节退行性变。诊疗经过：给予保守治疗。"
        "住院期间复查血常规、凝血功能及肝肾功能，结合患者症状调整止痛和康复治疗方案。"
        "病情好转，予以出院。出院医嘱：门诊随访，每1个月复查，坚持功能锻炼。"
    )
    fields = {
        "admission_date": {"status": "missing"},
        "discharge_date": {"status": "missing"},
        "admission_condition": {"status": "present", "source_quote": "入院查体左膝关节压痛明显。"},
        "admission_diagnosis": {"status": "present", "source_quote": "入院诊断：左膝骨关节炎。"},
        "treatment_course": {"status": "present", "source_quote": "诊疗经过：给予保守治疗。"},
        "discharge_condition": {"status": "present", "source_quote": "病情好转。"},
        "discharge_advice": {"status": "present", "source_quote": "出院医嘱：门诊随访。"},
        "doctor_signature": {"status": "missing"},
    }

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-118",
                quote="出院记录未见明确入院日期和出院日期字段。",
                reason="完整出院记录字段矩阵缺入院日期、出院日期和医师签名。",
                metadata=_discharge_context(
                    discharge_text,
                    sc118_matrix={
                        "source_status": "near_full",
                        "matrix_source": "source_fields_and_sections",
                        "fields": fields,
                        "missing_fields": ["admission_date", "discharge_date", "doctor_signature"],
                        "unknown_fields": [],
                        "can_confirm_missing": True,
                    },
                ),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    matrix = rows[0]["confirmed_context_matrix"]
    assert matrix["admission_date"] is False
    assert matrix["discharge_date"] is False


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc118_when_fields_are_unknown_not_missing():
    discharge_text = (
        "患者以外伤入院。入院后完善相关辅助检查，行清创治疗。"
        "术后抗感染、换药治疗，病情好转予以出院。出院医嘱：门诊随访。"
    )
    fields = {
        "admission_date": {"status": "unknown"},
        "discharge_date": {"status": "unknown"},
        "admission_condition": {"status": "present_by_text_hint"},
        "admission_diagnosis": {"status": "unknown"},
        "treatment_course": {"status": "present"},
        "discharge_condition": {"status": "present_by_text_hint"},
        "discharge_advice": {"status": "present"},
        "doctor_signature": {"status": "unknown"},
    }

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-118",
                quote="患者以外伤入院。",
                reason="出院记录缺入院日期、出院日期和医师签名。",
                metadata=_discharge_context(
                    discharge_text,
                    sc118_matrix={
                        "source_status": "near_full",
                        "matrix_source": "source_fields_and_sections",
                        "fields": fields,
                        "missing_fields": [],
                        "unknown_fields": ["admission_date", "discharge_date", "admission_diagnosis", "doctor_signature"],
                        "can_confirm_missing": False,
                    },
                ),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["confirmed_context_matrix"]["admission_date"] is False
    assert rows[0]["sc118_unknown_fields"] == ["admission_date", "discharge_date", "admission_diagnosis", "doctor_signature"]


@pytest.mark.asyncio
async def test_context_matrix_should_reject_sc118_when_structured_matrix_is_complete():
    fields = {
        field: {"status": "present", "source_quote": "已记录"}
        for field in (
            "admission_date",
            "discharge_date",
            "admission_condition",
            "admission_diagnosis",
            "treatment_course",
            "discharge_condition",
            "discharge_advice",
            "doctor_signature",
        )
    }

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-118",
                quote="出院记录字段完整。",
                reason="误称出院记录缺项。",
                metadata=_discharge_context(
                    "完整出院记录。",
                    sc118_matrix={
                        "source_status": "near_full",
                        "matrix_source": "source_fields_and_sections",
                        "fields": fields,
                        "missing_fields": [],
                        "unknown_fields": [],
                        "can_confirm_missing": False,
                    },
                ),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["adjudicator_guardrail_failed"] is True


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc118_short_discharge_fragment():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-118",
                quote="患者李某，性别男，年龄75岁，以左膝疼痛入院。",
                reason="出院记录缺项。",
                metadata=_discharge_context("患者李某，性别男，年龄75岁，以左膝疼痛入院。"),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc121_with_treatment_course_and_contrast():
    discharge_text = (
        "患者因肺栓塞入院，入院完善CTA提示肺动脉栓塞。诊疗经过：予以多索茶碱、甲泼尼龙抗炎平喘，"
        "哌拉西林他唑巴坦抗感染，呋塞米及螺内酯利尿，并持续监测血气分析、凝血功能和氧合情况。"
        "患者病情仍危重，家属要求转院，出院时已告知继续治疗风险。"
    )
    sc121_matrix = {
        "discharge_treatment_course_context": "near_full",
        "discharge_has_specific_treatment_summary": True,
        "key_drug_categories": ["抗凝"],
        "key_treatment_orders": [
            {
                "source_table": "inpat_drug_order",
                "document_type": "医嘱",
                "evidence_text": "低分子肝素抗凝治疗。",
            }
        ],
        "important_abnormal_exam_or_lab_results": [
            {
                "source_table": "exam_item_report",
                "document_type": "检查报告",
                "evidence_text": "CTA提示肺动脉栓塞。",
            }
        ],
        "course_change_or_treatment_adjustment_quotes": [],
        "cross_document_contrast_present": True,
        "missing_from_discharge_candidates": ["抗凝"],
        "matrix_source_tables": ["discharge_record", "exam_item_report", "inpat_drug_order"],
    }

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-121",
                quote="予以多索茶碱、甲泼尼龙抗炎平喘，哌拉西林他唑巴坦抗感染，呋塞米及螺内酯利尿。",
                reason="诊疗经过缺少抗凝治疗方案和相关重要辅助检查结果分析。",
                metadata=_discharge_context(
                    discharge_text,
                    contrast_quote="医嘱提示低分子肝素抗凝治疗。",
                    sc121_matrix=sc121_matrix,
                ),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-121"
    assert rows[0]["confirmed_context_matrix"]["cross_document_contrast_present"] is True
    assert rows[0]["sc121_treatment_course_evidence_matrix"]["missing_from_discharge_candidates"] == ["抗凝"]


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc121_short_treatment_sentence_without_contrast():
    discharge_text = (
        "患者陈某以黑便入院。入院完善腹部CT等检查。治疗上予以护胃、补液等对症支持治疗。"
        "病情稳定后出院，嘱门诊随访。"
    )

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-121",
                quote="治疗上予以护胃、补液等对症支持治疗。",
                reason="无主要药品名称。",
                metadata=_discharge_context(discharge_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["adjudicator_guardrail_failed"] is True
    assert rows[0]["confirmed_context_matrix"]["cross_document_contrast_present"] is False


@pytest.mark.asyncio
async def test_context_matrix_should_reject_sc121_when_discharge_course_reasonably_summarized():
    discharge_text = (
        "出院记录：诊疗经过：入院后完善胸部CT、血常规等检查，予抗感染、平喘、护胃及补液治疗，"
        "根据病情调整治疗方案，患者咳嗽气促较前缓解，病情稳定后出院。"
    )
    sc121_matrix = {
        "discharge_treatment_course_context": "near_full",
        "discharge_has_specific_treatment_summary": True,
        "key_drug_categories": ["抗感染", "平喘", "护胃", "补液"],
        "key_treatment_orders": [
            {"source_table": "inpat_drug_order", "document_type": "医嘱", "evidence_text": "抗感染、平喘、护胃及补液治疗。"}
        ],
        "important_abnormal_exam_or_lab_results": [],
        "course_change_or_treatment_adjustment_quotes": [],
        "cross_document_contrast_present": True,
        "missing_from_discharge_candidates": [],
        "matrix_source_tables": ["discharge_record", "inpat_drug_order"],
    }

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-121",
                quote="予抗感染、平喘、护胃及补液治疗，患者病情稳定后出院。",
                reason="诊疗经过不够详细。",
                metadata=_discharge_context(discharge_text, sc121_matrix=sc121_matrix),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-121"
    assert rows[0]["sc121_cross_document_contrast_present"] is True


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc122_followup_fragment_only():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-122",
                quote="随访方式:其他随访周期:无需随访日期:2026年04月07日",
                reason="出院记录仅见随访方式，缺其他出院医嘱。",
                evidence="随访方式:其他随访周期:无需随访日期:2026年04月07日",
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-122"
    assert rows[0]["confirmed_context_matrix"]["source_is_full_discharge_advice_section"] is False


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc122_full_discharge_advice_with_missing_core_content():
    discharge_text = (
        "出院医嘱：出院后注意休息，保持伤口清洁干燥。若腹痛、发热、阴道流血增多及时返院。"
        "本次出院医嘱仅记录一般注意事项，未给出后续治疗计划和复诊安排，请患者自行观察。"
        "医生签名：张三。"
    )

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-122",
                quote="本次出院医嘱仅记录一般注意事项，未给出后续治疗计划和复诊安排。",
                reason="完整出院医嘱段缺后续治疗计划和复诊安排。",
                metadata=_discharge_context(discharge_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-122"


@pytest.mark.asyncio
async def test_context_matrix_should_reject_sc122_reasonable_full_discharge_advice():
    discharge_text = (
        "出院医嘱：1、按时口服出院带药。2、清淡饮食，避免剧烈活动，注意休息。"
        "3、术后两周门诊复查，如出现发热、腹痛或伤口渗液及时就诊。"
        "4、保持伤口清洁干燥，遵医嘱换药。"
    )

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-122",
                quote="出院医嘱缺失。",
                reason="无出院医嘱或出院医嘱不全。",
                metadata=_discharge_context(discharge_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-122"


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc034_symptom_and_symptomatic_treatment_only():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-034",
                quote="患者术后呕吐多次浅褐色胃内容物，予以胃复安止吐对症治疗。",
                reason="针对术后呕吐缺乏病因分析及后续调整依据。",
                evidence="患者术后呕吐多次浅褐色胃内容物，予以胃复安止吐对症治疗。",
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-034"
    assert rows[0]["confirmed_context_matrix"]["order_or_treatment_change_present"] is False


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc034_order_change_without_course_analysis():
    course_text = "患者术后呕吐多次，查房记录仅记载予以处理，未见原因分析、依据或后续计划。"
    order_text = "临时医嘱：甲氧氯普胺注射液 10mg 肌注 新开。"

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-034",
                quote="临时医嘱：甲氧氯普胺注射液 10mg 肌注 新开。",
                reason="存在止吐医嘱变化，但病程未记录原因、依据及效果分析。",
                metadata=_course_order_context(course_text, order_text=order_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-034"
    assert rows[0]["confirmed_context_matrix"]["order_or_treatment_change_present"] is True


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc034_missing_order_change_source():
    course_text = "患者术后发热，予以对症处理，继续观察。"

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-034",
                quote="患者术后发热，予以对症处理，继续观察。",
                reason="治疗措施变化未分析。",
                metadata=_course_order_context(course_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-034"


@pytest.mark.asyncio
async def test_context_matrix_should_reject_sc015_male_menstrual_claim():
    admission_text = "患者性别：男，年龄45岁。个人史：否认吸烟饮酒。婚育史：已婚已育。家族史：否认遗传病史。"

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-015",
                quote="个人史：否认吸烟饮酒。婚育史：已婚已育。家族史：否认遗传病史。",
                reason="月经史未记录。",
                metadata=_admission_context(admission_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-015"
    assert rows[0]["adjudicator_guardrail_failed"] is True


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc015_unknown_history_policy_pending():
    admission_text = "患者性别：女，年龄32岁。个人史：具体不详。婚育史：不详。月经史：具体不详。家族史：否认。"

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-015",
                quote="个人史：具体不详。婚育史：不详。月经史：具体不详。",
                reason="个人史、婚育史、月经史记录不详。",
                metadata=_admission_context(admission_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["policy_pending_flags"] == ["policy_pending_history_unknown"]


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc018_specialty_exam_pointer_only():
    admission_text = "主诉：左膝疼痛。体格检查：T36.5℃，心肺腹未见异常。专科检查：详见专科检查。"

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-018",
                quote="专科检查：详见专科检查。",
                reason="专科查体缺少左膝阳性体征。",
                metadata=_admission_context(admission_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-018"


@pytest.mark.asyncio
async def test_context_matrix_should_reject_sc036_when_followup_treatment_exists():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-036",
                quote="CRP 80mg/L，白细胞升高。后续病程考虑感染，给予抗感染治疗并复查血常规。",
                reason="异常炎症指标未分析处理。",
                metadata=_daily_context(
                    "后续病程：考虑感染可能，给予抗感染治疗并复查血常规。",
                    report_text="检验报告：CRP 80mg/L 升高，白细胞 15*10^9/L 升高。",
                    order_text="医嘱：抗感染治疗，复查血常规。",
                ),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-036"


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc036_same_as_before_without_report():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-036",
                quote="辅助检查同前。",
                reason="无异常检查分析。",
                metadata=_daily_context("病程记录：辅助检查同前。"),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-036"


@pytest.mark.asyncio
async def test_context_matrix_should_reject_sc047_pathology_result_without_revision_trigger():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-047",
                quote="病理报告提示腺癌。",
                reason="病理结果提示诊断变化但未记录理由。",
                metadata=_daily_context("病程记录：病理报告提示腺癌，继续当前治疗方案。"),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-047"


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc047_revision_without_basis():
    course_text = "2026年01月02日病程：补充诊断：肺部感染。原诊断为慢阻肺急性加重，目前诊断增加肺部感染。"

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-047",
                quote="补充诊断：肺部感染。原诊断为慢阻肺急性加重，目前诊断增加肺部感染。",
                reason="存在补充诊断动作，但邻近病程未记录补充理由及诊断依据。",
                metadata=_daily_context(course_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-047"


@pytest.mark.asyncio
async def test_context_matrix_should_reject_sc050_with_analysis_and_opinion():
    course_text = (
        "2026年01月03日主任医师查房：患者病情较前稳定，结合检查考虑感染控制中。"
        "诊疗意见：继续抗感染治疗，复查血常规及CRP，观察体温变化。"
    )

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-050",
                quote="主任医师查房：患者病情较前稳定。诊疗意见：继续抗感染治疗。",
                reason="上级医师查房无病情分析和诊疗意见。",
                metadata=_daily_context(course_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-050"


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc050_short_round_fragment():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-050",
                quote="上级医师查房。",
                reason="上级医师查房记录短，缺分析。",
                metadata=_daily_context("上级医师查房。"),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-050"


@pytest.mark.asyncio
async def test_context_matrix_should_downgrade_sc105_short_postsurg_fragment():
    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-105",
                quote="术毕安返病房。",
                reason="术后首次病程记录缺项。",
                metadata=_surgery_context(postsurg_text="术毕安返病房。", surgery_text="手术记录：行胆囊切除术。"),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "data_quality_gap"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-105"


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc105_full_postsurg_record_missing_fields():
    postsurg_text = (
        "术后首次病程记录：患者今日在全麻下行腹腔镜胆囊切除术，术中过程顺利，出血少。"
        "术后予抗感染、补液、镇痛等治疗，注意观察腹痛、发热及切口渗血情况。"
        "返回病房后生命体征平稳。本记录未见术后诊断和医师签名字段。"
    )

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-105",
                quote="本记录未见术后诊断和医师签名字段。",
                reason="术后首次病程字段矩阵缺术后诊断和医师签名。",
                metadata=_surgery_context(postsurg_text=postsurg_text, surgery_text="手术记录：行腹腔镜胆囊切除术。"),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-105"


@pytest.mark.asyncio
async def test_context_matrix_should_reject_sc125_subjective_order_without_marker():
    discharge_text = "出院诊断：肺部感染；慢性阻塞性肺疾病急性加重。诊疗经过：予抗感染、平喘治疗后好转。"
    diagnosis_text = "入院诊断：慢性阻塞性肺疾病急性加重；肺部感染。"

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-125",
                quote="出院诊断：肺部感染；慢性阻塞性肺疾病急性加重。",
                reason="诊断顺序应调整，主要诊断应排第一。",
                metadata=_discharge_diagnosis_context(discharge_text, diagnosis_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "rejected_by_system"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-125"


@pytest.mark.asyncio
async def test_context_matrix_should_keep_sc125_objective_omission_with_diagnosis_matrix():
    discharge_text = (
        "入院诊断：胃恶性肿瘤。诊疗经过：行胃癌根治术，术后病理提示胃腺癌伴淋巴结转移。"
        "出院诊断：胃恶性肿瘤。"
    )
    diagnosis_text = "入院诊断：胃恶性肿瘤。病理诊断：胃腺癌伴淋巴结转移。"

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-125",
                quote="术后病理提示胃腺癌伴淋巴结转移。出院诊断：胃恶性肿瘤。",
                reason="出院诊断漏填术后病理明确的淋巴结转移诊断。",
                metadata=_discharge_diagnosis_context(discharge_text, diagnosis_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-125"


@pytest.mark.asyncio
async def test_adjudicator_prompt_should_include_rule_specific_criteria():
    captured: dict[str, str] = {}

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        captured["prompt"] = prompt
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-012",
                                        "adjudicated_display_status": "data_quality_gap",
                                        "adjudicator_reason": "无法确认证据来自入院记录现病史。",
                                        "adjudicator_supporting_quote": "",
                                        "adjudicator_confidence": 0.7,
                                        "rule_requirement_match": "data_gap",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-012",
                "rule_name": "入院前检查治疗经过欠缺",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "入院前治疗经过欠缺。",
                "evidence": "外院输液治疗，具体不详。",
            }
        ],
        llm_generate=_fake_generate,
    )

    assert "规则专属判定标准" in captured["prompt"]
    assert "required_document" in captured["prompt"]
    assert "admission_record/入院记录" in captured["prompt"]
    assert "现病史/发病后到入院前" in captured["prompt"]
    assert rows[0]["rule_criteria_version"] == "formal_high_false_positive_rule_criteria_v1"
    assert rows[0]["required_document"] == "admission_record/入院记录"
    assert rows[0]["data_gap_reason"] == "无法确认证据来自入院记录现病史。"


@pytest.mark.asyncio
async def test_adjudicator_prompt_should_include_near_full_discharge_context_hint():
    captured: dict[str, str] = {}
    discharge_text = (
        "诊疗经过：" + "患者入院后完善血常规、凝血功能、CTA等检查，予以抗感染、平喘、利尿治疗。" * 20
        + "出院医嘱：转上级医院继续治疗，门诊随访。"
    )

    async def _fake_generate(prompt: str) -> dict[str, Any]:
        captured["prompt"] = prompt
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-121",
                                        "adjudicated_display_status": "data_quality_gap",
                                        "adjudicator_reason": "测试返回。",
                                        "adjudicator_supporting_quote": "",
                                        "adjudicator_confidence": 0.5,
                                        "rule_requirement_match": "data_gap",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-121",
                "rule_name": "诊疗经过不全面、不详细",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "诊疗经过不全面。",
                "evidence": "予以抗感染、平喘治疗。",
                "metadata": {
                    "targeted_evidence_context": {
                        "discharge_record_evidence": [
                            {
                                "source_table": "discharge_record",
                                "document_type": "出院记录",
                                "evidence_text": discharge_text,
                            }
                        ]
                    }
                },
            }
        ],
        llm_generate=_fake_generate,
    )

    assert "rule_context_coverage_hint" in captured["prompt"]
    assert '"discharge_record_context_near_full": true' in captured["prompt"]
    assert "不能只因 item.evidence/supporting_quote 较短就转 data_quality_gap" in captured["prompt"]


@pytest.mark.asyncio
async def test_adjudicator_should_keep_criteria_metadata_on_confirmed_result():
    async def _fake_generate(_prompt: str) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "items": [
                                    {
                                        "index": 0,
                                        "rule_id": "SC-034",
                                        "adjudicated_display_status": "confirmed_defect",
                                        "adjudicator_reason": "存在明确医嘱变化，但病程未记录原因、依据和效果分析。",
                                        "adjudicator_supporting_quote": "临时医嘱：甲氧氯普胺注射液 10mg 肌注 新开。",
                                        "adjudicator_confidence": 0.88,
                                        "rule_requirement_match": "matched",
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    rows = await adjudicate_postprocessed_qc_results(
        [
            {
                "rule_id": "SC-034",
                "rule_name": "病程中对治疗措施、药物、医嘱变化未记录或分析",
                "status": "non_compliant",
                "display_status": "qc_review_candidate",
                "findings": "医嘱变化未分析。",
                "evidence": "临时医嘱：甲氧氯普胺注射液 10mg 肌注 新开。",
                "metadata": _course_order_context(
                    "患者术后呕吐多次，病程仅记载予以处理，未见原因分析、依据或后续计划。",
                    order_text="临时医嘱：甲氧氯普胺注射液 10mg 肌注 新开。",
                ),
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["rule_criteria_version"] == "formal_high_false_positive_rule_criteria_v1"
    assert rows[0]["required_document"] == "daily_course_record/病程记录 + 医嘱/治疗变化来源"
    assert "order_or_treatment_change_quote" in rows[0]["field_matrix_evidence"]
    assert rows[0]["metadata"]["confirmed_guardrail_reason"] == "存在明确医嘱变化，但病程未记录原因、依据和效果分析。"
