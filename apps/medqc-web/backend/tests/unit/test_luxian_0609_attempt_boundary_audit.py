"""原始 0609 同 ID 重试的执行尝试隔离回归。"""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timedelta
from fastapi import HTTPException

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.routers import qc_sichuan
from app.core.settings import Settings
from app.services.luxian_0609.rule_decision_settings import (
    LX0609_TASK_SETTINGS_FILTER_KEY,
    LX0609_TASK_RUNTIME_FILTER_KEY,
    capture_luxian_0609_task_settings,
    capture_luxian_0609_task_runtime,
    resolve_mainline_rule_decision_settings,
)
from app.services import custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services.detached_task_runner import submit_detached_task
from app.services.luxian_0609.basic_timeliness_customer_projection import (
    safe_basic_timeliness_customer_display_facts,
)
from app.services.qc_workspace.canonical_result_store import CanonicalResultStore
from tests.unit.test_qc_sichuan_batch_throughput import _ServiceStub, _WorkspaceStub


@pytest.fixture
def storage(monkeypatch):
    engine = sa.create_engine("sqlite://")
    monkeypatch.setattr(workspace_module, "engine", engine)
    monkeypatch.setattr(workspace_module, "_draft_schema", lambda: None)
    monkeypatch.setattr(workspace_module, "_sync_batch_job_parent_columns", lambda **_: None)
    service = CustomQCWorkspaceService()
    metadata = sa.MetaData()
    table = service._batch_job_table.to_metadata(metadata, schema=None)
    metadata.create_all(engine)
    envelope_table = service._record_result_envelope_table.to_metadata(sa.MetaData(), schema=None)
    envelope_table.create(bind=engine)
    factory = sessionmaker(bind=engine)
    service._batch_job_table = table
    service._record_result_envelope_table = envelope_table
    monkeypatch.setattr(workspace_module, "_session", factory)
    with engine.begin() as connection:
        connection.execute(table.insert().values(
            id="attempt-job", draft_id="sichuan-rule-library", created_by="tester",
            status="queued", rule_code="LX0609", rule_name="隔离审计", scope="final",
            total_records=1, created_at=datetime(2026, 9, 24),
            updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_ids": ["LX0609-01-01-01"],
            }),
        ))
    yield service, engine, table
    engine.dispose()


def _stale_failed_completion(service: CustomQCWorkspaceService, attempt: str) -> bool | None:
    return service.complete_batch_job(
        job_id="attempt-job",
        attempt_filters_json=attempt,
        summary={
            "execution_status": "failed", "total_records": 1,
            "completed_rule_count": 0, "failed_rule_count": 1,
        },
        items=[],
        failed_records=[{
            "institute_id": "I", "patient_id": "P", "visit_id": "V",
            "rule_id": "LX0609-01-01-01", "error_phase": "execution",
        }],
    )


def _status(engine, table) -> str:
    with engine.connect() as connection:
        return connection.execute(sa.select(table.c.status)).scalar_one()


def test_restart_scan_selects_only_queued_luxian_leaves(storage):
    service, engine, table = storage
    rows = [
        ("paused-parent", "queued", "parent", "luxian_0609_qc_v1"),
        ("other-ruleset", "queued", "leaf", "luxian_0916_qc_v1"),
        ("already-running", "running", "leaf", "luxian_0609_qc_v1"),
        ("another-leaf", "queued", "leaf", "luxian_0609_qc_v1"),
    ]
    with engine.begin() as connection:
        for job_id, status, job_kind, rule_set_key in rows:
            connection.execute(table.insert().values(
                id=job_id, draft_id="synthetic-draft", created_by="tester",
                status=status, job_kind=job_kind, rule_code="LX0609",
                rule_name="重启扫描测试", scope="final", total_records=1,
                created_at=datetime(2026, 9, 25), updated_at=datetime(2026, 9, 25),
                filters_json=json.dumps({"rule_set_key": rule_set_key}),
            ))
    assert service.list_queued_luxian_0609_batch_job_ids() == (
        "attempt-job", "another-leaf",
    )


def test_stale_leased_attempt_fails_and_cannot_submit_late_result(storage):
    service, engine, table = storage
    attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(attempt, str)
    assert json.loads(attempt)["_lx0609_lease_v1"] == 1

    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                updated_at=datetime.utcnow() - timedelta(hours=1),
                summary_json=json.dumps({
                    "luxian_0609_usage_observation_complete": True,
                    "luxian_0609_usage_unknown_executor_keys": [],
                    "total_tokens": 12,
                }),
            )
        )

    assert service.fail_stale_luxian_0609_running_jobs(
        stale_before=datetime.utcnow() - timedelta(minutes=5),
    ) == ("attempt-job",)
    assert _status(engine, table) == "failed"
    failed = service.get_batch_job_for_processing(job_id="attempt-job")
    assert failed is not None
    assert failed["summary"]["luxian_0609_usage_observation_complete"] is False
    assert failed["summary"]["total_tokens"] == 12
    assert _stale_failed_completion(service, attempt) is False


def test_lease_renewal_prevents_stale_failure_and_legacy_attempt_is_not_reclaimed(storage):
    service, engine, table = storage
    attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(attempt, str)
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                updated_at=datetime.utcnow() - timedelta(hours=1),
            )
        )

    assert service.renew_luxian_0609_batch_job_lease(
        job_id="attempt-job", attempt_filters_json=attempt,
    ) is True
    assert service.fail_stale_luxian_0609_running_jobs(
        stale_before=datetime.utcnow() - timedelta(minutes=5),
    ) == ()
    assert _status(engine, table) == "running"

    # 旧进程没有续约协议，不能仅凭更新时间推断它已死亡。
    legacy_filters = json.loads(attempt)
    legacy_filters.pop("_lx0609_lease_v1")
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                filters_json=json.dumps(legacy_filters),
                updated_at=datetime.utcnow() - timedelta(days=1),
            )
        )
    assert service.fail_stale_luxian_0609_running_jobs(
        stale_before=datetime.utcnow() - timedelta(minutes=5),
    ) == ()
    assert _status(engine, table) == "running"


