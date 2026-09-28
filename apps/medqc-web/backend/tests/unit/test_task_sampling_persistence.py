from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app.services import task_sampling_persistence as persistence


def save_sample(snapshot, records, *, actor_id="qc-user"):
    return persistence.save_task_sample(snapshot, records, actor_id=actor_id)


@pytest.fixture
def database(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks",
        metadata,
        Column("id", String, primary_key=True),
        Column("creator_id", String),
        Column("scene", String),
        Column("status", String, nullable=False),
        Column("total_records", Integer, nullable=False, default=0),
        Column("date_range", Text),
        Column("department_filter", Text),
        Column("record_ids", Text),
        Column("sampling_method", String),
        Column("sampling_config", Text),
        Column("updated_at", String),
    )
    records = Table(
        "qc_task_records",
        metadata,
        Column("id", String, primary_key=True),
        Column("task_id", String, nullable=False),
        Column("record_id", String, nullable=False),
        Column("assignee_id", String),
        Column("assignee_name", String),
        Column("status", String, nullable=False),
        Column("defect_count", Integer, nullable=False),
        Column("created_at", String, nullable=False),
    )
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(persistence, "SessionLocal", factory)
    yield engine, factory, tasks, records
    engine.dispose()


def task_snapshot(task_id: str = "task-1", **overrides):
    task = {
        "id": task_id,
        "creator_id": "qc-user",
        "scene": None,
        "status": "draft",
        "total_records": 0,
        "date_range": {"start": "2026-09-01", "end": "2026-09-22"},
        "department_filter": ["内科"],
        "record_ids": [],
        "sampling_method": "all",
        "sampling_config": {},
        "updated_at": "2026-09-22T08:00:00",
    }
    task.update(overrides)
    return task


def insert_task(engine, tasks, task: dict):
    stored = dict(task)
    for field in ("date_range", "department_filter", "record_ids", "sampling_config"):
        if not isinstance(stored.get(field), str):
            stored[field] = json.dumps(stored.get(field), ensure_ascii=False)
    with engine.begin() as connection:
        connection.execute(tasks.insert().values(**stored))


def read_state(engine, tasks, records, task_id="task-1"):
    with engine.connect() as connection:
        task = connection.execute(select(tasks).where(tasks.c.id == task_id)).mappings().first()
        saved = connection.execute(
            select(records).where(records.c.task_id == task_id).order_by(records.c.created_at, records.c.id)
        ).mappings().all()
    return dict(task) if task else None, [dict(item) for item in saved]


@contextmanager
def fail_statement(engine, prefix: str):
    def before_cursor_execute(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith(prefix):
            raise RuntimeError(f"forced {prefix} failure")

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_successfully_saves_records_and_task_state(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)

    result = save_sample(snapshot, [{"id": "r-1"}, {"record_id": "r-2"}])

    task, saved = read_state(engine, tasks, records)
    assert result["task_id"] == "task-1"
    assert result["sampled_count"] == 2
    assert {item["record_id"] for item in result["records"]} == {"r-1", "r-2"}
    assert task["status"] == "sampling" and task["total_records"] == 2
    assert {item["record_id"] for item in saved} == {"r-1", "r-2"}
    assert all(
        item["status"] == "pending"
        and item["assignee_id"] is None
        and item["defect_count"] == 0
        for item in saved
    )


def test_transaction_guard_runs_before_task_write_in_same_transaction(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)
    guarded = []

    def guard(session):
        guarded.append(session.execute(select(tasks.c.id).where(tasks.c.id == "task-1")).scalar_one())

    result = persistence.save_task_sample(
        snapshot,
        [{"id": "r-1"}],
        actor_id="qc-user",
        transaction_guard=guard,
    )

    task, saved = read_state(engine, tasks, records)
    assert guarded == ["task-1"]
    assert result["sampled_count"] == 1
    assert task["status"] == "sampling" and len(saved) == 1


def test_transaction_guard_rejection_leaves_task_and_records_unchanged(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)

    def reject(_session):
        raise persistence.SamplingConflict("运行租约已失效")

    with pytest.raises(persistence.SamplingConflict, match="租约已失效"):
        persistence.save_task_sample(
            snapshot,
            [{"id": "r-1"}],
            actor_id="qc-user",
            transaction_guard=reject,
        )

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and task["total_records"] == 0
    assert saved == []


@pytest.mark.parametrize(
    ("creator_id", "actor_id"),
    [("another-user", "qc-user"), (None, "qc-user"), ("", "qc-user"), ("qc-user", "")],
)
def test_locked_owner_rejects_unauthorized_sample_without_writes(database, creator_id, actor_id):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot(creator_id=creator_id)
    insert_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingForbidden, match="仅任务创建人"):
        save_sample(snapshot, [{"id": "r-1"}], actor_id=actor_id)

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and task["total_records"] == 0
    assert saved == []


