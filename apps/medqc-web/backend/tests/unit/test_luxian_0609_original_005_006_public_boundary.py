"""原始005/006查房时限：已发布事实只校验，不重新投影。"""

from __future__ import annotations

import json
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

import app.services.custom_qc_workspace_service as workspace_module
import app.services.luxian_0609.canonical_result_finalizer as finalizer_module
from app.services.luxian_0609.basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
)
from app.services.luxian_0609.decision_binding import bind_and_reduce_luxian_0609_rule_decisions
from app.services.luxian_0609.native_basic_timeliness import execute_luxian_0609_native_basic_timeliness
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore, envelope_item_from_rule_result, safe_customer_display_facts,
)
from tests.unit.test_luxian_0609_basic_timeliness_architecture_freeze import _frozen_session
from tests.unit.test_luxian_0609_native_basic_timeliness import _typed_basic_session


CASES = (
    ("LX0609-02-01-01", "attending_course_record", "主治医师及以上首次查房记录", 48),
    ("LX0609-02-01-02", "senior_course_record", "副主任医师或主任医师首次查房记录", 72),
)


@pytest.mark.parametrize("rule_id,target,label,threshold", CASES)
@pytest.mark.parametrize("state,elapsed", (
    ("within", 1.004), ("late", 73.004), ("missing", None),
))
def test_005_006_published_facts_are_unchanged(rule_id, target, label, threshold, state, elapsed):
    raw = {
        "failure_kind": (
            "timeliness_requirement_satisfied" if state == "within"
            else "timeliness_requirement_not_met"
        ),
        "target_document": target, "source_label": label,
        "timeliness_state": state, "threshold_hours": threshold,
        "anchor_date": "2026-06-01",
    }
    if elapsed is not None:
        raw.update(observed_time="2026-06-04 09:00:00", elapsed_hours=elapsed)
    published = safe_basic_timeliness_customer_display_facts(rule_id=rule_id, raw=raw)
    assert published is not None
    assert safe_customer_display_facts({"customer_display_facts": published}, rule_id=rule_id) == published


@pytest.mark.parametrize("rule_id,target,label,threshold", CASES)
@pytest.mark.parametrize("bad_key,bad_value", (
    ("remaining_hours", 999.0), ("elapsed_hours", True),
    ("elapsed_hours", float("nan")), ("source_label", []),
    ("threshold_hours", 24), ("unknown_field", "secret"),
))
def test_005_006_corrupt_published_fact_is_rejected(rule_id, target, label, threshold, bad_key, bad_value):
    published = safe_basic_timeliness_customer_display_facts(
        rule_id=rule_id,
        raw={
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": target, "source_label": label,
            "timeliness_state": "within", "threshold_hours": threshold,
            "elapsed_hours": 1.0,
        },
    )
    assert published is not None
    with pytest.raises(ValueError, match="解释合同不完整"):
        safe_customer_display_facts(
            {"customer_display_facts": {**published, bad_key: bad_value}}, rule_id=rule_id,
        )


@pytest.mark.parametrize("rule_id,target,label,threshold", CASES)
@pytest.mark.parametrize("state", ("within", "late"))
def test_005_006_old_two_step_rounding_is_accepted(rule_id, target, label, threshold, state):
    # 每条规则分别在本身阈值附近构造双重舍入，不重算已发布的派生值。
    elapsed = threshold - 0.005 if state == "within" else threshold + 0.004
    published = safe_basic_timeliness_customer_display_facts(
        rule_id=rule_id,
        raw={
            "failure_kind": (
                "timeliness_requirement_satisfied" if state == "within"
                else "timeliness_requirement_not_met"
            ),
            "target_document": target, "source_label": label,
            "timeliness_state": state, "threshold_hours": threshold,
            "elapsed_hours": elapsed,
        },
    )
    assert published is not None
    assert safe_customer_display_facts({"customer_display_facts": published}, rule_id=rule_id) == published


