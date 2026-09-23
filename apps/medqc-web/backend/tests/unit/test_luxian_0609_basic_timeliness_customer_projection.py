from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.luxian_0609.basic_timeliness_customer_projection import (
    BASIC_TIMELINESS_CUSTOMER_RULE_IDS,
    basic_timeliness_customer_fact_status_is_valid,
    safe_basic_timeliness_customer_display_facts,
    validate_published_rescue_content_facts,
)
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    finalizer_owns_executor_customer_display_facts,
    finalizer_requires_public_fact_ref_evidence,
)
import app.services.luxian_0609.canonical_result_finalizer as finalizer_module
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.qc_workspace.canonical_result_store import (
    safe_customer_display_facts,
    validated_customer_explanation,
)
from app.services.custom_qc_workspace_service import project_customer_safe_result_item


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


def test_rescue_missing_participant_title_survives_safe_fact_save_and_read():
    rule_id = "LX0609-09-01-02"
    raw = deepcopy(_WITHIN_FACTS_BY_RULE[rule_id])
    raw["content_state"] = "non_compliant"
    raw["missing_fields"] = ["participant_titles"]
    raw["rescue_content_events"][0]["missing_fields"] = ["participant_titles"]
    raw["rescue_content_events"][0]["field_facts"]["participant_titles"] = {
        "state": "absent", "start": None, "end": None, "quote": "",
    }

    safe = safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=raw)
    assert safe is not None
    assert safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=safe) is None
    item = {"customer_display_facts": safe}
    assert safe_customer_display_facts(item, rule_id=rule_id) == safe
    assert validated_customer_explanation(
        item, rule_id=rule_id, status="non_compliant"
    ) == (safe, [])
    projected = project_customer_safe_result_item(
        {"rule_id": rule_id, "status": "non_compliant", "result_status": "non_compliant",
         "display_status": "non_compliant", "is_compliant": False,
         "customer_display_facts": safe},
        hmac_key="unit-test-key",
    )
    assert projected["customer_display_facts"] == safe
    assert "document_ref" not in repr(safe)
    assert "source_document_id" not in repr(safe)
    assert "quote" not in repr(safe)

    for extra in (
        {"source_document_id": "RESCUE-1"},
        {"document_ref": "a" * 64},
    ):
        forged = deepcopy(safe)
        forged["rescue_content_events"][0].update(extra)
        assert safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=forged) is None
    forged = deepcopy(safe)
    forged["rescue_content_events"][0]["field_facts"]["participant_titles"]["quote"] = "伪造原文"
    assert safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=forged) is None


def test_rescue_published_facts_reject_internal_shape_and_unknown_fields():
    rule_id = "LX0609-09-01-02"
    raw = deepcopy(_WITHIN_FACTS_BY_RULE[rule_id])
    safe = safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=raw)
    assert safe is not None
    assert safe_customer_display_facts({"customer_display_facts": safe}, rule_id=rule_id) == safe
    missing_required = deepcopy(safe)
    missing_required.pop("content_state")
    for invalid in (raw, {**safe, "unexpected": "private"}, missing_required):
        with pytest.raises(ValueError):
            safe_customer_display_facts({"customer_display_facts": invalid}, rule_id=rule_id)
        with pytest.raises(ValueError):
            project_customer_safe_result_item(
                {"rule_id": rule_id, "status": "compliant", "customer_display_facts": invalid},
                hmac_key="unit-test-key",
            )


@pytest.mark.parametrize(
    ("path", "invalid"),
    [
        (("content_state",), []),
        (("failure_kind",), {}),
        (("missing_fields",), [{}]),
        (("unknown_fields",), [[]]),
        (("rescue_content_events", 0, "body_scope"), {}),
        (("rescue_content_events", 0, "missing_fields"), [{}]),
        (("rescue_content_events", 0, "unknown_fields"), [[]]),
        (("rescue_content_events", 0, "field_facts", "participant_titles", "state"), []),
    ],
)
def test_rescue_published_facts_reject_json_field_type_errors(path, invalid):
    raw = deepcopy(_WITHIN_FACTS_BY_RULE["LX0609-09-01-02"])
    safe = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-09-01-02", raw=raw,
    )
    assert safe is not None and safe["rescue_content_events"]
    target = safe
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid
    assert validate_published_rescue_content_facts(safe) is None
    with pytest.raises(ValueError):
        safe_customer_display_facts(
            {"customer_display_facts": safe}, rule_id="LX0609-09-01-02",
        )


def test_rescue_reduced_publication_does_not_reproject_published_facts(monkeypatch):
    raw = deepcopy(_WITHIN_FACTS_BY_RULE["LX0609-09-01-02"])
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id="LX0609-09-01-02", snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT,
        qc_direction=QcDirection.SATISFIED,
        reason_code="requirement_satisfied", fact_refs=("b" * 64,),
        evaluator_version="test-v1", confidence=1.0,
    ))

    original = finalizer_module.validate_luxian_0609_executor_customer_display_facts
    calls = []
    def tracked_internal_projection(**kwargs):
        calls.append(kwargs["raw"])
        return original(**kwargs)
    monkeypatch.setattr(
        finalizer_module, "validate_luxian_0609_executor_customer_display_facts",
        tracked_internal_projection,
    )
    result = finalizer_module.finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=raw,
        evidence_snapshot=None, evidence_materials=None,
    )
    assert result["status"] == "compliant"
    assert result["customer_display_facts"] == (
        safe_basic_timeliness_customer_display_facts(
            rule_id="LX0609-09-01-02", raw=raw,
        )
    )
    assert calls == [raw]


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
