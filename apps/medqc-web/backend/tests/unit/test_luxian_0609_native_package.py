from __future__ import annotations

import pytest

from app.services.luxian_0609.customer_rule_package import RULE_FAMILY_DEFINITIONS
from app.services.luxian_0609.native_package import (
    EXECUTION_MODE_COMPATIBILITY,
    EXECUTION_MODE_NATIVE_ASYNC,
    EXECUTION_MODE_NATIVE_SYNC,
    build_luxian_0609_dependency_inventory,
    build_luxian_0609_package_plan,
    resolve_package_entry_execution_rule_ids,
    resolve_selected_customer_rule_ids,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules


@pytest.mark.unit
def test_dependency_inventory_covers_all_49_rules_and_seven_families():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    assert len(inventory) == 49
    assert tuple(item.rule_id for item in inventory) == tuple(
        f"LX0609-{number:03d}" for number in range(1, 50)
    )
    assert {item.family_key for item in inventory} == {
        "basic_timeliness",
        "course_quality",
        "exam_lab",
        "consultation_quality",
        "surgery_anesthesia",
        "transfusion",
        "tumor_pathology",
    }
    assert sum(len(item.compatibility_rule_ids) for item in inventory) == 90
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
        "LX0609-001",
        "LX0609-002",
        "LX0609-004",
        "LX0609-005",
        "LX0609-006",
        "LX0609-029",
        "LX0609-030",
        "LX0609-032",
    }
    assert {rule_id for rule_id, mode in modes.items() if mode == EXECUTION_MODE_NATIVE_ASYNC} == {
        "LX0609-020",
        "LX0609-021",
        "LX0609-022",
        "LX0609-023",
        "LX0609-040"
    }
    assert sum(mode == EXECUTION_MODE_COMPATIBILITY for mode in modes.values()) == 36


@pytest.mark.unit
def test_package_plan_accepts_only_customer_ids_and_keeps_legacy_ids_internal():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=["LX0609-040", "LX0609-029", "LX0609-001"],
        native_sync_enabled=True,
        native_async_enabled=False,
        native_basic_timeliness_enabled=True,
    )

    assert plan.selected_rule_ids == ("LX0609-001", "LX0609-029", "LX0609-040")
    assert plan.native_sync_rule_ids == ("LX0609-001", "LX0609-029")
    assert plan.native_async_rule_ids == ()
    assert plan.compatibility_rule_ids == ("LX0609-040",)
    assert plan.compatibility_execution_rule_ids == ("SC-083", "CL-108")
    assert plan.bypassed_execution_rule_ids == ("SC-002", "CL-181", "SC-081")
    assert plan.native_executor_batches == (
        ("basic_timeliness", ("LX0609-001",)),
        ("surgery_presence", ("LX0609-029",)),
    )

    with pytest.raises(ValueError, match="invalid LX0609 customer rule id"):
        build_luxian_0609_package_plan(
            inventory=inventory,
            selected_rule_ids=["SC-002"],
            native_sync_enabled=True,
            native_async_enabled=False,
        )


@pytest.mark.unit
def test_transition_adapter_resolves_raw_ids_to_customer_ids_in_catalog_order():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    assert resolve_selected_customer_rule_ids(
        inventory=inventory,
        prepared_rule_ids={"SC-083", "CL-181", "SC-002"},
    ) == ("LX0609-001", "LX0609-029", "LX0609-040")


@pytest.mark.unit
def test_public_package_entry_expands_only_inside_the_package():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    assert resolve_package_entry_execution_rule_ids(
        inventory=inventory,
        selected_rule_ids=["LX0609-013"],
    ) == ("SC-037", "SC-099", "SC-114")

    with pytest.raises(ValueError, match="invalid LX0609 customer rule id"):
        resolve_package_entry_execution_rule_ids(
            inventory=inventory,
            selected_rule_ids=["SC-099"],
        )