def test_005_006_existing_executor_results_project_once(monkeypatch):
    selected = tuple(case[0] for case in CASES)
    session = _frozen_session()
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=selected, decision_rule_ids=selected, evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=selected,
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    original = finalizer_module.validate_luxian_0609_executor_customer_display_facts
    calls = []

    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(finalizer_module, "validate_luxian_0609_executor_customer_display_facts", counted)
    results = aggregate_luxian_0609_results(
        wrapper_rules=[rule for rule in load_luxian_0609_rules() if rule["rule_id"] in selected],
        execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts, format_evidence=False,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )
    expected_names = (
        "上级医生查房记录：入院后 48 小时内无主治医师首次查房记录。",
        "上级医生查房记录：入院后 72小时内无最高级别（副主任医师或主任医师）首次查房记录。",
    )
    expected_findings = (
        "已确认主治医师首次查房记录在入院后 48 小时内完成。",
        "已确认最高级别医师首次查房记录在入院后 72 小时内完成。",
    )
    assert results == [
        {
            "confidence": 1.0,
            "criterion_results": [],
            "customer_display_facts": {
                "anchor_time": "2026-06-01 08:00:00",
                "elapsed_hours": 24.0,
                "failure_kind": "timeliness_requirement_satisfied",
                "observed_time": "2026-06-02 08:00:00",
                "remaining_hours": threshold - 24.0,
                "source_label": label,
                "target_document": target,
                "threshold_hours": threshold,
                "timeliness_state": "within",
            },
            "customer_evidence": [{
                "evidence_excerpt": "主任医师首次查房记录",
                "excerpt_kind": "文书级依据",
                "field_path": "document_title",
                "record_time": "2026-06-02 08:00:00",
                "source_document_id": "SR-1",
                "source_type": "senior_course_record",
            }],
            "evidence": "已根据受控证据完成判断。",
            "evidence_items": [],
            "findings": expected_findings[index],
            "is_compliant": True,
            "qc_point_id": rule_id,
            "reason_code": "requirement_within_threshold",
            "result_status": "compliant",
            "rule_code": rule_id,
            "rule_id": rule_id,
            "rule_name": expected_names[index],
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "rule_version": "2026-06-09",
            "schema_version": "lx0609-customer-result-v2",
            "status": "compliant",
            "suggestion": "继续保持。",
        }
        for index, (rule_id, target, label, threshold) in enumerate(CASES)
    ]
    assert [(item["rule_id"], item["status"], item["reason_code"]) for item in results] == [
        (rule_id, "compliant", "requirement_within_threshold") for rule_id in selected
    ]
    assert [item["customer_display_facts"]["elapsed_hours"] for item in results] == [24.0, 24.0]
    assert [
        [(e["source_type"], e["source_document_id"]) for e in item["customer_evidence"]]
        for item in results
    ] == [[("senior_course_record", "SR-1")]] * 2
    assert calls == list(selected)
    assert getattr(execution, "llm_call_count", 0) == 0
    assert getattr(execution, "total_tokens", 0) == 0


@pytest.mark.parametrize("rule_id,target,label,threshold", CASES)
@pytest.mark.parametrize("case", ("within", "late", "missing", "no_anchor", "date_anchor"))
def test_005_006_frozen_executor_branches_keep_status_reason_and_fact_source(
    rule_id, target, label, threshold, case,
):
    senior_rows = {
        "within": [{"document_id": "SR-1", "document_title": "主任医师首次查房记录",
                    "record_time": "2026-06-02 08:00:00"}],
        "date_anchor": [{"document_id": "SR-DATE", "document_title": "主任医师首次查房记录",
                         "record_time": "2026-06-02 08:00:00"}],
        "late": [{"document_id": "SR-2", "document_title": "主任医师首次查房记录",
                  "record_time": "2026-06-05 08:00:00"}],
    }.get(case, [])
    source_rows = {
        "inpat_registration": (
            [] if case in {"no_anchor", "date_anchor"}
            else [{"admission_datetime": "2026-06-01 08:00:00"}]
        ),
        "discharge_record": (
            [{"admission_date": "2026-06-01"}] if case == "date_anchor" else []
        ),
        "admission_record": (
            [{"document_title": "入院记录", "record_time": "2026-06-02 08:00:00",
              "chief_complaint": "反复腹痛三天"}]
            if case == "date_anchor" else []
        ),
        "senior_course_record": senior_rows,
    }
    session = _typed_basic_session(
        source_rows, selected_rule_ids=(rule_id,), evaluation_as_of_date="2026-06-07",
    )
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=(rule_id,), decision_rule_ids=(rule_id,), evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule_id,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    result = aggregate_luxian_0609_results(
        wrapper_rules=[rule for rule in load_luxian_0609_rules() if rule["rule_id"] == rule_id],
        execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts, format_evidence=False,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )[0]
    expected = {
        "within": ("compliant", "requirement_within_threshold", "within"),
        "late": ("non_compliant", "threshold_exceeded", "late"),
        "missing": (
            ("data_gap", "source_empty", None) if rule_id == CASES[0][0]
            else ("non_compliant", "required_document_missing", "missing")
        ),
        "no_anchor": ("data_gap", "authoritative_time_missing", None),
        "date_anchor": ("compliant", "requirement_within_threshold", "within"),
    }[case]
    assert (result["status"], result["reason_code"]) == expected[:2]
    if expected[2] is not None:
        facts = result["customer_display_facts"]
        assert (facts["target_document"], facts["threshold_hours"]) == (target, threshold)
        assert facts["timeliness_state"] == expected[2]
        assert facts["source_label"] == label
        assert ("anchor_date" in facts) == (case == "date_anchor")
    else:
        assert not result.get("customer_display_facts")
    assert getattr(execution, "llm_call_count", 0) == 0
    assert getattr(execution, "total_tokens", 0) == 0


