from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import (
    reduce_luxian_0609_rule_decision,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609.evidence_material import build_material_document_refs
from app.services.luxian_0609.customer_evidence_enrichment import (
    project_selected_document_evidence,
)
from app.services.luxian_0609.native_basic_timeliness import (
    execute_luxian_0609_native_basic_timeliness,
)
from app.services.luxian_0609.source_evidence_reader import (
    CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
)
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_result_aggregator import (
    aggregate_luxian_0609_results,
)


_ALL_SOURCE_KEYS = (
    "inpat_registration",
    "admission_record",
    "first_course_record",
    "daily_course_record",
    "senior_course_record",
    "rescue_record",
    CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
    "discharge_record",
)


def _session(
    *, rows_by_source: Mapping[str, list[dict]], rule_ids: tuple[str, ...]
):
    def read_rows(**kwargs):
        source_key = kwargs["source_key"]
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    return build_luxian_0609_evidence_read_session(
        selected_rule_ids=rule_ids,
        institute_id="I",
        patient_id="P",
        visit_id="V",
        source_schema=None,
        created_at="2026-06-05T12:00:00+08:00",
        evaluation_as_of_date="2026-06-05",
        row_reader=read_rows,
        additional_source_keys=_ALL_SOURCE_KEYS,
    )


def _execute_and_aggregate(session, rule_ids: tuple[str, ...]):
    execution = execute_luxian_0609_native_basic_timeliness(
        rule_ids=rule_ids,
        decision_rule_ids=rule_ids,
        evidence_payload=None,
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=rule_ids,
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    selected = set(rule_ids)
    results = aggregate_luxian_0609_results(
        wrapper_rules=[
            rule for rule in load_luxian_0609_rules() if rule["rule_id"] in selected
        ],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=execution.customer_display_facts,
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )
    return execution, reduced, results


def _fact_ref_source_keys(session, execution) -> dict[str, frozenset[str]]:
    source_by_ref = {
        observation.snapshot_ref.removeprefix("sha256:"): observation.source_key
        for observation in session.snapshot.observations
    }
    for observation in session.snapshot.observations:
        if session.materials.has_source(observation.source_key):
            try:
                document_rows = session.materials.document_rows(
                    observation.source_key, snapshot=session.snapshot
                )
            except ValueError:
                continue
            source_by_ref.update(
                (reference, observation.source_key) for reference, _row in document_rows
            )
    return {
        decision.rule_id: frozenset(
            source_by_ref[reference] for reference in decision.fact_refs
        )
        for decision in execution.decisions
    }


def _coordinates(result: Mapping[str, object]) -> list[tuple[str, str, str, str]]:
    return [
        (
            str(item.get("source_type") or ""),
            str(item.get("source_document_id") or ""),
            str(item.get("field_path") or ""),
            str(item.get("record_time") or ""),
        )
        for item in result.get("customer_evidence") or []
    ]


def _multi_document_session(rule_ids: tuple[str, ...]):
    return _session(
        rule_ids=rule_ids,
        rows_by_source={
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "ADM-EARLY-TEMPLATE",
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 09:00:00",
                    "record_content": "入院记录 时间 2026-06-01 09:00:00 正文",
                },
                {
                    "document_id": "ADM-SELECTED",
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 11:00:00",
                    "chief_complaint": "腹痛3天",
                },
            ],
            "first_course_record": [
                {
                    "document_id": "FC-LATE",
                    "document_title": "首次病程记录",
                    "record_time": "2026-06-01 18:00:00",
                    "record_content": "已完成病史采集、体格检查、诊断分析和治疗计划。",
                },
                {
                    "document_id": "FC-SELECTED",
                    "document_title": "首次病程记录",
                    "record_time": "2026-06-01 10:00:00",
                    "record_content": "已完成病史采集、体格检查、诊断分析和治疗计划。",
                },
            ],
            "daily_course_record": [
                {
                    "document_id": "ROUND-ATTENDING-LATE",
                    "document_title": "主治医师首次查房记录",
                    "record_time": "2026-06-03 10:00:00",
                },
                {
                    "document_id": "ROUND-ATTENDING-SELECTED",
                    "document_title": "主治医师首次查房记录",
                    "record_time": "2026-06-02 08:00:00",
                },
            ],
            "senior_course_record": [
                {
                    "document_id": "ROUND-SENIOR-LATE",
                    "document_title": "主任医师首次查房记录",
                    "record_time": "2026-06-04 09:00:00",
                },
                {
                    "document_id": "ROUND-SENIOR-SELECTED",
                    "document_title": "副主任医师首次查房记录",
                    "record_time": "2026-06-03 08:00:00",
                },
            ],
        },
    )


