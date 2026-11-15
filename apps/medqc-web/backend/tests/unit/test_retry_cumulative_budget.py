"""累计 MQ 自动恢复预算跨人工后继保留；全部使用合成内存 SQLite。"""

import json
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.qc_worker.recovery import RecoveryOutcome, WorkerRecovery
from app.services.qc_dispatch.repository import QCDispatchRepository
from test_qc_partial_failure_persistence import canonical_storage


pytestmark = pytest.mark.usefixtures("workspace_tables_without_database")


@pytest.fixture
def mq_storage(canonical_storage):
    service, engine, jobs, envelopes = canonical_storage
    sessions = sessionmaker(bind=engine)
    repository = QCDispatchRepository(sessions, jobs, schema=None)
    repository.dispatch_table.metadata.create_all(engine)
    service._qc_dispatch = repository
    source_id = str(uuid.uuid4())
    with sessions.begin() as session:
        filters = json.loads(session.execute(sa.select(jobs.c.filters_json)).scalar_one())
        filters["qc_dispatch"] = {"schema_version": 1, "mode": "rabbitmq"}
        session.execute(jobs.update().values(id=source_id, filters_json=json.dumps(filters)))
        repository.add_dispatch(session, job_id=source_id, mode="rabbitmq")
    return service, repository, sessions, jobs, envelopes, source_id


def _rows(sessions, table):
    with sessions() as session:
        return [dict(row) for row in session.execute(sa.select(table)).mappings()]


def _fail_without_output(service, job_id):
    # 模拟真正失联的旧兼容形态，不写入会否决自动恢复的任务级错误合同。
    claim = service.mark_batch_job_running(job_id=job_id)
    assert isinstance(claim, str)
    service.fail_batch_job(
        job_id=job_id, attempt_filters_json=claim, error_message="合成无产出中断",
    )
    assert service.get_batch_job_for_processing(job_id=job_id)["status"] == "failed"


def _prepare_source(storage, consumed):
    service, repository, sessions, _, _, source_id = storage
    _fail_without_output(service, source_id)
    with sessions.begin() as session:
        session.execute(repository.dispatch_table.update().where(
            repository.dispatch_table.c.job_id == source_id,
        ).values(failure_count=consumed))
    return source_id


def _successor_id(repository, source_id):
    source = repository.get_dispatch(source_id)
    assert source.recovery_reason_code == "retry_successor_created"
    return json.loads(source.recovery_scope_json)["retry_job_id"]


def test_manual_retry_preserves_two_consumed_attempts_then_auto_stops_at_three(mq_storage):
    service, repository, sessions, jobs, envelopes, _ = mq_storage
    source_id = _prepare_source(mq_storage, consumed=2)
    original_jobs = _rows(sessions, jobs)
    original_envelopes = _rows(sessions, envelopes)
    manual = service.retry_batch_job(job_id=source_id, created_by="tester")
    manual_id = manual["id"]
    assert manual_id != source_id
    assert repository.get_dispatch(manual_id).failure_count == 2
    assert repository.get_dispatch(manual_id).failure_budget == 3

    _fail_without_output(service, manual_id)
    recovery = WorkerRecovery(repository=repository, workspace=service)
    assert recovery.recover_failed_job(manual_id) == RecoveryOutcome.RETRY_SCHEDULED
    automatic_id = _successor_id(repository, manual_id)
    assert automatic_id not in {source_id, manual_id}
    assert repository.get_dispatch(automatic_id).failure_count == 3
    assert repository.get_dispatch(automatic_id).failure_budget == 3
    _fail_without_output(service, automatic_id)
    assert recovery.recover_failed_job(automatic_id) == RecoveryOutcome.TERMINAL_FAILURE
    assert repository.get_dispatch(automatic_id).last_failure_code == "retry_budget_exhausted"
    assert len(_rows(sessions, jobs)) == 3
    assert [row for row in _rows(sessions, jobs) if row["id"] == source_id] == original_jobs
    assert _rows(sessions, envelopes) == original_envelopes
    assert repository.get_dispatch(source_id).failure_count == 2
    assert len([row for row in _rows(sessions, repository.outbox_table) if row["target"] == "main"]) == 3


