"""020–023 会诊族公开事实只校验已发布 JSON。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609.consultation_customer_projection as consultation_projection
from app.services.luxian_0609 import native_consultation_episode_execution as episode
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_reduced_customer_result,
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState, EvidenceState, QcDirection, RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result,
)
from tests.unit.test_luxian_0609_consultation_family_architecture_freeze import (
    RecordingClient, _run_formal_chain, _session,
)
from tests.unit.test_luxian_0609_native_consultation_episode_execution import (
    _SequentialClient, _episode, _execution, _payload, _rows, _window_session,
)


RULE_020 = "LX0609-03-01-01"
RULE_021 = "LX0609-03-01-02"
RULE_022 = "LX0609-03-01-03"
RULE_023 = "LX0609-03-01-04"
EXECUTION_BASE = {"completed_opinion_episode_count": 1, "recommendation_count": 1,
                  "specific_execution_count": 1, "generic_execution_count": 0,
                  "missing_execution_count": 0, "source_document_ids": ["CONSULT-1"]}
EVIDENCE = {"episode_index": 1, "recommendation_index": 1, "execution_state": "specific",
            "opinion_refs": [{"source_type": "consultation_record", "source_document_id": "CONSULT-1"}],
            "execution_refs": [{"source_type": "daily_course_record", "source_document_id": "COURSE-1"}]}


@pytest.mark.parametrize("rule_id,raw", [
    (RULE_020, {"verification_kind": "consultation_execution_relation_check", **EXECUTION_BASE,
                "relation_state": "all_linked", "recommendation_results": [
                    {"episode_index": 1, "recommendation_index": 1, "action_type": "test", "execution_state": "specific"}],
                "recommendation_evidence": [EVIDENCE]}),
    (RULE_020, {"verification_kind": "consultation_execution_relation_check",
                **{**EXECUTION_BASE, "completed_opinion_episode_count": 0, "recommendation_count": 0,
                   "specific_execution_count": 0, "source_document_ids": []},
                "relation_state": "not_triggered", "recommendation_results": []}),
    (RULE_023, {"verification_kind": "consultation_execution_quality_check", **EXECUTION_BASE,
                "relation_state": "specific_execution", "recommendation_evidence": [EVIDENCE]}),
    (RULE_023, {"verification_kind": "consultation_execution_quality_check",
                **{**EXECUTION_BASE, "completed_opinion_episode_count": 0, "recommendation_count": 0,
                   "specific_execution_count": 0, "source_document_ids": []},
                "relation_state": "not_triggered", "recommendation_evidence": []}),
    (RULE_021, {"verification_kind": "consultation_application_quality_check", "episode_count": 1,
                "document_count": 1, "semantic_state": "clear",
                "checked_requirement": "说明具体临床问题、会诊理由或明确会诊目的",
                "source_document_ids": ["CONSULT-1"], "episode_results": [
                    {"episode_index": 1, "semantic_state": "clear", "source_document_id": "CONSULT-1",
                     "record_time": "2026-07-20 01:00:00", "document_title": "会诊申请单"}]}),
    (RULE_022, {"verification_kind": "consultation_opinion_quality_check", "episode_count": 0,
                "document_count": 0, "semantic_state": "absent",
                "checked_requirement": "给出针对当前病情的明确诊疗意见",
                "source_document_ids": [], "episode_results": []}),
    (RULE_022, {"verification_kind": "consultation_opinion_quality_check", "episode_count": 1,
                "document_count": 1, "semantic_state": "clear",
                "checked_requirement": "给出针对当前病情的明确诊疗意见",
                "source_document_ids": ["CONSULT-1"]}),
    (RULE_020, {"consultation_assessment": "明确", "execution_record_state": "已发现明确执行记录",
                "execution_candidate_count": 1, "source_document_ids": ["CONSULT-1"]}),
    (RULE_021, {"consultation_assessment": "不符合要求", "source_document_ids": ["CONSULT-1"]}),
    (RULE_022, {"consultation_assessment": "明确", "source_document_ids": ["CONSULT-1"]}),
    (RULE_023, {"failure_kind": "consultation_execution_too_generic",
                "observed_expression": "仅笼统记录已按会诊意见执行",
                "missing_details": ["具体执行措施", "执行结果或后续安排"],
                "source_document_ids": ["CONSULT-1"]}),
])
def test_published_shapes_preserve_values_and_reject_internal_ids(rule_id, raw):
    published = consultation_projection.safe_consultation_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    assert validate_luxian_0609_published_customer_display_facts(rule_id=rule_id, raw=published) == published
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=rule_id, raw={**published, "source_document_ids": ["SYNTHETIC-INTERNAL"]},
        )


@pytest.mark.parametrize("bad_key", ["opinion_refs", "execution_refs"])
def test_023_public_nested_internal_refs_are_rejected(bad_key):
    internal = {"verification_kind": "consultation_execution_quality_check", **EXECUTION_BASE,
                "relation_state": "specific_execution", "recommendation_evidence": [EVIDENCE]}
    published = consultation_projection.safe_consultation_customer_display_facts(rule_id=RULE_023, raw=internal)
    assert published is not None
    damaged = deepcopy(published)
    damaged["recommendation_evidence"][0][bad_key] = EVIDENCE[bad_key]
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE_023, raw=damaged)


def test_023_public_ref_value_and_unknown_field_are_rejected():
    internal = {"verification_kind": "consultation_execution_quality_check", **EXECUTION_BASE,
                "relation_state": "specific_execution", "recommendation_evidence": [EVIDENCE]}
    published = consultation_projection.safe_consultation_customer_display_facts(rule_id=RULE_023, raw=internal)
    assert published is not None
    damaged = deepcopy(published)
    damaged["recommendation_evidence"][0]["opinion_evidence"][0]["source_ref"] = "CONSULT-1"
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(rule_id=RULE_023, raw=damaged)
    with pytest.raises(ValueError, match="解释合同不完整"):
        validate_luxian_0609_published_customer_display_facts(
            rule_id=RULE_023, raw={**published, "source_document_refs": []},
        )


def test_canonical_store_023_read_keeps_public_facts_and_rejects_nested_pollution():
    facts = consultation_projection.safe_consultation_customer_display_facts(
        rule_id=RULE_023, raw={"verification_kind": "consultation_execution_quality_check", **EXECUTION_BASE,
                              "relation_state": "specific_execution", "recommendation_evidence": [EVIDENCE]},
    )
    assert facts is not None
    item = {"record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P", "rule_id": RULE_023,
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
            loaded = store.load_selected(db, **selected)
            assert loaded["items"][0]["customer_display_facts"] == facts
            damaged = deepcopy(loaded)
            damaged["items"][0]["customer_display_facts"]["recommendation_evidence"][0]["opinion_refs"] = []
            db.execute(sa.update(table).values(envelope_json=json.dumps(damaged)))
            db.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db, **selected)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_paused_020_022_remain_not_executed_without_model(monkeypatch):
    calls = []
    original = consultation_projection.safe_consultation_customer_display_facts

    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(consultation_projection, "safe_consultation_customer_display_facts", counted)
    selected = (RULE_020, RULE_021, RULE_022)
    client = RecordingClient(RuntimeError("paused rules must not call the model"))
    context, delivered = await _run_formal_chain(
        monkeypatch, selected_rule_ids=selected,
        session=_session(selected_rule_ids=selected), client=client,
    )
    assert [(item["rule_id"], item["status"]) for item in delivered["results"][:3]] == [
        (RULE_020, "not_executed"), (RULE_021, "not_executed"), (RULE_022, "not_executed"),
    ]
    assert context.native_llm_call_count == 0 and client.prompts == [] and calls == []


def test_023_initial_finalizer_projection_is_called_once(monkeypatch):
    original = consultation_projection.safe_consultation_customer_display_facts
    calls = []

    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(consultation_projection, "safe_consultation_customer_display_facts", counted)
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id=RULE_023, snapshot_hash="a" * 64,
        applicability=ApplicabilityState.NOT_APPLICABLE,
        evidence_state=EvidenceState.SUFFICIENT, qc_direction=QcDirection.UNKNOWN,
        reason_code="trigger_absent_complete", fact_refs=(), evaluator_version="consultation-v1",
    ))
    raw = {"verification_kind": "consultation_execution_quality_check",
           "completed_opinion_episode_count": 0, "recommendation_count": 0,
           "specific_execution_count": 0, "generic_execution_count": 0,
           "missing_execution_count": 0, "relation_state": "not_triggered",
           "source_document_ids": ["SYNTHETIC-INTERNAL"], "recommendation_evidence": []}
    result = finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=raw,
        evidence_snapshot=None, evidence_materials=None,
    )
    assert calls == [RULE_023]
    assert result["status"] == "not_applicable"
    assert result["reason_code"] == "trigger_absent_complete"
    published = original(rule_id=RULE_023, raw=raw)
    assert result["customer_display_facts"] == published
    published_result = finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=published,
        evidence_snapshot=None, evidence_materials=None,
    )
    assert calls == [RULE_023]  # 已发布输入只校验，不再调用内部投影。
    for key in ("status", "reason_code", "customer_display_facts", "conclusion", "suggestion"):
        assert published_result.get(key) == result.get(key)


@pytest.mark.asyncio
async def test_023_fixed_native_binding_aggregate_keeps_decision_evidence_and_usage(monkeypatch):
    original = consultation_projection.safe_consultation_customer_display_facts
    projection_calls = []

    def counted(*, rule_id, raw):
        projection_calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(consultation_projection, "safe_consultation_customer_display_facts", counted)
    monkeypatch.setattr(episode, "safe_consultation_customer_display_facts", counted)
    consultation_rows = _rows("申请与明确会诊意见", day=2)
    consultation_rows[0]["document_id"] = "CONSULT-OPINION-1"
    course_rows = _rows("已具体落实会诊意见", day=3)
    course_rows[0]["document_id"] = "COURSE-EXECUTION-1"
    session = _window_session(rows_by_source={
        "consultation_record": tuple(consultation_rows),
        "daily_course_record": tuple(course_rows),
    })
    client = _SequentialClient(
        _payload(episodes=[_episode("consultation_record-1", ["consultation_record-1"])]),
        _execution({"episode_ref": "consultation_record-1", "execution_state": "linked_specific",
                    "execution_refs": ["daily_course_record-1"], "confidence": "high"}),
    )
    native = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=(RULE_023,), decision_rule_ids=(RULE_023,),
        institute_id="I", patient_id="P", visit_id="V", source_schema=None,
        llm_client=client, evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    assert projection_calls == [RULE_023]
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=native.decisions, expected_rule_ids=(RULE_023,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    canonical = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": RULE_023}], execution_results=native.results,
        reduced_decisions=reduced, customer_display_facts=native.customer_display_facts,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )[0]
    assert projection_calls == [RULE_023]
    assert native.llm_call_count == 2 and native.total_tokens == 32
    assert (reduced[0].final_state.value, reduced[0].reason_code) == ("compliant", "requirement_satisfied")
    assert (canonical["status"], canonical["reason_code"]) == ("compliant", "requirement_satisfied")
    assert canonical["customer_display_facts"] == consultation_projection.safe_consultation_customer_display_facts(
        rule_id=RULE_023, raw=dict(native.customer_display_facts)[RULE_023],
    )
    assert {(item["source_type"], item["source_document_id"]) for item in canonical["customer_evidence"]} == {
        ("consultation_record", "CONSULT-OPINION-1"),
        ("daily_course_record", "COURSE-EXECUTION-1"),
    }