@pytest.mark.unit
def test_001_002_005_006_multi_document_selection_and_evidence_are_frozen():
    rule_ids = ("LX0609-01-01-01", "LX0609-01-02-01", "LX0609-02-01-01", "LX0609-02-01-02")
    session = _multi_document_session(rule_ids)

    execution, reduced, results = _execute_and_aggregate(session, rule_ids)

    assert [(item.final_state.value, item.reason_code) for item in reduced] == [
        ("compliant", "requirement_within_threshold"),
        ("compliant", "requirement_within_threshold"),
        ("compliant", "requirement_within_threshold"),
        ("compliant", "requirement_within_threshold"),
    ]
    expected_customer_display_facts = {
        "LX0609-01-01-01": {
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "admission_record",
            "source_label": "入院记录",
            "timeliness_state": "within",
            "threshold_hours": 24,
            "anchor_time": "2026-06-01 08:00:00",
            "observed_time": "2026-06-01 11:00:00",
            "elapsed_hours": 3.0,
            "remaining_hours": 21.0,
        },
        "LX0609-01-02-01": {
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "first_course_record",
            "source_label": "首次病程记录",
            "timeliness_state": "within",
            "threshold_hours": 8,
            "anchor_time": "2026-06-01 08:00:00",
            "observed_time": "2026-06-01 10:00:00",
            "elapsed_hours": 2.0,
            "remaining_hours": 6.0,
        },
        "LX0609-02-01-01": {
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "attending_course_record",
            "source_label": "主治医师及以上首次查房记录",
            "timeliness_state": "within",
            "threshold_hours": 48,
            "anchor_time": "2026-06-01 08:00:00",
            "observed_time": "2026-06-02 08:00:00",
            "elapsed_hours": 24.0,
            "remaining_hours": 24.0,
        },
        "LX0609-02-01-02": {
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "senior_course_record",
            "source_label": "上级医师首次查房记录",
            "timeliness_state": "within",
            "threshold_hours": 72,
            "anchor_time": "2026-06-01 08:00:00",
            "observed_time": "2026-06-03 08:00:00",
            "elapsed_hours": 48.0,
            "remaining_hours": 24.0,
        },
    }
    assert dict(execution.customer_display_facts) == expected_customer_display_facts
    assert [item["customer_display_facts"] for item in results] == [
        expected_customer_display_facts[rule_id] for rule_id in rule_ids
    ]
    assert [
        (item["status"], item["reason_code"], item["findings"])
        for item in results
    ] == [
        ("compliant", "requirement_within_threshold", "已确认入院记录在入院后 24 小时内完成。"),
        ("compliant", "requirement_within_threshold", "已确认首次病程记录在入院后 8 小时内完成。"),
        ("compliant", "requirement_within_threshold", "已确认主治医师首次查房记录在入院后 48 小时内完成。"),
        ("compliant", "requirement_within_threshold", "已确认上级医师首次查房记录在入院后 72 小时内完成。"),
    ]
    assert [_coordinates(item) for item in results] == [
        [("admission_record", "ADM-SELECTED", "chief_complaint", "2026-06-01 11:00:00")],
        [("first_course_record", "FC-SELECTED", "record_content", "2026-06-01 10:00:00")],
        [("daily_course_record", "ROUND-ATTENDING-SELECTED", "document_title", "2026-06-02 08:00:00")],
        [
            (
                "senior_course_record",
                "ROUND-SENIOR-SELECTED",
                "document_title",
                "2026-06-03 08:00:00",
            )
        ],
    ]
    assert _fact_ref_source_keys(session, execution) == {
        "LX0609-01-01-01": frozenset(
            {"evaluation_context.horizon", "inpat_registration", "admission_record"}
        ),
        "LX0609-01-02-01": frozenset(
            {
            "evaluation_context.horizon",
            "inpat_registration",
            "first_course_record",
            "admission_record",
            }
        ),
        "LX0609-02-01-01": frozenset(
            {"evaluation_context.horizon", "inpat_registration", "daily_course_record"}
        ),
        "LX0609-02-01-02": frozenset(
            {"evaluation_context.horizon", "inpat_registration", "senior_course_record"}
        ),
    }


