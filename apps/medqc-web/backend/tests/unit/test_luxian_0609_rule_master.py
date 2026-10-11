from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from app.services import luxian_0609_rule_master as rule_master_module
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_rule_master import (
    LUXIAN_0609_RULE_DEFINITION_VERSION,
    LUXIAN_0609_RULE_MASTER_VERSION,
    Luxian0609RuleMasterEntry,
    compile_luxian_0609_rule_master,
    get_luxian_0609_rule_master_entry,
    get_luxian_0609_rule_master_summary,
    load_luxian_0609_rule_master,
)


_RAW_MASTER_PATH = Path(__file__).resolve().parents[2] / "app/data/luxian_0609_rule_master_v1.json"
_APPROVED_EXTENSION_IDS = (
    "LX0609-06-01-01",
    "LX0609-06-01-03",
    "LX0609-06-03-01",
    "LX0609-06-03-02",
    "LX0609-06-02-01",
    "LX0609-09-01-02",
    "LX0609-08-01-05",
)


def _raw_master():
    return json.loads(_RAW_MASTER_PATH.read_text(encoding="utf-8"))


def _frozen_rule_ids() -> tuple[str, ...]:
    """迁移清单仅由测试读取，生产目录不依赖旧编号。"""
    mapping_path = Path(__file__).resolve().parents[3] / "docs/plans/lx0609-four-part-rule-code-mapping-v1.csv"
    with mapping_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert all(row["mapping_status"] == "frozen_identity_migration" for row in rows)
    assert len({row["legacy_rule_id"] for row in rows}) == len(rows)
    assert len({row["rule_id"] for row in rows}) == len(rows)
    return tuple(row["rule_id"] for row in sorted(rows, key=lambda row: row["legacy_rule_id"]))


@pytest.mark.unit
def test_rule_master_derives_its_scope_without_numeric_continuity() -> None:
    """子类允许预留编号；目录直接决定规则集合，不靠旧三位范围。"""

    payload = json.loads(rule_master_module._MASTER_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload["rules"], list)
    extension = dict(payload["rules"][-1])
    extension["rule_id"] = "LX0609-06-01-09"
    current_ids = tuple(item["rule_id"] for item in payload["rules"])
    payload["rules"].append(extension)

    entries = compile_luxian_0609_rule_master(payload)

    assert tuple(entry.rule_id for entry in entries) == (*current_ids, "LX0609-06-01-09")


def test_rule_master_keeps_declared_order_instead_of_sorting_identity() -> None:
    payload = json.loads(rule_master_module._MASTER_PATH.read_text(encoding="utf-8"))
    expected = tuple(item["rule_id"] for item in reversed(payload["rules"]))
    payload["rules"] = list(reversed(payload["rules"]))
    entries = compile_luxian_0609_rule_master(payload)
    assert tuple(entry.rule_id for entry in entries) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "invalid_scope",
    (
        "duplicate",
        "zero",
        "zero_category",
        "zero_subcategory",
        "zero_point",
        "malformed",
        "wrong_prefix",
        "empty",
    ),
)
def test_rule_master_rejects_duplicate_malformed_or_empty_scope(
    invalid_scope: str,
) -> None:
    payload = json.loads(rule_master_module._MASTER_PATH.read_text(encoding="utf-8"))

    if invalid_scope == "duplicate":
        payload["rules"][-1] = {
            **payload["rules"][-1],
            "rule_id": "LX0609-12-02-01",
        }
        match = "unique rule IDs"
    elif invalid_scope in {"zero_category", "zero_subcategory", "zero_point"}:
        part = {"zero_category": 1, "zero_subcategory": 2, "zero_point": 3}[invalid_scope]
        identity = "LX0609-01-01-01".split("-")
        identity[part] = "00"
        payload["rules"][0]["rule_id"] = "-".join(identity)
        match = "invalid LX0609 rule identity"
    elif invalid_scope == "zero":
        payload["rules"][0] = {
            **payload["rules"][0],
            "rule_id": "LX0609-000",
        }
        match = "invalid LX0609 rule identity"
    elif invalid_scope == "malformed":
        payload["rules"][-1] = {
            **payload["rules"][-1],
            "rule_id": "LX0609-76",
        }
        match = "invalid LX0609 rule identity"
    elif invalid_scope == "wrong_prefix":
        payload["rules"][-1] = {
            **payload["rules"][-1],
            "rule_id": "SC-077",
        }
        match = "invalid LX0609 rule identity"
    else:
        payload["rules"] = []
        match = "at least one rule"

    with pytest.raises(ValueError, match=match):
        compile_luxian_0609_rule_master(payload)