def test_lease_heartbeat_stops_when_attempt_is_no_longer_current(monkeypatch):
    observed = threading.Event()
    stopped = threading.Event()
    calls = []

    class Workspace:
        def renew_luxian_0609_batch_job_lease(self, *, job_id, attempt_filters_json):
            calls.append((job_id, attempt_filters_json))
            observed.set()
            return False

    monkeypatch.setattr(batch_worker, "LX0609_LEASE_HEARTBEAT_SECONDS", 0.01)
    thread = threading.Thread(
        target=batch_worker._renew_luxian_0609_lease_until_stopped,
        kwargs={
            "workspace": Workspace(), "job_id": "attempt-job",
            "attempt_filters_json": "frozen-attempt", "stopped": stopped,
        },
    )
    thread.start()
    try:
        assert observed.wait(timeout=1)
        thread.join(timeout=1)
        assert not thread.is_alive()
        assert calls == [("attempt-job", "frozen-attempt")]
    finally:
        stopped.set()


def test_expired_child_lease_refreshes_parent_without_publishing_result(storage):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(table.insert().values(
            id="lease-parent", draft_id="sichuan-rule-library", created_by="tester",
            status="running", job_kind="parent", rule_code="LX0609",
            rule_name="父任务", scope="final", total_records=1,
            child_job_ids_json='["attempt-job"]',
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({"rule_set_key": "luxian_0609_qc_v1"}),
        ))
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                job_kind="child", parent_job_id="lease-parent",
            )
        )
    attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(attempt, str)
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                updated_at=datetime.utcnow() - timedelta(hours=1),
            )
        )
    assert service.fail_stale_luxian_0609_running_jobs(
        stale_before=datetime.utcnow() - timedelta(minutes=5),
    ) == ("attempt-job",)
    with engine.connect() as connection:
        rows = connection.execute(sa.select(table.c.id, table.c.status)).all()
    assert dict(rows) == {"attempt-job": "failed", "lease-parent": "failed"}


def test_cancelled_terminal_rejects_late_completion_until_same_job_is_retried(storage):
    service, engine, table = storage
    old_attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(old_attempt, str)
    canceled = service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert canceled is not None and canceled["status"] == "canceled"
    assert _stale_failed_completion(service, old_attempt) is False
    assert _status(engine, table) == "canceled"

    retried = service.retry_batch_job(job_id="attempt-job", created_by="tester")
    assert retried is not None and retried["id"] == "attempt-job"
    assert retried["status"] == "queued"
    new_attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(new_attempt, str) and new_attempt != old_attempt
    assert _stale_failed_completion(service, old_attempt) is False
    assert _status(engine, table) == "running"


def test_cancel_running_luxian_attempt_marks_cost_observation_unknown(storage):
    service, engine, table = storage
    attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(attempt, str)
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                summary_json=json.dumps({
                    "luxian_0609_usage_observation_complete": True,
                    "luxian_0609_usage_unknown_executor_keys": [],
                }),
            )
        )

    canceled = service.cancel_batch_job(job_id="attempt-job", created_by="tester")

    assert canceled is not None and canceled["status"] == "canceled"
    assert canceled["summary"]["luxian_0609_usage_observation_complete"] is False
    assert canceled["summary"]["luxian_0609_usage_unknown_executor_keys"] == []
    assert _stale_failed_completion(service, attempt) is False


def test_unexpected_running_failure_does_not_keep_previous_cost_observation_complete(storage):
    service, engine, table = storage
    attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(attempt, str)
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                summary_json=json.dumps({
                    "luxian_0609_usage_observation_complete": True,
                    "luxian_0609_usage_unknown_executor_keys": [],
                    "total_tokens": 12,
                }),
            )
        )

    service.fail_batch_job(
        job_id="attempt-job", error_message="synthetic outer worker failure",
        attempt_filters_json=attempt,
    )

    failed = service.get_batch_job_for_processing(job_id="attempt-job")
    assert failed is not None and failed["status"] == "failed"
    assert failed["summary"]["luxian_0609_usage_observation_complete"] is False
    assert failed["summary"]["luxian_0609_usage_unknown_executor_keys"] == []
    assert failed["summary"]["total_tokens"] == 12
    safe = workspace_module.project_customer_safe_batch_job(
        failed, hmac_key=workspace_module.customer_safe_projection_key(),
    )
    assert safe["summary"]["luxian_0609_usage_observation_complete"] is False


def test_queued_luxian_failure_does_not_claim_a_model_cost_observation(storage):
    service, _engine, _table = storage
    queued = service.get_batch_job_for_processing(job_id="attempt-job")
    assert queued is not None and queued["status"] == "queued"
    service.fail_batch_job(
        job_id="attempt-job", error_message="synthetic admission failure",
        queued_only=True, expected_queued_filters_json=queued["_claim_filters_json"],
    )
    failed = service.get_batch_job_for_processing(job_id="attempt-job")
    assert failed is not None and failed["status"] == "failed"
    assert "luxian_0609_usage_observation_complete" not in failed["summary"]


def test_nonformal_running_failure_keeps_its_existing_summary(storage):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                filters_json=json.dumps({"rule_set_key": "other_ruleset"}),
                summary_json=json.dumps({"luxian_0609_usage_observation_complete": True}),
            )
        )
    assert service.mark_batch_job_running(job_id="attempt-job") is True
    service.fail_batch_job(job_id="attempt-job", error_message="synthetic other task failure")
    failed = service.get_batch_job_for_processing(job_id="attempt-job")
    assert failed is not None and failed["status"] == "failed"
    assert failed["summary"]["luxian_0609_usage_observation_complete"] is True


