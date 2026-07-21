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
        "LX0609-030",
        "LX0609-032",
    }
    assert {rule_id for rule_id, mode in modes.items() if mode == EXECUTION_MODE_NATIVE_ASYNC} == {
        "LX0609-010",
        "LX0609-011",
        "LX0609-012",
        "LX0609-013",
        "LX0609-014",
        "LX0609-015",
        "LX0609-019",
        "LX0609-026",
        "LX0609-027",
        "LX0609-020",
        "LX0609-021",
        "LX0609-022",
        "LX0609-023",
        "LX0609-040",
        "LX0609-041",
        "LX0609-042",
        "LX0609-043",
        "LX0609-044",
        "LX0609-045",
        "LX0609-046",
        "LX0609-047",
        "LX0609-048",
        "LX0609-049",
        "LX0609-003",
        "LX0609-007",
        "LX0609-008",
        "LX0609-009",
        "LX0609-016",
        "LX0609-017",
        "LX0609-018",
        "LX0609-024",
        "LX0609-025",
        "LX0609-028",
        "LX0609-029",
        "LX0609-031",
        "LX0609-033",
        "LX0609-034",
        "LX0609-035",
        "LX0609-036",
        "LX0609-037",
        "LX0609-038",
        "LX0609-039",
    }
    # 023 仍保留会诊执行器归属；是否派发由包计划的第一阶段白名单决定，
    # 不能通过把它降为 compatibility 来破坏规则契约。
    assert sum(mode == EXECUTION_MODE_COMPATIBILITY for mode in modes.values()) == 0


@pytest.mark.unit
def test_exam_lab_family_flag_partitions_only_five_customer_rules():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    selected = ["LX0609-010", "LX0609-011", "LX0609-012", "LX0609-014", "LX0609-015"]

    enabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_async_enabled=False,
        native_exam_lab_enabled=True,
    )
    disabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_async_enabled=False,
        native_exam_lab_enabled=False,
    )

    assert enabled.native_async_rule_ids == tuple(selected)
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == (("exam_lab", tuple(selected)),)
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == tuple(selected)


@pytest.mark.unit
def test_transfusion_family_flag_partitions_only_nine_customer_rules():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    selected = [f"LX0609-{number:03d}" for number in range(41, 50)]

    enabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_async_enabled=False,
        native_transfusion_enabled=True,
    )
    disabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_async_enabled=False,
        native_transfusion_enabled=False,
    )

    assert enabled.native_async_rule_ids == tuple(selected)
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == (("transfusion", tuple(selected)),)
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == tuple(selected)


@pytest.mark.unit
def test_tumor_pathology_family_flag_partitions_only_four_customer_rules():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    selected = ["LX0609-013", "LX0609-019", "LX0609-026", "LX0609-027"]

    enabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_async_enabled=False,
        native_tumor_pathology_enabled=True,
    )
    disabled = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=selected,
        native_sync_enabled=True,
        native_async_enabled=False,
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
            ["LX0609-007", "LX0609-008", "LX0609-009", "LX0609-016", "LX0609-017", "LX0609-018"],
            "native_course_quality_enabled",
            "course_quality",
        ),
        (
            ["LX0609-003", "LX0609-024", "LX0609-025", "LX0609-028", "LX0609-031", "LX0609-033"],
            "native_surgery_gate_enabled",
            "surgery_gate",
        ),
        (
            ["LX0609-034", "LX0609-035", "LX0609-036", "LX0609-037", "LX0609-038", "LX0609-039"],
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
        "native_async_enabled": False,
    }

    enabled = build_luxian_0609_package_plan(**common, **{flag_name: True})
    disabled = build_luxian_0609_package_plan(**common, **{flag_name: False})

    assert enabled.native_async_rule_ids == tuple(selected)
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == ((executor_key, tuple(selected)),)
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == tuple(selected)


@pytest.mark.unit
def test_all_native_family_flags_eliminate_runtime_compatibility_dispatch():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=[item.rule_id for item in inventory],
        native_sync_enabled=True,
        native_async_enabled=True,
        native_basic_timeliness_enabled=True,
        native_consultation_enabled=True,
        native_exam_lab_enabled=True,
        native_transfusion_enabled=True,
        native_tumor_pathology_enabled=True,
        native_course_quality_enabled=True,
        native_surgery_gate_enabled=True,
        native_surgery_document_enabled=True,
        native_surgery_document_029_enabled=True,
    )

    assert len(plan.native_sync_rule_ids) + len(plan.native_async_rule_ids) == 47
    assert plan.compatibility_rule_ids == ("LX0609-020", "LX0609-023")
    assert plan.compatibility_execution_rule_ids == (
        "LX-017",
        "CL-250",
        "CL-248",
        "CL-071",
    )


@pytest.mark.unit
def test_029_surgery_document_requires_its_explicit_unified_opt_in():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )
    common = {
        "inventory": inventory,
        "selected_rule_ids": ["LX0609-029"],
        "native_sync_enabled": True,
        "native_async_enabled": False,
        "native_surgery_document_enabled": True,
    }

    compatibility = build_luxian_0609_package_plan(**common)
    enabled = build_luxian_0609_package_plan(
        **common,
        native_surgery_document_029_enabled=True,
    )

    assert compatibility.compatibility_rule_ids == ("LX0609-029",)
    assert compatibility.compatibility_execution_rule_ids == ("CL-181", "SC-081")
    assert enabled.native_async_rule_ids == ("LX0609-029",)
    assert enabled.native_executor_batches == (
        ("surgery_document", ("LX0609-029",)),
    )


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
        native_surgery_document_enabled=True,
        native_surgery_document_029_enabled=True,
    )

    assert plan.selected_rule_ids == ("LX0609-001", "LX0609-029", "LX0609-040")
    assert plan.native_sync_rule_ids == ("LX0609-001",)
    assert plan.native_async_rule_ids == ("LX0609-029",)
    assert plan.compatibility_rule_ids == ("LX0609-040",)
    assert plan.compatibility_execution_rule_ids == ("SC-083", "CL-108")
    assert plan.bypassed_execution_rule_ids == ("SC-002", "CL-181", "SC-081")
    assert plan.native_executor_batches == (
        ("basic_timeliness", ("LX0609-001",)),
        ("surgery_document", ("LX0609-029",)),
    )

    with pytest.raises(ValueError, match="invalid LX0609 customer rule id"):
        build_luxian_0609_package_plan(
            inventory=inventory,
            selected_rule_ids=["SC-002"],
            native_sync_enabled=True,
            native_async_enabled=False,
        )


@pytest.mark.unit
def test_consultation_native_flag_keeps_020_023_compatibility_and_native_scopes_021_022():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=[
            "LX0609-020",
            "LX0609-021",
            "LX0609-022",
            "LX0609-023",
        ],
        native_sync_enabled=True,
        native_async_enabled=False,
        native_consultation_enabled=True,
    )

    assert plan.native_async_rule_ids == (
        "LX0609-021",
        "LX0609-022",
    )
    assert plan.compatibility_rule_ids == ("LX0609-020", "LX0609-023")
    assert plan.native_executor_batches == (
        (
            "consultation_quality",
            ("LX0609-021", "LX0609-022"),
        ),
    )
    assert plan.compatibility_execution_rule_ids == (
        "LX-017",
        "CL-250",
        "CL-248",
        "CL-071",
    )
    assert "CL-250" not in plan.bypassed_execution_rule_ids
    assert "CL-248" not in plan.bypassed_execution_rule_ids


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