@pytest.mark.unit
def test_rule_master_preserves_frozen_migration_and_approved_extensions():
    payload = _raw_master()
    raw_rules = payload["rules"]
    raw_ids = tuple(raw["rule_id"] for raw in raw_rules)
    migrated_ids = _frozen_rule_ids()
    migrated_set = set(migrated_ids)
    entries = load_luxian_0609_rule_master()
    actual_ids = tuple(entry.rule_id for entry in entries)

    assert actual_ids == raw_ids
    assert len(set(raw_ids)) == len(raw_ids)
    assert tuple(rule_id for rule_id in raw_ids if rule_id in migrated_set) == migrated_ids
    assert tuple(rule_id for rule_id in actual_ids if rule_id in migrated_set) == migrated_ids
    assert tuple(rule_id for rule_id in raw_ids if rule_id not in migrated_set) == _APPROVED_EXTENSION_IDS
    assert migrated_set.isdisjoint(_APPROVED_EXTENSION_IDS)
    assert set(raw_ids) == migrated_set | set(_APPROVED_EXTENSION_IDS)
    statuses = Counter(raw["implementation_status"] for raw in raw_rules)
    assert set(statuses).issubset({"active", "contract_ready", "pending_definition"})
    assert get_luxian_0609_rule_master_summary() == {
        "total": len(raw_rules),
        **{status: statuses[status] for status in ("active", "contract_ready", "pending_definition")},
    }
    assert LUXIAN_0609_RULE_MASTER_VERSION == payload["master_version"] == "2026-09-22-identity-v1"
    assert LUXIAN_0609_RULE_DEFINITION_VERSION == payload["definition_version"] == "lx0609-defined-scope-2026-09-22-identity-v1"


@pytest.mark.unit
def test_execution_catalog_is_exactly_the_active_master_projection():
    master_active_ids = tuple(
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "active"
    )
    execution_ids = tuple(rule["rule_id"] for rule in load_luxian_0609_rules())

    assert execution_ids == master_active_ids
    assert "LX0609-06-04-01" in execution_ids
    assert "LX0609-10-03-01" in execution_ids


@pytest.mark.unit
def test_recently_defined_rules_are_activated_with_the_full_catalog():
    ready_ids = {
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "contract_ready"
    }

    assert ready_ids == set()
    assert get_luxian_0609_rule_master_entry("lx0609-06-04-01").implementation_status == "active"
    assert get_luxian_0609_rule_master_entry("LX0609-07-01-03").implementation_status == "active"


@pytest.mark.unit
def test_pending_rules_keep_customer_definition_gaps_visible():
    pending_entries = tuple(
        entry
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "pending_definition"
    )

    assert tuple(entry.rule_id for entry in pending_entries) == (
        "LX0609-06-03-01",
    )
    assert all(entry.definition_note for entry in pending_entries)
    assert all(entry.pending_definition_note for entry in pending_entries)
    assert all(entry.phase_status == "pending_definition" for entry in pending_entries)
    assert all(entry.rule_id not in {rule["rule_id"] for rule in load_luxian_0609_rules()} for entry in pending_entries)


