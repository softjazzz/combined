"""隔离 PostgreSQL 中验证任务 Bundle 标记与原子发布，不接触真实病例。"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.services import task_record_sync_service as sync
from app.services.bundles import assembly
from app.services.case_identity import CaseRef


TARGET_DB = "medqc_v36_validation_20260924"
TARGET_REVISION = "20260924_000051"
SCENE_TABLES = ("running_record_bundle", "final_record_bundle")
DOMAIN_TABLES = (
    "admission_domain_bundle", "course_domain_bundle", "surgery_domain_bundle",
    "consult_discussion_domain_bundle", "terminal_domain_bundle",
    "index_coding_settlement_domain_bundle",
)
TABLES = SCENE_TABLES + DOMAIN_TABLES
DOMAINS = ("admission", "course", "surgery", "consult_discussion", "terminal", "index_coding_settlement")


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


@pytest.fixture
def synthetic_bundles(pg_engine, monkeypatch):
    columns = {table: {item["name"] for item in inspect(pg_engine).get_columns(table, schema="public")}
               for table in TABLES}
    assert all({"institute_id", "patient_id", "visit_id", "policy_version", "bundle_updated_at"} <= names
               for names in columns.values())
    marker = uuid.uuid4().hex
    refs = [CaseRef("SYNTH_BUNDLE_PUBLISH", f"SYNTH_{marker}", f"VISIT_{marker}_{index}")
            for index in (1, 2)]
    ref_rows = [dict(institute_id=ref.institute_id, patient_id=ref.patient_id, visit_id=ref.visit_id)
                for ref in refs]
    old_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=2)
    try:
        with pg_engine.begin() as conn:
            for table, scene in zip(SCENE_TABLES, ("running", "final")):
                conn.execute(text(f"""
                    INSERT INTO public.{table}
                        (institute_id, patient_id, visit_id, scene, bundle_schema_version,
                         policy_version, medical_text, text_available, bundle_updated_at)
                    VALUES (:institute_id, :patient_id, :visit_id, :scene, :schema_version,
                            :policy_version, 'synthetic only', true, :bundle_updated_at)
                """), [dict(**row, scene=scene, schema_version="bundle-v6",
                            policy_version=sync.CONTRACT_VERSION, bundle_updated_at=old_time)
                       for row in ref_rows])
            for table, domain in zip(DOMAIN_TABLES, DOMAINS):
                conn.execute(text(f"""
                    INSERT INTO public.{table}
                        (institute_id, patient_id, visit_id, execution_domain,
                         bundle_schema_version, policy_version, bundle_updated_at)
                    VALUES (:institute_id, :patient_id, :visit_id, :execution_domain,
                            :schema_version, :policy_version, :bundle_updated_at)
                """), [dict(**row, execution_domain=domain, schema_version="bundle-v6",
                            policy_version=sync.CONTRACT_VERSION, bundle_updated_at=old_time)
                       for row in ref_rows])
        monkeypatch.setattr(sync, "SessionLocal", sessionmaker(bind=pg_engine))
        yield pg_engine, refs
    finally:
        with pg_engine.begin() as conn:
            for table in TABLES:
                conn.execute(text(f"""
                    DELETE FROM public.{table}
                    WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
                """), ref_rows)


@pytest.fixture
def empty_synthetic_bundle_ref(pg_engine, monkeypatch):
    marker = uuid.uuid4().hex
    ref = CaseRef("SYNTH_BUNDLE_PUBLISH", f"SYNTH_EMPTY_{marker}", f"VISIT_{marker}")
    params = ref.as_dict()
    monkeypatch.setattr(sync, "SessionLocal", sessionmaker(bind=pg_engine))
    monkeypatch.setattr(assembly, "engine", pg_engine)
    try:
        with pg_engine.connect() as conn:
            for table in TABLES:
                assert conn.execute(text(f"""
                    SELECT COUNT(*) FROM public.{table}
                    WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
                """), params).scalar_one() == 0
        yield pg_engine, ref
    finally:
        with pg_engine.begin() as conn:
            for table in TABLES:
                conn.execute(text(f"""
                    DELETE FROM public.{table}
                    WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
                """), params)


def _versions(engine, ref):
    params = dict(institute_id=ref.institute_id, patient_id=ref.patient_id, visit_id=ref.visit_id)
    with engine.connect() as conn:
        return {table: conn.execute(text(f"""
            SELECT policy_version FROM public.{table}
            WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
        """), params).scalar_one() for table in TABLES}


def _timestamps(engine, ref):
    with engine.connect() as conn:
        return {table: conn.execute(text(f"""
            SELECT bundle_updated_at FROM public.{table}
            WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
        """), ref.as_dict()).scalar_one() for table in TABLES}


def _staging_token():
    return f"{sync.INVALIDATED_POLICY_VERSION}:{uuid.uuid4().hex}"


def _stage_bundles(engine, refs, token):
    with engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"""
                UPDATE public.{table} SET policy_version = :staging_token,
                    bundle_updated_at = :refreshed_at
                WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
            """), [dict(institute_id=ref.institute_id, patient_id=ref.patient_id,
                        visit_id=ref.visit_id, staging_token=token,
                        refreshed_at=datetime.now(timezone.utc)) for ref in refs])


def test_partial_scene_refresh_stays_invalid_and_cannot_publish(synthetic_bundles):
    engine, refs = synthetic_bundles
    sync._invalidate_existing_bundles("running", refs)
    for ref in refs:
        assert set(_versions(engine, ref).values()) == {sync.INVALIDATED_POLICY_VERSION}
    staging_token = _staging_token()
    first = refs[0]
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE public.running_record_bundle SET policy_version = :staging_token,
                bundle_updated_at = :updated_at
            WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
        """), dict(institute_id=first.institute_id, patient_id=first.patient_id,
                    visit_id=first.visit_id, staging_token=staging_token,
                    updated_at=datetime.now(timezone.utc)))
    with engine.connect() as reader:
        assert reader.execute(text("""
            SELECT policy_version FROM public.running_record_bundle
            WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
        """), dict(institute_id=first.institute_id, patient_id=first.patient_id,
                    visit_id=first.visit_id)).scalar_one() == staging_token
    with pytest.raises(RuntimeError, match="任务 Bundle 刷新不完整"):
        sync._publish_refreshed_bundles(refs, staging_token)
    versions = _versions(engine, first)
    assert versions["running_record_bundle"] == staging_token
    assert set(versions.values()) == {staging_token, sync.INVALIDATED_POLICY_VERSION}
    assert set(_versions(engine, refs[1]).values()) == {sync.INVALIDATED_POLICY_VERSION}


