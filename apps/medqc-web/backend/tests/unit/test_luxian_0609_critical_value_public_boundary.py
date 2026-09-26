"""原始 052/053 已发布危急值事实：读取校验，不重新投影或计算时效。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609.critical_value_result_mapping as critical_mapping
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.customer_evidence_enrichment import project_selected_document_evidence
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result,
)
from tests.unit.test_luxian_0609_critical_value_result_mapping import _facts
from tests.unit.test_luxian_0609_native_extended_document_execution import _evaluate_selected


RULE_052 = "LX0609-06-04-01"
RULE_053 = "LX0609-06-04-02"
DETAIL_GAP = {"failure_kind": "critical_value_result_detail_missing", "lab_report_count": 1,
              "missing_source": "labtest_item_report"}


@pytest.mark.parametrize("rule_id,raw", [
    (RULE_052, _facts(rule_id=RULE_052, outcome="timely")),
    (RULE_052, _facts(rule_id=RULE_052, outcome="overdue")),
    (RULE_052, _facts(rule_id=RULE_052, outcome="unhandled")),
    (RULE_052, _facts(rule_id=RULE_052, outcome="association_failed")),
    (RULE_053, _facts(rule_id=RULE_053, outcome="handled")),
    (RULE_053, _facts(rule_id=RULE_053, outcome="unhandled")),
    (RULE_053, _facts(rule_id=RULE_053, outcome="association_failed")),
    (RULE_052, DETAIL_GAP), (RULE_053, DETAIL_GAP),
    (RULE_052, {"verification_kind": "critical_value_evaluation_horizon_unavailable",
                "issue": "authoritative_time_missing"}),
    (RULE_052, {"verification_kind": "critical_value_evaluation_horizon_unavailable",
                "issue": "authoritative_time_conflict"}),
])
def test_all_base_published_shapes_preserve_values_and_reject_extra_keys(rule_id, raw):
    published = critical_mapping.safe_critical_value_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=published) == published
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule_id, raw={**published, "source_document_ids": ["SYNTHETIC-INTERNAL"]},
        )


@pytest.mark.parametrize("key,value", [
    ("evaluation_time", "2026-06-01 12:00:00"),
    ("evaluation_date", "2026-06-01"),
])
def test_052_unmatured_window_time_and_date_published_shapes(key, value):
    raw = {**_facts(rule_id=RULE_052, outcome="window_not_mature"),
           "evaluation_window_mature": False, "deadline_times": ["2026-06-01 14:00:00"], key: value}
    published = critical_mapping.safe_critical_value_customer_display_facts(rule_id=RULE_052, raw=raw)
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(rule_id=RULE_052, raw=published) == published


@pytest.mark.parametrize("report,deadline,key,evaluation,valid", [
    ("2026-06-01 08:00:00", "2026-06-01 14:00:00", "evaluation_time", "2026-06-01 13:59:59", True),
    ("2026-06-01 08:00:00", "2026-06-01 14:00:00", "evaluation_time", "2026-06-01 14:00:00", False),
    ("2026-06-01 08:00:00", "2026-06-01 14:00:00", "evaluation_time", "2026-06-01 15:00:00", False),
    ("2026-06-01 08:00:00", "2026-06-01 15:00:00", "evaluation_time", "2026-06-01 12:00:00", False),
    ("2026-06-01 08:00:00+08:00", "2026-06-01 06:00:00+00:00", "evaluation_time", "2026-06-01 05:00:00+00:00", True),
    ("2026-06-01 08:00:00+08:00", "2026-06-01 14:00:00", "evaluation_time", "2026-06-01 12:00:00+08:00", False),
    ("2026-06-01 08:00:00", "not-a-time", "evaluation_time", "2026-06-01 12:00:00", False),
    ("2026-06-01 08:00:00", "2026-06-01 14:00:00", "evaluation_date", "2026-06-01", True),
    ("2026-06-01 08:00:00", "2026-06-01 14:00:00", "evaluation_date", "2026-06-02", False),
    ("2026-06-01 08:00:00", "2026-06-01 14:00:00", "evaluation_date", "20260601", False),
])
def test_052_window_public_consistency_matches_existing_publisher(report, deadline, key, evaluation, valid):
    raw = _facts(rule_id=RULE_052, outcome="window_not_mature")
    raw["event_results"][0]["report_time"] = report
    raw.update(evaluation_window_mature=False, deadline_times=[deadline], **{key: evaluation})
    published = critical_mapping.safe_critical_value_customer_display_facts(rule_id=RULE_052, raw=raw)
    assert (published is not None) is valid
    if valid:
        assert validate_luxian_0609_published_customer_display_facts(rule_id=RULE_052, raw=published) == published
    else:
        with pytest.raises(ValueError, match="解释合同不完整"):
            validate_luxian_0609_published_customer_display_facts(rule_id=RULE_052, raw=raw)


@pytest.mark.parametrize("rule_id", [RULE_052, RULE_053])
def test_absent_facts_keep_existing_none_semantics(rule_id):
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=None) is None


@pytest.mark.parametrize("field,value", [
    ("actual_interval_hours", [1.23456]),
    ("actual_interval_hours", [float("nan")]),
    ("actual_interval_hours", [True]),
    ("threshold_hours", True),
    ("event_results", [{**_facts(rule_id=RULE_052, outcome="timely")["event_results"][0],
                        "interval_hours": 1.23456}]),
    ("event_results", [{**_facts(rule_id=RULE_052, outcome="timely")["event_results"][0],
                        "source_document_id": "SYNTHETIC-INTERNAL"}]),
])
def test_052_invalid_published_numbers_and_nested_fields_fail_closed(field, value):
    raw = critical_mapping.safe_critical_value_customer_display_facts(
        rule_id=RULE_052, raw=_facts(rule_id=RULE_052, outcome="timely"),
    )
    assert raw is not None
    damaged = {**raw, field: value}
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE_052, raw=damaged)


def test_052_original_internal_projection_rounds_but_public_read_rejects_unrounded():
    raw = _facts(rule_id=RULE_052, outcome="timely")
    raw["actual_interval_hours"] = [1.23456]
    raw["event_results"][0]["interval_hours"] = 1.23456
    published = critical_mapping.safe_critical_value_customer_display_facts(rule_id=RULE_052, raw=raw)
    assert published is not None
    assert published["actual_interval_hours"] == [1.23]
    assert published["event_results"][0]["interval_hours"] == 1.23
    assert validate_luxian_0609_published_customer_display_facts(rule_id=RULE_052, raw=published) == published
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE_052, raw=raw)


@pytest.mark.parametrize("rule_id,outcome", [(RULE_052, "timely"), (RULE_053, "handled")])
def test_public_read_never_calls_internal_projection(monkeypatch, rule_id, outcome):
    published = critical_mapping.safe_critical_value_customer_display_facts(
        rule_id=rule_id, raw=_facts(rule_id=rule_id, outcome=outcome),
    )
    assert published is not None

    def forbidden(*, rule_id, raw):
        raise AssertionError("published read must not use internal projection")

    monkeypatch.setattr(critical_mapping, "safe_critical_value_customer_display_facts", forbidden)
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=published) == published


def test_053_rejects_invalid_nested_event_shape():
    published = critical_mapping.safe_critical_value_customer_display_facts(
        rule_id=RULE_053, raw=_facts(rule_id=RULE_053, outcome="handled"),
    )
    assert published is not None
    damaged = deepcopy(published)
    damaged["event_results"][0]["critical_flags"] = [True]
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE_053, raw=damaged)


def test_052_actual_intervals_retain_original_unbounded_length_and_negative_values():
    raw = _facts(rule_id=RULE_052, outcome="timely")
    raw["actual_interval_hours"] = [-1.23] * 101
    published = critical_mapping.safe_critical_value_customer_display_facts(rule_id=RULE_052, raw=raw)
    assert published is not None and len(published["actual_interval_hours"]) == 101
    assert validate_luxian_0609_published_customer_display_facts(rule_id=RULE_052, raw=published) == published


def test_052_initial_finalizer_projection_is_called_once(monkeypatch):
    original = critical_mapping.safe_critical_value_customer_display_facts
    calls = []

    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(critical_mapping, "safe_critical_value_customer_display_facts", counted)
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id=RULE_052, snapshot_hash="a" * 64,
        applicability=ApplicabilityState.APPLICABLE, evidence_state=EvidenceState.DATA_GAP,
        qc_direction=QcDirection.UNKNOWN, reason_code="required_field_missing",
        fact_refs=(), evaluator_version="critical-value-v1",
    ))
    result = finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=DETAIL_GAP,
        evidence_snapshot=None, evidence_materials=None,
    )
    assert calls == [RULE_052]
    assert (result["status"], result["reason_code"]) == ("data_gap", "required_field_missing")
    assert result["customer_display_facts"] == DETAIL_GAP


def test_canonical_store_052_reads_same_facts_and_rejects_nested_corruption():
    facts = critical_mapping.safe_critical_value_customer_display_facts(
        rule_id=RULE_052, raw=_facts(rule_id=RULE_052, outcome="timely"),
    )
    assert facts is not None
    item = {"record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P", "rule_id": RULE_052,
            "status": "compliant", "result_status": "compliant", "display_status": "compliant",
            "is_compliant": True, "reason_code": "requirement_satisfied", "customer_display_facts": facts}
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
                                  projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                                  projection_key="test-key")
            db.commit()
            loaded = store.load_selected(db, **selected, projection_key="test-key")
            assert loaded["items"][0]["customer_display_facts"] == facts
            damaged = deepcopy(loaded)
            damaged["items"][0]["customer_display_facts"]["event_results"][0]["interval_hours"] = 2.3456
            db.execute(sa.update(table).values(envelope_json=json.dumps(damaged)))
            db.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db, **selected, projection_key="test-key")
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_fixed_052_053_native_binding_aggregate_keeps_facts_evidence_and_usage():
    snapshot, materials, execution, reduced = await _evaluate_selected(
        (RULE_052, RULE_053),
        {"labtest_item_report": ({"item_name": "血钾", "result_flag": "PH",
                                  "report_time": "2026-06-01 14:00:00"},),
         "evaluation_context.horizon": ({"horizon_datetime": "2026-06-01 19:00:00",
                                         "horizon_date": "2026-06-01", "basis": "evaluation_as_of"},)},
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": RULE_052}, {"rule_id": RULE_053}],
        execution_results=execution.results, reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        audit_context={"evidence_snapshot": snapshot, "evidence_materials": materials},
    )
    by_rule = {item["rule_id"]: item for item in canonical}
    assert execution.llm_call_count == execution.total_tokens == 0
    assert [(item.final_state.value, item.reason_code) for item in reduced] == [
        ("not_applicable", "evaluation_window_not_mature"),
        ("non_compliant", "required_document_missing"),
    ]
    for decision in reduced:
        result = by_rule[decision.rule_id]
        assert (result["status"], result["reason_code"]) == (decision.final_state.value, decision.reason_code)
        assert result["customer_display_facts"] == dict(execution.customer_display_facts)[decision.rule_id]
        assert result["customer_display_facts"] == validate_luxian_0609_published_customer_display_facts(
            rule_id=decision.rule_id, raw=result["customer_display_facts"],
        )
        assert result.get("customer_evidence", []) == project_selected_document_evidence(
            decision=decision, evidence_snapshot=snapshot, evidence_materials=materials,
        )
