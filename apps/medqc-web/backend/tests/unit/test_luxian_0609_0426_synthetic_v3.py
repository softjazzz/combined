from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "build_luxian_0609_0426_synthetic_v3.py"
)
SPEC = importlib.util.spec_from_file_location(
    "build_luxian_0609_0426_synthetic_v3",
    SCRIPT_PATH,
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def _case(index: int, family: str):
    return module.V2.CandidateCase(
        target_index=index,
        family=family,
        selected_rule_ids=[],
        source_item={"matched_visit_id": f"SOURCE-{index}"},
        source_reason="unit",
        source_status="selected",
        target_visit_id=f"LX0609_0426_SYN_V3_{index:03d}",
        target_patient_id=f"P-LX0609_0426_SYN_V3_{index:03d}",
        target_mr_no=f"LX0609V3-{index:03d}",
        target_patient_name="李某某",
    )


def test_v3_family_projection_covers_the_unique_75_rule_master() -> None:
    all_rules = module.build_master_family_rule_ids()
    active_rules = module.build_master_family_rule_ids(statuses={"active"})

    flattened_all = [rule_id for rules in all_rules.values() for rule_id in rules]
    flattened_active = [rule_id for rules in active_rules.values() for rule_id in rules]
    assert len(flattened_all) == len(set(flattened_all)) == 75
    assert len(flattened_active) == len(set(flattened_active)) == 63
    assert "LX0609-052" in all_rules["检查检验"]
    assert "LX0609-052" not in active_rules["检查检验"]
    assert "LX0609-075" in all_rules["手术麻醉"]
    assert "LX0609-075" not in active_rules["手术麻醉"]


def test_v3_coverage_ledger_never_activates_ready_or_pending_rules() -> None:
    raw_cases = [
        _case(index, family)
        for index, family in enumerate(module.FAMILY_QUOTAS, start=1)
    ]
    cases = module._assign_full_active_family_scope(raw_cases)

    ledger = module.build_coverage_ledger(cases)
    counts = Counter(row["coverage_status"] for row in ledger)

    assert len(ledger) == 75
    assert counts == {
        "assigned_pending_golden_review": 63,
        "candidate_family_available_executor_inactive": 4,
        "blocked_definition": 8,
    }
    assert all(
        row["candidate_visit_ids"]
        for row in ledger
        if row["implementation_status"] == "active"
    )
    assert all(
        not row["candidate_visit_ids"]
        for row in ledger
        if row["implementation_status"] == "pending_definition"
    )


def test_v3_compatibility_configuration_keeps_v2_logic_but_uses_v3_identity() -> None:
    module._configure_v2_compatibility()

    assert module.V2.TARGET_POOL_ID == "luxian-0609-0426-syn-v3"
    assert module.V2.TARGET_VISIT_PREFIX == "LX0609_0426_SYN_V3_"
    assert module.V2.TARGET_MR_PREFIX == "LX0609V3-"
    assert sum(module.V2.FAMILY_QUOTAS.values()) == 38
    assert len(
        {
            rule_id
            for rule_ids in module.V2.FAMILY_RULE_IDS.values()
            for rule_id in rule_ids
        }
    ) == 63
