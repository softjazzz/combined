from __future__ import annotations

import importlib.util
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.qc_dispatch.contracts import (
    BatchDispatchEnvelope,
    dispatch_filter_payload,
    qc_dispatch_mode_from_filters,
)
from app.services.qc_dispatch.outbox import qc_dispatch_tables
from app.services.qc_dispatch.repository import (
    QCDispatchRepository,
    QCDispatchSchemaUnavailable,
)


def _uuid() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def repository():
    engine = sa.create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    job_metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        job_metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filters_json", sa.Text, nullable=False),
        sa.Column("items_json", sa.Text),
        sa.Column("failed_records_json", sa.Text),
        sa.Column("job_kind", sa.String(20)),
        sa.Column("parent_job_id", sa.String(36)),
        sa.Column("created_by", sa.String(64)),
    )
    job_metadata.create_all(engine)
    tables = qc_dispatch_tables(schema=None)
    tables.dispatch.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    return QCDispatchRepository(sessions, jobs, None), sessions, jobs, tables


def _insert_job(session, jobs, job_id: str, *, status: str = "queued", kind: str = "leaf"):
    session.execute(
        jobs.insert().values(
            id=job_id,
            status=status,
            filters_json=json.dumps(
                {"rule_set_key": "luxian_0609_qc_v1", "qc_dispatch": dispatch_filter_payload("rabbitmq")}
            ),
            items_json=None,
            failed_records_json=None,
            job_kind=kind,
            parent_job_id=None,
            created_by="synthetic",
        )
    )


def test_envelope_is_minimal_strict_and_bounded():
    envelope = BatchDispatchEnvelope.new(job_id=_uuid(), generation=1)
    payload = envelope.to_bytes()

    assert len(payload) < 4096
    assert BatchDispatchEnvelope.from_bytes(payload) == envelope
    assert set(json.loads(payload)) == {"schema_version", "message_id", "job_id", "generation"}

    raw = json.loads(payload)
    raw["patient_name"] = "synthetic"
    with pytest.raises(ValueError, match="fields"):
        BatchDispatchEnvelope.from_bytes(json.dumps(raw).encode())
    with pytest.raises(ValueError, match="positive"):
        BatchDispatchEnvelope.new(job_id=_uuid(), generation=0)
    with pytest.raises(ValueError, match="size"):
        BatchDispatchEnvelope.from_bytes(b"x" * 4097)


def test_dispatch_filter_missing_is_legacy_but_invalid_never_falls_back():
    assert qc_dispatch_mode_from_filters({}) == "legacy"
    assert qc_dispatch_mode_from_filters(
        {"qc_dispatch": {"schema_version": 1, "mode": "rabbitmq"}}
    ) == "rabbitmq"

    invalid_values = [
        None,
        "rabbitmq",
        {"schema_version": 1, "mode": "legacy"},
        {"schema_version": 2, "mode": "rabbitmq"},
        {"schema_version": 1, "mode": "rabbitmq", "extra": True},
    ]
    for value in invalid_values:
        with pytest.raises(ValueError):
            qc_dispatch_mode_from_filters({"qc_dispatch": value})


def test_job_and_outbox_rollback_together(repository):
    repo, sessions, jobs, tables = repository
    job_id = _uuid()
    session = sessions()
    _insert_job(session, jobs, job_id)
    repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")
    session.rollback()
    session.close()

    with sessions() as check:
        assert check.scalar(sa.select(sa.func.count()).select_from(jobs)) == 0
        assert check.scalar(sa.select(sa.func.count()).select_from(tables.dispatch)) == 0
        assert check.scalar(sa.select(sa.func.count()).select_from(tables.outbox)) == 0


def test_broker_unavailable_keeps_due_delivery_pending(repository):
    repo, sessions, jobs, _ = repository
    job_id = _uuid()
    with sessions.begin() as session:
        _insert_job(session, jobs, job_id)
        repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")

    claimed = repo.claim_outbox("publisher-a", lease_seconds=10, limit=1)
    assert len(claimed) == 1
    assert repo.mark_publish_failed(
        claimed[0].message_id,
        claimed[0].publication_token,
        "connection_failed",
        5,
    )
    pending = repo.get_outbox(claimed[0].message_id)
    assert pending is not None
    assert pending.status == "pending"
    assert pending.last_error_code == "connection_failed"


