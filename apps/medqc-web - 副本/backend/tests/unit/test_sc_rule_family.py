from __future__ import annotations

from app.services.sc_rule_family import (
    ALLOWED_RULE_FAMILIES,
    build_draft_sc_rule_family_map,
    list_sc_rule_ids_from_json_baseline,
    load_sc_rule_family_map,
    load_sc_rules_from_json_baseline,
    resolve_rule_family,
    validate_sc_rule_family_map,
)


def test_sc_rule_family_map_should_cover_sc_146_baseline():
    mapping = load_sc_rule_family_map()
    expected_rule_ids = list_sc_rule_ids_from_json_baseline()
    report = validate_sc_rule_family_map(mapping, expected_rule_ids=expected_rule_ids)

    assert report["ok"] is True
    assert len(mapping) == 146
    assert report["mapped_rule_count"] == 146


def test_build_draft_map_should_only_emit_allowed_families():
    rules = load_sc_rules_from_json_baseline()
    mapping = build_draft_sc_rule_family_map(rules)

    assert len(mapping) == 146
    assert set(mapping.values()).issubset(set(ALLOWED_RULE_FAMILIES))


def test_resolve_rule_family_should_use_mapping_for_sc_rule():
    mapping = load_sc_rule_family_map()
    rule = {
        "rule_id": "SC-001",
        "name": "无入院记录(或再次/多次入院记录)或24小时内入出院(死亡)记录。",
    }

    assert resolve_rule_family(rule, sc_mapping=mapping) == mapping["SC-001"]


def test_resolve_rule_family_should_fallback_to_general_for_non_sc_rule():
    rule = {
        "rule_id": "LX-001",
        "name": "首页测试规则",
    }

    assert resolve_rule_family(rule, sc_mapping={}) == "general"
