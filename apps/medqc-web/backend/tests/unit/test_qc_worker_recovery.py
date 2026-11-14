from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import uuid

import pytest
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.qc_worker.recovery import RecoveryOutcome, WorkerRecovery
from app.qc_worker.batch_consumer import BatchConsumer, ConsumerDecision
from app.services.qc_dispatch.contracts import BatchDispatchEnvelope
from app.services.qc_dispatch.execution import run_batch_dispatch_job
from app.services.qc_dispatch.outbox import batch_job_identity_table
from app.services.qc_dispatch.repository import QCDispatchRepository


@dataclass
class _Dispatch:
    mode: str = "rabbitmq"
    generation: int = 1
    failure_count: int = 0
    failure_budget: int = 2
    recovery_kind: str | None = None


class _Repository:
    def __init__(self, *, status="failed", dispatch=None):
        self.status = status
        self.dispatch = dispatch or _Dispatch()
        self.ensured = []
        self.recoveries = []
        self.terminal = []
        self.candidates = []

    def get_dispatch(self, _job_id):
        return self.dispatch

    def get_job_status(self, _job_id):
        return self.status

    def ensure_due_delivery(self, job_id, generation, *, target="main"):
        self.ensured.append((job_id, generation, target))

    def register_recovery(self, job_id, generation, *, recovery_kind, reason_code, scope=None):
        if generation != self.dispatch.generation:
            return False
        self.dispatch.recovery_kind = recovery_kind
        self.recoveries.append((job_id, generation, recovery_kind, reason_code, scope))
        return True

    def record_terminal_failure(self, job_id, generation, *, error_code):
        if self.status != "failed" or generation != self.dispatch.generation:
            return False
        self.terminal.append((job_id, generation, error_code))
        return True

    def list_recovery_candidates(self, *, limit=100):
        return self.candidates[:limit]


class _Workspace:
    def __init__(self, job, *, saved_refs=()):
        self.job = job
        self.saved_refs = tuple(saved_refs)
        self.retry_calls = []
        self.stale_mode = None

    def get_batch_job_for_processing(self, *, job_id):
        assert job_id == self.job["id"]
        return self.job

    def list_record_result_case_refs(self, *, job_id):
        assert job_id == self.job["id"]
        return self.saved_refs

    def list_queued_luxian_0609_batch_job_ids(self, *, dispatch_mode="legacy"):
        assert dispatch_mode == "rabbitmq"
        return (self.job["id"],)

    def retry_batch_job(self, **kwargs):
        self.retry_calls.append(kwargs)
        self.job = {**self.job, "status": "queued"}
        return self.job

    def fail_stale_luxian_0609_running_jobs(self, *, stale_before, dispatch_mode):
        assert isinstance(stale_before, datetime)
        self.stale_mode = dispatch_mode
        return (self.job["id"],)


def _job(*, items=None, failures=None):
    return {
        "id": "job-1",
        "job_kind": "leaf",
        "created_by": "tester",
        "status": "failed",
        "filters": {
            "rule_set_key": "luxian_0609_qc_v1",
            "qc_dispatch": {"schema_version": 1, "mode": "rabbitmq"},
        },
        "items": list(items or []),
        "failed_records": list(failures or []),
        "_claim_filters_json": "attempt-v1",
    }


def test_startup_queued_job_ensures_current_generation_delivery():
    repository = _Repository(status="queued", dispatch=_Dispatch(generation=3))
    workspace = _Workspace(_job())
    outcome = WorkerRecovery(repository=repository, workspace=workspace).ensure_queued_delivery("job-1")
    assert outcome == RecoveryOutcome.DELIVERY_ENSURED
    assert repository.recoveries == [(
        "job-1",
        3,
        "delivery",
        "startup_queued_reconcile",
        None,
    )]
    assert repository.ensured == [("job-1", 3, "main")]


