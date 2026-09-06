from dataclasses import replace
import json

import pytest

from app.services.luxian_0609 import phase_scope as phase_scope_module
from app.services import luxian_0609_rule_master as rule_master_module
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609.phase_scope import (
    Luxian0609PhaseScopeEntry,
    build_luxian_0609_pending_definition_result,
    compile_luxian_0609_phase_scope,
    load_luxian_0609_phase_scope,
    partition_luxian_0609_rule_scope,
)
from app.services.sample_validation_rule_sets import (
    get_luxian_0609_customer_delivery_rule_ids,
    get_luxian_0609_customer_execution_scope,
)


def test_phase_scope_freezes_all_77_customer_rules() -> None:
    entries = load_luxian_0609_phase_scope()

    assert len(entries) == 77
    assert tuple(entry.rule_id for entry in entries) == tuple(
        f"LX0609-{index:03d}" for index in range(1, 78)
    )
    assert {entry.definition_version for entry in entries} == {
        "lx0609-defined-scope-2026-09-05-r3"
    }
    assert sum(entry.phase_status == "phase_1_target" for entry in entries) == 71
    assert sum(entry.phase_status == "phase_1_partial" for entry in entries) == 0
    assert sum(entry.phase_status == "pending_definition" for entry in entries) == 6
    assert sum(entry.catalog_registered for entry in entries) == 77


def test_phase_scope_uses_latest_confirmed_contract_and_freezes_only_unresolved_rules() -> None:
    entries = {entry.rule_id: entry for entry in load_luxian_0609_phase_scope()}

    for rule_id in ("LX0609-009", "LX0609-010", "LX0609-017", "LX0609-023"):
        assert entries[rule_id].phase_status == "phase_1_target"
        assert entries[rule_id].pending_reason_code == ""

    assert entries["LX0609-025"].phase_status == "pending_definition"
    assert (
        entries["LX0609-025"].pending_reason_code
        == "implant_five_field_real_gold_pending"
    )
    assert entries["LX0609-059"].phase_status == "pending_definition"
    assert (
        entries["LX0609-059"].pending_reason_code
        == "treatment_event_order_course_real_gold_pending"
    )
    assert entries["LX0609-018"].phase_status == "phase_1_target"
    assert entries["LX0609-018"].active_criteria == (
        "chief_complaint_length",
        "diagnostic_direction",
    )
    assert entries["LX0609-018"].pending_criteria == ()
    assert entries["LX0609-018"].pending_reason_code == ""
    assert {
        rule_id
        for rule_id, entry in entries.items()
        if entry.phase_status == "pending_definition"
    } == {
        "LX0609-025",
        "LX0609-028",
        "LX0609-049",
        "LX0609-056",
        "LX0609-059",
        "LX0609-075",
    }


@pytest.mark.parametrize(
    ("rule_id", "pending_reason_code"),
    (
        ("LX0609-049", "charging_source_unavailable_customer_scope"),
        ("LX0609-056", "key_antimicrobial_catalog_missing"),
        ("LX0609-059", "treatment_event_order_course_real_gold_pending"),
        ("LX0609-075", "invasive_procedure_catalog_missing"),
    ),
)
def test_pending_definition_result_has_one_empty_evidence_contract(
    rule_id: str,
    pending_reason_code: str,
) -> None:
    result = build_luxian_0609_pending_definition_result(rule_id)

    assert result["rule_id"] == rule_id
    assert result["status"] == "not_executed"
    assert result["is_compliant"] is None
    assert result["facts"] == {}
    assert result["evidence"] == []
    assert result["metadata"] == {
        "execution_source": "lx0609_phase_gate",
        "executor_type": "programmatic",
        "reason_code": "policy_definition_pending",
        "pending_reason_code": pending_reason_code,
    }