@pytest.mark.asyncio
async def test_006_fixed_semantic_role_response_keeps_same_published_fact_shape(monkeypatch):
    class _FixedModel:
        def __init__(self):
            self.prompts = []

        async def generate(self, prompt):
            self.prompts.append(prompt)
            return {
                "choices": [{"message": {"content": (
                    '{"schema_version":"lx0609-006-round-role-v1",'
                    '"documents":[{"position":1,"role":"senior",'
                    '"physician_name":"彭中","physician_title":"主任医师",'
                    '"evidence_quote":"今日彭中主任医师联合神经疾病"}]}'
                )}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 12, "total_tokens": 52},
                "response_time": 0.2,
            }

    rule_id = CASES[1][0]
    session = _typed_basic_session(
        {
            "inpat_registration": [{"admission_datetime": "2026-07-15 13:48:49"}],
            "senior_course_record": [{
                "document_id": "safe-upper-round-ref", "document_title": "上级医师查房记录",
                "record_time": "2026-07-16 10:30:02",
                "record_content": "今日彭中主任医师联合神经疾病相关专业医师查房。",
            }],
        },
        selected_rule_ids=(rule_id,), evaluation_as_of_date="2026-07-20",
    )
    model = _FixedModel()
    execution = await execute_luxian_0609_native_basic_timeliness(
        rule_ids=(rule_id,), decision_rule_ids=(rule_id,), evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
        llm_client=model,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule_id,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    original = finalizer_module.validate_luxian_0609_executor_customer_display_facts
    calls = []

    def counted(*, rule_id, raw):
        calls.append(rule_id)
        return original(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(finalizer_module, "validate_luxian_0609_executor_customer_display_facts", counted)
    result = aggregate_luxian_0609_results(
        wrapper_rules=[rule for rule in load_luxian_0609_rules() if rule["rule_id"] == rule_id],
        execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts, format_evidence=False,
        audit_context={"evidence_snapshot": session.snapshot, "evidence_materials": session.materials},
    )[0]
    assert len(model.prompts) == execution.llm_call_count == 1
    assert execution.total_tokens == 52
    assert calls == [rule_id]
    assert (result["status"], result["reason_code"]) == (
        "compliant", "requirement_within_threshold",
    )
    assert result["customer_display_facts"] == {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "senior_course_record",
        "source_label": "副主任医师或主任医师首次查房记录",
        "timeliness_state": "within",
        "threshold_hours": 72,
        "anchor_time": "2026-07-15 13:48:49",
        "observed_time": "2026-07-16 10:30:02",
        "elapsed_hours": 20.69,
        "remaining_hours": 51.31,
    }


@pytest.mark.parametrize("rule_id,target,label,threshold", CASES)
def test_005_006_sqlite_read_rejects_corrupt_derivative(rule_id, target, label, threshold):
    published = safe_basic_timeliness_customer_display_facts(
        rule_id=rule_id,
        raw={
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": target, "source_label": label,
            "timeliness_state": "late", "threshold_hours": threshold,
            "elapsed_hours": threshold + 1.0,
        },
    )
    assert published is not None
    item = {
        "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P",
        "rule_id": rule_id, "status": "non_compliant", "result_status": "non_compliant",
        "display_status": "non_compliant", "is_compliant": False,
        "reason_code": "threshold_exceeded", "customer_display_facts": published,
    }
    table = workspace_module._record_result_envelopes_table().to_metadata(MetaData(), schema=None)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    expected = {
        "root_job_id": "J", "institute_id": "I", "patient_id": "P", "visit_id": "V",
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
    }
    try:
        with Session(engine) as db:
            store.replace_for_job(
                db,
                job_row={"id": "J", "created_by": "reviewer", "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                })},
                items=[item], now=datetime(2026, 9, 24, 10, 0),
                projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="test-key"),
                projection_key="test-key",
            )
            db.commit()
            loaded = store.load_selected(db, **expected, projection_key="test-key")
            assert loaded["items"][0]["customer_display_facts"] == published
            damaged = json.loads(json.dumps(loaded))
            damaged["items"][0]["customer_display_facts"]["overdue_hours"] = 999
            db.execute(sa.update(table).values(envelope_json=json.dumps(damaged)))
            db.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db, **expected, projection_key="test-key")
    finally:
        engine.dispose()
