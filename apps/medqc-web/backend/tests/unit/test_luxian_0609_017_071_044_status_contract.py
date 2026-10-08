"""017/071/044 状态事实合同四入口，隔离SQLite与无网络保护。"""
from copy import deepcopy
from datetime import datetime
import json
import socket

import pytest
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.services import custom_qc_workspace_service as workspace
from app.services.luxian_0609.canonical_result_finalizer import (
    finalize_luxian_0609_executor_customer_display_facts,
    validate_luxian_0609_published_customer_display_facts,
)
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result, validated_customer_explanation,
)

COPY = "LX0609-12-01-02"
HANDOFF = "LX0609-10-01-01"
ASSESS = "LX0609-07-01-02"
STATES = ("compliant", "non_compliant", "data_gap", "not_applicable", "not_executed", "uncertain", "technical_error", "", "unknown")

@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("合同测试禁止网络与模型")
    def sqlite_only(connection, *args):
        assert connection.dialect.name == "sqlite"
    monkeypatch.setattr(socket, "create_connection", blocked)
    event.listen(Engine, "before_cursor_execute", sqlite_only)
    yield
    event.remove(Engine, "before_cursor_execute", sqlite_only)


def copy_facts(kind="copy_similarity_threshold_exceeded"):
    return {"failure_kind": kind, "copy_similarity": .5 if kind == "copy_similarity_within_threshold" else 1.,
            "copy_similarity_threshold": .7, "copy_document_sources": ["daily_course_record", "daily_course_record"],
            "copy_document_record_times": ["2026-07-01 10:00:00", "2026-07-02 10:00:00"]}


def handoff_facts(count=2):
    return {"failure_kind": "physician_handoff_record_time_missing", "change_event_count": count,
            "handoff_record_count": count, "missing_handoff_time_count": 0,
            "handover_record_count": count, "missing_handover_time_count": 1, "handover_threshold_hours": 24}


def assessment_facts(kind, *, legacy=False):
    if kind == "system_data_contract_gap":
        return {"failure_kind": kind, "system_gap_reason": "pretransfusion_assessment_source_unavailable", "gap_owner": "system_integration"}
    if kind == "transfusion_requirement_not_documented":
        return {"failure_kind": kind, "requirement": "pretransfusion_assessment", "checked_sources": ["bloodtrans_record", "blood_application", "course_record"]}
    fields = ["indication", "laboratory_indicator", "risk_history_or_status"] if legacy else ["application_reason", "laboratory_indicator"]
    return {"verification_kind" if kind.endswith("complete") and not kind.endswith("incomplete") else "failure_kind": kind,
            "performed_transfusion_confirmed": True, "checked_fields": fields,
            "missing_fields": [fields[0]] if kind in {"pretransfusion_assessment_incomplete", "pretransfusion_assessment_missing"} else []}


def raw_result(rule, status, facts, reason=None):
    return {"schema_version": workspace.LUXIAN_0609_CUSTOMER_SCHEMA_VERSION, "rule_id": rule, "rule_code": rule, "status": status, "result_status": status,
            "is_compliant": True if status == "compliant" else False if status == "non_compliant" else None,
            "reason_code": reason or {"compliant": "requirement_satisfied", "non_compliant": "requirement_violated", "data_gap": "authoritative_time_missing", "not_applicable": "trigger_absent_complete"}.get(status, "model_invalid_output"),
            "customer_display_facts": deepcopy(facts), "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P"}


def published(item):
    return validate_luxian_0609_published_customer_display_facts(rule_id=item["rule_id"], raw=item["customer_display_facts"], status=item["status"], reason_code=item["reason_code"])


# g14 原八反例；两条 017、四条 071、两条 044。
ORIGINAL = [(COPY, status, copy_facts()) for status in ("compliant", "data_gap")]
ORIGINAL += [(HANDOFF, status, handoff_facts(2 if i == 3 else 1)) for i, status in enumerate(("compliant", "non_compliant", "not_applicable", "compliant"))]
ORIGINAL += [(ASSESS, status, assessment_facts("system_data_contract_gap")) for status in ("compliant", "non_compliant")]

@pytest.mark.parametrize("rule,status,facts", ORIGINAL)
def test_original_eight_contradictions(rule, status, facts):
    with pytest.raises(ValueError):
        published(raw_result(rule, status, facts))


