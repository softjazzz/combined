"""原始002首次病程时限：既有判定不变，已发布事实只校验不重算。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609.canonical_result_finalizer as finalizer_module
from app.services.custom_qc_workspace_service import project_customer_safe_result_item
from app.services.luxian_0609.basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_basic_timeliness import (
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    envelope_item_from_rule_result,
    safe_customer_display_facts,
)
from tests.unit.test_luxian_0609_basic_timeliness_architecture_freeze import _frozen_session


RULE_ID = "LX0609-01-02-01"


def _session_for_first_course(*, first_course_rows, admission_rows=None):
    rows_by_source = {
        "inpat_registration": (
            [{"admission_datetime": "2026-06-01 08:00:00"}]
            if admission_rows is None else admission_rows
        ),
        "first_course_record": first_course_rows,
    }
    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=(RULE_ID,), institute_id="I", patient_id="P", visit_id="V",
        source_schema=None, created_at="2026-06-04T12:00:00+08:00",
        evaluation_as_of_date="2026-06-04",
        row_reader=lambda **query: SnapshotSourceRows.create(
            source_key=query["source_key"],
            rows=rows_by_source.get(query["source_key"], []),
            truncated=False, limit_rows=50,
        ),
    )


@pytest.mark.parametrize("case,expected", [
    ("within", ("compliant", "requirement_within_threshold", "within")),
    ("late", ("non_compliant", "threshold_exceeded", "late")),
    ("missing", ("non_compliant", "required_document_missing", "missing")),
    ("no_anchor", ("data_gap", "authoritative_time_missing", None)),
])
def test_original_002_executor_branches_keep_status_and_published_fact_shape(case, expected):
    rows = {
        "within": [{"document_id": "FC-1", "record_time": "2026-06-01 09:00:00",
                    "record_content": "已完成病史采集、体格检查、诊断分析和治疗计划。"}],
        "late": [{"document_id": "FC-2", "record_time": "2026-06-01 17:00:00",
                  "record_content": "已完成病史采集、体格检查、诊断分析和治疗计划。"}],
        "missing": [], "no_anchor": [],
    }
    session = _session_for_first_course(
        first_course_rows=rows[case],
        admission_rows=[] if case == "no_anchor" else None,
    )
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=(RULE_ID,), decision_rule_ids=(RULE_ID,), evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE_ID,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    result = aggregate_luxian_0609_results(
        wrapper_rules=[rule for rule in load_luxian_0609_rules() if rule["rule_id"] == RULE_ID],
        execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts, format_evidence=False,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )[0]
    assert (result["status"], result["reason_code"]) == expected[:2]
    if expected[2] is None:
        assert not result.get("customer_display_facts")
    else:
        assert result["customer_display_facts"]["timeliness_state"] == expected[2]
    assert getattr(execution, "llm_call_count", 0) == 0
    assert getattr(execution, "total_tokens", 0) == 0


@pytest.mark.parametrize("state,elapsed", [("within", 1.004), ("late", 9.004), ("missing", None)])
def test_original_002_published_facts_are_preserved(state, elapsed):
    raw = {
        "failure_kind": (
            "timeliness_requirement_satisfied" if state == "within"
            else "timeliness_requirement_not_met"
        ),
        "target_document": "first_course_record", "source_label": "首次病程记录",
        "timeliness_state": state, "threshold_hours": 8,
        "anchor_time": "2026-06-01 08:00:00",
    }
    if elapsed is not None:
        raw["observed_time"] = "2026-06-01 09:00:00"
        raw["elapsed_hours"] = elapsed
    published = safe_basic_timeliness_customer_display_facts(rule_id=RULE_ID, raw=raw)
    assert published is not None
    assert safe_customer_display_facts({"customer_display_facts": published}, rule_id=RULE_ID) == published


@pytest.mark.parametrize("state,elapsed", [("within", 7.995), ("late", 8.004)])
def test_original_002_accepts_existing_two_step_rounding_without_recalculation(state, elapsed):
    published = safe_basic_timeliness_customer_display_facts(
        rule_id=RULE_ID,
        raw={
            "failure_kind": (
                "timeliness_requirement_satisfied" if state == "within"
                else "timeliness_requirement_not_met"
            ),
            "target_document": "first_course_record", "source_label": "首次病程记录",
            "timeliness_state": state, "threshold_hours": 8, "elapsed_hours": elapsed,
        },
    )
    assert published is not None
    assert safe_customer_display_facts({"customer_display_facts": published}, rule_id=RULE_ID) == published


@pytest.mark.parametrize("field,value", [
    ("remaining_hours", 999), ("elapsed_hours", True),
    ("elapsed_hours", float("nan")), ("source_label", []),
    ("threshold_hours", 24), ("unpublished", "private"),
])
def test_original_002_corrupt_published_facts_fail_closed(field, value):
    published = safe_basic_timeliness_customer_display_facts(
        rule_id=RULE_ID,
        raw={
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "first_course_record", "source_label": "首次病程记录",
            "timeliness_state": "within", "threshold_hours": 8,
            "elapsed_hours": 1.0,
        },
    )
    assert published is not None
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": {**published, field: value}}, rule_id=RULE_ID,
        )


def test_original_002_executor_to_publisher_keeps_fixed_result_and_one_projection(monkeypatch):
    session = _frozen_session()
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=(RULE_ID,), decision_rule_ids=(RULE_ID,), evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(RULE_ID,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    original = finalizer_module.validate_luxian_0609_executor_customer_display_facts
    calls = []

    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(finalizer_module, "validate_luxian_0609_executor_customer_display_facts", counted)
    result = aggregate_luxian_0609_results(
        wrapper_rules=[rule for rule in load_luxian_0609_rules() if rule["rule_id"] == RULE_ID],
        execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        format_evidence=False,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )[0]
    assert result == {
        "confidence": 1.0,
        "criterion_results": [],
        "customer_display_facts": {
            "anchor_time": "2026-06-01 08:00:00",
            "elapsed_hours": 2.0,
            "failure_kind": "timeliness_requirement_satisfied",
            "observed_time": "2026-06-01 10:00:00",
            "remaining_hours": 6.0,
            "source_label": "首次病程记录",
            "target_document": "first_course_record",
            "threshold_hours": 8,
            "timeliness_state": "within",
        },
        "customer_evidence": [{
            "evidence_excerpt": "已完成病史采集、体格检查、诊断分析和治疗计划。",
            "excerpt_kind": "文书级依据",
            "field_path": "record_content",
            "record_time": "2026-06-01 10:00:00",
            "source_document_id": "FC-1",
            "source_type": "first_course_record",
        }],
        "evidence": "已根据受控证据完成判断。",
        "evidence_items": [],
        "findings": "已确认首次病程记录在入院后 8 小时内完成。",
        "is_compliant": True,
        "qc_point_id": RULE_ID,
        "reason_code": "requirement_within_threshold",
        "result_status": "compliant",
        "rule_code": RULE_ID,
        "rule_id": RULE_ID,
        "rule_name": "首次病程：入院后 8 小时内无首次病程记录",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "rule_version": "2026-06-09",
        "schema_version": "lx0609-customer-result-v2",
        "status": "compliant",
        "suggestion": "继续保持。",
    }
    assert (result["status"], result["reason_code"]) == (
        "compliant", "requirement_within_threshold",
    )
    assert result["customer_display_facts"]["elapsed_hours"] == 2.0
    assert [
        (item["source_type"], item["source_document_id"], item["field_path"])
        for item in result["customer_evidence"]
    ] == [("first_course_record", "FC-1", "record_content")]
    assert calls == [RULE_ID]
    assert getattr(execution, "llm_call_count", 0) == 0
    assert getattr(execution, "total_tokens", 0) == 0


def test_original_002_sqlite_read_rejects_corrupted_published_facts():
    published = safe_basic_timeliness_customer_display_facts(
        rule_id=RULE_ID,
        raw={
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "first_course_record", "source_label": "首次病程记录",
            "timeliness_state": "late", "threshold_hours": 8, "elapsed_hours": 9.0,
        },
    )
    assert published is not None
    item = {
        "record_id": "visit-1", "visit_id": "visit-1", "institute_id": "inst-1",
        "patient_id": "patient-1", "rule_id": RULE_ID,
        "status": "non_compliant", "result_status": "non_compliant",
        "display_status": "non_compliant", "is_compliant": False,
        "reason_code": "threshold_exceeded", "customer_display_facts": published,
    }
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    expected = {
        "root_job_id": "job-1", "institute_id": "inst-1",
        "patient_id": "patient-1", "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
    }
    try:
        with Session(engine) as db_session:
            store.replace_for_job(
                db_session,
                job_row={
                    "id": "job-1", "created_by": "reviewer",
                    "filters_json": json.dumps({
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                    }),
                },
                items=[item], now=datetime(2026, 9, 24, 10, 0),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                projection_key="test-key",
            )
            db_session.commit()
            loaded = store.load_selected(db_session, **expected, projection_key="test-key")
            assert loaded["items"][0]["customer_display_facts"] == published
            assert project_customer_safe_result_item(
                loaded["items"][0], hmac_key="test-key",
            )["customer_display_facts"] == published
            corrupted = json.loads(json.dumps(loaded))
            corrupted["items"][0]["customer_display_facts"]["overdue_hours"] = 999
            db_session.execute(sa.update(table).values(envelope_json=json.dumps(corrupted)))
            db_session.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db_session, **expected, projection_key="test-key")
    finally:
        engine.dispose()
