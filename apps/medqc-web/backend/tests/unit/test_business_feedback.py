"""真实SQLite持久化验证；不连接共享数据库。"""
from copy import deepcopy
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from app.services.qc_agent import business_feedback as service
from app.services.qc_agent.business_access import BusinessAccess

USER = {"id": "real-user", "roles": ["doctor", "qc_manager"]}
IDENTITY = {"institute_id": "H", "patient_id": "P", "visit_id": "V"}
REF = "result:job:rec:R"


@pytest.fixture
def storage(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'feedback.sqlite'}")
    table = service.feedback_table()
    table.create(engine)
    yield service.BusinessFeedbackStore(sessionmaker(bind=engine), table), engine, table
    engine.dispose()


def target():
    return {**IDENTITY, "reference_id": REF, "root_job_id": "job", "record_ref": "rec", "rule_id": "R", "original_status": "non_compliant", "title": "保存问题"}


def payload(**changes):
    return service.FeedbackSubmit(reference_id=REF, comment=changes.pop("comment", " 请复核证据 "), request_id=changes.pop("request_id", uuid4()), **changes)


def test_persist_real_user_and_read_after_new_store(storage):
    store, engine, table = storage
    submitted = store.submit(uid=USER["id"], session_id="session-a", target=target(), payload=payload())
    restored = service.BusinessFeedbackStore(sessionmaker(bind=engine), table).read(uid=USER["id"], session_id="session-a", reference_id=REF)
    assert restored == submitted
    assert restored["status"] == "submitted"
    assert restored["comment"] == "请复核证据"
    with engine.connect() as conn:
        row = conn.execute(sa.select(table)).mappings().one()
        assert row["created_by"] == "real-user"
        assert row["patient_id"] == "P"
        assert row["original_status"] == "non_compliant"
    assert store.read(uid="other", session_id="session-a", reference_id=REF) is None
    assert store.read(uid=USER["id"], session_id="session-b", reference_id=REF) is None


def test_duplicate_requests_and_target_are_idempotent(storage):
    store, engine, table = storage
    request = payload()
    first = store.submit(uid=USER["id"], session_id="s", target=target(), payload=request)
    for repeated in (request, payload()):
        assert store.submit(uid=USER["id"], session_id="s", target=target(), payload=repeated) == first
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(table)) == 1
    for sid, request in (("s", payload(comment="不同理由")), ("other", request)):
        with pytest.raises(HTTPException) as error:
            store.submit(uid=USER["id"], session_id=sid, target=target(), payload=request)
        assert error.value.status_code == 409


def test_missing_migration_never_reports_success(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'unmigrated.sqlite'}")
    store = service.BusinessFeedbackStore(sessionmaker(bind=engine), service.feedback_table())
    try:
        for call in (lambda: store.read(uid="u", session_id="s", reference_id=REF),
                     lambda: store.submit(uid="u", session_id="s", target=target(), payload=payload())):
            with pytest.raises(HTTPException) as error:
                call()
            assert error.value.status_code == 503
            assert "20261002_000045" in error.value.detail
    finally:
        engine.dispose()


def test_concurrent_duplicate_clicks_only_insert_once(storage, monkeypatch):
    store, engine, table = storage
    original = store._existing
    barrier, lock = Barrier(2), Lock()
    reads = 0
    def synchronized_read(*args, **kwargs):
        nonlocal reads
        rows = original(*args, **kwargs)
        with lock:
            reads += 1
            initial = reads <= 2
        if initial:
            barrier.wait(timeout=5)
        return rows
    monkeypatch.setattr(store, "_existing", synchronized_read)
    def submit(_):
        return store.submit(uid=USER["id"], session_id="s", target=target(), payload=payload())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert results[0] == results[1]
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(table)) == 1


def test_migration_roundtrip_matches_runtime_table(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).resolve().parents[2] / "alembic/versions/20261002_000045_business_feedback.py"
    spec = importlib.util.spec_from_file_location("feedback_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setenv("DB_SCHEMA_MODE", "single")
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.sqlite'}")
    try:
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
                columns = sa.inspect(conn).get_columns("qc_business_feedback")
                assert {column["name"] for column in columns} == set(service.feedback_table().c.keys())
                migration.downgrade()
                assert not sa.inspect(conn).has_table("qc_business_feedback")
    finally:
        engine.dispose()


def metadata():
    return {"owner_id": USER["id"], "session_id": "session", "context": {"view": "doctor", **IDENTITY},
            "references": {REF: {"kind": "saved_result", "identity": dict(IDENTITY), "job_id": "job", "record_ref": "rec", "rule_id": "R"}}}


def access():
    return BusinessAccess({"version": 1, "accounts": {USER["id"]: {"doctor_cases": [IDENTITY], "manager_scopes": [{"institute_id": "H", "department": "D"}]}}})


def test_target_only_uses_server_saved_result(monkeypatch):
    saved = {"job_id": "job", "record_ref": "rec", "items": [{"rule_id": "R", "status": "non_compliant", "qc_point": "保存问题"}]}
    before = deepcopy(saved)
    monkeypatch.setattr(service.business_reads, "saved_record", lambda identity: saved)
    actual = service.resolve_target(metadata(), USER, access(), REF)
    assert actual == target()
    assert saved == before


@pytest.mark.parametrize("case,status", [("owner", 404), ("unbound", 404), ("patient", 403), ("revoked", 403), ("version", 409)])
def test_target_rejects_cross_context_and_stale_result(monkeypatch, case, status):
    meta = metadata()
    grants = access()
    saved = {"job_id": "job", "record_ref": "rec", "items": [{"rule_id": "R", "status": "compliant"}]}
    if case == "owner":
        meta["owner_id"] = "other"
    elif case == "unbound":
        meta["references"] = {}
    elif case == "patient":
        meta["references"][REF]["identity"]["patient_id"] = "another"
    elif case == "revoked":
        grants = BusinessAccess({"version": 1, "accounts": {}})
    elif case == "version":
        saved["job_id"] = "new-job"
    monkeypatch.setattr(service.business_reads, "saved_record", lambda identity: saved)
    with pytest.raises(HTTPException) as error:
        service.resolve_target(meta, USER, grants, REF)
    assert error.value.status_code == status


def test_manager_rechecks_current_case_department(monkeypatch):
    meta = metadata()
    meta["context"] = {"view": "manager", "institute_id": "H", "department": "D", "care_phase": "discharged",
                       "completed_from": "2026-09-01T00:00:00+08:00", "completed_to": "2026-10-01T00:00:00+08:00"}
    monkeypatch.setattr(service.business_reads, "scoped_records", lambda **kwargs: [])
    with pytest.raises(HTTPException) as error:
        service.resolve_target(meta, USER, access(), REF)
    assert error.value.status_code == 403


def test_reason_required_and_identity_cannot_be_supplied():
    for changes in ({"comment": "   "}, {"patient_id": "other"}, {"created_by": "admin-001"}):
        with pytest.raises(ValidationError):
            payload(**changes)


@pytest.mark.parametrize("value", ["2026-10-02T16:30:00+08:00", "2026-10-02T08:30:00+00:00", "2026-10-02T08:30:00"])
def test_feedback_serialization_preserves_instant(value):
    result = service.public_feedback({"id": "id", "reference_id": REF, "comment": "请复核",
                                      "created_at": datetime.fromisoformat(value)})
    assert result["created_at"] == "2026-10-02T08:30:00+00:00"
