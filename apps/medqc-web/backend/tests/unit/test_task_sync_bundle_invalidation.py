"""隔离验证任务同步在 CDM 写入前持久关闭旧 Bundle。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskRecord
from app.services import task_record_sync_service as service
from app.services.bundles import publication
from app.services.case_identity import CaseRef


@pytest.fixture
def workspace(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS public")
        conn.exec_driver_sql("ATTACH DATABASE ':memory:' AS cdm")
        conn.exec_driver_sql("CREATE TABLE cdm.first_table_write (id INTEGER PRIMARY KEY)")
        for table in service._BUNDLE_TABLES:
            conn.exec_driver_sql(f"""
                CREATE TABLE public.{table} (
                    institute_id TEXT, patient_id TEXT, visit_id TEXT,
                    scene TEXT, execution_domain TEXT,
                    policy_version TEXT, bundle_schema_version TEXT,
                    bundle_updated_at TIMESTAMP, medical_text TEXT,
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
        for table in service._BUNDLE_TABLES:
            session.execute(sa.text(f"""
                INSERT INTO public.{table}
                    (institute_id, patient_id, visit_id, policy_version,
                     bundle_schema_version, bundle_updated_at, medical_text)
                VALUES
                    ('hospital', 'same', 'visit-1', :version, :schema, CURRENT_TIMESTAMP, '原文1'),
                    ('hospital', 'same', 'visit-2', :version, :schema, CURRENT_TIMESTAMP, '原文2'),
                    ('other-hospital', 'same', 'visit-1', :version, :schema, CURRENT_TIMESTAMP, '其他医院'),
                    ('hospital', 'same', 'other-visit', :version, :schema, CURRENT_TIMESTAMP, '其他就诊')
            """), {"version": service.CONTRACT_VERSION,
                    "schema": service.BUNDLE_SCHEMA_VERSION_CURRENT})
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


def _stage_all(factory, token, *, skip_table=None, skip_visit=None):
    with factory.begin() as session:
        for table in service._BUNDLE_TABLES:
            for visit_id in ("visit-1", "visit-2"):
                if table == skip_table and visit_id == skip_visit:
                    continue
                session.execute(sa.text(f"""
                    UPDATE public.{table} SET policy_version=:token
                    WHERE institute_id='hospital' AND patient_id='same' AND visit_id=:visit_id
                """), {"token": token, "visit_id": visit_id})


def _complete_refresh_stats(count=2):
    def counts():
        return {"updated": count, "processed": count, "failed": 0}

    return {
        "scenes": {name: counts() for name in ("running", "final")},
        "domains": {
            name.removesuffix("_domain_bundle"): counts()
            for name in service._BUNDLE_TABLES[2:]
        },
    }


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
        for table in service._BUNDLE_TABLES[1:]:
            with workspace() as session:
                versions = session.execute(sa.text(f"""
                    SELECT policy_version FROM public.{table}
                    WHERE institute_id='hospital' AND patient_id='same'
                      AND visit_id IN ('visit-1', 'visit-2')
                """)).scalars().all()
            assert versions == [service.INVALIDATED_POLICY_VERSION] * 2
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
                for table in service._BUNDLE_TABLES:
                    session.execute(sa.text(f"""
                        UPDATE public.{table} SET policy_version=:version
                        WHERE institute_id='hospital' AND patient_id='same'
                          AND visit_id IN ('visit-1', 'visit-2')
                    """), {"version": kwargs["bundle_policy_version"]})
            return SimpleNamespace(
                visible_case_refs=tuple(kwargs["case_refs"]),
                bundle_refresh=_complete_refresh_stats(),
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
    with workspace() as session:
        for table in service._BUNDLE_TABLES:
            assert set(session.execute(sa.text(f"""
                SELECT policy_version FROM public.{table}
            """)).scalars()) == {service.CONTRACT_VERSION}


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


def test_final_scene_invalidates_all_existing_variants(workspace):
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
    assert final_rows[("hospital", "same", "visit-2")] == service.INVALIDATED_POLICY_VERSION
    assert {
        row[3] for row in _versions(workspace, "running")
        if row[0] == "hospital" and row[1] == "same" and row[2] in {"visit-1", "visit-2"}
    } == {service.INVALIDATED_POLICY_VERSION}


def test_unrefreshed_old_variant_cannot_be_published(workspace):
    class PartialRefresh:
        def sync_case_set(self, **kwargs):
            _stage_all(
                workspace, kwargs["bundle_policy_version"],
                skip_table="terminal_domain_bundle", skip_visit="visit-2",
            )
            return SimpleNamespace(
                visible_case_refs=tuple(kwargs["case_refs"]),
                bundle_refresh=_complete_refresh_stats(),
                synced_tables=tuple(
                    {"table_name": name, "sync_status": "synced"}
                    for name in kwargs["table_names"]
                ),
            )

    with pytest.raises(RuntimeError, match="发布失败"):
        service.sync_task_records(
            task_id="task-1", actor_id="owner", sync_factory=PartialRefresh,
            readiness_checker=lambda *_: pytest.fail("未完整发布不能 ready"),
        )
    with workspace() as session:
        for table in service._BUNDLE_TABLES:
            versions = set(session.execute(sa.text(f"""
                SELECT policy_version FROM public.{table}
                WHERE institute_id='hospital' AND patient_id='same'
                  AND visit_id IN ('visit-1', 'visit-2')
            """)).scalars())
            assert service.CONTRACT_VERSION not in versions


def test_incomplete_refresh_count_blocks_publish_even_if_rows_are_staged(workspace):
    class IncompleteRefresh:
        def sync_case_set(self, **kwargs):
            _stage_all(workspace, kwargs["bundle_policy_version"])
            stats = _complete_refresh_stats()
            stats["domains"]["course"]["updated"] = 1
            return SimpleNamespace(
                visible_case_refs=tuple(kwargs["case_refs"]),
                bundle_refresh=stats,
                synced_tables=tuple(
                    {"table_name": name, "sync_status": "synced"}
                    for name in kwargs["table_names"]
                ),
            )

    with pytest.raises(RuntimeError, match="发布失败"):
        service.sync_task_records(
            task_id="task-1", actor_id="owner", sync_factory=IncompleteRefresh,
            readiness_checker=lambda *_: pytest.fail("刷新计数不完整不能 ready"),
        )
    with workspace() as session:
        for table in service._BUNDLE_TABLES:
            versions = set(session.execute(sa.text(f"""
                SELECT policy_version FROM public.{table}
                WHERE institute_id='hospital' AND patient_id='same'
                  AND visit_id IN ('visit-1', 'visit-2')
            """)).scalars())
            assert len(versions) == 1
            assert next(iter(versions)).startswith(service.INVALIDATED_POLICY_VERSION + ":")


def test_last_variant_publish_failure_rolls_back_all_versions(workspace):
    with workspace.begin() as session:
        session.execute(sa.text("""
            CREATE TRIGGER public.reject_last_publish
            BEFORE UPDATE ON index_coding_settlement_domain_bundle
            WHEN NEW.policy_version = 'task-record-sync-v1'
            BEGIN SELECT RAISE(ABORT, 'publish rejected'); END
        """))

    class CompleteRefresh:
        def sync_case_set(self, **kwargs):
            _stage_all(workspace, kwargs["bundle_policy_version"])
            return SimpleNamespace(
                visible_case_refs=tuple(kwargs["case_refs"]),
                bundle_refresh=_complete_refresh_stats(),
                synced_tables=tuple(
                    {"table_name": name, "sync_status": "synced"}
                    for name in kwargs["table_names"]
                ),
            )

    with pytest.raises(RuntimeError, match="发布失败"):
        service.sync_task_records(
            task_id="task-1", actor_id="owner", sync_factory=CompleteRefresh,
            readiness_checker=lambda *_: pytest.fail("事务失败不能 ready"),
        )
    with workspace() as session:
        for table in service._BUNDLE_TABLES:
            versions = set(session.execute(sa.text(f"""
                SELECT policy_version FROM public.{table}
                WHERE institute_id='hospital' AND patient_id='same'
                  AND visit_id IN ('visit-1', 'visit-2')
            """)).scalars())
            assert len(versions) == 1
            assert next(iter(versions)).startswith(service.INVALIDATED_POLICY_VERSION + ":")


def test_missing_bundle_rows_are_fenced_before_source_write(workspace):
    with workspace.begin() as session:
        for table in service._BUNDLE_TABLES:
            session.execute(sa.text(f"""
                DELETE FROM public.{table}
                WHERE institute_id='hospital' AND patient_id='same' AND visit_id='visit-2'
            """))

    class InterruptedSync:
        def sync_case_set(self, **kwargs):
            with workspace() as session:
                for table in service._BUNDLE_TABLES:
                    row = session.execute(sa.text(f"""
                        SELECT policy_version FROM public.{table}
                        WHERE institute_id='hospital' AND patient_id='same' AND visit_id='visit-2'
                    """)).scalar_one()
                    assert row == service.INVALIDATED_POLICY_VERSION
            raise TimeoutError("首张 CDM 表之前中断")

    with pytest.raises(RuntimeError, match="可重试"):
        service.sync_task_records(
            task_id="task-1", actor_id="owner", sync_factory=InterruptedSync,
        )
    with workspace() as session:
        for table in service._BUNDLE_TABLES:
            assert session.execute(sa.text(f"""
                SELECT policy_version FROM public.{table}
                WHERE institute_id='hospital' AND patient_id='same' AND visit_id='visit-2'
            """)).scalar_one() == service.INVALIDATED_POLICY_VERSION


def test_large_publication_uses_bounded_set_queries_and_allows_empty_policy(workspace):
    refs = [CaseRef("hospital", "synthetic", f"visit-{index:03d}") for index in range(205)]
    publication.invalidate_bundle_variants(refs, session_factory=workspace)
    token = publication.new_bundle_staging_token()
    with workspace.begin() as session:
        for table in publication.BUNDLE_TABLES:
            session.execute(sa.text(f"""
                UPDATE public.{table} SET policy_version=:token
                WHERE institute_id='hospital' AND patient_id='synthetic'
            """), {"token": token})

    statements = []

    def count_statements(_conn, _cursor, statement, _params, _context, _many):
        if "public." in statement:
            statements.append(statement)

    sa.event.listen(workspace.kw["bind"], "before_cursor_execute", count_statements)
    try:
        publication.publish_bundle_variants(
            refs, staging_token=token, published_policy_version="", session_factory=workspace,
        )
    finally:
        sa.event.remove(workspace.kw["bind"], "before_cursor_execute", count_statements)

    checks = [sql for sql in statements if "SELECT COUNT(*) FROM public." in sql]
    updates = [sql for sql in statements if "UPDATE public." in sql]
    assert len(checks) == len(updates) == len(publication.BUNDLE_TABLES) * 2
    with workspace() as session:
        for table in publication.BUNDLE_TABLES:
            assert session.execute(sa.text(f"""
                SELECT COUNT(*) FROM public.{table}
                WHERE institute_id='hospital' AND patient_id='synthetic' AND policy_version=''
            """)).scalar_one() == len(refs)
