"""不适用结果只保留安全来源回执，不伪造事件文书。"""

import json
from dataclasses import replace

import pytest

from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
from app.services.luxian_0609.evidence_material import Luxian0609EvidenceMaterialStore, build_material_document_refs, build_material_snapshot_ref
from app.services.luxian_0609.evidence_snapshot import EVIDENCE_SNAPSHOT_SCHEMA_VERSION, Luxian0609EvidenceSnapshot, SourceCompleteness, SourceObservation
from app.services.luxian_0609.source_evidence_reader import SnapshotSourceRows
from app.services.luxian_0609.source_manifest import QueryStatus
from app.services.luxian_0609.source_registry import SOURCE_REGISTRY_VERSION

RULE = "LX0609-03-01-02"
SOURCE = "consultation_record"
VERSION = "snapshot-provider-consultation_record-v1"


def _case(state="empty", completeness="complete", scope=None):
    rows = ({"record_content": "合成非会诊记录", "document_id": "SYNTHETIC-ONLY"},) if state == "available" else ()
    material = SnapshotSourceRows(source_key=SOURCE, rows=rows, truncated=completeness == "truncated", limit_rows=10, material_scope=scope)
    doc_refs = build_material_document_refs(SOURCE, rows)
    ref = build_material_snapshot_ref(source_key=SOURCE, query_version=VERSION, query_state=QueryStatus(state), completeness=SourceCompleteness(completeness), document_refs=doc_refs, material_scope=scope)
    observation = SourceObservation.create(source_key=SOURCE, query_state=state, completeness=completeness, record_count=len(rows) if state in {"empty", "available"} else None, query_version=VERSION, snapshot_ref=ref, error_code="SOURCE_QUERY_FAILED" if state == "error" else "", reason_code="SOURCE_READER_NOT_REGISTERED" if state == "unavailable" else "")
    snapshot = Luxian0609EvidenceSnapshot.create(institute_id="SYN-I", patient_id="SYN-P", visit_id="SYN-V", snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION, source_registry_version=SOURCE_REGISTRY_VERSION, observations=(observation,), facts=(), document_refs=doc_refs, created_at="2026-11-15T00:00:00Z")
    store = Luxian0609EvidenceMaterialStore.create(snapshot=snapshot, sources={SOURCE: material} if state in {"empty", "available"} else {})
    decision = RuleDecision(rule_id=RULE, snapshot_hash=snapshot.snapshot_hash, applicability=ApplicabilityState.NOT_APPLICABLE, evidence_state=EvidenceState.SUFFICIENT, qc_direction=QcDirection.UNKNOWN, reason_code="trigger_absent_complete", fact_refs=(ref.removeprefix("sha256:"),), evaluator_version="receipt-test-v1")
    return snapshot, store, decision


def _reduce(snapshot, store, decision):
    return bind_and_reduce_luxian_0609_rule_decisions(decisions=(decision,), expected_rule_ids=(decision.rule_id,), snapshot=snapshot, evidence_materials=store)[0]


def test_complete_empty_source_has_serializable_receipt_without_fake_document():
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    snapshot, store, decision = _case()
    reduced = _reduce(snapshot, store, decision)
    result = finalize_luxian_0609_reduced_customer_result(decision=reduced, raw_customer_display_facts=None, evidence_snapshot=snapshot, evidence_materials=store)
    assert result["status"] == "not_applicable"
    assert not result.get("customer_evidence")
    receipt = json.loads(json.dumps(result))["applicability_receipt"]
    assert receipt["snapshot_hash"] == snapshot.snapshot_hash
    assert receipt["decision_fingerprint"] == decision.fingerprint()
    assert receipt["fact_refs"] == list(decision.fact_refs)
    assert receipt["source_checks"][0]["record_count"] == 0
    assert receipt["source_checks"][0]["depended_on"] is True
    assert receipt["event_basis"] == []


@pytest.mark.parametrize("state,completeness,scope,status,reason", [
    ("unavailable", "unproven", None, "data_gap", "source_unavailable"),
    ("available", "truncated", None, "data_gap", "source_truncated"),
    ("error", "unproven", None, "technical_error", "source_query_error"),
    ("empty", "complete", {"status": "empty_unconfirmed", "coverage": "unknown", "can_judge_clinical_absence": False}, "data_gap", "source_readiness_unproven"),
    ("empty", "complete", {"status": "available", "coverage": "complete", "can_judge_clinical_absence": True}, "not_applicable", "trigger_absent_complete"),
])
def test_no_trigger_requires_actual_source_completeness(state, completeness, scope, status, reason):
    reduced = _reduce(*_case(state, completeness, scope))
    assert (reduced.final_state.value, reduced.reason_code) == (status, reason)


