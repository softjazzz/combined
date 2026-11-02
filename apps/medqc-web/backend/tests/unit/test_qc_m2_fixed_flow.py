"""M2 真实 owner 的合成内存事务、发布、消费与 Canonical 固定流。"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import uuid

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.qc_worker.batch_consumer import BatchConsumer, ConsumerDecision
import app.services.custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import (
    CustomQCWorkspaceService,
    _batch_jobs_table,
    _record_result_envelopes_table,
)
from app.services.luxian_0609_result_schema import RULE_SET_VERSION
from app.services.qc_dispatch.contracts import BatchDispatchEnvelope
from app.services.qc_dispatch.publisher import OutboxPublisher, OutboxPublisherSettings
from app.services.qc_dispatch.repository import QCDispatchRepository
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
import app.services.qc_dispatch.repository as repository_module
from tests.luxian_0609_published_result_support import (
    ADMISSION_TIMELINESS_RULE_ID,
    published_lx0609_items,
)
from tests.scheduler_support.fake_broker import FakeBroker, FakeDelivery


@pytest.fixture
def m2_store():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    jobs = _batch_jobs_table(readonly=True)
    jobs.metadata.create_all(engine)
    repository = QCDispatchRepository(sessions, jobs, schema=None)
    repository.dispatch_table.metadata.create_all(engine)
    envelopes = _record_result_envelopes_table()
    envelopes.metadata.create_all(engine)
    try:
        yield sessions, jobs, repository, envelopes
    finally:
        engine.dispose()


@pytest.fixture
def fixed_admission_result() -> dict[str, object]:
    # 同步 fixture 在 pytest 启动 async 用例前完成正式纯程序执行/聚合链。
    return published_lx0609_items()[ADMISSION_TIMELINESS_RULE_ID]


def _job_values(job_id: str) -> dict[str, object]:
    filters = {
        "record_refs": [
            {
                "institute_id": "synthetic-institute",
                "patient_id": "synthetic-patient",
                "visit_id": "synthetic-visit",
            }
        ],
        "rule_ids": [ADMISSION_TIMELINESS_RULE_ID],
        "rule_set_key": "luxian_0609_qc_v1",
        "rule_set_version": RULE_SET_VERSION,
    }
    return {
        "id": job_id,
        "draft_id": "synthetic-m2-draft",
        "rule_code": "LX0609",
        "rule_name": "synthetic-m2-fixed-flow",
        "scene": "final",
        "scope": "final",
        "status": "queued",
        "filters_json": json.dumps(filters, separators=(",", ":"), sort_keys=True),
        "record_ids_json": "[]",
        "summary_json": None,
        "items_json": None,
        "failed_records_json": None,
        "error_message": None,
        "job_kind": "leaf",
        "parent_job_id": None,
        "created_by": "synthetic-m2-user",
        "created_at": datetime(2026, 10, 30, 12, 0, 0),
        "updated_at": datetime(2026, 10, 30, 12, 0, 0),
        "total_records": 1,
        "success_count": 0,
        "failed_count": 0,
        "issue_records": 0,
        "compliant_records": 0,
        "total_tokens": 0,
        "total_processing_time": 0.0,
    }


def test_task_and_outbox_share_one_rollback_boundary(m2_store) -> None:
    sessions, jobs, repository, _envelopes = m2_store
    job_id = str(uuid.uuid4())

    with sessions() as session:
        session.execute(jobs.insert().values(**_job_values(job_id)))
        repository.add_dispatch(
            session,
            job_id=job_id,
            mode="rabbitmq",
            enqueue_leaf=True,
        )
        session.rollback()

    assert repository.get_job_status(job_id) is None
    assert repository.get_dispatch(job_id) is None
    assert repository.claim_outbox("rollback-check", 5, 1) == []


@pytest.mark.asyncio
async def test_cancel_and_generation_fence_prevent_late_execution(m2_store) -> None:
    sessions, jobs, repository, _envelopes = m2_store
    job_id = str(uuid.uuid4())
    with sessions.begin() as session:
        session.execute(jobs.insert().values(**_job_values(job_id)))
        dispatch = repository.add_dispatch(
            session,
            job_id=job_id,
            mode="rabbitmq",
            enqueue_leaf=True,
        )
    outbox = repository.claim_outbox("fence-test", 5, 1)[0]
    stale_delivery = FakeDelivery(body=outbox.payload)

    with sessions.begin() as session:
        next_generation = repository.advance_generation(
            session,
            job_id=job_id,
            expected_generation=dispatch.generation,
        )
        assert next_generation == 2
        assert not repository.transition_dispatch(
            job_id=job_id,
            generation=1,
            from_statuses=("queued",),
            to_status="completed",
            session=session,
        )

    execution_calls = 0

    async def must_not_execute(_envelope) -> None:
        nonlocal execution_calls
        execution_calls += 1

    consumer = BatchConsumer(repository=repository, execute_job=must_not_execute)
    decision = await consumer.handle_delivery(stale_delivery)
    assert decision is ConsumerDecision.ACK_OLD_GENERATION
    assert stale_delivery.ack_count == 1
    assert execution_calls == 0

    current_outbox = repository.claim_outbox("cancel-test", 5, 1)[0]
    current_envelope = BatchDispatchEnvelope.from_bytes(current_outbox.payload)
    assert current_envelope.generation == 2
    with sessions.begin() as session:
        session.execute(update(jobs).where(jobs.c.id == job_id).values(status="canceled"))
    canceled_delivery = FakeDelivery(body=current_outbox.payload)
    canceled_decision = await consumer.handle_delivery(canceled_delivery)
    assert canceled_decision is ConsumerDecision.ACK_TERMINAL
    assert canceled_delivery.ack_count == 1
    assert execution_calls == 0


@pytest.mark.asyncio
async def test_poison_body_is_rejected_without_log_or_dead_copy(
    m2_store,
    caplog,
) -> None:
    _sessions, _jobs, repository, _envelopes = m2_store
    patient_marker = "synthetic-patient-name-must-not-leak"
    delivery = FakeDelivery(
        body=json.dumps({"patient_name": patient_marker}).encode("utf-8")
    )
    broker = FakeBroker()

    async def must_not_execute(_envelope) -> None:
        raise AssertionError("poison message must not execute")

    consumer = BatchConsumer(repository=repository, execute_job=must_not_execute)
    decision = await consumer.handle_delivery(delivery)

    assert decision is ConsumerDecision.REJECT_INVALID
    assert delivery.reject_count == 1
    assert delivery.rejected_requeue is False
    assert patient_marker not in caplog.text
    assert broker.bodies(target="dead") == ()


@pytest.mark.asyncio
async def test_confirm_loss_redelivery_executes_once_and_reads_canonical(
    m2_store,
    monkeypatch,
    fixed_admission_result,
) -> None:
    sessions, jobs, repository, envelopes = m2_store
    clock = {"now": datetime(2026, 10, 30, 12, 0, 0)}
    monkeypatch.setattr(repository_module, "_utcnow", lambda: clock["now"])
    job_id = str(uuid.uuid4())
    job_values = _job_values(job_id)
    with sessions.begin() as session:
        session.execute(jobs.insert().values(**job_values))
        repository.add_dispatch(
            session,
            job_id=job_id,
            mode="rabbitmq",
            enqueue_leaf=True,
        )

    broker = FakeBroker()
    broker.lose_next_confirm = True
    publisher = OutboxPublisher(
        repository,
        broker,
        OutboxPublisherSettings(owner="synthetic-publisher", lease_seconds=5),
    )

    first_publish = await publisher.run_once()
    assert first_publish.claimed == 1
    assert first_publish.confirmation_unknown == 1
    assert first_publish.published == 0

    clock["now"] += timedelta(seconds=6)
    second_publish = await publisher.run_once()
    assert second_publish.claimed == 1
    assert second_publish.published == 1
    deliveries = broker.deliveries()
    assert len(deliveries) == 2
    assert deliveries[0].body == deliveries[1].body

    # 由正式纯程序执行/聚合链产生固定结果；没有模型客户端或患者原文。
    fixed_result = {
        **fixed_admission_result,
        "institute_id": "synthetic-institute",
        "patient_id": "synthetic-patient",
        "visit_id": "synthetic-visit",
        "record_id": "synthetic-visit",
    }
    execution_calls = 0
    model_calls = 0
    store = CanonicalResultStore(envelopes)
    workspace = object.__new__(CustomQCWorkspaceService)
    workspace._batch_job_table = jobs
    workspace._record_result_envelope_table = envelopes
    workspace._qc_dispatch = repository
    monkeypatch.setattr(workspace_module, "_session", sessions)

    async def execute_fixed_result(envelope) -> None:
        nonlocal execution_calls
        execution_calls += 1
        attempt_filters_json = workspace.mark_batch_job_running(job_id=envelope.job_id)
        assert isinstance(attempt_filters_json, str)
        assert workspace.complete_batch_job(
            job_id=envelope.job_id,
            summary={
                "execution_status": "completed",
                "total_records": 1,
                "success_count": 1,
                "failed_count": 0,
                "issue_records": 0,
                "compliant_records": 1,
                "total_tokens": 0,
                "total_processing_time": 0.0,
            },
            items=[fixed_result],
            failed_records=[],
            attempt_filters_json=attempt_filters_json,
        ) is True

    consumer = BatchConsumer(
        repository=repository,
        execute_job=execute_fixed_result,
    )
    first_decision = await consumer.handle_delivery(deliveries[0])
    duplicate_decision = await consumer.handle_delivery(deliveries[1])

    assert first_decision is ConsumerDecision.ACK_TERMINAL
    assert duplicate_decision is ConsumerDecision.ACK_TERMINAL
    assert deliveries[0].ack_count == deliveries[1].ack_count == 1
    assert execution_calls == 1
    assert model_calls == 0

    with sessions() as session:
        loaded = store.load_selected(
            session,
            root_job_id=job_id,
            institute_id="synthetic-institute",
            patient_id="synthetic-patient",
            visit_id="synthetic-visit",
            rule_set_key="luxian_0609_qc_v1",
            rule_set_version=RULE_SET_VERSION,
        )
    assert loaded["job_id"] == job_id
    assert [item["rule_id"] for item in loaded["items"]] == [
        ADMISSION_TIMELINESS_RULE_ID
    ]
    assert all(
        key not in loaded["items"][0]
        for key in ("institute_id", "patient_id", "visit_id")
    )