def test_same_id_retry_preserves_original_luxian_settings_snapshot(storage):
    service, engine, table = storage
    original = capture_luxian_0609_task_settings(
        resolve_mainline_rule_decision_settings(Settings(_env_file=None, JWT_SECRET="synthetic-retry"))
    )
    accepted_runtime = capture_luxian_0609_task_runtime(_ServiceStub())
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                filters_json=json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_ids": ["LX0609-01-01-01"],
                    LX0609_TASK_SETTINGS_FILTER_KEY: original,
                    LX0609_TASK_RUNTIME_FILTER_KEY: accepted_runtime,
                })
            )
        )
    canceled = service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert canceled is not None and canceled["status"] == "canceled"
    retried = service.retry_batch_job(job_id="attempt-job", created_by="tester")
    assert retried is not None and retried["status"] == "queued"
    assert retried["filters"][LX0609_TASK_SETTINGS_FILTER_KEY] == original
    assert retried["filters"][LX0609_TASK_RUNTIME_FILTER_KEY] == accepted_runtime


def test_running_job_can_be_claimed_by_two_workers(storage):
    service, engine, table = storage
    assert isinstance(service.mark_batch_job_running(job_id="attempt-job"), str)
    assert service.mark_batch_job_running(job_id="attempt-job") is False
    assert _status(engine, table) == "running"


@pytest.mark.asyncio
async def test_public_retry_route_resubmits_same_job_id(storage, monkeypatch):
    service, _, _ = storage
    canceled = service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert canceled is not None and canceled["status"] == "canceled"
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: service)
    submitted: list[tuple[str, str]] = []
    monkeypatch.setattr(
        qc_sichuan, "submit_detached_task",
        lambda name, func, job_id: submitted.append((name, job_id)),
    )
    request = Request({"type": "http", "headers": []})
    await qc_sichuan.retry_workspace_batch_job(
        request, "attempt-job", current_user={"id": "tester"}
    )
    with pytest.raises(HTTPException) as rejected:
        await qc_sichuan.retry_workspace_batch_job(
            request, "attempt-job", current_user={"id": "tester"}
        )
    assert rejected.value.status_code == 409
    assert submitted == [
        ("sichuan_workspace_batch_job_retry", "attempt-job"),
    ]


def test_detached_runner_has_no_job_id_deduplication():
    async def work(job_id: str) -> str:
        await asyncio.sleep(0)
        return job_id

    first = submit_detached_task("audit", work, "same-job")
    second = submit_detached_task("audit", work, "same-job")
    assert first is not second
    assert first.result(timeout=3) == second.result(timeout=3) == "same-job"


def test_stale_progress_failure_retry_and_poll_do_not_take_new_attempt(storage, monkeypatch):
    service, engine, table = storage
    frozen = datetime(2026, 9, 24, 12, 0, 0)
    monkeypatch.setattr(workspace_module, "_now_utc", lambda: frozen)
    old = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(old, str)
    service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert service.retry_batch_job(job_id="attempt-job", created_by="tester") is not None
    new = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(new, str) and new != old
    with engine.connect() as connection:
        started_at = connection.execute(sa.select(table.c.started_at)).scalar_one()
    assert started_at == frozen
    assert service.is_batch_job_canceled_or_missing(job_id="attempt-job", attempt_filters_json=old)
    assert not service.is_batch_job_canceled_or_missing(job_id="attempt-job", attempt_filters_json=new)
    assert service.update_batch_job_progress(
        job_id="attempt-job", attempt_filters_json=old, step_key="run", rule_index=1,
        rule_count=1, processed_records=1, total_records=1,
        summary_patch={"stale": True},
    ) is None
    service.fail_batch_job(job_id="attempt-job", error_message="stale", attempt_filters_json=old)
    assert service.retry_batch_job(
        job_id="attempt-job", created_by="tester", automatic=True,
        expected_attempt_filters_json=old,
    ) is None
    assert _status(engine, table) == "running"
    with engine.connect() as connection:
        row = connection.execute(sa.select(table.c.summary_json, table.c.error_message)).one()
    assert "stale" not in (row.summary_json or "")
    assert row.error_message is None


@pytest.mark.asyncio
async def test_old_worker_exits_after_provider_wait_when_new_attempt_started(storage, monkeypatch):
    service, engine, _ = storage
    entered = asyncio.Event()
    release = asyncio.Event()

    async def provider():
        entered.set()
        await release.wait()
        return object()

    class Activation:
        def enforce(self):
            return None

    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: Activation())
    old_worker = asyncio.create_task(batch_worker.run_sichuan_workspace_batch_job(
        "attempt-job", workspace=service, qc_service_provider=provider,
    ))
    await asyncio.wait_for(entered.wait(), timeout=3)
    service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert service.retry_batch_job(job_id="attempt-job", created_by="tester") is not None
    assert isinstance(service.mark_batch_job_running(job_id="attempt-job"), str)
    release.set()
    await asyncio.wait_for(old_worker, timeout=3)
    assert _status(engine, service._batch_job_table) == "running"


def test_current_attempt_can_complete_and_retry_once(storage):
    service, engine, _ = storage
    attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(attempt, str)
    assert service.update_batch_job_progress(
        job_id="attempt-job", attempt_filters_json=attempt, step_key="run", rule_index=0,
        rule_count=1, processed_records=0, total_records=1,
    ) is not None
    assert service.complete_batch_job(
        job_id="attempt-job", attempt_filters_json=attempt,
        summary={"execution_status": "completed", "total_records": 1},
        items=[], failed_records=[], persist_record_envelopes=False,
    ) is True
    assert _status(engine, service._batch_job_table) == "completed"
    assert service.retry_batch_job(
        job_id="attempt-job", created_by="tester", automatic=True,
        expected_attempt_filters_json=attempt,
    ) is not None
    assert service.retry_batch_job(
        job_id="attempt-job", created_by="tester", automatic=True,
        expected_attempt_filters_json=attempt,
    ) is None
    assert _status(engine, service._batch_job_table) == "queued"