def test_claim_lease_and_publication_token_are_cas_fenced(repository):
    repo, sessions, jobs, _ = repository
    job_id = _uuid()
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    with sessions.begin() as session:
        _insert_job(session, jobs, job_id)
        repo.add_dispatch(session, job_id=job_id, mode="rabbitmq", available_at=now)

    first = repo.claim_outbox("publisher-a", lease_seconds=10, limit=1, now=now)[0]
    assert repo.claim_outbox(
        "publisher-b", lease_seconds=10, limit=1, now=now + timedelta(seconds=9)
    ) == []
    second = repo.claim_outbox(
        "publisher-b", lease_seconds=10, limit=1, now=now + timedelta(seconds=11)
    )[0]

    assert first.message_id == second.message_id
    assert first.publication_token != second.publication_token
    assert second.publish_attempts == 2
    assert not repo.mark_confirmed(first.message_id, first.publication_token)
    assert repo.mark_confirmed(second.message_id, second.publication_token)


def test_confirm_loss_republishes_same_message_without_new_generation(repository):
    repo, sessions, jobs, _ = repository
    job_id = _uuid()
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)
    with sessions.begin() as session:
        _insert_job(session, jobs, job_id)
        repo.add_dispatch(session, job_id=job_id, mode="rabbitmq", available_at=now)

    lost = repo.claim_outbox("publisher-a", lease_seconds=2, limit=1, now=now)[0]
    retried = repo.claim_outbox(
        "publisher-a", lease_seconds=2, limit=1, now=now + timedelta(seconds=3)
    )[0]
    assert retried.message_id == lost.message_id
    assert retried.generation == lost.generation == 1
    assert BatchDispatchEnvelope.from_bytes(retried.payload).message_id == lost.message_id


def test_generation_advance_is_atomic_and_old_generation_cannot_be_reopened(repository):
    repo, sessions, jobs, tables = repository
    job_id = _uuid()
    with sessions.begin() as session:
        _insert_job(session, jobs, job_id, status="failed")
        repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")

    with sessions.begin() as session:
        session.execute(jobs.update().where(jobs.c.id == job_id).values(status="queued"))
        assert repo.advance_generation(session, job_id=job_id, expected_generation=1) == 2

    assert repo.get_dispatch(job_id).generation == 2
    with pytest.raises(ValueError, match="not current"):
        repo.ensure_due_delivery(job_id, 1)
    with sessions() as session:
        deliveries = session.execute(
            sa.select(tables.outbox.c.generation).where(tables.outbox.c.job_id == job_id)
        ).scalars().all()
    assert deliveries == [1, 2]


def test_parent_has_identity_but_only_child_is_delivered(repository):
    repo, sessions, jobs, tables = repository
    parent_id, child_id = _uuid(), _uuid()
    with sessions.begin() as session:
        _insert_job(session, jobs, parent_id, kind="parent")
        _insert_job(session, jobs, child_id, kind="child")
        session.execute(
            jobs.update().where(jobs.c.id == child_id).values(parent_job_id=parent_id)
        )
        repo.add_dispatch(
            session, job_id=parent_id, mode="rabbitmq", enqueue_leaf=False
        )
        repo.add_dispatch(session, job_id=child_id, mode="rabbitmq", enqueue_leaf=True)

    assert repo.get_dispatch(parent_id) is not None
    assert repo.get_dispatch(child_id) is not None
    with sessions() as session:
        delivered_job_ids = session.execute(
            sa.select(tables.outbox.c.job_id).where(tables.outbox.c.target == "main")
        ).scalars().all()
    assert delivered_job_ids == [child_id]


def test_confirmed_delivery_requires_prior_recovery_registration_to_reopen(repository):
    repo, sessions, jobs, _ = repository
    job_id = _uuid()
    with sessions.begin() as session:
        _insert_job(session, jobs, job_id)
        repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")
    claimed = repo.claim_outbox("publisher", lease_seconds=10, limit=1)[0]
    assert repo.mark_confirmed(claimed.message_id, claimed.publication_token)

    assert repo.ensure_due_delivery(job_id, 1).status == "confirmed"
    assert repo.register_recovery(
        job_id, 1, recovery_kind="delivery", reason_code="lease_expired"
    )
    assert repo.ensure_due_delivery(job_id, 1).status == "pending"


