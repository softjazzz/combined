from unittest.mock import MagicMock

import pytest

from app.services.sichuan_qc_service import SichuanQCService


def _build_sc_rule(rule_id: str = "SC-001") -> dict:
    return {
        "rule_id": rule_id,
        "name": "测试规则",
        "description": "测试描述",
        "category": "完整性",
        "complexity": "中复杂度",
        "defect_level": "一般缺陷",
        "applicable_documents": ["admission_record"],
        "custom_prompt": "",
        "executor_type": "program",
        "execution_domain": "admission",
        "doc_scope": "primary",
        "rule_version": "v2",
        "prompt_version": "default-v1",
        "cost_class": "low",
    }


def test_get_rule_by_id_should_prefer_registry_for_sc_rule():
    service = SichuanQCService()
    service.rule_registry.load_rule_by_id = MagicMock(return_value=(_build_sc_rule("SC-001"), "pg_governance"))

    rule = service.get_rule_by_id("SC-001")

    assert rule is not None
    assert rule["rule_id"] == "SC-001"
    assert rule["executor_type"] == "program"
    service.rule_registry.load_rule_by_id.assert_called_once()


def test_update_rule_prompt_should_use_registry_first_for_sc_rule():
    service = SichuanQCService()
    service.rule_registry.update_rule_prompt_version = MagicMock(return_value=True)

    ok = service.update_rule_prompt("SC-001", "新的提示词", operator="tester")

    assert ok is True
    service.rule_registry.update_rule_prompt_version.assert_called_once_with(
        rule_id="SC-001",
        custom_prompt="新的提示词",
        operator="tester",
    )


@pytest.mark.asyncio
async def test_load_applicable_rules_should_use_registry_active_sc_rules():
    service = SichuanQCService()
    service.rule_registry.load_active_rules = MagicMock(return_value=([_build_sc_rule("SC-001")], "pg_governance"))
    service._custom_rules_cache = []

    rules = await service._load_applicable_rules("入院记录")
    source = service.get_rule_source_overview()

    rule_ids = {str(item.get("rule_id") or "") for item in rules}
    assert "SC-001" in rule_ids
    assert source["sc_source"] == "pg_governance"
    assert source["sc_rule_count"] >= 1

