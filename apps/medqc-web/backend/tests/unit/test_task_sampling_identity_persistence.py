from __future__ import annotations

import json
from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.services import task_sampling_persistence as persistence


def save_sample(snapshot, records, *, actor_id="qc-user"):
    return persistence.save_task_sample(snapshot, records, actor_id=actor_id)


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks", metadata,
        Column("id", String, primary_key=True),
        Column("creator_id", String),
        Column("scene", String),
        Column("status", String, nullable=False),
        Column("total_records", Integer, nullable=False),
        Column("date_range", Text),
        Column("department_filter", Text),
        Column("record_ids", Text),
        Column("record_refs", Text),
        Column("sampling_method", String),
        Column("sampling_config", Text),
        Column("updated_at", String),
    )
    records = Table(
        "qc_task_records", metadata,
        Column("id", String, primary_key=True),
        Column("task_id", String, nullable=False),
        Column("record_id", String, nullable=False),
        Column("institute_id", String),
        Column("patient_id", String),
        Column("visit_id", String),
        Column("assignee_id", String),
        Column("assignee_name", String),
        Column("status", String, nullable=False),
        Column("defect_count", Integer, nullable=False),
        Column("created_at", String, nullable=False),
        Column("department", String),
    )
    metadata.create_all(engine)
    monkeypatch.setattr(persistence, "SessionLocal", sessionmaker(bind=engine, future=True))
    yield engine, tasks, records
    engine.dispose()


def snapshot(**overrides):
    value = {
        "id": "task-1", "creator_id": "qc-user", "scene": "outpatient", "status": "draft", "total_records": 0,
        "date_range": None, "department_filter": [], "record_ids": [],
        "record_refs": [], "sampling_method": "all", "sampling_config": {},
        "updated_at": "2026-09-23T00:00:00",
    }
    value.update(overrides)
    return value


def case(institute="h1", patient="p1", visit="v1"):
    return {"institute_id": institute, "patient_id": patient, "visit_id": visit}


def insert_task(engine, tasks, value):
    stored = dict(value)
    for field in ("date_range", "department_filter", "record_ids", "record_refs", "sampling_config"):
        if not isinstance(stored[field], str):
            stored[field] = json.dumps(stored[field], ensure_ascii=False)
    with engine.begin() as connection:
        connection.execute(tasks.insert().values(**stored))


def state(engine, tasks, records):
    with engine.connect() as connection:
        task = connection.execute(select(tasks)).mappings().one()
        saved = connection.execute(select(records).order_by(records.c.created_at)).mappings().all()
    return dict(task), [dict(row) for row in saved]


