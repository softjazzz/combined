from __future__ import annotations

from tests.luxian_0609_identity_test_support import published_rule_ids

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.luxian_0609.customer_rule_package import RULE_FAMILY_DEFINITIONS
from app.services.luxian_0609.native_package import (
    EXECUTION_MODE_COMPATIBILITY,
    EXECUTION_MODE_NATIVE_ASYNC,
    EXECUTION_MODE_NATIVE_SYNC,
    assert_luxian_0609_formal_package_plan_native_only,
    build_luxian_0609_dependency_inventory,
    build_luxian_0609_package_plan,
    build_luxian_0609_package_plan_from_settings,
    resolve_package_entry_execution_rule_ids,
    resolve_selected_customer_rule_ids,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules


_DATA_PATH = Path(__file__).resolve().parents[2] / "app/data"


def _raw_master_rules():
    return json.loads((_DATA_PATH / "luxian_0609_rule_master_v1.json").read_text(encoding="utf-8"))["rules"]


def _raw_catalog_rules():
    return [
        *json.loads((_DATA_PATH / "luxian_0609_rules_v1.json").read_text(encoding="utf-8")),
        *json.loads((_DATA_PATH / "luxian_0609_phase1_rules_extension_v1.json").read_text(encoding="utf-8")),
    ]


# d897689ca^ 的原 84 项有序映射，保留累计 125 依赖及逐项身份，不能只提高总数。
_PRE_DISCHARGE_COMPATIBILITY_DEPENDENCIES = (
    ('LX0609-01-01-01', ('SC-002',)),
    ('LX0609-01-02-01', ('CL-081', 'SC-021')),
    ('LX0609-04-02-01', ('LX-026', 'SC-096')),
    ('LX0609-09-01-01', ('SC-054',)),
    ('LX0609-02-01-01', ('SC-048',)),
    ('LX0609-02-01-02', ('SC-049', 'CL-080')),
    ('LX0609-02-01-03', ('LXE-18',)),
    ('LX0609-02-01-04', ('SC-051', 'CL-231')),
    ('LX0609-02-01-05', ('SC-051', 'CL-231')),
    ('LX0609-06-01-02', ('LXE-23',)),
    ('LX0609-06-01-04', ('LXE-23', 'SC-114')),
    ('LX0609-06-01-05', ('LXE-23',)),
    ('LX0609-06-02-03', ('SC-037', 'SC-099', 'SC-114')),
    ('LX0609-06-03-03', ('LXE-24',)),
    ('LX0609-06-03-04', ('LXE-24', 'LX-031')),
    ('LX0609-12-01-01', ('CL-273',)),
    ('LX0609-12-01-02', ('CL-275', 'LXE-21')),
    ('LX0609-01-01-02', ('SC-008', 'LX-001', 'CL-068')),
    ('LX0609-06-02-02', ('SC-037', 'SC-099')),
    ('LX0609-03-01-01', ('LX-017', 'CL-250')),
    ('LX0609-03-01-02', ('SC-068', 'LX-015')),
    ('LX0609-03-01-03', ('SC-069',)),
    ('LX0609-03-01-04', ('CL-248', 'CL-250', 'CL-071')),
    ('LX0609-04-02-03', ('SC-099',)),
    ('LX0609-04-02-04', ('SC-100', 'SC-101')),
    ('LX0609-05-02-01', ('SC-034', 'SC-146')),
    ('LX0609-08-01-04', ('SC-116', 'SC-124')),
    ('LX0609-05-01-01', ('SC-044', 'LX-012')),
    ('LX0609-04-01-01', ('CL-181', 'SC-081')),
    ('LX0609-04-02-02', ('LX-025', 'SC-095')),
    ('LX0609-04-02-05', ('LX-027', 'CL-173', 'SC-098')),
    ('LX0609-04-03-01', ('SC-102', 'LXE-33')),
    ('LX0609-11-01-01', ('SC-087', 'LXE-31')),
    ('LX0609-11-02-01', ('LX-022', 'SC-090')),
    ('LX0609-11-02-02', ('SC-090', 'LX-022')),
    ('LX0609-04-04-01', ('LX-020',)),
    ('LX0609-04-04-02', ('LX-020', 'SC-090')),
    ('LX0609-04-04-03', ('SC-090',)),
    ('LX0609-04-01-02', ('LX-019', 'SC-082')),
    ('LX0609-04-01-03', ('SC-083', 'CL-108')),
    ('LX0609-11-03-01', ('SC-133', 'LXE-52')),
    ('LX0609-11-03-02', ('SC-134', 'SC-133')),
    ('LX0609-07-01-01', ('SC-073', 'SC-138')),
    ('LX0609-07-01-02', ('SC-074', 'LX-018')),
    ('LX0609-07-02-01', ('SC-074', 'LX-018')),
    ('LX0609-07-02-02', ('SC-074', 'LX-018')),
    ('LX0609-07-03-01', ('CL-255', 'SC-074')),
    ('LX0609-07-04-01', ('CL-256', 'CL-208', 'SC-074')),
    ('LX0609-07-04-02', ('SC-146',)),
    ('LX0609-03-02-01', ('LX0609-03-02-01',)),
    ('LX0609-09-02-01', ('LX0609-09-02-01',)),
    ('LX0609-06-04-01', ('LX0609-06-04-01',)),
    ('LX0609-06-04-02', ('LX0609-06-04-02',)),
    ('LX0609-05-01-02', ('LX0609-05-01-02',)),
    ('LX0609-05-01-03', ('LX0609-05-01-03',)),
    ('LX0609-05-01-04', ('LX0609-05-01-04',)),
    ('LX0609-05-01-05', ('LX0609-05-01-05',)),
    ('LX0609-05-01-06', ('LX0609-05-01-06',)),
    ('LX0609-05-03-01', ('LX0609-05-03-01',)),
    ('LX0609-04-02-06', ('LX0609-04-02-06',)),
    ('LX0609-08-01-01', ('LX0609-08-01-01',)),
    ('LX0609-08-01-02', ('LX0609-08-01-02',)),
    ('LX0609-08-01-03', ('LX0609-08-01-03',)),
    ('LX0609-04-05-01', ('LX0609-04-05-01',)),
    ('LX0609-04-05-02', ('LX0609-04-05-02',)),
    ('LX0609-04-05-03', ('LX0609-04-05-03',)),
    ('LX0609-08-02-01', ('LX0609-08-02-01',)),
    ('LX0609-08-02-02', ('LX0609-08-02-02',)),
    ('LX0609-04-02-07', ('LX0609-04-02-07',)),
    ('LX0609-07-01-03', ('LX0609-07-01-03',)),
    ('LX0609-10-01-01', ('LX0609-10-01-01',)),
    ('LX0609-10-02-01', ('LX0609-10-02-01',)),
    ('LX0609-10-02-02', ('LX0609-10-02-02',)),
    ('LX0609-12-02-01', ('LX0609-12-02-01',)),
    ('LX0609-10-03-01', ('LX0609-10-03-01',)),
    ('LX0609-04-02-08', ('LX0609-04-02-08',)),
    ('LX0609-01-02-02', ('LX0609-01-02-02',)),
    ('LX0609-04-01-04', ('LX0609-04-01-04',)),
    ('LX0609-04-01-05', ('LX0609-04-01-05',)),
    ('LX0609-06-01-01', ('LX0609-06-01-01',)),
    ('LX0609-06-01-03', ('LX0609-06-01-03',)),
    ('LX0609-06-03-02', ('LX0609-06-03-02',)),
    ('LX0609-06-02-01', ('LX0609-06-02-01',)),
    ('LX0609-09-01-02', ('LX0609-09-01-02',)),
)


def _assert_full_catalog_plan_partition(plan, *, compatibility_exception: str | None = None) -> None:
    raw_active = tuple(raw for raw in _raw_master_rules() if raw["implementation_status"] == "active")
    expected_selected = tuple(raw["rule_id"] for raw in raw_active)
    expected_pending = tuple(
        raw["rule_id"] for raw in raw_active
        if raw.get("phase_status", "phase_1_target") != "phase_1_target"
    )
    expected_executable = tuple(rule_id for rule_id in expected_selected if rule_id not in expected_pending)
    expected_native = tuple(rule_id for rule_id in expected_executable if rule_id != compatibility_exception)
    sync_ids = set(plan.native_sync_rule_ids)
    async_ids = set(plan.native_async_rule_ids)
    assert plan.selected_rule_ids == expected_selected
    assert plan.not_executed_rule_ids == expected_pending
    assert plan.executable_rule_ids == expected_executable
    assert sync_ids.isdisjoint(async_ids)
    assert tuple(rule_id for rule_id in expected_selected if rule_id in sync_ids | async_ids) == expected_native
    assert sync_ids | async_ids == set(expected_native)
    assert tuple(rule_id for rule_id in expected_selected if rule_id in sync_ids) == plan.native_sync_rule_ids
    assert tuple(rule_id for rule_id in expected_selected if rule_id in async_ids) == plan.native_async_rule_ids
    assert set(expected_native).isdisjoint(expected_pending)
    expected_compatibility = {compatibility_exception} if compatibility_exception else set()
    assert set(expected_native).isdisjoint(expected_compatibility)
    assert set(expected_native) | set(expected_pending) | expected_compatibility == set(expected_selected)


@pytest.mark.unit
def test_native_rule_does_not_require_a_legacy_rule_mapping():
    rule_id = "LX0609-01-01-01"
    wrapper = next(
        item for item in load_luxian_0609_rules() if item["rule_id"] == rule_id
    )
    inventory = build_luxian_0609_dependency_inventory(
        rules=[{**wrapper, "mapped_rule_ids": []}],
        family_definitions=[
            {"key": "basic_timeliness", "name": "基础时限", "rule_ids": (rule_id,)}
        ],
    )

    assert inventory[0].execution_mode == EXECUTION_MODE_NATIVE_SYNC
    assert inventory[0].compatibility_rule_ids == ()


@pytest.mark.unit
def test_compatibility_rule_still_requires_a_legacy_rule_mapping():
    rule_id = "LX0609-99-99-01"
    wrapper = load_luxian_0609_rules()[0]
    with pytest.raises(ValueError, match="missing compatibility dependency"):
        build_luxian_0609_dependency_inventory(
            rules=[{**wrapper, "rule_id": rule_id, "mapped_rule_ids": []}],
            family_definitions=[
                {"key": "extension_test", "name": "测试扩展", "rule_ids": (rule_id,)}
            ],
        )


@pytest.mark.unit
def test_dependency_inventory_covers_raw_active_catalog_and_preserves_frozen_dependencies():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    expected_ids = tuple(raw["rule_id"] for raw in _raw_master_rules() if raw["implementation_status"] == "active")
    assert expected_ids
    assert len(set(expected_ids)) == len(expected_ids)
    assert tuple(item.rule_id for item in inventory) == expected_ids
    assert tuple(str(item["rule_id"]) for item in load_luxian_0609_rules()) == expected_ids
    raw_wrappers = _raw_catalog_rules()
    assert len({raw["rule_id"] for raw in raw_wrappers}) == len(raw_wrappers)
    assert {raw["rule_id"] for raw in raw_wrappers} == set(expected_ids)
    wrappers_by_id = {raw["rule_id"]: raw for raw in raw_wrappers}
    family_members = [rule_id for family in RULE_FAMILY_DEFINITIONS for rule_id in family["rule_ids"]]
    assert Counter(family_members) == Counter(expected_ids)
    for item in inventory:
        raw = wrappers_by_id[item.rule_id]
        owners = [family for family in RULE_FAMILY_DEFINITIONS if item.rule_id in family["rule_ids"]]
        assert len(owners) == 1
        assert (item.family_key, item.family_name) == (owners[0]["key"], owners[0]["name"])
        assert item.compatibility_rule_ids == tuple(dict.fromkeys(raw.get("mapped_rule_ids", ()))), item.rule_id
        assert item.rule_version == raw["rule_version"], item.rule_id
        assert item.applicable_documents == tuple(raw["applicable_documents"]), item.rule_id
        assert item.data_dependencies == tuple(raw["data_dependencies"]), item.rule_id
        assert item.dependency_type == raw["dependency_type"], item.rule_id
        assert item.executor_type == raw["executor_type"], item.rule_id
    assert {item.family_key for item in inventory} == {
        "basic_timeliness",
        "course_quality",
        "exam_lab",
        "consultation_quality",
        "surgery_anesthesia",
        "transfusion",
        "tumor_pathology",
        "extended_document",
    }
    frozen_ids = {rule_id for rule_id, _dependencies in _PRE_DISCHARGE_COMPATIBILITY_DEPENDENCIES}
    assert tuple((item.rule_id, item.compatibility_rule_ids) for item in inventory if item.rule_id in frozen_ids) == _PRE_DISCHARGE_COMPATIBILITY_DEPENDENCIES
    assert sum(len(item.compatibility_rule_ids) for item in inventory if item.rule_id in frozen_ids) == 125
    assert tuple((item.rule_id, item.compatibility_rule_ids) for item in inventory if item.rule_id not in frozen_ids) == (
        ("LX0609-08-01-05", ("LX0609-08-01-05",)),
        ("LX0609-03-01-05", ("LX0609-03-01-05",)),
        ("LX0609-04-02-09", ("LX0609-04-02-09",)),
        ("LX0609-10-04-01", ("LX0609-10-04-01",)),
        ("LX0609-06-03-05", ("LX0609-06-03-05",)),
        ("LX0609-06-03-06", ("LX0609-06-03-06",)),
    )
    assert all(item.applicable_documents for item in inventory)
    assert all(item.dependency_type for item in inventory)


@pytest.mark.unit
def test_dependency_inventory_exposes_current_native_and_compatibility_boundary():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    modes = {item.rule_id: item.execution_mode for item in inventory}

    assert {rule_id for rule_id, mode in modes.items() if mode == EXECUTION_MODE_NATIVE_SYNC} == {
        "LX0609-01-01-01",
        "LX0609-01-02-01",
        "LX0609-09-01-01",
        "LX0609-02-01-01",
        "LX0609-02-01-02",
        "LX0609-04-02-02",
        "LX0609-04-03-01",
        "LX0609-09-01-02",
    }
    assert {rule_id for rule_id, mode in modes.items() if mode == EXECUTION_MODE_NATIVE_ASYNC} == {
        "LX0609-06-01-01",
        "LX0609-06-01-02",
        "LX0609-06-01-04",
        "LX0609-06-01-05",
        "LX0609-06-02-03",
        "LX0609-06-03-03",
        "LX0609-06-03-04",
        "LX0609-06-02-02",
        "LX0609-05-02-01",
        "LX0609-08-01-04",
        "LX0609-03-01-01",
        "LX0609-03-01-02",
        "LX0609-03-01-03",
        "LX0609-03-01-04",
        "LX0609-03-01-05",
        "LX0609-04-01-03",
        "LX0609-11-03-01",
        "LX0609-11-03-02",
        "LX0609-07-01-01",
        "LX0609-07-01-02",
        "LX0609-07-02-01",
        "LX0609-07-02-02",
        "LX0609-07-03-01",
        "LX0609-07-04-01",
        "LX0609-07-04-02",
        "LX0609-03-02-01",
        "LX0609-06-04-01",
        "LX0609-06-04-02",
        "LX0609-05-01-02",
        "LX0609-05-01-03",
        "LX0609-05-01-04",
        "LX0609-05-01-05",
        "LX0609-05-01-06",
        "LX0609-05-03-01",
        "LX0609-08-01-03",
        "LX0609-08-01-05",
        "LX0609-07-01-03",
        "LX0609-10-03-01",
        "LX0609-04-02-08",
        "LX0609-04-02-09",
        "LX0609-10-04-01",
        "LX0609-06-03-05", "LX0609-06-03-06",
        "LX0609-01-02-02",
        "LX0609-04-01-04",
        "LX0609-04-01-05",
        "LX0609-04-02-01",
        "LX0609-02-01-03",
        "LX0609-02-01-04",
        "LX0609-02-01-05",
        "LX0609-12-01-01",
        "LX0609-12-01-02",
        "LX0609-01-01-02",
        "LX0609-04-02-03",
        "LX0609-04-02-04",
        "LX0609-05-01-01",
        "LX0609-04-01-01",
        "LX0609-04-02-05",
        "LX0609-11-01-01",
        "LX0609-11-02-01",
        "LX0609-11-02-02",
        "LX0609-04-04-01",
        "LX0609-04-04-02",
        "LX0609-04-04-03",
        "LX0609-04-01-02",
        "LX0609-09-02-01",
        "LX0609-04-02-06",
        "LX0609-08-01-01",
        "LX0609-08-01-02",
        "LX0609-04-05-01",
        "LX0609-04-05-02",
        "LX0609-04-05-03",
        "LX0609-08-02-01",
        "LX0609-08-02-02",
        "LX0609-04-02-07",
        "LX0609-10-01-01",
        "LX0609-10-02-01",
        "LX0609-10-02-02",
        "LX0609-12-02-01",
        "LX0609-06-01-03",
        "LX0609-06-03-02",
        "LX0609-06-02-01",
    }
    # 培养医嘱—病程一致性仍只登记；CT一致性已进入原生异步族。
    assert {
        rule_id
        for rule_id, mode in modes.items()
        if mode == EXECUTION_MODE_COMPATIBILITY
    } == set()
    assert "LX0609-06-03-01" not in modes
    assert modes["LX0609-06-01-01"] == EXECUTION_MODE_NATIVE_ASYNC


@pytest.mark.unit
def test_exam_lab_family_flag_partitions_only_five_customer_rules():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    selected = ["LX0609-06-01-02", "LX0609-06-01-04", "LX0609-06-01-05", "LX0609-06-03-03", "LX0609-06-03-04"]

    enabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_exam_lab_enabled=True,
    )
    disabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_exam_lab_enabled=False,
    )

    assert enabled.native_async_rule_ids == tuple(selected)
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == (("exam_lab", tuple(selected)),)
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == tuple(selected)


