"""客户自建测试病历八变体发布及失败关闭。"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.services import custom_qc_sample_pool_service as module
from app.services.case_identity import CaseRef


def _counts(*, failed_domain: str = ""):
    names = ("admission", "course", "surgery", "consult_discussion", "terminal", "index_coding_settlement")
    return {
        "scenes": {name: {"processed": 1, "updated": 1, "failed": 0} for name in ("running", "final")},
        "domains": {
            name: {"processed": 1, "updated": 0 if name == failed_domain else 1,
                   "failed": 1 if name == failed_domain else 0}
            for name in names
        },
    }


def test_partial_domain_refresh_cannot_publish(monkeypatch):
    ref = CaseRef("CUSTOMER_TEST", "patient", "visit")
    calls = []
    monkeypatch.setattr(module.CustomQCSamplePoolService, "_customer_test_staged_running_usable",
                        lambda *_: True)
    monkeypatch.setattr(module, "invalidate_bundle_variants", lambda refs, **_: calls.append(("invalidate", refs)))
    monkeypatch.setattr(module, "refresh_all_bundle_variants_for_rows",
                        lambda **kwargs: calls.append(("refresh", kwargs)) or _counts(failed_domain="terminal"))
    monkeypatch.setattr(module, "publish_bundle_variants", lambda *_args, **_kwargs: calls.append("publish"))

    with pytest.raises(RuntimeError, match="Bundle 刷新不完整"):
        module.CustomQCSamplePoolService._publish_customer_test_bundle(ref)

    assert [call[0] for call in calls] == ["invalidate", "refresh"]
    assert calls[1][1]["policy_version"].startswith(module.TASK_SYNC_INVALIDATED_POLICY_VERSION + ":")


def test_complete_refresh_uses_same_staging_token_for_atomic_publish(monkeypatch):
    ref = CaseRef("CUSTOMER_TEST", "patient", "visit")
    calls = []
    monkeypatch.setattr(module.CustomQCSamplePoolService, "_customer_test_staged_running_usable",
                        lambda *_: True)
    monkeypatch.setattr(module, "invalidate_bundle_variants", lambda refs, **_: calls.append(("invalidate", refs)))
    monkeypatch.setattr(module, "refresh_all_bundle_variants_for_rows",
                        lambda **kwargs: calls.append(("refresh", kwargs)) or _counts())
    monkeypatch.setattr(module, "publish_bundle_variants",
                        lambda refs, **kwargs: calls.append(("publish", refs, kwargs)))

    module.CustomQCSamplePoolService._publish_customer_test_bundle(ref)

    assert [call[0] for call in calls] == ["invalidate", "refresh", "publish"]
    assert calls[2][2]["staging_token"] == calls[1][1]["policy_version"]
    assert calls[2][2]["published_policy_version"] == "customer_test_record_builder"


def test_unusable_staged_running_cannot_publish(monkeypatch):
    ref = CaseRef("CUSTOMER_TEST", "patient", "visit")
    calls = []
    monkeypatch.setattr(module, "invalidate_bundle_variants", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(module, "refresh_all_bundle_variants_for_rows", lambda **_: _counts())
    monkeypatch.setattr(module.CustomQCSamplePoolService, "_customer_test_staged_running_usable",
                        lambda *_: False)
    monkeypatch.setattr(module, "publish_bundle_variants", lambda *_args, **_kwargs: calls.append("publish"))

    with pytest.raises(RuntimeError, match="running Bundle 内容不可用"):
        module.CustomQCSamplePoolService._publish_customer_test_bundle(ref)

    assert calls == []


class _Session:
    def __init__(self):
        self.statements = []
        self.commits = 0

    def execute(self, statement):
        self.statements.append(statement)

    def commit(self):
        self.commits += 1


def _service(monkeypatch, *, complete, publish_error=None):
    service = object.__new__(module.CustomQCSamplePoolService)
    service._item_table = sa.table("sample_items", sa.column("id"), sa.column("bundle_status"), sa.column("updated_at"))
    service._customer_test_bundle_write_lock = lambda: __import__("contextlib").nullcontext()
    events = []
    service._customer_test_bundle_complete = lambda ref: complete

    def publish(ref):
        events.append(("publish", ref))
        if publish_error:
            raise publish_error

    service._publish_customer_test_bundle = publish
    service._wait_running_bundle_ready = lambda **_: "ready"
    return service, events


def _item(status):
    return {
        "id": "item", "pool_id": module.CUSTOMER_TEST_POOL_ID, "bundle_status": status,
        "matched_institute_id": "CUSTOMER_TEST", "matched_patient_id": "patient",
        "matched_visit_id": "CUSTOMER_TEST_visit",
    }


def test_old_ready_with_incomplete_variants_is_demoted_on_rebuild_failure(monkeypatch):
    service, events = _service(monkeypatch, complete=False, publish_error=RuntimeError("final failed"))
    session = _Session()

    rows = service._heal_customer_test_bundle_statuses(session=session, rows=[_item("ready")])

    assert rows[0]["bundle_status"] == "pending"
    assert len(events) == 1
    assert session.commits == 1


def test_pending_is_not_promoted_when_published_variants_cannot_be_verified(monkeypatch):
    service, events = _service(monkeypatch, complete=False)
    session = _Session()

    rows = service._heal_customer_test_bundle_statuses(session=session, rows=[_item("pending")])

    assert rows[0]["bundle_status"] == "pending"
    assert len(events) == 1
    assert session.commits == 0


@pytest.mark.skipif(os.getenv("MEDQC_PG_RACE_NONPROD_DB") != "medqc_v36_validation_20260924",
                    reason="explicit non-production database opt-in required")
def test_pg_partial_refresh_keeps_all_variants_invalidated(monkeypatch):
    env_path = Path(__file__).resolve().parents[2] / ".env"
    raw_url = next((line.split("=", 1)[1].strip().strip("\"'") for line in env_path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("DATABASE_URL=")), "")
    if not raw_url:
        pytest.skip("PostgreSQL URL unavailable")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("PostgreSQL required")
    engine = sa.create_engine(url.set(database="medqc_v36_validation_20260924"))
    ref = CaseRef("SYNTH_CUSTOMER_BUNDLE", f"patient_{uuid.uuid4().hex}", f"visit_{uuid.uuid4().hex}")
    try:
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT current_database()")).scalar_one() == "medqc_v36_validation_20260924"
            assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == "20260924_000051"
        monkeypatch.setattr(module, "engine", engine)
        monkeypatch.setattr(module, "SessionLocal", sessionmaker(bind=engine))
        monkeypatch.setattr(module, "refresh_all_bundle_variants_for_rows", lambda **_: _counts(failed_domain="terminal"))
        from app.services.task_record_sync_job_service import _GLOBAL_LOCK_KEY

        with module.CustomQCSamplePoolService._customer_test_bundle_write_lock():
            with engine.connect() as contender:
                assert contender.execute(sa.text("SELECT pg_try_advisory_lock(:key)"),
                                         {"key": _GLOBAL_LOCK_KEY}).scalar_one() is False
            with pytest.raises(RuntimeError, match="Bundle 刷新不完整"):
                module.CustomQCSamplePoolService._publish_customer_test_bundle(ref)
        with engine.connect() as contender:
            assert contender.execute(sa.text("SELECT pg_try_advisory_lock(:key)"),
                                     {"key": _GLOBAL_LOCK_KEY}).scalar_one() is True
            contender.execute(sa.text("SELECT pg_advisory_unlock(:key)"), {"key": _GLOBAL_LOCK_KEY})

        with engine.connect() as conn:
            policies = [conn.execute(sa.text(f"""
                SELECT policy_version FROM public.{table}
                WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
            """), ref.as_dict()).scalar_one() for table in module.BUNDLE_TABLES]
        assert policies == [module.TASK_SYNC_INVALIDATED_POLICY_VERSION] * 8
        with engine.begin() as conn:
            for table in module.BUNDLE_TABLES:
                conn.execute(sa.text(f"""
                    UPDATE public.{table} SET policy_version='customer_test_record_builder'
                    WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
                """), ref.as_dict())
        service = object.__new__(module.CustomQCSamplePoolService)
        assert service._customer_test_bundle_complete(ref) is False
    finally:
        with engine.begin() as conn:
            for table in module.BUNDLE_TABLES:
                conn.execute(sa.text(f"""
                    DELETE FROM public.{table}
                    WHERE institute_id=:institute_id AND patient_id=:patient_id AND visit_id=:visit_id
                """), ref.as_dict())
        engine.dispose()
