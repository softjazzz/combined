from __future__ import annotations

from pathlib import Path

import pytest

from app.services.luxian_0609.antimicrobial_result_mapping import (
    ANTIMICROBIAL_CUSTOMER_RULE_IDS,
    antimicrobial_customer_fact_status_is_valid,
    safe_antimicrobial_customer_display_facts,
)
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalizer_owns_executor_customer_display_facts,
    finalizer_requires_public_fact_ref_evidence,
)


_FACTS_BY_CASE = {
    "054_compliant": (
        "LX0609-054",
        "compliant",
        {
            "verification_kind": "antimicrobial_reason_documentation_check",
            "antimicrobials": ["美罗培南"],
            "reason_documented": True,
            "unmatched_antimicrobials": [],
            "association_ambiguous": False,
        },
    ),
    "054_non_compliant": (
        "LX0609-054",
        "non_compliant",
        {
            "verification_kind": "antimicrobial_reason_documentation_check",
            "antimicrobials": ["美罗培南"],
            "reason_documented": False,
            "unmatched_antimicrobials": ["美罗培南"],
            "association_ambiguous": False,
        },
    ),
    "054_association_failed": (
        "LX0609-054",
        "data_gap",
        {
            "verification_kind": "antimicrobial_reason_documentation_check",
            "antimicrobials": ["美罗培南"],
            "reason_documented": False,
            "unmatched_antimicrobials": ["美罗培南"],
            "association_ambiguous": True,
        },
    ),
    "055_compliant": (
        "LX0609-055",
        "compliant",
        {
            "verification_kind": "antimicrobial_effect_evaluation_check",
            "antimicrobials": ["美罗培南"],
            "window_hours": [48, 72],
            "evaluation_intervals": [50.0],
            "unmatched_antimicrobials": [],
            "association_ambiguous": False,
        },
    ),
    "055_non_compliant": (
        "LX0609-055",
        "non_compliant",
        {
            "verification_kind": "antimicrobial_effect_evaluation_check",
            "antimicrobials": ["美罗培南"],
            "window_hours": [48, 72],
            "evaluation_intervals": [],
            "unmatched_antimicrobials": ["美罗培南"],
            "association_ambiguous": False,
        },
    ),
    "055_window_not_mature": (
        "LX0609-055",
        "not_applicable",
        {
            "verification_kind": "antimicrobial_effect_evaluation_check",
            "antimicrobials": ["美罗培南"],
            "window_hours": [48, 72],
            "evaluation_intervals": [],
            "unmatched_antimicrobials": [],
            "association_ambiguous": False,
        },
    ),
    "055_horizon_missing": (
        "LX0609-055",
        "data_gap",
        {
            "verification_kind": "antimicrobial_effect_evaluation_check",
            "antimicrobials": ["美罗培南"],
            "window_hours": [48, 72],
            "evaluation_intervals": [],
            "unmatched_antimicrobials": [],
            "association_ambiguous": False,
        },
    ),
    "057_compliant": (
        "LX0609-057",
        "compliant",
        {
            "verification_kind": "empiric_antimicrobial_reason_check",
            "antimicrobials": ["美罗培南"],
            "empiric_use_confirmed": True,
            "reason_or_no_specimen_documented": True,
        },
    ),
    "057_non_compliant": (
        "LX0609-057",
        "non_compliant",
        {
            "verification_kind": "empiric_antimicrobial_reason_check",
            "antimicrobials": ["美罗培南"],
            "empiric_use_confirmed": True,
            "reason_or_no_specimen_documented": False,
        },
    ),
    "058_compliant": (
        "LX0609-058",
        "compliant",
        {
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南"],
            "expert_support_present": True,
            "first_antimicrobial_time": "2026-06-01 10:00:00",
            "expert_support_time": "2026-06-01 09:00:00",
            "support_before_use": True,
            "unmatched_special_antimicrobials": [],
            "association_ambiguous": False,
        },
    ),
    "058_late_support": (
        "LX0609-058",
        "non_compliant",
        {
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南"],
            "expert_support_present": True,
            "first_antimicrobial_time": "2026-06-01 10:00:00",
            "expert_support_time": "2026-06-01 11:00:00",
            "support_before_use": False,
            "unmatched_special_antimicrobials": ["美罗培南"],
            "association_ambiguous": False,
        },
    ),
    "058_time_missing": (
        "LX0609-058",
        "data_gap",
        {
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南"],
            "expert_support_present": False,
            "first_antimicrobial_time": None,
            "expert_support_time": None,
            "support_before_use": False,
            "unmatched_special_antimicrobials": [],
            "association_ambiguous": False,
        },
    ),
    "058_association_failed": (
        "LX0609-058",
        "data_gap",
        {
            "verification_kind": "special_antimicrobial_expert_support_check",
            "special_antimicrobials": ["美罗培南"],
            "expert_support_present": True,
            "first_antimicrobial_time": "2026-06-01 10:00:00",
            "expert_support_time": "2026-06-01 09:00:00",
            "support_before_use": False,
            "unmatched_special_antimicrobials": [],
            "association_ambiguous": True,
        },
    ),
}


@pytest.mark.parametrize("_case", _FACTS_BY_CASE.values(), ids=_FACTS_BY_CASE)
def test_antimicrobial_mapping_freezes_reachable_safe_fact_shapes(
    _case: tuple[str, str, dict[str, object]],
) -> None:
    rule_id, status, raw_facts = _case

    safe_facts = safe_antimicrobial_customer_display_facts(
        rule_id=rule_id,
        raw=raw_facts,
    )

    assert safe_facts == raw_facts
    assert antimicrobial_customer_fact_status_is_valid(
        rule_id=rule_id,
        status=status,
        safe_facts=safe_facts,
    )


@pytest.mark.parametrize("rule_id", sorted(ANTIMICROBIAL_CUSTOMER_RULE_IDS))
def test_antimicrobial_rules_are_finalizer_facts_and_public_fact_ref_owners(
    rule_id: str,
) -> None:
    assert finalizer_owns_executor_customer_display_facts(rule_id)
    assert finalizer_requires_public_fact_ref_evidence(rule_id)


@pytest.mark.parametrize(
    ("status", "raw_facts"),
    [
        ("compliant", _FACTS_BY_CASE["058_late_support"][2]),
        (
            "non_compliant",
            {
                **_FACTS_BY_CASE["058_late_support"][2],
                "source_document_refs": ["forged-internal-ref"],
            },
        ),
        (
            "data_gap",
            {
                **_FACTS_BY_CASE["058_late_support"][2],
                "support_before_use": True,
                "unmatched_special_antimicrobials": [],
            },
        ),
    ],
    ids=["status_conflict", "private_fact_ref", "illegal_field_relationship"],
)
def test_antimicrobial_contract_failure_safely_downgrades_to_technical_error(
    status: str,
    raw_facts: object,
) -> None:
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-058",
            "status": status,
            "reason_code": "executor_reason",
            "findings": "执行器结论",
            "customer_evidence": [{"source_type": "must-be-cleared"}],
        },
        raw_facts=raw_facts,
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["result_status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert finalized["is_compliant"] is None
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized
    assert "findings" not in finalized


def test_aggregator_has_no_antimicrobial_rule_reference() -> None:
    aggregator_source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    ).read_text(encoding="utf-8")

    assert all(
        rule_id not in aggregator_source for rule_id in ANTIMICROBIAL_CUSTOMER_RULE_IDS
    )
