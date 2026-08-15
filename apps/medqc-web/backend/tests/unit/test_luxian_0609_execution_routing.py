from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.execution import (
    aggregate_luxian_0609_orchestrated_results,
    prepare_luxian_0609_execution,
)
from app.services.luxian_0609.executor_registry import (
    LEGACY_NATIVE_EXECUTION_ORDER,
    resolve_legacy_executor_material_source_keys,
)
from app.services.luxian_0609.native_package import (
    EXECUTION_MODE_NATIVE_ASYNC,
    EXECUTION_MODE_NATIVE_SYNC,
    load_luxian_0609_dependency_inventory,
    resolve_package_entry_execution_rule_ids,
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


def test_full_mainline_selects_only_currently_executable_typed_decisions() -> None:
    selected = _rule_ids(1, 75)

    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=selected,
        settings=_settings(),
        unified_engine_enabled=True,
        always_typed_rule_ids=_rule_ids(50, 75),
        native_async_rule_ids=selected,
    )

    assert resolved == tuple(
        rule_id
        for rule_id in selected
        if rule_id
        not in {
            "LX0609-024",
            "LX0609-025",
            "LX0609-028",
            "LX0609-049",
            "LX0609-056",
            "LX0609-059",
            "LX0609-075",
        }
    )


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

    assert resolved == tuple(
        rule_id
        for rule_id in _rule_ids(50, 75)
        if rule_id not in {"LX0609-056", "LX0609-059", "LX0609-075"}
    )


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


def test_public_execution_returns_controlled_not_executed_for_pending_rule() -> None:
    inventory = load_luxian_0609_dependency_inventory()
    prepared_rules = [
        {"rule_id": rule_id}
        for rule_id in resolve_package_entry_execution_rule_ids(
            inventory=inventory,
            selected_rule_ids=("LX0609-049",),
        )
    ]
    settings = _settings(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
    )

    executable_rules, context = asyncio.run(
        prepare_luxian_0609_execution(
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
            prepared_rules=prepared_rules,
            visit_id="V-1",
            medical_text="",
            evidence_payload=None,
            llm_client=object(),
            settings=settings,
            selected_customer_rule_ids=("LX0609-049",),
        )
    )

    assert executable_rules == []
    assert context.package_plan is not None
    assert context.package_plan.not_executed_rule_ids == ("LX0609-049",)
    assert context.native_llm_call_count == 0

    aggregated = aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="V-1",
        model_name="unused",
        evidence_payload=None,
    )

    assert len(aggregated["results"]) == 1
    result = aggregated["results"][0]
    assert result["rule_id"] == "LX0609-049"
    assert result["status"] == "not_executed"
    assert result["findings"] == "本质控点当前不参与正式结论，未生成合规或问题判定。"
    assert result["suggestion"] == "待院方确认并发布业务口径后再启用本质控点。"