@contextmanager
def fail_statement(engine, prefix):
    def fail(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(prefix):
            raise RuntimeError("forced statement failure")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        yield
    finally:
        event.remove(engine, "before_cursor_execute", fail)


def test_same_visit_in_different_hospital_and_patient_are_distinct(database):
    engine, tasks, records = database
    task = snapshot()
    insert_task(engine, tasks, task)
    identities = [case(), case("h2", "p1", "v1"), case("h1", "p2", "v1")]

    first = save_sample(task, identities)
    replay = save_sample(task, [case("ignored", "ignored", "ignored")])

    stored_task, saved = state(engine, tasks, records)
    assert stored_task["status"] == "sampling" and stored_task["total_records"] == 3
    assert first == replay
    assert [(row["institute_id"], row["patient_id"], row["visit_id"]) for row in saved] == [
        ("h1", "p1", "v1"), ("h2", "p1", "v1"), ("h1", "p2", "v1")
    ]
    assert all(row["record_id"] == row["id"] for row in saved)
    assert first["record_id_semantics"] == "association_id_not_medical_record_id"


@pytest.mark.parametrize("selected", [[case(), case()], [case("h1", "p1", " ")], [{"visit_id": "v1"}]])
def test_duplicate_or_incomplete_coordinate_rolls_back(database, selected):
    engine, tasks, records = database
    task = snapshot()
    insert_task(engine, tasks, task)

    with pytest.raises(persistence.SamplingConflict):
        save_sample(task, selected)

    locked, saved = state(engine, tasks, records)
    assert locked["status"] == "draft" and saved == []


def test_explicit_refs_limit_selection_and_snapshot_is_locked(database):
    engine, tasks, records = database
    task = snapshot(record_refs=[case()])
    insert_task(engine, tasks, task)

    with pytest.raises(persistence.SamplingConflict, match="不属于"):
        save_sample(task, [case("h2")])
    with pytest.raises(persistence.SamplingConflict, match="record_refs"):
        save_sample(snapshot(record_refs=[case("h2")]), [case()])

    locked, saved = state(engine, tasks, records)
    assert locked["status"] == "draft" and saved == []
    result = save_sample(task, [case()])
    assert result["sampled_count"] == 1


def test_modern_replay_rejects_changed_refs_and_count(database):
    engine, tasks, records = database
    task = snapshot(record_refs=[case()])
    insert_task(engine, tasks, task)
    save_sample(task, [case()])
    with pytest.raises(persistence.SamplingConflict, match="record_refs"):
        save_sample(snapshot(record_refs=[case("h2")]), [])
    with engine.begin() as connection:
        connection.execute(tasks.update().values(total_records=2))
    with pytest.raises(persistence.SamplingConflict, match="数量与已保存关联不一致"):
        save_sample(task, [])
    _locked, saved = state(engine, tasks, records)
    assert len(saved) == 1


def test_replay_rejects_legacy_row_even_when_count_matches(database):
    engine, tasks, records = database
    task = snapshot(status="sampling", total_records=1)
    insert_task(engine, tasks, task)
    with engine.begin() as connection:
        connection.execute(records.insert().values(
            id="old", task_id="task-1", record_id="medical-id", status="pending",
            defect_count=0, created_at="2026-09-23T00:00:00",
        ))

    with pytest.raises(persistence.SamplingConflict, match="三坐标"):
        save_sample(task, [])


def test_modern_rejects_legacy_record_ids(database):
    engine, tasks, records = database
    task = snapshot(record_ids=["v1"])
    insert_task(engine, tasks, task)
    with pytest.raises(persistence.SamplingConflict, match="record_ids"):
        save_sample(task, [case()])
    locked, saved = state(engine, tasks, records)
    assert locked["status"] == "draft" and saved == []


def test_zero_sample_saves_and_replays(database):
    engine, tasks, records = database
    task = snapshot()
    insert_task(engine, tasks, task)
    first = save_sample(task, [])
    second = save_sample(task, [case()])
    locked, saved = state(engine, tasks, records)
    assert first == second
    assert first["sampled_count"] == 0 and first["records"] == []
    assert locked["status"] == "sampling" and saved == []


@pytest.mark.parametrize("prefix", ["INSERT INTO QC_TASK_RECORDS", "UPDATE QC_TASKS"])
def test_insert_or_update_failure_rolls_back(database, prefix):
    engine, tasks, records = database
    task = snapshot()
    insert_task(engine, tasks, task)
    with fail_statement(engine, prefix), pytest.raises(RuntimeError, match="forced"):
        save_sample(task, [case()])
    locked, saved = state(engine, tasks, records)
    assert locked["status"] == "draft" and saved == []


def test_missing_record_refs_column_fails_closed(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks", metadata, Column("id", String, primary_key=True), Column("creator_id", String), Column("scene", String),
        Column("status", String), Column("total_records", Integer), Column("date_range", Text),
        Column("department_filter", Text), Column("record_ids", Text), Column("sampling_method", String),
        Column("sampling_config", Text), Column("updated_at", String),
    )
    metadata.create_all(engine)
    monkeypatch.setattr(persistence, "SessionLocal", sessionmaker(bind=engine, future=True))
    stored = snapshot()
    stored.pop("record_refs")
    with engine.begin() as connection:
        connection.execute(tasks.insert().values(**{
            key: json.dumps(value) if key in {"department_filter", "record_ids", "sampling_config"}
            else value for key, value in stored.items()
        }))
    with pytest.raises(persistence.SamplingConflict, match="缺少三坐标配置列"):
        save_sample(snapshot(), [case()])
    engine.dispose()


def test_missing_coordinate_columns_fail_before_write(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks", metadata, Column("id", String, primary_key=True), Column("creator_id", String), Column("scene", String),
        Column("status", String), Column("total_records", Integer), Column("date_range", Text),
        Column("department_filter", Text), Column("record_ids", Text), Column("record_refs", Text),
        Column("sampling_method", String), Column("sampling_config", Text), Column("updated_at", String),
    )
    records = Table(
        "qc_task_records", metadata, Column("id", String, primary_key=True),
        Column("task_id", String), Column("record_id", String), Column("created_at", String),
    )
    metadata.create_all(engine)
    monkeypatch.setattr(persistence, "SessionLocal", sessionmaker(bind=engine, future=True))
    insert_task(engine, tasks, snapshot())
    with pytest.raises(Exception, match="no such column"):
        save_sample(snapshot(), [case()])
    locked, saved = state(engine, tasks, records)
    assert locked["status"] == "draft" and saved == []
    engine.dispose()


def test_postgresql_modern_path_uses_configured_search_path_before_lock(monkeypatch):
    statements = []

    class StopBeforeDatabase(Exception):
        pass

    class FakeSession:
        bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def begin(self):
            return nullcontext()

        def execute(self, statement):
            statements.append(str(statement))
            raise StopBeforeDatabase()

        def close(self):
            pass

    monkeypatch.setattr(persistence, "SessionLocal", FakeSession)
    with pytest.raises(StopBeforeDatabase):
        save_sample(snapshot(), [case()])

    assert len(statements) == 1
    assert "FOR UPDATE" in statements[0]