@pytest.mark.unit
def test_rule_master_requires_complete_customer_policy_metadata_for_all_rules():
    entries = load_luxian_0609_rule_master()

    assert tuple(entry.rule_id for entry in entries) == tuple(raw["rule_id"] for raw in _raw_master()["rules"])
    migrated_ids = set(_frozen_rule_ids())
    assert all(entry.policy_sources for entry in entries)
    assert all("customer_confirmed" in entry.policy_sources for entry in entries if entry.rule_id in migrated_ids)
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
            rule_id="LX0609-01-01-01",
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
            rule_id="LX0609-01-01-01",
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

    assert entries["LX0609-02-01-05"].policy_sources == (
        "sichuan_2023_standard",
        "customer_confirmed",
    )
    assert "动态改变" in entries["LX0609-02-01-05"].policy_summary
    assert "24小时" in entries["LX0609-02-01-05"].policy_summary
    assert entries["LX0609-02-01-05"].pending_definition_note == ""

    assert entries["LX0609-06-01-02"].policy_sources == (
        "sichuan_2026_handbook",
        "customer_confirmed",
        "hospital_local_extension",
    )
    assert "order_id" in entries["LX0609-06-01-02"].policy_summary
    assert "exam_id" in entries["LX0609-06-01-02"].policy_summary
    assert entries["LX0609-06-01-02"].pending_definition_note == ""

    assert entries["LX0609-06-01-05"].policy_sources == (
        "sichuan_2026_handbook",
        "customer_confirmed",
        "hospital_local_extension",
    )
    assert "明确异常病灶或异常征象" in entries["LX0609-06-01-05"].policy_summary
    assert "不要求原文出现“阳性”" in entries["LX0609-06-01-05"].policy_summary
    assert "24小时" in entries["LX0609-06-01-05"].policy_summary

    assert entries["LX0609-12-01-02"].policy_sources == (
        "sichuan_2026_handbook",
        "customer_confirmed",
        "hospital_local_extension",
    )
    assert "相似度≥70%" in entries["LX0609-12-01-02"].policy_summary
    assert "3至5组" in entries["LX0609-12-01-02"].policy_summary
    assert "一次LLM" in entries["LX0609-12-01-02"].policy_summary
    assert entries["LX0609-01-01-02"].policy_sources == (
        "customer_confirmed",
        "hospital_local_extension",
    )
    assert "主诉≤20字" in entries["LX0609-01-01-02"].policy_summary

    assert entries["LX0609-03-01-01"].policy_sources == (
        "sichuan_2023_standard",
        "customer_confirmed",
    )
    assert "会诊意见及执行情况" in entries["LX0609-03-01-01"].policy_summary
    assert "任一建议完全未找到执行证据" in entries["LX0609-03-01-04"].policy_summary
    assert "未明确具体措施" in entries["LX0609-03-01-04"].policy_summary

    implant = entries["LX0609-04-02-04"]
    assert all(
        field in implant.policy_summary
        for field in ("名称", "种类", "规格或型号", "材质", "数量")
    )
    assert "条码不属于本规则必填字段" in implant.policy_summary
    assert "病程仅辅助确认实际使用" in implant.policy_summary
    assert "正式手术记录" in implant.policy_summary
    assert "真实病例金标" in implant.pending_definition_note

    treatment_order = entries["LX0609-05-03-01"]
    assert "暂不执行" in treatment_order.policy_summary
    assert "不得因资料缺失" in treatment_order.policy_summary
    assert "真实病例金标" in treatment_order.pending_definition_note
    assert "院内绩效优先国家目录" in entries["LX0609-04-01-03"].policy_summary
    assert "缺任一项" in entries["LX0609-07-01-02"].policy_summary
    assert "暂不执行" in entries["LX0609-07-04-02"].policy_summary
    assert "不得因收费资料缺失" in entries["LX0609-07-04-02"].policy_summary
    # 院方口径（2026-10-11）：056 按重点抗菌药物七类清单恢复执行。
    assert "七类共25个药品" in entries["LX0609-05-01-04"].policy_summary
    # 院方口径（2026-10-11）：075 按院方 92 项有创操作目录恢复执行。
    assert "共92项" in entries["LX0609-10-03-01"].policy_summary
    assert "首页手术操作编码" in entries["LX0609-10-03-01"].policy_summary
    assert entries["LX0609-10-03-01"].phase_status == "phase_1_target"
    assert "乙肝五项、艾滋、丙肝、梅毒、谷丙转氨酶" in entries["LX0609-07-01-03"].policy_summary
    assert "急诊补检" in entries["LX0609-07-01-03"].pending_definition_note