@pytest.mark.unit
def test_formal_plan_rejects_exam_lab_compatibility_and_accepts_fully_native_plan():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    common = {
        "inventory": inventory,
        "selected_rule_ids": ["LX0609-06-01-02"],
        "native_sync_enabled": True,
        "native_mdt_enabled": False,
    }
    compatibility = build_luxian_0609_package_plan(
        **common,
        native_exam_lab_enabled=False,
    )
    fully_native = build_luxian_0609_package_plan(
        **common,
        native_exam_lab_enabled=True,
    )

    with pytest.raises(ValueError, match="正式质控禁止兼容执行.*LX0609-06-01-02.*LXE-23"):
        assert_luxian_0609_formal_package_plan_native_only(
            compatibility,
            context="test",
        )
    assert_luxian_0609_formal_package_plan_native_only(
        fully_native,
        context="test",
    ) is fully_native

    pending = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=["LX0609-04-02-04"],
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_surgery_gate_enabled=True,
    )
    assert pending.not_executed_rule_ids == ("LX0609-04-02-04",)
    assert "LX0609-04-02-04" in pending.prepared_rule_ids_to_remove
    assert_luxian_0609_formal_package_plan_native_only(
        pending,
        context="test",
    ) is pending


@pytest.mark.unit
def test_transfusion_family_flag_partitions_only_nine_customer_rules():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    selected = list(published_rule_ids(41, 49))

    enabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_transfusion_enabled=True,
    )
    disabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_transfusion_enabled=False,
    )

    pending_ids = {raw["rule_id"] for raw in _raw_master_rules() if raw.get("phase_status") == "pending_definition"}
    expected_executable = tuple(rule_id for rule_id in selected if rule_id not in pending_ids)
    expected_pending = tuple(rule_id for rule_id in selected if rule_id in pending_ids)
    assert enabled.native_async_rule_ids == expected_executable
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == ((("transfusion", expected_executable),) if expected_executable else ())
    assert enabled.not_executed_rule_ids == expected_pending
    assert "LX0609-07-04-02" in enabled.prepared_rule_ids_to_remove
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == expected_executable
    assert disabled.not_executed_rule_ids == expected_pending
    assert all(rule_id in disabled.prepared_rule_ids_to_remove for rule_id in expected_pending)
    assert "LX0609-07-04-02" in disabled.prepared_rule_ids_to_remove


