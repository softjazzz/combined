from __future__ import annotations

import asyncio
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import ProgrammingError

from app.routers import clinical_completeness, qc_sichuan
from app.services import task_record_sync_job_service


def _request():
    return SimpleNamespace(state=SimpleNamespace(trace_id="test-trace"))


def _qc_service():
    return SimpleNamespace(client=SimpleNamespace(model="test-model"))


async def _call_route(name: str, service):
    if name == "clinical":
        return await clinical_completeness.get_clinical_completeness(
            _request(), "V", patient_id="P", institute_id="H",
            force_refresh=True, current_user={"id": "tester"},
        )
    if name == "bundle":
        return await qc_sichuan.evaluate_bundle(
            _request(),
            qc_sichuan.SichuanBundleEvaluateRequest(
                scene="final", institute_id="H", patient_id="P", visit_id="V",
            ),
            service,
        )
    return await qc_sichuan.evaluate_rule_for_visit(
        _request(),
        qc_sichuan.SichuanRuleVisitEvaluateRequest(
            rule_id="SC001", institute_id="H", patient_id="P", visit_id="V",
            force_refresh_bundle=True,
        ),
        service,
    )


def _install_fake_service(monkeypatch, name: str, events: list[str]):
    service = _qc_service()
    monkeypatch.setattr(qc_sichuan, "_enforce_sc_source_guard", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(qc_sichuan, "get_trace_id", lambda _request: "test-trace")
    monkeypatch.setattr(clinical_completeness, "get_trace_id", lambda _request: "test-trace")

    if name == "clinical":
        def load(**_kwargs):
            events.append("read")
            return {"documents": []}

        monkeypatch.setattr(clinical_completeness, "_load_clinical_bundle", load)
        monkeypatch.setattr(
            clinical_completeness, "ClinicalTimelineService",
            lambda: SimpleNamespace(build_from_bundle=lambda _bundle: SimpleNamespace(
                to_dict=lambda: {"status": "ok"},
            )),
        )
    elif name == "bundle":
        async def evaluate(**_kwargs):
            events.append("read")
            return {"status": "ok"}

        monkeypatch.setattr(qc_sichuan, "evaluate_running_final_bundle", evaluate)
    else:
        async def evaluate(**_kwargs):
            events.append("read")
            return {"status": "ok"}

        service.evaluate_rule_for_visit = evaluate
    return service


@pytest.mark.parametrize("name", ["clinical", "bundle", "rule"])
@pytest.mark.asyncio
async def test_routes_hold_lock_until_bundle_work_finishes(monkeypatch, name):
    events: list[str] = []
    service = _install_fake_service(monkeypatch, name, events)
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: events.append("lock") or "lock")
    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", lambda _lock: events.append("unlock"))

    result = await _call_route(name, service)
    assert result["data"]["status"] == "ok"
    assert events == ["lock", "read", "unlock"]


@pytest.mark.parametrize("name", ["clinical", "bundle", "rule"])
@pytest.mark.asyncio
async def test_routes_fail_closed_on_lock_timeout(monkeypatch, name):
    events: list[str] = []
    service = _install_fake_service(monkeypatch, name, events)

    def timeout():
        raise TimeoutError("database busy")

    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", timeout)
    with pytest.raises(HTTPException) as error:
        await _call_route(name, service)
    assert error.value.status_code == 503
    assert events == []


@pytest.mark.parametrize("name", ["clinical", "bundle", "rule"])
@pytest.mark.asyncio
async def test_routes_release_lock_when_service_fails(monkeypatch, name):
    events: list[str] = []
    service = _install_fake_service(monkeypatch, name, events)
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: "lock")
    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", lambda _lock: events.append("unlock"))

    if name == "clinical":
        def fail(**_kwargs):
            raise RuntimeError("read failed")

        monkeypatch.setattr(clinical_completeness, "_load_clinical_bundle", fail)
    elif name == "bundle":
        async def fail(**_kwargs):
            raise RuntimeError("read failed")

        monkeypatch.setattr(qc_sichuan, "evaluate_running_final_bundle", fail)
    else:
        async def fail(**_kwargs):
            raise RuntimeError("read failed")

        service.evaluate_rule_for_visit = fail

    with pytest.raises(HTTPException):
        await _call_route(name, service)
    assert events == ["unlock"]


@pytest.mark.parametrize("name", ["clinical", "bundle", "rule"])
@pytest.mark.asyncio
async def test_routes_work_without_pg_lock(monkeypatch, name):
    events: list[str] = []
    service = _install_fake_service(monkeypatch, name, events)
    bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    monkeypatch.setattr(qc_sichuan, "SessionLocal", SimpleNamespace(kw={"bind": bind}))
    monkeypatch.setattr(qc_sichuan, "create_engine", lambda *_args, **_kwargs: pytest.fail("PG lock used"))

    await _call_route(name, service)
    assert events == ["read"]


