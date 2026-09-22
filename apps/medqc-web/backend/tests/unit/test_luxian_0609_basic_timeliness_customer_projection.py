from __future__ import annotations

import pytest

from app.services.luxian_0609.basic_timeliness_customer_projection import (
    BASIC_TIMELINESS_CUSTOMER_RULE_IDS,
    basic_timeliness_customer_fact_status_is_valid,
    safe_basic_timeliness_customer_display_facts,
)
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalizer_owns_executor_customer_display_facts,
    finalizer_requires_public_fact_ref_evidence,
)


_WITHIN_FACTS_BY_RULE = {
    "LX0609-01-01-01": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "admission_record",
        "timeliness_state": "within",
        "threshold_hours": 24,
        "source_label": "入院记录",
    },
    "LX0609-01-02-01": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "first_course_record",
        "timeliness_state": "within",
        "threshold_hours": 8,
        "source_label": "首次病程记录",
    },
    "LX0609-09-01-01": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "rescue_record",
        "timeliness_state": "within",
        "threshold_hours": 6,
        "source_label": "抢救记录",
    },
    "LX0609-09-01-02": {
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "content_state": "compliant",
        "required_fields": [
            "condition_change",
            "rescue_time",
            "rescue_measures",
            "rescue_outcome",
            "participant_names",
            "participant_titles",
        ],
        "missing_fields": [],
        "unknown_fields": [],
        "rescue_content_events": [
            {
                "event_index": 1,
                "document_ref": "a" * 64,
                "source_document_id": "RESCUE-1",
                "record_time": "2026-09-01T10:00:00+08:00",
                "body_scope": "complete",
                "field_facts": {
                    field: {
                        "state": "present",
                        "start": 0,
                        "end": 1,
                        "quote": "抢",
                    }
                    for field in (
                        "condition_change",
                        "rescue_time",
                        "rescue_measures",
                        "rescue_outcome",
                        "participant_names",
                        "participant_titles",
                    )
                },
                "missing_fields": [],
                "unknown_fields": [],
            }
        ],
        "failure_kind": "",
    },
    "LX0609-02-01-01": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "attending_course_record",
        "timeliness_state": "within",
        "threshold_hours": 48,
        "source_label": "主治医师首次查房记录",
    },
    "LX0609-02-01-02": {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "senior_course_record",
        "timeliness_state": "within",
        "threshold_hours": 72,
        "source_label": "最高级别医师首次查房记录",
    },
}


def _executor_result(rule_id: str, status: str) -> dict[str, str]:
    return {
        "rule_id": rule_id,
        "status": status,
        "reason_code": "executor_reason",
        "findings": "执行器结论",
        "customer_evidence": [{"source_type": "forbidden-on-contract-failure"}],
    }


@pytest.mark.parametrize("rule_id", sorted(BASIC_TIMELINESS_CUSTOMER_RULE_IDS))
def test_all_basic_timeliness_rules_have_safe_compliant_fact_shape(rule_id: str):
    raw_facts = _WITHIN_FACTS_BY_RULE[rule_id]

    safe_facts = safe_basic_timeliness_customer_display_facts(
        rule_id=rule_id,
        raw=raw_facts,
    )

    if rule_id == "LX0609-09-01-02":
        assert safe_facts is not None
        assert safe_facts["content_state"] == "compliant"
        assert safe_facts["missing_fields"] == []
        assert safe_facts["unknown_fields"] == []
        assert safe_facts["rescue_content_events"][0]["field_facts"] == {
            field: {"state": "present"}
            for field in raw_facts["required_fields"]
        }
        serialized = repr(safe_facts)
        assert "document_ref" not in serialized
        assert "source_document_id" not in serialized
        assert "quote" not in serialized
        assert "start" not in serialized
        assert "end" not in serialized
    else:
        assert safe_facts == raw_facts
    assert basic_timeliness_customer_fact_status_is_valid(
        rule_id=rule_id,
        status="compliant",
        safe_facts=safe_facts,
    )


@pytest.mark.parametrize("rule_id", sorted(BASIC_TIMELINESS_CUSTOMER_RULE_IDS))
def test_all_basic_timeliness_rules_are_finalizer_facts_and_public_evidence_owners(
    rule_id: str,
):
    assert finalizer_owns_executor_customer_display_facts(rule_id)
    assert finalizer_requires_public_fact_ref_evidence(rule_id)


def test_lx004_data_gap_fact_shape_is_accepted_without_reinterpreting_rescue_logic():
    raw_facts = {
        "failure_kind": "rescue_record_missing_after_trigger",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
    }

    safe_facts = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-01",
        raw=raw_facts,
    )

    assert safe_facts == raw_facts
    assert basic_timeliness_customer_fact_status_is_valid(
        rule_id="LX0609-09-01-01",
        status="data_gap",
        safe_facts=safe_facts,
    )


def test_lx001_uncertain_conflict_fact_shape_is_accepted():
    raw_facts = {
        "failure_kind": "evidence_time_conflict",
        "target_document": "admission_record",
        "source_label": "入院记录",
        "timeliness_state": "before",
        "threshold_hours": 24,
        "anchor_time": "2026-06-01T09:00:00",
        "observed_time": "2026-06-01T08:00:00",
        "time_conflict_seconds": 3600,
    }

    safe_facts = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-01-01-01",
        raw=raw_facts,
    )

    assert basic_timeliness_customer_fact_status_is_valid(
        rule_id="LX0609-01-01-01",
        status="uncertain",
        safe_facts=safe_facts,
    )


@pytest.mark.parametrize(
    ("status", "raw_facts"),
    [
        ("compliant", None),
        ("non_compliant", _WITHIN_FACTS_BY_RULE["LX0609-01-01-01"]),
        (
            "compliant",
            {
                **_WITHIN_FACTS_BY_RULE["LX0609-01-01-01"],
                "source_document_refs": ["forged-internal-ref"],
            },
        ),
    ],
    ids=["missing_facts", "contradictory_status", "private_fact_ref"],
)
def test_basic_timeliness_contract_failure_safely_downgrades_to_technical_error(
    status: str,
    raw_facts: object,
):
    finalized, handled = finalize_luxian_0609_executor_customer_display_facts(
        result=_executor_result("LX0609-01-01-01", status),
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