def test_owner_changed_after_route_snapshot_fails_inside_transaction(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)
    with engine.begin() as connection:
        connection.execute(tasks.update().where(tasks.c.id == "task-1").values(creator_id="another-user"))

    with pytest.raises(persistence.SamplingForbidden, match="仅任务创建人"):
        save_sample(snapshot, [{"id": "r-1"}])

    task, saved = read_state(engine, tasks, records)
    assert task["creator_id"] == "another-user" and task["status"] == "draft"
    assert saved == []


def test_non_creator_cannot_replay_saved_sample(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)
    saved_result = save_sample(snapshot, [{"id": "r-1"}])

    with pytest.raises(persistence.SamplingForbidden, match="仅任务创建人"):
        save_sample(snapshot, [], actor_id="another-user")

    task, saved = read_state(engine, tasks, records)
    assert saved_result["sampled_count"] == len(saved) == 1
    assert task["status"] == "sampling"


def test_zero_records_is_committed_as_replayable_sampling(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)

    first = save_sample(snapshot, [])
    second = save_sample(snapshot, [{"id": "ignored-on-replay"}])

    task, saved = read_state(engine, tasks, records)
    assert first == second == {"task_id": "task-1", "sampled_count": 0, "records": []}
    assert task["status"] == "sampling" and task["total_records"] == 0
    assert saved == []


def test_response_is_limited_to_first_twenty_records(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)

    result = save_sample(snapshot, [{"id": f"r-{index:02d}"} for index in range(25)])
    replay = save_sample(snapshot, [{"id": "ignored"}])

    task, saved = read_state(engine, tasks, records)
    assert result["sampled_count"] == 25 and len(result["records"]) == 20
    assert replay == result
    assert task["total_records"] == len(saved) == 25


@pytest.mark.parametrize("prefix", ["INSERT INTO QC_TASK_RECORDS", "UPDATE QC_TASKS"])
def test_statement_failure_rolls_back_all_changes(database, prefix):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)

    with fail_statement(engine, prefix), pytest.raises(RuntimeError, match="forced"):
        save_sample(snapshot, [{"id": "r-1"}])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and task["total_records"] == 0
    assert saved == []


@pytest.mark.parametrize(
    ("trigger_name", "timing"),
    [
        ("ignore_record_insert", "BEFORE INSERT ON qc_task_records"),
        ("ignore_task_update", "BEFORE UPDATE ON qc_tasks"),
    ],
)
def test_zero_affected_rows_is_rejected_and_rolled_back(database, trigger_name, timing):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"CREATE TRIGGER {trigger_name} {timing} BEGIN SELECT RAISE(IGNORE); END"
        )

    with pytest.raises(RuntimeError, match="写入数量不完整|状态更新失败"):
        save_sample(snapshot, [{"id": "r-1"}])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and task["total_records"] == 0
    assert saved == []


def test_commit_failure_rolls_back_all_changes(database, monkeypatch):
    engine, factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)

    def failing_factory():
        session = factory()

        def fail_commit(_session):
            raise RuntimeError("forced commit failure")

        event.listen(session, "before_commit", fail_commit, once=True)
        return session

    monkeypatch.setattr(persistence, "SessionLocal", failing_factory)
    with pytest.raises(RuntimeError, match="forced commit failure"):
        save_sample(snapshot, [{"id": "r-1"}])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and task["total_records"] == 0
    assert saved == []