def test_missing_attempt_cannot_write_claimed_formal_job_and_token_is_private(storage):
    service, engine, table = storage
    attempt = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(attempt, str)
    assert workspace_module.LX0609_ATTEMPT_FILTER_KEY not in (
        service.get_batch_job_for_processing(job_id="attempt-job") or {}
    ).get("filters", {})
    assert service.update_batch_job_progress(
        job_id="attempt-job", step_key="run", rule_index=0,
        rule_count=1, processed_records=1, total_records=1,
    ) is None
    service.fail_batch_job(job_id="attempt-job", error_message="without-token")
    assert service.complete_batch_job(
        job_id="attempt-job", summary={"execution_status": "completed", "total_records": 1},
        items=[], failed_records=[], persist_record_envelopes=False,
    ) is None
    assert _status(engine, table) == "running"
    with engine.connect() as connection:
        assert connection.execute(sa.select(table.c.error_message)).scalar_one() is None


def test_preclaim_failure_cannot_fail_other_workers_running_attempt(storage):
    service, engine, table = storage
    assert isinstance(service.mark_batch_job_running(job_id="attempt-job"), str)
    service.fail_batch_job(job_id="attempt-job", error_message="activation", queued_only=True)
    assert _status(engine, table) == "running"
    service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert service.retry_batch_job(job_id="attempt-job", created_by="tester") is not None
    queued = service.get_batch_job_for_processing(job_id="attempt-job")
    assert queued is not None
    service.fail_batch_job(
        job_id="attempt-job", error_message="activation", queued_only=True,
        expected_queued_filters_json=queued["_claim_filters_json"],
    )
    assert _status(engine, table) == "failed"


def test_preclaim_failure_uses_original_queued_snapshot(storage):
    service, engine, table = storage
    first = service.get_batch_job_for_processing(job_id="attempt-job")
    assert first is not None
    original = first["_claim_filters_json"]
    service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert service.retry_batch_job(job_id="attempt-job", created_by="tester") is not None
    service.fail_batch_job(
        job_id="attempt-job", error_message="late-activation", queued_only=True,
        expected_queued_filters_json=original,
    )
    assert _status(engine, table) == "queued"


def test_parent_retry_rotates_each_child_queued_snapshot(storage):
    service, engine, table = storage
    first_filters = {
        "rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-01-01-01"],
        "family_key": "admission", "department": "内科",
    }
    second_filters = {
        "rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-06-01-01"],
        "family_key": "ct", "department": "外科",
    }
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            filters_json=json.dumps(first_filters),
        ))
    original = service.get_batch_job_for_processing(job_id="attempt-job")
    assert original is not None
    old_first_filters = original["_claim_filters_json"]
    old_second_filters = json.dumps(second_filters)
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            status="canceled", parent_job_id="parent-job",
        ))
        connection.execute(table.insert().values(
            id="second-child", draft_id="sichuan-rule-library", created_by="tester",
            status="canceled", parent_job_id="parent-job", family_key="ct",
            rule_code="LX0609", rule_name="影像子任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=old_second_filters,
        ))
        connection.execute(table.insert().values(
            id="parent-job", draft_id="sichuan-rule-library", created_by="tester",
            status="canceled", job_kind="parent",
            child_job_ids_json='["attempt-job", "second-child"]',
            rule_code="LX0609", rule_name="父任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({
                "rule_set_key": "luxian_0609_qc_v1",
                "rule_ids": ["LX0609-01-01-01", "LX0609-06-01-01"],
            }),
        ))
    assert service.retry_batch_job(job_id="parent-job", created_by="tester") is not None
    first = service.get_batch_job_for_processing(job_id="attempt-job")
    second = service.get_batch_job_for_processing(job_id="second-child")
    assert first is not None and second is not None
    assert first["status"] == second["status"] == "queued"
    new_first = json.loads(first["_claim_filters_json"])
    new_second = json.loads(second["_claim_filters_json"])
    assert new_first.pop(workspace_module.LX0609_ATTEMPT_FILTER_KEY) != new_second.pop(
        workspace_module.LX0609_ATTEMPT_FILTER_KEY
    )
    assert new_first == first_filters
    assert new_second == second_filters
    service.fail_batch_job(
        job_id="attempt-job", error_message="old-activation", queued_only=True,
        expected_queued_filters_json=old_first_filters,
    )
    service.fail_batch_job(
        job_id="second-child", error_message="old-activation", queued_only=True,
        expected_queued_filters_json=old_second_filters,
    )
    with engine.connect() as connection:
        assert connection.execute(sa.select(table.c.status).where(
            table.c.id.in_(["attempt-job", "second-child"])
        ).order_by(table.c.id)).scalars().all() == ["queued", "queued"]


def test_parent_retry_rejects_running_child_without_partial_reset(storage):
    service, engine, table = storage
    first_original = service.get_batch_job_for_processing(job_id="attempt-job")
    assert first_original is not None
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            status="canceled", parent_job_id="parent-job",
        ))
        connection.execute(table.insert().values(
            id="running-child", draft_id="sichuan-rule-library", created_by="tester",
            status="running", parent_job_id="parent-job", family_key="ct",
            rule_code="LX0609", rule_name="执行中子任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-06-01-01"]}),
        ))
        connection.execute(table.insert().values(
            id="parent-job", draft_id="sichuan-rule-library", created_by="tester",
            status="canceled", job_kind="parent",
            child_job_ids_json='["attempt-job", "running-child"]',
            rule_code="LX0609", rule_name="父任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-01-01-01"]}),
        ))
    assert service.retry_batch_job(job_id="parent-job", created_by="tester") is None
    with engine.connect() as connection:
        rows = connection.execute(sa.select(
            table.c.id, table.c.status, table.c.filters_json
        ).where(table.c.id.in_(["parent-job", "attempt-job", "running-child"]))).mappings().all()
    by_id = {row["id"]: row for row in rows}
    assert by_id["parent-job"]["status"] == "canceled"
    assert by_id["attempt-job"]["status"] == "canceled"
    assert by_id["attempt-job"]["filters_json"] == first_original["_claim_filters_json"]
    assert by_id["running-child"]["status"] == "running"
    assert json.loads(by_id["running-child"]["filters_json"])["rule_ids"] == ["LX0609-06-01-01"]