@pytest.mark.unit
def test_tumor_pathology_family_flag_partitions_only_four_customer_rules():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    selected = ["LX0609-06-02-03", "LX0609-06-02-02", "LX0609-05-02-01", "LX0609-08-01-04"]

    enabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_tumor_pathology_enabled=True,
    )
    disabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_tumor_pathology_enabled=False,
    )

    assert enabled.native_async_rule_ids == tuple(selected)
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == (("tumor_pathology", tuple(selected)),)
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == tuple(selected)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("selected", "flag_name", "executor_key"),
    [
        (
            ["LX0609-02-01-03", "LX0609-02-01-04", "LX0609-02-01-05", "LX0609-12-01-01", "LX0609-12-01-02", "LX0609-01-01-02"],
            "native_course_quality_enabled",
            "course_quality",
        ),
        (
            ["LX0609-04-02-01", "LX0609-04-02-03", "LX0609-04-02-04", "LX0609-05-01-01", "LX0609-04-02-05", "LX0609-11-01-01"],
            "native_surgery_gate_enabled",
            "surgery_gate",
        ),
        (
            ["LX0609-11-02-01", "LX0609-11-02-02", "LX0609-04-04-01", "LX0609-04-04-02", "LX0609-04-04-03", "LX0609-04-01-02"],
            "native_surgery_document_enabled",
            "surgery_document",
        ),
    ],
)
def test_remaining_family_flags_partition_only_their_customer_rules(
    selected, flag_name, executor_key
):
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    common = {
        "inventory": inventory,
        "selected_rule_ids": selected,
        "native_sync_enabled": True,
        "native_mdt_enabled": False,
    }

    enabled = build_luxian_0609_package_plan(**common, **{flag_name: True})
    disabled = build_luxian_0609_package_plan(**common, **{flag_name: False})

    expected_executable = tuple(raw["rule_id"] for raw in _raw_master_rules()
                                if raw["rule_id"] in selected and raw.get("phase_status", "phase_1_target") == "phase_1_target")
    assert enabled.executable_rule_ids == expected_executable
    expected_pending = tuple(
        rule_id for rule_id in selected if rule_id not in expected_executable
    )
    assert enabled.native_async_rule_ids == expected_executable
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == (((executor_key, expected_executable),) if expected_executable else ())
    assert enabled.not_executed_rule_ids == expected_pending
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == expected_executable
    assert disabled.not_executed_rule_ids == expected_pending


