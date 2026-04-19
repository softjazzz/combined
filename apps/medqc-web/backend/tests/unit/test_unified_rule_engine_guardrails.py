from app.services.unified_rule_engine import UnifiedRuleEngine


def test_apply_result_sanity_should_downgrade_non_compliant_without_evidence():
    result = {
        "status": "non_compliant",
        "is_compliant": False,
        "evidence": "",
        "suggestion": "请补充诊疗计划。",
        "confidence": 0.82,
    }

    normalized = UnifiedRuleEngine._apply_result_sanity(result)

    assert normalized["status"] == "uncertain"
    assert normalized["is_compliant"] is False
    assert normalized["confidence"] == 0.5
    assert "原文证据" in normalized["suggestion"]


def test_apply_result_sanity_should_downgrade_contradictory_no_change_suggestion():
    result = {
        "status": "non_compliant",
        "is_compliant": False,
        "evidence": "病例特点：患者为40岁男性……",
        "suggestion": "无需修改。",
        "confidence": 0.9,
    }

    normalized = UnifiedRuleEngine._apply_result_sanity(result)

    assert normalized["status"] == "uncertain"
    assert normalized["is_compliant"] is False
    assert normalized["confidence"] == 0.5
    assert "人工复核" in normalized["suggestion"]


def test_apply_result_sanity_should_downgrade_boundary_sensitive_rule_without_verified_evidence():
    result = {
        "rule_id": "SC-023",
        "status": "non_compliant",
        "is_compliant": False,
        "evidence": "患者为40岁男性……",
        "evidence_verified": False,
        "suggestion": "请补充病例特点。",
        "confidence": 0.84,
    }

    normalized = UnifiedRuleEngine._apply_result_sanity(result)

    assert normalized["status"] == "uncertain"
    assert normalized["is_compliant"] is False
    assert normalized["confidence"] == 0.5
    assert "规则边界较敏感" in normalized["suggestion"]


def test_apply_result_sanity_should_downgrade_sc032_when_findings_self_report_uncertain():
    result = {
        "rule_id": "SC-032",
        "status": "compliant",
        "is_compliant": True,
        "evidence": "肛门切口轻微肿胀",
        "evidence_verified": False,
        "findings": "最终判定：uncertain。当前处于合规与不合规的边界。",
        "suggestion": "建议补充病情变化细节。",
        "confidence": 0.76,
    }

    normalized = UnifiedRuleEngine._apply_result_sanity(result)

    assert normalized["status"] == "uncertain"
    assert normalized["is_compliant"] is False
    assert normalized["confidence"] == 0.5
    assert "边界" in normalized["suggestion"]


def test_apply_batch_output_mode_should_trim_long_text():
    result = {
        "status": "uncertain",
        "findings": "这是一段非常长的结论文本，需要被压缩成简短摘要以避免批量阶段输出过长。" * 2,
        "evidence": "这是一段非常长的证据引用，需要保留最关键的原文片段即可，不应该在批量阶段展开完整大段落。" * 2,
        "suggestion": "这是一段非常长的整改建议，需要缩短成一句简洁动作建议即可。" * 2,
        "issues": ["x"],
    }

    normalized = UnifiedRuleEngine._apply_batch_output_mode(result, batch_output_mode="minimal")

    assert len(normalized["findings"]) <= 43
    assert len(normalized["evidence"]) <= 83
    assert len(normalized["suggestion"]) <= 33
    assert normalized["issues"] == []


async def _unused_llm_generate(prompt: str):  # pragma: no cover
    return {"choices": [{"message": {"content": "{}"}}], "usage": {"total_tokens": 0}, "_api_time": 0.0}


def test_build_batch_prompt_compact_should_use_minimal_output_contract():
    engine = UnifiedRuleEngine(_unused_llm_generate)
    prompt, _ = engine._build_batch_prompt_compact(
        [
            {
                "rule_id": "SC-121",
                "name": "诊疗经过不全面、不详细",
                "defect_level": "一般缺陷",
                "rule_family": "content_completeness",
                "custom_prompt": "检查诊疗经过是否完整。",
            }
        ],
        {"content": "出院记录正文"},
        quality_profile="effect_priority_v1",
        batch_output_mode="minimal",
    )

    assert "findings 最多 40 字" in prompt
    assert "issues 固定输出空数组 []" in prompt