def test_parent_cancel_marks_running_child_usage_observation_incomplete(storage):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            status="running", parent_job_id="parent-job",
            summary_json=json.dumps({
                "luxian_0609_usage_observation_complete": True,
                "total_tokens": 12,
            }),
        ))
        connection.execute(table.insert().values(
            id="parent-job", draft_id="sichuan-rule-library", created_by="tester",
            status="running", job_kind="parent", child_job_ids_json='["attempt-job"]',
            rule_code="LX0609", rule_name="父任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({"rule_set_key": "luxian_0609_qc_v1"}),
        ))

    service.cancel_batch_job(job_id="parent-job", created_by="tester")

    with engine.connect() as connection:
        row = connection.execute(sa.select(table.c.status, table.c.summary_json).where(
            table.c.id == "attempt-job"
        )).one()
    assert row.status == "canceled"
    child_summary = json.loads(row.summary_json)
    assert child_summary["luxian_0609_usage_observation_complete"] is False
    assert child_summary["total_tokens"] == 12


@pytest.mark.parametrize("retry_target", ["parent-job", "attempt-job"])
@pytest.mark.parametrize("claim_new_parent", [False, True])
def test_parent_refresh_rejects_stale_aggregate_after_retry(
    storage, monkeypatch, retry_target, claim_new_parent,
):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            status="completed", parent_job_id="parent-job",
            summary_json=json.dumps({"progress": {"step_key": "completed"}}),
        ))
        connection.execute(table.insert().values(
            id="parent-job", draft_id="sichuan-rule-library", created_by="tester",
            status="completed", job_kind="parent", child_job_ids_json='["attempt-job"]',
            rule_code="LX0609", rule_name="父任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-01-01-01"]}),
            summary_json=json.dumps({"progress": {"step_key": "completed"}}),
        ))
    original = service._aggregate_parent_job
    interleaved = False
    writes = []

    def aggregate_then_retry(session, parent_job, *, include_items=True):
        nonlocal interleaved
        aggregate = original(session, parent_job, include_items=include_items)
        if not interleaved:
            interleaved = True
            assert service.retry_batch_job(job_id=retry_target, created_by="tester") is not None
            if claim_new_parent:
                assert isinstance(service.mark_batch_job_running(job_id="parent-job"), str)
        return aggregate

    monkeypatch.setattr(service, "_aggregate_parent_job", aggregate_then_retry)
    monkeypatch.setattr(service, "_write_record_result_envelopes", lambda *args, **kwargs: writes.append(kwargs))
    service.refresh_parent_batch_job(parent_job_id="parent-job")
    with engine.connect() as connection:
        rows = connection.execute(sa.select(table.c.id, table.c.status).where(
            table.c.id.in_(["parent-job", "attempt-job"])
        )).all()
    assert {row.id: row.status for row in rows} == {
        "parent-job": "running" if claim_new_parent else "queued", "attempt-job": "queued",
    }
    assert writes == []


def test_two_parent_refreshes_cannot_apply_old_child_snapshot_last(storage, monkeypatch):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(parent_job_id="parent-job"))
        connection.execute(table.insert().values(
            id="parent-job", draft_id="sichuan-rule-library", created_by="tester",
            status="queued", job_kind="parent", child_job_ids_json='["attempt-job"]',
            rule_code="LX0609", rule_name="父任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-01-01-01"]}),
            summary_json=json.dumps({"progress": {"step_key": "queued"}}),
        ))
    original = service._aggregate_parent_job
    interleaved = False

    def aggregate_then_newer_refresh(session, parent_job, *, include_items=True):
        nonlocal interleaved
        aggregate = original(session, parent_job, include_items=include_items)
        if not interleaved:
            interleaved = True
            assert isinstance(service.mark_batch_job_running(job_id="attempt-job"), str)
            service.refresh_parent_batch_job(parent_job_id="parent-job")
        return aggregate

    monkeypatch.setattr(service, "_aggregate_parent_job", aggregate_then_newer_refresh)
    service.refresh_parent_batch_job(parent_job_id="parent-job")
    with engine.connect() as connection:
        row = connection.execute(sa.select(table.c.status, table.c.summary_json).where(
            table.c.id == "parent-job"
        )).one()
    assert row.status == "running"
    assert json.loads(row.summary_json)["progress"]["step_key"] == "running"


@pytest.mark.parametrize("parent_status,expected_writes", [("queued", 1), ("canceled", 0)])
def test_parent_refresh_keeps_normal_completion_and_cancellation(storage, monkeypatch, parent_status, expected_writes):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            status="completed", parent_job_id="parent-job",
        ))
        connection.execute(table.insert().values(
            id="parent-job", draft_id="sichuan-rule-library", created_by="tester",
            status=parent_status, job_kind="parent", child_job_ids_json='["attempt-job"]',
            rule_code="LX0609", rule_name="父任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({"rule_set_key": "luxian_0609_qc_v1", "rule_ids": ["LX0609-01-01-01"]}),
        ))
    writes = []
    monkeypatch.setattr(service, "_write_record_result_envelopes", lambda *args, **kwargs: writes.append(kwargs))
    service.refresh_parent_batch_job(parent_job_id="parent-job")
    with engine.connect() as connection:
        status = connection.execute(sa.select(table.c.status).where(table.c.id == "parent-job")).scalar_one()
    assert status == ("canceled" if parent_status == "canceled" else "completed")
    assert len(writes) == expected_writes


