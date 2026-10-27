"""主协调验证死亡/出院公开合同经正式 Canonical 保存读取，不重投影。"""
from copy import deepcopy
from datetime import datetime
import importlib
import json

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
from app.services.luxian_0609.canonical_result_finalizer import validate_luxian_0609_published_customer_display_facts
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore, envelope_item_from_rule_result

CASES = [
    ("LX0609-04-02-09", "death_document", {"verification_kind": "death_record_timeliness_check", "death_time": "2026-09-01 01:00:00", "record_time": "2026-09-02 01:00:01", "threshold_hours": 24, "elapsed_seconds": 86401.0}),
    ("LX0609-09-02-01", "death_document", {"verification_kind": "death_discussion_timeliness_check", "death_time": "2026-09-01 01:00:00", "discussion_time": "2026-09-01 02:00:00", "threshold_hours": 168, "actual_interval_hours": 1.23456}),
    ("LX0609-04-02-06", "death_document", {"verification_kind": "death_record_presence_check", "death_confirmed": True, "death_record_count": 1}),
    ("LX0609-08-01-01", "discharge", {"verification_kind": "discharge_record_timeliness_check", "discharge_time": "2026-09-01 01:00:00", "record_time": "2026-09-01 02:00:00", "threshold_hours": 24, "actual_interval_hours": 1.23}),
    ("LX0609-08-01-02", "discharge", {"verification_kind": "discharge_medication_completeness_check", "medication_count": 1, "required_fields": ["drug_name", "dose", "route", "duration"], "missing_fields": []}),
    ("LX0609-08-01-03", "discharge", {"verification_kind": "discharge_diagnosis_consistency_check", "authoritative_diagnoses": ["肺炎"], "written_diagnoses": ["肺炎"], "diagnoses_consistent": True}),
    ("LX0609-08-02-01", "discharge", {"verification_kind": "predischarge_course_presence_check", "discharge_date": "2026-09-02", "checked_dates": ["2026-09-01", "2026-09-02"], "course_present": True}),
    ("LX0609-08-02-02", "discharge", {"verification_kind": "senior_discharge_approval_present", "discharge_date": "2026-09-02", "checked_dates": ["2026-09-01", "2026-09-02"], "checked_source": "senior_course_record", "approval_present": True, "approval_path": "senior_approval"}),
]

@pytest.mark.parametrize("rid,family,facts", CASES)
def test_actual_store_preserves_facts_without_internal_projection(monkeypatch, rid, family, facts):
    module = importlib.import_module(f"app.services.luxian_0609.{family}_result_mapping")
    projection_name = f"safe_{family}_customer_display_facts"
    assert getattr(module, projection_name)(rule_id=rid, raw=facts) == facts
    def forbidden_projection(**kwargs):
        raise AssertionError("公开读取不应重入内部投影")
    item = {"record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P", "rule_id": rid,
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
            monkeypatch.setattr(module, projection_name, forbidden_projection)
            loaded = store.load_selected(db, **selected)
            assert loaded["items"][0]["customer_display_facts"] == facts
            damaged = deepcopy(loaded)
            damaged["items"][0]["customer_display_facts"]["source_document_id"] = "INTERNAL"
            db.execute(sa.update(table).values(envelope_json=json.dumps(damaged)))
            db.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db, **selected)
    finally:
        engine.dispose()

@pytest.mark.parametrize("rid,family,facts", CASES)
def test_absent_facts_preserve_previous_optional_contract(rid, family, facts):
    for raw in (None, {}):
        assert validate_luxian_0609_published_customer_display_facts(rule_id=rid, raw=raw) is None


@pytest.mark.parametrize("rid,family,raw", [
    ("LX0609-09-02-01", "death_document", {"verification_kind": "death_discussion_evaluation_horizon_unavailable", "death_time": "2026-09-01 01:00:00", "issue": "authoritative_time_missing"}),
    ("LX0609-08-01-02", "discharge", {"verification_kind": "discharge_medication_extraction_pending", "extraction_state": "data_gap"}),
])
def test_initial_publish_calls_internal_projection_once(monkeypatch, rid, family, raw):
    from app.services.luxian_0609.canonical_result_finalizer import finalize_luxian_0609_reduced_customer_result
    from app.services.luxian_0609.decision_model import ApplicabilityState, EvidenceState, QcDirection, RuleDecision
    from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
    module = importlib.import_module(f"app.services.luxian_0609.{family}_result_mapping")
    name = f"safe_{family}_customer_display_facts"
    original = getattr(module, name)
    calls = []
    def counted(**kwargs):
        calls.append(kwargs["rule_id"])
        return original(**kwargs)
    monkeypatch.setattr(module, name, counted)
    decision = reduce_luxian_0609_rule_decision(RuleDecision(
        rule_id=rid, snapshot_hash="a" * 64, applicability=ApplicabilityState.APPLICABLE,
        evidence_state=EvidenceState.DATA_GAP, qc_direction=QcDirection.UNKNOWN,
        reason_code="required_field_missing", fact_refs=(), evaluator_version="fixed-test",
    ))
    result = finalize_luxian_0609_reduced_customer_result(
        decision=decision, raw_customer_display_facts=raw, evidence_snapshot=None, evidence_materials=None,
    )
    assert calls == [rid]
    assert (result["status"], result["reason_code"]) == ("data_gap", "required_field_missing")
    assert result["customer_display_facts"] == raw
