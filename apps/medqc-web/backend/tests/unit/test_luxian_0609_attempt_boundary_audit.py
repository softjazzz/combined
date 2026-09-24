"""原始 0609 同 ID 重试的执行尝试隔离回归。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
from fastapi import HTTPException

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.routers import qc_sichuan
from app.core.settings import Settings
from app.services.luxian_0609.rule_decision_settings import (
    LX0609_TASK_SETTINGS_FILTER_KEY,
    capture_luxian_0609_task_settings,
    resolve_mainline_rule_decision_settings,
)
from app.services import custom_qc_workspace_service as workspace_module
from app.services.custom_qc_workspace_service import CustomQCWorkspaceService
from app.services import sichuan_workspace_batch_worker as batch_worker
from app.services.detached_task_runner import submit_detached_task
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
    factory = sessionmaker(bind=engine)
    service._batch_job_table = table
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


def test_same_id_retry_preserves_original_luxian_settings_snapshot(storage):
    service, engine, table = storage
    original = capture_luxian_0609_task_settings(
        resolve_mainline_rule_decision_settings(Settings(_env_file=None, JWT_SECRET="synthetic-retry"))
    )
    with engine.begin() as connection:
        connection.execute(
            table.update().where(table.c.id == "attempt-job").values(
                filters_json=json.dumps({
                    "rule_set_key": "luxian_0609_qc_v1",
                    "rule_ids": ["LX0609-01-01-01"],
                    LX0609_TASK_SETTINGS_FILTER_KEY: original,
                })
            )
        )
    canceled = service.cancel_batch_job(job_id="attempt-job", created_by="tester")
    assert canceled is not None and canceled["status"] == "canceled"
    retried = service.retry_batch_job(job_id="attempt-job", created_by="tester")
    assert retried is not None and retried["status"] == "queued"
    assert retried["filters"][LX0609_TASK_SETTINGS_FILTER_KEY] == original


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
    qc_service.client = SimpleNamespace(max_parallel_records=1)

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
