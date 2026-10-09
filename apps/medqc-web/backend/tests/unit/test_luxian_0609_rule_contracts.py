from __future__ import annotations

import json
from copy import deepcopy
from itertools import combinations
from pathlib import Path

import pytest

from app.services.luxian_0609.customer_rule_package import RULE_FAMILY_DEFINITIONS
from app.services.luxian_0609.rule_contracts import (
    RuleCriterionContract,
    compile_luxian_0609_rule_contracts,
    load_luxian_0609_rule_contracts,
)
from app.services.luxian_0609.surgery_text_fact_contract import (
    LX0609_025_REQUIRED_FIELDS,
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

    raw_master = json.loads(
        (Path(__file__).resolve().parents[2] / "app/data/luxian_0609_rule_master_v1.json").read_text(encoding="utf-8")
    )
    raw_active = tuple(raw for raw in raw_master["rules"] if raw["implementation_status"] == "active")
    expected_ids = tuple(raw["rule_id"] for raw in raw_active)
    assert expected_ids
    assert len(set(expected_ids)) == len(expected_ids)
    assert tuple(contract.rule_id for contract in contracts) == expected_ids
    assert tuple(str(item["rule_id"]) for item in load_luxian_0609_rules()) == expected_ids
    for contract, raw in zip(contracts, raw_active, strict=True):
        assert (
            contract.phase_status,
            contract.active_criteria,
            contract.pending_criteria,
            contract.pending_reason_code,
            contract.definition_version,
        ) == (
            raw.get("phase_status", "phase_1_target"),
            tuple(raw.get("active_criteria", ())),
            tuple(raw.get("pending_criteria", ())),
            raw.get("pending_reason_code", ""),
            raw_master["definition_version"],
        ), contract.rule_id
    phase_sets = []
    for status in ("phase_1_target", "phase_1_partial", "pending_definition"):
        expected = tuple(raw["rule_id"] for raw in raw_active if raw.get("phase_status", "phase_1_target") == status)
        actual = tuple(contract.rule_id for contract in contracts if contract.phase_status == status)
        assert actual == expected
        phase_sets.append(set(actual))
    assert all(left.isdisjoint(right) for left, right in combinations(phase_sets, 2))
    assert set().union(*phase_sets) == set(expected_ids)
    assert {"LX0609-06-03-01"}.isdisjoint(
        contract.rule_id for contract in contracts
    )
    assert {contract.definition_version for contract in contracts} == {
        "lx0609-defined-scope-2026-09-22-identity-v1"
    }
    assert json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))["definition_version"] == (
        "lx0609-defined-scope-2026-09-22-identity-v1"
    )
    assert all(
        "not_executed" in contract.allowed_final_states for contract in contracts
    )


@pytest.mark.unit
def test_rule_contracts_include_partial_and_pending_definition_boundaries() -> None:
    contracts = {item.rule_id: item for item in load_luxian_0609_rule_contracts()}

    critical_course = contracts["LX0609-02-01-05"]
    assert critical_course.phase_status == "phase_1_target"
    assert critical_course.pending_criteria == ()

    complaint_rule = contracts["LX0609-01-01-02"]
    assert complaint_rule.phase_status == "phase_1_target"
    assert complaint_rule.active_criteria == (
        "chief_complaint_length",
        "diagnostic_direction",
    )
    assert complaint_rule.pending_criteria == ()
    assert complaint_rule.pending_reason_code == ""
    assert complaint_rule.decision_authority == "program_then_optional_llm"
    assert complaint_rule.max_llm_calls_per_rule == 1

    copy_rule = contracts["LX0609-12-01-01"]
    assert copy_rule.decision_authority == "program_only"
    assert copy_rule.max_llm_calls_per_rule == 0

    basic_senior_round = contracts["LX0609-02-01-02"]
    assert basic_senior_round.family_key == "basic_timeliness"
    assert basic_senior_round.executor_key == "basic_timeliness"
    assert basic_senior_round.execution_mode == "native_sync"
    assert basic_senior_round.decision_authority == "program_then_optional_llm"
    assert basic_senior_round.max_llm_calls_per_rule == 1

    repeated_course = contracts["LX0609-12-01-02"]
    assert repeated_course.contract_version == "v7"
    assert repeated_course.decision_authority == "program_then_optional_llm"
    assert repeated_course.max_llm_calls_per_rule == 1

    exam_course = contracts["LX0609-06-01-02"]
    assert exam_course.phase_status == "phase_1_target"
    assert exam_course.pending_reason_code == ""

    implant = contracts["LX0609-04-02-04"]
    assert implant.phase_status == "pending_definition"
    assert implant.pending_reason_code == "implant_five_field_real_gold_pending"

    treatment_order = contracts["LX0609-05-03-01"]
    expected_treatment_sources = (
        "exam_master",
        "exam_item_report",
        "surgery_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "daily_course_record",
        "senior_course_record",
    )
    assert treatment_order.applicable_documents == expected_treatment_sources
    assert treatment_order.data_dependencies[:7] == expected_treatment_sources
    assert treatment_order.phase_status == "pending_definition"
    assert (
        treatment_order.pending_reason_code
        == "treatment_event_order_course_real_gold_pending"
    )


