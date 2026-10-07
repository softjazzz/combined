from collections.abc import Mapping
from typing import Any

import pytest

from app.services.luxian_0916.input_context import (
    build_luxian_0916_context,
    merge_luxian_0916_semantic_facts,
)
from app.services.luxian_0916.surgery_consent_rules import (
    execute_surgery_consent_rules,
)


def test_unavailable_empty_anesthesia_source_remains_unknown_through_rule_execution():
    context = build_luxian_0916_context(
        bundle={},
        evidence_payload={
            "programmatic_timeline": {
                "documents": {"anesthesia_record": []},
                "source_readiness": {"anesthesia_record": "unavailable"},
            }
        },
    )
    merged = merge_luxian_0916_semantic_facts(context=context, extracted={})

    result = execute_surgery_consent_rules(merged, ("LX0916-023",))[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_fact_unavailable"
    assert result.decision_facts["event_value"] is None


def _execute(
    timeline: Mapping[str, Any],
    *,
    explicit_events: Mapping[str, Any] | None = None,
    extracted: Mapping[str, Any] | None = None,
):
    context = build_luxian_0916_context(
        bundle={
            "structured_context": {
                "luxian_0916_facts": {"event_facts": explicit_events or {}}
            }
        },
        evidence_payload={"programmatic_timeline": timeline},
    )
    merged = merge_luxian_0916_semantic_facts(
        context=context, extracted=extracted or {}
    )
    return merged, execute_surgery_consent_rules(merged, ("LX0916-023",))[0]


@pytest.mark.parametrize(
    "readiness", ["partial", "unavailable", None, "unknown", "Complete", True]
)
def test_incomplete_empty_source_blocks_model_false(readiness):
    merged, result = _execute(
        {
            "documents": {"anesthesia_record": []},
            "source_readiness": {"anesthesia_record": readiness},
        },
        extracted={"event_facts": {"anesthesia_performed": False}},
    )

    assert merged["event_facts"]["anesthesia_performed"] is None
    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_fact_unavailable"
    assert result.decision_facts["event_value"] is None


def test_empty_source_without_readiness_is_not_negative_evidence():
    _, result = _execute({"documents": {"anesthesia_record": []}})

    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_fact_unavailable"


@pytest.mark.parametrize("readiness", ["partial", "unavailable", "complete"])
def test_attempted_source_without_document_field_remains_unknown(readiness):
    merged, result = _execute({"source_readiness": {"anesthesia_record": readiness}})

    assert merged["event_facts"] == {"anesthesia_performed": None}
    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_fact_unavailable"


@pytest.mark.parametrize("rows", [[], ()])
def test_complete_valid_empty_array_preserves_negative_projection(rows):
    merged, result = _execute(
        {
            "documents": {"anesthesia_record": rows},
            "source_readiness": {"anesthesia_record": "complete"},
        },
        extracted={"event_facts": {"anesthesia_performed": True}},
    )

    assert merged["event_facts"] == {
        "anesthesia_performed": False,
        "anesthesia_record_formed": False,
    }
    assert result.status == "not_applicable"
    assert result.reason_code == "trigger_event_not_present"
    assert result.decision_facts["event_value"] is False


@pytest.mark.parametrize("rows", [None, "", {}, ["invalid-row"], 0])
def test_complete_readiness_does_not_turn_invalid_document_field_into_empty_source(
    rows,
):
    merged, result = _execute(
        {
            "documents": {"anesthesia_record": rows},
            "source_readiness": {"anesthesia_record": "complete"},
        }
    )

    assert merged["event_facts"]["anesthesia_performed"] is None
    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_fact_unavailable"


@pytest.mark.parametrize("readiness", ["partial", "complete", None])
def test_existing_record_preserves_positive_event_and_original_anchor(readiness):
    merged, result = _execute(
        {
            "documents": {"anesthesia_record": [{"document_id": "ANA-1"}]},
            "source_readiness": {"anesthesia_record": readiness},
        },
        extracted={"event_facts": {"anesthesia_performed": False}},
    )

    assert merged["event_facts"]["anesthesia_performed"] is True
    assert merged["event_facts"]["anesthesia_record_formed"] is True
    assert result.status == "compliant"
    assert result.reason_code == "anesthesia_record_present"
    assert result.document_anchors == (
        {"document_type": "anesthesia_record", "document_id": "ANA-1"},
    )


@pytest.mark.parametrize("explicit_value", [True, False])
def test_incomplete_empty_source_preserves_only_explicit_positive_event(explicit_value):
    merged, result = _execute(
        {
            "documents": {"anesthesia_record": []},
            "source_readiness": {"anesthesia_record": "unavailable"},
        },
        explicit_events={"anesthesia_performed": explicit_value},
        extracted={"event_facts": {"anesthesia_performed": False}},
    )

    assert merged["event_facts"]["anesthesia_performed"] is (
        True if explicit_value else None
    )
    assert result.status == "data_quality_gap"
    assert result.reason_code == (
        "semantic_fact_unavailable" if explicit_value else "event_fact_unavailable"
    )


def test_absent_unattempted_source_does_not_add_unknown_event():
    context = build_luxian_0916_context(bundle={}, evidence_payload={})
    assert "anesthesia_performed" not in context["event_facts"]

    merged, result = _execute(
        {}, extracted={"event_facts": {"anesthesia_performed": False}}
    )
    assert merged["event_facts"]["anesthesia_performed"] is False
    assert result.status == "not_applicable"


def test_source_gate_does_not_change_formed_surgery_or_discharge_projections():
    merged, _ = _execute(
        {
            "documents": {
                "anesthesia_record": [],
                "surgery_application": [],
                "surgery_record": [],
                "discharge_record": [],
            },
            "discharge_time": "",
            "source_readiness": {"anesthesia_record": "partial"},
        }
    )

    assert merged["event_facts"] == {
        "anesthesia_performed": None,
        "anesthesia_record_formed": False,
        "surgery_arranged": False,
        "surgery_performed": False,
    }
    assert merged["discharge_facts"] == {
        "discharge_arranged": False,
        "discharge_record_formed": False,
    }


def test_shared_anesthesia_event_keeps_022_unknown_without_arranged_event():
    merged, _ = _execute(
        {
            "documents": {"anesthesia_record": []},
            "source_readiness": {"anesthesia_record": "unavailable"},
        },
        explicit_events={"anesthesia_arranged": False},
    )

    result = execute_surgery_consent_rules(merged, ("LX0916-022",))[0]

    assert result.status == "data_quality_gap"
    assert result.reason_code == "event_fact_unavailable"
    assert result.decision_facts["event_value"] is None