@pytest.mark.parametrize("stage", ["registration", "terminal"])
def test_manual_successor_wins_recovery_cas_without_stopping_owner(stage):
    from types import SimpleNamespace
    repository = _Repository(dispatch=_Dispatch(failure_budget=0 if stage == "terminal" else 2))
    workspace = _Workspace(_job())
    original_get = repository.get_dispatch

    def lookup(job_id):
        if job_id == "job-2":
            return SimpleNamespace(job_id="job-2", mode="rabbitmq")
        return original_get(job_id)

    def manual_wins(*_args, **_kwargs):
        repository.dispatch.recovery_reason_code = "retry_successor_created"
        repository.dispatch.recovery_scope_json = json.dumps({"retry_job_id": "job-2"})
        return False

    repository.get_dispatch = lookup
    if stage == "registration":
        repository.register_recovery = manual_wins
    else:
        repository.record_terminal_failure = manual_wins
    result = WorkerRecovery(repository=repository, workspace=workspace).recover_failed_job("job-1")
    assert result == RecoveryOutcome.RETRY_SCHEDULED
    assert workspace.retry_calls == []


@pytest.mark.parametrize("status,expected", [(403, RecoveryOutcome.MANUAL_SCOPE_REQUIRED),
                                             (503, RecoveryOutcome.SKIPPED),
                                             ("retry_rule_scope_paused", RecoveryOutcome.MANUAL_SCOPE_REQUIRED),
                                             ("retry_lineage_identity_mismatch", RecoveryOutcome.MANUAL_SCOPE_REQUIRED)])
def test_permission_failure_does_not_stop_later_recovery_candidates(status, expected):
    from fastapi import HTTPException
    from types import SimpleNamespace
    repository = _Repository()
    repository.candidates = [SimpleNamespace(job_id="job-1"), SimpleNamespace(job_id="job-2")]
    # 两个任务的持久恢复状态相互独立。
    repository.register_recovery = lambda job_id, generation, **kwargs: (
        repository.recoveries.append((job_id, generation, kwargs)) or True)

    class Workspace:
        def get_batch_job_for_processing(self, *, job_id):
            return {**_job(), "id": job_id}
        def list_record_result_case_refs(self, *, job_id):
            return ()
        def retry_batch_job(self, *, job_id, **kwargs):
            if job_id == "job-1":
                if isinstance(status, str):
                    raise ValueError(status)
                raise HTTPException(status, "controlled permission error")
            return {"id": "new-job-2", "status": "queued"}

    outcomes = WorkerRecovery(repository=repository, workspace=Workspace()).recover_failed_candidates()
    assert outcomes == {"job-1": expected, "job-2": RecoveryOutcome.RETRY_SCHEDULED}
    assert repository.terminal == []
    if status == 403:
        assert any(item[2].get("reason_code") == "retry_permission_revoked" for item in repository.recoveries)
    if isinstance(status, str):
        assert any(item[2].get("reason_code") == "retry_contract_rejected" for item in repository.recoveries)


def test_startup_recovery_reopens_confirmed_delivery_with_same_message_id():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    jobs = batch_job_identity_table(schema=None)
    jobs.metadata.create_all(engine)
    repository = QCDispatchRepository(sessions, jobs, schema=None)
    repository.dispatch_table.metadata.create_all(engine)
    job_id = str(uuid.uuid4())
    filters = {
        "rule_set_key": "luxian_0609_qc_v1",
        "qc_dispatch": {"schema_version": 1, "mode": "rabbitmq"},
    }
    try:
        with sessions.begin() as session:
            session.execute(jobs.insert().values(
                id=job_id,
                status="queued",
                filters_json=json.dumps(filters),
                items_json=None,
                failed_records_json=None,
                job_kind="leaf",
                parent_job_id=None,
                created_by="synthetic-worker",
            ))
            repository.add_dispatch(session, job_id=job_id, mode="rabbitmq")

        claimed = repository.claim_outbox("publisher", lease_seconds=10, limit=1)
        assert len(claimed) == 1
        original_message_id = claimed[0].message_id
        assert repository.mark_confirmed(
            original_message_id,
            claimed[0].publication_token,
        )
        assert repository.get_outbox(original_message_id).status == "confirmed"

        workspace = _Workspace({
            **_job(),
            "id": job_id,
            "filters": filters,
        })
        outcome = WorkerRecovery(
            repository=repository,
            workspace=workspace,
        ).ensure_queued_delivery(job_id)
        assert outcome == RecoveryOutcome.DELIVERY_ENSURED
        reopened = repository.get_outbox(original_message_id)
        assert reopened is not None
        assert reopened.message_id == original_message_id
        assert reopened.status == "pending"
    finally:
        engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("rule_set_key", ["luxian_0916", "custom_qc"])
