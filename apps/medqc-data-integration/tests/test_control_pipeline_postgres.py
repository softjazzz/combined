"""真实 PG18 + 合成 Caché，验证控制任务复用旧抽取/发布事务边界。"""

from __future__ import annotations

import os
from contextlib import closing
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from control_pg_fixture import (
    PORT,
    clear_pipeline_databases,
    guarded_connection,
    initialize_pipeline_databases,
)

from medqc_ingest.config import SourceSettings
from medqc_ingest.control.admission import AdmissionService
from medqc_ingest.control.memory import MemoryJobRepository
from medqc_ingest.control.models import Actor
from medqc_ingest.control.pipeline import PipelineBinding, PipelineExecutor
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.runner import JobRunner
from medqc_ingest.domain import ErrorKind, IngestError, resolve_interface
from medqc_ingest.repositories.postgres import PostgresCdmRepository

pytestmark = pytest.mark.skipif(
    os.getenv("MEDQC_SYNC_PIPELINE_TEST_PORT") != str(PORT),
    reason="explicit isolated PG18 pipeline opt-in required",
)


class SyntheticSource:
    """只能生成虚构值；没有 ODBC/JDBC 调用或凭据读取路径。"""

    def __init__(self, *, count=3, fail_fetch=False):
        self.count, self.fail_fetch = count, fail_fetch
        self.index, self.query_calls, self.closed = 0, 0, False

    def open(self):
        pass

    def query(self, spec, arguments):
        assert spec.name == "web.mr"
        assert arguments == ("2026-10-28",)
        self.index, self.query_calls = 0, self.query_calls + 1
        return self

    @property
    def columns(self):
        return resolve_interface("web.mr").source_columns

    @property
    def source_types(self):
        return ("str",) * len(self.columns)

    def fetchmany(self, size):
        if self.fail_fetch and self.index == 1:
            raise IngestError(ErrorKind.SOURCE_QUERY, "synthetic_fetch_fault")
        if self.index == self.count:
            return []
        rows = []
        while self.index < self.count and len(rows) < size:
            payload = dict.fromkeys(self.columns)
            payload.update(
                institute_id="synthetic-institute",
                patient_id=f"synthetic-patient-{self.index}",
                visit_id=f"synthetic-visit-{self.index}",
                name=f"synthetic-name-{self.index}",
            )
            rows.append(tuple(payload[column] for column in self.columns))
            self.index += 1
        return rows

    def close(self):
        self.closed = True


class FailAfterRealCdmWrite(PostgresCdmRepository):
    def upsert_target(self, target, rows):
        super().upsert_target(target, rows)
        raise IngestError(ErrorKind.CDM_WRITE, "synthetic_write_fault")


@pytest.fixture(scope="module")
def databases():
    return initialize_pipeline_databases()


@pytest.fixture()
def pipeline(databases, monkeypatch):
    monkeypatch.setenv("MEDQC_PG_DRIVER", "psycopg2")
    monkeypatch.delenv("PGPASSWORD", raising=False)
    ingest, cdm = databases
    clear_pipeline_databases(ingest, cdm)
    catalog = ProfileCatalog()
    source = SourceSettings(
        "odbc",
        "synthetic.invalid",
        1,
        "synthetic",
        "synthetic",
        ingest.password_file,
        "synthetic-unused-driver",
        None,
        None,
        (),
    )
    binding = PipelineBinding(source, ingest, cdm, chunk_size=1)
    return catalog, binding


def submit(catalog, *, repository=None, key="synthetic-request"):
    repository = repository or MemoryJobRepository()
    admission = AdmissionService(
        catalog, repository, clock=lambda: datetime(2026, 11, 1, tzinfo=timezone.utc)
    )
    job = admission.submit(
        {
            "profile": "core13",
            "interfaces": ["web.mr"],
            "mode": "replay",
            "start_date": "2026-10-28",
            "end_date": "2026-10-28",
            "publish": True,
        },
        Actor("synthetic-operator", frozenset({"run"})),
        key,
    )
    return repository, job


