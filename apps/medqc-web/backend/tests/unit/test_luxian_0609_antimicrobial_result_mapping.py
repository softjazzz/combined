from __future__ import annotations

from copy import deepcopy
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
from app.services.qc_workspace.canonical_result_store import (
    envelope_item_from_rule_result,
)


_MATURE_EVENT = {
    "antimicrobial": "美罗培南",
    "event_state": "mature",
    "start_time": "2026-06-01 10:00:00",
    "window_start_time": "2026-06-03 10:00:00",
    "window_end_time": "2026-06-04 10:00:00",
    "evaluation_time": "2026-06-04 10:00:00",
    "elapsed_hours": 72.0,
}
_NOT_MATURE_EVENT = {
    **_MATURE_EVENT,
    "event_state": "not_mature",
    "evaluation_time": "2026-06-03 22:00:00",
    "elapsed_hours": 60.0,
}


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
            "event_windows": [_MATURE_EVENT],
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
            "event_windows": [_MATURE_EVENT],
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
            "event_windows": [_NOT_MATURE_EVENT],
            "window_state": "evaluation_window_not_mature",
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
            "event_windows": [],
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


def _055_facts(*events: dict[str, object]) -> dict[str, object]:
    return {
        "verification_kind": "antimicrobial_effect_evaluation_check",
        "antimicrobials": list(dict.fromkeys(
            str(event["antimicrobial"]) for event in events
        )) or ["美罗培南"],
        "window_hours": [48, 72],
        "evaluation_intervals": [],
        "unmatched_antimicrobials": [],
        "association_ambiguous": False,
        "event_windows": list(events),
    }


def test_055_c03_three_mature_event_windows_survive_mapping_and_envelope() -> None:
    events = [
        {
            "antimicrobial": name,
            "event_state": "mature",
            "start_time": start,
            "window_start_time": window_start,
            "window_end_time": window_end,
            "evaluation_time": "2025-08-13 09:27:40",
            "elapsed_hours": elapsed,
        }
        for name, start, window_start, window_end, elapsed in (
            ("头孢呋辛", "2025-08-09 21:11:42", "2025-08-11 21:11:42", "2025-08-12 21:11:42", 84.27),
            ("左氧氟沙星", "2025-08-09 21:16:59", "2025-08-11 21:16:59", "2025-08-12 21:16:59", 84.18),
            ("左氧氟沙星", "2025-08-09 21:17:14", "2025-08-11 21:17:14", "2025-08-12 21:17:14", 84.17),
        )
    ]
    raw = _055_facts(*events)
    raw["unmatched_antimicrobials"] = ["头孢呋辛", "左氧氟沙星"]

    safe = safe_antimicrobial_customer_display_facts(rule_id="LX0609-055", raw=raw)
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-055",
            "status": "non_compliant",
            "reason_code": "threshold_exceeded",
        },
        raw_facts=raw,
    )
    envelope = envelope_item_from_rule_result(finalized)

    assert safe == raw
    assert handled is True
    assert finalized["customer_display_facts"]["event_windows"] == events
    assert envelope["customer_display_facts"]["event_windows"] == events
    assert envelope["decision_facts"]["event_windows"] == events


@pytest.mark.parametrize(
    ("elapsed", "evaluation_time", "event_state"),
    (
        (0.0, "2026-06-01 10:00:00", "not_started"),
        (48.0, "2026-06-03 10:00:00", "not_mature"),
        (72.0, "2026-06-04 10:00:00", "mature"),
    ),
)
def test_055_datetime_event_state_keeps_exact_48_72_boundaries(
    elapsed: float, evaluation_time: str, event_state: str,
) -> None:
    event = {
        **_MATURE_EVENT,
        "event_state": event_state,
        "evaluation_time": evaluation_time,
        "elapsed_hours": elapsed,
    }
    raw = _055_facts(event)

    assert safe_antimicrobial_customer_display_facts(
        rule_id="LX0609-055", raw=raw
    ) == raw


@pytest.mark.parametrize(
    ("evaluation_date", "event_state"),
    (("2026-05-31", "conflict"), ("2026-06-02", "not_started"),
     ("2026-06-04", "not_mature"), ("2026-06-05", "mature")),
)
def test_055_date_only_window_uses_conservative_state_without_elapsed(
    evaluation_date: str, event_state: str,
) -> None:
    event = {
        key: value for key, value in _MATURE_EVENT.items()
        if key not in {"evaluation_time", "elapsed_hours"}
    }
    event.update(event_state=event_state, evaluation_date=evaluation_date)
    raw = _055_facts(event)

    assert safe_antimicrobial_customer_display_facts(
        rule_id="LX0609-055", raw=raw
    ) == raw


