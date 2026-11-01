from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from test_job_runner import FakeExecutor, queued_job

from medqc_ingest.control import bootstrap
from medqc_ingest.control.cli import build_parser
from medqc_ingest.control.models import Actor, ControlError
from medqc_ingest.control.runner import UnitFailure


def services(tmp_path):
    bindings_file = tmp_path / "bindings.json"
    bindings_file.write_text("{}", encoding="utf-8")
    repository, job = queued_job()
    bindings = Mock(return_value={})
    runtime = SimpleNamespace(
        worker=SimpleNamespace(
            worker_id="worker-one",
            lease_seconds=180,
            heartbeat_seconds=10,
            poll_seconds=0.01,
            bindings_file=bindings_file,
            automatic_retries=2,
            job_budget_seconds=3600,
        ),
        load_bindings=bindings,
    )
    return SimpleNamespace(
        runtime=runtime, repository=repository, catalog=object(), admission=object()
    ), job


def test_child_rejects_lost_token_before_bindings_and_source_instantiation(tmp_path):
    control, job = services(tmp_path)
    control.repository.claim("worker-one")
    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch("medqc_ingest.control.pipeline.PipelineExecutor") as executor,
        pytest.raises(ControlError) as error,
    ):
        bootstrap.run_child(Path("fictional-config"), job["job_id"], str(uuid4()))
    assert error.value.code == "lease_lost"
    control.runtime.load_bindings.assert_not_called()
    executor.assert_not_called()


@pytest.mark.parametrize("recovery", [False, True])
def test_child_exit_status_reflects_failed_or_unknown_commit_job(recovery, tmp_path):
    control, job = services(tmp_path)
    claimed = control.repository.claim("worker-one")

    def fail(_job, _unit):
        raise UnitFailure("execution_failed", "fictional_test", recovery_required=recovery)

    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch("medqc_ingest.control.pipeline.PipelineExecutor", return_value=FakeExecutor(fail)),
    ):
        status = bootstrap.run_child(
            Path("fictional-config"), job["job_id"], claimed["lease_token"]
        )
    assert status == 1
    assert control.repository.get_job(job["job_id"])["status"] == (
        "recovery_required" if recovery else "failed"
    )


def test_child_success_preserves_normal_zero_exit(tmp_path):
    control, job = services(tmp_path)
    claimed = control.repository.claim("worker-one")
    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch("medqc_ingest.control.pipeline.PipelineExecutor", return_value=FakeExecutor()),
    ):
        assert (
            bootstrap.run_child(Path("fictional-config"), job["job_id"], claimed["lease_token"])
            == 0
        )
    assert control.repository.get_job(job["job_id"])["status"] == "succeeded"


def test_worker_rejects_missing_bindings_before_claim_or_credential_reads(tmp_path):
    control, job = services(tmp_path)
    control.runtime.worker.bindings_file.unlink()
    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch("medqc_ingest.control.worker.WorkerSupervisor") as supervisor,
        pytest.raises(ControlError) as error,
    ):
        bootstrap.run_worker(Path("fictional-config"), once=True)
    assert error.value.location == "worker_bindings_required"
    assert control.repository.get_job(job["job_id"])["status"] == "queued"
    control.runtime.load_bindings.assert_not_called()
    supervisor.assert_not_called()


def test_once_drains_pending_retry_and_returns_actual_logical_completion(capsys, tmp_path):
    control, _ = services(tmp_path)
    instances = []

    class Supervisor:
        def __init__(self, *args, **kwargs):
            self.process = None
            self.retry_pending = None
            self.calls = 0
            instances.append(self)

        def tick(self):
            self.calls += 1
            if self.calls == 1:
                self.process = object()
                return {"status": "started"}
            if self.calls == 2:
                self.process = None
                self.retry_pending = ("fictional-job", 0)
                return {"status": "retry_wait"}
            if self.calls == 3:
                self.retry_pending = None
                self.process = object()
                return {"status": "started"}
            self.process = None
            return {"status": "succeeded"}

    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch("medqc_ingest.control.worker.WorkerSupervisor", Supervisor),
        patch("medqc_ingest.control.scheduler.Scheduler"),
        patch.object(bootstrap.signal, "signal"),
        patch.object(bootstrap.time, "sleep"),
    ):
        result = bootstrap.run_worker(Path("fictional-config"), once=True)
    assert result == 0 and instances[0].calls == 4
    assert json.loads(capsys.readouterr().out)["status"] == "succeeded"