@pytest.mark.unit
def test_003_decision_support_loads_anesthesia_record_for_end_time() -> None:
    assert "anesthesia_record" in resolve_luxian_0609_decision_support_source_keys(
        ("LX0609-04-02-01",)
    )


@pytest.mark.unit
def test_009_decision_support_loads_daily_coverage_and_minimal_change_sources() -> None:
    assert set(resolve_luxian_0609_decision_support_source_keys(("LX0609-02-01-05",))) == {
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.severity_order",
        "daily_course_record",
        "senior_course_record",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
    }


@pytest.mark.unit
def test_025_decision_support_loads_surgery_and_course_record_sources() -> None:
    assert set(resolve_luxian_0609_decision_support_source_keys(("LX0609-04-02-04",))) == {
        "surgery_record",
        "mr_surgery",
        "daily_course_record",
    }


@pytest.mark.unit
def test_025_and_059_compile_the_latest_machine_verifiable_pending_contracts() -> None:
    contracts = {item.rule_id: item for item in load_luxian_0609_rule_contracts()}

    implant = contracts["LX0609-04-02-04"]
    assert implant.phase_status == "pending_definition"
    assert implant.decision_authority == "program_then_optional_llm"
    assert implant.max_llm_calls_per_rule == 1
    assert implant.golden_gate_state == "pending"
    assert tuple(item.criterion_id for item in implant.criteria) == LX0609_025_REQUIRED_FIELDS
    assert tuple(item.source_fact for item in implant.criteria) == tuple(
        f"surgery_record.{field}" for field in LX0609_025_REQUIRED_FIELDS
    )
    assert all(item.kind == "completeness" for item in implant.criteria)
    assert "implant_barcode" not in {
        item.criterion_id for item in implant.criteria
    }
    assert implant.applicable_documents == ("surgery_record",)
    assert "病程记录仅辅助确认实际使用，不得替代正式手术记录五字段" in (
        implant.data_dependencies
    )

    treatment_order = contracts["LX0609-05-03-01"]
    expected_treatment_sources = (
        "exam_master",
        "exam_item_report",
        "surgery_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "daily_course_record",
        "senior_course_record",
    )
    assert treatment_order.applicable_documents == expected_treatment_sources
    assert treatment_order.data_dependencies[:7] == expected_treatment_sources
    assert treatment_order.phase_status == "pending_definition"
    assert treatment_order.decision_authority == "program_then_optional_llm"
    assert treatment_order.max_llm_calls_per_rule == 1
    assert treatment_order.golden_gate_state == "pending"
    assert tuple(item.criterion_id for item in treatment_order.criteria) == (
        "event_order_business_key",
        "event_course_semantic_relation",
    )
    assert treatment_order.executor_key == "extended_document"
    assert all(
        key in treatment_order.data_dependencies
        for key in ("order_id", "application_id", "event_code")
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
    typed_malignancy = {
        contract.rule_id
        for contract in contracts
        if contract.source_contract_state == "typed_malignancy_gate_v1"
    }

    assert program_only == {
        "LX0609-01-01-01",
        "LX0609-01-02-01",
        "LX0609-04-02-01",
        "LX0609-09-01-01",
        "LX0609-02-01-01",
        "LX0609-02-01-03",
        "LX0609-02-01-04",
        "LX0609-12-01-01",
        "LX0609-04-02-05",
        "LX0609-11-02-01",
        "LX0609-11-02-02",
        "LX0609-04-04-01",
        "LX0609-04-04-03",
        "LX0609-04-01-02",
        "LX0609-11-03-01",
        "LX0609-11-03-02",
        "LX0609-07-01-01",
        "LX0609-07-03-01",
        "LX0609-07-04-01",
        "LX0609-07-04-02",
        "LX0609-03-02-01",
        "LX0609-06-04-01",
        "LX0609-06-04-02",
        "LX0609-05-01-02",
        "LX0609-05-01-04",
        "LX0609-05-01-05",
        "LX0609-05-01-06",
        "LX0609-08-01-03",
        "LX0609-10-03-01",
        "LX0609-04-02-08",
        "LX0609-04-01-01",
        "LX0609-04-02-02",
        "LX0609-04-03-01",
        "LX0609-09-02-01",
        "LX0609-04-02-06",
        "LX0609-08-01-01",
        "LX0609-08-01-02",
        "LX0609-04-05-01",
        "LX0609-04-05-03",
        "LX0609-08-02-02",
        "LX0609-04-02-07",
        "LX0609-10-01-01",
        "LX0609-10-02-01",
        "LX0609-10-02-02",
        "LX0609-06-01-03",
        "LX0609-06-03-02",
        "LX0609-06-02-01",
    }
    effect_contract = next(contract for contract in contracts if contract.rule_id == "LX0609-05-01-03")
    assert (effect_contract.contract_version, effect_contract.decision_authority,
            effect_contract.max_llm_calls_per_rule, effect_contract.prompt_version) == (
                "v2", "program_then_optional_llm", 1, "lx0609-antimicrobial-effect-facts-v1")
    visit_contract = next(contract for contract in contracts if contract.rule_id == "LX0609-04-04-02")
    assert (visit_contract.contract_version, visit_contract.decision_authority, visit_contract.max_llm_calls_per_rule, visit_contract.prompt_version) == ("v3", "program_then_optional_llm", 1, "lx0609-anesthesia-visit-facts-v1")
    for rule in ("LX0609-04-05-02", "LX0609-08-02-01"):
        course_contract = next(contract for contract in contracts if contract.rule_id == rule)
        assert (course_contract.contract_version, course_contract.decision_authority, course_contract.max_llm_calls_per_rule, course_contract.prompt_version) == ("v2", "program_then_optional_llm", 1, "lx0609-course-body-facts-v1")
    assert typed_shadow == {
        "LX0609-06-01-01",
        "LX0609-01-01-01",
        "LX0609-01-02-01",
        "LX0609-04-02-01",
        "LX0609-09-01-01",
        "LX0609-02-01-01",
        "LX0609-02-01-02",
        "LX0609-02-01-03",
        "LX0609-02-01-04",
        "LX0609-02-01-05",
        "LX0609-06-01-02",
        "LX0609-06-01-04",
        "LX0609-06-01-05",
        "LX0609-06-02-03",
        "LX0609-06-03-03",
        "LX0609-06-03-04",
        "LX0609-12-01-01",
        "LX0609-12-01-02",
        "LX0609-01-01-02",
        "LX0609-06-02-02",
        "LX0609-03-01-01",
        "LX0609-03-01-02",
        "LX0609-03-01-03",
        "LX0609-03-01-04",
        "LX0609-04-02-04",
        "LX0609-05-01-01",
        "LX0609-04-01-01",
        "LX0609-04-02-02",
        "LX0609-04-03-01",
        "LX0609-04-02-05",
        "LX0609-11-01-01",
        "LX0609-11-02-01",
        "LX0609-11-02-02",
        "LX0609-04-04-01",
        "LX0609-04-04-02",
        "LX0609-04-04-03",
        "LX0609-04-01-02",
        "LX0609-04-01-03",
        "LX0609-11-03-01",
        "LX0609-11-03-02",
        "LX0609-07-01-01",
        "LX0609-07-01-02",
        "LX0609-07-02-01",
        "LX0609-07-02-02",
        "LX0609-07-03-01",
        "LX0609-07-04-01",
        "LX0609-07-04-02",
        "LX0609-03-02-01",
        "LX0609-06-04-01",
        "LX0609-06-04-02",
        "LX0609-05-01-02",
        "LX0609-05-01-03",
        "LX0609-05-01-04",
        "LX0609-05-01-05",
        "LX0609-05-01-06",
        "LX0609-05-03-01",
        "LX0609-08-01-03",
        "LX0609-07-01-03",
        "LX0609-10-03-01",
        "LX0609-09-02-01",
        "LX0609-04-02-06",
        "LX0609-08-01-01",
        "LX0609-08-01-02",
        "LX0609-04-05-01",
        "LX0609-04-05-02",
        "LX0609-04-05-03",
        "LX0609-08-02-01",
        "LX0609-08-02-02",
        "LX0609-04-02-07",
        "LX0609-10-01-01",
        "LX0609-10-02-01",
        "LX0609-10-02-02",
        "LX0609-12-02-01",
        "LX0609-04-02-08",
        "LX0609-01-02-02",
        "LX0609-04-01-04",
        "LX0609-04-01-05",
        "LX0609-06-01-03",
        "LX0609-06-03-02",
        "LX0609-06-02-01",
        "LX0609-09-01-02",
        "LX0609-08-01-05",
    }
    assert typed_malignancy == {"LX0609-04-02-03", "LX0609-05-02-01", "LX0609-08-01-04"}
    assert all(contract.golden_gate_state == "pending" for contract in contracts)
    assert all(contract.data_dependencies for contract in contracts)
    assert all(
        contract.max_llm_calls_per_rule == 0
        if contract.decision_authority == "program_only"
        else contract.max_llm_calls_per_rule
        == (2 if contract.rule_id in {"LX0609-03-01-04", "LX0609-04-02-03"} else 1)
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
        match=r"LX0609 rule contract drift: LX0609-01-01-01\.executor_key",
    ):
        compile_luxian_0609_rule_contracts(
            payload=drifted,
            rules=load_luxian_0609_rules(),
            family_definitions=RULE_FAMILY_DEFINITIONS,
        )


@pytest.mark.unit
def test_rule_contract_compiler_rejects_authority_version_drift() -> None:
    payload = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    payload["definition_version"] = "lx0609-defined-scope-stale"

    with pytest.raises(ValueError, match="definition version drift"):
        compile_luxian_0609_rule_contracts(
            payload=payload,
            rules=load_luxian_0609_rules(),
            family_definitions=RULE_FAMILY_DEFINITIONS,
        )


@pytest.mark.unit
def test_018_compiles_two_independent_criteria_from_catalog() -> None:
    contract = next(
        item
        for item in load_luxian_0609_rule_contracts()
        if item.rule_id == "LX0609-01-01-02"
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


@pytest.mark.unit
def test_070_controlled_performance_extraction_contract_is_optional_single_call_v2() -> None:
    contract = next(item for item in load_luxian_0609_rule_contracts() if item.rule_id == "LX0609-07-01-03")
    assert contract.contract_version == "v2"
    assert contract.decision_authority == "program_then_optional_llm"
    assert contract.max_llm_calls_per_rule == 1
    assert contract.prompt_version == "lx0609-transfusion-performance-v1"
