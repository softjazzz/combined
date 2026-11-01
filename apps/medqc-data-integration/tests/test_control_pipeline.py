from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from medqc_ingest.config import PostgresSettings, SourceSettings, source_zone
from medqc_ingest.control.models import ControlError, SourceLimited
from medqc_ingest.control.pipeline import BoundedOdbcSource, PipelineBinding, PipelineExecutor
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.runner import UnitFailure
from medqc_ingest.domain import ErrorKind, IngestError
from medqc_ingest.service import PublishResult


def binding():
    pg = PostgresSettings("127.0.0.1", 1234, "fictional", "medqc_sync", Path("unused"))
    source = SourceSettings(
        "odbc",
        "fictional",
        1972,
        "fictional",
        "fictional",
        Path("unused"),
        "InterSystems ODBC35",
        None,
        None,
        (),
    )
    return PipelineBinding(source, pg, pg, 1)


def task(mode="replay", phase="extract", profile="core13", interface="web.mr"):
    return (
        {"job_id": str(uuid4()), "source": "manual", "request": {"profile": profile, "mode": mode}},
        {
            "unit_id": str(uuid4()),
            "interface_name": interface,
            "phase": phase,
            "source_date": "2026-10-26",
        },
    )


class FakeSource:
    def __init__(self, spec, error=None):
        self.spec, self.error, self.closed = spec, error, False

    def open(self):
        pass

    def query(self, spec, arguments):
        if self.error:
            try:
                raise RuntimeError("HY000", "fictional-private-source [Native Code 400]")
            except RuntimeError:
                raise IngestError(ErrorKind.SOURCE_QUERY, self.error) from None
        self.sent = False
        return self

    @property
    def columns(self):
        return self.spec.source_columns

    @property
    def source_types(self):
        return ("str",) * len(self.columns)

    def fetchmany(self, size):
        if self.sent:
            return []
        self.sent = True
        row = dict.fromkeys(self.columns)
        row.update({name: "fictional-" + name for name in self.spec.key_fields})
        return [tuple(row[name] for name in self.columns)]

    def close(self):
        self.closed = True


class FakeRepository:
    def __init__(self):
        self.evidence = None
        self.status = "failed"
        self.advanced = False
        self.fail_correlation = False

    def connect_control(self):
        pass

    def acquire_lock(self, scope):
        return True

    def release_lock(self, scope):
        pass

    def start_batch(self, interface, start, end, evidence):
        self.evidence = evidence
        self.status = "running"
        return 71

    def mark_batch_succeeded(self, batch_id, counts, checkpoint_state):
        self.status = "succeeded"

    def mark_batch_failed(self, batch_id, kind, location):
        self.status = "failed"

    def begin_data(self):
        pass

    def write_schema(self, *args):
        pass

    def upsert_raw(self, interface, schema, records, *args):
        return {"inserted": len(records), "updated": 0, "unchanged": 0}

    def advance_checkpoint(self, *args):
        self.advanced = True
        return True

    def commit_data(self):
        pass

    def rollback_data(self):
        pass

    def drop_data(self):
        pass

    def close(self):
        pass

    def failure_identity(self, interface, evidence, phase):
        if self.fail_correlation:
            raise RuntimeError("fictional-private-correlation-message")
        return 71, self.status


def test_dry_uses_real_extract_flow_without_pg_factories_or_password_read():
    catalog = ProfileCatalog()
    source = FakeSource(catalog.resolve_spec("core13", "web.mr"))
    executor = PipelineExecutor(
        catalog,
        {"core13": binding()},
        source_factory=lambda _: source,
        repository_factory=lambda *_: pytest.fail("no PG for dry"),
    )
    job, unit = task(mode="dry")
    result = executor.execute(job, unit)
    assert result["counts"]["fetched"] == 1 and result["batch_id"] is None
    assert source.closed


def test_replay_correlation_contains_exact_job_unit_and_per_attempt_uuid():
    catalog, repository = ProfileCatalog(), FakeRepository()
    source = FakeSource(catalog.resolve_spec("core13", "web.mr"))
    executor = PipelineExecutor(
        catalog,
        {"core13": binding()},
        source_factory=lambda _: source,
        repository_factory=lambda *_: repository,
    )
    job, unit = task()
    result = executor.execute(job, unit)
    assert result["batch_id"] == 71 and result["checkpoint_state"] == "held"
    assert f";job:{job['job_id']};unit:{unit['unit_id']};attempt:" in repository.evidence
    assert not repository.advanced


def test_publish_only_does_not_open_source_and_reuses_publish_service():
    repo = FakeRepository()
    executor = PipelineExecutor(
        ProfileCatalog(),
        {"core13": replace(binding(), source=None)},
        source_factory=lambda _: pytest.fail("no source for publish"),
        repository_factory=lambda *_: repo,
        cdm_factory=lambda _: object(),
    )
    with patch("medqc_ingest.control.pipeline.PublishService") as service:
        service.return_value.run.return_value = PublishResult(72, "a" * 64, 4, 0)
        result = executor.execute(*task(mode="publish_only", phase="publish"))
    assert result["publish_batch_id"] == 72 and result["selected"] == 4
    service.assert_called_once()