@pytest.mark.parametrize(
    "mismatch_kind",
    ("missing", "extra", "duplicate", "reordered"),
)
def test_phase_scope_rejects_any_id_set_or_order_drift_from_master(
    mismatch_kind: str,
) -> None:
    payload = json.loads(phase_scope_module._SCOPE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload["rules"], list)
    rules = payload["rules"]

    if mismatch_kind == "missing":
        rules.pop()
    elif mismatch_kind == "extra":
        rules.append({**rules[-1], "rule_id": "LX0609-078"})
    elif mismatch_kind == "duplicate":
        rules[-1] = {**rules[-1], "rule_id": "LX0609-074"}
    else:
        rules[-2], rules[-1] = rules[-1], rules[-2]

    with pytest.raises(ValueError, match="exactly match rule master"):
        compile_luxian_0609_phase_scope(payload)


def test_phase_scope_requires_target_rules_to_be_catalog_registered() -> None:
    payload = json.loads(phase_scope_module._SCOPE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload["rules"], list)
    payload["rules"][0] = {
        **payload["rules"][0],
        "catalog_registered": False,
    }

    with pytest.raises(ValueError, match="catalog registration drift"):
        compile_luxian_0609_phase_scope(payload)


def test_phase_scope_rejects_target_rule_not_active_in_master(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未注册的合同就绪规则不能只靠 phase target 进入执行范围。"""

    payload = json.loads(phase_scope_module._SCOPE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload["rules"], list)
    payload["rules"][0] = {
        **payload["rules"][0],
        "catalog_registered": False,
    }
    master_entries = list(rule_master_module.load_luxian_0609_rule_master())
    master_entries[0] = replace(
        master_entries[0],
        implementation_status="contract_ready",
        definition_note="合同已就绪，尚未进入执行目录。",
    )
    monkeypatch.setattr(
        phase_scope_module,
        "load_luxian_0609_rule_master",
        lambda: tuple(master_entries),
    )

    with pytest.raises(ValueError, match="phase target must be catalog registered"):
        compile_luxian_0609_phase_scope(payload)


def test_phase_scope_partitions_customer_selection_in_catalog_order() -> None:
    executable, pending = partition_luxian_0609_rule_scope(
        ("LX0609-059", "LX0609-017", "LX0609-049", "LX0609-001")
    )

    assert executable == ("LX0609-001", "LX0609-017")
    assert pending == ("LX0609-049", "LX0609-059")


def test_customer_delivery_scope_is_72_with_66_executable_and_6_withheld() -> None:
    delivery = get_luxian_0609_customer_delivery_rule_ids()
    executable, withheld = get_luxian_0609_customer_execution_scope()

    assert len(delivery) == 72
    assert len(executable) == 66
    assert len(withheld) == 6
    assert set(executable).isdisjoint(withheld)
    assert set(executable) | set(withheld) == set(delivery)
    catalog_ids = {
        str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        for item in load_luxian_0609_rules()
    }
    assert set(delivery) == catalog_ids - {
        "LX0609-033",
        "LX0609-034",
        "LX0609-035",
        "LX0609-041",
        "LX0609-042",
    }
    assert delivery == tuple(
        entry.rule_id
        for entry in load_luxian_0609_phase_scope()
        if entry.rule_id not in {
            "LX0609-033",
            "LX0609-034",
            "LX0609-035",
            "LX0609-041",
            "LX0609-042",
        }
    )


def test_phase_scope_fails_closed_for_partial_rule_until_criterion_projection_exists(
    monkeypatch,
) -> None:
    entries = (
        Luxian0609PhaseScopeEntry(
            rule_id="LX0609-001",
            phase_status="phase_1_target",
            catalog_registered=True,
            definition_version="v-test",
        ),
        Luxian0609PhaseScopeEntry(
            rule_id="LX0609-002",
            phase_status="phase_1_partial",
            catalog_registered=True,
            definition_version="v-test",
            active_criteria=("criterion_ready",),
            pending_criteria=("criterion_pending",),
        ),
        Luxian0609PhaseScopeEntry(
            rule_id="LX0609-003",
            phase_status="pending_definition",
            catalog_registered=True,
            definition_version="v-test",
            pending_reason_code="pending_contract",
        ),
    )
    monkeypatch.setattr(
        phase_scope_module,
        "load_luxian_0609_phase_scope",
        lambda: entries,
    )

    executable, withheld = partition_luxian_0609_rule_scope(
        ("LX0609-003", "LX0609-002", "LX0609-001")
    )

    assert executable == ("LX0609-001",)
    assert withheld == ("LX0609-002", "LX0609-003")
