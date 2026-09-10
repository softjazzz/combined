from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    project_customer_safe_result_item,
)
from app.services.luxian_0609.customer_rule_package import LUXIAN_0609_RULE_SET_KEY
from app.services.luxian_0609.decision_model import (
    ApplicabilityState,
    EvidenceState,
    QcDirection,
    RuleDecision,
)
from app.services.luxian_0609.decision_reducer import reduce_luxian_0609_rule_decision
from app.services.luxian_0609.execution import (
    Luxian0609ExecutionContext,
    aggregate_luxian_0609_orchestrated_results,
    prepare_luxian_0609_execution,
)
from app.services.luxian_0609.native_package import (
    load_luxian_0609_dependency_inventory,
    resolve_package_entry_execution_rule_ids,
)
from app.services.luxian_0609.rule_decision_settings import (
    RULE_DECISION_ROLLOUT_GROUPS,
)
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
from app.services.sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
)
from app.services.qc_workspace.canonical_result_store import (
    envelope_item_from_rule_result,
    safe_customer_display_facts,
)
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_executor_customer_display_facts,
)


class _Rows:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def mappings(self) -> "_Rows":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _ReadSession:
    def __init__(self, result_sets: list[list[dict[str, Any]]]):
        self._result_sets = iter(result_sets)

    def execute(self, _statement: Any) -> _Rows:
        return _Rows(next(self._result_sets))

    def close(self) -> None:
        return None


class _WriteSession:
    def __init__(self):
        self.statements: list[Any] = []

    def execute(self, statement: Any) -> None:
        self.statements.append(statement)


class _BrokenReadSession:
    def execute(self, _statement: Any) -> _Rows:
        raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))

    def close(self) -> None:
        return None


