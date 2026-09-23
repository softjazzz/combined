from __future__ import annotations

from typing import Any

import pytest

from app.services import sichuan_workspace_batch_worker as sichuan_worker
from app.services.luxian_0916 import batch_worker as luxian_worker


VALID_REF = {"institute_id": "I-1", "patient_id": "P-1", "visit_id": "V-1"}


class _Workspace:
    def __init__(self, *, luxian: bool, filters: dict[str, Any]) -> None:
        self.job = {
            "id": "job-1",
            "scope": "running" if luxian else "final",
            "record_ids": ["V-1"],
            "filters": filters,
        }
        self.collect_calls: list[dict[str, Any]] = []
        self.failures: list[str] = []

    def get_batch_job_for_processing(self, *, job_id: str) -> dict[str, Any]:
        assert job_id == "job-1"
        return self.job

    def mark_batch_job_running(self, *, job_id: str) -> bool:
        assert job_id == "job-1"
        return True

    def collect_records(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.collect_calls.append(kwargs)
        return []

    def fail_batch_job(self, *, job_id: str, error_message: str) -> None:
        assert job_id == "job-1"
        self.failures.append(error_message)


@pytest.mark.asyncio
@pytest.mark.parametrize("worker_name", ["sichuan", "luxian"])
@pytest.mark.parametrize(
    "refs",
    [None, [], [{}], [{"institute_id": "I-1", "patient_id": "P-1", "record_id": "V-1"}],
     [{"institute_id": "I-1", "patient_id": " ", "visit_id": "V-1"}],
     [VALID_REF, {"visit_id": "V-2"}]],
    ids=["missing", "empty", "empty-ref", "legacy-record-id", "blank-coordinate", "mixed-invalid"],
)
async def test_task_job_rejects_invalid_refs_before_collect(
    monkeypatch: pytest.MonkeyPatch, worker_name: str, refs: Any
) -> None:
    filters = {"task_id": "task-1", "rule_ids": ["SC-001"]}
    if worker_name == "luxian":
        filters.pop("rule_ids")
        filters["rule_set_key"] = luxian_worker.LUXIAN_0916_RULE_SET_KEY
    if refs is not None:
        filters["record_refs"] = refs
    workspace = _Workspace(luxian=worker_name == "luxian", filters=filters)

    if worker_name == "luxian":
        await luxian_worker.run_luxian_0916_batch_job("job-1", workspace=workspace)
    else:
        monkeypatch.setattr(
            sichuan_worker, "get_product_activation_service",
            lambda: type("Activation", (), {"enforce": lambda self: None})(),
        )

        async def qc_service_provider() -> object:
            return object()

        await sichuan_worker.run_sichuan_workspace_batch_job(
            "job-1", workspace=workspace, qc_service_provider=qc_service_provider
        )

    assert workspace.collect_calls == []
    assert workspace.failures


@pytest.mark.asyncio
@pytest.mark.parametrize("worker_name", ["sichuan", "luxian"])
@pytest.mark.parametrize("task_job", [False, True], ids=["ordinary", "task"])
async def test_valid_task_refs_and_ordinary_fallback_reach_collect(
    monkeypatch: pytest.MonkeyPatch, worker_name: str, task_job: bool
) -> None:
    filters: dict[str, Any] = {"rule_ids": ["SC-001"]}
    if worker_name == "luxian":
        filters.pop("rule_ids")
        filters["rule_set_key"] = luxian_worker.LUXIAN_0916_RULE_SET_KEY
    if task_job:
        filters.update(task_id="task-1", record_refs=[dict(VALID_REF)])
    workspace = _Workspace(luxian=worker_name == "luxian", filters=filters)

    if worker_name == "luxian":
        await luxian_worker.run_luxian_0916_batch_job("job-1", workspace=workspace)
    else:
        monkeypatch.setattr(
            sichuan_worker, "get_product_activation_service",
            lambda: type("Activation", (), {"enforce": lambda self: None})(),
        )

        async def qc_service_provider() -> object:
            return object()

        await sichuan_worker.run_sichuan_workspace_batch_job(
            "job-1", workspace=workspace, qc_service_provider=qc_service_provider
        )

    assert len(workspace.collect_calls) == 1
    assert workspace.collect_calls[0]["record_refs"] == ([VALID_REF] if task_job else None)
    assert workspace.collect_calls[0]["record_ids"] == (None if task_job else ["V-1"])
