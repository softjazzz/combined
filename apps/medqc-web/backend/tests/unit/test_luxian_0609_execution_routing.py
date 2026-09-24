from __future__ import annotations

from tests.luxian_0609_identity_test_support import published_rule_ids
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master

import asyncio
from types import SimpleNamespace

import pytest

from app.services.luxian_0609 import execution as execution_module
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
    return published_rule_ids(start, end)


def test_rollout_groups_cover_legacy_rules_once() -> None:
    flattened = [
        rule_id
        for _, rule_ids in RULE_DECISION_ROLLOUT_GROUPS
        for rule_id in rule_ids
    ]

    assert len(flattened) == len(set(flattened))
    assert set(_rule_ids(1, 49)).issubset(flattened)
    assert set(flattened).issubset(
        entry.rule_id for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "active"
    )


def test_full_mainline_selects_only_currently_executable_typed_decisions() -> None:
    selected = _rule_ids(1, 77)

    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=selected,
        settings=_settings(),
        unified_engine_enabled=True,
        always_typed_rule_ids=_rule_ids(50, 77),
        native_async_rule_ids=selected,
    )

    assert resolved == tuple(
        rule_id
        for rule_id in selected
        if rule_id
        not in {
            "LX0609-03-01-01",
            "LX0609-03-01-02",
            "LX0609-03-01-03",
            "LX0609-04-02-04",
            "LX0609-05-01-01",
            "LX0609-04-04-01",
            "LX0609-07-04-02",
            "LX0609-05-01-04",
            "LX0609-05-03-01",
            "LX0609-10-03-01",
        }
    )


def test_all_catalog_rules_have_one_contract_executor_and_registered_material_sources() -> None:
    expected_rule_ids = tuple(
        entry.rule_id for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "active"
    )
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
        selected_rule_ids=_rule_ids(1, 77),
        settings=_settings(),
        unified_engine_enabled=False,
        always_typed_rule_ids=_rule_ids(50, 77),
        native_async_rule_ids=_rule_ids(1, 77),
    )

    assert resolved == tuple(
        rule_id
        for rule_id in _rule_ids(50, 77)
        if rule_id not in {"LX0609-05-01-04", "LX0609-05-03-01", "LX0609-10-03-01"}
    )


def test_consultation_typed_decisions_require_native_dispatch() -> None:
    selected = ("LX0609-03-01-01", "LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04")

    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=selected,
        settings=_settings(),
        unified_engine_enabled=True,
        always_typed_rule_ids=(),
        native_async_rule_ids=("LX0609-03-01-02", "LX0609-03-01-03", "LX0609-03-01-04"),
    )

    # 020/021/022 暂停后不再进入 Typed Decision 范围，023 仍要求 native 派发。
    assert resolved == ("LX0609-03-01-04",)


def test_new_native_rule_without_legacy_rollout_group_uses_its_typed_contract() -> None:
    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=("LX0609-01-02-02",),
        settings=_settings(),
        unified_engine_enabled=True,
        always_typed_rule_ids=(),
        native_async_rule_ids=("LX0609-01-02-02",),
    )

    assert resolved == ("LX0609-01-02-02",)


def test_disabled_rollout_flag_only_removes_its_group() -> None:
    resolved = resolve_typed_decision_rule_ids(
        selected_rule_ids=("LX0609-02-01-03", "LX0609-02-01-04", "LX0609-01-01-02"),
        settings=_settings(LUXIAN_0609_RULE_DECISION_007_ENABLED=False),
        unified_engine_enabled=True,
        always_typed_rule_ids=(),
        native_async_rule_ids=("LX0609-02-01-03", "LX0609-02-01-04", "LX0609-01-01-02"),
    )

    assert resolved == ("LX0609-02-01-04", "LX0609-01-01-02")


@pytest.mark.parametrize(
    ("rule_id", "pending_reason_code"),
    (
        ("LX0609-07-04-02", "charging_source_unavailable_customer_scope"),
        ("LX0609-05-01-04", "key_antimicrobial_catalog_missing"),
        ("LX0609-05-03-01", "treatment_event_order_course_real_gold_pending"),
        ("LX0609-10-03-01", "invasive_procedure_catalog_missing"),
    ),
)
def test_public_execution_returns_controlled_not_executed_for_pending_rule(
    rule_id: str, pending_reason_code: str
) -> None:
    inventory = load_luxian_0609_dependency_inventory()
    prepared_rules = [
        {"rule_id": rule_id}
        for rule_id in resolve_package_entry_execution_rule_ids(
            inventory=inventory,
            selected_rule_ids=(rule_id,),
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
            selected_customer_rule_ids=(rule_id,),
        )
    )

    assert executable_rules == []
    assert context.package_plan is not None
    assert context.package_plan.not_executed_rule_ids == (rule_id,)
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
    assert result["rule_id"] == rule_id
    assert result["status"] == "not_executed"
    assert result["is_compliant"] is None
    assert result["evidence"] == []
    assert result["metadata"]["reason_code"] == "policy_definition_pending"
    assert result["metadata"]["pending_reason_code"] == pending_reason_code
    assert result["findings"] == "本质控点当前不参与正式结论，未生成合规或问题判定。"
    assert result["suggestion"] == "待院方确认并发布业务口径后再启用本质控点。"


def test_formal_execution_wraps_llm_client_at_single_egress_boundary(monkeypatch) -> None:
    original_client = object()
    wrapped_client = object()
    seen: list[object] = []

    def _wrap(client):
        seen.append(client)
        return wrapped_client

    monkeypatch.setattr(execution_module, "wrap_luxian_0609_llm_client", _wrap)
    inventory = load_luxian_0609_dependency_inventory()
    prepared_rules = [
        {"rule_id": rule_id}
        for rule_id in resolve_package_entry_execution_rule_ids(
            inventory=inventory,
            selected_rule_ids=("LX0609-04-02-04",),
        )
    ]

    asyncio.run(
        prepare_luxian_0609_execution(
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
            prepared_rules=prepared_rules,
            visit_id="V-1",
            medical_text="",
            evidence_payload=None,
            llm_client=original_client,
            settings=_settings(
                LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
                LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
                LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
                LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
            ),
            selected_customer_rule_ids=("LX0609-04-02-04",),
        )
    )

    assert seen == [original_client]
