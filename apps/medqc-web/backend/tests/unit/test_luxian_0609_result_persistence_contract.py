"""LX0609 Canonical 结果持久化合同。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260812_000032_index_luxian_0609_latest_results.py"
)


class _Rows:
    def __init__(self, row: dict[str, Any]) -> None:
        self._row = row

    def mappings(self) -> "_Rows":
        return self

    def first(self) -> dict[str, Any]:
        return self._row


class _CompletionSession:
    def __init__(self, row: dict[str, Any]) -> None:
        self._row = row
        self.execute_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    def execute(self, _statement: Any) -> _Rows | None:
        self.execute_count += 1
        if self.execute_count == 1:
            return _Rows(self._row)
        return None

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1


class _EmptyRows:
    def mappings(self) -> "_EmptyRows":
        return self

    def all(self) -> list[dict[str, Any]]:
        return []


class _QueryCaptureSession:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    def execute(self, statement: Any) -> _EmptyRows:
        self.statements.append(statement)
        return _EmptyRows()

    def close(self) -> None:
        return None


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "luxian_0609_latest_results_index_migration",
        MIGRATION_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_complete_batch_job_does_not_commit_completed_when_canonical_envelope_write_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Envelope 交付失败时，公开完成入口必须整体失败而不是留下 completed。"""

    session = _CompletionSession(
        {
            "id": "job-1",
            "parent_job_id": None,
            "created_by": "reviewer-1",
            "filters_json": "{}",
        }
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    service = CustomQCWorkspaceService()

    def fail_envelope_write(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError(
            "INSERT INTO luxian_0609_record_result_envelopes",
            {},
            RuntimeError("envelope unavailable"),
        )

    monkeypatch.setattr(service, "_write_record_result_envelopes", fail_envelope_write)

    with pytest.raises(OperationalError, match="envelope unavailable"):
        service.complete_batch_job(
            job_id="job-1",
            summary={"total_records": 1, "success_count": 1},
            items=[
                {
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                    "rule_id": "LX0609-001",
                    "status": "compliant",
                }
            ],
            failed_records=[],
        )

    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_complete_batch_job_commits_task_and_canonical_envelope_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """任务状态和 Canonical Envelope 成功时必须由同一事务一次提交。"""

    session = _CompletionSession(
        {
            "id": "job-1",
            "parent_job_id": None,
            "created_by": "reviewer-1",
            "filters_json": "{}",
        }
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    service = CustomQCWorkspaceService()
    write_commit_counts: list[int] = []

    def capture_envelope_write(*_args: Any, **_kwargs: Any) -> None:
        write_commit_counts.append(session.commit_count)

    monkeypatch.setattr(service, "_write_record_result_envelopes", capture_envelope_write)

    service.complete_batch_job(
        job_id="job-1",
        summary={"total_records": 1, "success_count": 1},
        items=[
            {
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "visit_id": "visit-1",
                "rule_id": "LX0609-001",
                "status": "compliant",
            }
        ],
        failed_records=[],
    )

    assert write_commit_counts == [0]
    assert session.commit_count == 1
    assert session.rollback_count == 0


def test_complete_batch_job_rejects_luxian_result_without_frozen_case_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LX0609 冻结病例没有形成 Envelope 时不得标记任务完成。"""

    session = _CompletionSession(
        {
            "id": "job-1",
            "parent_job_id": None,
            "created_by": "reviewer-1",
            "filters_json": (
                '{"rule_set_key":"luxian_0609_qc_v1",'
                '"record_refs":[{"institute_id":"inst-1",'
                '"patient_id":"patient-1","visit_id":"visit-1"}]}'
            ),
        }
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    with pytest.raises(ValueError, match="Canonical Envelope 病例集合不完整"):
        CustomQCWorkspaceService().complete_batch_job(
            job_id="job-1",
            summary={"total_records": 1, "success_count": 1},
            items=[{"rule_id": "LX0609-001", "status": "compliant"}],
            failed_records=[],
        )

    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_complete_batch_job_rejects_incomplete_luxian_rule_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """活动、门控和暂停规则必须全部形成唯一 Canonical 结果后才能完成。"""

    session = _CompletionSession(
        {
            "id": "job-1",
            "parent_job_id": None,
            "created_by": "reviewer-1",
            "filters_json": (
                '{"rule_set_key":"luxian_0609_qc_v1",'
                '"rule_ids":["LX0609-001","LX0609-002"],'
                '"paused_customer_rule_ids":["LX0609-033"],'
                '"record_refs":[{"institute_id":"inst-1",'
                '"patient_id":"patient-1","visit_id":"visit-1"}]}'
            ),
        }
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    with pytest.raises(ValueError, match="Canonical Envelope 规则集合不完整"):
        CustomQCWorkspaceService().complete_batch_job(
            job_id="job-1",
            summary={"total_records": 1, "success_count": 1},
            items=[
                {
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                    "rule_id": "LX0609-001",
                    "status": "compliant",
                },
                {
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                    "rule_id": "LX0609-033",
                    "status": "not_executed",
                },
            ],
            failed_records=[],
        )

    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_latest_single_record_result_uses_case_coordinate_without_scanning_record_ids_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """最新结果读取应由三坐标 Envelope 定位，不再扫描任务 JSON。"""

    session = _QueryCaptureSession()
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    result = CustomQCWorkspaceService().get_latest_luxian_0609_record_result(
        institute_id="inst-1",
        patient_id="patient-1",
        visit_id="visit-1",
        rule_set_key="luxian_0609_qc_v1",
        rule_set_version="2026-06-09",
    )

    assert result["state"] == "not_found"
    statement = session.statements[0]
    query = str(statement.whereclause)
    full_query = str(statement)
    assert "record_ids_json" not in query
    for column in (
        "institute_id",
        "patient_id",
        "visit_id",
        "rule_set_key",
        "rule_set_version",
    ):
        assert column in query
    assert "root_job_id" in full_query


def test_latest_result_index_migration_matches_runtime_case_coordinate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """发布迁移必须为运行时三坐标最新结果查询建立同口径索引。"""

    migration = _load_migration()

    assert migration.revision == "20260812_000032"
    assert migration.down_revision == "20260811_000031"
    assert migration.INDEX_COLUMNS == (
        "institute_id",
        "patient_id",
        "visit_id",
        "rule_set_key",
        "rule_set_version",
        "root_job_id",
    )
    monkeypatch.setenv("DB_SCHEMA_MODE", "single")
    assert migration._target_schema() == "public"
    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    assert migration._target_schema() == "qc"
