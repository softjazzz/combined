from __future__ import annotations

import asyncio
import json
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import MetaData, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

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
from app.services.luxian_0609_rule_catalog import load_luxian_0609_rules
from app.services.luxian_0609_rule_master import load_luxian_0609_rule_master
from app.services.sample_validation_rule_sets import (
    LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS,
)
from app.services.qc_workspace.canonical_result_store import (
    CanonicalResultStore,
    canonical_envelope_items_are_consistent,
    envelope_item_from_rule_result,
    safe_customer_display_facts,
)
from app.services.qc_workspace import result_feedback_demo_store as feedback_module
from app.services.qc_workspace.result_feedback_demo_store import ResultFeedbackDemoStore
from app.schemas.qc_sichuan import QcResultFeedbackRequest
from app.services.luxian_0609.canonical_result_finalizer import (
    validate_luxian_0609_executor_customer_display_facts,
)
from app.services.luxian_0609.basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
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
        self.statements: list[Any] = []

    def execute(self, statement: Any) -> _Rows:
        self.statements.append(statement)
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
            "LX0609-04-02-03",
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
            "LX0609-04-02-04",
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
            "LX0609-05-01-01",
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
            "LX0609-04-01-01",
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
            "LX0609-04-02-02",
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
            "LX0609-04-03-01",
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
            "LX0609-11-02-01",
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
            "LX0609-11-02-02",
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
            "LX0609-04-04-01",
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
            "LX0609-04-04-02",
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
            "LX0609-04-01-02",
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
        ("LX0609-04-02-04", {"missing_fields": ["implant_material"]}),
        (
            "LX0609-04-02-04",
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
    ],
)
def test_store_rejects_invalid_known_rule_customer_facts(
    rule_id: str,
    raw: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="客户结果解释合同"):
        safe_customer_display_facts(
            {"customer_display_facts": raw},
            rule_id=rule_id,
        )