def test_sampling_replay_returns_saved_ids_without_writes_or_snapshot_comparison(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot(status="sampling", total_records=2)
    insert_task(engine, tasks, snapshot)
    existing = [
        {
            "id": "saved-1",
            "task_id": "task-1",
            "record_id": "r-1",
            "assignee_id": None,
            "assignee_name": None,
            "status": "pending",
            "defect_count": 0,
            "created_at": "2026-09-22T08:00:00",
        },
        {
            "id": "saved-2",
            "task_id": "task-1",
            "record_id": "r-2",
            "assignee_id": None,
            "assignee_name": None,
            "status": "pending",
            "defect_count": 0,
            "created_at": "2026-09-22T08:00:01",
        },
    ]
    with engine.begin() as connection:
        connection.execute(records.insert(), existing)

    replay = save_sample(
        task_snapshot(sampling_method="percentage", sampling_config={"percentage": 99}),
        [{"id": "must-not-be-written"}],
    )

    _task, saved = read_state(engine, tasks, records)
    assert replay["sampled_count"] == 2
    assert [item["id"] for item in replay["records"]] == ["saved-1", "saved-2"]
    assert [item["id"] for item in saved] == ["saved-1", "saved-2"]


def test_sampling_replay_rejects_count_mismatch(database):
    engine, _factory, tasks, records = database
    insert_task(engine, tasks, task_snapshot(status="sampling", total_records=1))

    with pytest.raises(persistence.SamplingConflict, match="数量与已保存关联不一致"):
        save_sample(task_snapshot(), [])

    _task, saved = read_state(engine, tasks, records)
    assert saved == []


def test_sampling_snapshot_cannot_overwrite_task_changed_back_to_draft(database):
    engine, _factory, tasks, records = database
    locked_task = task_snapshot(status="draft")
    insert_task(engine, tasks, locked_task)
    stale_snapshot = task_snapshot(status="sampling")

    with pytest.raises(persistence.SamplingConflict, match="任务状态已变化"):
        save_sample(stale_snapshot, [])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and task["total_records"] == 0
    assert saved == []


def test_draft_with_legacy_records_is_rejected_without_changes(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)
    legacy = {
        "id": "legacy",
        "task_id": "task-1",
        "record_id": "r-old",
        "assignee_id": None,
        "assignee_name": None,
        "status": "pending",
        "defect_count": 0,
        "created_at": "2026-09-22T08:00:00",
    }
    with engine.begin() as connection:
        connection.execute(records.insert().values(**legacy))

    with pytest.raises(persistence.SamplingConflict, match="已存在抽样关联"):
        save_sample(snapshot, [{"id": "r-new"}])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and [item["id"] for item in saved] == ["legacy"]


def test_missing_task_uses_narrow_not_found_exception(database):
    with pytest.raises(persistence.SamplingTaskNotFound):
        save_sample(task_snapshot("missing"), [])


@pytest.mark.parametrize("status", ["assigned", "in_progress", "completed", "cancelled"])
def test_non_draft_status_is_rejected(database, status):
    engine, _factory, tasks, records = database
    insert_task(engine, tasks, task_snapshot(status=status))

    with pytest.raises(persistence.SamplingConflict, match="不允许执行抽样"):
        save_sample(task_snapshot(status=status), [{"id": "r-1"}])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == status and saved == []


def test_unknown_scene_is_rejected_before_writes(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot(scene="unknown")
    insert_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingConflict, match="场景抽样暂不可用"):
        save_sample(snapshot, [{"id": "r-1"}])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []


def test_unknown_scene_is_also_rejected_for_sampling_replay(database):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot(scene="unknown", status="sampling", total_records=0)
    insert_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingConflict, match="场景抽样暂不可用"):
        save_sample(snapshot, [])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "sampling" and saved == []


@pytest.mark.parametrize(
    ("field", "changed_value"),
    [
        ("scene", "running"),
        ("date_range", {"start": "2026-09-02", "end": "2026-09-22"}),
        ("department_filter", ["外科"]),
        ("record_ids", ["r-fixed"]),
        ("sampling_method", "percentage"),
        ("sampling_config", {"percentage": 20}),
    ],
)
def test_snapshot_drift_is_rejected_for_every_authoritative_field(
    database, field, changed_value
):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)
    snapshot[field] = changed_value
    with pytest.raises(persistence.SamplingConflict, match=field):
        save_sample(snapshot, [])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []


@pytest.mark.parametrize(
    "candidate_records",
    [[{"name": "missing"}], [{"id": "  "}], [{"id": "r-1"}, {"id": "r-1"}]],
)
def test_candidate_ids_must_be_nonempty_and_unique(database, candidate_records):
    engine, _factory, tasks, records = database
    snapshot = task_snapshot()
    insert_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingConflict):
        save_sample(snapshot, candidate_records)

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []


def test_legacy_task_table_without_scene_column_remains_compatible(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks",
        metadata,
        Column("id", String, primary_key=True),
        Column("creator_id", String),
        Column("status", String, nullable=False),
        Column("total_records", Integer, nullable=False),
        Column("date_range", Text),
        Column("department_filter", Text),
        Column("record_ids", Text),
        Column("sampling_method", String),
        Column("sampling_config", Text),
        Column("updated_at", String),
    )
    records = Table(
        "qc_task_records",
        metadata,
        Column("id", String, primary_key=True),
        Column("task_id", String, nullable=False),
        Column("record_id", String, nullable=False),
        Column("assignee_id", String),
        Column("assignee_name", String),
        Column("status", String, nullable=False),
        Column("defect_count", Integer, nullable=False),
        Column("created_at", String, nullable=False),
    )
    metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(persistence, "SessionLocal", factory)
    snapshot = task_snapshot()
    stored = {key: value for key, value in snapshot.items() if key != "scene"}
    for field in ("date_range", "department_filter", "record_ids", "sampling_config"):
        stored[field] = json.dumps(stored[field], ensure_ascii=False)
    with engine.begin() as connection:
        connection.execute(tasks.insert().values(**stored))

    result = save_sample(snapshot, [{"id": "r-1"}])

    task, saved = read_state(engine, tasks, records)
    assert result["sampled_count"] == 1
    assert task["status"] == "sampling" and len(saved) == 1
    engine.dispose()


def test_lock_statement_compiles_to_postgresql_for_update():
    sql = str(
        persistence._lock_task_statement("task-1").compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )

    assert "SELECT *" in sql
    assert "FROM qc_tasks" in sql
    assert "FOR UPDATE" in sql


@pytest.fixture
def modern_database(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks", metadata,
        Column("id", String, primary_key=True),
        Column("creator_id", String), Column("scene", String),
        Column("status", String), Column("total_records", Integer),
        Column("date_range", Text), Column("department_filter", Text),
        Column("record_ids", Text), Column("record_refs", Text),
        Column("sampling_method", String), Column("sampling_config", Text),
        Column("updated_at", String),
    )
    records = Table(
        "qc_task_records", metadata,
        Column("id", String, primary_key=True), Column("task_id", String),
        Column("record_id", String), Column("institute_id", String),
        Column("patient_id", String), Column("visit_id", String),
        Column("assignee_id", String), Column("assignee_name", String),
        Column("status", String), Column("defect_count", Integer),
        Column("created_at", String), Column("department", String),
    )
    metadata.create_all(engine)
    monkeypatch.setattr(persistence, "SessionLocal", sessionmaker(bind=engine, future=True))
    yield engine, tasks, records
    engine.dispose()


def modern_snapshot(scene: str, **overrides):
    value = task_snapshot(
        scene=scene, date_range=None, department_filter=[], record_refs=[],
    )
    value.update(overrides)
    return value


def modern_case(institute="hospital-1", patient="patient-1", visit="visit-1"):
    return {"institute_id": institute, "patient_id": patient, "visit_id": visit}


def insert_modern_task(engine, tasks, snapshot):
    stored = dict(snapshot)
    for field in ("date_range", "department_filter", "record_ids", "record_refs", "sampling_config"):
        stored[field] = json.dumps(stored[field], ensure_ascii=False)
    with engine.begin() as connection:
        connection.execute(tasks.insert().values(**stored))


@pytest.mark.parametrize("scene", ["running", "final"])
def test_clinical_scene_saves_coordinates_and_replays(modern_database, scene):
    engine, tasks, records = modern_database
    snapshot = modern_snapshot(scene)
    insert_modern_task(engine, tasks, snapshot)
    selected = [modern_case(), modern_case("hospital-2")]

    first = save_sample(snapshot, selected)
    replay = save_sample(snapshot, [modern_case("ignored")])

    task, saved = read_state(engine, tasks, records)
    assert first == replay
    assert first["sampled_count"] == task["total_records"] == 2
    assert first["record_id_semantics"] == "association_id_not_medical_record_id"
    assert task["status"] == "sampling"
    assert [(row["institute_id"], row["patient_id"], row["visit_id"]) for row in saved] == [
        ("hospital-1", "patient-1", "visit-1"),
        ("hospital-2", "patient-1", "visit-1"),
    ]
    assert all(row["id"] == row["record_id"] and row["status"] == "pending" for row in saved)