@pytest.mark.unit
@pytest.mark.parametrize(
    ("native_mdt_enabled", "native_extended_document_enabled", "expected_native"),
    (
        (False, False, ()),
        (False, True, ("LX0609-03-02-01",)),
        (True, False, ("LX0609-04-01-03",)),
        (True, True, ("LX0609-04-01-03", "LX0609-03-02-01")),
    ),
)
def test_mdt_and_extended_document_gates_are_independent(
    native_mdt_enabled,
    native_extended_document_enabled,
    expected_native,
):
    """040 仅受 MDT 门控，extended_document 仅受自身门控。"""

    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    selected = (
        "LX0609-04-01-03",
        "LX0609-03-02-01",
        "LX0609-05-03-01",
    )

    plan = build_luxian_0609_package_plan_from_settings(
        inventory=inventory,
        selected_rule_ids=selected,
        settings=SimpleNamespace(
            LUXIAN_0609_NATIVE_EXECUTION_ENABLED=True,
            LUXIAN_0609_NATIVE_MDT_040_ENABLED=native_mdt_enabled,
            LUXIAN_0609_NATIVE_EXTENDED_DOCUMENT_ENABLED=(
                native_extended_document_enabled
            ),
        ),
    )

    pending_ids = {raw["rule_id"] for raw in _raw_master_rules() if raw.get("phase_status") == "pending_definition"}
    current_native = tuple(rule_id for rule_id in expected_native if rule_id not in pending_ids)
    assert plan.native_async_rule_ids == current_native
    assert plan.not_executed_rule_ids == tuple(rule_id for rule_id in selected if rule_id in pending_ids)
    assert plan.compatibility_rule_ids == tuple(
        rule_id for rule_id in selected if rule_id not in pending_ids and rule_id not in current_native
    )
    assert "LX0609-04-01-03" in plan.not_executed_rule_ids


