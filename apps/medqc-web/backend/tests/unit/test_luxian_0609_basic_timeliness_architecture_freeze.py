from __future__ import annotations

from pathlib import Path

import pytest

import app.services.luxian_0609.canonical_result_finalizer as finalizer_module

from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.native_basic_timeliness import (
    BASIC_TIMELINESS_RULE_IDS,
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_result_aggregator import aggregate_luxian_0609_results


def _frozen_session(*, rescue_rows=None):
    rows_by_source = {
        "inpat_registration": [
            {"admission_datetime": "2026-06-01 08:00:00"},
        ],
        "admission_record": [
            {
                "document_id": "ADM-1",
                "document_title": "入院记录",
                "record_time": "2026-06-01 09:00:00",
                "chief_complaint": "腹痛3天",
            }
        ],
        "first_course_record": [
            {
                "document_id": "FC-1",
                "document_title": "首次病程记录",
                "record_time": "2026-06-01 10:00:00",
                "record_content": "已完成病史采集、体格检查、诊断分析和治疗计划。",
            }
        ],
        "daily_course_record": [],
        "senior_course_record": [
            {
                "document_id": "SR-1",
                "document_title": "主任医师首次查房记录",
                "record_time": "2026-06-02 08:00:00",
            }
        ],
        "rescue_record": rescue_rows if rescue_rows is not None else [],
        "inpat_nondrug_order": [],
        "discharge_record": [],
    }

    def read_rows(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=BASIC_TIMELINESS_RULE_IDS,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-06-04T12:00:00+08:00",
        evaluation_as_of_date="2026-06-04",
        row_reader=read_rows,
        additional_source_keys=tuple(rows_by_source),
    )


def _evidence_coordinates(result: dict) -> list[tuple[str, str, str, str]]:
    return [
        (
            str(item.get("source_type") or ""),
            str(item.get("source_document_id") or ""),
            str(item.get("field_path") or ""),
            str(item.get("record_time") or ""),
        )
        for item in result.get("customer_evidence") or []
    ]


def test_basic_timeliness_family_canonical_behavior_is_frozen_without_sha_assertions(
    monkeypatch,
):
    session = _frozen_session()
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=BASIC_TIMELINESS_RULE_IDS,
        decision_rule_ids=BASIC_TIMELINESS_RULE_IDS,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=BASIC_TIMELINESS_RULE_IDS,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    selected = set(BASIC_TIMELINESS_RULE_IDS)
    wrapper_rules = [
        rule for rule in load_luxian_0609_rules() if rule["rule_id"] in selected
    ]

    original_validator = finalizer_module.validate_luxian_0609_executor_customer_display_facts
    calls = []

    def counted_validator(*, rule_id, raw):
        calls.append(rule_id)
        return original_validator(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(
        finalizer_module,
        "validate_luxian_0609_executor_customer_display_facts",
        counted_validator,
    )
    results = aggregate_luxian_0609_results(
        wrapper_rules=wrapper_rules,
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert tuple(item["rule_id"] for item in results) == BASIC_TIMELINESS_RULE_IDS
    assert [(item["status"], item["reason_code"]) for item in results] == [
        ("compliant", "requirement_within_threshold"),
        ("compliant", "requirement_within_threshold"),
        ("not_applicable", "trigger_absent_complete"),
        ("compliant", "requirement_within_threshold"),
        ("compliant", "requirement_within_threshold"),
    ]
    assert [item["findings"] for item in results] == [
        "已确认入院记录在入院后 24 小时内完成。",
        "已确认首次病程记录在入院后 8 小时内完成。",
        "本次未发现有效抢救事件，不启动抢救记录6小时时限核对",
        "已确认主治医师首次查房记录在入院后 48 小时内完成。",
        "已确认最高级别医师首次查房记录在入院后 72 小时内完成。",
    ]
    assert [
        item.get("customer_display_facts", {}).get("elapsed_hours")
        for item in results
    ] == [1.0, 2.0, None, 24.0, 24.0]
    assert [_evidence_coordinates(item) for item in results] == [
        [("admission_record", "ADM-1", "chief_complaint", "2026-06-01 09:00:00")],
        [
            # 只交付执行器明确选中的目标文书，入院锚点仍保留在受控事实中。
            ("first_course_record", "FC-1", "record_content", "2026-06-01 10:00:00"),
        ],
        [],
        [("senior_course_record", "SR-1", "document_title", "2026-06-02 08:00:00")],
        [("senior_course_record", "SR-1", "document_title", "2026-06-02 08:00:00")],
    ]
    assert getattr(execution, "llm_call_count", 0) == 0
    assert getattr(execution, "total_tokens", 0) == 0
    assert calls.count("LX0609-01-01-01") == 1

    # 在相同冻结输入下强制走旧的二次校验分支，比对完整客户结果。
    original_finalize = finalizer_module.finalize_luxian_0609_executor_customer_display_facts

    def legacy_finalize(**kwargs):
        if kwargs["result"]["rule_id"] == "LX0609-01-01-01":
            kwargs["_validated_facts"] = NotImplemented
        return original_finalize(**kwargs)

    monkeypatch.setattr(
        finalizer_module, "finalize_luxian_0609_executor_customer_display_facts",
        legacy_finalize,
    )
    legacy_results = aggregate_luxian_0609_results(
        wrapper_rules=wrapper_rules, execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    assert legacy_results == results


def test_original_004_mixed_rescue_events_publish_once(monkeypatch):
    rule_id = "LX0609-09-01-01"
    session = _frozen_session(rescue_rows=[
        {
            "document_id": "RS-1", "record_time": "2026-06-01 11:00:00",
            "record_content": "抢救结束时间：2026-06-01 10:00:00。",
        },
        {
            "document_id": "RS-2", "record_time": "2026-06-02 09:00:00",
            "record_content": "抢救结束时间：2026-06-01 12:00:00。",
        },
    ])
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=(rule_id,), decision_rule_ids=(rule_id,), evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule_id,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    original_validator = finalizer_module.validate_luxian_0609_executor_customer_display_facts
    calls = []

    def counted_validator(*, rule_id, raw):
        calls.append(rule_id)
        return original_validator(rule_id=rule_id, raw=raw)

    monkeypatch.setattr(
        finalizer_module,
        "validate_luxian_0609_executor_customer_display_facts",
        counted_validator,
    )
    results = aggregate_luxian_0609_results(
        wrapper_rules=[
            rule for rule in load_luxian_0609_rules() if rule["rule_id"] == rule_id
        ],
        execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert calls.count(rule_id) == 1
    assert len(results) == 1
    assert results[0]["status"] == "non_compliant"
    assert results[0]["reason_code"] == "threshold_exceeded"
    assert [event["event_state"] for event in results[0]["customer_display_facts"]["rescue_events"]] == [
        "within", "late",
    ]
    assert results[0]["customer_display_facts"]["elapsed_hours"] == 21.0
    assert getattr(execution, "llm_call_count", 0) == 0

    original_finalize = finalizer_module.finalize_luxian_0609_executor_customer_display_facts

    def legacy_finalize(**kwargs):
        kwargs["_validated_facts"] = NotImplemented
        return original_finalize(**kwargs)

    monkeypatch.setattr(
        finalizer_module, "finalize_luxian_0609_executor_customer_display_facts",
        legacy_finalize,
    )
    legacy_results = aggregate_luxian_0609_results(
        wrapper_rules=[
            rule for rule in load_luxian_0609_rules() if rule["rule_id"] == rule_id
        ],
        execution_results=[], reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    assert legacy_results == results


@pytest.mark.parametrize(
    ("rule_id", "failure"),
    [
        ("LX0609-01-01-01", "missing"),
        ("LX0609-01-01-01", "private_identifier"),
        ("LX0609-09-01-01", "missing"),
        ("LX0609-09-01-01", "private_identifier"),
    ],
)
def test_original_001_004_missing_and_invalid_facts_keep_previous_result(
    monkeypatch, rule_id, failure,
):
    rescue_rows = (
        [{
            "document_id": "RS-1", "record_time": "2026-06-01 11:00:00",
            "record_content": "抢救结束时间：2026-06-01 10:00:00。",
        }]
        if rule_id == "LX0609-09-01-01" and failure != "missing"
        else None
    )
    session = _frozen_session(rescue_rows=rescue_rows)
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=(rule_id,), decision_rule_ids=(rule_id,), evidence_payload=None,
        evidence_snapshot=session.snapshot, evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions, expected_rule_ids=(rule_id,),
        snapshot=session.snapshot, evidence_materials=session.materials,
    )
    if failure == "missing":
        submitted_facts = ()
    else:
        original_facts = execution.customer_display_facts[0][1]
        submitted_facts = ((rule_id, {
            **original_facts, "source_document_id": "FORGED",
        }),)
    rules = [
        rule for rule in load_luxian_0609_rules() if rule["rule_id"] == rule_id
    ]
    options = {
        "wrapper_rules": rules, "execution_results": [],
        "reduced_decisions": reduced,
        "customer_display_facts": submitted_facts, "format_evidence": False,
        "audit_context": {
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    }
    actual = aggregate_luxian_0609_results(**options)
    original_finalize = finalizer_module.finalize_luxian_0609_executor_customer_display_facts

    def legacy_finalize(**kwargs):
        kwargs["_validated_facts"] = NotImplemented
        return original_finalize(**kwargs)

    monkeypatch.setattr(
        finalizer_module, "finalize_luxian_0609_executor_customer_display_facts",
        legacy_finalize,
    )
    assert actual == aggregate_luxian_0609_results(**options)
    if failure == "private_identifier":
        assert actual[0]["status"] == "technical_error"
        assert actual[0]["reason_code"] == "model_invalid_output"


def test_basic_timeliness_rule_literals_do_not_return_to_result_aggregator():
    aggregator_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "luxian_0609_result_aggregator.py"
    )
    aggregator_source = aggregator_path.read_text(encoding="utf-8")

    assert all(
        rule_id not in aggregator_source for rule_id in BASIC_TIMELINESS_RULE_IDS
    )


def test_finalizer_accepts_executor_safe_facts_and_rejects_internal_document_ids():
    safe_facts = {
        "failure_kind": "timeliness_requirement_satisfied",
        "target_document": "admission_record",
        "source_label": "入院记录",
        "timeliness_state": "within",
        "threshold_hours": 24,
        "anchor_time": "2026-06-01 08:00:00",
        "observed_time": "2026-06-01 09:00:00",
        "elapsed_hours": 1.0,
        "remaining_hours": 23.0,
    }

    assert validate_luxian_0609_executor_customer_display_facts(
        rule_id="LX0609-01-01-01", raw=safe_facts
    ) == safe_facts
    assert validate_luxian_0609_executor_customer_display_facts(
        rule_id="LX0609-01-01-01",
        raw={**safe_facts, "source_document_id": "ADM-INTERNAL"},
    ) is None


def test_aggregator_safely_downgrades_executor_facts_with_internal_document_id():
    session = _frozen_session()
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=("LX0609-01-01-01",),
        decision_rule_ids=("LX0609-01-01-01",),
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-01-01-01",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    safe_facts = dict(execution.customer_display_facts[0][1])

    results = aggregate_luxian_0609_results(
        wrapper_rules=[
            rule
            for rule in load_luxian_0609_rules()
            if rule["rule_id"] == "LX0609-01-01-01"
        ],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=(
            ("LX0609-01-01-01", {**safe_facts, "source_document_id": "FORGED"}),
        ),
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert len(results) == 1
    assert results[0]["status"] == "technical_error"
    assert results[0]["reason_code"] == "model_invalid_output"
    assert "customer_display_facts" not in results[0]
    assert "customer_evidence" not in results[0]