@pytest.mark.unit
def test_004_multi_rescue_events_and_effective_order_without_record_are_frozen():
    event_session = _session(
        rule_ids=("LX0609-09-01-01",),
        rows_by_source={
            "rescue_record": [
                {
                    "document_id": "late-rescue-ref",
                    "record_time": "2026-06-01 16:01:00",
                    "record_content": "抢救结束时间：2026-06-01 09:00:00",
                },
                {
                    "document_id": "most-overdue-rescue-ref",
                    "record_time": "2026-06-02 18:00:00",
                    "record_content": "抢救结束时间：2026-06-02 09:00:00",
                },
                {
                    "document_id": "missing-end-ref",
                    "record_time": "2026-06-03 11:00:00",
                    "record_content": "抢救结束，患者情况平稳。",
                },
            ]
        },
    )
    execution, reduced, results = _execute_and_aggregate(
        event_session, ("LX0609-09-01-01",)
    )

    assert [(item.final_state.value, item.reason_code) for item in reduced] == [
        ("non_compliant", "threshold_exceeded")
    ]
    assert dict(execution.customer_display_facts) == {
        "LX0609-09-01-01": {
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "late",
            "threshold_hours": 6,
            "anchor_time": "2026-06-02 09:00:00",
            "observed_time": "2026-06-02 18:00:00",
            "elapsed_hours": 9.0,
            "overdue_hours": 3.0,
            "rescue_events": [
                {
                    "event_index": 1,
                    "rescue_end_time": "2026-06-01 09:00:00",
                    "document_completion_time": "2026-06-01 16:01:00",
                    "event_state": "late",
                    "elapsed_hours": 7.02,
                },
                {
                    "event_index": 2,
                    "rescue_end_time": "2026-06-02 09:00:00",
                    "document_completion_time": "2026-06-02 18:00:00",
                    "event_state": "late",
                    "elapsed_hours": 9.0,
                },
                {
                    "event_index": 3,
                    "document_completion_time": "2026-06-03 11:00:00",
                    "event_state": "rescue_end_time_missing",
                },
            ],
        }
    }
    assert results[0]["customer_display_facts"] == {
        "failure_kind": "timeliness_requirement_not_met",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "timeliness_state": "late",
        "threshold_hours": 6,
        "anchor_time": "2026-06-02 09:00:00",
        "observed_time": "2026-06-02 18:00:00",
        "elapsed_hours": 9.0,
        "overdue_hours": 3.0,
        "rescue_events": [
            {
                "event_index": 1,
                "rescue_end_time": "2026-06-01 09:00:00",
                "document_completion_time": "2026-06-01 16:01:00",
                "event_state": "late",
                "elapsed_hours": 7.02,
            },
            {
                "event_index": 2,
                "rescue_end_time": "2026-06-02 09:00:00",
                "document_completion_time": "2026-06-02 18:00:00",
                "event_state": "late",
                "elapsed_hours": 9.0,
            },
            {
                "event_index": 3,
                "document_completion_time": "2026-06-03 11:00:00",
                "event_state": "rescue_end_time_missing",
            },
        ],
    }
    assert results[0]["findings"] == (
        "抢救记录于抢救结束后 9 小时完成（抢救结束时间 2026-06-02 09:00:00；"
        "记录时间 2026-06-02 18:00:00），超过 6 小时要求 3 小时。"
    )
    event_coordinates = _coordinates(results[0])
    assert set(event_coordinates) == {
        ("rescue_record", "most-overdue-rescue-ref", "record_content", "2026-06-02 18:00:00"),
        ("rescue_record", "late-rescue-ref", "record_content", "2026-06-01 16:01:00"),
        ("rescue_record", "missing-end-ref", "record_content", "2026-06-03 11:00:00"),
    }
    assert len(event_coordinates) == len(set(event_coordinates)) == 3
    _repeat_execution, _repeat_reduced, repeat_results = _execute_and_aggregate(
        event_session, ("LX0609-09-01-01",)
    )
    assert _coordinates(repeat_results[0]) == event_coordinates
    assert _fact_ref_source_keys(event_session, execution) == {
        "LX0609-09-01-01": frozenset(
            {
            CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
            "rescue_record",
            }
        )
    }
    rescue_document_refs = set(
        build_material_document_refs(
            "rescue_record",
            tuple(event_session.materials.rows("rescue_record")),
        )
    )
    assert rescue_document_refs.issubset(execution.decisions[0].fact_refs)

    order_session = _session(
        rule_ids=("LX0609-09-01-01",),
        rows_by_source={
            "rescue_record": [],
            CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY: [
                {"order_id": "rescue-order-ref", "status_state": "effective"},
                {"order_id": "rescue-order-ref-2", "status_state": "effective"},
            ],
        },
    )
    order_execution, order_reduced, order_results = _execute_and_aggregate(
        order_session, ("LX0609-09-01-01",)
    )

    assert [(item.final_state.value, item.reason_code) for item in order_reduced] == [
        ("data_gap", "rescue_record_missing_after_trigger")
    ]
    assert dict(order_execution.customer_display_facts) == {
        "LX0609-09-01-01": {
            "failure_kind": "rescue_record_missing_after_trigger",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
        }
    }
    assert order_results[0]["customer_display_facts"] == {
        "failure_kind": "rescue_record_missing_after_trigger",
        "target_document": "rescue_record",
        "source_label": "抢救记录",
    }
    assert order_results[0]["findings"] == "已发现有效抢救医嘱，但未读取到对应抢救记录"
    order_coordinates = _coordinates(order_results[0])
    assert set(order_coordinates) == {
        ("inpat_nondrug_order", "rescue-order-ref", "", ""),
        ("inpat_nondrug_order", "rescue-order-ref-2", "", ""),
    }
    assert len(order_coordinates) == len(set(order_coordinates)) == 2
    assert project_selected_document_evidence(
        decision=order_reduced[0],
        evidence_snapshot=order_session.snapshot,
        evidence_materials=order_session.materials,
    ) == [
        {
            "source_type": "inpat_nondrug_order",
            "source_document_id": "rescue-order-ref",
        },
        {
            "source_type": "inpat_nondrug_order",
            "source_document_id": "rescue-order-ref-2",
        }
    ]
    assert _fact_ref_source_keys(order_session, order_execution) == {
        "LX0609-09-01-01": frozenset(
            {
                CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
                "rescue_record",
            }
        )
    }
    order_document_refs = set(
        build_material_document_refs(
            CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY,
            tuple(order_session.materials.rows(CURRENT_VISIT_RESCUE_ORDER_SOURCE_KEY)),
        )
    )
    assert order_document_refs.issubset(order_execution.decisions[0].fact_refs)
    _repeat_execution, _repeat_reduced, repeat_order_results = _execute_and_aggregate(
        order_session, ("LX0609-09-01-01",)
    )
    assert _coordinates(repeat_order_results[0]) == order_coordinates