def test_terminal_failure_requires_matching_job_state_and_generation(repository):
    repo, sessions, jobs, tables = repository
    job_id = _uuid()
    with sessions.begin() as session:
        _insert_job(session, jobs, job_id)
        repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")

    assert not repo.record_terminal_failure(job_id, 1, error_code="worker_failed")
    with sessions.begin() as session:
        session.execute(jobs.update().where(jobs.c.id == job_id).values(status="failed"))
    assert not repo.record_terminal_failure(job_id, 2, error_code="worker_failed")
    assert repo.record_terminal_failure(job_id, 1, error_code="worker_failed")
    with sessions() as session:
        targets = session.execute(
            sa.select(tables.outbox.c.target).where(tables.outbox.c.job_id == job_id)
        ).scalars().all()
    assert set(targets) == {"main", "dead"}


def test_readiness_probe_fails_closed_without_migration_tables():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    metadata = sa.MetaData()
    jobs = sa.Table(
        "custom_qc_batch_jobs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
    )
    metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    repo = QCDispatchRepository(sessions, jobs, None)

    with pytest.raises(QCDispatchSchemaUnavailable):
        repo.assert_schema_ready()


def test_migration_schema_owner_matches_runtime_mode(monkeypatch):
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "20261030_000056_qc_dispatch_outbox.py"
    )
    spec = importlib.util.spec_from_file_location("qc_dispatch_migration_056", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class Inspector:
        def __init__(self, tables):
            self.tables = tables

        def get_schema_names(self):
            return ["public", "qc"]

        def get_table_names(self, *, schema):
            return self.tables.get(schema, [])

    both = Inspector({None: [migration.JOB_TABLE], "qc": [migration.JOB_TABLE]})
    monkeypatch.setenv("DB_SCHEMA_MODE", "single")
    assert migration._target_schema(both) is None
    monkeypatch.setenv("DB_SCHEMA_MODE", "split")
    assert migration._target_schema(both) == "qc"

    mismatch = Inspector({None: [migration.JOB_TABLE], "qc": []})
    with pytest.raises(RuntimeError, match="job table is missing"):
        migration._target_schema(mismatch)


@pytest.fixture()
def workspace_service(monkeypatch, tmp_path):
    from app.services import custom_qc_workspace_service as workspace_module

    engine = sa.create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "SessionLocal", sessions)
    monkeypatch.setattr(workspace_module, "DB_SCHEMA_MODE", "single")
    monkeypatch.setattr(
        workspace_module,
        "get_settings",
        lambda: SimpleNamespace(QC_TASK_DISPATCH_MODE="rabbitmq", QC_DISPATCH_STATE_DIR=str(tmp_path),
            LLM_DISPATCH_MODE="gateway", LLM_GATEWAY_URL="http://synthetic-gateway",
            LLM_GATEWAY_TOKEN="synthetic-token", LLM_GATEWAY_PROFILE="alibaba_first_pass"),
    )
    workspace_module._drafts_table.cache_clear()
    workspace_module._batch_jobs_table.cache_clear()
    workspace_module._record_result_envelopes_table.cache_clear()
    draft_table = workspace_module._drafts_table(readonly=True)
    batch_table = workspace_module._batch_jobs_table(readonly=True)
    draft_table.metadata.create_all(engine)
    batch_table.metadata.create_all(engine)
    service = workspace_module.CustomQCWorkspaceService(readonly=True)
    service._record_result_envelope_table.metadata.create_all(engine)
    dispatch_tables = qc_dispatch_tables(schema=None)
    dispatch_tables.dispatch.metadata.create_all(engine)
    try:
        yield workspace_module, service, sessions, dispatch_tables
    finally:
        workspace_module._drafts_table.cache_clear()
        workspace_module._batch_jobs_table.cache_clear()
        workspace_module._record_result_envelopes_table.cache_clear()
        engine.dispose()