def test_once_failed_job_has_nonzero_exit_and_launch_argv_has_only_control_references(
    capsys, tmp_path
):
    control, _ = services(tmp_path)
    launches = []
    job_id, token = str(uuid4()), str(uuid4())

    class Supervisor:
        def __init__(self, _repository, factory, **kwargs):
            self.factory, self.process, self.retry_pending = factory, None, None
            self.calls = 0

        def tick(self):
            self.calls += 1
            if self.calls == 1:
                self.process = self.factory(job_id, token)
                return {"status": "started"}
            self.process = None
            return {"status": "failed"}

    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch("medqc_ingest.control.worker.WorkerSupervisor", Supervisor),
        patch("medqc_ingest.control.scheduler.Scheduler"),
        patch.object(bootstrap.signal, "signal"),
        patch.object(bootstrap.time, "sleep"),
        patch.object(
            bootstrap.subprocess,
            "Popen",
            side_effect=lambda args, **kwargs: launches.append((args, kwargs)) or object(),
        ),
    ):
        result = bootstrap.run_worker(Path("fictional-config"), once=True)
    assert result == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    args, kwargs = launches[0]
    assert args[1:4] == ["-m", "medqc_ingest.control.bootstrap", "run-child"]
    assert args[-4:] == ["--job-id", job_id, "--lease-token", token]
    assert kwargs["stdin"] == bootstrap.subprocess.DEVNULL
    assert kwargs["stdout"] == bootstrap.subprocess.DEVNULL
    assert "PYTHONPATH" in kwargs["env"]


def recovery_command(tmp_path, decision="retry", proof=None):
    control, job = services(tmp_path)
    control.catalog = Mock()
    claimed = control.repository.claim("worker-one")
    assert control.repository.mark_recovery(job["job_id"], claimed["lease_token"], "child_lost")
    proof_file = tmp_path / "recovery-proof.json"
    proof_file.write_text(
        json.dumps(
            proof
            if proof is not None
            else {
                "executor_stopped": True,
                "target_locks_clear": True,
                "batches_checked": True,
                "commit_state": "idempotent_retry",
            }
        ),
        encoding="utf-8",
    )
    args = build_parser().parse_args(
        [
            "--config",
            str(tmp_path / "worker.json"),
            "job",
            "reconcile",
            job["job_id"],
            "--decision",
            decision,
            "--proof-file",
            str(proof_file),
        ]
    )
    return control, job, args


@pytest.mark.parametrize(
    "decision,status", [("retry", "queued"), ("cancel", "cancelled"), ("fail", "failed")]
)
def test_reconcile_cli_uses_worker_role_without_bindings_and_records_operator_attestation(
    decision, status, capsys, tmp_path
):
    control, job, args = recovery_command(tmp_path, decision)
    old_attempts = dict(control.repository.attempts)
    with (
        patch.object(bootstrap, "build_control", return_value=control) as build,
        patch.object(
            bootstrap, "_actor", return_value=Actor("recovery-operator", frozenset({"schedule"}))
        ),
    ):
        assert bootstrap.dispatch(args) == 0
    build.assert_called_once_with(args.config, role="worker")
    assert json.loads(capsys.readouterr().out)["status"] == status
    assert control.repository.get_job(job["job_id"])["status"] == status
    assert control.repository.attempts == old_attempts
    event = control.repository.events[-1]
    assert event["details"]["verification"] == "operator-attested"
    assert event["actor_id"] == "recovery-operator"
    control.runtime.load_bindings.assert_not_called()
    assert control.catalog.validate.call_count == (1 if decision == "retry" else 0)


def test_reconcile_cli_rejects_run_only_actor_before_reading_proof(tmp_path):
    control, job, args = recovery_command(tmp_path)
    args.proof_file.unlink()
    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch.object(bootstrap, "_actor", return_value=Actor("runner", frozenset({"run"}))),
        pytest.raises(ControlError) as error,
    ):
        bootstrap.dispatch(args)
    assert error.value.code == "forbidden"
    assert control.repository.get_job(job["job_id"])["status"] == "recovery_required"


@pytest.mark.parametrize(
    "mutation",
    [{"executor_stopped": False}, {"commit_state": "unknown"}, {"sql": "fictional-secret"}],
)
def test_reconcile_cli_rejects_unverified_or_extra_proof_fields(mutation, tmp_path):
    proof = {
        "executor_stopped": True,
        "target_locks_clear": True,
        "batches_checked": True,
        "commit_state": "idempotent_retry",
    }
    proof.update(mutation)
    control, job, args = recovery_command(tmp_path, proof=proof)
    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch.object(bootstrap, "_actor", return_value=Actor("operator", frozenset({"schedule"}))),
        pytest.raises(ControlError) as error,
    ):
        bootstrap.dispatch(args)
    assert "fictional-secret" not in str(error.value)
    assert control.repository.get_job(job["job_id"])["status"] == "recovery_required"
    control.catalog.validate.assert_not_called()


def test_reconcile_retry_checks_current_profile_approval_before_requeue(tmp_path):
    control, job, args = recovery_command(tmp_path)
    control.catalog.validate.side_effect = ControlError("profile_disabled", "profile_gate", 409)
    with (
        patch.object(bootstrap, "build_control", return_value=control),
        patch.object(bootstrap, "_actor", return_value=Actor("operator", frozenset({"schedule"}))),
        pytest.raises(ControlError) as error,
    ):
        bootstrap.dispatch(args)
    assert error.value.code == "profile_disabled"
    assert control.repository.get_job(job["job_id"])["status"] == "recovery_required"