@pytest.mark.unit
def test_unknown_native_async_executor_is_not_implicitly_enabled():
    """新增 executor 必须显式获得自己的门控，不能复用 MDT 兜底。"""

    inventory = tuple(
        replace(item, executor_key="future_async_executor")
        if item.rule_id == "LX0609-03-02-01"
        else item
        for item in build_luxian_0609_dependency_inventory(
            rules=load_luxian_0609_rules(),
            family_definitions=RULE_FAMILY_DEFINITIONS,
        )
    )

    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=("LX0609-03-02-01",),
        native_sync_enabled=True,
        native_mdt_enabled=True,
        native_extended_document_enabled=True,
    )

    assert plan.native_async_rule_ids == ()
    assert plan.compatibility_rule_ids == ("LX0609-03-02-01",)
    assert plan.native_executor_batches == ()


@pytest.mark.unit
def test_stage_one_consultation_flags_keep_paused_rules_out_of_all_dispatch():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=[item.rule_id for item in inventory],
        native_sync_enabled=True,
        native_mdt_enabled=True,
        native_extended_document_enabled=True,
        native_basic_timeliness_enabled=True,
        native_consultation_enabled=True,
        native_consultation_execution_link_enabled=False,
        native_exam_lab_enabled=True,
        native_transfusion_enabled=True,
        native_tumor_pathology_enabled=True,
        native_course_quality_enabled=True,
        native_surgery_gate_enabled=True,
        native_surgery_document_enabled=True,
        native_surgery_document_029_enabled=True,
    )

    _assert_full_catalog_plan_partition(plan)
    assert plan.compatibility_rule_ids == ()
    assert plan.compatibility_execution_rule_ids == ()
    assert "LX0609-03-01-04" in plan.not_executed_rule_ids