def _create_workspace_job(service, *, kind: str = "leaf", parent_id: str | None = None):
    return service.create_batch_job(
        draft={
            "id": "sichuan-rule-library",
            "rule_code": "SC-BATCH",
            "name": "合成正式任务",
            "scene": "final",
        },
        created_by="synthetic",
        scope="final",
        filters={
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "rule_ids": ["LX0609-001"],
            "lx0609_task_runtime": {
                role: {"dispatch_mode": "gateway", "gateway_profile": "alibaba_first_pass",
                       "gateway_endpoint_sha256": "a" * 64}
                for role in ("first_pass", "adjudicator")
            },
        },
        record_ids=["synthetic-visit"],
        total_records=1,
        job_kind=kind,
        parent_job_id=parent_id,
    )


def test_workspace_create_commits_job_dispatch_and_outbox_together(workspace_service):
    _, service, sessions, tables = workspace_service
    job = _create_workspace_job(service)

    assert qc_dispatch_mode_from_filters(job["filters"]) == "rabbitmq"
    with sessions() as session:
        assert session.scalar(
            sa.select(sa.func.count()).select_from(service._batch_job_table)
        ) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(tables.dispatch)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(tables.outbox)) == 1


def test_saved_toggle_controls_new_jobs_and_not_old_jobs(workspace_service):
    from app.services.qc_dispatch.control import save_control
    module, service, sessions, tables = workspace_service
    cfg = module.get_settings()
    save_control(enabled=False, expected_revision=0, actor='synthetic', settings=cfg)
    legacy = _create_workspace_job(service)
    save_control(enabled=True, expected_revision=1, actor='synthetic', settings=cfg)
    mq = _create_workspace_job(service)
    save_control(enabled=False, expected_revision=2, actor='synthetic', settings=cfg)
    later = _create_workspace_job(service)
    assert qc_dispatch_mode_from_filters(legacy['filters']) == 'legacy'
    assert qc_dispatch_mode_from_filters(mq['filters']) == 'rabbitmq'
    assert qc_dispatch_mode_from_filters(later['filters']) == 'legacy'
    assert service.get_batch_job(job_id=mq['id'], created_by='synthetic')['filters']['qc_dispatch']['mode'] == 'rabbitmq'
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(tables.outbox)) == 1
        assert session.scalar(sa.select(sa.func.count()).select_from(tables.dispatch)) == 1


def test_mode_changed_after_preflight_cannot_insert_direct_model_mq_job(workspace_service, monkeypatch):
    from app.services.qc_dispatch.dispatcher import QCDispatchEntrypointError
    module, service, sessions, tables = workspace_service
    cfg = module.get_settings()
    cfg.LLM_DISPATCH_MODE = 'direct'
    monkeypatch.setattr(module, 'get_settings', lambda: cfg)
    with pytest.raises(QCDispatchEntrypointError, match='Gateway'):
        _create_workspace_job(service)
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(service._batch_job_table)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(tables.outbox)) == 0


def test_workspace_dispatch_failure_rolls_back_job_insert(workspace_service, monkeypatch):
    _, service, sessions, tables = workspace_service

    def fail_dispatch(*args, **kwargs):
        raise RuntimeError("synthetic outbox failure")

    monkeypatch.setattr(service._qc_dispatch, "add_dispatch", fail_dispatch)
    with pytest.raises(RuntimeError, match="synthetic outbox failure"):
        _create_workspace_job(service)

    with sessions() as session:
        assert session.scalar(
            sa.select(sa.func.count()).select_from(service._batch_job_table)
        ) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(tables.dispatch)) == 0
        assert session.scalar(sa.select(sa.func.count()).select_from(tables.outbox)) == 0


def test_mq_retry_without_failure_scope_preserves_success_and_requires_recovery(
    workspace_service,
):
    _, service, sessions, _ = workspace_service
    job = _create_workspace_job(service)
    preserved_items = [{"rule_id": "LX001", "status": "compliant"}]
    with sessions.begin() as session:
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == job["id"])
            .values(
                status="failed",
                items_json=json.dumps(preserved_items),
                success_count=1,
                error_message="synthetic failure",
            )
        )

    assert service.retry_batch_job(job_id=job["id"], created_by="synthetic") is None
    saved = service.get_batch_job(job_id=job["id"], created_by="synthetic")
    assert saved["status"] == "failed"
    assert [(item["rule_id"], item["status"]) for item in saved["items"]] == [
        ("LX001", "compliant")
    ]
    dispatch = service._qc_dispatch.get_dispatch(job["id"])
    assert dispatch.generation == 1
    assert dispatch.recovery_kind == "manual_scope_required"