async def test_unsupported_existing_mq_job_is_dead_lettered_once_and_acknowledged(
    rule_set_key,
):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    jobs = batch_job_identity_table(schema=None)
    jobs.metadata.create_all(engine)
    repository = QCDispatchRepository(sessions, jobs, schema=None)
    repository.dispatch_table.metadata.create_all(engine)
    job_id = str(uuid.uuid4())
    filters = {
        "rule_set_key": rule_set_key,
        "qc_dispatch": {"schema_version": 1, "mode": "rabbitmq"},
    }

    class Workspace:
        def get_batch_job_for_processing(self, *, job_id):
            with sessions() as session:
                status = session.execute(
                    select(jobs.c.status).where(jobs.c.id == job_id)
                ).scalar_one()
            return {
                "id": job_id,
                "job_kind": "leaf",
                "status": status,
                "filters": filters,
                "_claim_filters_json": json.dumps(filters),
            }

        def fail_batch_job(self, *, job_id, **_kwargs):
            with sessions.begin() as session:
                session.execute(
                    update(jobs).where(jobs.c.id == job_id).values(status="failed")
                )

    class Delivery:
        def __init__(self, body):
            self.body = body
            self.acked = False

        async def ack(self):
            self.acked = True

        async def reject(self, *, requeue=False):
            raise AssertionError(f"unsupported persisted job must use dead intent: {requeue}")

    try:
        with sessions.begin() as session:
            session.execute(jobs.insert().values(
                id=job_id,
                status="queued",
                filters_json=json.dumps(filters),
                items_json=None,
                failed_records_json=None,
                job_kind="leaf",
                parent_job_id=None,
                created_by="synthetic-worker",
            ))
            repository.add_dispatch(session, job_id=job_id, mode="rabbitmq")
        main_outbox = repository.claim_outbox("publisher", lease_seconds=10, limit=1)[0]
        envelope = BatchDispatchEnvelope.from_bytes(main_outbox.payload)

        async def must_not_run():
            raise AssertionError("unsupported job must not create a QC service")

        await run_batch_dispatch_job(
            envelope,
            workspace=Workspace(),
            dispatch_repository=repository,
            qc_service_provider=must_not_run,
        )

        dispatch = repository.get_dispatch(job_id)
        assert repository.get_job_status(job_id) == "failed"
        assert dispatch.status == "failed"
        assert dispatch.last_failure_code == "worker_failed"
        with sessions() as session:
            dead_count = session.execute(
                select(repository.outbox_table.c.id).where(
                    repository.outbox_table.c.job_id == job_id,
                    repository.outbox_table.c.target == "dead",
                )
            ).all()
        assert len(dead_count) == 1

        delivery = Delivery(envelope.to_bytes())

        async def must_not_execute(_envelope):
            raise AssertionError("terminal unsupported job must not execute twice")

        decision = await BatchConsumer(
            repository=repository,
            execute_job=must_not_execute,
        ).handle_delivery(delivery)
        assert decision is ConsumerDecision.ACK_FAILED_RECORDED
        assert delivery.acked is True
    finally:
        engine.dispose()