def test_store_does_not_project_unknown_rule_customer_facts() -> None:
    assert safe_customer_display_facts(
        {"customer_display_facts": {"failure_kind": "unknown"}},
        rule_id="LX0609-999",
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


def _case_record_ref(
    institute_id: str = "inst-1", patient_id: str = "patient-1", visit_id: str = "visit-1",
) -> str:
    """按现有引用机制，由病例三坐标与服务密钥生成保存时的 Envelope 病历引用。"""

    from app.services.case_identity import CaseRef
    from app.services.qc_workspace.canonical_result_store import (
        customer_safe_projection_key,
        keyed_ref,
    )

    return keyed_ref(
        "rec",
        CaseRef(institute_id, patient_id, visit_id).as_key(),
        hmac_key=customer_safe_projection_key(),
    )


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
                            "rule_id": "LX0609-01-01-01",
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


@pytest.mark.parametrize("task_status", ["running", "failed", "canceled"])
def test_completed_record_envelope_from_incomplete_task_is_ready(monkeypatch, task_status):
    """整批未完整完成时，已写入 Envelope 的病历仍可独立展示。"""

    identity = ("inst-1", "patient-1", "visit-1")
    job = {
        "id": "job-partial",
        "status": task_status,
        "created_at": "2026-09-15T08:00:00",
        "finished_at": None,
        "filters_json": json.dumps({
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
        }),
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
        "updated_at": "2026-09-15T08:05:00",
        "envelope_json": json.dumps({
            "schema_version": "lx0609-record-result-envelope-v1",
            "delivery_mode": "canonical_straight_through",
            "items": [{
                "rule_id": "LX0609-01-01-01",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            }],
        }),
    }
    session = _ReadSession([[job], [envelope]])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[{
            "institute_id": identity[0],
            "patient_id": identity[1],
            "visit_id": identity[2],
        }],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result[identity]["status"] == "ready"
    assert result[identity]["completed_at"] == "2026-09-15T08:05:00"


def test_running_retry_without_envelope_does_not_hide_previous_completed_result(monkeypatch):
    identity = ("inst-1", "patient-1", "visit-1")
    filters_json = json.dumps({
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
    })
    completed_job = {
        "id": "job-completed",
        "status": "completed",
        "created_at": "2026-09-14T08:00:00",
        "finished_at": "2026-09-14T08:05:00",
        "filters_json": filters_json,
        "record_ids_json": json.dumps([identity[2]]),
        "summary_json": "{}",
    }
    retrying_job = {
        "id": "job-retrying",
        "status": "running",
        "created_at": "2026-09-15T08:00:00",
        "finished_at": None,
        "filters_json": filters_json,
        "record_ids_json": json.dumps([identity[2]]),
        "summary_json": "{}",
    }
    envelope = {
        "root_job_id": completed_job["id"],
        "job_id": completed_job["id"],
        "institute_id": identity[0],
        "patient_id": identity[1],
        "visit_id": identity[2],
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": "2026-06-09",
        "updated_at": completed_job["finished_at"],
        "envelope_json": json.dumps({
            "schema_version": "lx0609-record-result-envelope-v1",
            "delivery_mode": "canonical_straight_through",
            "items": [{
                "rule_id": "LX0609-01-01-01",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            }],
        }),
    }
    session = _ReadSession([[completed_job, retrying_job], [envelope]])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    result = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
        record_refs=[{
            "institute_id": identity[0],
            "patient_id": identity[1],
            "visit_id": identity[2],
        }],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result[identity]["status"] == "ready"
    assert result[identity]["completed_at"] == completed_job["finished_at"]


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
                        "rule_id": "LX0609-01-01-01",
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
                        "rule_id": "LX0609-11-01-01",
                        "status": "not_executed",
                        "result_status": "not_executed",
                        "is_compliant": None,
                    },
                    {
                        "rule_id": "LX0609-01-01-01",
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
    assert projection["items"][0]["rule_id"] == "LX0609-01-01-01"


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
                "record_ref": _case_record_ref(),
                "items": [
                    {
                        "rule_id": "LX0609-01-01-01",
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
    assert dto["record_ref"] == _case_record_ref()
    assert dto["items"][0]["rule_id"] == "LX0609-01-01-01"
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
        "rule_id": "LX0609-01-01-01",
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
        expected_rule_ids=["LX0609-01-01-01"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_missing"
    assert result["items"] == []
    assert result["result_rule_count"] == 0


@pytest.mark.parametrize("task_status", ["running", "failed", "canceled"])
def test_single_record_result_from_incomplete_task_is_ready_when_envelope_exists(
    monkeypatch,
    task_status,
):
    """病历池标为可查看的独立 Envelope，单病历详情也必须能够读取。"""

    selected_job = {
        **_selected_job(),
        "status": task_status,
    }
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": _case_record_ref(),
        "items": [_published_pilot_item_for_read_boundary("LX0609-01-01-01")],
    }
    session = _ReadSession(
        [
            [selected_job],
            [{"envelope_json": json.dumps(envelope)}],
        ]
    )
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
        expected_rule_ids=["LX0609-01-01-01"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "ready"
    assert result["record_ref"] == envelope["record_ref"]
    assert result["result_rule_count"] == 1
    root_query_params = session.statements[0].compile().params
    assert any(
        isinstance(value, (list, tuple)) and task_status in value
        for value in root_query_params.values()
    )
    envelope_where = str(session.statements[1].whereclause)
    assert "root_job_id" in envelope_where
    assert "created_by" not in envelope_where


def test_single_record_result_does_not_convert_database_read_error_to_not_found(monkeypatch):
    monkeypatch.setattr(workspace_module, "_session", _BrokenReadSession)

    with pytest.raises(OperationalError, match="database unavailable"):
        CustomQCWorkspaceService().get_latest_luxian_0609_record_result(
            institute_id="inst-1",
            patient_id="patient-1",
            visit_id="visit-1",
            expected_rule_ids=["LX0609-01-01-01"],
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
                        "rule_id": "LX0609-01-01-01",
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
                        "rule_id": "LX0609-01-01-01",
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
                "rule_id": "LX0609-01-01-01",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
            {
                "rule_code": "LX0609-01-01-01",
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


def test_single_record_result_rejects_historical_non_deliverable_status_without_projection(
    monkeypatch,
):
    canonical_item = {
        "rule_id": "LX0609-04-02-04",
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
        "record_ref": _case_record_ref(),
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
        expected_rule_ids=["LX0609-04-02-04"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_invalid"
    assert result["items"] == []
    assert canonical_item == original_canonical_item
    assert json.dumps(envelope, ensure_ascii=False) == original_envelope_json


def test_single_record_result_projects_catalog_rule_master_metadata_in_envelope_order(monkeypatch):
    master_by_id = {
        entry.rule_id: entry for entry in load_luxian_0609_rule_master()
    }
    customer_rule_ids = [
        str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        for item in load_luxian_0609_rules()
        if str(item.get("rule_id") or item.get("rule_code") or "").strip().upper()
        not in LUXIAN_0609_CUSTOMER_EXCLUDED_RULE_IDS
    ]
    assert all(master_by_id[rule_id].source_document and master_by_id[rule_id].qc_point
               for rule_id in customer_rule_ids)
    # 跨族验证正式读取顺序；不能为全目录伪造同一条“合规且无事实”的结果。
    rule_ids = [
        "LX0609-01-01-01", "LX0609-09-01-01", "LX0609-09-01-02",
        "LX0609-06-01-01", "LX0609-06-02-01",
    ]
    assert set(rule_ids).issubset(customer_rule_ids)
    canonical_items = [
        _published_pilot_item_for_read_boundary(rule_id)
        for rule_id in reversed(rule_ids)
    ]
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": _case_record_ref(),
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
    for item in result["items"]:
        master_entry = master_by_id[item["rule_id"]]
        assert item["source_document"] == master_entry.source_document
        assert item["qc_point"] == master_entry.qc_point


def test_single_record_result_rejects_rule_id_removed_from_current_catalog(monkeypatch):
    """同一规则集版本的旧 Envelope 不能把已移除规则混入当前结果页。"""

    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": _case_record_ref(),
        "items": [
            {
                "rule_id": "LX0609-01-01-01",
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
                "rule_id": "LX0609-04-02-04",
                "status": "invented_status",
                "result_status": "invented_status",
                "is_compliant": None,
            }
        ],
        [
            {
                "rule_id": "LX0609-04-02-04",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
            {
                "rule_id": "LX0609-04-02-04",
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
        "record_ref": _case_record_ref(),
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
        expected_rule_ids=["LX0609-04-02-04"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_invalid"
    assert result["items"] == []


@pytest.mark.parametrize("malformed_item", [
    "malformed",
    {"rule_id": "LX0609-09-01-02", "status": "compliant", "result_status": "compliant", "is_compliant": True},
    {"rule_id": "LX0609-06-02-01", "status": "compliant", "result_status": "compliant", "is_compliant": True,
     "customer_display_facts": {"raw_text": "invalid private fields"}},
])
def test_single_record_result_rejects_malformed_item_mixed_with_valid_item(monkeypatch, malformed_item):
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": _case_record_ref(),
        "items": [
            {
                "rule_id": "LX0609-04-02-04",
                "status": "compliant",
                "result_status": "compliant",
                "is_compliant": True,
            },
            malformed_item,
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
        expected_rule_ids=["LX0609-04-02-04"],
    )

    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_invalid"
    assert result["items"] == []


@pytest.mark.parametrize(
    "canonical_item",
    [
        {
            "rule_id": "LX0609-04-02-04",
            "status": "compliant",
            "result_status": "compliant",
            "is_compliant": False,
        },
        {
            "rule_id": "LX0609-04-02-04",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "is_compliant": True,
        },
        {
            "rule_id": "LX0609-04-02-04",
            "status": "data_gap",
            "result_status": "data_gap",
            "is_compliant": False,
        },
        *[
            {
                "rule_id": "LX0609-04-02-04",
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
            "rule_id": "LX0609-04-02-04",
            "status": "non_compliant",
            "result_status": "uncertain",
            "is_compliant": False,
        },
        {
            "rule_id": "LX0609-04-02-04",
            "status": "non_compliant",
            "result_status": "non_compliant",
            "display_status": "uncertain",
            "is_compliant": False,
        },
        {
            "rule_id": "LX0609-04-02-04",
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
        "record_ref": _case_record_ref(),
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
        expected_rule_ids=["LX0609-04-02-04"],
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
                "record_ref": _case_record_ref(),
                "items": [
                    {
                        "rule_id": "LX0609-01-01-01",
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
        "record_ref": _case_record_ref(),
        "items": [
            {
                "rule_id": "LX0609-01-01-01",
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
    ],
)
def test_writer_accepts_rule_001_published_status_semantics(status, is_compliant):
    session = _WriteSession()
    item = {
        **_published_pilot_item_for_read_boundary("LX0609-01-01-01"),
        "status": status,
        "result_status": status,
        "display_status": status,
        "is_compliant": is_compliant,
    }
    if status == "non_compliant":
        item["reason_code"] = "deadline_exceeded"
        item["customer_display_facts"] = safe_basic_timeliness_customer_display_facts(
            rule_id="LX0609-01-01-01",
            raw={
                "failure_kind": "timeliness_requirement_not_met",
                "target_document": "admission_record", "source_label": "入院记录",
                "timeliness_state": "late", "threshold_hours": 24,
                "elapsed_hours": 26,
            },
        )
        assert item["customer_display_facts"] is not None
        item["criterion_results"] = [
            {
                "criterion_id": "requirement_check",
                "kind": "semantic_relation",
                "status": "failed",
                "reason_code": "requirement_violated",
            }
        ]
    elif status == "data_gap":
        item["reason_code"] = "source_unavailable"
        item.pop("customer_display_facts")

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


@pytest.mark.parametrize(
    "status", ["not_applicable", "not_executed", "ai_suggested_compliant", "ai_suggested_non_compliant"],
)
def test_writer_rejects_rule_001_unsupported_status_without_reinterpreting_facts(status):
    session = _WriteSession()
    item = _published_pilot_item_for_read_boundary("LX0609-01-01-01")
    item.update(status=status, result_status=status, display_status=status, is_compliant=None)

    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        CustomQCWorkspaceService()._write_record_result_envelopes(
            session,
            job_row={
                "id": "job-current", "created_by": "reviewer-a",
                "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                }),
            },
            items=[item],
            now=datetime(2026, 8, 15, 10, 0, 0),
        )
    assert session.statements == []


def test_original_rescue_timeliness_store_rejects_changed_published_overdue_hours():
    rule_id = "LX0609-09-01-01"
    published = safe_basic_timeliness_customer_display_facts(
        rule_id=rule_id,
        raw={
            "failure_kind": "timeliness_requirement_not_met",
            "target_document": "rescue_record",
            "source_label": "抢救记录",
            "timeliness_state": "late",
            "threshold_hours": 6,
            "elapsed_hours": 7,
        },
    )
    assert published is not None
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "rule_id": rule_id,
        "status": "non_compliant",
        "result_status": "non_compliant",
        "display_status": "non_compliant",
        "is_compliant": False,
        "reason_code": "requirement_violated",
        "customer_display_facts": published,
    }
    table = workspace_module._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None,
    )
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    try:
        with Session(engine) as db_session:
            store.replace_for_job(
                db_session,
                job_row={
                    "id": "job-current",
                    "created_by": "reviewer-a",
                    "filters_json": json.dumps({
                        "rule_set_key": "luxian_0609_qc_v1",
                        "rule_set_version": "2026-06-09",
                    }),
                },
                items=[item],
                now=datetime(2026, 9, 24, 10, 0, 0),
                projector=lambda raw: envelope_item_from_rule_result(
                    raw, hmac_key="unit-test-key",
                ),
                projection_key="unit-test-key",
            )
            db_session.commit()
            expected = {
                "root_job_id": "job-current",
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "visit_id": "visit-1",
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09",
            }
            loaded = store.load_selected(db_session, **expected, projection_key="unit-test-key")
            assert loaded["items"][0]["customer_display_facts"] == published
            assert loaded["items"][0]["status"] == "non_compliant"
            assert loaded["items"][0]["reason_code"] == "requirement_violated"
            projected = project_customer_safe_result_item(
                loaded["items"][0], hmac_key="unit-test-key",
            )
            assert projected["customer_display_facts"] == published
            assert projected["status"] == "non_compliant"
            assert projected["reason_code"] == "requirement_violated"
            assert projected.get("customer_evidence", []) == loaded["items"][0].get("customer_evidence", [])
            changed = deepcopy(loaded)
            changed["items"][0]["customer_display_facts"]["overdue_hours"] = 999
            db_session.execute(
                sa.update(table).values(envelope_json=json.dumps(changed)),
            )
            db_session.commit()
            with pytest.raises(ValueError, match="解释合同不完整"):
                store.load_selected(db_session, **expected, projection_key="unit-test-key")
    finally:
        engine.dispose()


@pytest.mark.parametrize("status", ["uncertain", "technical_error"])
def test_canonical_consistency_rejects_non_deliverable_status(status):
    item = {
        "rule_id": "LX0609-01-01-01",
        "status": status,
        "result_status": status,
        "is_compliant": None,
    }

    assert not canonical_envelope_items_are_consistent([item])


@pytest.mark.parametrize("status", ["uncertain", "technical_error"])
def test_writer_rejects_non_deliverable_status_before_mutating_any_envelope(status):
    session = _WriteSession()
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "rule_id": "LX0609-01-01-01",
        "status": status,
        "result_status": status,
        "display_status": status,
        "is_compliant": None,
    }

    with pytest.raises(ValueError, match="Canonical Envelope 状态字段"):
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

    assert session.statements == []


def test_writer_rejects_unexplained_current_lx0609_defect_without_rejudging_status():
    """Store 不得将当前确定问题隐式重判为资料缺口。"""

    session = _WriteSession()
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "rule_id": "LX0609-04-02-04",
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
        rule_id="LX0609-04-02-03",
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
                "rule_id": "LX0609-04-02-03",
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


def test_rescue_non_compliant_safe_facts_survive_canonical_write_and_task_projection():
    fields = (
        "condition_change", "rescue_time", "rescue_measures", "rescue_outcome",
        "participant_names", "participant_titles",
    )
    safe_facts = {
        "target_document": "rescue_record",
        "source_label": "抢救记录",
        "content_state": "non_compliant",
        "required_fields": list(fields),
        "missing_fields": ["participant_titles"],
        "unknown_fields": [],
        "rescue_content_events": [{
            "event_index": 1,
            "record_time": "2026-09-01T10:00:00+08:00",
            "body_scope": "complete",
            "field_facts": {
                field: {"state": "absent" if field == "participant_titles" else "present"}
                for field in fields
            },
            "missing_fields": ["participant_titles"],
            "unknown_fields": [],
        }],
        "failure_kind": "",
    }
    item = {
        "record_id": "visit-1",
        "visit_id": "visit-1",
        "institute_id": "inst-1",
        "patient_id": "patient-1",
        "rule_id": "LX0609-09-01-02",
        "status": "non_compliant",
        "result_status": "non_compliant",
        "display_status": "non_compliant",
        "is_compliant": False,
        "reason_code": "requirement_violated",
        "customer_display_facts": safe_facts,
    }
    # 用隔离的内存库执行真实 INSERT/SELECT，覆盖任务完成后的读回路径。
    table = workspace_module._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None
    )
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as db_session:
        store.replace_for_job(
            db_session,
            job_row={
                "id": "job-current",
                "created_by": "reviewer-a",
                "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }),
            },
            items=[item],
            now=datetime(2026, 9, 1, 10, 0, 0),
            projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="unit-test-key"),
            projection_key="unit-test-key",
        )
        db_session.commit()
        loaded = store.load_selected(
            db_session,
            root_job_id="job-current",
            institute_id="inst-1",
            patient_id="patient-1",
            visit_id="visit-1",
            rule_set_key="luxian_0609_qc_v1",
            rule_set_version="2026-06-09",
            projection_key="unit-test-key",
        )
    engine.dispose()
    assert loaded["items"][0]["customer_display_facts"] == safe_facts
    projected = project_customer_safe_result_item(
        loaded["items"][0], hmac_key="unit-test-key",
    )
    assert projected["customer_display_facts"] == safe_facts
    assert projected["status"] == "non_compliant"
    invalid_item = deepcopy(item)
    invalid_item["customer_display_facts"]["rescue_content_events"][0]["field_facts"][
        "participant_titles"
    ]["quote"] = "内部引文"
    rejected_session = _WriteSession()
    with pytest.raises(ValueError):
        store.replace_for_job(
            rejected_session,
            job_row={
                "id": "job-invalid", "created_by": "reviewer-a",
                "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }),
            },
            items=[invalid_item], now=datetime(2026, 9, 1, 10, 0, 0),
            projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="unit-test-key"),
            projection_key="unit-test-key",
        )
    assert rejected_session.statements == []


@pytest.mark.parametrize(
    ("status", "event_reason", "report_count", "missing_count", "reason_code"),
    [
        ("compliant", "pathology_report_present", 1, 0, "pathology_reports_complete"),
        ("data_gap", "target_report_missing", 0, 1, "target_report_missing"),
    ],
)
def test_pathology_published_facts_commit_and_read_without_reprojection(
    status, event_reason, report_count, missing_count, reason_code,
):
    facts = {
        "verification_kind": "pathology_report_completeness",
        "decision_status": status,
        "event_count": 1,
        "report_count": report_count,
        "missing_report_count": missing_count,
        "unresolved_event_count": int(status == "data_gap"),
        "excluded_event_count": 0,
        "checked_sources": [
            {"source": source, "state": "present", "completeness": "complete"}
            for source in ("pathology_exam_master", "pathology_exam_report")
        ],
        "events": [{
            "event_index": 1, "status": status, "reason_code": event_reason,
            "execution_confirmed": True, "report_count": report_count,
        }],
    }
    item = {
        "record_id": "visit-1", "visit_id": "visit-1",
        "institute_id": "inst-1", "patient_id": "patient-1",
        "schema_version": "lx0609-customer-result-v2",
        "rule_id": "LX0609-06-02-01", "status": status,
        "result_status": status, "display_status": status,
        "is_compliant": True if status == "compliant" else None,
        "reason_code": reason_code, "customer_display_facts": facts,
        "conclusion": "已发布结论",
    }
    table = workspace_module._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None,
    )
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as db_session:
        store.replace_for_job(
            db_session,
            job_row={
                "id": "job-pathology", "created_by": "reviewer-a",
                "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }),
            },
            items=[item], now=datetime(2026, 9, 1, 10, 0, 0),
            projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="unit-test-key"),
            projection_key="unit-test-key",
        )
        db_session.commit()
        loaded = store.load_selected(
            db_session, root_job_id="job-pathology",
            institute_id="inst-1", patient_id="patient-1", visit_id="visit-1",
            rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            projection_key="unit-test-key",
        )
    engine.dispose()
    saved = loaded["items"][0]
    assert saved["customer_display_facts"] == facts
    assert saved["status"] == status
    assert saved["reason_code"] == reason_code
    assert saved["conclusion"] == "已发布结论"
    projected = project_customer_safe_result_item(saved, hmac_key="unit-test-key")
    assert projected["customer_display_facts"] == facts
    assert projected["conclusion"] == "已发布结论"
    corrupted = deepcopy(loaded)
    corrupted["items"][0]["customer_display_facts"]["events"][0]["fact_refs"] = ["a" * 64]
    with pytest.raises(ValueError):
        store.load_selected(
            _ReadSession([[{"envelope_json": json.dumps(corrupted)}]]),
            root_job_id="job-pathology", institute_id="inst-1",
            patient_id="patient-1", visit_id="visit-1",
            rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            projection_key="unit-test-key",
        )


def _published_pilot_item_for_read_boundary(rule_id: str) -> dict[str, Any]:
    original_timeliness = {
        "LX0609-01-01-01": ("admission_record", "入院记录", 24),
        "LX0609-01-02-01": ("first_course_record", "首次病程记录", 8),
        "LX0609-02-01-01": ("attending_course_record", "主治医师及以上首次查房记录", 48),
        "LX0609-02-01-02": ("senior_course_record", "副主任医师或主任医师首次查房记录", 72),
    }
    if rule_id in original_timeliness:
        target, label, threshold = original_timeliness[rule_id]
        facts = safe_basic_timeliness_customer_display_facts(
            rule_id=rule_id,
            raw={
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": target, "source_label": label,
                "timeliness_state": "within", "threshold_hours": threshold,
                "elapsed_hours": 1.0,
            },
        )
        assert facts is not None
    elif rule_id == "LX0609-09-01-01":
        facts = safe_basic_timeliness_customer_display_facts(
            rule_id=rule_id,
            raw={
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": "rescue_record", "source_label": "抢救记录",
                "timeliness_state": "within", "threshold_hours": 6,
                "elapsed_hours": 5,
            },
        )
        assert facts is not None
    elif rule_id == "LX0609-06-01-01":
        facts = {
            "verification_kind": "ct_order_course_review", "subject": "ct_mri",
            "requirement": "order_course_consistency", "review_scope_complete": True,
            "event_count": 1, "event_results": [{"event_position": 1,
                "event_status": "compliant", "issue_kind": "order_course_consistent"}],
            "order_results": [{"event_position": 1, "order_position": 1,
                "status": "compliant", "issue_kind": "order_course_consistent",
                "order_reference_positions": [1], "course_locations": [{
                    "reference_position": 2, "field_path": "record_content",
                    "start": 0, "end": 10, "clause_id": "C1", "offset_unit": "unicode_codepoint"}]}],
        }
    elif rule_id == "LX0609-06-01-05":
        facts = {
            "verification_kind": "exam_lab_requirement_checked",
            "subject": "ct_mri",
            "requirement": "positive_result_analysis_within_24h",
            "event_phase": "report",
            "checked_sources": ["exam_lab_report", "course_record"],
        }
    elif rule_id == "LX0609-09-01-02":
        fields = [
            "condition_change", "rescue_time", "rescue_measures", "rescue_outcome",
            "participant_names", "participant_titles",
        ]
        facts = {
            "target_document": "rescue_record", "source_label": "抢救记录",
            "content_state": "compliant", "required_fields": fields,
            "missing_fields": [], "unknown_fields": [], "failure_kind": "",
            "rescue_content_events": [{
                "event_index": 1, "record_time": "2026-09-01T10:00:00+08:00",
                "body_scope": "complete",
                "field_facts": {field: {"state": "present"} for field in fields},
                "missing_fields": [], "unknown_fields": [],
            }],
        }
    else:
        facts = {
            "verification_kind": "pathology_report_completeness",
            "decision_status": "compliant", "event_count": 1,
            "report_count": 1, "missing_report_count": 0,
            "unresolved_event_count": 0, "excluded_event_count": 0,
            "checked_sources": [
                {"source": source, "state": "present", "completeness": "complete"}
                for source in ("pathology_exam_master", "pathology_exam_report")
            ],
            "events": [{
                "event_index": 1, "status": "compliant",
                "reason_code": "pathology_report_present",
                "execution_confirmed": True, "report_count": 1,
            }],
        }
    return {
        "record_id": "visit-1", "visit_id": "visit-1",
        "institute_id": "inst-1", "patient_id": "patient-1",
        "schema_version": "lx0609-customer-result-v2", "rule_id": rule_id,
        "status": "compliant", "result_status": "compliant",
        "display_status": "compliant", "is_compliant": True,
        "reason_code": "requirement_satisfied", "conclusion": "已发布结论",
        "customer_display_facts": facts,
    }


@pytest.mark.parametrize(
    "rule_ids",
    [
        ("LX0609-09-01-02", "LX0609-06-02-01"),
        ("LX0609-09-01-01",),
        ("LX0609-01-01-01",),
        ("LX0609-01-02-01", "LX0609-02-01-01", "LX0609-02-01-02"),
    ],
    ids=["new_pilots", "original_004", "original_001", "original_002_005_006"],
)
def test_published_rules_keep_identity_through_sqlite_dto_feedback_and_exports(
    monkeypatch, rule_ids,
):
    """发布后的同一 Envelope 是反馈与三个导出格式的结果来源。"""
    import csv
    from io import StringIO

    import app.services.qc_workspace.canonical_result_store as canonical_store

    # 服务层读取按服务密钥复核 Envelope 病历引用；与本测试保存所用密钥保持一致。
    monkeypatch.setattr(
        canonical_store, "get_settings", lambda: SimpleNamespace(JWT_SECRET="unit-test-key"),
    )

    from openpyxl import load_workbook

    canonical_table = workspace_module._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None,
    )
    feedback_table = feedback_module._feedback_table().to_metadata(
        MetaData(), schema=None,
    )
    # TestClient 的线程池需要看到同一份隔离内存库。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    canonical_table.metadata.create_all(engine)
    feedback_table.metadata.create_all(engine)
    store = CanonicalResultStore(canonical_table)
    items = [_published_pilot_item_for_read_boundary(rule_id) for rule_id in rule_ids]
    for item in items:
        item["conclusion"] = f"{item['rule_id']} 已核对"
        item["suggestion"] = f"{item['rule_id']} 无需补充"
        if item["rule_id"] == "LX0609-09-01-01":
            item["evidence"] = [{
                "source_document_id": "synthetic-rescue-document-1",
                "source_type": "rescue_record",
                "source_label": "抢救记录",
                "record_time": "2026-09-01 10:00:00",
                "evidence_excerpt": "合成记录：抢救结束后五小时完成记录",
                "excerpt_kind": "文书级依据",
            }]
    with Session(engine) as session:
        store.replace_for_job(
            session,
            job_row={
                "id": "job-pilots", "created_by": "admin-001",
                "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                    "scoped_customer_rule_ids": list(rule_ids),
                }),
            },
            items=items,
            now=datetime(2026, 9, 1, 10, 0, 0),
            projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="unit-test-key"),
            projection_key="unit-test-key",
        )
        session.commit()
        loaded = store.load_selected(
            session, root_job_id="job-pilots", institute_id="inst-1",
            patient_id="patient-1", visit_id="visit-1",
            rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            projection_key="unit-test-key",
        )
    saved_items = loaded["items"]
    assert [item["rule_id"] for item in saved_items] == list(rule_ids)
    assert all(item["record_ref"] == loaded["record_ref"] for item in saved_items)
    assert all(item["status"] == "compliant" for item in saved_items)
    assert all(item["customer_display_facts"] for item in saved_items)
    assert all(item["conclusion"].endswith("已核对") for item in saved_items)
    assert all(item["suggestion"].endswith("无需补充") for item in saved_items)
    if rule_ids == ("LX0609-09-01-01",):
        assert len(saved_items[0]["evidence"]) == 1
        assert saved_items[0]["evidence"][0]["source_ref"].startswith("src_")
        assert "synthetic-rescue-document-1" not in json.dumps(saved_items)

    # latest-result 真实服务入口读取同一隔离SQLite产生的 Envelope 内容。
    latest_session = _ReadSession([
        [_selected_job()], [{"envelope_json": json.dumps(loaded, ensure_ascii=False)}],
    ])
    monkeypatch.setattr(workspace_module, "_session", lambda: latest_session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService, "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )
    service = object.__new__(CustomQCWorkspaceService)
    service._record_result_envelope_table = canonical_table
    service._batch_job_table = sa.Table(
        "custom_qc_batch_jobs", MetaData(),
        sa.Column("id", sa.String(36)),
        sa.Column("status", sa.String(20)),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
    )
    latest = service.build_latest_single_record_result_dto(
        institute_id="inst-1", patient_id="patient-1", visit_id="visit-1",
        expected_rule_ids=list(rule_ids),
        rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
    )
    assert latest["state"] == "ready"
    assert [item["rule_id"] for item in latest["items"]] == list(rule_ids)
    assert [item["customer_display_facts"] for item in latest["items"]] == [
        item["customer_display_facts"] for item in saved_items
    ]
    assert [item["evidence"] for item in latest["items"]] == [
        item["evidence"] for item in saved_items
    ]

    if rule_ids != ("LX0609-09-01-02", "LX0609-06-02-01"):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.security import get_current_user
        from app.routers import qc_sichuan

        app = FastAPI()
        app.include_router(qc_sichuan.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-001", "roles": ["admin"],
        }
        monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
        monkeypatch.setattr(workspace_module, "_session", lambda: _ReadSession([
            [_selected_job()], [{"envelope_json": json.dumps(loaded, ensure_ascii=False)}],
        ]))
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/qc/sichuan/workspace/records/visit-1/latest-result",
                params={"institute_id": "inst-1", "patient_id": "patient-1"},
            )
        assert response.status_code == 200
        http_result = response.json()["data"]
        assert http_result["state"] == "ready"
        assert [
            {key: item[key] for key in (
                "rule_id", "status", "reason_code", "conclusion", "suggestion",
                "customer_display_facts", "evidence",
            )}
            for item in http_result["items"]
        ] == [
            {key: item[key] for key in (
                "rule_id", "status", "reason_code", "conclusion", "suggestion",
                "customer_display_facts", "evidence",
            )}
            for item in latest["items"]
        ]

        # 批量详情走正式 HTTP 路由和真实 SQLite Envelope 读取；任务表中的
        # 旧 items 只用于验证不会越过 Canonical 成为另一份交付结果。
        detail_job = {
            "id": "job-pilots",
            "draft_id": "sichuan-rule-library",
            "created_by": "admin-001",
            "status": "completed",
            "total_records": 1,
            "filters": {
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_set_version": "2026-06-09",
                "record_refs": [{
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                }],
            },
            "items": [{"rule_id": "LX0609-99-99-99", "status": "non_compliant"}],
        }
        service.get_batch_job = lambda *, job_id, created_by: (
            detail_job if job_id == "job-pilots" and created_by == "admin-001" else None
        )
        service._load_batch_job_canonical_items = lambda *, job, allow_partial=False: (
            store.load_root_job_items(
                job=job,
                session_factory=lambda: Session(engine),
                allow_partial=allow_partial,
                projection_key="unit-test-key",
            )
        )
        with TestClient(app) as client:
            detail_response = client.get(
                "/api/v1/qc/sichuan/workspace/batch-jobs/job-pilots"
            )
        assert detail_response.status_code == 200
        detail_items = detail_response.json()["data"]["items"]
        assert [item["rule_id"] for item in detail_items] == list(rule_ids)
        assert [
            {key: item[key] for key in (
                "rule_id", "status", "reason_code", "conclusion", "suggestion",
                "customer_display_facts",
            )}
            for item in detail_items
        ] == [
            {key: item[key] for key in (
                "rule_id", "status", "reason_code", "conclusion", "suggestion",
                "customer_display_facts",
            )}
            for item in http_result["items"]
        ]
        assert [
            [{key: evidence[key] for key in (
                "source_type", "source_ref", "record_time",
                "evidence_excerpt", "excerpt_kind",
            )} for evidence in item["evidence"]]
            for item in detail_items
        ] == [
            [{key: evidence[key] for key in (
                "source_type", "source_ref", "record_time",
                "evidence_excerpt", "excerpt_kind",
            )} for evidence in item["evidence"]]
            for item in http_result["items"]
        ]
        latest_http_body = response.json()
        detail_http_body = detail_response.json()

        # 病历详情抽屉也应从同一份已保存 Envelope 读取；不把任务原始项
        # 或其他数据源重新解释成 0609 结果。
        from app.routers import records

        record_app = FastAPI()
        record_app.include_router(records.router)
        record_app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-001", "roles": ["admin"],
        }
        monkeypatch.setattr(records, "get_supabase", lambda: None)
        monkeypatch.setattr(
            records, "medical_records_db", SimpleNamespace(get=lambda _record_id: None),
        )
        monkeypatch.setattr(records, "_load_bundle_payload_for_record", lambda _record_id: {})
        monkeypatch.setattr(
            records, "_luxian_0609_envelope_identities",
            lambda _record_id, **_kwargs: {("inst-1", "patient-1", "visit-1")},
        )
        monkeypatch.setattr(
            records,
            "_resolve_visit_identity",
            lambda _record_id: {
                "institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1",
            },
        )
        monkeypatch.setattr(workspace_module, "CustomQCWorkspaceService", lambda: service)
        monkeypatch.setattr(workspace_module, "_session", lambda: _ReadSession([
            [_selected_job()], [{"envelope_json": json.dumps(loaded, ensure_ascii=False)}],
        ]))
        with TestClient(record_app) as client:
            review_response = client.get("/api/v1/records/visit-1/qc-detail")
        assert review_response.status_code == 200
        review_result = review_response.json()["data"]
        assert review_result["review_result_state"] == (
            "ready" if http_result["is_complete"] else "incomplete"
        )
        assert [item["rule_code"] for item in review_result["review_items"]] == list(rule_ids)
        assert [item["status"] for item in review_result["review_items"]] == [
            item["status"] for item in http_result["items"]
        ]
        assert [item["findings"] for item in review_result["review_items"]] == [
            item["conclusion"] for item in http_result["items"]
        ]
        assert [item["suggestion"] for item in review_result["review_items"]] == [
            item["suggestion"] for item in http_result["items"]
        ]
        assert all(
            item["source"] == "canonical_result_envelope"
            for item in review_result["review_items"]
        )
        if rule_ids == ("LX0609-09-01-01",):
            from app.services.luxian_0609_result_export_service import customer_evidence_summary

            assert review_result["review_items"][0]["evidence"] == (
                "抢救记录（2026-09-01 10:00:00、文书级依据）："
                "合成记录：抢救结束后五小时完成记录"
            )
            assert customer_evidence_summary(detail_items[0]["evidence"]) == (
                review_result["review_items"][0]["evidence"]
            )

    feedback = ResultFeedbackDemoStore.__new__(ResultFeedbackDemoStore)
    feedback._canonical_table = canonical_table
    feedback._feedback_table = feedback_table
    monkeypatch.setattr(feedback_module, "_session", lambda: Session(engine))
    for item in saved_items:
        response = feedback.save(
            root_job_id="job-pilots", record_ref=loaded["record_ref"],
            rule_id=item["rule_id"], created_by="admin-001",
            payload=QcResultFeedbackRequest.model_validate({
                "root_job_id": "job-pilots", "record_ref": loaded["record_ref"],
                "feedback_type": "note", "comment": "人工核对完成。",
            }),
        )
        assert response["rule_id"] == item["rule_id"]
        assert response["original_status"] == item["status"]
        assert response["result_digest"] == feedback_module._result_digest(item)
    by_rule = feedback.list_for_record(
        root_job_id="job-pilots", record_ref=loaded["record_ref"],
        created_by="admin-001",
    )
    assert set(by_rule) == set(rule_ids)

    job = {
        "id": "job-pilots", "filters": {"rule_set_key": "luxian_0609_qc_v1"},
        "items": saved_items,
    }
    projected = workspace_module.flatten_customer_safe_result_items(
        job, hmac_key="unit-test-key",
    )
    assert [item["customer_display_facts"] for item in projected] == [
        item["customer_display_facts"] for item in saved_items
    ]
    _, export_rows, _ = workspace_module._customer_export_rows(
        job, hmac_key="unit-test-key",
    )
    assert [row[1] for row in export_rows] == list(rule_ids)
    assert all(row[3] == "合规" and row[5].endswith("已核对") for row in export_rows)
    if rule_ids == ("LX0609-09-01-01",):
        assert export_rows[0][7] == review_result["review_items"][0]["evidence"]
    csv_text = workspace_module._export_customer_safe_csv(
        job, hmac_key="unit-test-key",
    ).getvalue()
    csv_rows = list(csv.reader(StringIO(csv_text)))
    assert all(any(row[1:7] == expected[1:7] for row in csv_rows) for expected in export_rows)
    if rule_ids == ("LX0609-09-01-01",):
        assert any(len(row) > 7 and row[7] == export_rows[0][7] for row in csv_rows)
    workbook = load_workbook(workspace_module._export_customer_safe_workbook(
        job, hmac_key="unit-test-key",
    ))
    xlsx_rows = list(workbook["全部明细"].values)
    assert all(any(tuple(row[:7]) == tuple(expected[:7]) for row in xlsx_rows) for expected in export_rows)
    if rule_ids == ("LX0609-09-01-01",):
        assert any(len(row) > 7 and row[7] == export_rows[0][7] for row in xlsx_rows)
    html_text = workspace_module._export_customer_safe_html(
        job, hmac_key="unit-test-key", canonical_items=saved_items,
    )
    assert all(rule_id in html_text for rule_id in rule_ids)
    assert all(item["conclusion"] in html_text for item in saved_items)
    if rule_ids == ("LX0609-09-01-01",):
        assert export_rows[0][7] in html_text
        assert "synthetic-rescue-document-1" not in html_text
    engine.dispose()

    # 所有交付断言通过后，才为实际浏览器写出本测试的合成 HTTP 产物。
    browser_fixture_path = os.getenv("MEDQC_LX0609_BROWSER_FIXTURE_OUT")
    if browser_fixture_path and rule_ids == ("LX0609-09-01-01",):
        output_path = Path(browser_fixture_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps({
                "fixture_kind": "synthetic_sqlite_http",
                "latest": latest_http_body,
                "detail": detail_http_body,
            }, ensure_ascii=False),
            encoding="utf-8",
        )


@pytest.mark.parametrize(
    ("rule_id", "path", "invalid"),
    [
        ("LX0609-01-01-01", ("remaining_hours",), 999),
        ("LX0609-01-02-01", ("remaining_hours",), 999),
        ("LX0609-02-01-01", ("remaining_hours",), 999),
        ("LX0609-02-01-02", ("remaining_hours",), 999),
        ("LX0609-09-01-01", ("remaining_hours",), 999),
        ("LX0609-06-01-01", ("order_results",), "DELETE"),
        ("LX0609-06-01-01", ("order_results", 0, "course_locations"), []),
        ("LX0609-06-01-01", ("order_results", 0, "course_locations", 0, "start"), -1),
        ("LX0609-06-01-05", ("checked_sources", 0), "corrupted_source"),
        ("LX0609-09-01-02", ("missing_fields",), [{}]),
        ("LX0609-06-02-01", ("decision_status",), []),
        ("LX0609-06-02-01", ("checked_sources", 0, "state"), {}),
        ("LX0609-06-02-01", ("events", 0, "status"), []),
    ],
)
def test_invalid_published_json_type_is_controlled_through_store_and_single_record_dto(
    monkeypatch, rule_id, path, invalid,
):
    table = workspace_module._record_result_envelopes_table().to_metadata(
        MetaData(), schema=None,
    )
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    store = CanonicalResultStore(table)
    with Session(engine) as db_session:
        store.replace_for_job(
            db_session,
            job_row={
                "id": "job-current", "created_by": "reviewer-a",
                "filters_json": json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_set_version": "2026-06-09",
                }),
            },
            items=[_published_pilot_item_for_read_boundary(rule_id)],
            now=datetime(2026, 9, 1, 10, 0, 0),
            projector=lambda raw: envelope_item_from_rule_result(raw, hmac_key="unit-test-key"),
            projection_key="unit-test-key",
        )
        db_session.commit()
        accepted = store.load_selected(
            db_session, root_job_id="job-current",
            institute_id="inst-1", patient_id="patient-1", visit_id="visit-1",
            rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
            projection_key="unit-test-key",
        )
        assert accepted["items"][0]["customer_display_facts"] == (
            _published_pilot_item_for_read_boundary(rule_id)["customer_display_facts"]
        )
        envelope = json.loads(
            db_session.execute(table.select()).mappings().one()["envelope_json"]
        )
        target = envelope["items"][0]["customer_display_facts"]
        for key in path[:-1]:
            target = target[key]
        if invalid == "DELETE":
            del target[path[-1]]
        else:
            target[path[-1]] = invalid
        envelope_json = json.dumps(envelope, ensure_ascii=False)
        db_session.execute(table.update().values(envelope_json=envelope_json))
        db_session.commit()
        with pytest.raises(ValueError, match="客户结果解释合同"):
            store.load_selected(
                db_session, root_job_id="job-current",
                institute_id="inst-1", patient_id="patient-1", visit_id="visit-1",
                rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
                projection_key="unit-test-key",
            )
    engine.dispose()

    session = _ReadSession([
        [_selected_job()], [{"envelope_json": envelope_json}],
    ])
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    monkeypatch.setattr(workspace_module, "_row_to_batch_job", lambda row: dict(row))
    monkeypatch.setattr(
        CustomQCWorkspaceService, "_aggregate_parent_job",
        lambda _self, _session, job: job,
    )
    service = object.__new__(CustomQCWorkspaceService)
    service._record_result_envelope_table = table
    service._batch_job_table = sa.Table(
        "custom_qc_batch_jobs", MetaData(),
        sa.Column("id", sa.String(36)),
        sa.Column("status", sa.String(20)),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
    )
    result = service.build_latest_single_record_result_dto(
        institute_id="inst-1", patient_id="patient-1", visit_id="visit-1",
        expected_rule_ids=[rule_id],
        rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
    )
    assert result["state"] == "technical_error"
    assert result["reason_code"] == "canonical_result_envelope_invalid"
    assert result["items"] == []

    if rule_id in {
        "LX0609-01-01-01", "LX0609-01-02-01", "LX0609-09-01-01",
        "LX0609-02-01-01", "LX0609-02-01-02",
    }:
        # 复用实际SQLite中损坏的字节，补验真实HTTP路由的错误DTO搬运。
        # 任务选择SQL与认证仍是替身，不能称为部署或权限完整验收。
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.core.security import get_current_user
        from app.routers import qc_sichuan

        app = FastAPI()
        app.include_router(qc_sichuan.router)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-001", "roles": ["admin"],
        }
        monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
        monkeypatch.setattr(workspace_module, "_session", lambda: _ReadSession([
            [_selected_job()], [{"envelope_json": envelope_json}],
        ]))
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/qc/sichuan/workspace/records/visit-1/latest-result",
                params={"institute_id": "inst-1", "patient_id": "patient-1"},
            )
        assert response.status_code == 200
        body = response.json()["data"]
        assert body["state"] == "technical_error"
        assert body["reason_code"] == "canonical_result_envelope_invalid"
        assert body["items"] == []


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
        items=[{
            **_published_pilot_item_for_read_boundary("LX0609-01-01-01"),
            "conclusion": "引擎结论原文",
        }],
        now=datetime(2026, 7, 30, 10, 0, 0),
    )

    insert_params = session.statements[-1].compile().params
    envelope = json.loads(insert_params["envelope_json"])
    assert envelope["delivery_mode"] == "canonical_straight_through"
    assert envelope["items"][0]["status"] == "compliant"
    assert envelope["items"][0]["result_status"] == "compliant"
    assert envelope["items"][0]["reason_code"] == "requirement_satisfied"
    assert envelope["items"][0]["is_compliant"] is True
    assert envelope["items"][0]["conclusion"] == "引擎结论原文"