def test_completed_parent_publishes_one_envelope_after_child_validation(storage):
    service, engine, table = storage
    envelope_table = service._record_result_envelope_table
    facts = safe_basic_timeliness_customer_display_facts(
        rule_id="LX0609-01-01-01",
        raw={
            "failure_kind": "timeliness_requirement_satisfied",
            "target_document": "admission_record", "source_label": "入院记录",
            "timeliness_state": "within", "threshold_hours": 24, "elapsed_hours": 1.0,
        },
    )
    assert facts is not None
    item = {
        "record_id": "V", "visit_id": "V", "institute_id": "I", "patient_id": "P",
        "schema_version": "lx0609-customer-result-v2", "rule_id": "LX0609-01-01-01",
        "status": "compliant", "result_status": "compliant",
        "display_status": "compliant", "is_compliant": True,
        "reason_code": "requirement_satisfied", "conclusion": "已核对",
        "customer_display_facts": facts,
    }
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            status="running", parent_job_id="parent-job",
        ))
        connection.execute(table.insert().values(
            id="parent-job", draft_id="sichuan-rule-library", created_by="tester",
            status="queued", job_kind="parent", child_job_ids_json='["attempt-job"]',
            rule_code="LX0609", rule_name="父任务", scope="final", total_records=1,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=json.dumps({
                "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
                "rule_ids": ["LX0609-01-01-01"],
                "record_refs": [{"institute_id": "I", "patient_id": "P", "visit_id": "V"}],
            }),
        ))

    service.complete_batch_job(
        job_id="attempt-job",
        summary={"total_records": 1, "success_count": 1},
        items=[item], failed_records=[],
    )
    service.refresh_parent_batch_job(parent_job_id="parent-job")

    with engine.connect() as connection:
        rows = connection.execute(sa.select(envelope_table).where(
            envelope_table.c.root_job_id == "parent-job"
        )).mappings().all()
        parent_status = connection.execute(sa.select(table.c.status).where(
            table.c.id == "parent-job"
        )).scalar_one()
        envelope = CanonicalResultStore(envelope_table).load_selected(
            connection, root_job_id="parent-job", institute_id="I", patient_id="P",
            visit_id="V", rule_set_key="luxian_0609_qc_v1", rule_set_version="2026-06-09",
        )
    assert parent_status == "completed"
    assert len(rows) == 1
    assert rows[0]["job_id"] == "parent-job"
    assert [published["rule_id"] for published in envelope["items"]] == ["LX0609-01-01-01"]


@pytest.mark.parametrize("second_child_outcome", ["completed", "partial_failed", "failed"])
def test_parent_exports_only_complete_cases_across_children(storage, second_child_outcome):
    service, engine, table = storage
    record_a = {"institute_id": "I", "patient_id": "P-A", "visit_id": "V-A"}
    record_b = {"institute_id": "I", "patient_id": "P-B", "visit_id": "V-B"}
    first_rule = "LX0609-01-01-01"
    second_rule = "LX0609-01-02-01"

    def filters(rule_ids):
        return json.dumps({
            "rule_set_key": "luxian_0609_qc_v1",
            "rule_set_version": "2026-06-09",
            "rule_ids": rule_ids,
            "record_refs": [record_a, record_b],
        })

    def item(record, rule_id, target_document, source_label, threshold):
        facts = safe_basic_timeliness_customer_display_facts(
            rule_id=rule_id,
            raw={
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": target_document,
                "source_label": source_label,
                "timeliness_state": "within",
                "threshold_hours": threshold,
                "elapsed_hours": 1.0,
            },
        )
        assert facts is not None
        return {
            **record,
            "record_id": record["visit_id"],
            "schema_version": "lx0609-customer-result-v2",
            "rule_id": rule_id,
            "status": "compliant",
            "result_status": "compliant",
            "display_status": "compliant",
            "is_compliant": True,
            "reason_code": "requirement_satisfied",
            "conclusion": "已核对",
            "customer_display_facts": facts,
        }

    first_items = [item(record, first_rule, "admission_record", "入院记录", 24) for record in (record_a, record_b)]
    second_items = [item(record_b, second_rule, "first_course_record", "首次病程记录", 8)]
    if second_child_outcome == "completed":
        second_items.insert(0, item(record_a, second_rule, "first_course_record", "首次病程记录", 8))
    failed_records = [] if second_child_outcome == "completed" else [{
        **record, "rule_id": second_rule,
        "reason_code": "model_invalid_output", "error_phase": "result_status",
    } for record in ([record_a] if second_child_outcome == "partial_failed" else [record_a, record_b])]
    if second_child_outcome == "failed":
        second_items.clear()
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            status="running", parent_job_id="parent-job", total_records=2,
            filters_json=filters([first_rule]),
        ))
        connection.execute(table.insert().values(
            id="second-child", draft_id="sichuan-rule-library", created_by="tester",
            status="running", job_kind="child", parent_job_id="parent-job",
            rule_code="LX0609", rule_name="第二子任务", scope="final", total_records=2,
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=filters([second_rule]),
        ))
        connection.execute(table.insert().values(
            id="parent-job", draft_id="sichuan-rule-library", created_by="tester",
            status="running", job_kind="parent",
            child_job_ids_json='["attempt-job", "second-child"]',
            rule_code="LX0609", rule_name="父任务", scope="final", total_records=2,
            record_ids_json=json.dumps(["V-A", "V-B"]),
            created_at=datetime(2026, 9, 24), updated_at=datetime(2026, 9, 24),
            filters_json=filters([first_rule, second_rule]),
        ))

    service.complete_batch_job(
        job_id="attempt-job",
        summary={"total_records": 2, "success_count": 2, "completed_rule_count": 2},
        items=first_items, failed_records=[],
    )
    service.complete_batch_job(
        job_id="second-child",
        summary={
            "total_records": 2,
            "success_count": len(second_items),
            "failed_count": len(failed_records),
            "execution_status": second_child_outcome,
            "completed_rule_count": len(second_items),
            "failed_rule_count": len(failed_records),
        },
        items=second_items,
        failed_records=failed_records,
    )
    service.refresh_parent_batch_job(parent_job_id="parent-job")
    service.refresh_parent_batch_job(parent_job_id="parent-job")
    parent = service.get_batch_job(job_id="parent-job", created_by="tester")
    expected_parent_status = "completed" if second_child_outcome == "completed" else "failed"
    assert parent is not None and parent["status"] == expected_parent_status
    assert parent["summary"]["execution_status"] == (
        "completed" if second_child_outcome == "completed" else "partial_failed"
    )
    exported_items = service._load_batch_job_export_items(job=parent)
    expected_success_count = len(second_items)
    assert parent["success_count"] == expected_success_count
    hydrated = qc_sichuan._hydrate_luxian_canonical_batch_job_or_409(
        workspace=service, job=parent,
    )
    safe_job = workspace_module.project_customer_safe_batch_job(
        hydrated, hmac_key="synthetic-parent-test-key",
    )
    assert safe_job["summary"]["success_count"] == expected_success_count
    assert len(safe_job["items"]) == len(exported_items)
    listed = service.list_batch_jobs(created_by="tester", status=expected_parent_status)
    listed_parent = next(job for job in listed.items if job["id"] == "parent-job")
    assert listed_parent["success_count"] == expected_success_count
    assert {row["rule_id"] for row in exported_items} == (
        {first_rule, second_rule} if expected_success_count else set()
    )
    assert len({row["record_ref"] for row in exported_items}) == expected_success_count
    for record, should_deliver in (
        (record_a, second_child_outcome == "completed"),
        (record_b, second_child_outcome != "failed"),
    ):
        latest = service.build_latest_single_record_result_dto(
            **record, expected_rule_ids=[first_rule, second_rule],
        )
        if should_deliver:
            assert latest["state"] == "ready"
            assert latest["is_complete"] is True
            assert {item["rule_id"] for item in latest["items"]} == {first_rule, second_rule}
            assert latest["job_id"] == "parent-job"
            exported_by_rule = {
                item["rule_id"]: item
                for item in exported_items
                if item["record_ref"] == latest["record_ref"]
            }
            for latest_item in latest["items"]:
                exported = exported_by_rule[latest_item["rule_id"]]
                for field in (
                    "status", "reason_code", "conclusion", "suggestion",
                    "customer_display_facts", "evidence",
                ):
                    assert latest_item.get(field) == exported.get(field)
        else:
            assert latest["state"] != "ready"
            assert latest["items"] == []
    with engine.connect() as connection:
        envelopes = connection.execute(sa.select(service._record_result_envelope_table).where(
            service._record_result_envelope_table.c.root_job_id == "parent-job"
        )).mappings().all()
    assert [(row["patient_id"], row["job_id"]) for row in envelopes] == (
        [("P-A", "parent-job"), ("P-B", "parent-job")]
        if second_child_outcome == "completed"
        else [("P-B", "parent-job")]
        if second_child_outcome == "partial_failed"
        else []
    )


