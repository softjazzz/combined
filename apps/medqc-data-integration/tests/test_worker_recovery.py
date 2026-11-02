from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from test_job_runner import queued_job

from medqc_ingest.control.models import ControlError
from medqc_ingest.control.recovery import RecoveryService, validate_recovery_proof
from medqc_ingest.control.worker import WorkerSupervisor


class Process:
    def __init__(self):
        self.exit_code = None

    def poll(self):
        return self.exit_code


def test_supervisor_heartbeats_while_child_runs_and_never_claims_second_job():
    repo, job = queued_job()
    process, calls, ticks = Process(), [], []
    now = [0.0]
    supervisor = WorkerSupervisor(
        repo,
        lambda *args: calls.append(args) or process,
        worker_id="worker-one",
        clock=lambda: now[0],
        scheduler=type("Schedule", (), {"tick": lambda self: ticks.append(1)})(),
    )
    assert supervisor.tick()["status"] == "started"
    now[0] = 11
    assert supervisor.tick()["status"] == "running"
    repo.cancel(job["job_id"], "test-operator")
    assert supervisor.tick()["status"] == "running"  # 取消不kill子进程。
    assert len(calls) == 1 and len(ticks) == 3
    process.exit_code = 1
    assert supervisor.tick()["status"] == "recovery_required"
    assert supervisor.tick()["status"] == "idle"  # 仓储恢复闸门阻止再领。


def test_child_exit_zero_without_completion_is_not_succeeded():
    repo, _job = queued_job()
    process = Process()
    supervisor = WorkerSupervisor(repo, lambda *_: process, worker_id="worker-one")
    supervisor.tick()
    process.exit_code = 0
    assert supervisor.tick()["status"] == "recovery_required"


def test_process_launch_failure_preserves_recovery_state_without_exception_text():
    repo, job = queued_job()

    def fail(*_args):
        raise OSError("fictional-private-launch-details")

    result = WorkerSupervisor(repo, fail, worker_id="worker-one").tick()
    assert result["status"] == "recovery_required"
    assert "fictional-private" not in str(repo.get_job(job["job_id"]))


def test_recovery_requires_actual_checker_and_complete_safe_proof():
    repo, job = queued_job()
    claim = repo.claim("worker-one")
    repo.mark_recovery(job["job_id"], claim["lease_token"], "worker_child_exit")
    with pytest.raises(ControlError):
        RecoveryService(repo).reconcile(job["job_id"], "test-operator", "retry")
    for proof in (
        {},
        {"executor_stopped": True},
        {
            "executor_stopped": True,
            "target_locks_clear": False,
            "batches_checked": True,
            "commit_state": "idempotent_retry",
        },
    ):
        with pytest.raises(ControlError):
            validate_recovery_proof(proof)
    proof = {
        "executor_stopped": True,
        "target_locks_clear": True,
        "batches_checked": True,
        "commit_state": "idempotent_retry",
    }
    service = RecoveryService(repo, lambda _job_id: proof)
    assert service.reconcile(job["job_id"], "test-operator", "retry")["status"] == "queued"


def test_invalid_worker_timing_rejected():
    repo, _ = queued_job()
    with pytest.raises(ControlError):
        WorkerSupervisor(
            repo,
            lambda *_: Process(),
            worker_id="worker-one",
            lease_seconds=10,
            heartbeat_seconds=10,
        )


def test_transient_retry_is_bounded_and_uses_existing_job_after_backoff():
    repo, job = queued_job()
    processes = []
    now = [0.0]
    wall = datetime(2026, 11, 1, tzinfo=timezone.utc)
    repo.clock = lambda: wall + timedelta(seconds=now[0])

    def launch(*_):
        process = Process()
        processes.append(process)
        return process

    supervisor = WorkerSupervisor(repo, launch, worker_id="worker-one", clock=lambda: now[0])
    assert supervisor.tick()["status"] == "started"
    for number, delay in ((1, 30), (2, 120), (3, None)):
        active = repo.jobs[job["job_id"]]
        assert active["attempt_count"] == number
        repo.finish_job(
            job["job_id"],
            active["lease_token"],
            "failed",
            {"error_kind": "source_connect_error", "sqlstate": "08001"},
        )
        processes[-1].exit_code = 1
        result = supervisor.tick()
        if delay is None:
            assert result["status"] == "failed" and supervisor.retry_pending is None
        else:
            assert result["status"] == "retry_wait"
            assert supervisor.tick()["status"] == "retry_wait"
            now[0] += delay
            assert supervisor.tick()["status"] == "started"
    assert len(processes) == 3


def test_authentication_failure_is_not_auto_retried():
    repo, job = queued_job()
    process = Process()
    supervisor = WorkerSupervisor(repo, lambda *_: process, worker_id="worker-one")
    supervisor.tick()
    active = repo.jobs[job["job_id"]]
    repo.finish_job(
        job["job_id"],
        active["lease_token"],
        "failed",
        {"error_kind": "source_connect_error", "sqlstate": "HY000", "native": 417},
    )
    process.exit_code = 1
    assert supervisor.tick()["status"] == "failed"
    assert supervisor.retry_pending is None


def test_cancel_during_retry_backoff_prevents_automatic_retry():
    repo, job = queued_job()
    process, calls = Process(), []
    now = [0.0]
    supervisor = WorkerSupervisor(
        repo,
        lambda *args: calls.append(args) or process,
        worker_id="worker-one",
        clock=lambda: now[0],
    )
    supervisor.tick()
    active = repo.jobs[job["job_id"]]
    repo.finish_job(
        job["job_id"],
        active["lease_token"],
        "failed",
        {"error_kind": "source_connect_error", "sqlstate": "08001"},
    )
    process.exit_code = 1
    assert supervisor.tick()["status"] == "retry_wait"
    repo.cancel(job["job_id"], "test-operator")
    now[0] = 31
    assert supervisor.tick()["status"] == "idle"
    assert len(calls) == 1


def test_job_budget_only_requests_cancel_and_never_kills_child():
    repo, job = queued_job()
    process = Process()
    now = [0.0]
    supervisor = WorkerSupervisor(
        repo, lambda *_: process, worker_id="worker-one", clock=lambda: now[0], job_budget_seconds=5
    )
    supervisor.tick()
    now[0] = 6
    assert supervisor.tick()["status"] == "running"
    assert repo.get_job(job["job_id"])["cancel_requested"]
    active = repo.jobs[job["job_id"]]
    repo.finish_job(job["job_id"], active["lease_token"], "cancelled")
    process.exit_code = 0
    assert supervisor.tick()["status"] == "cancelled"