@pytest.mark.asyncio
async def test_cancel_during_acquisition_releases_acquired_lock(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    events: list[str] = []

    def acquire():
        started.set()
        assert finish.wait(1)
        return "lock"

    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", acquire)
    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", lambda _lock: events.append("unlock"))
    task = asyncio.create_task(qc_sichuan._await_cdm_read_lock_acquire())
    assert await asyncio.to_thread(started.wait, 1)
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == ["unlock"]


@pytest.mark.asyncio
async def test_batch_worker_cancel_during_acquisition_releases_later_lock(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    events: list[str] = []

    def acquire():
        started.set()
        assert finish.wait(1)
        events.append("lock")
        return "lock"

    class Workspace:
        def get_batch_job_for_processing(self, *, job_id):
            pytest.fail(f"batch job {job_id} read after cancellation")

        def fail_batch_job(self, **_kwargs):
            pytest.fail("batch job failed after cancellation")

    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", Workspace)
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", acquire)
    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", lambda _lock: events.append("unlock"))
    task = asyncio.create_task(qc_sichuan._run_sichuan_workspace_batch_job("job-1"))
    assert await asyncio.to_thread(started.wait, 1)
    task.cancel()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == ["lock", "unlock"]


@pytest.mark.asyncio
async def test_cancel_during_bundle_work_releases_lock(monkeypatch):
    events: list[str] = []
    entered = asyncio.Event()
    service = _install_fake_service(monkeypatch, "bundle", events)
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: "lock")

    def slow_release(_lock):
        time.sleep(0.02)
        events.append("unlock")

    monkeypatch.setattr(qc_sichuan, "_release_cdm_read_lock", slow_release)

    async def wait_forever(**_kwargs):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(qc_sichuan, "evaluate_running_final_bundle", wait_forever)
    task = asyncio.create_task(_call_route("bundle", service))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == ["unlock"]


@pytest.mark.parametrize("source_fails", [False, True])
@pytest.mark.asyncio
async def test_old_database_missing_async_job_table_does_not_override_read(monkeypatch, caplog, source_fails):
    events: list[str] = []
    service = _install_fake_service(monkeypatch, "clinical", events)

    class Connection:
        def execute(self, statement, _parameters=None):
            events.append(str(statement))

        def commit(self):
            events.append("commit")

        def close(self):
            events.append("close")

    engine = SimpleNamespace(dispose=lambda: events.append("dispose"))
    monkeypatch.setattr(qc_sichuan, "SessionLocal", object())
    monkeypatch.setattr(qc_sichuan, "_acquire_cdm_read_lock", lambda: (engine, Connection()))

    def missing_table(_factory):
        raise ProgrammingError(
            "SELECT * FROM qc.qc_async_jobs", {},
            RuntimeError("relation qc.qc_async_jobs does not exist"),
        )

    monkeypatch.setattr(task_record_sync_job_service, "_schedule_next", missing_table)
    if source_fails:
        def fail(**_kwargs):
            raise RuntimeError("source read failed")

        monkeypatch.setattr(clinical_completeness, "_load_clinical_bundle", fail)
        with pytest.raises(HTTPException, match="source read failed") as error:
            await _call_route("clinical", service)
        assert error.value.status_code == 503
    else:
        result = await _call_route("clinical", service)
        assert result["data"]["status"] == "ok"

    assert "SELECT pg_advisory_unlock_shared(:key)" in events
    assert events[-2:] == ["close", "dispose"]
    assert "qc_cdm_sync_wakeup_failed error_type=ProgrammingError" in caplog.text
    assert "relation qc.qc_async_jobs does not exist" not in caplog.text


def test_pg_unlock_failure_is_not_swallowed(monkeypatch):
    events: list[str] = []

    class Connection:
        def execute(self, _statement, _parameters=None):
            raise RuntimeError("unlock failed")

        def close(self):
            events.append("close")

    engine = SimpleNamespace(dispose=lambda: events.append("dispose"))
    monkeypatch.setattr(qc_sichuan, "SessionLocal", object())
    monkeypatch.setattr(
        task_record_sync_job_service, "_schedule_next",
        lambda _factory: pytest.fail("scheduler ran after unlock failure"),
    )
    with pytest.raises(RuntimeError, match="unlock failed"):
        qc_sichuan._release_cdm_read_lock((engine, Connection()))
    assert events == ["close", "dispose"]