def query(settings, sql, parameters=None):
    with (
        closing(guarded_connection(settings.database, settings.password_file)) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(sql, parameters)
        return cursor.fetchall()


def test_real_pipeline_first_write_then_idempotent_replay_and_publish(pipeline):
    catalog, binding = pipeline
    source = SyntheticSource()
    executor = PipelineExecutor(catalog, {"core13": binding}, source_factory=lambda _: source)
    repository, first = submit(catalog)
    assert JobRunner(repository, executor).run(repository.claim("synthetic-worker"))["status"] == (
        "succeeded"
    )
    first_units = repository.units(first["job_id"])
    assert first_units[0]["result"]["counts"] == {
        "fetched": 3,
        "inserted": 3,
        "updated": 0,
        "unchanged": 0,
    }
    assert first_units[1]["result"]["selected"] == first_units[1]["result"]["written"] == 3
    original_cdm = query(binding.cdm, "SELECT row_to_json(mr) FROM cdm.mr ORDER BY patient_id")
    _, second = submit(catalog, repository=repository, key="synthetic-request-two")
    assert JobRunner(repository, executor).run(repository.claim("synthetic-worker"))["status"] == (
        "succeeded"
    )
    second_units = repository.units(second["job_id"])
    assert second_units[0]["result"]["counts"] == {
        "fetched": 3,
        "inserted": 0,
        "updated": 0,
        "unchanged": 3,
    }
    assert second_units[1]["result"]["written"] == 0
    assert source.query_calls == 2 and source.closed
    assert (
        query(binding.cdm, "SELECT row_to_json(mr) FROM cdm.mr ORDER BY patient_id") == original_cdm
    )
    assert query(binding.ingest, "SELECT count(*) FROM cache_raw.source_record") == [(3,)]
    assert query(binding.ingest, "SELECT count(*) FROM cache_raw.source_record_version") == [(3,)]
    assert query(binding.ingest, "SELECT count(*) FROM sync_ops.sync_checkpoint") == [(0,)]
    assert query(
        binding.ingest, "SELECT status,count(*) FROM sync_ops.sync_batch GROUP BY status"
    ) == [("succeeded", 2)]
    assert query(binding.ingest, "SELECT count(*) FROM sync_ops.publish_lineage") == [(6,)]
    for job in (first, second):
        for unit in repository.units(job["job_id"]):
            table = (
                "sync_ops.sync_batch" if unit["phase"] == "extract" else "sync_ops.publish_batch"
            )
            key = "batch_id" if unit["phase"] == "extract" else "publish_batch_id"
            evidence = query(
                binding.ingest,
                f"SELECT evidence_version FROM {table} WHERE {key}=%s",
                (unit["result"][key],),
            )[0][0]
            assert f";job:{job['job_id']};unit:{unit['unit_id']};attempt:" in evidence


def test_real_fetch_failure_rolls_back_previously_written_chunk_and_keeps_audit(pipeline):
    catalog, binding = pipeline
    source = SyntheticSource(fail_fetch=True)
    executor = PipelineExecutor(catalog, {"core13": binding}, source_factory=lambda _: source)
    repository, job = submit(catalog)
    assert (
        JobRunner(repository, executor).run(repository.claim("synthetic-worker"))["status"]
        == "failed"
    )
    units = repository.units(job["job_id"])
    assert units[0]["status"] == "failed" and units[1]["status"] == "queued"
    assert units[0]["result"]["batch_id"] == 1
    for table in (
        "cache_raw.source_record",
        "cache_raw.source_record_version",
        "sync_ops.source_schema",
        "sync_ops.sync_checkpoint",
        "sync_ops.publish_batch",
    ):
        assert query(binding.ingest, f"SELECT count(*) FROM {table}") == [(0,)]
    assert query(
        binding.ingest, "SELECT batch_id,status,error_location FROM sync_ops.sync_batch"
    ) == [(1, "failed", "synthetic_fetch_fault")]
    assert query(binding.cdm, "SELECT count(*) FROM cdm.mr") == [(0,)]


def test_real_publish_failure_rolls_back_and_retry_only_publishes(pipeline):
    catalog, binding = pipeline
    source = SyntheticSource()
    failing = PipelineExecutor(
        catalog,
        {"core13": binding},
        source_factory=lambda _: source,
        cdm_factory=FailAfterRealCdmWrite,
    )
    repository, job = submit(catalog)
    assert (
        JobRunner(repository, failing).run(repository.claim("synthetic-worker"))["status"]
        == "failed"
    )
    units = repository.units(job["job_id"])
    assert [unit["status"] for unit in units] == ["succeeded", "failed"]
    assert units[1]["result"]["publish_batch_id"] == 1
    assert query(binding.cdm, "SELECT count(*) FROM cdm.mr") == [(0,)]
    assert query(binding.ingest, "SELECT count(*) FROM sync_ops.publish_lineage") == [(0,)]
    assert query(binding.ingest, "SELECT status,error_location FROM sync_ops.publish_batch") == [
        ("failed", "synthetic_write_fault")
    ]
    assert query(binding.ingest, "SELECT count(*) FROM cache_raw.source_record") == [(3,)]
    forbidden_source = Mock(side_effect=AssertionError("successful extraction must not repeat"))
    recovered = PipelineExecutor(catalog, {"core13": binding}, source_factory=forbidden_source)
    repository.retry(job["job_id"], "synthetic-operator")
    assert JobRunner(repository, recovered).run(repository.claim("synthetic-worker-two"))[
        "status"
    ] == ("succeeded")
    forbidden_source.assert_not_called()
    assert source.query_calls == 1
    assert query(binding.cdm, "SELECT count(*) FROM cdm.mr") == [(3,)]
    assert query(binding.ingest, "SELECT count(*) FROM sync_ops.sync_batch") == [(1,)]
    assert query(binding.ingest, "SELECT count(*) FROM sync_ops.publish_lineage") == [(3,)]
    assert query(
        binding.ingest, "SELECT status FROM sync_ops.publish_batch ORDER BY publish_batch_id"
    ) == [("failed",), ("succeeded",)]
