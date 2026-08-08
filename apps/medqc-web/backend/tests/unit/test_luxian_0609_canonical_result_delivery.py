from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService


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
                "items": [{"rule_id": "LX0609-001", "status": "compliant"}],
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
                "items": [{"rule_id": "LX0609-001", "status": "compliant"}],
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
        [{"status": "compliant"}],
        [
            {"rule_id": "LX0609-001", "status": "compliant"},
            {"rule_code": "LX0609-001", "status": "non_compliant"},
        ],
    ],
)
def test_completed_projection_rejects_canonical_items_without_unique_rule_id(items):
    result = CustomQCWorkspaceService._summarize_completed_record_result_envelope(
        envelope_row={
            "envelope_json": json.dumps(
                {
                    "schema_version": "lx0609-record-result-envelope-v1",
                    "delivery_mode": "canonical_straight_through",
                    "items": items,
                }
            )
        },
        completed_at="2026-08-08T10:00:00",
    )

    assert result == {
        "status": "technical_error",
        "reason_code": "canonical_envelope_invalid",
    }


def test_single_record_result_returns_canonical_envelope_items_without_reprojection(
    monkeypatch,
):
    canonical_item = {
        "rule_id": "LX0609-001",
        "rule_name": "入院记录",
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
    envelope = {
        "schema_version": "lx0609-record-result-envelope-v1",
        "delivery_mode": "canonical_straight_through",
        "record_ref": "rec_1234567890abcdef12345678",
        "items": [canonical_item],
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
        expected_rule_ids=["LX0609-001"],
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "ready"
    assert result["record_ref"] == "rec_1234567890abcdef12345678"
    assert result["items"] == [canonical_item]


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
