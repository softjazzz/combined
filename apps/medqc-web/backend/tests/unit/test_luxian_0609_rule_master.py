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
        "active": 75,
        "contract_ready": 0,
        "pending_definition": 0,
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
    assert "LX0609-052" in execution_ids
    assert "LX0609-075" in execution_ids


@pytest.mark.unit
def test_recently_defined_rules_are_activated_with_the_full_catalog():
    ready_ids = {
        entry.rule_id
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "contract_ready"
    }

    assert ready_ids == set()
    assert get_luxian_0609_rule_master_entry("lx0609-052").implementation_status == "active"
    assert get_luxian_0609_rule_master_entry("LX0609-070").implementation_status == "active"


@pytest.mark.unit
def test_pending_rules_keep_customer_definition_gaps_visible():
    pending_entries = tuple(
        entry
        for entry in load_luxian_0609_rule_master()
        if entry.implementation_status == "pending_definition"
    )

    assert pending_entries == ()