def test_writer_uses_facade_envelope_item_projector(monkeypatch):
    session = _WriteSession()
    service = CustomQCWorkspaceService()
    projected_item = {
        **_published_pilot_item_for_read_boundary("LX0609-01-01-01"),
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
        items=[_published_pilot_item_for_read_boundary("LX0609-01-01-01")],
        now=datetime(2026, 8, 15, 10, 0, 0),
    )

    insert_params = session.statements[-1].compile().params
    envelope = json.loads(insert_params["envelope_json"])
    assert envelope["items"] == [{**projected_item, "record_ref": envelope["record_ref"]}]
    assert "record_ref" not in projected_item


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
            selected_rule_ids=("LX0609-07-04-02",),
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
            selected_customer_rule_ids=("LX0609-07-04-02",),
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
                    "scoped_customer_rule_ids": ["LX0609-07-04-02"],
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
        expected_rule_ids=["LX0609-07-04-02"],
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
            rule_id="LX0609-03-02-01",
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
        wrapper_rules=[{"rule_id": "LX0609-03-02-01", "name": "疑难病例讨论"}],
        prepared_rule_count=1,
        reduced_decisions=(reduced,),
        customer_display_facts=(("LX0609-03-02-01", controlled_facts),),
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
            "rule_id": "LX0609-03-02-01",
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
                "rule_id": "LX0609-03-02-01",
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
                    "rule_id": "LX0609-01-01-01",
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
                        "scoped_customer_rule_ids": ["LX0609-01-01-01"],
                    }
                ),
            },
            items=[
                _published_pilot_item_for_read_boundary("LX0609-01-01-01"),
                {
                    **_published_pilot_item_for_read_boundary("LX0609-01-01-01"),
                    "record_id": "visit-2",
                    "visit_id": "visit-2",
                    "patient_id": "patient-2",
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
                "rule_id": "LX0609-01-01-01",
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
        "rule_id": "LX0609-01-01-01",
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
                    "rule_id": "LX0609-10-01-01",
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
                "rule_id": "LX0609-10-01-01",
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
                "rule_id": "LX0609-04-05-01",
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