def test_incremental_cannot_skip_day_or_bootstrap_without_explicit_binding():
    calls = []
    for checkpoint in (None, datetime(2026, 10, 27, tzinfo=source_zone("Asia/Shanghai"))):
        executor = PipelineExecutor(
            ProfileCatalog(),
            {"core13": binding()},
            repository_factory=lambda *_: calls.append(1),
            checkpoint_reader=lambda *_, prior=checkpoint: prior,
        )
        with pytest.raises(ControlError) as error:
            executor.execute(*task(mode="incremental"))
        assert error.value.code == "checkpoint_gap"
    assert not calls


def test_incremental_contiguous_window_passes_and_advances_once():
    catalog, repo = ProfileCatalog(), FakeRepository()
    executor = PipelineExecutor(
        catalog,
        {"core13": binding()},
        source_factory=lambda _: FakeSource(catalog.resolve_spec("core13", "web.mr")),
        repository_factory=lambda *_: repo,
        checkpoint_reader=lambda *_: datetime(2026, 10, 26, tzinfo=source_zone("Asia/Shanghai")),
    )
    result = executor.execute(*task(mode="incremental"))
    assert result["checkpoint_state"] == "advanced" and repo.advanced
    assert replace(
        binding(), initial_incremental_start=date(2026, 10, 26)
    ).initial_incremental_start


def test_periop_known_query_failure_retains_exact_failed_batch_not_empty_success():
    catalog = ProfileCatalog({"periop13": {"enabled": True, "ready": True}})
    repo = FakeRepository()
    spec = catalog.resolve_spec("periop13", "web.blood_application")
    executor = PipelineExecutor(
        catalog,
        {"periop13": binding()},
        source_factory=lambda _: FakeSource(spec, "odbc_call"),
        repository_factory=lambda *_: repo,
    )
    job, unit = task(profile="periop13", interface=spec.name)
    unit["source_date"] = "2026-10-28"
    with pytest.raises(SourceLimited) as error:
        executor.execute(job, unit)
    assert error.value.result["batch_id"] == 71 and error.value.result["source_limited"]
    assert "fictional-private" not in str(error.value.result)


def test_correlation_unavailable_cannot_be_accepted_as_source_limitation():
    catalog = ProfileCatalog({"periop13": {"enabled": True, "ready": True}})
    repo = FakeRepository()
    repo.fail_correlation = True
    spec = catalog.resolve_spec("periop13", "web.blood_application")
    executor = PipelineExecutor(
        catalog,
        {"periop13": binding()},
        source_factory=lambda _: FakeSource(spec, "odbc_call"),
        repository_factory=lambda *_: repo,
    )
    job, unit = task(profile="periop13", interface=spec.name)
    unit["source_date"] = "2026-10-28"
    with pytest.raises(UnitFailure) as error:
        executor.execute(job, unit)
    assert error.value.recovery_required


def test_unknown_commit_is_recovery_even_if_audit_was_marked_failed():
    repo = FakeRepository()
    executor = PipelineExecutor(
        ProfileCatalog(), {"core13": binding()}, repository_factory=lambda *_: repo
    )
    with patch("medqc_ingest.control.pipeline.ExtractService") as service:
        service.return_value.run.side_effect = IngestError(ErrorKind.INGEST_WRITE, "commit_data")
        with pytest.raises(UnitFailure) as error:
            executor.execute(*task())
    assert error.value.recovery_required and error.value.result["batch_id"] == 71


def test_periop_not_ready_is_rejected_before_any_source_or_repository():
    executor = PipelineExecutor(
        ProfileCatalog(),
        {"periop13": binding()},
        repository_factory=lambda *_: pytest.fail("no repository"),
    )
    with pytest.raises(ControlError):
        executor.execute(*task(profile="periop13", interface="web.nursing_record"))


def test_worker_rechecks_full_source_date_before_opening_source_or_data_repository():
    executor = PipelineExecutor(
        ProfileCatalog(),
        {"core13": binding()},
        repository_factory=lambda *_: pytest.fail("no PG for future date"),
    )
    job, unit = task()
    unit["source_date"] = "2100-01-01"
    with pytest.raises(UnitFailure):
        executor.execute(job, unit)


def test_odbc_statement_timeout_is_set_after_connect_before_cursor_creation():
    connection = SimpleNamespace(timeout=0, closed=False)
    connection.close = lambda: setattr(connection, "closed", True)
    driver = SimpleNamespace(connect=lambda *args, **kwargs: connection)
    settings = binding().source
    with (
        patch("medqc_ingest.adapters.cache.importlib.import_module", return_value=driver),
        patch.object(SourceSettings, "password", return_value="fictional-unused-password"),
    ):
        source = BoundedOdbcSource(settings, 120)
        source.open()
        assert connection.timeout == 120
        source.close()
    assert connection.closed


def test_timeout_set_failure_closes_connected_driver_without_private_message():
    class Connection:
        closed = False

        @property
        def timeout(self):
            return 0

        @timeout.setter
        def timeout(self, value):
            raise RuntimeError("fictional-private-timeout-driver-message")

        def close(self):
            self.closed = True

    connection = Connection()
    driver = SimpleNamespace(connect=lambda *args, **kwargs: connection)
    with (
        patch("medqc_ingest.adapters.cache.importlib.import_module", return_value=driver),
        patch.object(SourceSettings, "password", return_value="fictional-unused-password"),
        pytest.raises(IngestError) as error,
    ):
        BoundedOdbcSource(binding().source, 120).open()
    assert connection.closed
    assert error.value.location == "control_odbc_timeout"
    assert "fictional-private" not in str(error.value)
