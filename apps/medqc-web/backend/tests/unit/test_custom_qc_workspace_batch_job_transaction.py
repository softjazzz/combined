from __future__ import annotations

from typing import Any

import pytest

from app.services import custom_qc_workspace_service as workspace_module


class _Insert:
    def __init__(self) -> None:
        self.payload: dict[str, Any] = {}

    def values(self, **payload: Any) -> "_Insert":
        self.payload = payload
        return self


class _Table:
    def insert(self) -> _Insert:
        return _Insert()


class _Session:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.inserted: list[dict[str, Any]] = []
        self.commits = 0
        self.closes = 0

    def execute(self, statement: _Insert) -> None:
        if self.error is not None:
            raise self.error
        self.inserted.append(statement.payload)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closes += 1


def _workspace() -> workspace_module.CustomQCWorkspaceService:
    workspace = workspace_module.CustomQCWorkspaceService.__new__(workspace_module.CustomQCWorkspaceService)
    workspace._batch_job_table = _Table()
    return workspace


def _create(workspace: workspace_module.CustomQCWorkspaceService, **kwargs: Any) -> dict[str, Any]:
    return workspace.create_batch_job(
        draft={"id": "draft-1", "rule_code": "CUST-001", "name": "测试规则", "scene": "final"},
        created_by="qc-user",
        scope="final",
        filters={},
        record_ids=["visit-1"],
        total_records=1,
        **kwargs,
    )


def test_external_session_inserts_without_commit_close_or_independent_read(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace()
    session = _Session()

    def unexpected_session() -> None:
        raise AssertionError("external transaction must not open another session")

    monkeypatch.setattr(workspace_module, "_session", unexpected_session)
    monkeypatch.setattr(
        workspace,
        "get_batch_job",
        lambda **_: pytest.fail("uncommitted job must not be read through a new session"),
    )

    job = _create(
        workspace,
        session=session,
        record_refs=[{"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}],
    )

    assert len(session.inserted) == 1
    assert session.commits == 0
    assert session.closes == 0
    assert job["id"] == session.inserted[0]["id"]
    assert job["status"] == "queued"
    assert job["record_refs"] == [
        {"institute_id": "hospital", "patient_id": "patient", "visit_id": "visit-1"}
    ]


def test_default_session_commits_closes_and_returns_existing_read_result(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = _workspace()
    session = _Session()
    monkeypatch.setattr(workspace_module, "_session", lambda: session)
    read_calls: list[dict[str, str]] = []

    def read_job(*, job_id: str, created_by: str) -> dict[str, str]:
        read_calls.append({"job_id": job_id, "created_by": created_by})
        return {"id": job_id, "status": "aggregated"}

    monkeypatch.setattr(workspace, "get_batch_job", read_job)

    job = _create(workspace)

    assert session.commits == 1
    assert session.closes == 1
    assert read_calls == [{"job_id": session.inserted[0]["id"], "created_by": "qc-user"}]
    assert job == {"id": session.inserted[0]["id"], "status": "aggregated"}


def test_external_session_insert_error_propagates_without_commit_or_close() -> None:
    workspace = _workspace()
    session = _Session(error=RuntimeError("insert failed"))

    with pytest.raises(RuntimeError, match="insert failed"):
        _create(workspace, session=session)

    assert session.commits == 0
    assert session.closes == 0