def test_parent_retry_only_requeues_failed_mq_child_and_preserves_completed_child(
    workspace_service, monkeypatch,
):
    module, service, sessions, tables = workspace_service
    # 合成历史父任务，仅覆盖原有恢复合同；生产新建入口明确禁止MQ父任务。
    with monkeypatch.context() as historical:
        historical.setattr(module, "assert_new_qc_task_dispatch_ready", lambda **_kwargs: "rabbitmq")
        parent = _create_workspace_job(service, kind="parent")
    completed = _create_workspace_job(service, kind="child", parent_id=parent["id"])
    failed = _create_workspace_job(service, kind="child", parent_id=parent["id"])
    service.update_parent_child_jobs(
        parent_job_id=parent["id"],
        created_by="synthetic",
        child_job_ids=[completed["id"], failed["id"]],
    )
    completed_items = [{"rule_id": "LX001", "status": "compliant"}]
    with sessions.begin() as session:
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == parent["id"])
            .values(status="failed")
        )
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == completed["id"])
            .values(
                status="completed",
                items_json=json.dumps(completed_items),
                success_count=1,
            )
        )
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == failed["id"])
            .values(status="failed")
        )

    retried = service.retry_batch_job(
        job_id=parent["id"], created_by="synthetic", retry_delay_seconds=3
    )
    assert retried is not None
    completed_saved = service.get_batch_job(
        job_id=completed["id"], created_by="synthetic"
    )
    failed_saved = service.get_batch_job(job_id=failed["id"], created_by="synthetic")
    assert completed_saved["status"] == "completed"
    assert [
        (item["rule_id"], item["status"]) for item in completed_saved["items"]
    ] == [("LX001", "compliant")]
    assert service._qc_dispatch.get_dispatch(completed["id"]).generation == 1
    assert failed_saved["status"] == "queued"
    assert service._qc_dispatch.get_dispatch(failed["id"]).generation == 2
    assert service._qc_dispatch.get_dispatch(parent["id"]).generation == 2
    with sessions() as session:
        parent_deliveries = session.scalar(
            sa.select(sa.func.count())
            .select_from(tables.outbox)
            .where(tables.outbox.c.job_id == parent["id"])
        )
        failed_generations = session.execute(
            sa.select(tables.outbox.c.generation)
            .where(tables.outbox.c.job_id == failed["id"])
            .order_by(tables.outbox.c.generation)
        ).scalars().all()
    assert parent_deliveries == 0
    assert failed_generations == [1, 2]


def test_recovery_candidates_exclude_manual_scope_rows_before_limit(repository):
    repo, sessions, jobs, _ = repository
    manual_ids = [_uuid(), _uuid(), _uuid()]
    live_id = _uuid()
    with sessions.begin() as session:
        for job_id in [*manual_ids, live_id]:
            _insert_job(session, jobs, job_id, status="failed")
            repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")
            assert repo.transition_dispatch(
                job_id=job_id,
                generation=1,
                from_statuses=("queued",),
                to_status="failed",
                session=session,
            )
        for job_id in manual_ids:
            assert repo.register_recovery(
                job_id,
                1,
                recovery_kind="manual_scope_required",
                reason_code="manual_scope_required",
                session=session,
            )

    assert [item.job_id for item in repo.list_recovery_candidates(limit=1)] == [live_id]


def test_corrupted_mq_filters_cannot_fall_back_to_legacy_retry(
    workspace_service, monkeypatch
):
    workspace_module, service, sessions, _ = workspace_service
    job = _create_workspace_job(service)
    with sessions.begin() as session:
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == job["id"])
            .values(status="failed", filters_json="{}")
        )

    monkeypatch.setattr(
        workspace_module,
        "get_settings",
        lambda: SimpleNamespace(QC_TASK_DISPATCH_MODE="legacy"),
    )
    with pytest.raises(ValueError, match="禁止回退legacy"):
        service.retry_batch_job(job_id=job["id"], created_by="synthetic")
    assert service._qc_dispatch.get_dispatch(job["id"]).generation == 1


