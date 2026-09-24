"""Large saved task sets retain one fence and one complete receipt."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.services import task_record_sync_service as service
from app.services import task_record_sync_job_service as jobs
from app.services.case_identity import CaseRef


def _records(size: int) -> list[tuple[str, CaseRef]]:
    return [
        (f"record-{index:05d}", CaseRef("hospital", f"patient-{index:05d}", f"visit-{index:05d}"))
        for index in range(size)
    ]


def _refresh(count: int) -> dict:
    value = {"updated": count, "processed": count, "failed": 0}
    return {
        "scenes": {name: value for name in ("running", "final")},
        "domains": {
            name.removesuffix("_domain_bundle"): value
            for name in service._BUNDLE_TABLES[2:]
        },
    }


def test_saved_task_snapshot_accepts_501_distinct_case_refs():
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    records = _records(501)
    try:
        with factory.begin() as session:
            session.execute(QCTask.__table__.insert().values(
                id="task", task_number="TASK-501", task_name="批量任务", task_type="one_time",
                scene="running", creator_id="owner", status="sampling", total_records=501,
            ))
            session.execute(QCTaskRecord.__table__.insert(), [
                {"id": record_id, "task_id": "task", "record_id": record_id, **ref.as_dict()}
                for record_id, ref in records
            ])
        with factory() as session:
            assert service.load_task_refs_in_session(session, "task", "owner", False) == ("running", records)
    finally:
        engine.dispose()


def test_async_job_preserves_501_record_snapshot_and_receipt():
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS qc")
        connection.exec_driver_sql("""
            CREATE TABLE qc.qc_async_jobs (
                id TEXT PRIMARY KEY, job_number TEXT NOT NULL UNIQUE,
                job_type TEXT, business_type TEXT, business_id TEXT, source_module TEXT,
                priority INTEGER, status TEXT, queue_name TEXT, requested_by TEXT,
                payload TEXT, result_summary TEXT, progress_pct REAL,
                attempt_count INTEGER, max_attempts INTEGER, next_retry_at TIMESTAMP,
                accepted_at TIMESTAMP, queued_at TIMESTAMP, started_at TIMESTAMP,
                finished_at TIMESTAMP, last_heartbeat_at TIMESTAMP,
                created_at TIMESTAMP, updated_at TIMESTAMP,
                error_code TEXT, error_message TEXT
            )
        """)
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    records = _records(501)
    try:
        with factory.begin() as session:
            session.execute(QCTask.__table__.insert().values(
                id="task", task_number="TASK-501", task_name="批量任务", task_type="one_time",
                scene="running", creator_id="owner", status="sampling", total_records=501,
            ))
            session.execute(QCTaskRecord.__table__.insert(), [
                {"id": record_id, "task_id": "task", "record_id": record_id, **ref.as_dict()}
                for record_id, ref in records
            ])
        queued = jobs.enqueue_task_record_sync(
            task_id="task", actor_id="owner", session_factory=factory,
            dispatch=lambda job_id: None,
        )

        def sync_func(**kwargs):
            assert len(kwargs["expected_records"]) == 501
            return {
                "contract_version": service.CONTRACT_VERSION,
                "task_id": "task", "total": 501, "ready_count": 501, "failed_count": 0,
                "records": [
                    {"task_record_id": record_id, "status": "ready",
                     "bundle_schema_version": service.BUNDLE_SCHEMA_VERSION_CURRENT,
                     "policy_version": service.CONTRACT_VERSION,
                     "bundle_updated_at": "2026-09-24T00:00:00.000000+00:00"}
                    for record_id, _ in records
                ],
            }

        jobs.run_task_record_sync_job(
            queued["job_id"], session_factory=factory, sync_func=sync_func,
        )
        receipt = jobs.get_task_record_sync_job(
            task_id="task", job_id=queued["job_id"], actor_id="owner",
            session_factory=factory,
        )
        assert (receipt["status"], receipt["total"], receipt["ready_count"]) == ("completed", 501, 501)
        assert [item["task_record_id"] for item in receipt["records"]] == [record_id for record_id, _ in records]
    finally:
        engine.dispose()


@pytest.mark.parametrize("size,expected_batches", [(101, 1), (500, 1), (501, 2), (1001, 3)])
def test_large_task_publishes_once_with_complete_ordered_receipt(monkeypatch, size, expected_batches):
    records = _records(size)
    events = []
    calls = []
    monkeypatch.setattr(service, "_load_task_refs", lambda *_: ("running", records))
    monkeypatch.setattr(service, "_table_names", lambda: ["inpat_registration", "admission_record"])
    monkeypatch.setattr(service, "_invalidate_existing_bundles", lambda scene, refs: events.append(("invalidate", tuple(refs))))
    monkeypatch.setattr(service, "_publish_refreshed_bundles", lambda refs, token: events.append(("publish", tuple(refs), token)))

    class Syncer:
        def sync_case_set(self, **kwargs):
            calls.append(kwargs)
            events.append(("sync", tuple(kwargs["case_refs"])))
            assert events[0] == ("invalidate", tuple(ref for _, ref in records))
            return SimpleNamespace(
                visible_case_refs=tuple(kwargs["case_refs"]),
                synced_tables=tuple({"table_name": name, "sync_status": "synced"} for name in kwargs["table_names"]),
                bundle_refresh=_refresh(len(kwargs["case_refs"])),
            )

    receipt = service.sync_task_records(
        task_id="task", actor_id="owner", sync_factory=Syncer,
        readiness_checker=lambda scene, refs: set(refs),
        expected_records=[{
            "task_record_id": record_id, **ref.as_dict(),
        } for record_id, ref in records],
    )
    assert [len(call["case_refs"]) for call in calls] == [
        min(500, size - start) for start in range(0, size, 500)
    ]
    assert len(calls) == expected_batches
    assert len({call["bundle_policy_version"] for call in calls}) == 1
    assert events[-1] == ("publish", tuple(ref for _, ref in records), calls[0]["bundle_policy_version"])
    assert [event[0] for event in events] == ["invalidate", *(["sync"] * expected_batches), "publish"]
    assert (receipt["total"], receipt["ready_count"], receipt["failed_count"]) == (size, size, 0)
    assert [row["task_record_id"] for row in receipt["records"]] == [record_id for record_id, _ in records]


@pytest.mark.parametrize("failure", ["exception", "missing_table", "foreign_ref", "duplicate_ref", "duplicate_table"])
def test_later_batch_failure_never_publishes_partial_task(monkeypatch, failure):
    records = _records(501)
    events = []
    monkeypatch.setattr(service, "_load_task_refs", lambda *_: ("running", records))
    monkeypatch.setattr(service, "_table_names", lambda: ["inpat_registration", "admission_record"])
    monkeypatch.setattr(service, "_invalidate_existing_bundles", lambda scene, refs: events.append("invalidate"))
    monkeypatch.setattr(service, "_publish_refreshed_bundles", lambda refs, token: events.append("publish"))

    class Syncer:
        def sync_case_set(self, **kwargs):
            events.append("sync")
            batch = list(kwargs["case_refs"])
            if len(batch) == 1 and failure == "exception":
                raise TimeoutError("second batch failed")
            if len(batch) == 1 and failure == "foreign_ref":
                batch = [records[0][1]]
            if len(batch) == 1 and failure == "duplicate_ref":
                batch = batch * 2
            statuses = tuple(
                {"table_name": name, "sync_status": (
                    "source_table_unavailable" if len(kwargs["case_refs"]) == 1
                    and failure == "missing_table" and name == "admission_record" else "synced"
                )}
                for name in kwargs["table_names"]
            )
            if len(batch) == 1 and failure == "duplicate_table":
                statuses += (statuses[0],)
            return SimpleNamespace(
                visible_case_refs=tuple(batch), synced_tables=statuses,
                bundle_refresh=_refresh(len(batch)),
            )

    if failure in {"exception", "foreign_ref", "duplicate_ref", "duplicate_table"}:
        with pytest.raises(RuntimeError, match="可重试"):
            service.sync_task_records(task_id="task", actor_id="owner", sync_factory=Syncer)
    else:
        receipt = service.sync_task_records(
            task_id="task", actor_id="owner", sync_factory=Syncer,
            readiness_checker=lambda *_: pytest.fail("incomplete task cannot be ready"),
        )
        assert receipt["ready_count"] == 0
        assert receipt["failed_count"] == 501
        assert len(receipt["records"]) == 501
    assert events == ["invalidate", "sync", "sync"]


def test_missing_primary_in_later_batch_keeps_record_level_receipt(monkeypatch):
    records = _records(501)
    published = []
    monkeypatch.setattr(service, "_load_task_refs", lambda *_: ("running", records))
    monkeypatch.setattr(service, "_table_names", lambda: ["inpat_registration"])
    monkeypatch.setattr(service, "_invalidate_existing_bundles", lambda *_: None)
    monkeypatch.setattr(service, "_publish_refreshed_bundles", lambda refs, token: published.extend(refs))

    class Syncer:
        def sync_case_set(self, **kwargs):
            visible = kwargs["case_refs"] if len(kwargs["case_refs"]) == 500 else []
            return SimpleNamespace(
                visible_case_refs=tuple(visible),
                synced_tables=({"table_name": "inpat_registration", "sync_status": "synced"},),
                bundle_refresh=_refresh(len(visible)),
            )

    receipt = service.sync_task_records(
        task_id="task", actor_id="owner", sync_factory=Syncer,
        readiness_checker=lambda scene, refs: set(refs),
    )
    assert published == [ref for _, ref in records[:500]]
    assert (receipt["ready_count"], receipt["failed_count"]) == (500, 1)
    assert receipt["records"][-1]["reason_code"] == "source_primary_missing"


def test_readiness_queries_are_bounded(monkeypatch):
    refs = [ref for _, ref in _records(1001)]
    calls = []

    class Repo:
        def __init__(self, **kwargs):
            pass

        def collect_records(self, **kwargs):
            calls.append(kwargs["record_refs"])
            return []

    monkeypatch.setattr(service, "SessionLocal", object())
    monkeypatch.setattr(service, "RecordRepository", Repo)
    assert service._ready_refs("running", refs) == {}
    assert [len(batch) for batch in calls] == [500, 500, 1]
    assert [ref for batch in calls for ref in batch] == refs
