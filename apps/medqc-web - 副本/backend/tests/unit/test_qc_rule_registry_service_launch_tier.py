from __future__ import annotations

import json

from app.services.qc_rule_registry_service import QCRuleRegistryService


def test_qc_rule_registry_service_should_inject_launch_tier_for_intrinsic_rule(tmp_path):
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(
            [
                {
                    "rule_id": "SC-004",
                    "name": "测试规则",
                    "description": "测试描述",
                    "category": "入院记录",
                    "complexity": "低复杂度",
                    "defect_level": "轻微缺陷",
                    "applicable_documents": ["admission_record"],
                    "custom_prompt": "",
                    "executor_type": "llm",
                    "execution_domain": "admission",
                    "doc_scope": "primary",
                    "rule_version": "v1",
                    "prompt_version": "default-v1",
                    "cost_class": "medium",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = QCRuleRegistryService(session_factory=None, json_path=rules_path)

    rules, source = service.load_active_rules()

    assert source == "json_file"
    assert len(rules) == 1
    assert rules[0]["rule_id"] == "SC-004"
    assert rules[0]["launch_tier"] == "A"


def test_qc_rule_registry_service_should_return_unknown_for_non_intrinsic_rule(tmp_path):
    rules_path = tmp_path / "rules.json"
    rules_path.write_text(
        json.dumps(
            [
                {
                    "rule_id": "SC-001",
                    "name": "测试规则",
                    "description": "测试描述",
                    "category": "入院记录",
                    "complexity": "低复杂度",
                    "defect_level": "严重缺陷",
                    "applicable_documents": ["admission_record"],
                    "custom_prompt": "",
                    "executor_type": "program",
                    "execution_domain": "admission",
                    "doc_scope": "primary",
                    "rule_version": "v1",
                    "prompt_version": "default-v1",
                    "cost_class": "low",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    service = QCRuleRegistryService(session_factory=None, json_path=rules_path)

    rules, _ = service.load_active_rules()

    assert len(rules) == 1
    assert rules[0]["rule_id"] == "SC-001"
    assert rules[0]["launch_tier"] == "UNKNOWN"