@pytest.mark.unit
def test_restored_029_requires_explicit_native_opt_in():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=[item.rule_id for item in inventory],
        native_sync_enabled=True,
        native_mdt_enabled=True,
        native_extended_document_enabled=True,
        native_basic_timeliness_enabled=True,
        native_consultation_enabled=True,
        native_consultation_execution_link_enabled=True,
        native_exam_lab_enabled=True,
        native_transfusion_enabled=True,
        native_tumor_pathology_enabled=True,
        native_course_quality_enabled=True,
        native_surgery_gate_enabled=True,
        native_surgery_document_enabled=True,
        native_surgery_document_029_enabled=False,
    )

    _assert_full_catalog_plan_partition(plan, compatibility_exception="LX0609-04-01-01")
    assert plan.compatibility_rule_ids == ("LX0609-04-01-01",)
    assert plan.compatibility_execution_rule_ids == ("CL-181", "SC-081")
    assert "LX0609-04-01-01" not in plan.not_executed_rule_ids
    with pytest.raises(ValueError, match="正式质控禁止兼容执行"):
        assert_luxian_0609_formal_package_plan_native_only(plan, context="test")


@pytest.mark.unit
def test_restored_029_explicit_opt_in_selects_native_without_legacy_fallback():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    common = {
        "inventory": inventory,
        "selected_rule_ids": ["LX0609-04-01-01"],
        "native_sync_enabled": True,
        "native_mdt_enabled": False,
        "native_surgery_document_enabled": True,
    }

    compatibility = build_luxian_0609_package_plan(**common)
    enabled = build_luxian_0609_package_plan(
        **common,
        native_surgery_document_029_enabled=True,
    )

    assert compatibility.compatibility_rule_ids == ("LX0609-04-01-01",)
    assert compatibility.compatibility_execution_rule_ids == ("CL-181", "SC-081")
    assert compatibility.not_executed_rule_ids == ()
    assert enabled.compatibility_rule_ids == ()
    assert enabled.compatibility_execution_rule_ids == ()
    assert enabled.native_async_rule_ids == ("LX0609-04-01-01",)
    assert enabled.native_executor_batches == (("surgery_document", ("LX0609-04-01-01",)),)
    assert enabled.not_executed_rule_ids == ()
    assert_luxian_0609_formal_package_plan_native_only(enabled, context="test")