def test_unknown_dependency_is_gap_instead_of_asserting_absence():
    snapshot, store, decision = _case()
    reduced = _reduce(snapshot, store, replace(decision, fact_refs=()))
    assert reduced.final_state.value == "data_gap"


def test_affirmative_applicability_survives_unproven_absence_and_records_basis():
    from app.services import case_material_snapshot
    from app.services.automatic_material_scope import describe_source
    from app.services.luxian_0609.applicability_receipt import build_applicability_receipt, validate_applicability_receipt

    scope = describe_source((), ({"document_id": "SYNTHETIC-ONLY"},))
    snapshot, store, decision = _case("available", scope=scope)
    state = {"automatic_material": {"sources": {SOURCE: scope}}}
    with case_material_snapshot.activate(state):
        # 同样的已读来源仍不能按其覆盖未知来证明事件不存在。
        assert _reduce(snapshot, store, decision).final_state.value == "data_gap"
        affirmed = replace(decision, affirmative_applicability=True)
        assert _reduce(snapshot, store, affirmed).final_state.value == "data_gap"
        reduced = _reduce(snapshot, store, replace(affirmed, fact_refs=snapshot.document_refs))
    assert reduced.final_state.value == "not_applicable"
    receipt = build_applicability_receipt(decision=reduced, snapshot=snapshot, materials=store)
    assert receipt["affirmative_applicability"] is True
    assert receipt["source_checks"][0]["scope"]["can_judge_clinical_absence"] is False
    with pytest.raises(ValueError):
        validate_applicability_receipt({**receipt, "source_checks": [{
            **receipt["source_checks"][0], "query_state": "empty", "record_count": 0,
        }]})
    with pytest.raises(ValueError):
        validate_applicability_receipt({**receipt, "fact_refs": list(decision.fact_refs)})


@pytest.mark.parametrize("state,completeness,reason", [
    ("empty", "complete", "source_readiness_unproven"),
    ("available", "truncated", "source_truncated"),
    ("error", "unproven", "source_query_error"),
])
def test_affirmative_applicability_requires_readable_complete_nonempty_evidence(state, completeness, reason):
    snapshot, store, decision = _case(state, completeness)
    result = _reduce(snapshot, store, replace(decision, affirmative_applicability=True))
    assert result.reason_code == reason
    assert result.final_state.value != "not_applicable"


def test_precise_time_gap_remains_a_gap_with_original_reason_despite_unknown_coverage():
    from app.services import case_material_snapshot
    from app.services.automatic_material_scope import describe_source

    scope = describe_source((), ())
    snapshot, store, decision = _case("empty", scope=scope)
    decision = replace(
        decision, applicability=ApplicabilityState.UNKNOWN, evidence_state=EvidenceState.DATA_GAP,
        reason_code="authoritative_time_missing",
    )
    with case_material_snapshot.activate({"automatic_material": {"sources": {SOURCE: scope}}}):
        result = _reduce(snapshot, store, decision)
    assert (result.final_state.value, result.reason_code) == ("data_gap", "authoritative_time_missing")


@pytest.mark.parametrize("state, completeness, scope_status, expected", [
    ("unavailable", "unproven", "table_missing", ("data_gap", "source_unavailable")),
    ("available", "truncated", "available", ("data_gap", "source_truncated")),
    ("error", "unproven", "empty_unconfirmed", ("technical_error", "source_query_error")),
])
def test_specific_gap_does_not_mask_actual_consumed_source_failure(state, completeness, scope_status, expected):
    from app.services import case_material_snapshot
    scope = {"status": scope_status, "can_judge_clinical_absence": False}
    snapshot, store, decision = _case(state, completeness)
    decision = replace(
        decision, applicability=ApplicabilityState.UNKNOWN, evidence_state=EvidenceState.DATA_GAP,
        reason_code="authoritative_time_missing",
    )
    with case_material_snapshot.activate({"automatic_material": {"sources": {SOURCE: scope}}}):
        result = _reduce(snapshot, store, decision)
    assert (result.final_state.value, result.reason_code) == expected


