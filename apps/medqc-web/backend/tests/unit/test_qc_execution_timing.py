import asyncio
import json
import logging
import threading
from concurrent.futures import Future

import pytest

from app.core import execution_timing as timing
from app.core import http as http_module


def test_nested_stages_are_measured_separately_and_projection_is_safe(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(timing, "perf_counter", lambda: clock[0])
    with timing.timing_scope() as collector:
        with timing.measure_stage("record_execution"):
            clock[0] = 1
            with timing.timing_labels(family="extended_document", unit="documents"):
                with timing.measure_stage("extended_group"):
                    clock[0] = 4
            clock[0] = 5
        result = collector.snapshot()
    assert result["wall_clock_seconds"] == 5
    assert result["stages"]["record_execution"]["total_seconds"] == 5
    assert result["stages"]["extended_group"]["total_seconds"] == 3
    assert result["families"]["extended_document"]["extended_group"]["count"] == 1
    assert result["units"]["documents"]["extended_group"]["max_seconds"] == 3
    assert result["complete"] is False
    result["patient_id"] = "never-export"
    result["stages"]["raw_prompt"] = {"text": "never-export"}
    result["families"]["unsafe patient label"] = {"raw": 1}
    safe = timing.project_stage_timing(result)
    assert "never-export" not in json.dumps(safe)
    assert "unsafe patient label" not in safe["families"]
    assert timing.current_timing_snapshot() is None


def test_attempt_wall_clock_does_not_include_recursive_retry_wait(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(timing, "perf_counter", lambda: clock[0])
    with timing.timing_scope() as first:
        clock[0] = 10
        timing.finish_current_timing()
        clock[0] = 30
        with timing.timing_scope() as retry:
            clock[0] = 35
        assert retry.snapshot()["wall_clock_seconds"] == 5
    assert first.snapshot(complete=True)["wall_clock_seconds"] == 10


def test_pending_blocking_http_does_not_claim_complete_measurement():
    future = Future()
    with timing.timing_scope() as collector:
        timing.track_http_future(future)
        snapshot = collector.snapshot(complete=True)
        assert snapshot["pending_http_calls"] == 1
        assert snapshot["complete"] is False
        assert snapshot["boundary"] == "worker_return"
        assert timing.project_stage_timing(snapshot)["boundary"] == "worker_return"
        future.set_result(None)
        assert collector.snapshot(complete=True)["pending_http_calls"] == 0
        assert collector.snapshot(complete=True)["complete"] is True


@pytest.mark.asyncio
async def test_concurrent_worker_collectors_do_not_share_metrics(caplog):
    both_started = asyncio.Event()
    active = []

    @timing.observe_worker_timing
    async def worker(label):
        active.append(label)
        if len(active) == 2:
            both_started.set()
        with timing.timing_labels(family=label), timing.measure_stage("family_execution"):
            await both_started.wait()
        return timing.current_timing_snapshot()

    with caplog.at_level(logging.INFO, logger=timing.__name__):
        first, second = await asyncio.gather(worker("first"), worker("second"))
    assert set(first["families"]) == {"first"}
    assert set(second["families"]) == {"second"}
    logs = [json.loads(record.message.split("qc_stage_timing ", 1)[1])
            for record in caplog.records if record.message.startswith("qc_stage_timing ")]
    assert len(logs) == 2
    assert all(row["complete"] and row["boundary"] == "worker_return" for row in logs)
    assert timing.current_timing_snapshot() is None


@pytest.mark.asyncio
async def test_canceled_and_failed_spans_keep_original_exceptions():
    with timing.timing_scope() as collector:
        with pytest.raises(ValueError, match="failure"):
            with timing.measure_stage("bundle_read"):
                raise ValueError("failure")
        with pytest.raises(asyncio.CancelledError):
            with timing.measure_stage("family_queue"):
                raise asyncio.CancelledError()
    stages = collector.snapshot()["stages"]
    assert stages["bundle_read"]["failed_count"] == 1
    assert stages["family_queue"]["canceled_count"] == 1
    assert stages["family_queue"]["failed_count"] == 0


@pytest.mark.asyncio
async def test_http_wait_is_separate_and_thread_inherits_family_labels():
    resources = http_module._SharedHttpResources(1)
    first_started = threading.Event()
    release = threading.Event()
    waiting = threading.Event()
    original_acquire = resources._acquire_budget
    count = [0]
    lock = threading.Lock()

    def acquire():
        with lock:
            count[0] += 1
            if count[0] == 2:
                waiting.set()
        original_acquire()

    resources._acquire_budget = acquire

    def first_operation():
        first_started.set()
        assert release.wait(3)
        return "first"

    tasks = []
    try:
        with timing.timing_scope() as collector:
            with timing.timing_labels(family="extended_document", unit="antimicrobial"):
                tasks.append(asyncio.create_task(http_module.run_shared_http_call(first_operation, resources=resources)))
                assert await asyncio.to_thread(first_started.wait, 3)
                tasks.append(asyncio.create_task(http_module.run_shared_http_call(lambda: "second", resources=resources)))
                assert await asyncio.to_thread(waiting.wait, 3)
                assert resources._active_count == 1
                release.set()
                assert await asyncio.gather(*tasks) == ["first", "second"]
            stages = collector.snapshot()
        assert resources.max_concurrency == 1
        for bucket in (stages["stages"], stages["families"]["extended_document"], stages["units"]["antimicrobial"]):
            assert bucket["http_wait"]["count"] == 2
            assert bucket["http_request"]["count"] == 2
        assert resources._active_count == 0
    finally:
        release.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        resources.executor.shutdown(wait=True)
        resources.client.close()


def test_customer_projection_keeps_stage_metrics_but_not_private_trace():
    from app.services.custom_qc_workspace_service import project_customer_safe_batch_job

    with timing.timing_scope() as collector:
        with timing.measure_stage("bundle_read"):
            pass
        measured = collector.snapshot()
    measured["private_trace"] = "do-not-export"
    projected = project_customer_safe_batch_job({
        "id": "synthetic-task", "status": "completed", "items": [],
        "summary": {"performance_profile": {
            "stage_timing": measured,
            "rule_duration_basis": "allocated_or_reported_metadata",
        }},
    }, hmac_key="test-projection-only")
    profile = projected["summary"]["performance_profile"]
    assert profile["stage_timing"]["stages"]["bundle_read"]["count"] == 1
    assert profile["slow_rule_ranking_is_measured"] is False
    assert "do-not-export" not in json.dumps(projected)


@pytest.mark.asyncio
async def test_worker_persists_pre_save_timing_and_logs_final_save_separately(monkeypatch, caplog):
    from app.routers import qc_sichuan
    from test_qc_sichuan_batch_throughput import _WorkspaceStub, _ServiceStub

    workspace, service = _WorkspaceStub(), _ServiceStub()
    workspace.job["record_ids"] = ["synthetic-visit"]
    workspace.update_batch_job_progress = timing.timed("result_write")(workspace.update_batch_job_progress)
    workspace.complete_batch_job = timing.timed("final_save")(workspace.complete_batch_job)
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: workspace)

    async def provider():
        return service

    monkeypatch.setattr(qc_sichuan, "get_qc_service", provider)
    with caplog.at_level(logging.INFO, logger=timing.__name__):
        await qc_sichuan._run_sichuan_workspace_batch_job("job-throughput-001")
    assert workspace.job["status"] == "completed"
    snapshot = workspace.summary["performance_profile"]["stage_timing"]
    assert snapshot["boundary"] == "before_final_save" and snapshot["complete"] is False
    assert snapshot["stages"]["record_execution"]["count"] == 1
    assert snapshot["stages"]["result_write"]["count"] > 0
    assert "final_save" not in snapshot["stages"]
    rows = [json.loads(record.message.split("qc_stage_timing ", 1)[1])
            for record in caplog.records if record.message.startswith("qc_stage_timing ")]
    assert len(rows) == 1
    assert rows[0]["complete"] is True
    assert rows[0]["stages"]["final_save"]["count"] == 1
    assert service.evaluate_calls == 1


@pytest.mark.asyncio
async def test_logging_failure_cannot_change_clinical_return(monkeypatch):
    @timing.observe_worker_timing
    async def worker():
        return "preserved-result"

    def broken(*args, **kwargs):
        raise OSError("diagnostic disk unavailable")

    monkeypatch.setattr(timing.logger, "info", broken)
    assert await worker() == "preserved-result"
    assert timing.current_timing_snapshot() is None