@pytest.mark.unit
def test_package_plan_accepts_only_customer_ids_and_keeps_legacy_ids_internal():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=["LX0609-04-01-03", "LX0609-04-01-01", "LX0609-01-01-01"],
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_basic_timeliness_enabled=True,
        native_surgery_document_enabled=True,
        native_surgery_document_029_enabled=True,
    )

    assert plan.selected_rule_ids == ("LX0609-01-01-01", "LX0609-04-01-01", "LX0609-04-01-03")
    assert plan.native_sync_rule_ids == ("LX0609-01-01-01",)
    assert plan.native_async_rule_ids == ("LX0609-04-01-01",)
    assert plan.compatibility_rule_ids == ()
    assert plan.compatibility_execution_rule_ids == ()
    assert plan.not_executed_rule_ids == ("LX0609-04-01-03",)
    assert plan.bypassed_execution_rule_ids == ("SC-002", "CL-181", "SC-081", "SC-083", "CL-108")
    assert plan.native_executor_batches == (
        ("basic_timeliness", ("LX0609-01-01-01",)),
        ("surgery_document", ("LX0609-04-01-01",)),
    )

    with pytest.raises(ValueError, match="invalid LX0609 customer rule id"):
        build_luxian_0609_package_plan(
            inventory=inventory,
            selected_rule_ids=["SC-002"],
            native_sync_enabled=True,
            native_mdt_enabled=False,
        )


