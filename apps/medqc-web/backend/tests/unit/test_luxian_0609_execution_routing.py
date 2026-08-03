from __future__ import annotations

from types import SimpleNamespace

from app.services.luxian_0609.executor_registry import (
    LEGACY_NATIVE_EXECUTION_ORDER,
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.native_package import (
    EXECUTION_MODE_NATIVE_ASYNC,
    EXECUTION_MODE_NATIVE_SYNC,
    load_luxian_0609_dependency_inventory,
)
from app.services.luxian_0609.rule_contracts import (
    load_luxian_0609_rule_contracts,
)
from app.services.luxian_0609.rule_decision_settings import (
    RULE_DECISION_ROLLOUT_GROUPS,
    resolve_typed_decision_rule_ids,
)
from app.services.luxian_0609.source_registry import (
    is_registered_luxian_0609_source_key,
    resolve_luxian_0609_rule_sources,
)


def _settings(**overrides: bool) -> SimpleNamespace:
    values = {
        flag_name: True
        for flag_name, _ in RULE_DECISION_ROLLOUT_GROUPS
        if flag_name is not None
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _rule_ids(start: int, end: int) -> tuple[str, ...]:
    return tuple(f"LX0609-{index:03d}" for index in range(start, end + 1))


def test_rollout_groups_cover_legacy_rules_once() -> None:
    flattened = [
        rule_id
        for _, rule_ids in RULE_DECISION_ROLLOUT_GROUPS
        for rule_id in rule_ids
    ]

    assert len(flattened) == len(set(flattened)) == 49
    assert set(flattened) == set(_rule_ids(1, 49))


def test_full_mainline_selects_all_75_typed_decisions_in_catalog_order() -> None:
    selected = _rule_ids(1, 75)

    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=selected,
        settings=_settings(),
        unified_engine_enabled=True,
        always_typed_rule_ids=_rule_ids(50, 75),
        native_async_rule_ids=selected,
    )

    assert resolved == selected


def test_all_75_rules_have_one_contract_executor_and_registered_material_sources() -> None:
    expected_rule_ids = _rule_ids(1, 75)
    contracts = load_luxian_0609_rule_contracts()
    dependencies = load_luxian_0609_dependency_inventory()

    assert tuple(item.rule_id for item in contracts) == expected_rule_ids
    assert tuple(item.rule_id for item in dependencies) == expected_rule_ids
    assert {item.executor_key for item in contracts} == set(
        LEGACY_NATIVE_EXECUTION_ORDER
    )
    assert {
        item.execution_mode for item in dependencies
    } == {EXECUTION_MODE_NATIVE_SYNC, EXECUTION_MODE_NATIVE_ASYNC}

    dependencies_by_rule_id = {item.rule_id: item for item in dependencies}
    resolved_sources = resolve_luxian_0609_rule_sources(expected_rule_ids)
    for contract in contracts:
        dependency = dependencies_by_rule_id[contract.rule_id]
        assert dependency.executor_key == contract.executor_key

        declared_source_keys = tuple(
            source_key
            for entry in resolved_sources[contract.rule_id]
            for source_key in entry.source_keys
        )
        executor_source_keys = resolve_legacy_executor_material_source_keys(
            (contract.executor_key,),
            selected_rule_ids=(contract.rule_id,),
        )
        material_source_keys = tuple(
            dict.fromkeys((*declared_source_keys, *executor_source_keys))
        )
        assert material_source_keys, contract.rule_id
        assert all(
            is_registered_luxian_0609_source_key(source_key)
            for source_key in material_source_keys
        ), contract.rule_id


def test_unified_engine_off_keeps_only_always_typed_extended_rules() -> None:
    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=_rule_ids(1, 75),
        settings=_settings(),
        unified_engine_enabled=False,
        always_typed_rule_ids=_rule_ids(50, 75),
        native_async_rule_ids=_rule_ids(1, 75),
    )

    assert resolved == _rule_ids(50, 75)


def test_consultation_typed_decisions_require_native_dispatch() -> None:
    selected = ("LX0609-020", "LX0609-021", "LX0609-022", "LX0609-023")

    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=selected,
        settings=_settings(),
        unified_engine_enabled=True,
        always_typed_rule_ids=(),
        native_async_rule_ids=("LX0609-021", "LX0609-022", "LX0609-023"),
    )

    assert resolved == ("LX0609-021", "LX0609-022", "LX0609-023")


def test_disabled_rollout_flag_only_removes_its_group() -> None:
    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=("LX0609-007", "LX0609-008", "LX0609-018"),
        settings=_settings(LUXIAN_0609_RULE_DECISION_007_ENABLED=False),
        unified_engine_enabled=True,
        always_typed_rule_ids=(),
        native_async_rule_ids=("LX0609-007", "LX0609-008", "LX0609-018"),
    )

    assert resolved == ("LX0609-008", "LX0609-018")