LEGAL = [(COPY, "non_compliant", copy_facts())]
LEGAL += [(COPY, "compliant", copy_facts(kind)) for kind in ("copy_similarity_within_threshold", "copy_semantic_review_passed", "copy_template_shell_only")]
LEGAL += [(HANDOFF, "data_gap", handoff_facts(count)) for count in (1, 2)]
LEGAL += [(ASSESS, state, assessment_facts(kind, legacy=legacy)) for kind, state in (
    ("system_data_contract_gap", "data_gap"), ("pretransfusion_assessment_time_unavailable", "data_gap"),
    ("pretransfusion_assessment_complete", "compliant"), ("pretransfusion_assessment_incomplete", "non_compliant"),
    ("pretransfusion_assessment_missing", "non_compliant"), ("pretransfusion_assessment_time_conflict", "non_compliant"),
    ("transfusion_requirement_not_documented", "non_compliant")) for legacy in (False, True)]

@pytest.mark.parametrize("rule,expected,facts", LEGAL)
@pytest.mark.parametrize("status", STATES)
def test_all_kinds_typed_and_published_status_matrix(rule, expected, facts, status):
    item = raw_result(rule, status, facts)
    result, handled = finalize_luxian_0609_executor_customer_display_facts(result=item, raw_facts=facts)
    assert handled
    if status == expected:
        assert result["status"] == expected
        assert published(item) == facts
    else:
        assert result["status"] == "technical_error"
        assert "customer_display_facts" not in result
        with pytest.raises(ValueError):
            published(item)


@pytest.mark.parametrize("raw", [None, {}])
@pytest.mark.parametrize("status,reason", [("data_gap", "required_field_missing"), ("not_applicable", "trigger_absent_complete"), ("not_applicable", "eligibility_not_met")])
def test_017_approved_absent_history(raw, status, reason):
    assert published(raw_result(COPY, status, raw, reason)) is None

@pytest.mark.parametrize("status,reason", [("compliant", "requirement_satisfied"), ("non_compliant", "requirement_violated"), ("data_gap", "wrong_reason"), ("", "required_field_missing"), ("technical_error", "required_field_missing")])
def test_017_absent_outside_approved_combinations(status, reason):
    with pytest.raises(ValueError):
        published(raw_result(COPY, status, None, reason))

@pytest.mark.parametrize("key,value", [("change_event_count", 0), ("change_event_count", -1), ("change_event_count", True), ("change_event_count", "1"), ("change_event_count", 1.), ("missing_handover_time_count", 2), ("missing_handover_time_count", 0), ("handover_threshold_hours", 23), ("unknown", 1)])
def test_071_invalid_counts_and_extra_keys(key, value):
    facts = handoff_facts(1)
    facts[key] = value
    with pytest.raises(ValueError):
        published(raw_result(HANDOFF, "data_gap", facts))


def persist(item, path):
    table = workspace._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    store = CanonicalResultStore(table)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    table.metadata.create_all(engine)
    with Session(engine) as db:
        store.replace_for_job(db, job_row={"id": "J", "created_by": "reviewer", "filters_json": json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"})}, items=[item], now=datetime(2026, 10, 8), projection_key="d-contract", projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="d-contract"))
        db.commit()
    engine.dispose()
    # 新 engine / 新 Session 正式回读，避免同引擎缓存。
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        with Session(engine) as db:
            return store.load_selected(db, root_job_id="J", institute_id="I", patient_id="P", visit_id="V", rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09")["items"][0]
    finally:
        engine.dispose()

@pytest.mark.parametrize("rule,status,facts", LEGAL)
def test_legal_kind_formal_finalizer_store_new_engine_api(tmp_path, rule, status, facts):
    item, handled = finalize_luxian_0609_executor_customer_display_facts(result=raw_result(rule, status, facts), raw_facts=facts)
    assert handled and item["status"] == status
    expected = envelope_item_from_rule_result(item, hmac_key="d-contract")
    loaded = persist(item, tmp_path / "result.sqlite")
    for key in ("status", "reason_code", "is_compliant", "customer_display_facts", "criterion_results", "evidence", "findings", "suggestion"):
        assert loaded.get(key) == expected.get(key), key
    assert workspace.project_customer_safe_result_item(loaded, hmac_key="d-contract")["customer_display_facts"] == facts

@pytest.mark.parametrize("rule,status,facts", ORIGINAL + [(ASSESS, "compliant", assessment_facts("pretransfusion_assessment_time_unavailable")), (ASSESS, "compliant", assessment_facts("transfusion_requirement_not_documented")), (ASSESS, "data_gap", assessment_facts("transfusion_requirement_not_documented"))])
def test_contradictions_canonical_store_api_reject(tmp_path, rule, status, facts):
    item = raw_result(rule, status, facts)
    with pytest.raises(ValueError):
        validated_customer_explanation(item, rule_id=rule, status=status)
    with pytest.raises(ValueError):
        persist(item, tmp_path / "invalid.sqlite")
    with pytest.raises(ValueError):
        workspace.project_customer_safe_result_item(item, hmac_key="d-contract")
