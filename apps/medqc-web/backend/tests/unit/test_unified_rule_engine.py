import pytest

from app.services.unified_rule_engine import UnifiedRuleEngine


def _make_engine(capture: dict):
    async def _fake_llm(prompt: str):
        capture["prompt"] = prompt
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"is_compliant": true, "issues": [], "findings": "合规", '
                            '"evidence": "", "suggestion": "", "confidence": 0.91}'
                        )
                    }
                }
            ],
            "usage": {"total_tokens": 12},
            "_api_time": 0.01,
        }

    return UnifiedRuleEngine(_fake_llm)


def test_build_prompt_should_not_truncate_to_2000():
    capture = {}
    engine = _make_engine(capture)
    tail = "END-OF-MEDICAL-TEXT-TAIL"
    medical_text = "A" * 2400 + tail
    prompt = engine._build_prompt(
        {"rule_id": "SC-001", "name": "测试规则", "description": "测试描述"},
        medical_text,
    )
    assert tail in prompt
    assert "A" * 2200 in prompt


@pytest.mark.asyncio
async def test_evaluate_should_include_bundle_evidence_context_in_prompt():
    capture = {}
    engine = _make_engine(capture)
    rule = {
        "rule_id": "SC-001",
        "name": "测试规则",
        "description": "测试描述",
    }
    medical_record = {
        "content": "主文书正文",
        "document_type": "入院记录",
        "evidence_payload": {
            "supporting_documents": [
                {
                    "document_type": "病程记录",
                    "evidence_text": "辅助证据-病程记录片段",
                }
            ],
            "timeline_facts": ["2026-04-15 入院", "2026-04-16 查房"],
            "document_hits": {"admission_record": True, "daily_course_record": True},
            "data_quality_flags": ["missing:discharge_record"],
        },
    }

    result = await engine.evaluate(rule, medical_record)

    assert result["status"] == "compliant"
    prompt = capture["prompt"]
    assert "结构化证据上下文（Bundle）" in prompt
    assert "辅助证据-病程记录片段" in prompt
    assert "2026-04-15 入院" in prompt