@pytest.mark.parametrize("scene", ["running", "final"])
@pytest.mark.parametrize(
    "selected",
    [[modern_case(), modern_case()], [modern_case(visit=" ")], [{"visit_id": "visit-1"}]],
)
def test_clinical_scene_rejects_duplicate_or_missing_coordinates(modern_database, scene, selected):
    engine, tasks, records = modern_database
    snapshot = modern_snapshot(scene)
    insert_modern_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingConflict, match="三坐标"):
        save_sample(snapshot, selected)

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []


@pytest.mark.parametrize("scene", ["running", "final"])
def test_clinical_scene_rejects_out_of_scope_refs_and_snapshot_drift(modern_database, scene):
    engine, tasks, records = modern_database
    snapshot = modern_snapshot(scene, record_refs=[modern_case()])
    insert_modern_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingConflict, match="不属于"):
        save_sample(snapshot, [modern_case("hospital-2")])
    with pytest.raises(persistence.SamplingConflict, match="record_refs"):
        save_sample(modern_snapshot(scene, record_refs=[modern_case("hospital-2")]), [modern_case()])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []


@pytest.mark.parametrize("scene", ["running", "final"])
def test_clinical_scene_rejects_legacy_record_ids(modern_database, scene):
    engine, tasks, records = modern_database
    snapshot = modern_snapshot(scene, record_ids=["legacy-record"])
    insert_modern_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingConflict, match="record_ids"):
        save_sample(snapshot, [modern_case()])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []


@pytest.mark.parametrize("scene", ["running", "final"])
def test_clinical_scene_creator_and_replay_snapshot_contract(modern_database, scene):
    engine, tasks, records = modern_database
    snapshot = modern_snapshot(scene, record_refs=[modern_case()])
    insert_modern_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingForbidden, match="仅任务创建人"):
        save_sample(snapshot, [modern_case()], actor_id="another-user")
    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []

    save_sample(snapshot, [modern_case()])
    with pytest.raises(persistence.SamplingConflict, match="record_refs"):
        save_sample(modern_snapshot(scene, record_refs=[modern_case("hospital-2")]), [])
    with pytest.raises(persistence.SamplingForbidden, match="仅任务创建人"):
        save_sample(snapshot, [], actor_id="another-user")
    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "sampling" and len(saved) == 1


@pytest.mark.parametrize("scene", ["running", "final"])
def test_clinical_scene_missing_coordinate_columns_fail_before_write(monkeypatch, scene):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata = MetaData()
    tasks = Table(
        "qc_tasks", metadata,
        Column("id", String, primary_key=True), Column("creator_id", String),
        Column("scene", String), Column("status", String), Column("total_records", Integer),
        Column("date_range", Text), Column("department_filter", Text),
        Column("record_ids", Text), Column("record_refs", Text),
        Column("sampling_method", String), Column("sampling_config", Text),
        Column("updated_at", String),
    )
    records = Table(
        "qc_task_records", metadata,
        Column("id", String, primary_key=True), Column("task_id", String),
        Column("record_id", String), Column("created_at", String),
    )
    metadata.create_all(engine)
    monkeypatch.setattr(persistence, "SessionLocal", sessionmaker(bind=engine, future=True))
    snapshot = modern_snapshot(scene)
    insert_modern_task(engine, tasks, snapshot)

    with pytest.raises(Exception, match="no such column"):
        save_sample(snapshot, [modern_case()])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []
    engine.dispose()


@pytest.mark.parametrize("scene", ["running", "final", "outpatient"])
def test_modern_sample_persists_trimmed_department_and_blank_as_null(modern_database, scene):
    engine, tasks, records = modern_database
    snapshot = modern_snapshot(scene)
    insert_modern_task(engine, tasks, snapshot)
    selected = [
        {**modern_case(visit="v-1"), "department": "  内科 "},
        {**modern_case(visit="v-2"), "department": "   "},
        {**modern_case(visit="v-3"), "department": ""},
        modern_case(visit="v-4"),
        {**modern_case(visit="v-5"), "department": None},
    ]

    save_sample(snapshot, selected)

    _, saved = read_state(engine, tasks, records)
    assert [row["department"] for row in saved] == ["内科", None, None, None, None]


def test_modern_sample_rejects_overlong_department_without_writes(modern_database):
    engine, tasks, records = modern_database
    snapshot = modern_snapshot("running")
    insert_modern_task(engine, tasks, snapshot)

    with pytest.raises(persistence.SamplingConflict, match="科室"):
        save_sample(snapshot, [{**modern_case(), "department": "科" * 101}])

    task, saved = read_state(engine, tasks, records)
    assert task["status"] == "draft" and saved == []
