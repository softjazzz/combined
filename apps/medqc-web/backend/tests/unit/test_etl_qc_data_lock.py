"""The legacy ETL writer must join the task/QC data-lock protocol."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.services import etl_sync
from app.services.task_record_sync_job_service import _GLOBAL_LOCK_KEY


class _Scalar:
    def __init__(self, value: bool):
        self.value = value

    def scalar(self) -> bool:
        return self.value


class _Connection:
    def __init__(
        self,
        events: list[tuple[str, int | None]],
        *,
        denied_key: int | None,
        unlock_error_key: int | None = None,
        rollback_error: bool = False,
        acquire_error_key: int | None = None,
    ):
        self.events = events
        self.denied_key = denied_key
        self.unlock_error_key = unlock_error_key
        self.rollback_error = rollback_error
        self.acquire_error_key = acquire_error_key

    def execute(self, statement, params):
        sql = str(statement)
        key = params["lock_key"]
        if "pg_try_advisory_lock" in sql:
            self.events.append(("try", key))
            if key == self.acquire_error_key:
                raise RuntimeError("transaction is aborted")
            return _Scalar(key != self.denied_key)
        if "pg_advisory_unlock" in sql:
            self.events.append(("unlock", key))
            if key == self.unlock_error_key:
                raise RuntimeError("transaction is aborted")
            return _Scalar(True)
        raise AssertionError(f"unexpected SQL: {sql}")

    def rollback(self):
        self.events.append(("rollback", None))
        if self.rollback_error:
            raise RuntimeError("rollback failed")

    def invalidate(self):
        self.events.append(("invalidate", None))

    def close(self):
        self.events.append(("close", None))


class _Engine:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(
        self,
        events: list[tuple[str, int | None]],
        *,
        denied_key: int | None,
        unlock_error_key: int | None = None,
        rollback_error: bool = False,
        acquire_error_key: int | None = None,
    ):
        self.events = events
        self.denied_key = denied_key
        self.unlock_error_key = unlock_error_key
        self.rollback_error = rollback_error
        self.acquire_error_key = acquire_error_key

    def connect(self):
        self.events.append(("connect", None))
        return _Connection(
            self.events,
            denied_key=self.denied_key,
            unlock_error_key=self.unlock_error_key,
            rollback_error=self.rollback_error,
            acquire_error_key=self.acquire_error_key,
        )


@pytest.mark.parametrize(
    ("denied_key", "expected_events"),
    [
        (_GLOBAL_LOCK_KEY, [("try", _GLOBAL_LOCK_KEY)]),
        (etl_sync._SYNC_LOCK_KEY, [
            ("try", _GLOBAL_LOCK_KEY),
            ("try", etl_sync._SYNC_LOCK_KEY),
            ("rollback", None),
            ("unlock", _GLOBAL_LOCK_KEY),
        ]),
    ],
)
def test_busy_lock_prevents_all_sync_writes(monkeypatch, denied_key, expected_events):
    events: list[tuple[str, int | None]] = []
    monkeypatch.setattr(etl_sync, "engine", _Engine(events, denied_key=denied_key))
    monkeypatch.setattr(etl_sync._sync_state, "is_running", True)
    monkeypatch.setattr(
        etl_sync, "_upsert_sync_job_state",
        lambda _state: pytest.fail("busy sync must not rewrite another worker's state"),
    )
    monkeypatch.setattr(
        etl_sync, "get_remote_db_url",
        lambda: pytest.fail("busy sync must not start source work"),
    )

    result = etl_sync.run_sync()

    assert result == {"success": False, "error": "同步正在进行中，请稍后再试"}
    assert etl_sync._sync_state.is_running is True
    assert events == [("connect", None), *expected_events, ("close", None)]


def test_both_locks_survive_until_failure_cleanup_and_release_in_reverse(monkeypatch):
    events: list[tuple[str, int | None]] = []
    monkeypatch.setattr(etl_sync, "engine", _Engine(events, denied_key=None))
    monkeypatch.setattr(etl_sync._sync_state, "is_running", False)
    monkeypatch.setattr(
        etl_sync, "_upsert_sync_job_state",
        lambda _state: events.append(("state", None)),
    )
    monkeypatch.setattr(
        etl_sync, "get_remote_db_url",
        lambda: events.append(("source", None)) or None,
    )

    result = etl_sync.run_sync()

    assert result == {"success": False, "error": "REMOTE_DB_URL 未配置"}
    assert events[:3] == [
        ("connect", None),
        ("try", _GLOBAL_LOCK_KEY),
        ("try", etl_sync._SYNC_LOCK_KEY),
    ]
    assert events.index(("source", None)) > events.index(("try", etl_sync._SYNC_LOCK_KEY))
    assert events[-5:] == [
        ("rollback", None),
        ("unlock", etl_sync._SYNC_LOCK_KEY),
        ("rollback", None),
        ("unlock", _GLOBAL_LOCK_KEY),
        ("close", None),
    ]
    assert events.count(("state", None)) >= 2
    assert etl_sync._sync_state.is_running is False


@pytest.mark.parametrize("rollback_error", [False, True])
def test_failed_unlock_invalidates_pooled_connection(monkeypatch, rollback_error):
    events: list[tuple[str, int | None]] = []
    monkeypatch.setattr(
        etl_sync,
        "engine",
        _Engine(
            events,
            denied_key=etl_sync._SYNC_LOCK_KEY,
            unlock_error_key=_GLOBAL_LOCK_KEY,
            rollback_error=rollback_error,
        ),
    )
    monkeypatch.setattr(etl_sync._sync_state, "is_running", True)
    monkeypatch.setattr(
        etl_sync, "_upsert_sync_job_state",
        lambda _state: pytest.fail("busy sync must not write state"),
    )

    result = etl_sync.run_sync()

    assert result == {"success": False, "error": "同步正在进行中，请稍后再试"}
    assert events[-2:] == [("invalidate", None), ("close", None)]
    if rollback_error:
        assert ("unlock", _GLOBAL_LOCK_KEY) not in events
    else:
        assert ("unlock", _GLOBAL_LOCK_KEY) in events


def test_failed_second_acquisition_rolls_back_before_releasing_global_lock(monkeypatch):
    events: list[tuple[str, int | None]] = []
    monkeypatch.setattr(
        etl_sync,
        "engine",
        _Engine(
            events,
            denied_key=None,
            acquire_error_key=etl_sync._SYNC_LOCK_KEY,
        ),
    )
    monkeypatch.setattr(etl_sync._sync_state, "is_running", True)

    with pytest.raises(RuntimeError, match="transaction is aborted"):
        etl_sync.run_sync()

    assert events == [
        ("connect", None),
        ("try", _GLOBAL_LOCK_KEY),
        ("try", etl_sync._SYNC_LOCK_KEY),
        ("rollback", None),
        ("unlock", _GLOBAL_LOCK_KEY),
        ("close", None),
    ]


def test_coordination_key_import_failure_does_not_mask_error_or_write(monkeypatch):
    events: list[tuple[str, int | None]] = []
    monkeypatch.setattr(etl_sync, "engine", _Engine(events, denied_key=None))
    monkeypatch.setattr(etl_sync._sync_state, "is_running", True)
    monkeypatch.setattr(
        etl_sync, "_upsert_sync_job_state",
        lambda _state: pytest.fail("failed import must not write state"),
    )
    missing_key_module = ModuleType("app.services.task_record_sync_job_service")
    monkeypatch.setitem(sys.modules, missing_key_module.__name__, missing_key_module)

    with pytest.raises(ImportError, match="_GLOBAL_LOCK_KEY"):
        etl_sync.run_sync()

    assert events == []
    assert etl_sync._sync_state.is_running is True


@pytest.mark.parametrize("database_engine", [None, SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))])
def test_non_postgres_keeps_in_process_busy_semantics(monkeypatch, database_engine):
    monkeypatch.setattr(etl_sync, "engine", database_engine)
    monkeypatch.setattr(etl_sync._sync_state, "is_running", True)
    monkeypatch.setattr(
        etl_sync, "_upsert_sync_job_state",
        lambda _state: pytest.fail("busy sync must not write state"),
    )

    assert etl_sync.run_sync() == {"success": False, "error": "同步正在进行中，请稍后再试"}
    assert etl_sync._sync_state.is_running is True