def test_empty_case_invalidation_creates_eight_unreadable_placeholders(empty_synthetic_bundle_ref):
    engine, ref = empty_synthetic_bundle_ref
    sync._invalidate_existing_bundles("running", [ref])
    assert set(_versions(engine, ref).values()) == {sync.INVALIDATED_POLICY_VERSION}

    for scene in ("running", "final"):
        for force_refresh in (False, True):
            with pytest.raises(RuntimeError, match="同步尚未完成"):
                assembly.load_or_assemble_scene_bundle(
                    scene=scene, **ref.as_dict(), force_refresh=force_refresh,
                )
    for domain in DOMAINS:
        with pytest.raises(RuntimeError, match="同步尚未完成"):
            assembly.load_domain_bundle(execution_domain=domain, **ref.as_dict())
        for force_refresh in (False, True):
            with pytest.raises(RuntimeError, match="同步尚未完成"):
                assembly.load_or_assemble_domain_bundle(
                    execution_domain=domain, **ref.as_dict(), force_refresh=force_refresh,
                )
    assert set(_versions(engine, ref).values()) == {sync.INVALIDATED_POLICY_VERSION}


def test_existing_bundle_invalidation_preserves_all_update_times(synthetic_bundles):
    engine, refs = synthetic_bundles
    before = {ref: _timestamps(engine, ref) for ref in refs}
    sync._invalidate_existing_bundles("final", refs)
    for ref in refs:
        assert _timestamps(engine, ref) == before[ref]
        assert set(_versions(engine, ref).values()) == {sync.INVALIDATED_POLICY_VERSION}


