from __future__ import annotations

import pytest

from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_rule_master import (
    get_luxian_0609_rule_master_entry,
    get_luxian_0609_rule_master_summary,
    load_luxian_0609_rule_master,
)


@pytest.mark.unit
def test_rule_master_is_the_complete_ordered_75_rule_scope():
    entries = load_luxian_0609_rule_master()

    assert tuple(entry.rule_id for entry in entries) == tuple(
        f"LX0609-{index:03d}" for index in range(1, 76)
    )
    assert len({entry.rule_id for entry in entries}) == 75
    assert get_luxian_0609_rule_master_summary() == {
        "total": 75,
        "active": 63,
        "contract_ready": 4,
        "pending_definition": 8,
    }


@pytest.mark.unit
def test_execution_catalog_is_exactly_the_active_master_projection():
    master_active_ids = tuple(
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "active"
    )
    execution_ids = tuple(rule["rule_id"] for rule in load_luxian_0609_rules())

    assert execution_ids == master_active_ids
    assert "LX0609-052" not in execution_ids
    assert "LX0609-075" not in execution_ids


@pytest.mark.unit
def test_recently_defined_rules_are_ready_but_not_implicitly_activated():
    ready_ids = {
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "contract_ready"
    }

    assert ready_ids == {"LX0609-052", "LX0609-053", "LX0609-058", "LX0609-070"}
    assert "PL（极低）或PH（极高）" in (
        get_luxian_0609_rule_master_entry("lx0609-052").definition_note
    )
    assert "乙肝五项" in (
        get_luxian_0609_rule_master_entry("LX0609-070").definition_note
    )


@pytest.mark.unit
def test_pending_rules_keep_customer_definition_gaps_visible():
    pending_entries = tuple(
        entry
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "pending_definition"
    )

    assert {entry.rule_id for entry in pending_entries} == {
        "LX0609-050",
        "LX0609-054",
        "LX0609-055",
        "LX0609-056",
        "LX0609-057",
        "LX0609-059",
        "LX0609-063",
        "LX0609-075",
    }
    assert all(entry.definition_note for entry in pending_entries)