@pytest.mark.unit
def test_001_missing_selected_document_id_does_not_borrow_another_document_coordinate():
    session = _session(
        rule_ids=("LX0609-01-01-01",),
        rows_by_source={
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "OTHER-DOCUMENT-ID",
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 09:00:00",
                    "record_content": "入院记录 时间 2026-06-01 09:00:00 正文",
                },
                {
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 10:00:00",
                    "chief_complaint": "腹痛3天后加重",
                },
            ],
        },
    )

    execution, reduced, results = _execute_and_aggregate(session, ("LX0609-01-01-01",))

    assert [(item.final_state.value, item.reason_code) for item in reduced] == [
        ("compliant", "requirement_within_threshold")
    ]
    assert dict(execution.customer_display_facts) == {
        "LX0609-01-01-01": {
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "admission_record",
            "source_label": "入院记录",
            "timeliness_state": "within",
            "threshold_hours": 24,
            "anchor_time": "2026-06-01 08:00:00",
            "observed_time": "2026-06-01 10:00:00",
            "elapsed_hours": 2.0,
            "remaining_hours": 22.0,
        }
    }
    assert results[0]["customer_display_facts"] == dict(
        execution.customer_display_facts
    )["LX0609-01-01-01"]
    assert results[0]["findings"] == "已确认入院记录在入院后 24 小时内完成。"
    assert _coordinates(results[0]) == []
    assert _fact_ref_source_keys(session, execution) == {
        "LX0609-01-01-01": frozenset(
            {"evaluation_context.horizon", "inpat_registration", "admission_record"}
        )
    }


