"""在显式授权的隔离 PostgreSQL 中验证三坐标抽样与按比例分配。"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import MetaData, Table, create_engine, delete, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.database.models.qc import QCTask, QCTaskRecord, SysUser
from app.services import task_assignment_service as assignment
from app.services import task_sampling_persistence as sampling


TARGET_DB = "medqc_v36_validation_20260924"
TARGET_REVISION = "20260924_000051"


@pytest.fixture
def pg_engine():
    if os.getenv("MEDQC_PG_RACE_NONPROD_DB") != TARGET_DB:
        pytest.skip("explicit non-production database opt-in required")
    env_path = Path(__file__).resolve().parents[2] / ".env"
    raw_url = next(
        (line.split("=", 1)[1].strip().strip("\"'")
         for line in env_path.read_text(encoding="utf-8").splitlines()
         if line.startswith("DATABASE_URL=")),
        "",
    )
    if not raw_url:
        pytest.skip("backend/.env has no PostgreSQL connection")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("PostgreSQL is required")
    engine = create_engine(
        url.set(database=TARGET_DB), poolclass=NullPool,
        connect_args={"connect_timeout": 5, "options": "-csearch_path=qc,sys,cdm,public,legacy"},
    )
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == TARGET_DB
            assert conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one() == TARGET_REVISION
            assert conn.execute(text("SELECT current_schema()")).scalar_one() == "qc"
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def case_task(pg_engine, monkeypatch):
    marker = uuid.uuid4().hex
    task_id = str(uuid.uuid4())
    owner_id, qc_a, qc_b, doctor_id = (str(uuid.uuid4()) for _ in range(4))
    user_ids = (owner_id, qc_a, qc_b, doctor_id)
    refs = [
        {"institute_id": "SYNTH_ASSIGN", "patient_id": f"SYNTH_{marker}_{index}",
         "visit_id": f"VISIT_{marker}"}
        for index in (1, 2)
    ]
    factory = sessionmaker(bind=pg_engine)
    task_table = Table("qc_tasks", MetaData(), autoload_with=pg_engine)
    assert "attempt_count" in task_table.c
    monkeypatch.setattr(assignment, "SessionLocal", factory)
    monkeypatch.setattr(sampling, "SessionLocal", factory)
    try:
        with factory.begin() as session:
            session.add_all([
                SysUser(id=owner_id, username=f"synth_owner_{marker}", display_name="合成创建人",
                        role="doctor", is_active=True),
                SysUser(id=qc_a, username=f"synth_qca_{marker}", display_name="合成质控甲",
                        role="qc_staff", is_active=True),
                SysUser(id=qc_b, username=f"synth_qcb_{marker}", display_name="合成质控乙",
                        role="doctor", roles_json='["qc_staff"]', is_active=True),
                SysUser(id=doctor_id, username=f"synth_doctor_{marker}", display_name="合成非质控员",
                        role="doctor", is_active=True),
            ])
            session.execute(insert(task_table).values(
                id=task_id, task_number=f"SYNTH-{marker}", task_name="合成比例分配任务",
                task_type="one_time", scene="outpatient", status="draft", creator_id=owner_id,
                record_refs=refs, record_ids=None, sampling_method="all", assign_method="by_ratio",
                progress=0, total_records=0, completed_records=0, attempt_count=0,
                created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
            ))
        yield factory, task_id, owner_id, qc_a, qc_b, doctor_id, refs
    finally:
        with factory.begin() as session:
            session.execute(delete(QCTaskRecord).where(QCTaskRecord.task_id == task_id))
            session.execute(delete(QCTask).where(QCTask.id == task_id))
            session.execute(delete(SysUser).where(SysUser.id.in_(user_ids)))


def _snapshot(factory, task_id):
    with factory() as session:
        return dict(session.execute(
            select(QCTask.__table__).where(QCTask.id == task_id)
        ).mappings().one())


def _rows(factory, task_id):
    with factory() as session:
        return [dict(row) for row in session.execute(
            select(QCTaskRecord.__table__).where(QCTaskRecord.task_id == task_id)
            .order_by(QCTaskRecord.created_at, QCTaskRecord.id)
        ).mappings().all()]


def test_real_pg_sample_assignment_replay_and_authority(case_task):
    factory, task_id, owner_id, qc_a, qc_b, doctor_id, refs = case_task
    saved = sampling.save_task_sample(_snapshot(factory, task_id), refs, actor_id=owner_id)
    assert saved["sampled_count"] == 2
    assert saved["record_id_semantics"] == "association_id_not_medical_record_id"
    original_rows = _rows(factory, task_id)
    assert len(original_rows) == 2
    assert {(row["institute_id"], row["patient_id"], row["visit_id"]) for row in original_rows} == {
        (ref["institute_id"], ref["patient_id"], ref["visit_id"]) for ref in refs
    }
    assert all(row["id"] == row["record_id"] and row["assignee_id"] is None for row in original_rows)

    assignees = [
        {"user_id": qc_a, "user_name": "伪造甲"},
        {"user_id": qc_b, "user_name": "伪造乙"},
    ]
    with pytest.raises(assignment.AssignmentForbidden):
        assignment.assign_task_records(
            task_id=task_id, actor_id=doctor_id, assignees=assignees, method="by_ratio"
        )
    with pytest.raises(assignment.AssignmentConflict, match="有效质控员"):
        assignment.assign_task_records(
            task_id=task_id, actor_id=owner_id,
            assignees=[{"user_id": doctor_id, "user_name": "合成非质控员"}], method="by_ratio",
        )
    assert all(row["assignee_id"] is None for row in _rows(factory, task_id))

    result = assignment.assign_task_records(
        task_id=task_id, actor_id=owner_id, assignees=assignees, method="by_ratio"
    )
    assert result["total_assigned"] == 2 and result["idempotent"] is False
    assert result["assignment_details"] == [
        {"user_id": qc_a, "user_name": "合成质控甲", "count": 1},
        {"user_id": qc_b, "user_name": "合成质控乙", "count": 1},
    ]
    assigned_rows = _rows(factory, task_id)
    assert [row["assignee_id"] for row in assigned_rows] == [qc_a, qc_b]
    assert _snapshot(factory, task_id)["status"] == "assigned"
    replay = assignment.assign_task_records(
        task_id=task_id, actor_id=owner_id, assignees=assignees, method="by_ratio"
    )
    assert replay["idempotent"] is True
    assert _rows(factory, task_id) == assigned_rows
    with pytest.raises(assignment.AssignmentConflict, match="不同计划"):
        assignment.assign_task_records(
            task_id=task_id, actor_id=owner_id, assignees=list(reversed(assignees)), method="by_ratio"
        )


def test_real_pg_status_drift_fails_closed(case_task):
    factory, task_id, owner_id, qc_a, _qc_b, _doctor_id, refs = case_task
    sampling.save_task_sample(_snapshot(factory, task_id), refs, actor_id=owner_id)
    with factory.begin() as session:
        session.execute(update(QCTask).where(QCTask.id == task_id).values(status="running"))
    with pytest.raises(assignment.AssignmentConflict, match="状态"):
        assignment.assign_task_records(
            task_id=task_id, actor_id=owner_id,
            assignees=[{"user_id": qc_a, "user_name": "合成质控甲"}], method="by_ratio",
        )
    assert all(row["assignee_id"] is None for row in _rows(factory, task_id))


def test_real_pg_concurrent_same_plan_serializes(case_task):
    factory, task_id, owner_id, qc_a, qc_b, _doctor_id, refs = case_task
    sampling.save_task_sample(_snapshot(factory, task_id), refs, actor_id=owner_id)
    assignees = [
        {"user_id": qc_a, "user_name": "合成质控甲"},
        {"user_id": qc_b, "user_name": "合成质控乙"},
    ]
    barrier = Barrier(2)

    def assign_once():
        barrier.wait(timeout=5)
        return assignment.assign_task_records(
            task_id=task_id, actor_id=owner_id, assignees=assignees, method="by_ratio"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(assign_once) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(result["idempotent"] for result in results) == [False, True]
    assert all(result["total_assigned"] == 2 for result in results)
    assert len(_rows(factory, task_id)) == 2
    assert [row["assignee_id"] for row in _rows(factory, task_id)] == [qc_a, qc_b]