def test_workspace_terminal_updates_keep_dispatch_status_in_same_transaction(
    workspace_service,
):
    _, service, _, _ = workspace_service
    canceled = _create_workspace_job(service)
    assert service.cancel_batch_job(job_id=canceled["id"], created_by="synthetic")
    assert service._qc_dispatch.get_dispatch(canceled["id"]).status == "canceled"

    completed = _create_workspace_job(service)
    attempt = service.mark_batch_job_running(job_id=completed["id"])
    assert isinstance(attempt, str)
    assert service.complete_batch_job(
        job_id=completed["id"],
        summary={
            "execution_status": "completed",
            "total_records": 0,
            "success_count": 0,
            "failed_count": 0,
            "issue_records": 0,
            "compliant_records": 0,
            "total_tokens": 0,
            "total_processing_time": 0.0,
        },
        items=[],
        failed_records=[],
        attempt_filters_json=attempt,
    ) is True
    assert service._qc_dispatch.get_dispatch(completed["id"]).status == "completed"


def test_old_generation_cannot_claim_new_mq_attempt(workspace_service):
    _, service, sessions, _ = workspace_service
    job = _create_workspace_job(service)
    with sessions.begin() as session:
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == job["id"])
            .values(status="failed")
        )
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == job["id"])
            .values(status="queued")
        )
        assert service._qc_dispatch.advance_generation(
            session, job_id=job["id"], expected_generation=1
        ) == 2

    assert service.mark_batch_job_running(
        job_id=job["id"], expected_dispatch_generation=1
    ) is False
    assert service.get_batch_job(
        job_id=job["id"], created_by="synthetic"
    )["status"] == "queued"
    assert service._qc_dispatch.get_dispatch(job["id"]).status == "queued"


def test_legacy_retry_without_m2_tables_never_selects_dispatch(
    workspace_service, monkeypatch
):
    workspace_module, service, sessions, tables = workspace_service
    monkeypatch.setattr(
        workspace_module,
        "get_settings",
        lambda: SimpleNamespace(QC_TASK_DISPATCH_MODE="legacy"),
    )
    job = _create_workspace_job(service)
    assert qc_dispatch_mode_from_filters(job["filters"]) == "legacy"
    with sessions.begin() as session:
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == job["id"])
            .values(status="failed")
        )
    engine = sessions.kw["bind"]
    tables.dispatch.metadata.drop_all(engine)

    with sessions() as session:
        before = dict(session.execute(
            sa.select(service._batch_job_table).where(service._batch_job_table.c.id == job["id"])
        ).mappings().one())
    # 缺少精确失败范围的 legacy 重试必须保留原任务；也不能依赖已不存在的 M2 表。
    with pytest.raises(ValueError, match="new_task_required_preserve_history"):
        service.retry_batch_job(job_id=job["id"], created_by="synthetic")
    with sessions() as session:
        after = dict(session.execute(
            sa.select(service._batch_job_table).where(service._batch_job_table.c.id == job["id"])
        ).mappings().one())
    assert after == before
    assert after["status"] == "failed"


def test_new_generation_clears_old_terminal_code_and_can_reenter_recovery(repository):
    repo, sessions, jobs, _ = repository
    job_id = _uuid()
    with sessions.begin() as session:
        _insert_job(session, jobs, job_id, status="failed")
        repo.add_dispatch(session, job_id=job_id, mode="rabbitmq")
    assert repo.record_terminal_failure(job_id, 1, error_code="worker_failed")

    with sessions.begin() as session:
        session.execute(jobs.update().where(jobs.c.id == job_id).values(status="queued"))
        assert repo.advance_generation(session, job_id=job_id, expected_generation=1) == 2
        assert repo.transition_dispatch(
            job_id=job_id,
            generation=2,
            from_statuses=("queued",),
            to_status="running",
            session=session,
        )
        session.execute(jobs.update().where(jobs.c.id == job_id).values(status="failed"))
        assert repo.transition_dispatch(
            job_id=job_id,
            generation=2,
            from_statuses=("running",),
            to_status="failed",
            session=session,
        )

    dispatch = repo.get_dispatch(job_id)
    assert dispatch.generation == 2
    assert dispatch.last_failure_code is None
    assert [item.job_id for item in repo.list_recovery_candidates()] == [job_id]


