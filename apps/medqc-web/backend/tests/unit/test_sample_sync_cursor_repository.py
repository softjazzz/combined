from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.services.sample_sync_cursor_repository import (
    SampleSyncCursorRepository,
    VisitKey,
    build_cursor_table,
    build_source_identity,
)


def _repository():
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    table = build_cursor_table(schema=None)
    table.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    return session, SampleSyncCursorRepository(session, table=table)


def test_source_identity_is_stable_and_does_not_expose_connection_details():
    first = build_source_identity(
        host="192.168.140.160",
        port=16016,
        database="CustomerDB",
        schema="dbo",
    )
    second = build_source_identity(
        host=" 192.168.140.160 ",
        port="16016",
        database="customerdb",
        schema="DBO",
    )

    assert first == second
    assert len(first) == 32
    assert "192.168" not in first
    assert "customerdb" not in first
    assert build_source_identity(
        host="192.168.140.160",
        port=16016,
        database="CustomerDB",
        schema="other",
    ) != first


def test_cursor_advances_only_through_explicit_success_boundary():
    session, repository = _repository()
    source = "source-a"
    visit = VisitKey("H1", "P1", "V1")

    assert repository.get_many(
        source_identity=source,
        visit_keys=[visit],
        table_names=["daily_course_record"],
    ) == {}
    assert {
        name
        for name in dir(repository)
        if name.startswith("mark_") and callable(getattr(repository, name))
    } == {"mark_success", "mark_full_sync"}

    watermark = datetime(2026, 7, 31, 1, 2, tzinfo=timezone.utc)
    repository.mark_success(
        source_identity=source,
        visit_key=visit,
        table_name="daily_course_record",
        strategy="updated_at",
        schema_version="v1",
        watermark_column="update_time",
        watermark_value=watermark,
        source_row_count=3,
        job_id="job-1",
    )
    session.commit()

    cursor = next(
        iter(
            repository.get_many(
                source_identity=source,
                visit_keys=[visit],
                table_names=["daily_course_record"],
            ).values()
        )
    )
    assert cursor.watermark_value == watermark
    assert cursor.last_job_id == "job-1"
    assert cursor.last_full_sync_at is None


def test_rollback_after_mark_success_does_not_persist_cursor():
    session, repository = _repository()
    visit = VisitKey("H1", "P1", "V1")
    repository.mark_success(
        source_identity="source-a",
        visit_key=visit,
        table_name="medical_order",
        strategy="updated_at",
        schema_version="v1",
        watermark_value=datetime(2026, 7, 31, tzinfo=timezone.utc),
    )
    session.rollback()

    assert repository.get_many(
        source_identity="source-a",
        visit_keys=[visit],
        table_names=["medical_order"],
    ) == {}


def test_cursor_is_isolated_by_source_visit_coordinates_and_table():
    session, repository = _repository()
    visits = [VisitKey("H1", "P1", "V1"), VisitKey("H1", "P1", "V2")]
    for source in ("source-a", "source-b"):
        for visit in visits:
            repository.mark_success(
                source_identity=source,
                visit_key=visit,
                table_name="daily_course_record",
                strategy="updated_at",
                schema_version="v1",
                source_row_count=1,
            )
    session.commit()

    found = repository.get_many(
        source_identity="source-a",
        visit_keys=[visits[0]],
        table_names=["daily_course_record", "medical_order"],
    )

    assert len(found) == 1
    cursor = next(iter(found.values()))
    assert cursor.source_identity == "source-a"
    assert cursor.visit_id == "V1"
    assert cursor.table_name == "daily_course_record"


def test_database_upsert_does_not_move_watermark_backwards_with_stale_reader(
    monkeypatch,
):
    session, repository = _repository()
    visit = VisitKey("H1", "P1", "V1")
    latest = datetime(2026, 7, 31, 8, tzinfo=timezone.utc)
    common = {
        "source_identity": "source-a",
        "visit_key": visit,
        "table_name": "daily_course_record",
        "strategy": "updated_at",
        "schema_version": "v1",
        "watermark_column": "update_time",
    }
    repository.mark_success(**common, watermark_value=latest)
    # 模拟两个并发工作线程都在较新水位提交前读取到“无水位”。
    monkeypatch.setattr(repository, "get_many", lambda **_kwargs: {})
    repository.mark_success(**common, watermark_value=latest - timedelta(minutes=10))
    session.commit()

    monkeypatch.undo()
    cursor = next(
        iter(
            repository.get_many(
                source_identity="source-a",
                visit_keys=[visit],
                table_names=["daily_course_record"],
            ).values()
        )
    )
    assert cursor.watermark_value == latest


def test_rejects_strategy_outside_controlled_contract():
    _session, repository = _repository()

    try:
        repository.mark_success(
            source_identity="source-a",
            visit_key=VisitKey("H1", "P1", "V1"),
            table_name="daily_course_record",
            strategy="updated_at_watermark",
            schema_version="v1",
        )
    except ValueError as exc:
        assert "strategy 必须是" in str(exc)
    else:
        raise AssertionError("未受控的增量策略不应写入水位表")


def test_mark_full_sync_records_signature_and_preserves_full_sync_marker():
    session, repository = _repository()
    visit = VisitKey("H1", "P1", "V1")
    completed_at = datetime(2026, 7, 31, 9, tzinfo=timezone.utc)

    repository.mark_full_sync(
        source_identity="source-a",
        visit_key=visit,
        table_name="surgery_record",
        strategy="full_visit_reload",
        schema_version="v1",
        source_row_count=2,
        content_signature="sha256:content",
        job_id="job-full",
        succeeded_at=completed_at,
    )
    session.commit()

    cursor = next(
        iter(
            repository.get_many(
                source_identity="source-a",
                visit_keys=[visit],
                table_names=["surgery_record"],
            ).values()
        )
    )
    assert cursor.last_full_sync_at == completed_at
    assert cursor.last_success_at == completed_at
    assert cursor.source_row_count == 2
    assert cursor.content_signature == "sha256:content"
