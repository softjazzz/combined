"""仅在明确标记的独立合成PG中验证队列事务、并发和权限；不连接客户环境。"""

from __future__ import annotations

import os
import threading
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest

from medqc_ingest.config import PassfilePostgresSettings
from medqc_ingest.control.memory import MemoryJobRepository
from medqc_ingest.control.models import ControlError
from medqc_ingest.control.postgres import PostgresJobRepository, initialize_control

DATABASE = "medqc_sync_control_acceptance_20991101040001"
pytestmark = pytest.mark.skipif(
    not os.getenv("MEDQC_SYNC_STORAGE_TEST_PORT"), reason="isolated PG required"
)


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


def settings(user: str = "medqc_job_worker") -> PassfilePostgresSettings:
    return PassfilePostgresSettings(
        "127.0.0.1",
        int(os.environ["MEDQC_SYNC_STORAGE_TEST_PORT"]),
        DATABASE,
        user,
        Path(os.environ["MEDQC_SYNC_STORAGE_TEST_PASSFILE"]),
    )


def admin(database: str = DATABASE):
    import psycopg2

    current = settings("postgres")
    kwargs = current.connection_kwargs()
    kwargs["dbname"] = database
    connection = psycopg2.connect(**kwargs)
    with connection.cursor() as cur:
        cur.execute("SHOW cluster_name")
        if current.port == 5432 or cur.fetchone()[0] != "medqc_sync_control_synthetic":
            connection.close()
            raise RuntimeError("refuse storage tests outside marked synthetic cluster")
    connection.rollback()
    return connection


@pytest.fixture(scope="module", autouse=True)
def initialize():
    if not os.getenv("MEDQC_SYNC_STORAGE_TEST_PORT"):
        yield
        return
    with closing(admin("postgres")) as connection:
        connection.autocommit = True
        with connection.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE,))
            if not cur.fetchone():
                cur.execute("CREATE DATABASE " + DATABASE + " OWNER medqc_owner TEMPLATE template0")
    with closing(admin()) as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT to_regclass('sync_control.job')")
            exists = cur.fetchone()[0]
        connection.rollback()
        if not exists:
            initialize_control(connection, DATABASE)
    yield


@pytest.fixture()
def repository(initialize):
    with closing(admin()) as connection, connection, connection.cursor() as cur:
        # 只有本文件独占的合成库可清空；全局角色和其他测试库不修改。
        cur.execute("SELECT current_database()")
        assert cur.fetchone()[0] == DATABASE
        cur.execute(
            "TRUNCATE sync_control.event,sync_control.schedule_fire,sync_control.job_attempt,"
            "sync_control.job_unit,sync_control.job,sync_control.schedule"
        )
    return PostgresJobRepository(settings())


def test_persistence_and_transactional_duplicate_submission(repository):
    barrier = threading.Barrier(3)
    results, errors = [], []

    def submit():
        try:
            barrier.wait()
            results.append(
                PostgresJobRepository(settings()).submit(request(), "operator", "same-key")
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=submit) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    assert len({row["job_id"] for row in results}) == 1
    assert repository.get_job(results[0]["job_id"])["status"] == "queued"
    with closing(admin()) as connection, connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM sync_control.event")
        assert cur.fetchone()[0] == 1
    with pytest.raises(ControlError) as exc:
        repository.submit(dict(request(), publish=False), "operator", "same-key")
    assert exc.value.status_code == 409


def test_global_claim_and_old_token_fencing(repository):
    for number in range(3):
        repository.submit(request(), "operator", "key-" + str(number))
    barrier = threading.Barrier(3)
    results, errors = [], []

    def claim(number):
        try:
            barrier.wait()
            results.append(PostgresJobRepository(settings()).claim("worker-" + str(number)))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=claim, args=(n,)) for n in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    claims = [row for row in results if row is not None]
    assert not errors
    assert len(claims) == 1
    job = claims[0]
    assert "lease_token" not in repository.get_job(job["job_id"])
    assert not repository.heartbeat(job["job_id"], "wrong-token")
    assert repository.heartbeat(job["job_id"], job["lease_token"])
    assert repository.claim("other-worker") is None


