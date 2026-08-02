from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.services.luxian_0609.customer_rule_package import RULE_FAMILY_DEFINITIONS
from app.services.luxian_0609.rule_contracts import (
    RuleCriterionContract,
    compile_luxian_0609_rule_contracts,
    load_luxian_0609_rule_contracts,
)
from app.services.luxian_0609.source_registry import (
    resolve_luxian_0609_decision_support_source_keys,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules


_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "data"
    / "luxian_0609_rule_contracts_v1.json"
)


@pytest.mark.unit
def test_rule_contracts_cover_all_phase1_registered_rules_in_catalog_order() -> None:
    contracts = load_luxian_0609_rule_contracts()

    assert len(contracts) == 75
    assert tuple(contract.rule_id for contract in contracts) == tuple(
        str(item["rule_id"]) for item in load_luxian_0609_rules()
    )
    assert sum(contract.phase_status == "phase_1_target" for contract in contracts) == 65
    assert sum(contract.phase_status == "phase_1_partial" for contract in contracts) == 1
    assert sum(contract.phase_status == "pending_definition" for contract in contracts) == 9
    assert {contract.definition_version for contract in contracts} == {
        "lx0609-defined-scope-2026-08-02"
    }


@pytest.mark.unit
def test_rule_contracts_include_partial_and_pending_definition_boundaries() -> None:
    contracts = {item.rule_id: item for item in load_luxian_0609_rule_contracts()}

    critical_course = contracts["LX0609-009"]
    assert critical_course.phase_status == "phase_1_partial"
    assert critical_course.active_criteria == ("critical_daily_course_coverage",)
    assert critical_course.pending_criteria == (
        "condition_change_course_timeliness",
    )

    complaint_rule = contracts["LX0609-018"]
    assert complaint_rule.phase_status == "phase_1_target"
    assert complaint_rule.active_criteria == ()
    assert complaint_rule.pending_criteria == ()
    assert complaint_rule.decision_authority == "program_then_optional_llm"
    assert complaint_rule.max_llm_calls_per_rule == 1

    copy_rule = contracts["LX0609-016"]
    assert copy_rule.decision_authority == "program_only"
    assert copy_rule.max_llm_calls_per_rule == 0

    exam_course = contracts["LX0609-010"]
    assert exam_course.phase_status == "pending_definition"
    assert exam_course.pending_reason_code == "exam_course_linkage_window_undefined"


@pytest.mark.unit
def test_009_phase1_decision_support_only_loads_daily_coverage_sources() -> None:
    assert set(resolve_luxian_0609_decision_support_source_keys(("LX0609-009",))) == {
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.severity_order",
        "daily_course_record",
        "senior_course_record",
    }


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
        "LX0609-009",
        "LX0609-016",
        "LX0609-017",
        "LX0609-026",
        "LX0609-031",
        "LX0609-034",
        "LX0609-035",
        "LX0609-036",
        "LX0609-037",
        "LX0609-038",
        "LX0609-039",
        "LX0609-041",
        "LX0609-042",
        "LX0609-043",
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
        "LX0609-029",
        "LX0609-030",
        "LX0609-032",
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
        "LX0609-010",
        "LX0609-011",
        "LX0609-012",
        "LX0609-013",
        "LX0609-014",
        "LX0609-015",
        "LX0609-016",
        "LX0609-017",
        "LX0609-018",
        "LX0609-019",
        "LX0609-020",
        "LX0609-021",
        "LX0609-022",
        "LX0609-023",
        "LX0609-024",
        "LX0609-025",
        "LX0609-026",
        "LX0609-027",
        "LX0609-028",
        "LX0609-029",
        "LX0609-030",
        "LX0609-032",
        "LX0609-031",
        "LX0609-033",
        "LX0609-034",
        "LX0609-035",
        "LX0609-036",
        "LX0609-037",
        "LX0609-038",
        "LX0609-039",
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
    assert all(contract.golden_gate_state == "pending" for contract in contracts)
    assert all(contract.data_dependencies for contract in contracts)
    assert all(
        contract.max_llm_calls_per_rule == 0
        if contract.decision_authority == "program_only"
        else contract.max_llm_calls_per_rule
        == (2 if contract.rule_id == "LX0609-023" else 1)
        and bool(contract.prompt_version)
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


@pytest.mark.unit
def test_018_compiles_two_independent_criteria_from_catalog() -> None:
    contract = next(
        item
        for item in load_luxian_0609_rule_contracts()
        if item.rule_id == "LX0609-018"
    )

    assert [
        (item.criterion_id, item.label, item.kind)
        for item in contract.criteria
    ] == [
        ("chief_complaint_length", "主诉字数", "text_length"),
        ("diagnostic_direction", "第一诊断指向", "semantic_relation"),
    ]
    length = contract.criteria[0]
    assert length.source_fact == "admission_record.chief_complaint"
    assert length.operator == "lte"
    assert length.expected == 20
    assert length.unit == "character"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kind", "operator", "unit"),
    [
        ("presence", "present", "boolean"),
        ("timeliness", "lte", "hour"),
        ("coverage", "covers", "day"),
        ("completeness", "complete", "boolean"),
    ],
)
def test_rule_criterion_contract_accepts_controlled_explanation_kinds(
    kind: str,
    operator: str,
    unit: str,
) -> None:
    criterion = RuleCriterionContract(
        criterion_id="controlled_fact",
        label="受控判定事实",
        kind=kind,
        failure_reason_code="requirement_violated",
        source_fact="document.controlled_fact",
        operator=operator,
        expected=8 if kind == "timeliness" else True,
        unit=unit,
    )

    assert criterion.label == "受控判定事实"


@pytest.mark.unit
def test_rule_criterion_contract_rejects_missing_customer_label() -> None:
    with pytest.raises(ValueError, match="criterion label"):
        RuleCriterionContract(
            criterion_id="completion_interval",
            label="",
            kind="timeliness",
            failure_reason_code="requirement_violated",
            source_fact="document.completed_at",
            operator="lte",
            expected=8,
            unit="hour",
        )
