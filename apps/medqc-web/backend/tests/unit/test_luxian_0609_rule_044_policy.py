from __future__ import annotations

from datetime import datetime

import pytest

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609.customer_evidence_enrichment import (
    project_selected_document_evidence,
)
from app.services.luxian_0609.decision_binding import (
    bind_and_reduce_luxian_0609_rule_decisions,
)
from app.services.luxian_0609.evidence_snapshot_provider import (
    SnapshotSourceRows,
    build_luxian_0609_evidence_read_session,
)
from app.services.luxian_0609_result_aggregator import safe_luxian_0609_customer_display_facts


def _documents(
    *,
    transfusion_time: str | None = "2026-08-20 14:00:00",
    applications: list[dict] | None = None,
) -> dict:
    event = {"transfuse_variety": "红细胞"}
    if transfusion_time is not None:
        event["transfution_datetime"] = transfusion_time
    return {
        "mr_bloodtrans": [event],
        "bloodtrans_record": [{"record_content": "已实际输注红细胞2U。"}],
        "blood_application": applications or [],
        "daily_course_record": [],
        "__logical_source_states__": {
            "blood_application": "available" if applications else "empty",
            "daily_course_record": "empty",
        },
    }


def _application(**overrides: str) -> dict:
    row = {
        "application_id": "BA-001",
        "request_datetime": "2026-08-20 09:00:00",
        "reason_for_blood": "纠正贫血",
        "hemoglobin": "68 g/L",
    }
    row.update(overrides)
    return row


def test_044_accepts_complete_pretransfusion_application_without_separate_course_note() -> None:
    status, reason_code, facts = transfusion._programmatic_044_status(
        _documents(applications=[_application()])
    )

    assert status == "compliant"
    assert reason_code == "pretransfusion_assessment_complete"
    assert facts["application_time"] == "2026-08-20 09:00:00"
    assert facts["transfusion_time"] == "2026-08-20 14:00:00"
    assert facts["assessment_indicators"] == ["hemoglobin"]
    assert facts["missing_fields"] == []


def test_044_requires_both_application_reason_and_objective_indicator() -> None:
    missing_reason = _application(reason_for_blood="")
    missing_indicator = _application(hemoglobin="")

    reason_result = transfusion._programmatic_044_status(
        _documents(applications=[missing_reason])
    )
    indicator_result = transfusion._programmatic_044_status(
        _documents(applications=[missing_indicator])
    )

    assert reason_result[0:2] == (
        "non_compliant",
        "pretransfusion_assessment_incomplete",
    )
    assert reason_result[2]["missing_fields"] == ["application_reason"]
    assert indicator_result[0:2] == (
        "non_compliant",
        "pretransfusion_assessment_incomplete",
    )
    assert indicator_result[2]["missing_fields"] == ["laboratory_indicator"]


def test_044_extracts_numeric_indicator_from_legacy_application_content() -> None:
    application = _application(
        reason_for_blood="",
        hemoglobin="",
        record_content="因血红蛋白65g/L申请输注悬浮红细胞2U。",
    )

    status, reason_code, facts = transfusion._programmatic_044_status(
        _documents(applications=[application])
    )

    assert status == "non_compliant"
    assert reason_code == "pretransfusion_assessment_incomplete"
    assert facts["assessment_indicators"] == ["hemoglobin"]
    assert facts["missing_fields"] == ["application_reason"]


def test_044_rejects_application_completed_after_transfusion() -> None:
    status, reason_code, facts = transfusion._programmatic_044_status(
        _documents(
            applications=[
                _application(request_datetime="2026-08-20 15:00:00")
            ]
        )
    )

    assert status == "non_compliant"
    assert reason_code == "pretransfusion_assessment_time_conflict"
    assert facts["failure_kind"] == "pretransfusion_assessment_time_conflict"
    assert facts["elapsed_minutes"] == 60


def test_044_requires_application_time_to_strictly_precede_transfusion() -> None:
    status, reason_code, facts = transfusion._programmatic_044_status(
        _documents(
            applications=[
                _application(request_datetime="2026-08-20 14:00:00")
            ]
        )
    )

    assert status == "non_compliant"
    assert reason_code == "pretransfusion_assessment_time_conflict"
    assert facts["elapsed_minutes"] == 0