def test_expired_claim_requires_attested_recovery(repository):
    submitted = repository.submit(request(), "operator", "key")
    claim = repository.claim("worker")
    with closing(admin()) as connection, connection, connection.cursor() as cur:
        cur.execute(
            "UPDATE sync_control.job SET lease_expires_at=now()-interval '1 second' "
            "WHERE job_id=%s",
            (submitted["job_id"],),
        )
    assert repository.claim("other") is None
    assert repository.get_job(submitted["job_id"])["status"] == "recovery_required"
    assert not repository.heartbeat(submitted["job_id"], claim["lease_token"])
    with pytest.raises(ControlError):
        repository.retry(submitted["job_id"], "operator")
    proof = {"executor_stopped": True, "target_locks_clear": True, "batches_checked": True}
    assert (
        repository.reconcile(submitted["job_id"], "operator", "retry", proof)["status"] == "queued"
    )
    assert repository.claim("recovered")
    with closing(admin()) as connection, connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM sync_control.job_attempt")
        assert cur.fetchone()[0] == 2


def test_schedule_fire_job_and_next_date_commit_or_rollback_together(repository):
    config = {
        "request": {
            "profile": "core13",
            "interfaces": ["web.mr"],
            "mode": "replay",
            "publish": True,
        },
        "frequency": "daily",
        "local_time": "09:00",
        "window_days": 1,
        "timezone": "Asia/Shanghai",
    }
    schedule = repository.create_schedule(config, "operator")
    enabled = repository.set_schedule_enabled(schedule["schedule_id"], 1, True, "operator")
    fire = enabled["next_fire_at"]
    from datetime import datetime, timedelta

    next_fire = (datetime.fromisoformat(fire) + timedelta(days=1)).isoformat()
    original = MemoryJobRepository.enqueue_schedule

    def fail_after_mutation(self, *args):
        original(self, *args)
        raise RuntimeError("fictional-private-body-must-not-leak")

    with (
        patch.object(MemoryJobRepository, "enqueue_schedule", fail_after_mutation),
        pytest.raises(ControlError) as error,
    ):
        repository.enqueue_schedule(schedule["schedule_id"], 2, fire, request(), next_fire)
    assert "fictional-private" not in str(error.value)
    assert repository.list_jobs() == []
    assert repository.get_schedule(schedule["schedule_id"])["next_fire_at"] == fire
    job = repository.enqueue_schedule(schedule["schedule_id"], 2, fire, request(), next_fire)
    assert job
    assert (
        repository.enqueue_schedule(schedule["schedule_id"], 2, fire, request(), next_fire) is None
    )
    assert len(repository.list_jobs()) == 1


def test_api_role_can_admit_but_cannot_claim_ddl_or_delete_audit(repository):
    api = PostgresJobRepository(settings("medqc_job_api"))
    job = api.submit(request(), "operator", "api-key")
    with pytest.raises(ControlError):
        api.claim("forbidden-api-worker")
    assert api.get_job(job["job_id"])["status"] == "queued"
    import psycopg2

    with closing(psycopg2.connect(**settings("medqc_job_api").connection_kwargs())) as c:
        for query in (
            "CREATE TABLE sync_control.forbidden(id int)",
            "DELETE FROM sync_control.event",
        ):
            with pytest.raises(psycopg2.errors.InsufficientPrivilege), c.cursor() as cur:
                cur.execute(query)
            c.rollback()
    assert repository.claim("worker")


def test_initializer_refuses_nonempty_database(repository):
    with closing(admin()) as connection, pytest.raises(ControlError) as exc:
        initialize_control(connection, DATABASE)
    assert exc.value.code == "database_not_empty"