def test_receipt_validator_rejects_extra_text_and_invalid_material_hash():
    from app.services.luxian_0609.applicability_receipt import build_applicability_receipt, validate_applicability_receipt
    snapshot, store, decision = _case()
    receipt = build_applicability_receipt(decision=_reduce(snapshot, store, decision), snapshot=snapshot, materials=store)
    for unsafe in ({**receipt, "raw_error": "secret"}, {**receipt, "material_fingerprint": "raw-id"}, {**receipt, "source_checks": [{**receipt["source_checks"][0], "record_content": "secret"}]}):
        with pytest.raises(ValueError):
            validate_applicability_receipt(unsafe)
    assert validate_applicability_receipt({**receipt, "material_fingerprint": "f" * 64})["material_fingerprint"] == "f" * 64


def _extend_snapshot(snapshot, *, observations=None, facts=()):
    return Luxian0609EvidenceSnapshot.create(institute_id="SYN-I", patient_id="SYN-P", visit_id="SYN-V", snapshot_schema_version=EVIDENCE_SNAPSHOT_SCHEMA_VERSION, source_registry_version=SOURCE_REGISTRY_VERSION, observations=observations or snapshot.observations, facts=facts, document_refs=snapshot.document_refs, created_at=snapshot.created_at)


def test_unused_missing_alternative_is_recorded_but_does_not_block_complete_branch():
    from app.services.luxian_0609.applicability_receipt import build_applicability_receipt
    snapshot, store, decision = _case()
    missing = SourceObservation.create(source_key="daily_course_record", query_state="unavailable", completeness="unproven", record_count=None, query_version="snapshot-provider-daily_course_record-v1", snapshot_ref="sha256:" + "d" * 64, reason_code="SOURCE_READER_NOT_REGISTERED")
    extended = _extend_snapshot(snapshot, observations=(*snapshot.observations, missing))
    store = Luxian0609EvidenceMaterialStore.create(snapshot=extended, sources=store.diagnostic_sources(snapshot=snapshot))
    decision = replace(decision, rule_id="LX0609-03-01-01", snapshot_hash=extended.snapshot_hash)
    reduced = _reduce(extended, store, decision)
    assert reduced.final_state.value == "not_applicable"
    receipt = build_applicability_receipt(decision=reduced, snapshot=extended, materials=store)
    checks = {item["source_key"]: item for item in receipt["source_checks"]}
    assert checks["daily_course_record"]["query_state"] == "unavailable"
    assert checks["daily_course_record"]["depended_on"] is False


@pytest.mark.parametrize("assertion", ["affirmed", "negated"])
def test_fact_event_basis_preserves_only_safe_references_and_enums(assertion):
    from app.services.luxian_0609.applicability_receipt import build_applicability_receipt
    from app.services.luxian_0609.fact_schema import FACT_SCHEMA_VERSION, FactV2
    snapshot, store, decision = _case("available")
    fact = FactV2.create(visit_ref=snapshot.visit_ref, family="consultation", fact_type="consultation_event", normalized_value={"present": assertion == "affirmed"}, trigger_scope="prior_history", current_visit_relevance="not_relevant", assertion=assertion, assertion_context="past_history", event_status="performed", source_key=SOURCE, source_document_id="", source_document_type=SOURCE, record_time=None, submit_time=None, update_time=None, quote="", redaction_terms=(), confidence=1.0, extractor="deterministic", extractor_version="receipt-test-v1", fact_schema_version=FACT_SCHEMA_VERSION, source_snapshot_hash=snapshot.observations[0].snapshot_ref.removeprefix("sha256:"), created_at=snapshot.created_at, extensions={}, known_upstream_fact_ids=())
    extended = _extend_snapshot(snapshot, facts=(fact,))
    store = Luxian0609EvidenceMaterialStore.create(snapshot=extended, sources=store.diagnostic_sources(snapshot=snapshot))
    decision = replace(decision, snapshot_hash=extended.snapshot_hash, fact_refs=(fact.fact_id,))
    receipt = build_applicability_receipt(decision=_reduce(extended, store, decision), snapshot=extended, materials=store)
    assert receipt["event_basis"][0]["assertion"] == assertion
    assert receipt["event_basis"][0]["fact_ref"] == fact.fact_id
    assert "SYNTHETIC-ONLY" not in json.dumps(receipt)


