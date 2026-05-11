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
