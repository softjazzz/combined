from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.services.luxian_0609.customer_rule_package import RULE_FAMILY_DEFINITIONS
from app.services.luxian_0609.rule_contracts import (
    compile_luxian_0609_rule_contracts,
    load_luxian_0609_rule_contracts,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules


_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "data"
    / "luxian_0609_rule_contracts_v1.json"
)


@pytest.mark.unit
def test_rule_contracts_cover_all_49_customer_rules_in_catalog_order() -> None:
    contracts = load_luxian_0609_rule_contracts()

    assert len(contracts) == 49
    assert tuple(contract.rule_id for contract in contracts) == tuple(
        f"LX0609-{number:03d}" for number in range(1, 50)
    )


@pytest.mark.unit
def test_rule_contracts_make_current_authority_and_evidence_maturity_explicit() -> None:
    contracts = load_luxian_0609_rule_contracts()
    program_only = {
        contract.rule_id
        for contract in contracts
        if contract.decision_authority == "program_only"
    }
    typed_shadow = {
        contract.rule_id
        for contract in contracts
        if contract.source_contract_state == "typed_shadow_v1"
    }

    assert program_only == {
        "LX0609-001",
        "LX0609-002",
        "LX0609-003",
        "LX0609-004",
        "LX0609-005",
        "LX0609-006",
        "LX0609-007",
        "LX0609-008",
        "LX0609-047",
        "LX0609-029",
        "LX0609-030",
        "LX0609-032",
    }
    assert typed_shadow == {
        "LX0609-001",
        "LX0609-002",
        "LX0609-003",
        "LX0609-004",
        "LX0609-005",
        "LX0609-006",
        "LX0609-007",
        "LX0609-008",
        "LX0609-009",
        "LX0609-013",
        "LX0609-016",
        "LX0609-017",
        "LX0609-018",
        "LX0609-019",
        "LX0609-020",
        "LX0609-021",
        "LX0609-022",
        "LX0609-023",
        "LX0609-027",
        "LX0609-029",
        "LX0609-030",
        "LX0609-032",
        "LX0609-040",
        "LX0609-044",
        "LX0609-045",
        "LX0609-046",
        "LX0609-047",
    }
    assert all(contract.golden_gate_state == "pending" for contract in contracts)
    assert all(contract.data_dependencies for contract in contracts)
    assert all(
        contract.max_llm_calls_per_rule == 0
        if contract.decision_authority == "program_only"
        else contract.max_llm_calls_per_rule == 1 and bool(contract.prompt_version)
        for contract in contracts
    )


@pytest.mark.unit
def test_rule_contract_compiler_rejects_executor_registry_drift() -> None:
    payload = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    drifted = deepcopy(payload)
    drifted["rules"][0]["executor_key"] = "unexpected_executor"

    with pytest.raises(
        ValueError,
        match=r"LX0609 rule contract drift: LX0609-001\.executor_key",
    ):
        compile_luxian_0609_rule_contracts(
            payload=drifted,
            rules=load_luxian_0609_rules(),
            family_definitions=RULE_FAMILY_DEFINITIONS,
        )
