"""样本池同步与任务质控共享 CDM 写锁的隔离反例。"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.routers import qc_sample_pools as router
from app.services.task_record_sync_job_service import _GLOBAL_LOCK_KEY


class _Service:
    def __init__(self, events, *, payload=None, fail_sync=False):
        self.events = events
        self.payload = payload or {}
        self.fail_sync = fail_sync
        self.failed_message = None

    def get_sync_job(self, *, job_id):
        self.events.append("get")
        return {"pool_id": "pool-1", "payload": self.payload}

    def mark_sync_job_running(self, *, job_id):
        self.events.append("running")

    def update_sync_job_progress(self, *, job_id, progress):
        self.events.append("progress")

    def sync_pool_records(self, **kwargs):
        self.events.append("sync")
        if self.fail_sync:
            raise RuntimeError("source unavailable")
        return {"eligible_visits": 1}

    def finish_sync_job(self, *, job_id, summary):
        self.events.append("finished")

    def fail_sync_job(self, *, job_id, error_message):
        self.events.append("failed")
        self.failed_message = error_message

    def append_pool_items_by_admission_filter(self, **kwargs):
        self.events.append("append")
        return {"sync_item_ids": []}


def test_worker_holds_write_lock_through_sync_and_finish(monkeypatch):
    events = []
    service = _Service(events)
    monkeypatch.setattr(router, "_service", lambda: service)

    @contextmanager
    def lock():
        events.append("lock")
        yield True
        events.append("unlock")

    monkeypatch.setattr(router, "_sample_sync_write_lock", lock)
    router._run_sample_pool_sync_job("job-1")
    assert events == ["get", "lock", "running", "sync", "finished", "unlock"]


def test_busy_lock_fails_queued_job_without_pool_write(monkeypatch):
    events = []
    service = _Service(events)
    monkeypatch.setattr(router, "_service", lambda: service)

    @contextmanager
    def busy():
        events.append("lock_busy")
        yield False
        events.append("closed")

    monkeypatch.setattr(router, "_sample_sync_write_lock", busy)
    router._run_sample_pool_sync_job("job-1")
    assert events == ["get", "lock_busy", "failed", "closed"]
    assert "稍后重新发起" in service.failed_message


def test_failure_releases_lock_after_persisting_failure(monkeypatch):
    events = []
    service = _Service(events, fail_sync=True)
    monkeypatch.setattr(router, "_service", lambda: service)

    @contextmanager
    def lock():
        events.append("lock")
        yield True
        events.append("unlock")

    monkeypatch.setattr(router, "_sample_sync_write_lock", lock)
    router._run_sample_pool_sync_job("job-1")
    assert events == ["get", "lock", "running", "sync", "failed", "unlock"]


def test_empty_scope_finishes_without_sync_while_locked(monkeypatch):
    events = []
    service = _Service(events, payload={
        "admission_filter": {
            "start_date": "2026-09-01", "end_date": "2026-09-02", "departments": [],
        },
    })
    monkeypatch.setattr(router, "_service", lambda: service)

    @contextmanager
    def lock():
        events.append("lock")
        yield True
        events.append("unlock")

    monkeypatch.setattr(router, "_sample_sync_write_lock", lock)
    router._run_sample_pool_sync_job("job-1")
    assert events == ["get", "lock", "running", "append", "progress", "finished", "unlock"]


@pytest.mark.parametrize("available", [True, False])
def test_postgres_uses_shared_key_and_releases_connection(monkeypatch, available):
    events = []

    class Connection:
        def __enter__(self):
            events.append("connect")
            return self

        def __exit__(self, *_args):
            events.append("close")

        def execute(self, statement, params):
            events.append((str(statement), params["key"]))
            return SimpleNamespace(scalar_one=lambda: available)

        def commit(self):
            events.append("commit")

        def close(self):
            events.append("close")

    class LockEngine:
        def connect(self):
            return Connection()

        def dispose(self):
            events.append("dispose")

    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), url="postgresql://test")
    monkeypatch.setattr(router, "SessionLocal", SimpleNamespace(kw={"bind": bind}))
    monkeypatch.setattr(router, "create_engine", lambda *args, **kwargs: LockEngine())
    with router._sample_sync_write_lock() as acquired:
        assert acquired is available
        events.append("work")
    sql_calls = [event for event in events if isinstance(event, tuple)]
    expected = [("SELECT pg_try_advisory_lock(:key)", _GLOBAL_LOCK_KEY)]
    if available:
        expected.append(("SELECT pg_advisory_unlock(:key)", _GLOBAL_LOCK_KEY))
    assert sql_calls == expected
    assert events.index("work") < events.index("dispose")


def test_sqlite_never_calls_postgres_lock_api(monkeypatch):
    bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    monkeypatch.setattr(router, "SessionLocal", SimpleNamespace(kw={"bind": bind}))
    monkeypatch.setattr(router, "create_engine", lambda *args, **kwargs: pytest.fail("PG API invoked"))
    with router._sample_sync_write_lock() as acquired:
        assert acquired


def test_lock_acquisition_failure_marks_job_failed_before_running(monkeypatch):
    events = []
    service = _Service(events)
    monkeypatch.setattr(router, "_service", lambda: service)

    @contextmanager
    def broken_lock():
        raise OSError("database unavailable")
        yield True

    monkeypatch.setattr(router, "_sample_sync_write_lock", broken_lock)
    router._run_sample_pool_sync_job("job-1")
    assert events == ["get", "failed"]
    assert "锁获取失败" in service.failed_message


@pytest.mark.parametrize("failure", ["unlock", "commit"])
def test_release_failure_invalidates_connection_without_rewriting_completed_job(monkeypatch, failure):
    events = []
    service = _Service(events)
    monkeypatch.setattr(router, "_service", lambda: service)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            events.append("closed")

        def execute(self, statement, _params):
            if "pg_advisory_unlock" in str(statement) and failure == "unlock":
                raise RuntimeError("unlock failed")
            return SimpleNamespace(scalar_one=lambda: True)

        def commit(self):
            events.append("commit")
            if failure == "commit" and events.count("commit") == 2:
                raise RuntimeError("commit failed")

        def invalidate(self):
            events.append("invalidated")

    class LockEngine:
        def connect(self):
            return Connection()

        def dispose(self):
            events.append("disposed")

    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), url="postgresql://test")
    monkeypatch.setattr(router, "SessionLocal", SimpleNamespace(kw={"bind": bind}))
    monkeypatch.setattr(router, "create_engine", lambda *args, **kwargs: LockEngine())
    router._run_sample_pool_sync_job("job-1")
    assert events.index("finished") < events.index("invalidated") < events.index("closed")
    assert events[-1] == "disposed"
    assert "failed" not in events


def test_context_exit_error_does_not_rewrite_completed_job(monkeypatch):
    events = []
    service = _Service(events)
    monkeypatch.setattr(router, "_service", lambda: service)

    @contextmanager
    def broken_release():
        yield True
        raise RuntimeError("connection close failed")

    monkeypatch.setattr(router, "_sample_sync_write_lock", broken_release)
    router._run_sample_pool_sync_job("job-1")
    assert events == ["get", "running", "sync", "finished"]


def test_cancellation_releases_lock_context(monkeypatch):
    events = []
    service = _Service(events)
    monkeypatch.setattr(router, "_service", lambda: service)

    @contextmanager
    def lock():
        events.append("lock")
        try:
            yield True
        finally:
            events.append("unlock")

    def cancelled(**kwargs):
        events.append("sync")
        raise KeyboardInterrupt()

    monkeypatch.setattr(service, "sync_pool_records", cancelled)
    monkeypatch.setattr(router, "_sample_sync_write_lock", lock)
    with pytest.raises(KeyboardInterrupt):
        router._run_sample_pool_sync_job("job-1")
    assert events == ["get", "lock", "running", "sync", "unlock"]
