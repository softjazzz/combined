from app.services.luxian_0609 import phase_scope as phase_scope_module
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609.phase_scope import (
    Luxian0609PhaseScopeEntry,
    load_luxian_0609_phase_scope,
    partition_luxian_0609_rule_scope,
)
from app.services.sample_validation_rule_sets import (
    get_luxian_0609_customer_delivery_rule_ids,
    get_luxian_0609_customer_execution_scope,
)


def test_phase_scope_freezes_all_75_customer_rules() -> None:
    entries = load_luxian_0609_phase_scope()

    assert len(entries) == 75
    assert tuple(entry.rule_id for entry in entries) == tuple(
        f"LX0609-{index:03d}" for index in range(1, 76)
    )
    assert {entry.definition_version for entry in entries} == {
        "lx0609-defined-scope-2026-08-15-r2"
    }
    assert sum(entry.phase_status == "phase_1_target" for entry in entries) == 69
    assert sum(entry.phase_status == "phase_1_partial" for entry in entries) == 0
    assert sum(entry.phase_status == "pending_definition" for entry in entries) == 6
    assert sum(entry.catalog_registered for entry in entries) == 75


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


def test_phase_scope_partitions_customer_selection_in_catalog_order() -> None:
    executable, pending = partition_luxian_0609_rule_scope(
        ("LX0609-059", "LX0609-017", "LX0609-049", "LX0609-001")
    )

    assert executable == ("LX0609-001", "LX0609-017")
    assert pending == ("LX0609-049", "LX0609-059")


def test_customer_delivery_scope_is_70_with_64_executable_and_6_withheld() -> None:
    delivery = get_luxian_0609_customer_delivery_rule_ids()
    executable, withheld = get_luxian_0609_customer_execution_scope()

    assert len(delivery) == 70
    assert len(executable) == 64
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
