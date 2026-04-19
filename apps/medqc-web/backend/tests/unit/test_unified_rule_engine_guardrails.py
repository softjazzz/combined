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