def test_business_failure_of_explicit_nonformal_mq_job_is_recovery_visible(
    workspace_service,
):
    _, service, sessions, _ = workspace_service
    job = _create_workspace_job(service)
    corrupted_but_explicit_mq = {
        "rule_set_key": "unsupported_rule_set",
        "qc_dispatch": dispatch_filter_payload("rabbitmq"),
    }
    with sessions.begin() as session:
        session.execute(
            service._batch_job_table.update()
            .where(service._batch_job_table.c.id == job["id"])
            .values(filters_json=json.dumps(corrupted_but_explicit_mq))
        )

    # 模拟业务失败事务已提交、Worker尚未来得及记terminal的崩溃窗口。
    service.fail_batch_job(job_id=job["id"], error_message="unsupported dispatch")

    assert service.get_batch_job(job_id=job["id"], created_by="synthetic")["status"] == "failed"
    dispatch = service._qc_dispatch.get_dispatch(job["id"])
    assert dispatch.status == "failed"
    assert dispatch.last_failure_code is None
    assert [item.job_id for item in service._qc_dispatch.list_recovery_candidates()] == [
        job["id"]
    ]


def test_infra_job_uses_formal_gateway_identity_before_transaction(workspace_service, monkeypatch):
    from tests.scheduler_support import infra_runtime
    _, service, sessions, tables = workspace_service
    infra_runtime.PROBE.create(sessions.kw['bind'], checkfirst=True)
    monkeypatch.setattr(infra_runtime, 'runtime', lambda: (None, service))
    monkeypatch.setattr(infra_runtime, 'SessionLocal', sessions)
    monkeypatch.setenv('LLM_DISPATCH_MODE', 'gateway')
    monkeypatch.setenv('LLM_GATEWAY_URL', 'http://127.0.0.1:9/never-connect')
    monkeypatch.setenv('LLM_GATEWAY_TOKEN', 'synthetic-unreachable-gateway-token')
    monkeypatch.setenv('LLM_GATEWAY_PROFILE', 'alibaba_first_pass')
    job_id, _ = infra_runtime.new_job()
    job = service.get_batch_job(job_id=job_id, created_by='synthetic-infra')
    snapshot = job['filters']['lx0609_task_runtime']
    assert snapshot['schema_version'] == 2
    for role in ('first_pass', 'adjudicator'):
        assert snapshot[role]['dispatch_mode'] == 'gateway'
        assert len(snapshot[role]['gateway_endpoint_sha256']) == 64
    assert 'synthetic-unreachable-gateway-token' not in json.dumps(snapshot)
    with sessions() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(tables.outbox)) == 1


@pytest.mark.parametrize('fault', ['missing', 'direct', 'profile', 'endpoint'])
def test_infra_identity_failure_keeps_transaction_empty(workspace_service, monkeypatch, fault):
    from tests.scheduler_support import infra_runtime
    from app.services.luxian_0609 import rule_decision_settings
    from app.services.qc_dispatch.dispatcher import QCDispatchEntrypointError
    _, service, sessions, tables = workspace_service
    monkeypatch.setattr(infra_runtime, 'runtime', lambda: (None, service))
    monkeypatch.setenv('LLM_DISPATCH_MODE', 'gateway')
    monkeypatch.setenv('LLM_GATEWAY_URL', 'http://127.0.0.1:9/never-connect')
    monkeypatch.setenv('LLM_GATEWAY_TOKEN', 'synthetic-unreachable-gateway-token')
    monkeypatch.setenv('LLM_GATEWAY_PROFILE', 'alibaba_first_pass')
    capture = rule_decision_settings.capture_luxian_0609_task_runtime
    def invalid(service):
        snapshot = capture(service)
        if fault == 'missing':
            snapshot.pop('adjudicator')
        else:
            key, value = {'direct': ('dispatch_mode', 'direct'), 'profile': ('gateway_profile', ''),
                          'endpoint': ('gateway_endpoint_sha256', '')}[fault]
            snapshot['adjudicator'][key] = value
        return snapshot
    monkeypatch.setattr(rule_decision_settings, 'capture_luxian_0609_task_runtime', invalid)
    with pytest.raises(QCDispatchEntrypointError, match='Gateway'):
        infra_runtime.new_job()
    with sessions() as session:
        for table in (service._batch_job_table, tables.dispatch, tables.outbox):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
