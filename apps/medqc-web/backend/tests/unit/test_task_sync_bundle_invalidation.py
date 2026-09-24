"""隔离验证任务同步在 CDM 写入前持久关闭旧 Bundle。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskRecord
from app.services import task_record_sync_service as service


@pytest.fixture
def workspace(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS public")
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
        conn.exec_driver_sql("CREATE TABLE cdm.first_table_write (id INTEGER PRIMARY KEY)")
        for table in ("running_record_bundle", "final_record_bundle"):
            conn.exec_driver_sql(f"""
                CREATE TABLE public.{table} (
                    institute_id TEXT, patient_id TEXT, visit_id TEXT,
                    policy_version TEXT, medical_text TEXT,
                    PRIMARY KEY (institute_id, patient_id, visit_id)
                )
            """)
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    with factory.begin() as session:
        session.execute(QCTask.__table__.insert().values(
            id="task-1", task_number="TASK-1", task_name="测试", task_type="one_time",
            scene="running", creator_id="owner", status="sampling", total_records=2,
        ))
        session.execute(QCTaskRecord.__table__.insert(), [
            {"id": "assoc-1", "task_id": "task-1", "record_id": "assoc-1",
             "institute_id": "hospital", "patient_id": "same", "visit_id": "visit-1"},
            {"id": "assoc-2", "task_id": "task-1", "record_id": "assoc-2",
             "institute_id": "hospital", "patient_id": "same", "visit_id": "visit-2"},
        ])
        for table in ("running_record_bundle", "final_record_bundle"):
            session.execute(sa.text(f"""
                INSERT INTO public.{table} VALUES
                    ('hospital', 'same', 'visit-1', :version, '原文1'),
                    ('hospital', 'same', 'visit-2', :version, '原文2'),
                    ('other-hospital', 'same', 'visit-1', :version, '其他医院'),
                    ('hospital', 'same', 'other-visit', :version, '其他就诊')
            """), {"version": service.CONTRACT_VERSION})
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def _versions(factory, scene="running"):
    with factory() as session:
        return session.execute(sa.text(f"""
            SELECT institute_id, patient_id, visit_id, policy_version, medical_text
            FROM public.{scene}_record_bundle
            ORDER BY institute_id, patient_id, visit_id
        """)).all()


def test_failure_after_first_local_write_keeps_only_exact_scene_refs_invalid(workspace):
    calls = []

    class PartialSync:
        def sync_case_set(self, **kwargs):
            calls.append(kwargs)
            with workspace.begin() as session:
                current = session.execute(sa.text("""
                    SELECT policy_version FROM public.running_record_bundle
                    WHERE institute_id='hospital' AND patient_id='same' AND visit_id='visit-1'
                """)).scalar_one()
                assert current == service.INVALIDATED_POLICY_VERSION
                session.execute(sa.text("INSERT INTO cdm.first_table_write (id) VALUES (:id)"),
                                {"id": len(calls)})
            raise TimeoutError("首张 CDM 表之后异常")

    for _ in range(2):
        with pytest.raises(RuntimeError, match="可重试"):
            service.sync_task_records(
                task_id="task-1", actor_id="owner", sync_factory=PartialSync,
            )
        rows = _versions(workspace)
        actual = {(row[0], row[1], row[2]): (row[3], row[4]) for row in rows}
        assert actual == {
            ("hospital", "same", "visit-1"): (service.INVALIDATED_POLICY_VERSION, "原文1"),
            ("hospital", "same", "visit-2"): (service.INVALIDATED_POLICY_VERSION, "原文2"),
            ("hospital", "same", "other-visit"): (service.CONTRACT_VERSION, "其他就诊"),
            ("other-hospital", "same", "visit-1"): (service.CONTRACT_VERSION, "其他医院"),
        }
        assert {row[3] for row in _versions(workspace, "final")} == {service.CONTRACT_VERSION}
    assert len(calls) == 2
    with workspace() as session:
        assert session.execute(sa.text("SELECT COUNT(*) FROM cdm.first_table_write")).scalar_one() == 2


def test_successful_refresh_restores_contract_policy(workspace):
    class CompleteSync:
        def sync_case_set(self, **kwargs):
            with workspace.begin() as session:
                before = session.execute(sa.text("""
                    SELECT policy_version FROM public.running_record_bundle
                    WHERE institute_id='hospital' AND patient_id='same' AND visit_id='visit-1'
                """)).scalar_one()
                assert before == service.INVALIDATED_POLICY_VERSION
                session.execute(sa.text("""
                    UPDATE public.running_record_bundle SET policy_version=:version
                    WHERE institute_id='hospital' AND patient_id='same'
                      AND visit_id IN ('visit-1', 'visit-2')
                """), {"version": service.CONTRACT_VERSION})
            return SimpleNamespace(
                visible_case_refs=tuple(kwargs["case_refs"]),
                synced_tables=tuple(
                    {"table_name": name, "sync_status": "synced"}
                    for name in kwargs["table_names"]
                ),
            )

    result = service.sync_task_records(
        task_id="task-1", actor_id="owner", sync_factory=CompleteSync,
        readiness_checker=lambda _scene, refs: set(refs),
    )
    assert result["ready_count"] == 2
    assert {row[3] for row in _versions(workspace)} == {service.CONTRACT_VERSION}


def test_invalidation_transaction_failure_never_calls_source(workspace):
    with workspace.begin() as session:
        session.execute(sa.text("""
            CREATE TRIGGER public.reject_second_bundle BEFORE UPDATE ON running_record_bundle
            WHEN OLD.visit_id = 'visit-2' BEGIN SELECT RAISE(ABORT, 'blocked'); END
        """))
    calls = []

    class Source:
        def sync_case_set(self, **kwargs):
            calls.append(kwargs)

    with pytest.raises(RuntimeError, match="失效保护失败"):
        service.sync_task_records(
            task_id="task-1", actor_id="owner", sync_factory=Source,
        )
    assert calls == []
    assert {row[3] for row in _versions(workspace)} == {service.CONTRACT_VERSION}


def test_final_scene_only_invalidates_existing_final_bundles(workspace):
    with workspace.begin() as session:
        session.execute(sa.text("UPDATE qc_tasks SET scene='final' WHERE id='task-1'"))
        session.execute(sa.text("""
            DELETE FROM public.final_record_bundle
            WHERE institute_id='hospital' AND patient_id='same' AND visit_id='visit-2'
        """))

    class InterruptedSync:
        def sync_case_set(self, **kwargs):
            raise TimeoutError("中断")

    with pytest.raises(RuntimeError, match="可重试"):
        service.sync_task_records(
            task_id="task-1", actor_id="owner", sync_factory=InterruptedSync,
        )
    final_rows = {
        (row[0], row[1], row[2]): row[3] for row in _versions(workspace, "final")
    }
    assert final_rows[("hospital", "same", "visit-1")] == service.INVALIDATED_POLICY_VERSION
    assert ("hospital", "same", "visit-2") not in final_rows
    assert {row[3] for row in _versions(workspace, "running")} == {service.CONTRACT_VERSION}