def test_one_old_domain_row_cannot_join_seven_staged_variants(synthetic_bundles):
    engine, refs = synthetic_bundles
    sync._invalidate_existing_bundles("final", refs)
    staging_token = _staging_token()
    _stage_bundles(engine, refs, staging_token)
    old_ref = refs[0]
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE public.terminal_domain_bundle SET policy_version=:old_marker
            WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
        """), dict(institute_id=old_ref.institute_id, patient_id=old_ref.patient_id,
                    visit_id=old_ref.visit_id, old_marker=sync.INVALIDATED_POLICY_VERSION))

    with pytest.raises(RuntimeError, match="任务 Bundle 刷新不完整"):
        sync._publish_refreshed_bundles(refs, staging_token)

    versions = _versions(engine, old_ref)
    assert versions["terminal_domain_bundle"] == sync.INVALIDATED_POLICY_VERSION
    assert set(versions.values()) == {staging_token, sync.INVALIDATED_POLICY_VERSION}
    assert set(_versions(engine, refs[1]).values()) == {staging_token}


def test_publish_is_atomic_to_other_connections_and_failure_rolls_back(synthetic_bundles):
    engine, refs = synthetic_bundles
    sync._invalidate_existing_bundles("running", refs)
    staging_token = _staging_token()
    _stage_bundles(engine, refs, staging_token)
    entered = threading.Event()
    release = threading.Event()

    def pause_before_last_update(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "UPDATE public.index_coding_settlement_domain_bundle" in statement:
            entered.set()
            assert release.wait(10), "publish pause timed out"

    event.listen(engine, "before_cursor_execute", pause_before_last_update)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(sync._publish_refreshed_bundles, refs, staging_token)
            assert entered.wait(10), "publish never reached final table"
            for ref in refs:
                assert set(_versions(engine, ref).values()) == {staging_token}
            release.set()
            future.result(timeout=10)
    finally:
        release.set()
        event.remove(engine, "before_cursor_execute", pause_before_last_update)
    for ref in refs:
        assert set(_versions(engine, ref).values()) == {sync.CONTRACT_VERSION}


def test_failed_publish_rolls_back_all_scene_and_domain_updates(synthetic_bundles):
    engine, refs = synthetic_bundles
    sync._invalidate_existing_bundles("running", refs)
    staging_token = _staging_token()
    _stage_bundles(engine, refs, staging_token)

    def fail_last_update(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "UPDATE public.index_coding_settlement_domain_bundle" in statement:
            raise RuntimeError("synthetic publish failure")

    event.listen(engine, "before_cursor_execute", fail_last_update)
    try:
        with pytest.raises(RuntimeError, match="synthetic publish failure"):
            sync._publish_refreshed_bundles(refs, staging_token)
    finally:
        event.remove(engine, "before_cursor_execute", fail_last_update)
    for ref in refs:
        assert set(_versions(engine, ref).values()) == {staging_token}


def test_publish_does_not_cross_case_ref_or_staging_token(synthetic_bundles):
    engine, refs = synthetic_bundles
    sync._invalidate_existing_bundles("running", refs)
    first_token, second_token = _staging_token(), _staging_token()
    _stage_bundles(engine, [refs[0]], first_token)
    _stage_bundles(engine, [refs[1]], second_token)

    sync._publish_refreshed_bundles([refs[0]], first_token)

    assert set(_versions(engine, refs[0]).values()) == {sync.CONTRACT_VERSION}
    assert set(_versions(engine, refs[1]).values()) == {second_token}
