from __future__ import annotations

from dataclasses import replace
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


@pytest.mark.unit
def test_dependency_inventory_covers_all_77_registered_rules_and_eight_families():
    inventory = build_luxian_0609_dependency_inventory(
        rules=load_luxian_0609_rules(),
        family_definitions=RULE_FAMILY_DEFINITIONS,
    )

    assert len(inventory) == 77
    assert tuple(item.rule_id for item in inventory) == tuple(
        str(item["rule_id"]) for item in load_luxian_0609_rules()
    )
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
    assert sum(len(item.compatibility_rule_ids) for item in inventory) == 118
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
        "LX0609-050",
        "LX0609-052",
        "LX0609-053",
        "LX0609-054",
        "LX0609-055",
        "LX0609-056",
        "LX0609-057",
        "LX0609-058",
        "LX0609-059",
        "LX0609-063",
        "LX0609-070",
        "LX0609-075",
        "LX0609-076",
        "LX0609-077",
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
        "LX0609-051",
        "LX0609-060",
        "LX0609-061",
        "LX0609-062",
        "LX0609-064",
        "LX0609-065",
        "LX0609-066",
        "LX0609-067",
        "LX0609-068",
        "LX0609-069",
        "LX0609-071",
        "LX0609-072",
        "LX0609-073",
        "LX0609-074",
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
        "selected_rule_ids": ["LX0609-010"],
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

    with pytest.raises(ValueError, match="正式质控禁止兼容执行.*LX0609-010.*LXE-23"):
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
        selected_rule_ids=["LX0609-025"],
        native_sync_enabled=True,
        native_mdt_enabled=False,
        native_surgery_gate_enabled=True,
    )
    assert pending.not_executed_rule_ids == ("LX0609-025",)
    assert "LX0609-025" in pending.prepared_rule_ids_to_remove
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
    selected = [f"LX0609-{number:03d}" for number in range(41, 50)]

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

    expected_executable = tuple(selected[:-1])
    assert enabled.native_async_rule_ids == expected_executable
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == (("transfusion", expected_executable),)
    assert enabled.not_executed_rule_ids == ("LX0609-049",)
    assert "LX0609-049" in enabled.prepared_rule_ids_to_remove
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == expected_executable
    assert disabled.not_executed_rule_ids == ("LX0609-049",)
    assert "LX0609-041" not in disabled.prepared_rule_ids_to_remove
    assert "LX0609-049" in disabled.prepared_rule_ids_to_remove


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
        "native_mdt_enabled": False,
    }

    enabled = build_luxian_0609_package_plan(**common, **{flag_name: True})
    disabled = build_luxian_0609_package_plan(**common, **{flag_name: False})

    expected_executable = enabled.executable_rule_ids
    expected_pending = tuple(
        rule_id for rule_id in selected if rule_id not in expected_executable
    )
    assert enabled.native_async_rule_ids == expected_executable
    assert enabled.compatibility_rule_ids == ()
    assert enabled.native_executor_batches == ((executor_key, expected_executable),)
    assert enabled.not_executed_rule_ids == expected_pending
    assert disabled.native_async_rule_ids == ()
    assert disabled.compatibility_rule_ids == expected_executable
    assert disabled.not_executed_rule_ids == expected_pending


@pytest.mark.unit
@pytest.mark.parametrize(
    ("native_mdt_enabled", "native_extended_document_enabled", "expected_native"),
    (
        (False, False, ()),
        (False, True, ("LX0609-050",)),
        (True, False, ("LX0609-040",)),
        (True, True, ("LX0609-040", "LX0609-050")),
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
        "LX0609-040",
        "LX0609-050",
        "LX0609-056",
        "LX0609-059",
        "LX0609-075",
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

    assert plan.native_async_rule_ids == expected_native
    assert plan.not_executed_rule_ids == (
        "LX0609-056",
        "LX0609-059",
        "LX0609-075",
    )
    assert plan.compatibility_rule_ids == tuple(
        rule_id
        for rule_id in ("LX0609-040", "LX0609-050")
        if rule_id not in expected_native
    )


@pytest.mark.unit
def test_unknown_native_async_executor_is_not_implicitly_enabled():
    """新增 executor 必须显式获得自己的门控，不能复用 MDT 兜底。"""

    inventory = tuple(
        replace(item, executor_key="future_async_executor")
        if item.rule_id == "LX0609-050"
        else item
        for item in build_luxian_0609_dependency_inventory(
            rules=load_luxian_0609_rules(),
            family_definitions=RULE_FAMILY_DEFINITIONS,
        )
    )

    plan = build_luxian_0609_package_plan(
        inventory=inventory,
        selected_rule_ids=("LX0609-050",),
        native_sync_enabled=True,
        native_mdt_enabled=True,
        native_extended_document_enabled=True,
    )

    assert plan.native_async_rule_ids == ()
    assert plan.compatibility_rule_ids == ("LX0609-050",)
    assert plan.native_executor_batches == ()


@pytest.mark.unit
def test_stage_one_consultation_flags_keep_execution_rules_on_compatibility_path():
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

    assert len(plan.native_sync_rule_ids) + len(plan.native_async_rule_ids) == 69
    assert len(plan.not_executed_rule_ids) == 6
    assert plan.compatibility_rule_ids == ("LX0609-020", "LX0609-023")
    assert plan.compatibility_execution_rule_ids == (
        "LX-017",
        "CL-250",
        "CL-248",
        "CL-071",
    )


@pytest.mark.unit
def test_all_enabled_native_families_leave_only_029_as_explicit_compatibility_exception():
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

    assert len(plan.native_sync_rule_ids) + len(plan.native_async_rule_ids) == 70
    assert len(plan.not_executed_rule_ids) == 6
    assert plan.compatibility_rule_ids == ("LX0609-029",)
    assert plan.compatibility_execution_rule_ids == ("CL-181", "SC-081")


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
        "native_mdt_enabled": False,
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
        native_mdt_enabled=False,
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
        selected_rule_ids=["LX0609-059", "LX0609-017", "LX0609-049"],
        native_sync_enabled=True,
        native_mdt_enabled=True,
        native_course_quality_enabled=True,
        native_transfusion_enabled=True,
    )

    assert plan.selected_rule_ids == (
        "LX0609-017",
        "LX0609-049",
        "LX0609-059",
    )
    assert plan.executable_rule_ids == ("LX0609-017",)
    assert plan.not_executed_rule_ids == ("LX0609-049", "LX0609-059")
    assert plan.native_async_rule_ids == ("LX0609-017",)
    assert "LX0609-049" not in plan.compatibility_rule_ids
    assert "LX0609-059" not in plan.compatibility_rule_ids


@pytest.mark.unit
@pytest.mark.parametrize(
    ("native_consultation_enabled", "execution_link_enabled", "expected_native", "expected_compatibility"),
    (
        (False, False, (), ("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023")),
        (False, True, (), ("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023")),
        (True, False, ("LX0609-021", "LX0609-022"), ("LX0609-020", "LX0609-023")),
        (True, True, ("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023"), ()),
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
            "LX0609-020",
            "LX0609-021",
            "LX0609-022",
            "LX0609-023",
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
    if not execution_link_enabled:
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


@pytest.mark.unit
@pytest.mark.parametrize(
    "rule_id",
    (
        "LX0609-025",
        "LX0609-028",
        "LX0609-049",
        "LX0609-056",
        "LX0609-059",
        "LX0609-075",
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
