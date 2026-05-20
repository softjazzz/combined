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
            }
        ],
        llm_generate=_fake_generate,
    )

    assert rows[0]["first_pass_display_status"] == "qc_review_candidate"
    assert rows[0]["adjudicated_display_status"] == "confirmed_defect"
    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["can_show_as_defect"] is True
    assert rows[0]["display_bucket"] == "确认缺陷"


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


def _discharge_context(text: str, *, contrast_quote: str = "") -> dict[str, Any]:
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

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-118",
                quote="出院记录未见明确入院日期和出院日期字段。",
                reason="完整出院记录字段矩阵缺入院日期、出院日期和医师签名。",
                metadata=_discharge_context(discharge_text),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    matrix = rows[0]["confirmed_context_matrix"]
    assert matrix["admission_date"] is False
    assert matrix["discharge_date"] is False


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

    rows = await adjudicate_postprocessed_qc_results(
        [
            _confirmed_item(
                "SC-121",
                quote="予以多索茶碱、甲泼尼龙抗炎平喘，哌拉西林他唑巴坦抗感染，呋塞米及螺内酯利尿。",
                reason="诊疗经过缺少抗凝治疗方案和相关重要辅助检查结果分析。",
                metadata=_discharge_context(discharge_text, contrast_quote="医嘱提示低分子肝素抗凝治疗。"),
            )
        ],
        llm_generate=None,
    )

    assert rows[0]["display_status"] == "confirmed_defect"
    assert rows[0]["confirmed_context_matrix_rule"] == "SC-121"


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