def test_nonformal_task_keeps_existing_claim_and_retry_semantics(storage):
    service, engine, table = storage
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            filters_json=json.dumps({"rule_set_key": "other_set", "rule_ids": ["SC-001"]}),
        ))
    assert service.mark_batch_job_running(job_id="attempt-job") is True
    assert service.mark_batch_job_running(job_id="attempt-job") is True
    assert service.retry_batch_job(job_id="attempt-job", created_by="tester") is not None
    assert _status(engine, table) == "queued"


@pytest.mark.asyncio
async def test_old_worker_result_after_qc_await_cannot_publish_to_new_attempt(storage, monkeypatch):
    service, engine, table = storage
    workspace = _WorkspaceStub()
    workspace.job["id"] = "attempt-job"
    workspace.job["record_ids"] = ["visit-001"]
    # 仅隔离 Worker 写入边界：模型业务输入用简单桩，真实领取与持久化仍为 LX0609 行。
    workspace.mark_batch_job_running = service.mark_batch_job_running
    workspace.is_batch_job_canceled_or_missing = service.is_batch_job_canceled_or_missing
    workspace.update_batch_job_progress = service.update_batch_job_progress
    workspace.complete_batch_job = service.complete_batch_job
    workspace.fail_batch_job = service.fail_batch_job
    entered = asyncio.Event()
    release = asyncio.Event()
    qc_service = _ServiceStub()
    original_evaluate = qc_service.evaluate_document

    async def evaluate_document(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original_evaluate(*args, **kwargs)

    qc_service.evaluate_document = evaluate_document

    class Activation:
        def enforce(self):
            return None

    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: Activation())

    async def provider():
        return qc_service

    old_worker = asyncio.create_task(batch_worker.run_sichuan_workspace_batch_job(
        "attempt-job", workspace=workspace, qc_service_provider=provider,
    ))
    await asyncio.wait_for(entered.wait(), timeout=3)
    service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert service.retry_batch_job(job_id="attempt-job", created_by="tester") is not None
    assert isinstance(service.mark_batch_job_running(job_id="attempt-job"), str)
    release.set()
    await asyncio.wait_for(old_worker, timeout=3)
    assert _status(engine, table) == "running"
    with engine.connect() as connection:
        assert connection.execute(sa.select(table.c.items_json)).scalar_one() is None


