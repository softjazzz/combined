from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from medqc_ingest.control.admission import AdmissionService
from medqc_ingest.control.memory import MemoryJobRepository
from medqc_ingest.control.models import Actor, ControlError, SourceLimited
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.runner import JobRunner, UnitFailure, safe_result


def queued_job():
    repo = MemoryJobRepository()
    admission = AdmissionService(
        ProfileCatalog(), repo, clock=lambda: datetime(2026, 11, 1, tzinfo=timezone.utc)
    )
    job = admission.submit(
        {
            "profile": "core13",
            "interfaces": ["web.mr"],
            "start_date": "2026-10-26",
            "end_date": "2026-10-28",
            "mode": "replay",
            "publish": True,
        },
        Actor("test-operator", frozenset({"run"})),
        "request-one",
    )
    return repo, job


class FakeExecutor:
    def __init__(self, callback=None):
        self.calls = []
        self.callback = callback

    def execute(self, job, unit):
        self.calls.append(unit["unit_id"])
        if self.callback:
            return self.callback(job, unit)
        return {"counts": {"fetched": 1, "inserted": 0, "updated": 0, "unchanged": 1}}


def test_three_dates_then_publish_and_no_duplicate_finished_units():
    repo, job = queued_job()
    claimed = repo.claim("worker-one")
    executor = FakeExecutor()
    result = JobRunner(repo, executor).run(claimed)
    assert result["status"] == "succeeded"
    assert len(executor.calls) == 4
    assert [u["phase"] for u in repo.units(job["job_id"])] == ["extract"] * 3 + ["publish"]


def test_publish_failure_retries_only_publish_preserving_successful_extracts():
    repo, job = queued_job()

    def fail_publish(_job, unit):
        if unit["phase"] == "publish":
            raise UnitFailure("pipeline_failed", "test_publish", result={"code": "publish_failed"})
        return {"batch_id": 7}

    first = FakeExecutor(fail_publish)
    assert JobRunner(repo, first).run(repo.claim("worker-one"))["status"] == "failed"
    repo.retry(job["job_id"], "test-operator")
    second = FakeExecutor()
    assert JobRunner(repo, second).run(repo.claim("worker-two"))["status"] == "succeeded"
    assert len(second.calls) == 1
    assert repo.units(job["job_id"])[-1]["unit_id"] == second.calls[0]


def test_cancel_waits_for_current_unit_to_finish():
    repo, job = queued_job()

    def request_cancel(_job, _unit):
        repo.cancel(job["job_id"], "test-operator")
        return {"batch_id": 1}

    executor = FakeExecutor(request_cancel)
    result = JobRunner(repo, executor).run(repo.claim("worker-one"))
    assert result["status"] == "cancelled"
    assert len(executor.calls) == 1
    assert repo.units(job["job_id"])[0]["status"] == "succeeded"


def test_known_limit_is_visible_and_not_claimed_as_success():
    repo, job = queued_job()

    def limited(_job, unit):
        if unit["source_date"] == "2026-10-27":
            raise SourceLimited(result={"sqlstate": "HY000", "native": 400})
        return {}

    result = JobRunner(repo, FakeExecutor(limited)).run(repo.claim("worker-one"))
    assert result["status"] == "completed_with_source_limitations"
    assert repo.units(job["job_id"])[1]["status"] == "source_limited"


def test_unexpected_exception_text_never_enters_control_metadata():
    repo, job = queued_job()

    def fail(_job, _unit):
        raise RuntimeError("fictional-private-password-and-body")

    result = JobRunner(repo, FakeExecutor(fail)).run(repo.claim("worker-one"))
    assert result["status"] == "failed"
    assert "fictional-private" not in json.dumps(repo.get_job(job["job_id"]))
    assert "fictional-private" not in json.dumps(repo.units(job["job_id"]))


def test_unknown_commit_blocks_for_recovery_not_ordinary_retry():
    repo, job = queued_job()

    def uncertain(_job, _unit):
        raise UnitFailure(
            "pipeline_failed", "test_commit", result={"batch_id": 14}, recovery_required=True
        )

    result = JobRunner(repo, FakeExecutor(uncertain)).run(repo.claim("worker-one"))
    assert result["status"] == "recovery_required"
    assert repo.get_job(job["job_id"])["status"] == "recovery_required"
    assert repo.claim("worker-two") is None
    with pytest.raises(ControlError):
        repo.retry(job["job_id"], "test-operator")


def test_result_payload_and_uncontrolled_error_text_rejected():
    for result in (
        {"payload": {"name": "fictional"}},
        {"error_location": "raw text with spaces"},
        {"counts": {"fetched": True}},
        {"schema_hash": "not-a-hash"},
    ):
        with pytest.raises(ControlError):
            safe_result(result)


def test_audit_write_failure_after_execution_enters_recovery():
    repo, job = queued_job()
    original = repo.finish_unit
    repo.finish_unit = lambda *args, **kwargs: False
    result = JobRunner(repo, FakeExecutor()).run(repo.claim("worker-one"))
    repo.finish_unit = original
    assert result["status"] == "recovery_required"
    assert repo.get_job(job["job_id"])["status"] == "recovery_required"