@pytest.mark.unit
def test_001_same_document_id_on_multiple_rows_does_not_use_source_snapshot_fallback():
    """同 ID 并不代表同一材料行，缺行事实时不能投影任一坐标。"""

    rule_ids = ("LX0609-01-01-01",)
    session = _session(
        rule_ids=rule_ids,
        rows_by_source={
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "REUSED-DOCUMENT-ID",
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 09:00:00",
                    "chief_complaint": "腹痛3天",
                },
                {
                    "document_id": "REUSED-DOCUMENT-ID",
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 10:00:00",
                    "chief_complaint": "腹痛3天后加重",
                },
            ],
        },
    )
    execution, reduced, _results = _execute_and_aggregate(session, rule_ids)
    selected = {"LX0609-01-01-01"}
    results_without_display_facts = aggregate_luxian_0609_results(
        wrapper_rules=[
            rule for rule in load_luxian_0609_rules() if rule["rule_id"] in selected
        ],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=(),
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert dict(execution.customer_display_facts)["LX0609-01-01-01"]["observed_time"] == (
        "2026-06-01 09:00:00"
    )
    assert _coordinates(results_without_display_facts[0]) == []


@pytest.mark.unit
def test_001_single_material_row_keeps_source_snapshot_fallback_coordinate():
    """单条可识别材料是尚未迁移行事实前唯一可安全补回的坐标。"""

    rule_ids = ("LX0609-01-01-01",)
    session = _session(
        rule_ids=rule_ids,
        rows_by_source={
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "ONLY-DOCUMENT-ID",
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 10:00:00",
                    "chief_complaint": "腹痛3天",
                }
            ],
        },
    )
    _execution, reduced, _results = _execute_and_aggregate(session, rule_ids)
    selected = {"LX0609-01-01-01"}
    results_without_display_facts = aggregate_luxian_0609_results(
        wrapper_rules=[
            rule for rule in load_luxian_0609_rules() if rule["rule_id"] in selected
        ],
        execution_results=[],
        reduced_decisions=reduced,
        customer_display_facts=(),
        format_evidence=False,
        audit_context={
            "evidence_snapshot": session.snapshot,
            "evidence_materials": session.materials,
        },
    )

    assert _coordinates(results_without_display_facts[0]) == [
        (
            "admission_record",
            "ONLY-DOCUMENT-ID",
            "chief_complaint",
            "2026-06-01 10:00:00",
        )
    ]


@pytest.mark.unit
@pytest.mark.parametrize(
    "material_rows",
    [
        (
            {"document_id": "ONLY-ID-ON-OTHER-ROW"},
            {"record_time": "2026-06-01 10:00:00"},
        ),
        (
            {"document_id": "REUSED-FACT-ID", "record_time": "2026-06-01 09:00:00"},
            {"document_id": "REUSED-FACT-ID", "record_time": "2026-06-01 10:00:00"},
        ),
    ],
)
def test_fact_v2_without_document_id_does_not_backfill_from_multiple_material_rows(
    material_rows: tuple[dict[str, str], ...],
):
    """FactV2 无行 ID 时也必须按材料行数失败关闭，不能只看唯一非空 ID。"""

    decision = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-01-01-02",
            snapshot_hash="a" * 64,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.SATISFIED,
            reason_code="requirement_satisfied",
            fact_refs=("d" * 64,),
            evaluator_version="basic-timeliness-evidence-freeze-v1",
            confidence=1.0,
        )
    )
    result = aggregate_luxian_0609_results(
        wrapper_rules=[{"rule_id": "LX0609-01-01-02", "name": "主诉能导出第一诊断"}],
        execution_results=[],
        reduced_decisions=(decision,),
        audit_context={
            "evidence_snapshot": SimpleNamespace(
                facts=(
                    SimpleNamespace(
                        fact_id="d" * 64,
                        source_snapshot_hash="a" * 64,
                        source_key="admission_record",
                        source_document_id="",
                    ),
                ),
                observations=(),
            ),
            "evidence_materials": SimpleNamespace(
                rows=lambda source_key: (
                    material_rows if source_key == "admission_record" else ()
                )
            ),
        },
    )[0]

    assert "customer_evidence" not in result


@pytest.mark.unit
def test_document_refs_require_materials_for_binding():
    """逐文书引用必须携带可验证材料，不能仅凭全局引用存在而放行。"""

    session = _session(
        rule_ids=("LX0609-01-01-01",),
        rows_by_source={
            "inpat_registration": [
                {"admission_datetime": "2026-06-01 08:00:00"}
            ],
            "admission_record": [
                {
                    "document_id": "ADM-1",
                    "document_title": "入院记录",
                    "record_time": "2026-06-01 10:00:00",
                    "chief_complaint": "腹痛3天",
                }
            ],
        },
    )
    execution, reduced, _results = _execute_and_aggregate(session, ("LX0609-01-01-01",))
    document_ref = build_material_document_refs(
        "admission_record", tuple(session.materials.rows("admission_record"))
    )[0]
    document_ref_reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=(replace(execution.decisions[0], fact_refs=(document_ref,)),),
        expected_rule_ids=("LX0609-01-01-01",),
        snapshot=session.snapshot,
    )

    assert [(item.final_state.value, item.reason_code) for item in reduced] == [
        ("compliant", "requirement_within_threshold")
    ]
    assert _fact_ref_source_keys(session, execution) == {
        "LX0609-01-01-01": frozenset(
            {"evaluation_context.horizon", "inpat_registration", "admission_record"}
        )
    }
    assert [(item.final_state.value, item.reason_code) for item in document_ref_reduced] == [
        ("technical_error", "snapshot_mismatch")
    ]