@pytest.mark.unit
def test_package_plan_keeps_pending_rules_visible_but_never_dispatches_them():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=["LX0609-05-03-01", "LX0609-12-01-02", "LX0609-07-04-02"],
        native_sync_enabled=True,
        native_mdt_enabled=True,
        native_course_quality_enabled=True,
        native_transfusion_enabled=True,
    )

    assert plan.selected_rule_ids == (
        "LX0609-12-01-02",
        "LX0609-07-04-02",
        "LX0609-05-03-01",
    )
    assert plan.executable_rule_ids == ("LX0609-12-01-02",)
    assert plan.not_executed_rule_ids == ("LX0609-07-04-02", "LX0609-05-03-01")
    assert plan.native_async_rule_ids == ("LX0609-12-01-02",)
    assert "LX0609-07-04-02" not in plan.compatibility_rule_ids
    assert "LX0609-05-03-01" not in plan.compatibility_rule_ids


@pytest.mark.unit
@pytest.mark.parametrize(
    ("native_consultation_enabled", "execution_link_enabled", "expected_native", "expected_compatibility"),
    (
        # 020–023 全部暂停，任意开关组合都不得派发。
        (False, False, (), ()),
        (False, True, (), ()),
        (True, False, (), ()),
        (True, True, (), ()),
    ),
)
def test_consultation_two_stage_package_dispatch(
    native_consultation_enabled,
    execution_link_enabled,
    expected_native,
    expected_compatibility,
):
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=[
            "LX0609-03-01-01",
            "LX0609-03-01-02",
            "LX0609-03-01-03",
            "LX0609-03-01-04",
        ],
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_consultation_enabled=native_consultation_enabled,
        native_consultation_execution_link_enabled=execution_link_enabled,
    )

    assert plan.native_async_rule_ids == expected_native
    assert plan.compatibility_rule_ids == expected_compatibility
    if expected_native:
        assert plan.native_executor_batches == (("consultation_quality", expected_native),)
    else:
        assert plan.native_executor_batches == ()
    assert plan.not_executed_rule_ids == (
        "LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04",
    )
    assert plan.compatibility_execution_rule_ids == ()
    assert {"CL-250", "CL-248"} <= set(plan.bypassed_execution_rule_ids)


@pytest.mark.unit
def test_transition_adapter_resolves_raw_ids_to_customer_ids_in_catalog_order():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    assert resolve_selected_customer_rule_ids(
        inventory=inventory,
        prepared_rule_ids={"SC-083", "CL-181", "SC-002"},
    ) == ("LX0609-01-01-01", "LX0609-04-01-01", "LX0609-04-01-03")


@pytest.mark.unit
def test_public_package_entry_expands_only_inside_the_package():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    assert resolve_package_entry_execution_rule_ids(
        inventory=inventory,
        selected_rule_ids=["LX0609-06-02-03"],
    ) == ("SC-037", "SC-099", "SC-114")

    with pytest.raises(ValueError, match="invalid LX0609 customer rule id"):
        resolve_package_entry_execution_rule_ids(
            inventory=inventory,
            selected_rule_ids=["SC-099"],
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "rule_id",
    (
        "LX0609-04-02-04",
        "LX0609-07-04-02",
        "LX0609-05-03-01",
    ),
)
def test_public_package_entry_never_expands_pending_rules_to_legacy_execution_ids(
    rule_id: str,
) -> None:
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    assert resolve_package_entry_execution_rule_ids(
        inventory=inventory,
        selected_rule_ids=(rule_id,),
    ) == ()
