from __future__ import annotations

from pathlib import Path

import pytest

from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_canonical_result,
    finalize_luxian_0609_executor_customer_display_facts,
    finalizer_owns_executor_customer_display_facts,
    finalizer_requires_public_fact_ref_evidence,
)
from app.services.luxian_0609.critical_value_result_mapping import (
    critical_value_customer_fact_status_is_valid,
    safe_critical_value_customer_display_facts,
)


def _event(*, outcome: str, rule_id: str) -> dict[str, object]:
    event: dict[str, object] = {
        "critical_item_names": ["血钾"],
        "critical_flags": ["PH"],
        "report_time": "2026-06-01 08:00:00",
        "outcome": outcome,
    }
    if outcome in {"timely", "overdue", "handled"}:
        event["disposition_time"] = "2026-06-01 10:00:00"
    if rule_id == "LX0609-052" and outcome in {"timely", "overdue"}:
        event["interval_hours"] = 2.0 if outcome == "timely" else 7.0
    return event


def _facts(*, rule_id: str, outcome: str) -> dict[str, object]:
    facts: dict[str, object] = {
        "verification_kind": (
            "critical_value_timeliness_check"
            if rule_id == "LX0609-052"
            else "critical_value_disposition_presence_check"
        ),
        "critical_item_names": ["血钾"],
        "critical_flags": ["PH"],
        "report_times": ["2026-06-01 08:00:00"],
        "disposition_times": ["2026-06-01 10:00:00"]
        if outcome in {"timely", "overdue", "handled"}
        else [],
        "event_results": [_event(outcome=outcome, rule_id=rule_id)],
    }
    if rule_id == "LX0609-052":
        facts.update(threshold_hours=6, actual_interval_hours=[2.0])
    return facts


@pytest.mark.parametrize(
    ("rule_id", "facts", "status"),
    [
        ("LX0609-052", _facts(rule_id="LX0609-052", outcome="timely"), "compliant"),
        (
            "LX0609-052",
            _facts(rule_id="LX0609-052", outcome="overdue"),
            "non_compliant",
        ),
        (
            "LX0609-052",
            _facts(rule_id="LX0609-052", outcome="unhandled"),
            "non_compliant",
        ),
        ("LX0609-053", _facts(rule_id="LX0609-053", outcome="handled"), "compliant"),
        (
            "LX0609-053",
            _facts(rule_id="LX0609-053", outcome="unhandled"),
            "non_compliant",
        ),
    ],
)
def test_critical_value_mapping_preserves_active_outcomes(
    rule_id: str, facts: dict[str, object], status: str
) -> None:
    safe = safe_critical_value_customer_display_facts(rule_id=rule_id, raw=facts)

    assert safe == facts
    assert (
        critical_value_customer_fact_status_is_valid(
            rule_id=rule_id, status=status, safe_facts=safe
        )
        is True
    )
    assert (
        critical_value_customer_fact_status_is_valid(
            rule_id=rule_id, status="technical_error", safe_facts=safe
        )
        is True
    )


def test_critical_value_mapping_preserves_window_not_mature() -> None:
    facts = _facts(rule_id="LX0609-052", outcome="window_not_mature")
    facts.update(
        evaluation_window_mature=False,
        deadline_times=["2026-06-01 14:00:00"],
        evaluation_time="2026-06-01 12:00:00",
    )

    safe = safe_critical_value_customer_display_facts(rule_id="LX0609-052", raw=facts)

    assert safe == facts
    assert (
        critical_value_customer_fact_status_is_valid(
            rule_id="LX0609-052", status="not_applicable", safe_facts=safe
        )
        is True
    )
    assert (
        critical_value_customer_fact_status_is_valid(
            rule_id="LX0609-052", status="non_compliant", safe_facts=safe
        )
        is False
    )


@pytest.mark.parametrize("rule_id", ["LX0609-052", "LX0609-053"])
def test_critical_value_mapping_preserves_result_detail_gap(rule_id: str) -> None:
    facts = {
        "failure_kind": "critical_value_result_detail_missing",
        "lab_report_count": 1,
        "missing_source": "labtest_item_report",
    }
    safe = safe_critical_value_customer_display_facts(rule_id=rule_id, raw=facts)

    assert safe == facts
    assert (
        critical_value_customer_fact_status_is_valid(
            rule_id=rule_id, status="data_gap", safe_facts=safe
        )
        is True
    )


def test_critical_value_mapping_preserves_horizon_gap() -> None:
    facts = {
        "verification_kind": "critical_value_evaluation_horizon_unavailable",
        "issue": "authoritative_time_missing",
    }
    safe = safe_critical_value_customer_display_facts(rule_id="LX0609-052", raw=facts)

    assert safe == facts
    assert (
        critical_value_customer_fact_status_is_valid(
            rule_id="LX0609-052", status="data_gap", safe_facts=safe
        )
        is True
    )


def test_critical_value_finalizer_fail_closes_status_fact_conflict() -> None:
    facts = _facts(rule_id="LX0609-052", outcome="timely")
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-052",
            "status": "non_compliant",
            "reason_code": "threshold_exceeded",
            "customer_display_facts": facts,
            "customer_evidence": [{"source_document_id": "must-clear"}],
        },
        raw_facts=facts,
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized


def test_critical_value_finalizer_and_canonical_contract() -> None:
    facts = {
        "failure_kind": "critical_value_result_detail_missing",
        "lab_report_count": 1,
        "missing_source": "labtest_item_report",
    }
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-052",
            "status": "data_gap",
            "reason_code": "required_field_missing",
        },
        raw_facts=facts,
    )
    canonical = finalize_luxian_0609_canonical_result(finalized)

    assert handled is True
    assert canonical["customer_display_facts"] == facts
    assert canonical["missing_sources"] == ["检验结果明细"]
    assert finalizer_owns_executor_customer_display_facts("LX0609-052") is True
    assert finalizer_requires_public_fact_ref_evidence("LX0609-052") is True


def test_aggregator_has_no_critical_value_rule_reference() -> None:
    aggregator = (
        Path(__file__).parents[2] / "app/services/luxian_0609_result_aggregator.py"
    )
    source = aggregator.read_text(encoding="utf-8")

    assert "LX0609-052" not in source
    assert "LX0609-053" not in source
