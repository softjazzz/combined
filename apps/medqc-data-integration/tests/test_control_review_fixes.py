"""复审反例：仅合成配置、内存控制仓储及固定应答。"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from test_control_pipeline import binding
from test_job_runner import FakeExecutor, queued_job

from medqc_ingest.control.pipeline import PipelineExecutor
from medqc_ingest.control.profiles import ProfileCatalog
from medqc_ingest.control.runner import JobRunner, UnitFailure
from medqc_ingest.domain import IngestError, _project_value


def identity_executor(database="synthetic-A"):
    value = binding()
    value = replace(value, ingest=replace(value.ingest, database=database))
    return PipelineExecutor(ProfileCatalog(), {"core13": value})


def test_identity_is_stable_and_excludes_secret_file_rotation():
    _, job = queued_job()
    executor = identity_executor()
    identity = executor.execution_identity(job)
    original = executor.bindings["core13"]
    executor.bindings["core13"] = replace(
        original,
        source=replace(original.source, password_file=Path("new-secret-file")),
        ingest=replace(original.ingest, password_file=Path("new-passfile")),
    )
    assert executor.execution_identity(job) == identity
    assert len(identity) == 67 and "synthetic-A" not in identity
    assert identity_executor("synthetic-B").execution_identity(job) != identity


@pytest.mark.parametrize(
    "part,field,value",
    [
        ("source", "namespace", "different_namespace"),
        ("cdm", "database", "different_cdm"),
    ],
)
def test_identity_changes_with_data_scope(part, field, value):
    _, job = queued_job()
    executor = identity_executor()
    previous = executor.execution_identity(job)
    original = executor.bindings["core13"]
    executor.bindings["core13"] = replace(
        original, **{part: replace(getattr(original, part), **{field: value})}
    )
    assert executor.execution_identity(job) != previous


def test_changed_binding_cannot_reuse_completed_extract_or_publish_other_raw():
    repo, job = queued_job()
    identity = identity_executor().execution_identity(job)

    def first(_job, unit):
        if unit["phase"] == "publish":
            raise UnitFailure("pipeline_failed", "synthetic_publish", result={"code": "failed"})
        return {"batch_id": 71}

    original = FakeExecutor(first)
    original.execution_identity = lambda _job, stable=identity: stable
    assert JobRunner(repo, original).run(repo.claim("worker-A"))["status"] == "failed"
    repo.retry(job["job_id"], "operator")
    assert (
        JobRunner(repo, identity_executor("synthetic-B")).run(repo.claim("worker-B"))["status"]
        == "recovery_required"
    )
    assert repo.get_job(job["job_id"])["status"] == "recovery_required"
    assert [
        u["result"]["batch_id"] for u in repo.units(job["job_id"]) if u["phase"] == "extract"
    ] == [71] * 3
    assert repo.units(job["job_id"])[-1]["status"] == "queued"


def test_same_binding_retries_only_publish_and_legacy_completed_requires_recovery():
    for legacy in (False, True):
        repo, job = queued_job()
        identity = identity_executor().execution_identity(job)

        def fail_publish(_job, unit):
            if unit["phase"] == "publish":
                raise UnitFailure("pipeline_failed", "synthetic_publish", result={"code": "failed"})
            return {"batch_id": 71}

        first = FakeExecutor(fail_publish)
        if not legacy:
            first.execution_identity = lambda _job, stable=identity: stable
        JobRunner(repo, first).run(repo.claim("worker-A"))
        repo.retry(job["job_id"], "operator")
        second = FakeExecutor()
        second.execution_identity = lambda _job, stable=identity: stable
        result = JobRunner(repo, second).run(repo.claim("worker-B"))
        assert result["status"] == ("recovery_required" if legacy else "succeeded")
        assert len(second.calls) == (0 if legacy else 1)


def test_retry_intent_is_atomic_with_failure_even_before_supervisor_observes_exit():
    repo, job = queued_job()
    now = [datetime(2026, 11, 1, tzinfo=timezone.utc)]
    repo.clock = lambda: now[0]
    claimed = repo.claim("first")
    assert repo.finish_job(
        job["job_id"],
        claimed["lease_token"],
        "failed",
        {"error_kind": "source_connect_error", "sqlstate": "08001"},
    )
    assert repo.get_job(job["job_id"])["next_retry_at"] is not None
    assert repo.claim("restart") is None
    now[0] += timedelta(seconds=31)
    retried = repo.claim("restart")
    assert retried["job_id"] == job["job_id"] and retried["attempt_count"] == 2
    assert repo.claim("another") is None
    assert not repo.finish_job(job["job_id"], claimed["lease_token"], "succeeded")


@pytest.mark.parametrize("action", ["cancel", "manual", "recover"])
def test_retry_intent_obeys_cancel_manual_retry_and_recovery(action):
    repo, job = queued_job()
    now = [datetime(2026, 11, 1, tzinfo=timezone.utc)]
    repo.clock = lambda: now[0]
    claimed = repo.claim("first")
    if action == "recover":
        repo.mark_recovery(job["job_id"], claimed["lease_token"], "commit_unknown")
    else:
        repo.finish_job(
            job["job_id"],
            claimed["lease_token"],
            "failed",
            {"error_kind": "source_connect_error", "sqlstate": "08001"},
        )
        if action == "cancel":
            repo.cancel(job["job_id"], "operator")
        else:
            repo.retry(job["job_id"], "operator")
    now[0] += timedelta(seconds=200)
    assert (repo.claim("restart") is not None) is (action == "manual")


@pytest.mark.parametrize("target", ["datetime", "timestamptz"])
def test_date_only_never_becomes_precise_midnight(target):
    with pytest.raises(IngestError, match="datetime_precision_missing"):
        _project_value("2026-06-06", target)
    assert _project_value("2026-06-06 00:00:00", target).hour == 0
    assert _project_value(None, target) is None
    assert _project_value("2026-06-06T00:00:00+08:00", target) == _project_value(
        "2026-06-05T16:00:00Z", target
    )
    assert str(_project_value("2026-06-06", "date")) == "2026-06-06"


@pytest.mark.parametrize("upgraded", [False, True])
def test_connection_checks_002_before_ready_or_admission(upgraded):
    from unittest.mock import MagicMock, patch

    from medqc_ingest.config import PassfilePostgresSettings
    from medqc_ingest.control.models import ControlError
    from medqc_ingest.control.postgres import PostgresJobRepository

    settings = PassfilePostgresSettings(
        "127.0.0.1", 5432, "medqc_sync_control", "medqc_job_api", Path("unused")
    )
    repo = PostgresJobRepository(settings)
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (settings.database, settings.user, settings.user, "on")
    cursor.fetchall.return_value = (
        [("binding_identity", "character varying"), ("next_retry_at", "timestamp with time zone")]
        if upgraded
        else []
    )
    driver = MagicMock()
    driver.connect.return_value = connection
    with (
        patch("medqc_ingest.control.postgres.importlib.import_module", return_value=driver),
        patch.object(PassfilePostgresSettings, "connection_kwargs", return_value={}),
    ):
        if upgraded:
            assert repo._connect(True) is connection
        else:
            with pytest.raises(ControlError) as error:
                repo._connect(True)
            assert error.value.code == "migration_required"
            connection.close.assert_called_once()


def test_explicit_001_upgrade_is_transactional_and_packaged():
    from unittest.mock import MagicMock

    from medqc_ingest.control.postgres import upgrade_control_reliability

    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [("medqc_sync_control", "off"), (False,) * 6]
    cursor.fetchall.return_value = [
        (name,) for name in ("job", "job_unit", "job_attempt", "schedule", "schedule_fire", "event")
    ]
    upgrade_control_reliability(connection, "medqc_sync_control")
    sql = "\n".join(call.args[0] for call in cursor.execute.call_args_list)
    assert "ADD COLUMN binding_identity" in sql and "ADD COLUMN next_retry_at" in sql
    assert "DROP " not in sql and "001_job_control" not in sql
    connection.commit.assert_called_once()
    root = Path(__file__).resolve().parents[1]
    for filename in ("pyproject.toml", "tools/build_sync_control_package.py"):
        assert "002_execution_identity_retry.sql" in (root / filename).read_text(encoding="utf-8")
    cursor.fetchone.side_effect = [("other", "off")]
    from medqc_ingest.control.models import ControlError

    with pytest.raises(ControlError):
        upgrade_control_reliability(connection, "medqc_sync_control")
    connection.rollback.assert_called_once()


@pytest.mark.parametrize("schema", ["public", "cdm"])
def test_application_merge_validates_both_parents_and_physical_columns(schema):
    import importlib.util
    from unittest.mock import MagicMock

    import sqlalchemy as sa
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[2] / "medqc-web/backend/alembic"
    script = ScriptDirectory(str(root))
    # 应用最新head已前移；062合并点的双父链及下方物理字段负例必须保留。
    assert script.get_heads() == ["20261106_000064"]
    assert script.get_revision("20261106_000064").down_revision == "20261105_000063"
    assert script.get_revision("20261105_000063").down_revision == "20261102_000062"
    assert set(script.get_revision("20261102_000062").down_revision) == {
        "20261102_000060", "20261102_000061"
    }
    ancestors = {r.revision for r in script.walk_revisions()}
    assert {"20261101_000058", "20261030_000057"} <= ancestors
    spec = importlib.util.spec_from_file_location(
        "sync_merge", root / "versions/20261102_000060_sync_mq_heads.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tables = {}

    def typed(kind):
        return {
            "text": sa.Text(),
            "varchar": sa.String(100),
            "datetime": sa.DateTime(False),
            "timestamptz": sa.DateTime(True),
            "int": sa.Integer(),
            "bytes": sa.LargeBinary(),
            "aware": sa.DateTime(True),
        }[kind]

    for table, name, kind in module.FIELDS:
        tables.setdefault(table, []).append(
            {"name": name, "type": typed(kind), "nullable": True, "default": None}
        )
    tables["epidemic_record"] = [
        {"name": name, "type": typed(kind), "nullable": nullable, "default": None}
        for name, kind, nullable in module.EPIDEMIC_FIELDS
    ]
    for table, fields in module.MQ_REQUIRED.items():
        tables[table] = [
            {"name": name, "type": typed(kind), "nullable": False, "default": None}
            for name, kind in fields.items()
        ]
    inspector = MagicMock()
    inspector.has_table.side_effect = lambda table, **kw: table in tables
    inspector.get_columns.side_effect = lambda table, **kw: tables[table]
    inspector.get_pk_constraint.side_effect = lambda table, **kw: {
        "constrained_columns": ["institute_id", "patient_id", "visit_id", "document_id"]
        if table == "epidemic_record"
        else ["job_id"]
        if table == "qc_batch_dispatches"
        else ["id"]
    }
    module.validate_schema(inspector, cdm_schema=schema, qc_schema="qc")
    tables["daily_course_record"][0]["type"] = sa.Date()
    with pytest.raises(RuntimeError, match="cdm_field_mismatch"):
        module.validate_schema(inspector, cdm_schema=schema, qc_schema="qc")
    tables["daily_course_record"][0]["type"] = sa.DateTime(False)
    del tables["qc_dispatch_outbox_archive"]
    with pytest.raises(RuntimeError, match="mq_table_missing"):
        module.validate_schema(inspector, cdm_schema=schema, qc_schema="qc")


def test_contract_change_and_scheduled_identity_are_bound_before_attempt_suffix(monkeypatch):
    import copy

    _, job = queued_job()
    executor = identity_executor()
    original = executor.execution_identity(job)
    scheduled = copy.deepcopy(job)
    scheduled.update(source="schedule", attempt_count=99, lease_token="new-attempt")
    assert executor.execution_identity(scheduled) == original
    resolve = executor.catalog.resolve_spec
    monkeypatch.setattr(
        executor.catalog,
        "resolve_spec",
        lambda profile, name: replace(
            resolve(profile, name), evidence_version="changed-contract-v2"
        ),
    )
    assert executor.execution_identity(job) != original


def test_durable_intent_survives_new_repository_and_exhausts_after_two_retries():
    import copy

    from medqc_ingest.control.memory import MemoryJobRepository

    repo, job = queued_job()
    now = [datetime(2026, 11, 1, tzinfo=timezone.utc)]
    repo.clock = lambda: now[0]
    for attempt in (1, 2, 3):
        claim = repo.claim("restarted-worker")
        assert claim["attempt_count"] == attempt
        repo.finish_job(
            job["job_id"],
            claim["lease_token"],
            "failed",
            {"error_kind": "source_connect_error", "sqlstate": "08001"},
        )
        # 仓储JSON快照模拟控制库重载；监督进程任何内存提示均未复制。
        restarted = MemoryJobRepository(clock=lambda: now[0])
        for name in ("jobs", "job_units", "attempts", "schedules", "fires"):
            setattr(restarted, name, copy.deepcopy(getattr(repo, name)))
        repo = restarted
        if attempt < 3:
            assert repo.claim("too-early") is None
        now[0] += timedelta(seconds=121)
    assert repo.get_job(job["job_id"])["next_retry_at"] is None
    assert repo.claim("budget-spent") is None
