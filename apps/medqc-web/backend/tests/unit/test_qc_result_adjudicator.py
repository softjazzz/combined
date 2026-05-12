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