def test_only_current_attempt_commits_real_canonical_envelope(storage):
    service, engine, table = storage
    metadata = sa.MetaData()
    envelopes = service._record_result_envelope_table.to_metadata(metadata, schema=None)
    metadata.create_all(engine)
    service._record_result_envelope_table = envelopes
    old = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(old, str)
    service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert service.retry_batch_job(job_id="attempt-job", created_by="tester") is not None
    new = service.mark_batch_job_running(job_id="attempt-job")
    assert isinstance(new, str)
    payload = dict(
        job_id="attempt-job",
        summary={"execution_status": "completed", "total_records": 1},
        items=[{
            "institute_id": "inst-1", "patient_id": "patient-1", "visit_id": "visit-1",
            "rule_id": "LX0609-01-01-01", "status": "compliant",
            "result_status": "compliant", "display_status": "compliant",
            "is_compliant": True, "reason_code": "requirement_within_threshold",
            "customer_display_facts": {
                "failure_kind": "timeliness_requirement_satisfied",
                "target_document": "admission_record", "source_label": "入院记录",
                "timeliness_state": "within", "threshold_hours": 24,
                "anchor_time": "2026-09-20 08:00:00",
                "observed_time": "2026-09-20 09:00:00",
                "elapsed_hours": 1.0, "remaining_hours": 23.0,
            },
        }], failed_records=[],
    )
    assert service.complete_batch_job(**payload, attempt_filters_json=old) is False
    with engine.connect() as connection:
        assert connection.execute(sa.select(sa.func.count()).select_from(envelopes)).scalar_one() == 0
    assert service.complete_batch_job(**payload, attempt_filters_json=new) is True
    assert _status(engine, table) == "completed"
    with engine.connect() as connection:
        assert connection.execute(sa.select(sa.func.count()).select_from(envelopes)).scalar_one() == 1
    session = workspace_module._session()
    try:
        loaded = service._load_record_result_envelope_items(
            session, root_job_id="attempt-job", institute_id="inst-1",
            patient_id="patient-1", visit_id="visit-1",
            rule_set_key="luxian_0609_qc_v1", rule_set_version=workspace_module.RULE_SET_VERSION,
        )
    finally:
        session.close()
    assert loaded["items"][0]["rule_id"] == "LX0609-01-01-01"
    assert loaded["items"][0]["status"] == "compliant"
    assert loaded["items"][0]["reason_code"] == "requirement_within_threshold"
    assert loaded["items"][0]["customer_display_facts"] == payload["items"][0]["customer_display_facts"]


@pytest.mark.asyncio
async def test_formal_0609_worker_result_after_bundle_await_cannot_publish(storage, monkeypatch):
    service, engine, table = storage
    workspace = _WorkspaceStub()
    workspace.job["id"] = "attempt-job"
    workspace.job["record_ids"] = ["visit-001"]
    rule_id = "LX0609-01-01-01"
    workspace.job["filters"] = {
        "rule_ids": [rule_id], "selected_rule_ids": [rule_id],
        "scoped_customer_rule_ids": [rule_id],
        "record_rule_map": {"visit-001": [rule_id]},
        "rule_set_key": "luxian_0609_qc_v1", "rule_set_version": "2026-06-09",
        "validation_mode": "programmatic",
    }
    workspace.mark_batch_job_running = service.mark_batch_job_running
    workspace.is_batch_job_canceled_or_missing = service.is_batch_job_canceled_or_missing
    workspace.update_batch_job_progress = service.update_batch_job_progress
    workspace.complete_batch_job = service.complete_batch_job
    workspace.fail_batch_job = service.fail_batch_job
    entered = asyncio.Event()
    release = asyncio.Event()
    qc_service = _ServiceStub()
    qc_service.client.max_parallel_records = 1

    async def evaluate_running_final_bundle_input(**_kwargs):
        entered.set()
        await release.wait()
        return {"evaluation_results": [{
            "rule_id": rule_id, "status": "data_gap", "reason_code": "authoritative_time_missing",
            "is_compliant": False, "metadata": {},
        }]}

    qc_service.evaluate_running_final_bundle_input = evaluate_running_final_bundle_input

    class Activation:
        def enforce(self):
            return None

    monkeypatch.setattr(batch_worker, "get_product_activation_service", lambda: Activation())
    monkeypatch.setattr(batch_worker, "get_settings", lambda: Settings(
        _env_file=None, JWT_SECRET="attempt-test",
        LUXIAN_0609_CUSTOMER_AGGREGATION_ENABLED=True,
        LUXIAN_0609_MAINLINE_RULE_DECISION_ENABLED=True,
        LUXIAN_0609_UNIFIED_ENGINE_ENABLED=True,
        LUXIAN_0609_NATIVE_BASIC_TIMELINESS_ENABLED=True,
        LUXIAN_0609_TRIGGER_GATE_ENABLED=False,
    ))
    monkeypatch.setattr(batch_worker, "load_running_final_bundle", lambda **kwargs: {
        "scene": "final", "visit_id": kwargs.get("visit_id", "visit-001"),
        "institute_id": "HOSP-001", "patient_id": "PAT-synthetic", "medical_text": "合成资料",
        "structured_context": {}, "document_hits": {}, "text_available": True,
    })
    monkeypatch.setattr(batch_worker, "build_programmatic_evidence_payload", lambda **_kwargs: {
        "primary_document_text": "合成资料", "document_hits": {}, "text_available": True,
    })

    async def provider():
        return qc_service

    # 正式接纳配置随任务持久化；否则新门禁会在进入等待点前拒绝旧夹具。
    workspace.job["filters"][LX0609_TASK_SETTINGS_FILTER_KEY] = capture_luxian_0609_task_settings(
        resolve_mainline_rule_decision_settings(batch_worker.get_settings())
    )
    workspace.job["filters"][LX0609_TASK_RUNTIME_FILTER_KEY] = capture_luxian_0609_task_runtime(qc_service)
    with engine.begin() as connection:
        connection.execute(table.update().where(table.c.id == "attempt-job").values(
            filters_json=json.dumps(workspace.job["filters"]),
        ))

    old_worker = asyncio.create_task(batch_worker.run_sichuan_workspace_batch_job(
        "attempt-job", workspace=workspace, qc_service_provider=provider,
    ))
    await asyncio.wait_for(entered.wait(), timeout=5)
    service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert service.retry_batch_job(job_id="attempt-job", created_by="tester") is not None
    assert isinstance(service.mark_batch_job_running(job_id="attempt-job"), str)
    release.set()
    await asyncio.wait_for(old_worker, timeout=5)
    assert _status(engine, table) == "running"
    with engine.connect() as connection:
        assert connection.execute(sa.select(table.c.items_json)).scalar_one() is None
