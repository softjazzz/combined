"""原始 069/071–074 连续性族已发布事实的只读边界。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609.continuity_result_mapping as mapping
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result,
)
from tests.unit.test_luxian_0609_continuity_result_mapping import (
    test_continuity_mapping_freezes_all_reachable_fact_shapes as existing_shapes,
)
from tests.unit.test_luxian_0609_native_extended_document_execution import _evaluate_selected


RULES = (
    "LX0609-04-02-07", "LX0609-10-01-01", "LX0609-10-02-01",
    "LX0609-10-02-02", "LX0609-12-02-01",
)
RAW_SHAPES = existing_shapes.pytestmark[0].args[1]
GAP_SHAPES = (
    ("LX0609-10-01-01", {
        "failure_kind": "physician_signature_timeline_incomplete", "source_document_refs": [],
        "daily_course_record_count": 2, "eligible_daily_course_count": 2,
        "missing_title_count": 0, "missing_time_count": 1, "missing_signature_count": 0,
    }),
    ("LX0609-10-01-01", {
        "failure_kind": "physician_handoff_identity_missing", "source_document_refs": [],
        "change_event_count": 1, "change_times": ["2026-07-01 08:00:00"],
        "handoff_record_count": 1, "handoff_times": ["2026-07-01 07:50:00"],
        "handover_record_count": 1, "handover_times": ["2026-07-01 14:00:00"],
        "handover_threshold_hours": 24,
    }),
)


@pytest.mark.parametrize("rule_id,raw", RAW_SHAPES)
def test_all_existing_publisher_shapes_are_value_identical_and_reject_internal_field(rule_id, raw):
    published = mapping.safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=published, status="data_gap" if rule_id == "LX0609-10-01-01" else "") == published
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule_id, raw={**published, "source_document_refs": []},
        )


@pytest.mark.parametrize("rule_id", RULES)
def test_no_facts_preserves_none_semantics(rule_id):
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=None) is None
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw={}) is None


@pytest.mark.parametrize("rule_id,raw", GAP_SHAPES)
def test_internal_gap_references_are_removed_once_then_public_read_preserves_facts(rule_id, raw):
    published = mapping.safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None and "source_document_refs" not in published
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=published, status="data_gap" if rule_id == "LX0609-10-01-01" else "") == published
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=raw, status="data_gap" if rule_id == "LX0609-10-01-01" else "")


@pytest.mark.parametrize("rule_id,raw", GAP_SHAPES)
def test_gap_initial_finalizer_uses_one_projection(monkeypatch, rule_id, raw):
    original = mapping.safe_continuity_customer_display_facts
    calls = []

    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(mapping, "safe_continuity_customer_display_facts", counted)
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id=rule_id, snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE, evidence_state=EvidenceState.DATA_GAP,
        qc_direction=QcDirection.UNKNOWN, reason_code="required_field_missing",
        fact_refs=(), evaluator_version="continuity-v1",
    ))
    result = finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=raw,
        evidence_snapshot=None, evidence_materials=None,
    )
    assert calls == [rule_id]
    assert result["customer_display_facts"] == original(rule_id=rule_id, raw=raw)


def test_public_read_does_not_call_internal_projection(monkeypatch):
    for rule_id, raw in RAW_SHAPES:
        published = mapping.safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw)
        assert published is not None
        def forbidden(*, rule_id, raw):
            raise AssertionError("published read called internal projection")
        with monkeypatch.context() as patcher:
            patcher.setattr(mapping, "safe_continuity_customer_display_facts", forbidden)
            assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=published, status="data_gap" if rule_id == "LX0609-10-01-01" else "") == published


@pytest.mark.parametrize("rule_id,raw,change", [
    ("LX0609-10-01-01", GAP_SHAPES[0][1], {"missing_time_count": 3}),
    ("LX0609-10-01-01", GAP_SHAPES[1][1], {"handover_threshold_hours": 12}),
    ("LX0609-10-02-01", RAW_SHAPES[10][1], {"threshold_hours": 12}),
    ("LX0609-12-02-01", RAW_SHAPES[14][1], {"association_issue": "unknown"}),
])
def test_existing_pure_consistency_constraints_remain_rejections(rule_id, raw, change):
    published = mapping.safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    damaged = {**published, **change}
    assert mapping.safe_continuity_customer_display_facts(rule_id=rule_id, raw={**raw, **change}) is None
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=damaged, status="data_gap" if rule_id == "LX0609-10-01-01" else "")


def test_nested_events_and_non_json_numbers_fail_closed():
    rule_id, raw = RAW_SHAPES[0]
    published = mapping.safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    damaged = deepcopy(published)
    damaged["event_results"][0]["source_document_id"] = "INTERNAL"
    boolean_sequence = deepcopy(published)
    boolean_sequence["event_results"][0]["sequence"] = True
    for changed in (
        damaged,
        boolean_sequence,
        {**published, "threshold_hours": True},
        {**published, "actual_interval_hours": [float("nan")]},
        {**published, "actual_interval_hours": (6.0,)},
    ):
        with pytest.raises(ValueError, match="解释合同不完整"):
            validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=changed)

    handoff_rule, handoff_raw = RAW_SHAPES[3]
    handoff = mapping.safe_continuity_customer_display_facts(rule_id=handoff_rule, raw=handoff_raw)
    assert handoff is not None
    handoff["events"][0]["event_position"] = True
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=handoff_rule, raw=handoff)


@pytest.mark.asyncio
async def test_fixed_native_binding_aggregate_five_rules_preserves_decision_and_usage():
    snapshot, materials, execution, reduced = await _evaluate_selected(RULES, {
        "physician_change_event": (
            {"event_id": "CHANGE-1", "change_datetime": "2026-07-01 08:00:00",
             "old_physician_name": "甲1", "new_physician_name": "乙1"},
            {"event_id": "CHANGE-2", "change_datetime": "2026-07-03 08:00:00",
             "old_physician_name": "甲2", "new_physician_name": "乙2"},
        ),
        "handoff_record": (
            {"document_id": "HANDOFF-1", "shift_time": "2026-07-01 08:00:00",
             "handoff_doctor": "甲1", "record_time": "2026-07-01 07:50:00"},
            {"document_id": "HANDOFF-2", "shift_time": "2026-07-03 08:00:00",
             "handoff_doctor": "甲2", "record_time": "2026-07-03 07:50:00"},
        ),
        "handover_record": (
            {"document_id": "HANDOVER-1", "shift_time": "2026-07-01 08:00:00",
             "handover_doctor": "乙1", "record_time": "2026-07-01 14:00:00"},
        ),
    })
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": rule_id} for rule_id in RULES],
        execution_results=execution.results, reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    by_rule = {item["rule_id"]: item for item in canonical}
    assert execution.llm_call_count == execution.total_tokens == 0
    assert set(by_rule) == set(RULES)
    assert dict(execution.customer_display_facts)["LX0609-10-01-01"]["events"][1]["outcome"] == "handover_missing"
    for decision in reduced:
        result = by_rule[decision.rule_id]
        assert (result["status"], result["reason_code"]) == (
            decision.final_state.value, decision.reason_code,
        )
        raw = dict(execution.customer_display_facts).get(decision.rule_id)
        expected_facts = mapping.safe_continuity_customer_display_facts(rule_id=decision.rule_id, raw=raw)
        assert result.get("customer_display_facts") == expected_facts
        assert result.get("customer_display_facts") == validate_luxian_0609_published_customer_display_facts(
            rule_id=decision.rule_id, raw=result.get("customer_display_facts"),
        )
        if decision.rule_id == "LX0609-10-01-01":
            assert sorted(result["customer_evidence"], key=lambda item: item["source_document_id"]) == [
                {"source_type": "handoff_record", "source_document_id": "HANDOFF-1",
                 "record_time": "2026-07-01 07:50:00"},
                {"source_type": "handoff_record", "source_document_id": "HANDOFF-2",
                 "record_time": "2026-07-03 07:50:00"},
                {"source_type": "handover_record", "source_document_id": "HANDOVER-1",
                 "record_time": "2026-07-01 14:00:00"},
            ]


@pytest.mark.parametrize("rule_id,raw", GAP_SHAPES)
def test_sqlite_gap_facts_survive_store_and_corruption_is_rejected(rule_id, raw):
    facts = mapping.safe_continuity_customer_display_facts(rule_id=rule_id, raw=raw)
    assert facts is not None
    item = {"record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P", "rule_id": rule_id,
            "status": "data_gap", "result_status": "data_gap", "display_status": "data_gap",
            "is_compliant": None, "reason_code": "required_field_missing", "customer_display_facts": facts}
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    selected = {"root_job_id": "J", "institute_id": "I", "patient_id": "P", "visit_id": "V",
                "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"}
    try:
        with Session(engine) as db:
            store.replace_for_job(db, job_row={"id": "J", "created_by": "reviewer",
                                           "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1",
                                                                       "rule_set_version": "2026-06-09"})},
                                  items=[item], now=datetime(2026, 9, 24, 10),
                                  projector=lambda value: envelope_item_from_rule_result(value, hmac_key="test-key"),
                                  projection_key="test-key")
            db.commit()
            loaded = store.load_selected(db, **selected)
            assert loaded["items"][0]["customer_display_facts"] == facts
            damaged = deepcopy(loaded)
            damaged["items"][0]["customer_display_facts"]["source_document_refs"] = []
            db.execute(sa.update(table).values(envelope_json=json.dumps(damaged)))
            db.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db, **selected)
    finally:
        engine.dispose()