def test_stale_attempt_with_saved_success_requires_manual_scope_and_never_retries_all():
    repository = _Repository()
    workspace = _Workspace(_job(items=[{"rule_id": "R1"}]))
    outcome = WorkerRecovery(repository=repository, workspace=workspace).recover_failed_job("job-1")
    assert outcome == RecoveryOutcome.MANUAL_SCOPE_REQUIRED
    assert workspace.retry_calls == []
    assert repository.recoveries[0][2] == "manual_scope_required"


def test_stale_attempt_with_canonical_success_also_blocks_full_replay():
    repository = _Repository()
    workspace = _Workspace(_job(), saved_refs=("case-key",))
    outcome = WorkerRecovery(repository=repository, workspace=workspace).recover_failed_job("job-1")
    assert outcome == RecoveryOutcome.MANUAL_SCOPE_REQUIRED
    assert workspace.retry_calls == []


def test_failed_candidate_survives_crash_between_stale_fence_and_retry():
    repository = _Repository()
    repository.dispatch.job_id = "job-1"
    repository.candidates = [repository.dispatch]
    workspace = _Workspace(_job())

    outcomes = WorkerRecovery(
        repository=repository,
        workspace=workspace,
    ).recover_failed_candidates()
    assert outcomes == {"job-1": RecoveryOutcome.RETRY_SCHEDULED}
    assert len(workspace.retry_calls) == 1


def test_no_saved_success_can_schedule_one_bounded_new_generation():
    repository = _Repository()
    workspace = _Workspace(_job())
    outcome = WorkerRecovery(
        repository=repository,
        workspace=workspace,
        retry_delay_seconds=7,
    ).recover_failed_job("job-1")
    assert outcome == RecoveryOutcome.RETRY_SCHEDULED
    assert repository.recoveries[0][2] == "unstarted"
    assert workspace.retry_calls == [{
        "job_id": "job-1",
        "created_by": "tester",
        "automatic": True,
        "expected_attempt_filters_json": "attempt-v1",
        "retry_delay_seconds": 7.0,
    }]


def test_explicit_failed_scope_preserves_success_and_uses_scoped_retry():
    repository = _Repository()
    workspace = _Workspace(_job(
        items=[{"rule_id": "R0"}],
        failures=[{"rule_id": "R1", "record_id": "opaque-record-key"}],
    ))
    outcome = WorkerRecovery(repository=repository, workspace=workspace).recover_failed_job("job-1")
    assert outcome == RecoveryOutcome.RETRY_SCHEDULED
    assert repository.recoveries[0][2] == "failed_scope"
    assert len(workspace.retry_calls) == 1


def test_exhausted_failure_budget_becomes_durable_terminal_failure():
    repository = _Repository(dispatch=_Dispatch(failure_count=2, failure_budget=2))
    workspace = _Workspace(_job())
    outcome = WorkerRecovery(repository=repository, workspace=workspace).recover_failed_job("job-1")
    assert outcome == RecoveryOutcome.TERMINAL_FAILURE
    assert repository.terminal == [("job-1", 1, "retry_budget_exhausted")]
    assert workspace.retry_calls == []


def test_stale_scan_is_strictly_scoped_to_rabbitmq_jobs():
    repository = _Repository()
    workspace = _Workspace(_job())
    outcomes = WorkerRecovery(
        repository=repository,
        workspace=workspace,
        stale_after_seconds=60,
    ).recover_stale_once(now=datetime(2026, 10, 30, 12, 0, 0))
    assert workspace.stale_mode == "rabbitmq"
    assert outcomes["job-1"] == RecoveryOutcome.RETRY_SCHEDULED


def test_legacy_dispatch_is_not_recovered_by_independent_worker():
    repository = _Repository(dispatch=_Dispatch(mode="legacy"))
    workspace = _Workspace(_job())
    outcome = WorkerRecovery(repository=repository, workspace=workspace).recover_failed_job("job-1")
    assert outcome == RecoveryOutcome.SKIPPED
    assert workspace.retry_calls == []
    assert repository.recoveries == []