def test_historical_fact_relevant_to_current_stay_cannot_prove_affirmative_applicability():
    from app.services.luxian_0609.fact_schema import FACT_SCHEMA_VERSION, FactV2

    snapshot, store, decision = _case("available")
    fact = FactV2.create(
        visit_ref=snapshot.visit_ref, family="consultation", fact_type="consultation_event",
        normalized_value={"present": True}, trigger_scope="prior_history",
        current_visit_relevance="relevant", assertion="affirmed", assertion_context="past_history",
        event_status="performed", source_key=SOURCE, source_document_id="", source_document_type=SOURCE,
        record_time=None, submit_time=None, update_time=None, quote="", redaction_terms=(), confidence=1.0,
        extractor="deterministic", extractor_version="receipt-test-v1", fact_schema_version=FACT_SCHEMA_VERSION,
        source_snapshot_hash=snapshot.observations[0].snapshot_ref.removeprefix("sha256:"),
        created_at=snapshot.created_at, extensions={}, known_upstream_fact_ids=(),
    )
    extended = _extend_snapshot(snapshot, facts=(fact,))
    store = Luxian0609EvidenceMaterialStore.create(snapshot=extended, sources=store.diagnostic_sources(snapshot=snapshot))
    decision = replace(
        decision, snapshot_hash=extended.snapshot_hash, fact_refs=(fact.fact_id,),
        affirmative_applicability=True,
    )
    assert _reduce(extended, store, decision).final_state.value == "data_gap"


@pytest.mark.asyncio
@pytest.mark.parametrize("rule", [RULE, "LX0609-03-01-05"])
async def test_real_empty_consultation_branch_retains_checked_observation_without_model(rule):
    from app.services.luxian_0609.native_consultation_episode_execution import execute_luxian_0609_native_consultation_episode_rules
    snapshot, store, _ = _case()
    execution = await execute_luxian_0609_native_consultation_episode_rules(rule_ids=(rule,), institute_id="SYN-I", patient_id="SYN-P", visit_id="SYN-V", source_schema=None, llm_client=None, evidence_snapshot=snapshot, evidence_materials=store, decision_rule_ids=(rule,))
    assert execution.decisions[0].fact_refs == (snapshot.observations[0].snapshot_ref.removeprefix("sha256:"),)
    assert _reduce(snapshot, store, execution.decisions[0]).final_state.value == "not_applicable"


def test_nested_material_scope_is_projected_without_raw_manifest():
    from app.services.luxian_0609.applicability_receipt import build_applicability_receipt
    snapshot, store, decision = _case(scope={"status": "available", "coverage": {"secret": "raw"}, "can_judge_clinical_absence": True})
    receipt = build_applicability_receipt(decision=_reduce(snapshot, store, decision), snapshot=snapshot, materials=store)
    assert receipt["source_checks"][0]["scope"]["coverage"] == "unknown"
    assert "secret" not in json.dumps(receipt)


@pytest.mark.asyncio
async def test_disposition_unbound_document_is_controlled_technical_failure(monkeypatch):
    from app.services.luxian_0609 import native_consultation_episode_execution as episode
    from app.services.luxian_0609.consultation_disposition_record import DispositionRecordOutcome
    snapshot, store, _ = _case("available")
    # 模拟未携带材料绑定的异常输入，不代表正常Store.create能生成此形状。
    monkeypatch.setattr(episode, "_read_rows", lambda **_: [{"document_id": "SYNTHETIC-ONLY", "record_content": "合成非适用"}])
    async def checked(**_):
        return DispositionRecordOutcome("not_applicable", "trigger_absent_complete")
    monkeypatch.setattr(episode, "check_disposition_record", checked)
    execution = await episode.execute_luxian_0609_native_consultation_episode_rules(
        rule_ids=("LX0609-03-01-05",), institute_id="SYN-I", patient_id="SYN-P", visit_id="SYN-V",
        source_schema=None, llm_client=None, evidence_snapshot=snapshot, evidence_materials=store,
        decision_rule_ids=("LX0609-03-01-05",),
    )
    decision = _reduce(snapshot, store, execution.decisions[0])
    assert decision.final_state.value == "technical_error" and decision.reason_code == "snapshot_mismatch"
    assert decision.fact_refs == ()


@pytest.mark.parametrize("change", [{"depended_on": False}, {"record_count": 2}, {"query_state": "error"}, {"completeness": "unproven"}, {"query_version": "unregistered-v1"}])
def test_receipt_validator_rejects_unproven_or_contradictory_absence(change):
    from app.services.luxian_0609.applicability_receipt import build_applicability_receipt, validate_applicability_receipt
    snapshot, store, decision = _case()
    receipt = build_applicability_receipt(decision=_reduce(snapshot, store, decision), snapshot=snapshot, materials=store)
    receipt["source_checks"][0].update(change)
    with pytest.raises(ValueError):
        validate_applicability_receipt(receipt)
