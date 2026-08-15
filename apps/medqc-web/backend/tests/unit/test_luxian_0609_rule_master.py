from __future__ import annotations

import pytest

from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_rule_master import (
    LUXIAN_0609_RULE_DEFINITION_VERSION,
    LUXIAN_0609_RULE_MASTER_VERSION,
    Luxian0609RuleMasterEntry,
    get_luxian_0609_rule_master_entry,
    get_luxian_0609_rule_master_summary,
    load_luxian_0609_rule_master,
)


@pytest.mark.unit
def test_rule_master_is_the_complete_ordered_75_rule_scope():
    entries = load_luxian_0609_rule_master()

    assert tuple(entry.rule_id for entry in entries) == tuple(
        f"LX0609-{index:03d}" for index in range(1, 76)
    )
    assert len({entry.rule_id for entry in entries}) == 75
    assert get_luxian_0609_rule_master_summary() == {
        "total": 75,
        "active": 75,
        "contract_ready": 0,
        "pending_definition": 0,
    }
    assert LUXIAN_0609_RULE_MASTER_VERSION == "2026-08-15"
    assert LUXIAN_0609_RULE_DEFINITION_VERSION == "lx0609-defined-scope-2026-08-15"


@pytest.mark.unit
def test_execution_catalog_is_exactly_the_active_master_projection():
    master_active_ids = tuple(
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "active"
    )
    execution_ids = tuple(rule["rule_id"] for rule in load_luxian_0609_rules())

    assert execution_ids == master_active_ids
    assert "LX0609-052" in execution_ids
    assert "LX0609-075" in execution_ids


@pytest.mark.unit
def test_recently_defined_rules_are_activated_with_the_full_catalog():
    ready_ids = {
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "contract_ready"
    }

    assert ready_ids == set()
    assert get_luxian_0609_rule_master_entry("lx0609-052").implementation_status == "active"
    assert get_luxian_0609_rule_master_entry("LX0609-070").implementation_status == "active"


@pytest.mark.unit
def test_pending_rules_keep_customer_definition_gaps_visible():
    pending_entries = tuple(
        entry
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "pending_definition"
    )

    assert pending_entries == ()


@pytest.mark.unit
def test_rule_master_requires_complete_customer_policy_metadata_for_all_75_rules():
    entries = load_luxian_0609_rule_master()

    assert len(entries) == 75
    assert all(entry.policy_sources for entry in entries)
    assert all("customer_confirmed" in entry.policy_sources for entry in entries)
    assert all(entry.policy_summary for entry in entries)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("policy_sources", "policy_summary", "match"),
    (
        ((), "当前执行口径。", "policy sources"),
        (("customer_confirmed", "customer_confirmed"), "当前执行口径。", "duplicates"),
        (("unknown",), "当前执行口径。", "unknown policy source"),
        (("customer_confirmed", "sichuan_2023_standard"), "当前执行口径。", "stable order"),
        (("customer_confirmed",), "", "policy summary"),
        (("customer_confirmed",), "甲" * 241, "policy summary"),
    ),
)
def test_rule_master_rejects_invalid_policy_metadata(
    policy_sources: tuple[str, ...],
    policy_summary: str,
    match: str,
):
    with pytest.raises(ValueError, match=match):
        Luxian0609RuleMasterEntry(
            rule_id="LX0609-001",
            source_document="入院记录",
            qc_point="入院后24小时内是否完成",
            implementation_status="active",
            policy_sources=policy_sources,
            policy_summary=policy_summary,
        )


@pytest.mark.unit
def test_rule_master_rejects_too_long_pending_definition_note():
    with pytest.raises(ValueError, match="pending definition note"):
        Luxian0609RuleMasterEntry(
            rule_id="LX0609-001",
            source_document="入院记录",
            qc_point="入院后24小时内是否完成",
            implementation_status="active",
            policy_sources=("customer_confirmed",),
            policy_summary="当前执行口径。",
            pending_definition_note="甲" * 241,
        )


@pytest.mark.unit
def test_confirmed_policy_metadata_preserves_key_rule_contracts():
    entries = {entry.rule_id: entry for entry in load_luxian_0609_rule_master()}

    assert entries["LX0609-009"].policy_sources == (
        "sichuan_2023_standard",
        "customer_confirmed",
    )
    assert "动态改变" in entries["LX0609-009"].policy_summary
    assert "24小时" in entries["LX0609-009"].policy_summary
    assert entries["LX0609-009"].pending_definition_note == ""

    assert entries["LX0609-010"].policy_sources == (
        "sichuan_2026_handbook",
        "customer_confirmed",
        "hospital_local_extension",
    )
    assert "order_id" in entries["LX0609-010"].policy_summary
    assert "exam_id" in entries["LX0609-010"].policy_summary
    assert entries["LX0609-010"].pending_definition_note == ""

    assert entries["LX0609-012"].policy_sources == (
        "sichuan_2026_handbook",
        "customer_confirmed",
        "hospital_local_extension",
    )
    assert "明确异常病灶或异常征象" in entries["LX0609-012"].policy_summary
    assert "不要求原文出现“阳性”" in entries["LX0609-012"].policy_summary
    assert "24小时" in entries["LX0609-012"].policy_summary

    assert entries["LX0609-017"].policy_sources == (
        "sichuan_2026_handbook",
        "customer_confirmed",
        "hospital_local_extension",
    )
    assert "相似度≥70%" in entries["LX0609-017"].policy_summary
    assert "3至5组" in entries["LX0609-017"].policy_summary
    assert "一次LLM" in entries["LX0609-017"].policy_summary
    assert entries["LX0609-018"].policy_sources == (
        "customer_confirmed",
        "hospital_local_extension",
    )
    assert "主诉≤20字" in entries["LX0609-018"].policy_summary

    assert entries["LX0609-020"].policy_sources == (
        "sichuan_2023_standard",
        "customer_confirmed",
    )
    assert "会诊意见及执行情况" in entries["LX0609-020"].policy_summary
    assert "仅“遵嘱执行”" in entries["LX0609-023"].policy_summary

    assert "不参与正式结论" in entries["LX0609-025"].policy_summary
    assert "正式必填字段" in entries["LX0609-025"].pending_definition_note
    assert "院内绩效优先国家目录" in entries["LX0609-040"].policy_summary
    assert "未同时齐备" in entries["LX0609-044"].policy_summary
    assert "暂不执行" in entries["LX0609-049"].policy_summary
    assert "不得因收费资料缺失" in entries["LX0609-049"].policy_summary
    assert "乙肝五项、艾滋、丙肝、梅毒、谷丙转氨酶" in entries["LX0609-070"].policy_summary
    assert "急诊补检" in entries["LX0609-070"].pending_definition_note
