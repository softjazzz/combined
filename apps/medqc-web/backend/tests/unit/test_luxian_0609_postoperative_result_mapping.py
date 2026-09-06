from __future__ import annotations

from pathlib import Path

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalizer_owns_executor_customer_display_facts,
    finalizer_requires_public_fact_ref_evidence,
)
from app.services.luxian_0609.postoperative_result_mapping import (
    POSTOPERATIVE_CUSTOMER_RULE_IDS,
    postoperative_customer_fact_status_is_valid,
    safe_postoperative_customer_display_facts,
)


_FACTS_BY_CASE = {
    "064_timely": (
        "LX0609-064",
        "compliant",
        {
            "verification_kind": "postoperative_three_day_coverage_check",
            "surgery_time": "2026-07-01 10:00:00",
            "required_postop_dates": ["2026-07-02", "2026-07-03", "2026-07-04"],
            "covered_postop_dates": ["2026-07-02", "2026-07-03", "2026-07-04"],
            "surgeon_round_present": True,
        },
    ),
    "064_overdue": (
        "LX0609-064",
        "non_compliant",
        {
            "verification_kind": "postoperative_three_day_coverage_check",
            "surgery_time": "2026-07-01 10:00:00",
            "required_postop_dates": ["2026-07-02", "2026-07-03", "2026-07-04"],
            "covered_postop_dates": ["2026-07-02", "2026-07-03"],
            "surgeon_round_present": False,
            "performed_surgery_count": 1,
            "surgery_events": [{
                "document_id": "PRIVATE-SURGERY",
                "surgery_end_time": "2026-07-01 10:00:00",
                "surgeon_names": ["张医生"],
                "required_postop_dates": ["2026-07-02", "2026-07-03", "2026-07-04"],
                "covered_postop_dates": ["2026-07-02", "2026-07-03"],
                "surgeon_round_present": False,
            }],
        },
    ),
    "064_not_mature": (
        "LX0609-064",
        "not_applicable",
        {
            "verification_kind": "postoperative_three_day_window_not_mature",
            "surgery_times": ["2026-07-01 10:00:00"],
            "deadline_dates": ["2026-07-04"],
            "evaluation_date": "2026-07-03",
        },
    ),
    "064_horizon_missing": (
        "LX0609-064",
        "data_gap",
        {
            "verification_kind": "postoperative_three_day_window_unavailable",
            "issue": "authoritative_time_missing",
        },
    ),
    "065_timely": (
        "LX0609-065",
        "compliant",
        {
            "verification_kind": "postoperative_senior_round_check",
            "surgery_time": "2026-07-01 10:00:00",
            "threshold_hours": 72,
            "senior_round_times": ["2026-07-02 08:00:00"],
        },
    ),
    "065_overdue": (
        "LX0609-065",
        "non_compliant",
        {
            "verification_kind": "postoperative_senior_round_check",
            "surgery_time": "2026-07-01 10:00:00",
            "threshold_hours": 72,
            "senior_round_times": ["共1台手术中，1台手术结束后72小时内未查到上级医师查房"],
        },
    ),
    "065_result_detail_missing": (
        "LX0609-065",
        "data_gap",
        {
            "verification_kind": "postoperative_surgery_event_time_check",
            "performed_surgery_count": 1,
            "missing_surgery_end_events": ["PRIVATE-SURGERY"],
            "surgery_events": [{"document_id": "PRIVATE-SURGERY"}],
        },
    ),
    "065_horizon_missing": (
        "LX0609-065",
        "data_gap",
        {
            "verification_kind": "postoperative_senior_round_window_unavailable",
            "issue": "source_unavailable",
        },
    ),
    "066_timely": (
        "LX0609-066",
        "compliant",
        {
            "verification_kind": "postoperative_first_course_presence_check",
            "performed_surgery_count": 1,
            "postoperative_first_course_count": 1,
        },
    ),
    "066_unhandled": (
        "LX0609-066",
        "non_compliant",
        {
            "verification_kind": "postoperative_first_course_presence_check",
            "performed_surgery_count": 2,
            "postoperative_first_course_count": 1,
        },
    ),
}


@pytest.mark.parametrize("_case", _FACTS_BY_CASE.values(), ids=_FACTS_BY_CASE)
def test_postoperative_mapping_freezes_reachable_safe_fact_shapes(
    _case: tuple[str, str, dict[str, object]],
) -> None:
    rule_id, status, raw_facts = _case

    safe_facts = safe_postoperative_customer_display_facts(
        rule_id=rule_id,
        raw=raw_facts,
    )

    assert safe_facts is not None
    assert "document_id" not in repr(safe_facts)
    assert postoperative_customer_fact_status_is_valid(
        rule_id=rule_id,
        status=status,
        safe_facts=safe_facts,
    )


@pytest.mark.parametrize("rule_id", sorted(POSTOPERATIVE_CUSTOMER_RULE_IDS))
def test_postoperative_rules_are_finalizer_facts_and_public_fact_ref_owners(
    rule_id: str,
) -> None:
    assert finalizer_owns_executor_customer_display_facts(rule_id)
    assert finalizer_requires_public_fact_ref_evidence(rule_id)


@pytest.mark.parametrize(
    ("rule_id", "status", "raw_facts"),
    [
        ("LX0609-064", "compliant", _FACTS_BY_CASE["064_overdue"][2]),
        ("LX0609-065", "compliant", _FACTS_BY_CASE["065_overdue"][2]),
        ("LX0609-066", "non_compliant", _FACTS_BY_CASE["066_timely"][2]),
        (
            "LX0609-064",
            "data_gap",
            {
                **_FACTS_BY_CASE["064_horizon_missing"][2],
                "source_document_refs": ["forged-private-ref"],
            },
        ),
    ],
    ids=["064_status_conflict", "065_status_conflict", "066_status_conflict", "private_fact_ref"],
)
def test_postoperative_contract_failure_safely_downgrades_to_technical_error(
    rule_id: str, status: str, raw_facts: object
) -> None:
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": rule_id,
            "status": status,
            "reason_code": "executor_reason",
            "findings": "执行器结论",
            "customer_evidence": [{"source_type": "must-be-cleared"}],
        },
        raw_facts=raw_facts,
    )

    assert handled is True
    assert (finalized["status"], finalized["reason_code"]) == (
        "technical_error",
        "model_invalid_output",
    )
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized
    assert "findings" not in finalized


@pytest.mark.parametrize("status", ["data_gap", "not_applicable"])
def test_postoperative_absent_facts_preserve_existing_gap_or_not_applicable_status(
    status: str,
) -> None:
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={"rule_id": "LX0609-064", "status": status, "reason_code": "executor_reason"},
        raw_facts=None,
    )

    assert handled is True
    assert finalized["status"] == status
    assert "customer_display_facts" not in finalized


def test_aggregator_has_no_postoperative_rule_reference() -> None:
    aggregator_source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    ).read_text(encoding="utf-8")

    assert all(
        rule_id not in aggregator_source for rule_id in POSTOPERATIVE_CUSTOMER_RULE_IDS
    )
