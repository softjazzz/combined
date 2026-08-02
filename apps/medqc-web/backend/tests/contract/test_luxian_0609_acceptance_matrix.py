from __future__ import annotations

import json
from collections import Counter

import pytest

from scripts import run_luxian_0609_contract_acceptance as acceptance


def _matrix() -> dict:
    return json.loads(acceptance.MATRIX_PATH.read_text(encoding="utf-8"))


def test_matrix_is_generated_from_current_runtime_contract() -> None:
    committed = _matrix()
    generated = acceptance.build_acceptance_matrix()

    assert committed == generated
    assert [rule["rule_id"] for rule in committed["rules"]] == [
        f"LX0609-{index:03d}" for index in range(1, 76)
    ]


def test_matrix_keeps_formal_and_temporary_tiers_separate() -> None:
    payload = _matrix()
    summary = acceptance.validate_acceptance_matrix(payload)

    assert summary["rule_count"] == 75
    assert summary["definition_tiers"] == {"formal": 67, "temporary": 8}
    assert summary["bound_fixture_count"] == 75
    assert summary["case_slots"]["covered"] == 75
    assert summary["case_slots"]["missing"] > 0


def test_covered_means_controlled_fixture_binding_not_inferred_case_count() -> None:
    payload = _matrix()
    covered_slots = []
    for rule in payload["rules"]:
        for slot_name, slot in rule["cases"].items():
            if slot["coverage"] == "covered":
                covered_slots.append((rule["rule_id"], slot_name, slot["fixture_refs"]))

    assert len(covered_slots) == 75
    assert all(refs and refs[0].startswith("0426-v3:case-") for _, _, refs in covered_slots)
    assert Counter(slot_name for _, slot_name, _ in covered_slots) == {
        "compliant": 69,
        "confirmed_issue": 6,
    }


def test_matrix_contains_no_patient_identity_and_every_rule_has_contract() -> None:
    payload = _matrix()
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "patient_name" not in serialized
    assert "patient_id" not in serialized
    assert "visit_id" not in serialized
    for rule in payload["rules"]:
        assert rule["required_facts"]
        assert rule["required_evidence"]
        assert set(rule["cases"]) == set(acceptance.SLOT_KEYS)
        assert rule["expected_executor"]


def test_time_and_semantic_contracts_are_explicit_and_honest() -> None:
    payload = _matrix()
    time_rules = [rule for rule in payload["rules"] if "time_boundaries" in rule]
    semantic_rules = [rule for rule in payload["rules"] if "semantic_contract" in rule]

    assert time_rules
    assert all(
        set(rule["time_boundaries"])
        == {"before_threshold", "at_threshold", "after_threshold"}
        for rule in time_rules
    )
    assert all(
        boundary["coverage"] != "covered"
        for rule in time_rules
        for boundary in rule["time_boundaries"].values()
    )
    assert len(semantic_rules) == 21
    assert all(
        rule["semantic_contract"]["max_llm_calls_per_rule"]
        == rule["max_llm_calls_per_rule"]
        for rule in semantic_rules
    )


def test_validator_rejects_executor_drift() -> None:
    payload = _matrix()
    payload["rules"][0]["expected_executor"] = "wrong-executor"

    with pytest.raises(ValueError, match="LX0609-001 expected_executor mismatch"):
        acceptance.validate_acceptance_matrix(payload)


def test_report_states_fixture_coverage_is_not_execution_acceptance() -> None:
    payload = _matrix()
    summary = acceptance.validate_acceptance_matrix(payload)
    report = acceptance.render_report(payload, summary)

    assert "不以病例数量代替覆盖率" in report
    assert "不代表引擎执行已经通过" in report
    assert "正式 67 条" in report
    assert "临时 8 条" in report
