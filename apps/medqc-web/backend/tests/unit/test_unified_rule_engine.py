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


def test_build_prompt_should_fill_legacy_confidence_requirement_placeholder():
    capture = {}
    engine = _make_engine(capture)
    prompt = engine._build_prompt(
        {
            "rule_id": "SC-071",
            "name": "会诊记录时效",
            "description": "测试旧模板占位符",
            "defect_level": "一般缺陷",
            "custom_prompt": "规则 {rule_id} 缺陷 {defect_level} 置信度 {confidence_requirement} 文本 {medical_text}",
        },
        "病历正文",
    )

    assert "置信度 0.85" in prompt
    assert "{confidence_requirement}" not in prompt


def test_build_prompt_should_preserve_raw_json_braces_in_custom_prompt():
    capture = {}
    engine = _make_engine(capture)
    prompt = engine._build_prompt(
        {
            "rule_id": "CL-001",
            "name": "客户专项测试规则",
            "description": "测试原始 JSON 花括号",
            "custom_prompt": (
                "规则 {rule_id}\n"
                "输出格式示例：\n"
                "{\n"
                '  "is_compliant": true,\n'
                '  "findings": "合规"\n'
                "}\n"
                "病历文本：{medical_text}"
            ),
        },
        "病历正文",
    )

    assert '规则 CL-001' in prompt
    assert '{\n  "is_compliant": true,' in prompt
    assert '"findings": "合规"' in prompt
    assert "病历正文" in prompt


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


@pytest.mark.asyncio
async def test_evaluate_batch_compact_should_return_all_rule_results():
    async def _fake_llm(prompt: str):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"results": ['
                            '{"rule_id":"SC-001","is_compliant":true,"status":"compliant","findings":"合规","evidence":"主文书正文","suggestion":"","confidence":0.9},'
                            '{"rule_id":"SC-002","is_compliant":false,"status":"non_compliant","findings":"不合规","evidence":"主文书正文","suggestion":"补充","confidence":0.88}'
                            ']}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 28, "completion_tokens": 12, "total_tokens": 40},
            "_api_time": 0.2,
            "_first_result_latency": 0.2,
            "_usage_breakdown": {
                "prompt_tokens": 28,
                "completion_tokens": 12,
                "input_tokens": 28,
                "output_tokens": 12,
                "total_tokens": 40,
            },
            "_cot_observation": {
                "cot_mode": "disabled",
                "requested_enable_thinking": False,
                "thinking_heuristic_applied": False,
                "response_has_think_tags": False,
                "response_has_reasoning_content": False,
            },
        }

    engine = UnifiedRuleEngine(_fake_llm)
    result = await engine.evaluate_batch_compact(
        rules=[
            {"rule_id": "SC-001", "name": "规则1", "description": "描述1"},
            {"rule_id": "SC-002", "name": "规则2", "description": "描述2"},
        ],
        medical_record={"content": "主文书正文", "document_type": "病程记录"},
        pack_id="pack-1",
        pack_size=2,
    )

    assert result["parse_error"] is False
    assert len(result["results"]) == 2
    assert result["missing_rule_ids"] == []
    assert result["low_confidence_rule_ids"] == []
    assert result["context_tokens_estimate"] > 0
    assert all((item.get("metadata") or {}).get("prompt_strategy") == "batch_compact_v1" for item in result["results"])
    assert result["prompt_tokens"] == 28
    assert result["completion_tokens"] == 12
    assert result["first_result_latency"] == 0.2
    assert result["cot_observation"]["cot_mode"] == "disabled"
    assert all((item.get("metadata") or {}).get("prompt_tokens") == 14 for item in result["results"])
    assert all((item.get("metadata") or {}).get("completion_tokens") == 6 for item in result["results"])


@pytest.mark.asyncio
async def test_evaluate_batch_compact_should_report_missing_when_parse_failed():
    async def _fake_llm(prompt: str):
        return {
            "choices": [{"message": {"content": "非JSON输出"}}],
            "usage": {"total_tokens": 10},
            "_api_time": 0.05,
        }

    engine = UnifiedRuleEngine(_fake_llm)
    result = await engine.evaluate_batch_compact(
        rules=[
            {"rule_id": "SC-201", "name": "规则201", "description": "描述201"},
            {"rule_id": "SC-202", "name": "规则202", "description": "描述202"},
        ],
        medical_record={"content": "主文书正文", "document_type": "病程记录"},
        pack_id="pack-fail",
        pack_size=2,
    )

    assert result["parse_error"] is True
    assert sorted(result["missing_rule_ids"]) == ["SC-201", "SC-202"]


def test_resolve_context_token_budget_should_adapt_by_domain_and_model():
    capture = {}
    engine = _make_engine(capture)

    surgery_budget = engine._resolve_context_token_budget(
        rules=[{"rule_id": "SC-900", "execution_domain": "surgery", "doc_scope": "primary"}],
        medical_record={"execution_domain": "surgery", "doc_scope": "primary", "model_version": "qwen3.5-35b-a3b"},
        base_budget=7000,
    )
    coding_budget = engine._resolve_context_token_budget(
        rules=[{"rule_id": "SC-901", "execution_domain": "index_coding_settlement", "doc_scope": "primary"}],
        medical_record={"execution_domain": "index_coding_settlement", "doc_scope": "primary", "model_version": "qwen2.5-7b-instruct"},
        base_budget=7000,
    )

    assert surgery_budget > 7000
    assert coding_budget < 7000