@pytest.mark.parametrize(
    ("rule_id", "raw", "expected"),
    [
        (
            "LX0609-024",
            {
                "failure_kind": "lymph_node_dissection_not_documented",
                "performed_surgery_confirmed": True,
                "malignant_surgery_confirmed": True,
                "checked_sources": ["surgery_record"],
            },
            {
                "failure_kind": "lymph_node_dissection_not_documented",
                "performed_surgery_confirmed": True,
                "malignant_surgery_confirmed": True,
                "checked_sources": ["surgery_record"],
            },
        ),
        (
            "LX0609-025",
            {
                "failure_kind": "implant_information_incomplete",
                "performed_surgery_confirmed": True,
                "missing_fields": ["implant_material"],
                "implant_event_details": [
                    {
                        "event_ref": "implant-event-1",
                        "missing_fields": ["implant_material"],
                        "implant_names": ["人工髋关节"],
                        "source_document_id": "surgery-record-025",
                    }
                ],
                "source_label": "手术记录",
                "source_document_type": "surgery_record",
                "source_document_id": "surgery-record-025",
            },
            {
                "failure_kind": "implant_information_incomplete",
                "performed_surgery_confirmed": True,
                "source_label": "手术记录",
                "source_document_type": "surgery_record",
                "missing_fields": ["implant_material"],
                "implant_event_details": [
                    {
                        "event_position": 1,
                        "missing_fields": ["implant_material"],
                        "implant_names": ["人工髋关节"],
                    }
                ],
            },
        ),
        (
            "LX0609-028",
            {
                "failure_kind": "prophylaxis_duration_over_48h",
                "incision_class": "I",
                "start_time": "2026-09-01 08:00:00",
                "end_time": "2026-09-03 09:00:00",
                "duration_hours": 49.0,
                "threshold_hours": 48,
            },
            {
                "failure_kind": "prophylaxis_duration_over_48h",
                "incision_class": "I",
                "start_time": "2026-09-01 08:00:00",
                "end_time": "2026-09-03 09:00:00",
                "duration_hours": 49.0,
                "threshold_hours": 48,
            },
        ),
        (
            "LX0609-029",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "presurg_summary",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "presurg_summary",
                "surgery_trigger_kind": "performed_surgery",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-030",
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_record",
                "performed_surgery_confirmed": True,
            },
            {
                "failure_kind": "surgery_document_missing",
                "target_document": "surgery_record",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-032",
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
            {
                "failure_kind": "surgery_document_blank",
                "target_document": "surgery_safecheck_record",
                "performed_surgery_confirmed": True,
            },
        ),
        (
            "LX0609-034",
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
            },
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
            },
        ),
        (
            "LX0609-035",
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
            },
            {
                "failure_kind": "anesthesia_consent_missing",
                "performed_anesthesia_confirmed": True,
                "consent_state": "missing",
                "checked_sources": ["consent_form"],
            },
        ),
        (
            "LX0609-036",
            {
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": ["preane_surveil_record"],
            },
            {
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": ["preane_surveil_record"],
            },
        ),
        (
            "LX0609-037",
            {
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": ["postane_surveil_record"],
            },
            {
                "failure_kind": "anesthesia_visit_missing",
                "performed_anesthesia_confirmed": True,
                "missing_visit_sources": ["postane_surveil_record"],
            },
        ),
        (
            "LX0609-039",
            {
                "failure_kind": "preop_discussion_missing",
                "performed_surgery_confirmed": True,
                "emergency_rescue_exception_absent": True,
                "checked_sources": ["presurg_discussion"],
            },
            {
                "failure_kind": "preop_discussion_missing",
                "performed_surgery_confirmed": True,
                "emergency_rescue_exception_absent": True,
                "checked_sources": ["presurg_discussion"],
            },
        ),
    ],
)
def test_store_projects_only_finalizer_validated_customer_facts(
    rule_id: str,
    raw: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Store 只搬运共享合同已经验证的事实，不再维护规则号 fallback。"""

    validated = validate_luxian_0609_executor_customer_display_facts(
        rule_id=rule_id,
        raw=raw,
    )

    assert validated == expected
    assert safe_customer_display_facts(
        {"customer_display_facts": raw},
        rule_id=rule_id,
    ) == expected


@pytest.mark.parametrize(
    ("rule_id", "raw"),
    [
        ("LX0609-025", {"missing_fields": ["implant_material"]}),
        (
            "LX0609-025",
            {
                "failure_kind": "implant_information_incomplete",
                "performed_surgery_confirmed": True,
                "missing_fields": ["implant_material"],
                "implant_event_details": [
                    {
                        "event_ref": "implant-event-private",
                        "missing_fields": ["implant_material"],
                        "implant_names": ["人工髋关节"],
                        "source_document_id": "surgery-record-025",
                    }
                ],
                "source_label": "手术记录",
                "source_document_type": "surgery_record",
                "source_document_id": "surgery-record-025",
                "patient_id": "PRIVATE-025",
            },
        ),
        ("LX0609-999", {"failure_kind": "unknown"}),
    ],
)
def test_store_rejects_unvalidated_or_unknown_customer_facts(
    rule_id: str,
    raw: dict[str, Any],
) -> None:
    assert safe_customer_display_facts(
        {"customer_display_facts": raw},
        rule_id=rule_id,
    ) == {}


def test_store_has_no_rule_specific_customer_fact_contract_or_aggregator_dependency() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "app/services/qc_workspace/canonical_result_store.py"
    ).read_text(encoding="utf-8")

    assert re.search(r"LX0609-\d{3}", source) is None
    assert "luxian_0609_result_aggregator import" not in source
    assert "surgery_document_targets" not in source
    assert "historical_evidence_missing" not in source


def _selected_job(*, legacy_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": "job-current",
        "created_by": "reviewer-a",
        "status": "completed",
        "created_at": "2026-07-30T10:00:00",
        "finished_at": "2026-07-30T10:01:00",
        "record_ids": ["visit-1"],
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
        },
        "items": legacy_items or [],
    }


def test_terminal_reevaluation_candidates_require_latest_running_result_without_active_final_job():
    record_ref = {
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
    }
    completed_running = {
        "id": "job-running",
        "scope": "all",
        "status": "completed",
        "created_at": datetime(2026, 8, 13, 8, 0, 0),
        "finished_at": datetime(2026, 8, 13, 8, 10, 0),
        "filters_json": json.dumps(
            {
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09",
                "record_scene_snapshot": [
                    {**record_ref, "record_scene": "running", "resolved_scene": "running"}
                ],
            }
        ),
        **record_ref,
    }
    session = _ReadSession([[completed_running], []])

    result = CustomQCWorkspaceService().find_terminal_reevaluation_candidates(
        record_refs=[record_ref],
        session_factory=lambda: session,
    )

    assert [item.as_dict() for item in result] == [record_ref]


def test_terminal_reevaluation_candidates_skip_completed_or_active_final_jobs():
    record_refs = [
        {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"},
        {"institute_id": "inst-1", "patient_id": "patient-2", "visit_id": "visit-2"},
    ]
    completed_rows = [
        {
            "id": "job-final",
            "scope": "final",
            "status": "completed",
            "created_at": datetime(2026, 8, 13, 9, 0, 0),
            "finished_at": datetime(2026, 8, 13, 9, 10, 0),
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
            **record_refs[0],
        },
        {
            "id": "job-running-2",
            "scope": "running",
            "status": "completed",
            "created_at": datetime(2026, 8, 13, 8, 0, 0),
            "finished_at": datetime(2026, 8, 13, 8, 10, 0),
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
            **record_refs[1],
        },
    ]
    active_final = {
        "scope": "final",
        "status": "queued",
        "filters_json": json.dumps(
            {
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09",
                "record_refs": [record_refs[1]],
            }
        ),
    }
    session = _ReadSession([completed_rows, [active_final]])

    result = CustomQCWorkspaceService().find_terminal_reevaluation_candidates(
        record_refs=record_refs,
        session_factory=lambda: session,
    )

    assert result == ()


def test_completed_projection_indexes_summary_jobs_without_heavy_job_hydration(monkeypatch):
    """全院投影只读取结果选择必需字段，不能为每份病历反复完整解析任务。"""

    def job_row(job_id: str, visit_id: str) -> dict[str, Any]:
        return {
            "id": job_id,
            "status": "completed",
            "created_at": "2026-08-08T10:00:00",
            "finished_at": "2026-08-08T10:01:00",
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
            "record_ids_json": json.dumps([visit_id]),
            "summary_json": "{}",
        }

    def envelope(job_id: str, patient_id: str, visit_id: str) -> dict[str, Any]:
        return {
            "root_job_id": job_id,
            "job_id": job_id,
            "institute_id": "inst-1",
            "patient_id": patient_id,
            "visit_id": visit_id,
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "envelope_json": json.dumps(
                {
                    "schema_version": "lx0609-record-result-envelope-v1",
                    "delivery_mode": "canonical_straight_through",
                    "items": [
                        {
                            "rule_id": "LX0609-001",
                            "status": "compliant",
                            "result_status": "compliant",
                            "is_compliant": True,
                        }
                    ],
                }
            ),
        }

    session = _ReadSession(
        [
            [job_row("job-1", "visit-1"), job_row("job-2", "visit-2")],
            [envelope("job-1", "patient-1", "visit-1"), envelope("job-2", "patient-2", "visit-2")],
        ]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(
        workspace_module,
        "_row_to_batch_job",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("全院摘要不得完整水合任务 JSON")
        ),
    )
    original_selector = workspace_module.select_latest_authoritative_record_result_job
    selector_calls = 0

    def counted_selector(*args, **kwargs):
        nonlocal selector_calls
        selector_calls += 1
        return original_selector(*args, **kwargs)

    monkeypatch.setattr(
        workspace_module,
        "select_latest_authoritative_record_result_job",
        counted_selector,
    )

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"},
            {"institute_id": "inst-1", "patient_id": "patient-2", "visit_id": "visit-2"},
        ],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result[("inst-1", "patient-1", "visit-1")]["status"] == "ready"
    assert result[("inst-1", "patient-2", "visit-2")]["status"] == "ready"
    assert selector_calls <= 4


def test_completed_projection_rejects_removed_rule_from_current_catalog(monkeypatch):
    """病历池摘要也不能把旧规则目录项混入当前代次。"""

    identity = ("inst-1", "patient-1", "visit-1")
    job = {
        "id": "job-current",
        "status": "completed",
        "created_at": "2026-08-08T10:00:00",
        "finished_at": "2026-08-08T10:01:00",
        "filters_json": json.dumps(
            {
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09",
            }
        ),
        "record_ids_json": json.dumps([identity[2]]),
        "summary_json": "{}",
    }
    envelope = {
        "root_job_id": job["id"],
        "job_id": job["id"],
        "institute_id": identity[0],
        "patient_id": identity[1],
        "visit_id": identity[2],
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "envelope_json": json.dumps(
            {
                "schema_version": "lx0609-record-result-envelope-v1",
                "delivery_mode": "canonical_straight_through",
                "items": [
                    {
                        "rule_id": "LX0609-001",
                        "status": "compliant",
                        "result_status": "compliant",
                        "is_compliant": True,
                    },
                    {
                        "rule_id": "LX0609-999",
                        "status": "compliant",
                        "result_status": "compliant",
                        "is_compliant": True,
                    },
                ],
            },
            ensure_ascii=False,
        ),
    }
    session = _ReadSession([[job], [envelope]])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
            }
        ],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
        include_items=True,
    )

    assert result[identity] == {
        "status": "technical_error",
        "reason_code": "canonical_result_envelope_invalid",
    }


def test_completed_projection_filters_known_customer_excluded_rule(monkeypatch):
    """已知但不在客户交付范围的历史规则应过滤，而不是被当成未知规则。"""

    identity = ("inst-1", "patient-1", "visit-1")
    job = {
        "id": "job-current",
        "status": "completed",
        "created_at": "2026-08-08T10:00:00",
        "finished_at": "2026-08-08T10:01:00",
        "filters_json": json.dumps(
            {"rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09"}
        ),
        "record_ids_json": json.dumps([identity[2]]),
        "summary_json": "{}",
    }
    envelope = {
        "root_job_id": job["id"],
        "job_id": job["id"],
        "institute_id": identity[0],
        "patient_id": identity[1],
        "visit_id": identity[2],
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "envelope_json": json.dumps(
            {
                "schema_version": "lx0609-record-result-envelope-v1",
                "delivery_mode": "canonical_straight_through",
                "items": [
                    {
                        "rule_id": "LX0609-033",
                        "status": "not_executed",
                        "result_status": "not_executed",
                        "is_compliant": None,
                    },
                    {
                        "rule_id": "LX0609-001",
                        "status": "compliant",
                        "result_status": "compliant",
                        "is_compliant": True,
                    },
                ],
            },
            ensure_ascii=False,
        ),
    }
    session = _ReadSession([[job], [envelope]])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {
                "institute_id": identity[0],
                "patient_id": identity[1],
                "visit_id": identity[2],
            }
        ],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
        include_items=True,
    )

    projection = result[identity]
    assert projection["status"] == "ready"
    assert projection["total_rule_count"] == 1
    assert projection["items"][0]["rule_id"] == "LX0609-001"


def test_bulk_record_result_dtos_read_complete_canonical_items_in_one_batch(monkeypatch):
    job = {
        "id": "job-1",
        "status": "completed",
        "created_at": "2026-08-08T10:00:00",
        "finished_at": "2026-08-08T10:01:00",
        "filters_json": json.dumps(
            {
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09",
            }
        ),
        "record_ids_json": json.dumps(["visit-1"]),
        "summary_json": "{}",
    }
    envelope = {
        "root_job_id": "job-1",
        "job_id": "job-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "envelope_json": json.dumps(
            {
                "schema_version": "lx0609-record-result-envelope-v1",
                "delivery_mode": "canonical_straight_through",
                "record_ref": "rec_0123456789abcdef01234567",
                "items": [
                    {
                        "rule_id": "LX0609-001",
                        "status": "non_compliant",
                        "result_status": "non_compliant",
                        "is_compliant": False,
                        "conclusion": "未在规定时限内完成。",
                    }
                ],
            },
            ensure_ascii=False,
        ),
    }
    session = _ReadSession([[job], [envelope]])

    result = CustomQCWorkspaceService().build_latest_luxian_0609_record_result_dtos(
        record_refs=[
            {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}
        ],
        session_factory=lambda: session,
    )

    dto = result[("inst-1", "patient-1", "visit-1")]
    assert dto["state"] == "ready"
    assert dto["record_ref"] == "rec_0123456789abcdef01234567"
    assert dto["items"][0]["rule_id"] == "LX0609-001"
    assert dto["items"][0]["source_document"] == "入院记录"


def test_bulk_record_result_dtos_preserve_canonical_projection_failure_reason(monkeypatch):
    identity = ("inst-1", "patient-1", "visit-1")
    service = CustomQCWorkspaceService()
    monkeypatch.setattr(
        service,
        "build_luxian_0609_completed_record_result_summaries",
        lambda **_kwargs: {
            identity: {
                "status": "technical_error",
                "reason_code": "canonical_result_envelope_invalid",
            }
        },
    )

    result = service.build_latest_luxian_0609_record_result_dtos(
        record_refs=[
            {"institute_id": identity[0], "patient_id": identity[1], "visit_id": identity[2]}
        ]
    )

    assert result[identity]["state"] == "technical_error"
    assert result[identity]["reason_code"] == "canonical_result_envelope_invalid"


def test_single_record_result_does_not_fall_back_to_legacy_items_when_envelope_is_missing(
    monkeypatch,
):
    legacy_item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "rule_id": "LX0609-001",
        "status": "non_compliant",
        "conclusion": "旧任务结果不得交付。",
    }
    selected_job = _selected_job(legacy_items=[legacy_item])
    session = _ReadSession([[selected_job], []])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService,
        "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )

    result = CustomQCWorkspaceService().get_latest_luxian_0609_record_result(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        expected_rule_ids=["LX0609-001"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_missing"
    assert result["items"] == []
    assert result["result_rule_count"] == 0


def test_single_record_result_does_not_convert_database_read_error_to_not_found(monkeypatch):
    monkeypatch.setattr(workspace_module, "_session", _BrokenReadSession)

    with pytest.raises(OperationalError, match="database unavailable"):
        CustomQCWorkspaceService().get_latest_luxian_0609_record_result(
            institute_id="inst-1",
            patient_id="patient-1",
            visit_id="visit-1",
            expected_rule_ids=["LX0609-001"],
            rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09",
        )


def test_completed_projection_does_not_fall_back_when_newer_root_job_lacks_envelope(
    monkeypatch,
):
    """病历池不能用较旧 Envelope 遮蔽较新完成任务的交付缺口。"""

    old_job = {
        **_selected_job(),
        "id": "job-old",
        "created_at": "2026-08-08T09:00:00",
        "finished_at": "2026-08-08T09:01:00",
        "filters_json": json.dumps(_selected_job()["filters"]),
        "record_ids_json": json.dumps(["visit-1"]),
        "job_kind": "parent",
        "parent_job_id": None,
    }
    newer_job = {
        **old_job,
        "id": "job-new",
        "created_at": "2026-08-08T10:00:00",
        "finished_at": "2026-08-08T10:01:00",
    }
    old_envelope = {
        "root_job_id": "job-old",
        "job_id": "job-old",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "envelope_json": json.dumps(
            {
                "schema_version": "lx0609-record-result-envelope-v1",
                "delivery_mode": "canonical_straight_through",
                "items": [
                    {
                        "rule_id": "LX0609-001",
                        "status": "compliant",
                        "result_status": "compliant",
                        "is_compliant": True,
                    }
                ],
            }
        ),
    }
    session = _ReadSession([[old_job, newer_job], [old_envelope]])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row, **_kwargs: dict(row))

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}
        ],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result[("inst-1", "patient-1", "visit-1")] == {
        "status": "technical_error",
        "reason_code": "canonical_envelope_missing",
    }


def test_completed_projection_ignores_old_rule_version_envelopes(monkeypatch):
    """旧版结果已存在不代表当前规则版本的 Envelope 缺失。"""

    old_version_job = {
        **_selected_job(),
        "id": "job-old-version",
        "created_at": "2026-08-08T09:00:00",
        "finished_at": "2026-08-08T09:01:00",
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-08",
        },
        "record_ids_json": json.dumps(["visit-1"]),
        "job_kind": "parent",
        "parent_job_id": None,
    }
    newer_old_version_job = {
        **old_version_job,
        "id": "job-newer-old-version",
        "created_at": "2026-08-08T10:00:00",
        "finished_at": "2026-08-08T10:01:00",
    }
    old_version_envelope = {
        "root_job_id": "job-old-version",
        "job_id": "job-old-version",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-08",
        "envelope_json": "{}",
    }
    newer_old_version_envelope = {
        **old_version_envelope,
        "root_job_id": "job-newer-old-version",
        "job_id": "job-newer-old-version",
    }
    session = _ReadSession(
        [[old_version_job, newer_old_version_job], [old_version_envelope, newer_old_version_envelope]]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row, **_kwargs: dict(row))

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}
        ],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result[("inst-1", "patient-1", "visit-1")] == {"status": "not_run"}


def test_completed_projection_keeps_current_ready_when_newer_job_only_has_old_version_envelope(
    monkeypatch,
):
    current_job = {
        **_selected_job(),
        "id": "job-current",
        "created_at": "2026-08-08T09:00:00",
        "finished_at": "2026-08-08T09:01:00",
        "record_ids_json": json.dumps(["visit-1"]),
        "job_kind": "parent",
        "parent_job_id": None,
    }
    newer_old_version_job = {
        **current_job,
        "id": "job-newer-old-version",
        "created_at": "2026-08-08T10:00:00",
        "finished_at": "2026-08-08T10:01:00",
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-08",
        },
    }
    current_envelope = {
        "root_job_id": "job-current",
        "job_id": "job-current",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "envelope_json": json.dumps(
            {
                "schema_version": "lx0609-record-result-envelope-v1",
                "delivery_mode": "canonical_straight_through",
                "items": [
                    {
                        "rule_id": "LX0609-001",
                        "status": "compliant",
                        "result_status": "compliant",
                        "is_compliant": True,
                    }
                ],
            }
        ),
    }
    old_version_envelope = {
        **current_envelope,
        "root_job_id": "job-newer-old-version",
        "job_id": "job-newer-old-version",
        "rule_set_version": "2026-06-08",
    }
    session = _ReadSession([[current_job, newer_old_version_job], [current_envelope, old_version_envelope]])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row, **_kwargs: dict(row))

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}
        ],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result[("inst-1", "patient-1", "visit-1")]["status"] == "ready"


def test_completed_projection_treats_current_job_with_only_old_version_envelope_as_missing(
    monkeypatch,
):
    current_job = {
        **_selected_job(),
        "id": "job-current-with-old-envelope",
        "record_ids_json": json.dumps(["visit-1"]),
        "job_kind": "parent",
        "parent_job_id": None,
    }
    old_version_envelope = {
        "root_job_id": "job-current-with-old-envelope",
        "job_id": "job-current-with-old-envelope",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-08",
        "envelope_json": "{}",
    }
    session = _ReadSession([[current_job], [old_version_envelope]])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row, **_kwargs: dict(row))

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}
        ],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result[("inst-1", "patient-1", "visit-1")] == {
        "status": "technical_error",
        "reason_code": "canonical_envelope_missing",
    }


@pytest.mark.parametrize(
    "items",
    [
        [
            {
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            }
        ],
        [
            {
                "rule_id": "LX0609-001",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
            {
                "rule_code": "LX0609-001",
                "status": "non_compliant",
                "result_status": "non_compliant",
                "is_compliant": False,
            },
        ],
    ],
)
def test_completed_projection_rejects_canonical_items_without_unique_rule_id(
    monkeypatch,
    items,
):
    job = {
        **_selected_job(),
        "id": "job-invalid-items",
        "record_ids_json": json.dumps(["visit-1"]),
        "job_kind": "parent",
        "parent_job_id": None,
    }
    envelope = {
        "root_job_id": "job-invalid-items",
        "job_id": "job-invalid-items",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "envelope_json": json.dumps(
            {
                "schema_version": "lx0609-record-result-envelope-v1",
                "delivery_mode": "canonical_straight_through",
                "items": items,
            }
        ),
    }
    session = _ReadSession([[job], [envelope]])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row, **_kwargs: dict(row))

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}
        ],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result[("inst-1", "patient-1", "visit-1")] == {
        "status": "technical_error",
        "reason_code": "canonical_result_envelope_invalid",
    }


def test_single_record_result_adds_authoritative_presentation_metadata_without_mutating_envelope(
    monkeypatch,
):
    canonical_item = {
        "rule_id": "LX0609-025",
        "rule_name": "植入物相关记录",
        "status": "uncertain",
        "result_status": "uncertain",
        "reason_code": "customer_explanation_incomplete",
        "is_compliant": None,
        "conclusion": "引擎结论原文",
        "detail": "引擎明细原文",
        "evidence": [
            {
                "source_ref": "src_1234567890abcdef12345678",
                "evidence_excerpt": "引擎保存的证据摘录",
            }
        ],
    }
    original_canonical_item = json.loads(json.dumps(canonical_item, ensure_ascii=False))
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": "rec_1234567890abcdef12345678",
        "items": [canonical_item],
    }
    original_envelope_json = json.dumps(envelope, ensure_ascii=False)
    session = _ReadSession(
        [
            [_selected_job()],
            [{"envelope_json": original_envelope_json}],
        ]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService,
        "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )
    monkeypatch.setattr(
        workspace_module,
        "project_customer_safe_result_item",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("读取端不得再次投影")),
    )
    monkeypatch.setattr(
        workspace_module,
        "attach_authorized_evidence_excerpts",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("读取端不得重读 Bundle")),
    )

    result = CustomQCWorkspaceService().get_latest_luxian_0609_record_result(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        expected_rule_ids=["LX0609-025"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "ready"
    assert result["record_ref"] == "rec_1234567890abcdef12345678"
    assert result["items"] == [
        {
            **original_canonical_item,
            "source_document": "手术记录",
            "qc_point": "未记录植入物名称、种类、规格或型号、材质及数量等信息",
        }
    ]
    assert canonical_item == original_canonical_item
    assert json.dumps(envelope, ensure_ascii=False) == original_envelope_json


def test_single_record_result_projects_all_rule_master_metadata_in_envelope_order(monkeypatch):
    master_entries = load_luxian_0609_rule_master()
    customer_entries = [
        entry
        for entry in master_entries
        if entry.rule_id not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    ]
    rule_ids = [entry.rule_id for entry in customer_entries]
    canonical_items = [
        {
            "rule_id": entry.rule_id,
            "status": "compliant",
            "result_status": "compliant",
            "is_compliant": True,
            "reason_code": "requirement_satisfied",
        }
        for entry in reversed(customer_entries)
    ]
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": "rec_1234567890abcdef12345678",
        "items": canonical_items,
    }
    session = _ReadSession(
        [
            [_selected_job()],
            [{"envelope_json": json.dumps(envelope, ensure_ascii=False)}],
        ]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService,
        "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )

    result = CustomQCWorkspaceService().build_latest_single_record_result_dto(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        expected_rule_ids=rule_ids,
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "ready"
    assert result["is_complete"] is True
    assert [item["rule_id"] for item in result["items"]] == list(reversed(rule_ids))
    master_by_id = {entry.rule_id: entry for entry in customer_entries}
    for item in result["items"]:
        master_entry = master_by_id[item["rule_id"]]
        assert item["source_document"] == master_entry.source_document
        assert item["qc_point"] == master_entry.qc_point


def test_single_record_result_rejects_rule_id_removed_from_current_catalog(monkeypatch):
    """同一规则集版本的旧 Envelope 不能把已移除规则混入当前结果页。"""

    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": "rec_1234567890abcdef12345678",
        "items": [
            {
                "rule_id": "LX0609-001",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
            {
                "rule_id": "LX0609-999",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
        ],
    }
    session = _ReadSession(
        [[_selected_job()], [{"envelope_json": json.dumps(envelope)}]]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService,
        "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )

    result = CustomQCWorkspaceService().build_latest_single_record_result_dto(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_invalid"
    assert result["items"] == []


@pytest.mark.parametrize(
    "canonical_items",
    [
        [
            {
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            }
        ],
        [
            {
                "rule_id": "LX0609-025",
                "status": "invented_status",
                "result_status": "invented_status",
                "is_compliant": None,
            }
        ],
        [
            {
                "rule_id": "LX0609-025",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
            {
                "rule_id": "LX0609-025",
                "status": "non_compliant",
                "result_status": "non_compliant",
                "is_compliant": False,
            },
        ],
    ],
)
def test_single_record_result_rejects_invalid_rule_identity_before_metadata_projection(
    monkeypatch,
    canonical_items,
):
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": "rec_1234567890abcdef12345678",
        "items": canonical_items,
    }
    session = _ReadSession(
        [
            [_selected_job()],
            [{"envelope_json": json.dumps(envelope, ensure_ascii=False)}],
        ]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService,
        "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )
    monkeypatch.setattr(
        workspace_module,
        "load_luxian_0609_rule_master",
        lambda: (_ for _ in ()).throw(AssertionError("无效Envelope不得进入展示投影")),
    )

    result = CustomQCWorkspaceService().build_latest_single_record_result_dto(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        expected_rule_ids=["LX0609-025"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_invalid"
    assert result["items"] == []


def test_single_record_result_rejects_malformed_item_mixed_with_valid_item(monkeypatch):
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": "rec_1234567890abcdef12345678",
        "items": [
            {
                "rule_id": "LX0609-025",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
            "malformed",
        ],
    }
    session = _ReadSession(
        [
            [_selected_job()],
            [{"envelope_json": json.dumps(envelope, ensure_ascii=False)}],
        ]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService,
        "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )

    result = CustomQCWorkspaceService().build_latest_single_record_result_dto(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        expected_rule_ids=["LX0609-025"],
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_invalid"
    assert result["items"] == []


@pytest.mark.parametrize(
    "canonical_item",
    [
        {
            "rule_id": "LX0609-025",
            "status": "compliant",
            "result_status": "compliant",
            "is_compliant": False,
        },
        {
            "rule_id": "LX0609-025",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "is_compliant": True,
        },
        {
            "rule_id": "LX0609-025",
            "status": "data_gap",
            "result_status": "data_gap",
            "is_compliant": False,
        },
        *[
            {
                "rule_id": "LX0609-025",
                "status": status,
                "result_status": status,
                "is_compliant": True,
            }
            for status in (
                "uncertain",
                "not_applicable",
                "technical_error",
                "not_executed",
                "ai_suggested_compliant",
                "ai_suggested_non_compliant",
            )
        ],
        {
            "rule_id": "LX0609-025",
            "status": "non_compliant",
            "result_status": "uncertain",
            "is_compliant": False,
        },
        {
            "rule_id": "LX0609-025",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "display_status": "uncertain",
            "is_compliant": False,
        },
        {
            "rule_id": "LX0609-025",
            "status": "COMPLIANT",
            "result_status": "COMPLIANT",
            "is_compliant": True,
        },
    ],
)
def test_single_record_result_rejects_historical_canonical_status_inconsistency(
    monkeypatch,
    canonical_item,
):
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": "rec_1234567890abcdef12345678",
        "items": [canonical_item],
    }
    session = _ReadSession(
        [
            [_selected_job(legacy_items=[{"status": "compliant"}])],
            [{"envelope_json": json.dumps(envelope, ensure_ascii=False)}],
        ]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService,
        "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )

    result = CustomQCWorkspaceService().build_latest_single_record_result_dto(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        expected_rule_ids=["LX0609-025"],
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_invalid"
    assert result["items"] == []


def test_completed_projection_with_items_rejects_historical_status_inconsistency():
    job = {
        **_selected_job(),
        "record_ids_json": json.dumps(["visit-1"]),
        "filters_json": json.dumps(_selected_job()["filters"]),
        "summary_json": "{}",
    }
    envelope = {
        "root_job_id": "job-current",
        "job_id": "job-current",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "envelope_json": json.dumps(
            {
                "schema_version": "lx0609-record-result-envelope-v1",
                "delivery_mode": "canonical_straight_through",
                "record_ref": "rec_1234567890abcdef12345678",
                "items": [
                    {
                        "rule_id": "LX0609-001",
                        "status": "compliant",
                        "result_status": "compliant",
                        "is_compliant": False,
                    }
                ],
            }
        ),
    }
    session = _ReadSession([[job], [envelope]])

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[
            {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}
        ],
        include_items=True,
        session_factory=lambda: session,
    )

    assert result[("inst-1", "patient-1", "visit-1")] == {
        "status": "technical_error",
        "reason_code": "canonical_result_envelope_invalid",
    }


def test_exact_batch_html_rejects_historical_status_inconsistency_without_legacy_fallback(
    monkeypatch,
):
    service = object.__new__(CustomQCWorkspaceService)
    service._record_result_envelope_table = workspace_module._record_result_envelopes_table()
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "job_id": "job-current",
        "root_job_id": "job-current",
        "record_ref": "rec_1234567890abcdef12345678",
        "items": [
            {
                "rule_id": "LX0609-001",
                "status": "non_compliant",
                "result_status": "non_compliant",
                "is_compliant": True,
            }
        ],
    }
    session = _ReadSession(
        [
            [
                {
                    "job_id": "job-current",
                    "root_job_id": "job-current",
                    "created_by": "reviewer-a",
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                    "envelope_json": json.dumps(envelope),
                }
            ]
        ]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    job = {
        "id": "job-current",
        "created_by": "reviewer-a",
        "status": "completed",
        "total_records": 1,
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "record_refs": [
                {"institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1"}
            ],
        },
        "items": [{"rule_id": "LX0609-999", "status": "compliant"}],
    }

    with pytest.raises(ValueError, match="canonical_result_envelope_invalid"):
        service.export_batch_job_html(job=job)


@pytest.mark.parametrize(
    ("status", "is_compliant"),
    [
        ("compliant", True),
        ("non_compliant", False),
        ("data_gap", None),
        ("uncertain", None),
        ("not_applicable", None),
        ("technical_error", None),
        ("not_executed", None),
        ("ai_suggested_compliant", None),
        ("ai_suggested_non_compliant", None),
    ],
)
def test_writer_accepts_frozen_canonical_status_semantics(status, is_compliant):
    session = _WriteSession()
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "rule_id": "LX0609-001",
        "status": status,
        "result_status": status,
        "display_status": status,
        "is_compliant": is_compliant,
    }
    if status == "non_compliant":
        item["criterion_results"] = [
            {
                "criterion_id": "requirement_check",
                "kind": "semantic_relation",
                "status": "failed",
                "reason_code": "requirement_violated",
            }
        ]

    CustomQCWorkspaceService()._write_record_result_envelopes(
        session,
        job_row={
            "id": "job-current",
            "created_by": "reviewer-a",
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
        },
        items=[item],
        now=datetime(2026, 8, 15, 10, 0, 0),
    )

    assert len(session.statements) == 2


def test_writer_rejects_unexplained_current_lx0609_defect_without_rejudging_status():
    """Store 不得将当前确定问题隐式重判为资料缺口。"""

    session = _WriteSession()
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "rule_id": "LX0609-025",
        "schema_version": "lx0609-customer-result-v2",
        "status": "non_compliant",
        "result_status": "non_compliant",
        "display_status": "non_compliant",
        "is_compliant": False,
        "metadata": {"execution_source": "lx0609_native"},
    }

    with pytest.raises(ValueError, match="客户结果解释合同不完整"):
        CustomQCWorkspaceService()._write_record_result_envelopes(
            session,
            job_row={
                "id": "job-current",
                "created_by": "reviewer-a",
                "filters_json": json.dumps(
                    {
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                    }
                ),
            },
            items=[item],
            now=datetime(2026, 8, 15, 10, 0, 0),
        )

    assert item["status"] == "non_compliant"
    assert item["result_status"] == "non_compliant"
    assert item.get("reason_code", "") == ""
    assert session.statements == []


def test_writer_persists_finalizer_validated_customer_facts_unchanged():
    session = _WriteSession()
    raw_facts = {
        "failure_kind": "lymph_node_dissection_not_documented",
        "performed_surgery_confirmed": True,
        "malignant_surgery_confirmed": True,
        "checked_sources": ["surgery_record"],
    }
    expected_facts = validate_luxian_0609_executor_customer_display_facts(
        rule_id="LX0609-024",
        raw=raw_facts,
    )

    CustomQCWorkspaceService()._write_record_result_envelopes(
        session,
        job_row={
            "id": "job-current",
            "created_by": "reviewer-a",
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
        },
        items=[
            {
                "record_id": "visit-1",
                "visit_id": "visit-1",
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "rule_id": "LX0609-024",
                "status": "non_compliant",
                "result_status": "non_compliant",
                "display_status": "non_compliant",
                "is_compliant": False,
                "customer_display_facts": raw_facts,
            }
        ],
        now=datetime(2026, 8, 15, 10, 0, 0),
    )

    envelope = json.loads(session.statements[-1].compile().params["envelope_json"])
    assert expected_facts is not None
    assert envelope["items"][0]["customer_display_facts"] == expected_facts


def test_writer_marks_envelope_as_canonical_straight_through():
    session = _WriteSession()
    service = CustomQCWorkspaceService()
    service._write_record_result_envelopes(
        session,
        job_row={
            "id": "job-current",
            "created_by": "reviewer-a",
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
        },
        items=[
            {
                "record_id": "visit-1",
                "visit_id": "visit-1",
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "rule_id": "LX0609-001",
                "status": "uncertain",
                "result_status": "uncertain",
                "reason_code": "customer_explanation_incomplete",
                "is_compliant": None,
                "conclusion": "引擎结论原文",
            }
        ],
        now=datetime(2026, 7, 30, 10, 0, 0),
    )

    insert_params = session.statements[-1].compile().params
    envelope = json.loads(insert_params["envelope_json"])
    assert envelope["delivery_mode"] == "canonical_straight_through"
    assert envelope["items"][0]["status"] == "uncertain"
    assert envelope["items"][0]["result_status"] == "uncertain"
    assert envelope["items"][0]["reason_code"] == "customer_explanation_incomplete"
    assert envelope["items"][0]["is_compliant"] is None
    assert envelope["items"][0]["conclusion"] == "引擎结论原文"


def test_writer_uses_facade_envelope_item_projector(monkeypatch):
    session = _WriteSession()
    service = CustomQCWorkspaceService()
    projected_item = {
        "rule_id": "LX0609-001",
        "status": "compliant",
        "result_status": "compliant",
        "is_compliant": True,
        "projected_by_facade": True,
    }
    monkeypatch.setattr(
        service,
        "_envelope_item_from_rule_result",
        lambda item, *, hmac_key=None: dict(projected_item),
    )

    service._write_record_result_envelopes(
        session,
        job_row={
            "id": "job-current",
            "created_by": "reviewer-a",
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
        },
        items=[
            {
                "record_id": "visit-1",
                "visit_id": "visit-1",
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "rule_id": "LX0609-001",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            }
        ],
        now=datetime(2026, 8, 15, 10, 0, 0),
    )

    insert_params = session.statements[-1].compile().params
    envelope = json.loads(insert_params["envelope_json"])
    assert envelope["items"] == [projected_item]


def test_pending_rule_conclusion_remains_customer_text_through_canonical_delivery(
    monkeypatch,
):
    settings_values = {
        flag_name: True
        for flag_name, _ in RULE_DECISION_ROLLOUT_GROUPS
        if flag_name is not None
    }
    settings_values.update(
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
        LUXIAN_0609_EVIDENCE_FORMATTER_ENABLED=False,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=False,
    )
    inventory = load_luxian_0609_dependency_inventory()
    prepared_rules = [
        {"rule_id": rule_id}
        for rule_id in resolve_package_entry_execution_rule_ids(
            inventory=inventory,
            selected_rule_ids=("LX0609-049",),
        )
    ]
    executable_rules, context = asyncio.run(
        prepare_luxian_0609_execution(
            rule_set_key=LUXIAN_0609_RULE_SET_KEY,
            prepared_rules=prepared_rules,
            visit_id="visit-1",
            medical_text="",
            evidence_payload=None,
            llm_client=object(),
            settings=SimpleNamespace(**settings_values),
            selected_customer_rule_ids=("LX0609-049",),
        )
    )
    assert executable_rules == []
    aggregated = aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="visit-1",
        model_name="unused",
        evidence_payload=None,
    )
    delivered_item = {
        **aggregated["results"][0],
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "visit_id": "visit-1",
    }

    write_session = _WriteSession()
    service = CustomQCWorkspaceService()
    service._write_record_result_envelopes(
        write_session,
        job_row={
            "id": "job-current",
            "created_by": "reviewer-a",
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                    "record_refs": [
                        {
                            "institute_id": "inst-1",
                            "patient_id": "patient-1",
                            "visit_id": "visit-1",
                        }
                    ],
                    "scoped_customer_rule_ids": ["LX0609-049"],
                }
            ),
        },
        items=[delivered_item],
        now=datetime(2026, 8, 15, 10, 0, 0),
    )
    envelope_json = write_session.statements[-1].compile().params["envelope_json"]
    read_session = _ReadSession(
        [
            [_selected_job()],
            [{"envelope_json": envelope_json}],
        ]
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: read_session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService,
        "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )

    dto = service.build_latest_single_record_result_dto(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        expected_rule_ids=["LX0609-049"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert dto["state"] == "ready"
    assert dto["items"][0]["status"] == "not_executed"
    assert dto["items"][0]["conclusion"] == (
        "本质控点当前不参与正式结论，未生成合规或问题判定。"
    )
    assert isinstance(dto["items"][0]["conclusion"], str)


def test_typed_050_canonical_finding_survives_envelope_customer_projection() -> None:
    reduced = reduce_luxian_0609_rule_decision(
        RuleDecision(
            rule_id="LX0609-050",
            snapshot_hash="a" * 64,
            applicability=ApplicabilityState.APPLICABLE,
            evidence_state=EvidenceState.SUFFICIENT,
            qc_direction=QcDirection.DEFECT,
            reason_code="requirement_violated",
            fact_refs=("b" * 64,),
            evaluator_version="canonical-delivery-test-v1",
            confidence=1.0,
        )
    )
    controlled_facts = {
        "verification_kind": "uncertain_diagnosis_discussion_check",
        "admission_time": "2026-08-01 08:00:00",
        "uncertain_record_times": ["2026-08-09 09:00:00"],
        "discussion_count": 0,
        "raw_text": "PRIVATE_MEDICAL_BODY",
    }
    context = Luxian0609ExecutionContext(
        enabled=True,
        wrapper_rules=[{"rule_id": "LX0609-050", "name": "疑难病例讨论"}],
        prepared_rule_count=1,
        reduced_decisions=(reduced,),
        customer_display_facts=(("LX0609-050", controlled_facts),),
    )

    aggregated = aggregate_luxian_0609_orchestrated_results(
        orchestrated={"results": []},
        context=context,
        visit_id="PRIVATE_VISIT_ID",
        model_name="unused",
        evidence_payload=None,
    )
    envelope_item = envelope_item_from_rule_result(
        {
            **aggregated["results"][0],
            "record_id": "PRIVATE_RECORD_ID",
            "medical_text": "PRIVATE_MEDICAL_BODY",
            "customer_conclusion": "执行器已生成的疑难病例讨论结论。",
        }
    )
    projected = project_customer_safe_result_item(
        envelope_item,
        hmac_key="unit-test-key",
    )

    assert projected["schema_version"] == "customer-qc-result-v1"
    assert projected["status"] == "non_compliant"
    assert projected["conclusion"] == "执行器已生成的疑难病例讨论结论。"
    assert projected["findings"] == projected["conclusion"]
    dumped = json.dumps(projected, ensure_ascii=False)
    assert "PRIVATE_MEDICAL_BODY" not in dumped
    assert "执行器已生成的疑难病例讨论结论。" in dumped
    assert project_customer_safe_result_item(
        projected,
        hmac_key="unit-test-key",
    ) == projected


def test_typed_050_scope_uncertainty_survives_safe_projection_without_raw_text() -> None:
    projected = project_customer_safe_result_item(
        {
            "rule_id": "LX0609-050",
            "status": "uncertain",
            "reason_code": "diagnosis_scope_uncertain",
            "customer_display_facts": {
                "verification_kind": "uncertain_diagnosis_scope_unverified",
                "admission_time": "2026-08-01 08:00:00",
                "uncertain_record_times": ["2026-08-09 09:00:00"],
                "discussion_count": 0,
                "raw_text": "PRIVATE_MEDICAL_BODY",
            },
            "customer_conclusion": "FORGED_CUSTOMER_CONCLUSION",
        },
        hmac_key="unit-test-key",
    )

    assert projected["status"] == "uncertain"
    assert projected["reason_code"] == "diagnosis_scope_uncertain"
    assert "2026-08-09 09:00:00" in projected["conclusion"]
    assert "不能据此认定缺少疑难病例讨论" in projected["conclusion"]
    dumped = json.dumps(projected, ensure_ascii=False)
    assert "PRIVATE_MEDICAL_BODY" not in dumped
    assert "FORGED_CUSTOMER_CONCLUSION" not in dumped


@pytest.mark.parametrize(
    "field,value",
    [
        ("admission_time", "患者张三，身份证 510000199001011234"),
        ("admission_time", "2026-02-30 08:00:00"),
        ("uncertain_record_times", ["病历正文：患者李四住院于2026年08月01日"]),
        ("uncertain_record_times", ["2026-08-09 09:00:00"] * 101),
    ],
)
def test_typed_050_customer_projection_rejects_non_datetime_controlled_facts(
    field: str,
    value: object,
) -> None:
    facts = {
        "verification_kind": "uncertain_diagnosis_discussion_check",
        "admission_time": "2026-08-01 08:00:00",
        "uncertain_record_times": ["2026-08-09 09:00:00"],
        "discussion_count": 0,
    }
    facts[field] = value

    with pytest.raises(ValueError):
        project_customer_safe_result_item(
            {
                "rule_id": "LX0609-050",
                "status": "non_compliant",
                "is_compliant": False,
                "customer_display_facts": facts,
            },
            hmac_key="unit-test-key",
        )


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"status": "future_status", "result_status": "future_status", "is_compliant": None},
        {"status": "non_compliant", "result_status": "uncertain", "is_compliant": False},
        {"status": "non_compliant", "result_status": "non_compliant", "is_compliant": None},
        {
            "status": "non_compliant",
            "result_status": "non_compliant",
            "display_status": "uncertain",
            "is_compliant": False,
        },
    ],
)
def test_writer_rejects_invalid_or_conflicting_canonical_status_fields(
    invalid_fields: dict[str, Any],
):
    session = _WriteSession()
    service = CustomQCWorkspaceService()

    with pytest.raises(ValueError, match="Canonical Envelope 状态字段"):
        service._write_record_result_envelopes(
            session,
            job_row={
                "id": "job-current",
                "created_by": "reviewer-a",
                "filters_json": json.dumps(
                    {
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                    }
                ),
            },
            items=[
                {
                    "record_id": "visit-1",
                    "visit_id": "visit-1",
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "rule_id": "LX0609-001",
                    "reason_code": "requirement_violated",
                    **invalid_fields,
                }
            ],
            now=datetime(2026, 7, 30, 10, 0, 0),
        )

    assert session.statements == []


def test_writer_validates_all_records_before_mutating_any_envelope():
    session = _WriteSession()
    service = CustomQCWorkspaceService()

    with pytest.raises(ValueError, match="Canonical Envelope 状态字段"):
        service._write_record_result_envelopes(
            session,
            job_row={
                "id": "job-current",
                "created_by": "reviewer-a",
                "filters_json": json.dumps(
                    {
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                        "record_refs": [
                            {
                                "institute_id": "inst-1",
                                "patient_id": "patient-1",
                                "visit_id": "visit-1",
                            },
                            {
                                "institute_id": "inst-1",
                                "patient_id": "patient-2",
                                "visit_id": "visit-2",
                            },
                        ],
                        "scoped_customer_rule_ids": ["LX0609-001"],
                    }
                ),
            },
            items=[
                {
                    "record_id": "visit-1",
                    "visit_id": "visit-1",
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "rule_id": "LX0609-001",
                    "status": "compliant",
                    "result_status": "compliant",
                    "is_compliant": True,
                },
                {
                    "record_id": "visit-2",
                    "visit_id": "visit-2",
                    "institute_id": "inst-1",
                    "patient_id": "patient-2",
                    "rule_id": "LX0609-001",
                    "status": "compliant",
                    "result_status": "compliant",
                    "is_compliant": False,
                },
            ],
            now=datetime(2026, 7, 30, 10, 0, 0),
        )

    assert session.statements == []


@pytest.mark.parametrize(
    "items",
    [
        ["invalid-result-item"],
        [
            {
                "record_id": "visit-1",
                "visit_id": "visit-1",
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "rule_id": "LX0609-001",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
            "invalid-result-item",
        ],
    ],
)
def test_writer_rejects_non_mapping_items_before_mutating_any_envelope(items):
    session = _WriteSession()

    with pytest.raises(ValueError, match="Canonical Envelope 结果项格式非法"):
        CustomQCWorkspaceService()._write_record_result_envelopes(
            session,
            job_row={
                "id": "job-current",
                "created_by": "reviewer-a",
                "filters_json": json.dumps(
                    {
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                    }
                ),
            },
            items=items,
            now=datetime(2026, 8, 16, 10, 0, 0),
        )

    assert session.statements == []


@pytest.mark.parametrize(
    "missing_key",
    ["institute_id", "patient_id", "visit_id"],
)
def test_writer_rejects_incomplete_case_coordinate_before_mutating_any_envelope(
    missing_key,
):
    session = _WriteSession()
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "rule_id": "LX0609-001",
        "status": "compliant",
        "result_status": "compliant",
        "is_compliant": True,
    }
    item.pop(missing_key)

    with pytest.raises(ValueError, match="Canonical Envelope 病例三坐标不完整"):
        CustomQCWorkspaceService()._write_record_result_envelopes(
            session,
            job_row={
                "id": "job-current",
                "created_by": "reviewer-a",
                "filters_json": json.dumps(
                    {
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                    }
                ),
            },
            items=[item],
            now=datetime(2026, 8, 16, 10, 0, 0),
        )

    assert session.statements == []


def test_writer_rejects_non_compliant_without_controlled_explanation_before_mutation():
    session = _WriteSession()

    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        CustomQCWorkspaceService()._write_record_result_envelopes(
            session,
            job_row={
                "id": "job-current",
                "created_by": "reviewer-a",
                "filters_json": json.dumps(
                    {
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                    }
                ),
            },
            items=[
                {
                    "record_id": "visit-1",
                    "visit_id": "visit-1",
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "rule_id": "LX0609-071",
                    "status": "non_compliant",
                    "result_status": "non_compliant",
                    "display_status": "non_compliant",
                    "is_compliant": False,
                    "reason_code": "association_failed",
                }
            ],
            now=datetime(2026, 8, 16, 10, 0, 0),
        )

    assert session.statements == []


def test_writer_accepts_non_compliant_with_controlled_failed_criterion():
    session = _WriteSession()

    CustomQCWorkspaceService()._write_record_result_envelopes(
        session,
        job_row={
            "id": "job-current",
            "created_by": "reviewer-a",
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
        },
        items=[
            {
                "record_id": "visit-1",
                "visit_id": "visit-1",
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "rule_id": "LX0609-071",
                "status": "non_compliant",
                "result_status": "non_compliant",
                "display_status": "non_compliant",
                "is_compliant": False,
                "reason_code": "association_failed",
                "criterion_results": [
                    {
                        "criterion_id": "event_association",
                        "kind": "semantic_relation",
                        "status": "failed",
                        "reason_code": "association_failed",
                    }
                ],
            }
        ],
        now=datetime(2026, 8, 16, 10, 0, 0),
    )

    assert len(session.statements) == 2


def test_writer_accepts_064_non_compliant_with_projected_multievent_facts():
    session = _WriteSession()

    CustomQCWorkspaceService()._write_record_result_envelopes(
        session,
        job_row={
            "id": "job-current",
            "created_by": "reviewer-a",
            "filters_json": json.dumps(
                {
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }
            ),
        },
        items=[
            {
                "record_id": "visit-1",
                "visit_id": "visit-1",
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "rule_id": "LX0609-064",
                "status": "non_compliant",
                "result_status": "non_compliant",
                "display_status": "non_compliant",
                "is_compliant": False,
                "reason_code": "requirement_violated",
                "customer_display_facts": {
                    "verification_kind": "postoperative_three_day_coverage_check",
                    "performed_surgery_count": 1,
                    "surgery_time": "2026-07-07 18:30:00",
                    "required_postop_dates": [
                        "2026-07-08",
                        "2026-07-09",
                        "2026-07-10",
                    ],
                    "covered_postop_dates": ["2026-07-08", "2026-07-09"],
                    "surgeon_round_present": False,
                    "surgery_events": [
                        {
                            "surgery_time": "2026-07-07 18:30:00",
                            "surgery_name": "血肿清除术",
                            "surgeon_names": ["韩平"],
                            "required_postop_dates": [
                                "2026-07-08",
                                "2026-07-09",
                                "2026-07-10",
                            ],
                            "covered_postop_dates": [
                                "2026-07-08",
                                "2026-07-09",
                            ],
                            "surgeon_round_present": False,
                        }
                    ],
                },
            }
        ],
        now=datetime(2026, 8, 17, 10, 0, 0),
    )

    assert len(session.statements) == 2