def test_044_returns_data_gap_when_authoritative_times_are_missing() -> None:
    missing_application_time = _application(request_datetime="")

    application_result = transfusion._programmatic_044_status(
        _documents(applications=[missing_application_time])
    )
    transfusion_result = transfusion._programmatic_044_status(
        _documents(transfusion_time=None, applications=[_application()])
    )

    assert application_result[0:2] == (
        "data_gap",
        "authoritative_time_missing",
    )
    assert application_result[2]["missing_time_fields"] == ["application_time"]
    assert transfusion_result[0:2] == (
        "data_gap",
        "authoritative_time_missing",
    )
    assert transfusion_result[2]["missing_time_fields"] == ["transfusion_time"]


def test_044_customer_projection_preserves_controlled_times_and_conflict_delta() -> None:
    facts = safe_luxian_0609_customer_display_facts(
        rule_id="LX0609-07-01-02",
        raw={
            "failure_kind": "pretransfusion_assessment_time_conflict",
            "performed_transfusion_confirmed": True,
            "checked_fields": ["application_reason", "laboratory_indicator"],
            "missing_fields": [],
            "application_time": "2026-08-20 15:00:00",
            "transfusion_time": "2026-08-20 14:00:00",
            "elapsed_minutes": 60,
        },
    )

    assert facts == {
        "failure_kind": "pretransfusion_assessment_time_conflict",
        "performed_transfusion_confirmed": True,
        "checked_fields": ["application_reason", "laboratory_indicator"],
        "missing_fields": [],
        "application_time": "2026-08-20 15:00:00",
        "transfusion_time": "2026-08-20 14:00:00",
        "elapsed_minutes": 60,
    }


@pytest.mark.asyncio
async def test_044_projects_application_and_transfusion_record_locators() -> None:
    """044 的真实 native 决策经 Binding 和公共投影保留两份判定文书。"""

    rows_by_source = {
        "mr_bloodtrans": [
            {"transfution_datetime": datetime(2026, 8, 20, 14, 0)}
        ],
        "blood_application": [
            {
                "application_id": "BA-001",
                "document_id": "BA-001",
                "request_datetime": "2026-08-20 09:00:00",
                "reason_for_blood": "纠正贫血",
                "hemoglobin": "68 g/L",
            }
        ],
        "bloodtrans_record": [
            {
                "document_id": "BT-001",
                "record_content": "2026-08-20 14:00输血开始，已实际输注红细胞2U。",
                "record_time": "2026-08-20 14:10:00",
            }
        ],
    }

    def read(**kwargs: object) -> SnapshotSourceRows:
        source_key = str(kwargs["source_key"])
        return SnapshotSourceRows.create(
            source_key=source_key,
            rows=rows_by_source.get(source_key, []),
            truncated=False,
            limit_rows=50,
        )

    session = build_luxian_0609_evidence_read_session(
        selected_rule_ids=("LX0609-07-01-02",),
        institute_id="044-evidence-institute",
        patient_id="044-evidence-patient",
        visit_id="044-evidence-visit",
        source_schema=None,
        created_at="2026-09-06T12:00:00+08:00",
        row_reader=read,
    )
    execution = await transfusion.execute_luxian_0609_native_transfusion_rules(
        rule_ids=("LX0609-07-01-02",),
        wrapper_rules=[{"rule_id": "LX0609-07-01-02", "rule_name": "输血前评估"}],
        evidence_payload=None,
        institute_id="044-evidence-institute",
        patient_id="044-evidence-patient",
        visit_id="044-evidence-visit",
        source_schema=None,
        llm_client=None,
        evidence_materials=session.materials,
        evidence_snapshot=session.snapshot,
        decision_rule_ids=("LX0609-07-01-02",),
    )
    reduced = bind_and_reduce_luxian_0609_rule_decisions(
        decisions=execution.decisions,
        expected_rule_ids=("LX0609-07-01-02",),
        snapshot=session.snapshot,
        evidence_materials=session.materials,
    )

    assert len(reduced) == 1
    assert reduced[0].final_state.value == "compliant"
    projected = project_selected_document_evidence(
        decision=reduced[0],
        evidence_snapshot=session.snapshot,
        evidence_materials=session.materials,
    )
    assert projected is not None
    assert {
        (item["source_type"], item["source_document_id"])
        for item in projected
    } == {("blood_application", "BA-001"), ("bloodtrans_record", "BT-001")}