@pytest.mark.parametrize(
    ("event", "window_state"),
    ((_MATURE_EVENT | {"event_state": "not_started", "evaluation_time": "2026-06-02 10:00:00", "elapsed_hours": 24.0}, "evaluation_window_not_started"),
     (_NOT_MATURE_EVENT, "evaluation_window_not_mature")),
)
def test_055_immature_window_status_contract_is_preserved(
    event: dict[str, object], window_state: str,
) -> None:
    raw = _055_facts(event)
    raw["window_state"] = window_state
    safe = safe_antimicrobial_customer_display_facts(rule_id="LX0609-055", raw=raw)

    assert safe == raw
    assert antimicrobial_customer_fact_status_is_valid(
        rule_id="LX0609-055", status="not_applicable", safe_facts=safe
    )


def test_055_not_applicable_allows_evaluated_mature_event_with_immature_event() -> None:
    raw = _055_facts(deepcopy(_MATURE_EVENT), deepcopy(_NOT_MATURE_EVENT))
    raw["evaluation_intervals"] = [60.0]
    raw["window_state"] = "evaluation_window_not_mature"
    safe = safe_antimicrobial_customer_display_facts(rule_id="LX0609-055", raw=raw)

    assert safe == raw
    assert antimicrobial_customer_fact_status_is_valid(
        rule_id="LX0609-055", status="not_applicable", safe_facts=safe
    )


@pytest.mark.parametrize("case", ("empty", "mature_only", "unevaluated_mature"))
def test_055_not_applicable_rejects_missing_immaturity_or_mature_evaluation(
    case: str,
) -> None:
    if case == "empty":
        raw = _055_facts()
    elif case == "mature_only":
        raw = _055_facts(deepcopy(_MATURE_EVENT))
        raw["evaluation_intervals"] = [60.0]
    else:
        raw = _055_facts(deepcopy(_MATURE_EVENT), deepcopy(_NOT_MATURE_EVENT))
    raw["window_state"] = "evaluation_window_not_mature"
    safe = safe_antimicrobial_customer_display_facts(rule_id="LX0609-055", raw=raw)

    assert safe is not None
    assert not antimicrobial_customer_fact_status_is_valid(
        rule_id="LX0609-055", status="not_applicable", safe_facts=safe
    )


def test_055_empty_and_partial_data_gap_windows_remain_legal() -> None:
    empty = _055_facts()
    conflict = _055_facts({
        **_MATURE_EVENT,
        "event_state": "conflict",
        "evaluation_time": "2026-05-31 10:00:00",
        "elapsed_hours": -24.0,
    })
    for raw in (empty, conflict):
        safe = safe_antimicrobial_customer_display_facts(rule_id="LX0609-055", raw=raw)
        assert safe == raw
        assert antimicrobial_customer_fact_status_is_valid(
            rule_id="LX0609-055", status="data_gap", safe_facts=safe
        )


@pytest.mark.parametrize(
    ("mutation", "value"),
    (
        ("top_unknown", "forbidden"),
        ("event_order_id", "PRIVATE-ORDER-ID"),
        ("event_start_time", "2026-06-01"),
        ("event_elapsed_hours", float("nan")),
        ("event_elapsed_hours", 71.0),
        ("event_window_start_time", "2026-06-03 10:00:01"),
        ("event_event_state", "not_mature"),
        ("event_antimicrobial", "万古霉素"),
    ),
)
def test_055_rejects_unknown_identity_time_number_and_arithmetic_conflicts(
    mutation: str, value: object,
) -> None:
    raw = _055_facts(deepcopy(_MATURE_EVENT))
    if mutation == "top_unknown":
        raw["private_identity"] = value
    else:
        _, field = mutation.split("_", 1)
        raw["event_windows"][0][field] = value

    assert safe_antimicrobial_customer_display_facts(
        rule_id="LX0609-055", raw=raw
    ) is None


@pytest.mark.parametrize(
    ("status", "changes"),
    (
        ("compliant", {"evaluation_intervals": []}),
        ("compliant", {"evaluation_intervals": [47.99]}),
        ("non_compliant", {"unmatched_antimicrobials": []}),
        ("not_applicable", {"window_state": "evaluation_window_not_started"}),
    ),
)
def test_055_rejects_final_status_window_contradictions(
    status: str, changes: dict[str, object],
) -> None:
    raw = _055_facts(deepcopy(_MATURE_EVENT))
    raw.update(changes)
    safe = safe_antimicrobial_customer_display_facts(rule_id="LX0609-055", raw=raw)

    assert safe is not None
    assert not antimicrobial_customer_fact_status_is_valid(
        rule_id="LX0609-055", status=status, safe_facts=safe
    )


def test_055_invalid_event_facts_fail_closed_in_finalizer() -> None:
    raw = _055_facts({**_MATURE_EVENT, "order_id": "PRIVATE-ORDER-ID"})

    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result={
            "rule_id": "LX0609-055",
            "status": "non_compliant",
            "reason_code": "threshold_exceeded",
            "customer_evidence": [{"source_type": "must-be-cleared"}],
        },
        raw_facts=raw,
    )

    assert handled is True
    assert finalized["status"] == "technical_error"
    assert finalized["reason_code"] == "model_invalid_output"
    assert "customer_display_facts" not in finalized
    assert "customer_evidence" not in finalized

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
