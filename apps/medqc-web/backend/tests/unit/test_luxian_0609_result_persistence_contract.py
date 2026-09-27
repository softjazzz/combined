"""LX0609 Canonical 结果持久化合同。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService


pytestmark = pytest.mark.usefixtures("offline_workspace_schema")


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


class _UpdateResult:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _CompletionSession:
    def __init__(self, row: dict[str, Any], *, completion_rowcount: int = 1) -> None:
        self._row = row
        self._completion_rowcount = completion_rowcount
        self.execute_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0
        self.executed_statements: list[Any] = []

    def execute(self, _statement: Any) -> _Rows | _UpdateResult:
        self.executed_statements.append(_statement)
        self.execute_count += 1
        if self.execute_count == 1:
            return _Rows(self._row)
        return _UpdateResult(self._completion_rowcount)

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1


class _ParentRefreshSession:
    """模拟父刷新时，取消请求已使状态条件 UPDATE 不命中的竞争窗口。"""

    def __init__(self, parent_row: dict[str, Any], *, parent_update_rowcount: int) -> None:
        self._parent_row = parent_row
        self._parent_update_rowcount = parent_update_rowcount
        self.execute_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    def execute(self, _statement: Any) -> _Rows | _UpdateResult:
        self.execute_count += 1
        if self.execute_count == 1:
            return _Rows(self._parent_row)
        return _UpdateResult(self._parent_update_rowcount)

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


def test_complete_batch_job_rejects_malformed_result_without_completing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """畸形结果混入合法结果时，公开完成入口必须整体回滚。"""

    session = _CompletionSession(
        {
            "id": "job-1",
            "parent_job_id": None,
            "created_by": "reviewer-1",
            "filters_json": "{}",
        }
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    with pytest.raises(ValueError, match="Canonical Envelope 结果项格式非法"):
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
                "invalid-result-item",
            ],
            failed_records=[],
        )

    assert session.commit_count == 0
    assert session.rollback_count == 1


def test_complete_batch_job_rejects_unexplained_non_compliant_without_completing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """解释合同不完整的确定问题不得提交任务或Canonical结果。"""

    session = _CompletionSession(
        {
            "id": "job-1",
            "parent_job_id": None,
            "created_by": "reviewer-1",
            "filters_json": "{}",
        }
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)

    with pytest.raises(ValueError, match="LX0609 客户结果解释合同不完整"):
        CustomQCWorkspaceService().complete_batch_job(
            job_id="job-1",
            summary={"total_records": 1, "success_count": 1},
            items=[
                {
                    "institute_id": "inst-1",
                    "patient_id": "patient-1",
                    "visit_id": "visit-1",
                    "rule_id": "LX0609-071",
                    "status": "non_compliant",
                    "result_status": "non_compliant",
                    "display_status": "non_compliant",
                    "is_compliant": False,
                    "reason_code": "association_failed",
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


def test_complete_batch_job_canceled_before_completion_does_not_write_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """取消与完成竞争时，迟到结果不得进入正式病例结果。"""

    session = _CompletionSession(
        {
            "id": "job-canceled",
            "parent_job_id": "parent-canceled",
            "created_by": "reviewer-1",
            "filters_json": "{}",
        },
        completion_rowcount=0,
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    service = CustomQCWorkspaceService()
    envelope_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        service,
        "_write_record_result_envelopes",
        lambda *_args, **kwargs: envelope_calls.append(kwargs),
    )
    refreshed_parent_ids: list[str | None] = []
    monkeypatch.setattr(
        service,
        "refresh_parent_batch_job",
        lambda *, parent_job_id: refreshed_parent_ids.append(parent_job_id),
    )

    service.complete_batch_job(
        job_id="job-canceled",
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

    assert envelope_calls == []
    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert refreshed_parent_ids == ["parent-canceled"]


def test_refresh_parent_canceled_before_final_child_does_not_write_envelopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """最后一个子任务迟到收尾时，已取消父任务不能交付 Canonical 结果。"""

    session = _ParentRefreshSession(
        {"id": "parent-canceled", "job_kind": "parent", "status": "running", "summary_json": "{}"},
        parent_update_rowcount=0,
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    service = CustomQCWorkspaceService()
    monkeypatch.setattr(
        service,
        "_aggregate_parent_job",
        lambda *_args, **_kwargs: {
            "id": "parent-canceled",
            "job_kind": "parent",
            "status": "completed",
            "summary": {"progress": {"step_key": "completed"}},
            "children": [
                {
                    "items": [
                        {
                            "institute_id": "inst-1",
                            "patient_id": "patient-1",
                            "visit_id": "visit-1",
                            "rule_id": "LX0609-001",
                            "status": "compliant",
                        }
                    ]
                }
            ],
        },
    )
    envelope_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        service,
        "_write_record_result_envelopes",
        lambda *_args, **kwargs: envelope_calls.append(kwargs),
    )

    service.refresh_parent_batch_job(parent_job_id="parent-canceled")

    assert envelope_calls == []
    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.close_count == 1


def test_refresh_parent_completed_writes_envelopes_before_single_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未取消的父任务仍须在状态更新后、同一提交前交付 Canonical 结果。"""

    session = _ParentRefreshSession(
        {"id": "parent-completed", "job_kind": "parent", "status": "running", "summary_json": "{}"},
        parent_update_rowcount=1,
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    service = CustomQCWorkspaceService()
    monkeypatch.setattr(
        service,
        "_aggregate_parent_job",
        lambda *_args, **_kwargs: {
            "id": "parent-completed",
            "job_kind": "parent",
            "status": "completed",
            "summary": {"progress": {"step_key": "completed"}},
            "children": [{"items": [{"rule_id": "LX0609-001", "status": "compliant"}]}],
        },
    )
    write_commit_counts: list[int] = []
    monkeypatch.setattr(
        service,
        "_write_record_result_envelopes",
        lambda *_args, **_kwargs: write_commit_counts.append(session.commit_count),
    )

    service.refresh_parent_batch_job(parent_job_id="parent-completed")

    assert write_commit_counts == [0]
    assert session.commit_count == 1
    assert session.rollback_count == 0


def test_cancel_batch_job_does_not_overwrite_completion_that_won_the_lock_race(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """取消已读到 running 但完成先提交时，最终状态必须保持 completed。"""

    session = _CompletionSession(
        {
            "id": "job-completed-first",
            "parent_job_id": None,
            "created_by": "reviewer-1",
            "status": "running",
            "summary_json": "{}",
        },
        completion_rowcount=0,
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    service = CustomQCWorkspaceService()
    final_job = {
        "id": "job-completed-first",
        "created_by": "reviewer-1",
        "status": "completed",
    }
    monkeypatch.setattr(service, "get_batch_job", lambda **_kwargs: final_job)

    result = service.cancel_batch_job(job_id="job-completed-first", created_by="reviewer-1")

    assert result == final_job
    assert session.commit_count == 0
    assert session.rollback_count == 1
    update_sql = str(session.executed_statements[1])
    assert "status IN" in update_sql


def test_complete_independent_result_can_skip_luxian_0609_canonical_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """独立规则包只保存自身任务 items，不进入 0609 Canonical 合同。"""

    session = _CompletionSession(
        {
            "id": "job-0916",
            "parent_job_id": None,
            "created_by": "reviewer-1",
            "filters_json": (
                '{"rule_set_key":"luxian_0916_qc_v1",'
                '"rule_ids":["LX0916-001"]}'
            ),
        }
    )
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    service = CustomQCWorkspaceService()
    envelope_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        service,
        "_write_record_result_envelopes",
        lambda *_args, **kwargs: envelope_calls.append(kwargs),
    )

    service.complete_batch_job(
        job_id="job-0916",
        summary={
            "rule_count": 1,
            "total_records": 1,
            "success_count": 1,
            "failed_count": 0,
            "completed_rule_count": 1,
            "failed_rule_count": 0,
            "execution_status": "completed",
        },
        items=[
            {
                "institute_id": "inst-1",
                "patient_id": "patient-1",
                "visit_id": "visit-1",
                "rule_id": "LX0916-001",
                "status": "data_quality_gap",
                "reason_code": "semantic_fact_unavailable",
                "findings": "",
            }
        ],
        failed_records=[],
        persist_record_envelopes=False,
    )

    assert envelope_calls == []
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

    with pytest.raises(ValueError, match="Canonical Envelope 病例三坐标不完整"):
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
