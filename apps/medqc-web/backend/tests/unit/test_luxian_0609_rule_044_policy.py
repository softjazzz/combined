from __future__ import annotations

from app.services.luxian_0609 import native_transfusion_execution as transfusion
from app.services.luxian_0609_result_aggregator import (
    _customer_evidence_from_display_facts,
    safe_luxian_0609_customer_display_facts,
)


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
        rule_id="LX0609-044",
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


def test_044_projects_application_and_transfusion_record_locators() -> None:
    raw = {
        "verification_kind": "pretransfusion_assessment_complete",
        "performed_transfusion_confirmed": True,
        "checked_fields": ["application_reason", "laboratory_indicator"],
        "missing_fields": [],
        "application_time": "2026-08-20 09:00:00",
        "transfusion_time": "2026-08-20 14:00:00",
        "source_document_refs": [
            {
                "source_type": "blood_application",
                "source_document_id": "BA-001",
            },
            {
                "source_type": "bloodtrans_record",
                "source_document_id": "BT-001",
            },
        ],
    }

    assert _customer_evidence_from_display_facts(
        rule_id="LX0609-044", raw=raw
    ) == raw["source_document_refs"]
    assert "source_document_refs" not in (
        safe_luxian_0609_customer_display_facts(rule_id="LX0609-044", raw=raw)
        or {}
    )
