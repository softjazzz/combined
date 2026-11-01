"""任务仓储状态机保护测试；内存模式无数据库/网络，PG专项由隔离测试启用。"""

from __future__ import annotations

import copy
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from medqc_ingest.config import PassfilePostgresSettings
from medqc_ingest.control.memory import MemoryJobRepository, utc
from medqc_ingest.control.models import ControlError
from medqc_ingest.control.postgres import (
    PostgresJobRepository,
    initialize_control,
    validate_control_database,
)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


@pytest.mark.parametrize("role", ["medqc_owner", "medqc_job_api", "medqc_job_worker"])
@pytest.mark.parametrize("flag", [3, 4, 5, 6])
def test_initializer_rejects_privileged_owner_or_runtime_roles(role, flag):
    """CREATE ROLE/DB、BYPASSRLS、REPLICATION 都不是作业进程需要的能力。"""
    from unittest.mock import MagicMock

    database = "medqc_sync_control_acceptance_20991101040001"
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(database, "off"), (0,)]
    rows = [
        ["medqc_owner", False, False, False, False, False, False],
        ["medqc_job_worker", True, False, False, False, False, False],
        ["medqc_job_api", True, False, False, False, False, False],
    ]
    for row in rows:
        if row[0] == role:
            row[flag] = True
    cursor.fetchall.return_value = rows
    with pytest.raises(ControlError) as error:
        initialize_control(connection, database)
    assert error.value.code == "role_contract"
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()
    queries = [call.args[0] for call in cursor.execute.call_args_list]
    assert not any("CREATE SCHEMA" in query or "GRANT " in query for query in queries)


def request() -> dict:
    return {
        "profile": "core13",
        "interfaces": ["web.mr"],
        "mode": "replay",
        "start_date": "2026-10-28",
        "end_date": "2026-10-28",
        "publish": True,
        "units": [
            {"interface_name": "web.mr", "source_date": "2026-10-28", "phase": "extract"},
            {"interface_name": "web.mr", "source_date": None, "phase": "publish"},
        ],
    }


def schedule_config(weekly: bool = False) -> dict:
    config = {
        "request": {
            "profile": "core13",
            "interfaces": ["web.mr"],
            "mode": "replay",
            "publish": True,
        },
        "frequency": "weekly" if weekly else "daily",
        "local_time": "09:00",
        "window_days": 1,
        "timezone": "Asia/Shanghai",
    }
    if weekly:
        config["weekday"] = 0
    return config


def claimed(repo: MemoryJobRepository) -> tuple[dict, dict]:
    job = repo.submit(request(), "operator", "job-one")
    claim = repo.claim("worker-one")
    assert claim is not None
    return job, claim


def complete(repo: MemoryJobRepository, claim: dict) -> None:
    for unit in repo.units(claim["job_id"]):
        assert repo.start_unit(claim["job_id"], claim["lease_token"], unit["unit_id"])
        assert repo.finish_unit(
            claim["job_id"],
            claim["lease_token"],
            unit["unit_id"],
            "succeeded",
            {"counts": {"fetched": 1}},
        )
    assert repo.finish_job(claim["job_id"], claim["lease_token"], "succeeded")


def test_submission_idempotency_and_defensive_copies() -> None:
    repo = MemoryJobRepository()
    payload = request()
    first = repo.submit(payload, "operator", "key")
    again = repo.submit(copy.deepcopy(payload), "operator", "key")
    assert first["job_id"] == again["job_id"]
    assert len(repo.events) == 1
    payload["interfaces"].append("fictional")
    assert repo.get_job(first["job_id"])["request"]["interfaces"] == ["web.mr"]
    with pytest.raises(ControlError) as error:
        repo.submit(dict(request(), publish=False), "operator", "key")
    assert error.value.status_code == 409


def test_token_is_private_and_stale_token_does_not_mutate() -> None:
    repo = MemoryJobRepository()
    job, claim = claimed(repo)
    assert "lease_token" not in repo.get_job(job["job_id"])
    assert "lease_token" not in repo.list_jobs()[0]
    before = copy.deepcopy(repo.jobs)
    assert not repo.heartbeat(job["job_id"], "wrong-token")
    assert not repo.start_unit(
        job["job_id"], "wrong-token", repo.units(job["job_id"])[0]["unit_id"]
    )
    assert not repo.finish_job(job["job_id"], "wrong-token", "failed")
    assert before == repo.jobs
    assert repo.heartbeat(job["job_id"], claim["lease_token"])


