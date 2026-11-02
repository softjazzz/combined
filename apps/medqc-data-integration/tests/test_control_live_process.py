"""实际 HTTP/worker 子进程与控制库恢复证明；仅显式开启的独占 PG18 合成库。"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pytest
from control_pg_fixture import (
    DEFAULT_PASSFILE,
    PORT,
    ROOT,
    clear_pipeline_databases,
    guarded_connection,
    initialize_pipeline_databases,
)

from medqc_ingest.config import PassfilePostgresSettings
from medqc_ingest.control.admission import AdmissionService
from medqc_ingest.control.memory import MemoryJobRepository
from medqc_ingest.control.models import Actor
from medqc_ingest.control.pipeline import PipelineBinding, PipelineExecutor
from medqc_ingest.control.postgres import initialize_control
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.runner import JobRunner
from medqc_ingest.domain import resolve_interface

SUFFIX = "20991101060001"
DATABASE = "medqc_sync_control_acceptance_" + SUFFIX
RESTORE = "medqc_sync_control_acceptance_20991101060002"
READ_TOKEN = "synthetic-read-token-not-a-real-secret-0001"
RUN_TOKEN = "synthetic-run-token-not-a-real-secret-0002"
pytestmark = pytest.mark.skipif(
    os.getenv("MEDQC_SYNC_LIVE_PROCESS_TEST_PORT") != str(PORT),
    reason="explicit marked PG18 live-process opt-in required",
)


def control_connection(database=DATABASE):
    """先核对独立集群 marker，再连本测试固定的两个控制库。"""
    import psycopg2

    if database not in {DATABASE, RESTORE}:
        raise RuntimeError("synthetic control scope refused")
    with closing(guarded_connection("postgres")):
        pass
    settings = PassfilePostgresSettings("127.0.0.1", PORT, database, "postgres", DEFAULT_PASSFILE)
    connection = psycopg2.connect(**settings.connection_kwargs())
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(),current_setting('cluster_name')")
        assert cursor.fetchone() == (database, "medqc_sync_control_synthetic")
    connection.rollback()
    return connection


def initialize_databases():
    from psycopg2 import sql

    with closing(guarded_connection("postgres")) as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            for database in (DATABASE, RESTORE):
                cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (database,))
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {} OWNER medqc_owner TEMPLATE template0").format(
                            sql.Identifier(database)
                        )
                    )
    with closing(control_connection()) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('sync_control.job')")
            exists = cursor.fetchone()[0] is not None
        connection.rollback()
        if not exists:
            initialize_control(connection, DATABASE)
        with connection, connection.cursor() as cursor:
            cursor.execute(
                "TRUNCATE sync_control.event,sync_control.schedule_fire,"
                "sync_control.job_attempt,sync_control.job_unit,sync_control.job,"
                "sync_control.schedule RESTART IDENTITY CASCADE"
            )
    with (
        closing(control_connection(RESTORE)) as connection,
        connection,
        connection.cursor() as cursor,
    ):
        # 固定合成恢复库，允许重复运行；绝不清理任意配置库。
        cursor.execute("DROP SCHEMA IF EXISTS sync_control CASCADE")


class SyntheticSource:
    """内存虚构记录用于准备 raw；没有网络驱动、主机或账号配置。"""

    def open(self):
        self.read = False

    def query(self, spec, arguments):
        assert spec.name == "web.mr" and arguments == ("2026-10-28",)
        return self

    @property
    def columns(self):
        return resolve_interface("web.mr").source_columns

    @property
    def source_types(self):
        return ("str",) * len(self.columns)

    def fetchmany(self, size):
        if self.read:
            return []
        self.read = True
        payload = dict.fromkeys(self.columns)
        payload.update(
            institute_id="synthetic-process-institute",
            patient_id="synthetic-process-patient",
            visit_id="synthetic-process-visit",
        )
        return [tuple(payload[column] for column in self.columns)]

    def close(self):
        pass


def seed_raw(ingest, cdm):
    repository = MemoryJobRepository()
    catalog = ProfileCatalog()
    admission = AdmissionService(
        catalog, repository, clock=lambda: datetime(2026, 11, 1, tzinfo=timezone.utc)
    )
    admission.submit(
        {
            "profile": "core13",
            "interfaces": ["web.mr"],
            "mode": "replay",
            "start_date": "2026-10-28",
            "end_date": "2026-10-28",
            "publish": False,
        },
        Actor("synthetic-seeder", frozenset({"run"})),
        "synthetic-seed",
    )
    executor = PipelineExecutor(
        catalog,
        {"core13": PipelineBinding(None, ingest, cdm)},
        source_factory=lambda _: SyntheticSource(),
    )
    # executor 要求 replay 有源配置；这里使用仅内存 source 对象且不打开真实适配器。
    from medqc_ingest.config import SourceSettings

    executor.bindings["core13"] = PipelineBinding(
        SourceSettings(
            "odbc",
            "synthetic.invalid",
            1,
            "synthetic",
            "synthetic",
            DEFAULT_PASSFILE,
            "synthetic-unused",
            None,
            None,
            (),
        ),
        ingest,
        cdm,
    )
    assert JobRunner(repository, executor).run(repository.claim("synthetic-seeder"))["status"] == (
        "succeeded"
    )


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def pg_document(settings):
    return {
        "host": settings.host,
        "port": settings.port,
        "database": settings.database,
        "user": settings.user,
        "passfile": str(settings.password_file),
    }


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        process.terminate()
    process.wait(timeout=15)


def http(base, path, token=None, payload=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        headers.update({"Content-Type": "application/json", "Idempotency-Key": "process-proof"})
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
    )
    try:
        response = urllib.request.urlopen(request, timeout=2)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, json.loads(response.read())


def fingerprint(database):
    from psycopg2 import sql

    result = {"tables": {}, "sequences": {}}
    with closing(control_connection(database)) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname,c.relkind FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='sync_control' AND c.relkind IN ('r','S') ORDER BY c.relname"
        )
        for table, kind in cursor.fetchall():
            identifier = sql.Identifier("sync_control", table)
            if kind == "S":
                cursor.execute(sql.SQL("SELECT last_value,is_called FROM {}").format(identifier))
                result["sequences"][table] = cursor.fetchone()
            else:
                cursor.execute(sql.SQL("SELECT row_to_json(t) FROM {} t").format(identifier))
                rows = sorted(json.dumps(row[0], sort_keys=True) for row in cursor.fetchall())
                result["tables"][table] = {
                    "rows": len(rows),
                    "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest(),
                }
    return result


def test_real_http_restart_worker_and_control_backup_restore(tmp_path, monkeypatch):
    monkeypatch.delenv("PGPASSWORD", raising=False)
    monkeypatch.setenv("MEDQC_PG_DRIVER", "psycopg2")
    pg_bin = Path(os.environ["MEDQC_SYNC_TEST_PG_BIN"])
    assert pg_bin.is_absolute() and (pg_bin / "pg_dump.exe").is_file()
    initialize_databases()
    ingest, cdm = initialize_pipeline_databases(SUFFIX)
    clear_pipeline_databases(ingest, cdm)
    seed_raw(ingest, cdm)
    token_file = write_json(
        tmp_path / "tokens.json",
        {
            "tokens": [
                {"token": READ_TOKEN, "actor_id": "synthetic-reader", "permissions": ["read"]},
                {"token": RUN_TOKEN, "actor_id": "synthetic-operator", "permissions": ["run"]},
            ]
        },
    )
    binding_file = write_json(
        tmp_path / "bindings.json",
        {
            "profiles": {
                "core13": {
                    "ingest": pg_document(ingest),
                    "cdm": pg_document(cdm),
                }
            }
        },
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        api_port = probe.getsockname()[1]
    config = {
        "postgres": {
            "host": "127.0.0.1",
            "port": PORT,
            "database": DATABASE,
            "user": "medqc_job_api",
            "passfile": str(DEFAULT_PASSFILE),
        },
        "api": {"bind": "127.0.0.1", "port": api_port, "tokens_file": str(token_file)},
        "worker": {
            "worker_id": "synthetic-process-worker",
            "poll_seconds": 0.1,
            "heartbeat_seconds": 0.5,
            "lease_seconds": 30,
            "automatic_retries": 0,
            "bindings_file": str(binding_file),
        },
    }
    api_config = write_json(tmp_path / "api.json", config)
    worker_config = write_json(
        tmp_path / "worker.json",
        dict(config, postgres=dict(config["postgres"], user="medqc_job_worker")),
    )
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    env.pop("PGPASSWORD", None)
    base = f"http://127.0.0.1:{api_port}"
    command = [sys.executable, str(ROOT / "tools/run_sync_control.py")]
    processes = []

    def launch_api(log):
        process = subprocess.Popen(
            command + ["api", "--config", str(api_config)],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        processes.append(process)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            assert process.poll() is None, "owned API process exited; inspect synthetic log"
            try:
                if http(base, "/health/live")[0] == 200:
                    return process
            except OSError:
                pass
            time.sleep(0.1)
        raise AssertionError("owned API startup timeout")

    try:
        with (tmp_path / "api.log").open("wb") as log:
            api = launch_api(log)
            assert http(base, "/v1/jobs")[0] == 401
            payload = {"profile": "core13", "interfaces": ["web.mr"], "mode": "publish_only"}
            assert http(base, "/v1/jobs", READ_TOKEN, payload)[0] == 403
            status, job = http(base, "/v1/jobs", RUN_TOKEN, payload)
            assert status == 202 and job["status"] == "queued"
            job_id = job["job_id"]
            stop_process(api)
            api = launch_api(log)
            status, persisted = http(base, "/v1/jobs/" + job_id, READ_TOKEN)
            assert status == 200 and persisted["status"] == "queued"
            assert persisted["actor_id"] == "synthetic-operator"
            with (tmp_path / "worker.log").open("wb") as worker_log:
                worker = subprocess.Popen(
                    command + ["worker", "--once", "--config", str(worker_config)],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=worker_log,
                    stderr=worker_log,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                processes.append(worker)
                assert worker.wait(timeout=60) == 0
            status, completed = http(base, "/v1/jobs/" + job_id, READ_TOKEN)
            assert status == 200 and completed["status"] == "succeeded"
            assert completed["units"][0]["result"]["written"] == 1
            assert "lease_token" not in json.dumps(completed)
            stop_process(api)
        with closing(guarded_connection(cdm.database)) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM cdm.mr")
            assert cursor.fetchone()[0] == 1
        with (
            closing(guarded_connection(ingest.database)) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute("SELECT count(*) FROM sync_ops.sync_checkpoint")
            assert cursor.fetchone()[0] == 0
        before = fingerprint(DATABASE)
        dump = tmp_path / "control.dump"
        pg_env = dict(env, PGPASSFILE=str(DEFAULT_PASSFILE))
        common = ["-h", "127.0.0.1", "-p", str(PORT), "-U", "postgres", "--no-password"]
        for args in (
            [str(pg_bin / "pg_dump.exe"), *common, "-Fc", "-f", str(dump), DATABASE],
            [str(pg_bin / "pg_restore.exe"), *common, "--exit-on-error", "-d", RESTORE, str(dump)],
        ):
            result = subprocess.run(args, env=pg_env, capture_output=True, timeout=60, check=False)
            assert result.returncode == 0, "synthetic control backup/restore failed"
        assert fingerprint(RESTORE) == before
        assert len(before["tables"]) == 6
        write_json(
            tmp_path / "live-process-proof.json",
            {
                "synthetic": True,
                "http_statuses": [401, 403, 202],
                "api_restart_queue_preserved": True,
                "worker_subprocess_publish_only": True,
                "cache_accessed": False,
                "published_rows": 1,
                "checkpoint_rows": 0,
                "restore_fingerprint_equal": True,
                "fingerprint": before,
            },
        )
    finally:
        for process in reversed(processes):
            stop_process(process)
