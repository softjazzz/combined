"""PostgreSQL-only checks for the task sync/QC execution fence.

Run with MEDQC_PG_RACE_NONPROD_DB=medqc_v36_validation_20260924 and
--noconftest. These tests never connect to the business database or source.
"""

import asyncio
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool


TARGET_DB = "medqc_v36_validation_20260924"
TARGET_REVISION = "20260924_000051"
LOCK_KEY = 5373186903776294821


@pytest.fixture
def pg_engine():
    if os.getenv("MEDQC_PG_RACE_NONPROD_DB") != TARGET_DB:
        pytest.skip("explicit non-production database opt-in required")
    env_path = Path(__file__).resolve().parents[2] / ".env"
    raw_url = next(
        (line.split("=", 1)[1].strip().strip("\"'") for line in env_path.read_text(encoding="utf-8").splitlines()
         if line.startswith("DATABASE_URL=")),
        "",
    )
    if not raw_url:
        pytest.skip("backend/.env has no PostgreSQL connection")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("PostgreSQL is required")
    engine = create_engine(url.set(database=TARGET_DB), poolclass=NullPool, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == TARGET_DB
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == TARGET_REVISION
        yield engine
    finally:
        engine.dispose()


def test_shared_qc_lock_blocks_exclusive_sync_until_all_readers_release(pg_engine):
    with pg_engine.connect() as qc_one, pg_engine.connect() as qc_two, pg_engine.connect() as sync:
        assert qc_one.execute(text("SELECT pg_try_advisory_lock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert qc_two.execute(text("SELECT pg_try_advisory_lock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
        try:
            assert not sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
            assert qc_one.execute(text("SELECT pg_advisory_unlock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
            assert not sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        finally:
            qc_two.execute(text("SELECT pg_advisory_unlock_shared(:key)"), {"key": LOCK_KEY})
        assert sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        try:
            assert not qc_one.execute(text("SELECT pg_try_advisory_lock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
        finally:
            assert sync.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert qc_one.execute(text("SELECT pg_try_advisory_lock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert qc_one.execute(text("SELECT pg_advisory_unlock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()


def test_session_lock_is_released_when_owner_connection_fails(pg_engine):
    owner = pg_engine.connect()
    try:
        assert owner.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        with pg_engine.connect() as other:
            assert not other.execute(text("SELECT pg_try_advisory_lock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
        raise RuntimeError("synthetic worker failure")
    except RuntimeError:
        owner.close()
    with pg_engine.connect() as next_worker:
        assert next_worker.execute(text("SELECT pg_try_advisory_lock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert next_worker.execute(text("SELECT pg_advisory_unlock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()


def test_qc_worker_lock_entry_blocks_sync_lock(pg_engine, monkeypatch):
    from app.routers import qc_sichuan
    from app.services import task_record_sync_job_service as jobs

    assert jobs._GLOBAL_LOCK_KEY == LOCK_KEY
    monkeypatch.setattr(qc_sichuan, "SessionLocal", sessionmaker(bind=pg_engine))
    monkeypatch.setattr(jobs, "_schedule_next", lambda _factory: None)
    lock = qc_sichuan._acquire_cdm_read_lock()
    assert lock is not None
    try:
        with pg_engine.connect() as sync:
            assert not sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
    finally:
        qc_sichuan._release_cdm_read_lock(lock)
    with pg_engine.connect() as sync:
        assert sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert sync.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}).scalar_one()


def test_qc_worker_holds_read_lock_through_batch_execution(pg_engine, monkeypatch):
    from app.routers import qc_sichuan
    from app.services import task_record_sync_job_service as jobs
    from app.services.qc_diagnostics import support_store

    class FakeWorkspace:
        def get_batch_job_for_processing(self, *, job_id):
            assert job_id == "synthetic-qc-job"
            return {"status": "running", "scope": "running", "filters": {}}

    entered = asyncio.Event()
    finish = asyncio.Event()

    async def paused_worker(*_args, **_kwargs):
        entered.set()
        await finish.wait()

    monkeypatch.setattr(qc_sichuan, "SessionLocal", sessionmaker(bind=pg_engine))
    monkeypatch.setattr(qc_sichuan, "_sichuan_workspace_service", lambda: FakeWorkspace())
    monkeypatch.setattr(qc_sichuan, "_validate_task_job_after_cdm_lock", lambda *_args: None)
    monkeypatch.setattr(qc_sichuan, "run_sichuan_workspace_batch_job", paused_worker)
    monkeypatch.setattr(support_store, "capture_for_job", lambda *_args: None)
    monkeypatch.setattr(jobs, "_schedule_next", lambda _factory: None)

    async def exercise():
        worker = asyncio.create_task(qc_sichuan._run_sichuan_workspace_batch_job("synthetic-qc-job"))
        try:
            await asyncio.wait_for(entered.wait(), 10)
            with pg_engine.connect() as sync:
                assert not sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        finally:
            finish.set()
            await asyncio.wait_for(worker, 10)

    asyncio.run(exercise())
    with pg_engine.connect() as sync:
        assert sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert sync.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}).scalar_one()


def test_full_etl_entry_does_no_work_during_qc_read_and_releases_on_failure(pg_engine, monkeypatch):
    from app.services import etl_sync

    calls = {"state_write": 0, "source": 0}

    def state_write(_state):
        calls["state_write"] += 1

    def missing_source():
        calls["source"] += 1
        return None

    monkeypatch.setattr(etl_sync, "engine", pg_engine)
    monkeypatch.setattr(etl_sync, "_upsert_sync_job_state", state_write)
    monkeypatch.setattr(etl_sync, "get_remote_db_url", missing_source)
    with pg_engine.connect() as qc:
        assert qc.execute(text("SELECT pg_try_advisory_lock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
        try:
            assert etl_sync.run_sync() == {"success": False, "error": "同步正在进行中，请稍后再试"}
            assert calls == {"state_write": 0, "source": 0}
        finally:
            assert qc.execute(text("SELECT pg_advisory_unlock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
    result = etl_sync.run_sync()
    assert result == {"success": False, "error": "REMOTE_DB_URL 未配置"}
    assert calls["state_write"] >= 1
    assert calls["source"] == 1
    with pg_engine.connect() as next_sync:
        assert next_sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert next_sync.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}).scalar_one()

    def broken_source():
        raise RuntimeError("synthetic source setup failure")

    monkeypatch.setattr(etl_sync, "get_remote_db_url", broken_source)
    with pytest.raises(RuntimeError, match="synthetic source setup failure"):
        etl_sync.run_sync()
    with pg_engine.connect() as next_sync:
        assert next_sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert next_sync.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}).scalar_one()


def test_sample_pool_entry_does_no_sync_during_qc_read_and_releases_on_failure(pg_engine, monkeypatch):
    from app.routers import qc_sample_pools

    class FakeService:
        def __init__(self):
            self.calls = []
            self.fail_source = False

        def get_sync_job(self, *, job_id):
            assert job_id == "synthetic-sample-job"
            return {"pool_id": "synthetic-pool", "payload": {}}

        def fail_sync_job(self, *, job_id, error_message):
            self.calls.append(("failed", job_id, error_message))

        def mark_sync_job_running(self, *, job_id):
            self.calls.append(("running", job_id))

        def sync_pool_records(self, **_kwargs):
            self.calls.append(("sync",))
            if self.fail_source:
                raise RuntimeError("synthetic source failure")
            return {"synthetic": True}

        def finish_sync_job(self, *, job_id, summary):
            self.calls.append(("finished", job_id, summary))

    service = FakeService()
    monkeypatch.setattr(qc_sample_pools, "SessionLocal", sessionmaker(bind=pg_engine))
    monkeypatch.setattr(qc_sample_pools, "_service", lambda: service)
    with pg_engine.connect() as qc:
        assert qc.execute(text("SELECT pg_try_advisory_lock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
        try:
            qc_sample_pools._run_sample_pool_sync_job("synthetic-sample-job")
            assert [call[0] for call in service.calls] == ["failed"]
            assert "资源忙" in service.calls[0][2]
        finally:
            assert qc.execute(text("SELECT pg_advisory_unlock_shared(:key)"), {"key": LOCK_KEY}).scalar_one()
    qc_sample_pools._run_sample_pool_sync_job("synthetic-sample-job")
    assert [call[0] for call in service.calls[1:]] == ["running", "sync", "finished"]
    service.fail_source = True
    qc_sample_pools._run_sample_pool_sync_job("synthetic-sample-job")
    assert [call[0] for call in service.calls[-3:]] == ["running", "sync", "failed"]
    with pg_engine.connect() as next_sync:
        assert next_sync.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar_one()
        assert next_sync.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY}).scalar_one()


def test_committed_bundle_invalidation_rejects_old_policy_receipt(pg_engine, monkeypatch):
    from app.services import task_record_sync_service as sync

    marker = uuid.uuid4().hex
    identity = {"institute_id": "SYNTH_PG_RACE", "patient_id": f"SYNTH_{marker}",
                "visit_id": f"SYNTH_{marker}"}
    cleanup_tables = (
        "running_record_bundle", "final_record_bundle", "admission_domain_bundle",
        "course_domain_bundle", "surgery_domain_bundle", "consult_discussion_domain_bundle",
        "terminal_domain_bundle", "index_coding_settlement_domain_bundle",
    )
    try:
        with pg_engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO public.running_record_bundle
                    (institute_id, patient_id, visit_id, scene, bundle_schema_version,
                     policy_version, medical_text, text_available)
                VALUES (:institute_id, :patient_id, :visit_id, 'running',
                        'bundle-v6', :policy_version, 'synthetic test only', true)
            """), {**identity, "policy_version": sync.CONTRACT_VERSION})
        with pg_engine.connect() as reader:
            before = reader.execute(text("""
                SELECT policy_version, bundle_updated_at FROM public.running_record_bundle
                WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
            """), identity).mappings().one()
            old_receipt_policy = before["policy_version"]
            old_receipt_time = before["bundle_updated_at"]
        monkeypatch.setattr(sync, "SessionLocal", sessionmaker(bind=pg_engine))
        sync._invalidate_existing_bundles("running", [sync.CaseRef(**identity)])
        with pg_engine.connect() as reader:
            after = reader.execute(text("""
                SELECT policy_version, bundle_updated_at FROM public.running_record_bundle
                WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
            """), identity).mappings().one()
        assert after["policy_version"] == sync.INVALIDATED_POLICY_VERSION
        assert after["policy_version"] != old_receipt_policy
        assert after["bundle_updated_at"] == old_receipt_time
    finally:
        with pg_engine.begin() as conn:
            for table in cleanup_tables:
                conn.execute(text(f"""
                    DELETE FROM public.{table}
                    WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
                """), identity)