def test_claim_is_global_singleton_even_with_threads() -> None:
    repo = MemoryJobRepository()
    for n in range(4):
        repo.submit(request(), "operator", "key-" + str(n))
    barrier = threading.Barrier(4)
    results = []

    def run(number: int) -> None:
        barrier.wait()
        results.append(repo.claim("worker-" + str(number)))

    threads = [threading.Thread(target=run, args=(n,)) for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(value is not None for value in results) == 1


def test_expired_lease_is_quarantined_and_blocks_other_claims() -> None:
    clock = Clock()
    repo = MemoryJobRepository(clock)
    job = repo.submit(request(), "operator", "key")
    first = repo.claim("worker", 5)
    repo.submit(request(), "operator", "second")
    clock.now += timedelta(seconds=6)
    assert repo.claim("another") is None
    assert repo.get_job(job["job_id"])["status"] == "recovery_required"
    assert not repo.heartbeat(job["job_id"], first["lease_token"])
    with pytest.raises(ControlError):
        repo.retry(job["job_id"], "operator")
    assert len(repo.list_recovery()) == 1


def test_recovery_requires_proof_and_keeps_completed_units() -> None:
    repo = MemoryJobRepository()
    job, claim = claimed(repo)
    unit = repo.units(job["job_id"])[0]
    assert repo.start_unit(job["job_id"], claim["lease_token"], unit["unit_id"])
    assert repo.finish_unit(
        job["job_id"], claim["lease_token"], unit["unit_id"], "succeeded", {"batch_id": 99}
    )
    assert repo.mark_recovery(job["job_id"], claim["lease_token"], "commit_unknown")
    with pytest.raises(ControlError):
        repo.reconcile(job["job_id"], "operator", "retry", {"executor_stopped": True})
    proof = {"executor_stopped": True, "target_locks_clear": True, "batches_checked": True}
    result = repo.reconcile(job["job_id"], "operator", "retry", proof)
    assert result["status"] == "queued"
    assert repo.units(job["job_id"])[0]["status"] == "succeeded"
    assert repo.events[-1]["details"]["verification"] == "operator-attested"
    assert len(repo.attempts) == 1


def test_retry_only_resets_failed_and_unexecuted_units() -> None:
    repo = MemoryJobRepository()
    job, claim = claimed(repo)
    first, second = repo.units(job["job_id"])
    assert repo.start_unit(job["job_id"], claim["lease_token"], first["unit_id"])
    assert repo.finish_unit(job["job_id"], claim["lease_token"], first["unit_id"], "succeeded", {})
    assert repo.start_unit(job["job_id"], claim["lease_token"], second["unit_id"])
    assert repo.finish_unit(
        job["job_id"], claim["lease_token"], second["unit_id"], "failed", {"code": "failed"}
    )
    assert repo.finish_job(job["job_id"], claim["lease_token"], "failed", {"code": "failed"})
    assert repo.retry(job["job_id"], "operator")["status"] == "queued"
    assert [u["status"] for u in repo.units(job["job_id"])] == ["succeeded", "queued"]
    assert next(iter(repo.attempts.values()))["status"] == "failed"


def test_queued_cancel_and_running_cancel_are_different() -> None:
    repo = MemoryJobRepository()
    job = repo.submit(request(), "operator", "key")
    assert repo.cancel(job["job_id"], "operator")["status"] == "cancelled"
    assert all(u["status"] == "cancelled" for u in repo.units(job["job_id"]))
    second = repo.submit(request(), "operator", "key2")
    claim = repo.claim("worker")
    assert repo.cancel(second["job_id"], "operator")["status"] == "running"
    assert repo.get_job(second["job_id"])["cancel_requested"]
    assert repo.finish_job(second["job_id"], claim["lease_token"], "cancelled")


def test_cannot_claim_success_before_all_units_done() -> None:
    repo = MemoryJobRepository()
    job, claim = claimed(repo)
    assert not repo.finish_job(job["job_id"], claim["lease_token"], "succeeded")
    complete(repo, claim)
    assert repo.get_job(job["job_id"])["status"] == "succeeded"


def test_cancel_during_failed_backoff_blocks_automatic_retry() -> None:
    repo = MemoryJobRepository()
    job, claim = claimed(repo)
    assert repo.finish_job(job["job_id"], claim["lease_token"], "failed", {"code": "network_error"})
    cancelled = repo.cancel(job["job_id"], "operator")
    assert cancelled["status"] == "failed" and cancelled["cancel_requested"]
    assert repo.retry(job["job_id"], "operator")["cancel_requested"] is False


def test_source_limitation_is_not_success() -> None:
    repo = MemoryJobRepository()
    job, claim = claimed(repo)
    for unit in repo.units(job["job_id"]):
        assert repo.start_unit(job["job_id"], claim["lease_token"], unit["unit_id"])
        assert repo.finish_unit(
            job["job_id"],
            claim["lease_token"],
            unit["unit_id"],
            "source_limited",
            {"source_limited": True},
        )
    assert not repo.finish_job(job["job_id"], claim["lease_token"], "succeeded")
    assert repo.finish_job(job["job_id"], claim["lease_token"], "completed_with_source_limitations")


def test_payload_and_original_error_text_rejected() -> None:
    repo = MemoryJobRepository()
    job, claim = claimed(repo)
    unit = repo.units(job["job_id"])[0]
    assert repo.start_unit(job["job_id"], claim["lease_token"], unit["unit_id"])
    for result in (
        {"payload": "private"},
        {"error_location": "private clinical body"},
        {"counts": {"patient_id": 99}},
    ):
        with pytest.raises(ControlError):
            repo.finish_unit(job["job_id"], claim["lease_token"], unit["unit_id"], "failed", result)
    assert repo.units(job["job_id"])[0]["status"] == "running"


def test_schedule_fire_is_atomic_and_cannot_repeat_after_version_change() -> None:
    repo = MemoryJobRepository(Clock())
    schedule = repo.create_schedule(schedule_config(), "operator")
    assert not schedule["enabled"] and schedule["next_fire_at"] is None
    enabled = repo.set_schedule_enabled(schedule["schedule_id"], 1, True, "operator")
    fire = enabled["next_fire_at"]
    first = repo.enqueue_schedule(
        schedule["schedule_id"], 2, fire, request(), "2026-11-02T01:00:00+00:00"
    )
    assert first is not None
    assert (
        repo.enqueue_schedule(
            schedule["schedule_id"], 2, fire, request(), "2026-11-02T01:00:00+00:00"
        )
        is None
    )
    with pytest.raises(ControlError) as error:
        repo.set_schedule_enabled(schedule["schedule_id"], 1, False, "operator")
    assert error.value.status_code == 409
    assert len(repo.fires) == 1 and len(repo.jobs) == 1


def test_schedule_weekly_to_daily_replaces_config() -> None:
    repo = MemoryJobRepository(Clock())
    schedule = repo.create_schedule(schedule_config(weekly=True), "operator")
    changed = repo.update_schedule(schedule["schedule_id"], 1, schedule_config(), "operator")
    assert "weekday" not in changed["config"]
    assert repo.set_schedule_enabled(schedule["schedule_id"], 2, True, "operator")["next_fire_at"]


def test_db_scope_and_runtime_identity_checked_without_connecting() -> None:
    for database in ("medqc", "postgres", "medqc_cache_poc", "medqc_sync_control_acceptance_bad"):
        with pytest.raises(ControlError):
            validate_control_database(database)
    for user, host in (
        ("postgres", "127.0.0.1"),
        ("medqc_owner", "127.0.0.1"),
        ("worker", "remote"),
    ):
        with pytest.raises(ControlError):
            PostgresJobRepository(
                PassfilePostgresSettings(host, 5432, "medqc_sync_control", user, Path("missing"))
            )
    assert validate_control_database("medqc_sync_control_acceptance_20261101060001")


def test_pg_json_fractional_seconds_work_on_python310() -> None:
    assert utc("2026-11-01T07:38:53.23348+00:00").microsecond == 233480
    assert utc("2026-11-01T07:38:53.2Z").microsecond == 200000