def test_exhausted_source_allows_one_idempotent_manual_successor_without_auto_credit(mq_storage):
    service, repository, sessions, jobs, _, _ = mq_storage
    source_id = _prepare_source(mq_storage, consumed=3)
    original_jobs = _rows(sessions, jobs)
    first = service.retry_batch_job(job_id=source_id, created_by="tester")
    duplicate = service.retry_batch_job(job_id=source_id, created_by="tester")
    assert duplicate["id"] == first["id"]
    assert duplicate["idempotency_reused"] is True
    assert repository.get_dispatch(first["id"]).failure_count == 3
    assert repository.get_dispatch(first["id"]).failure_budget == 3
    _fail_without_output(service, first["id"])
    recovery = WorkerRecovery(repository=repository, workspace=service)
    assert recovery.recover_failed_job(first["id"]) == RecoveryOutcome.TERMINAL_FAILURE
    assert len(_rows(sessions, jobs)) == 2
    assert [row for row in _rows(sessions, jobs) if row["id"] == source_id] == original_jobs
    assert len([row for row in _rows(sessions, repository.outbox_table) if row["target"] == "main"]) == 2


@pytest.mark.parametrize("automatic_first, expected_count", [(False, 2), (True, 3)])
def test_manual_and_auto_commit_orders_share_one_successor_without_double_charge(
    mq_storage, automatic_first, expected_count,
):
    service, repository, sessions, jobs, _, _ = mq_storage
    source_id = _prepare_source(mq_storage, consumed=2)
    recovery = WorkerRecovery(repository=repository, workspace=service)
    if automatic_first:
        assert recovery.recover_failed_job(source_id) == RecoveryOutcome.RETRY_SCHEDULED
        first_id = _successor_id(repository, source_id)
        reused = service.retry_batch_job(job_id=source_id, created_by="tester")
        assert reused["id"] == first_id
        assert reused["idempotency_reused"] is True
    else:
        first_id = service.retry_batch_job(job_id=source_id, created_by="tester")["id"]
        assert recovery.recover_failed_job(source_id) == RecoveryOutcome.RETRY_SCHEDULED
    assert recovery.recover_failed_job(source_id) == RecoveryOutcome.RETRY_SCHEDULED
    assert _successor_id(repository, source_id) == first_id
    assert repository.get_dispatch(first_id).failure_count == expected_count
    assert repository.get_dispatch(source_id).failure_count == 2
    assert len(_rows(sessions, jobs)) == 2
    assert len(_rows(sessions, repository.dispatch_table)) == 2
    assert len(_rows(sessions, repository.outbox_table)) == 2


def test_automatic_budget_rejection_rolls_back_new_job_dispatch_and_outbox(mq_storage):
    _, repository, sessions, jobs, _, _ = mq_storage
    source_id = _prepare_source(mq_storage, consumed=3)
    before = {table.name: _rows(sessions, table) for table in (
        jobs, repository.dispatch_table, repository.outbox_table,
    )}
    successor_id = str(uuid.uuid4())
    with pytest.raises(ValueError, match="retry_budget_exhausted"):
        with sessions.begin() as session:
            payload = {**before[jobs.name][0], "id": successor_id, "status": "queued"}
            session.execute(jobs.insert().values(**payload))
            repository.add_dispatch(session, job_id=successor_id, mode="rabbitmq")
            repository.link_retry_successor(
                session, source_job_id=source_id, source_generation=1,
                successor_job_id=successor_id, automatic=True,
            )
    for table in (jobs, repository.dispatch_table, repository.outbox_table):
        assert _rows(sessions, table) == before[table.name]
