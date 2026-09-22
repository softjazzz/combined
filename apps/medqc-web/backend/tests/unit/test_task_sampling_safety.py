"""抽样失败不能伪造候选、落关联或返回成功。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import supabase_client
from app.core.security import get_current_user
from app.routers import tasks
from app.services.task_sampling_service import TaskSamplingService


class Database:
    def __init__(self, task=None, records=None, fail=None):
        self.task = {"status": "draft", **task} if task is not None else None
        self.records = records or []
        self.fail = fail
        self.calls = []
        self.writes = []
        self.save_calls = []
        self.save_error = None
        self.saved_result = None

    def table(self, name):
        return Query(self, name)


class Query:
    def __init__(self, db, table):
        self.db, self.table = db, table
        self.operation = "select"
        self.payload = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def in_(self, *_args):
        return self

    def gte(self, *_args):
        return self

    def lte(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def single(self):
        return self

    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.operation, self.payload = "update", payload
        return self

    def execute(self):
        key = (self.table, self.operation)
        self.db.calls.append(key)
        if self.db.fail == key:
            raise RuntimeError("internal database connection detail")
        if self.operation != "select":
            self.db.writes.append((key, self.payload))
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=self.db.task if self.table == "qc_tasks" else self.db.records)


def wire(monkeypatch, db):
    from app.services import task_sampling_persistence

    async def execute(query):
        return query.execute()

    def save(task, records):
        db.save_calls.append((task, records))
        if db.save_error is not None:
            raise db.save_error
        if db.fail in {("qc_task_records", "insert"), ("qc_tasks", "update")}:
            raise RuntimeError("internal database persistence detail")
        return db.saved_result or {
            "task_id": task["id"],
            "sampled_count": len(records),
            "records": records[:20],
        }

    monkeypatch.setattr(task_sampling_persistence, "save_task_sample", save)
    monkeypatch.setattr(supabase_client, "get_supabase", lambda: db)
    monkeypatch.setattr(supabase_client, "async_execute", execute)
    monkeypatch.setattr(tasks, "get_supabase", lambda: db)
    monkeypatch.setattr(tasks, "async_execute", execute)
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "qc-user", "roles": ["admin"]}
    return TestClient(app)


@pytest.mark.parametrize("scene", ["running", "final", "outpatient", "invalid", ""])
@pytest.mark.asyncio
async def test_scoped_sampling_never_uses_unscoped_source(monkeypatch, scene):
    db = Database(records=[{"id": "wrong-scene"}])
    wire(monkeypatch, db)
    with pytest.raises(NotImplementedError, match="场景抽样暂不可用"):
        await TaskSamplingService().sample({"scene": scene})
    assert db.calls == []


@pytest.mark.parametrize("record_ids", [[], ["record-1"]])
@pytest.mark.parametrize("unavailable", ["missing", "query_failure"])
@pytest.mark.asyncio
async def test_missing_source_and_query_failure_raise_not_fake_success(monkeypatch, record_ids, unavailable):
    db = None if unavailable == "missing" else Database(fail=("medical_records", "select"))
    wire(monkeypatch, db)
    with pytest.raises(RuntimeError, match="候选病历数据源不可用"):
        await TaskSamplingService().sample({"record_ids": record_ids})


@pytest.mark.asyncio
async def test_missing_explicit_id_rejects_partial_candidates(monkeypatch):
    db = Database(records=[{"id": "record-1"}])
    wire(monkeypatch, db)
    with pytest.raises(ValueError, match="指定病历不存在"):
        await TaskSamplingService().sample({"record_ids": ["record-1", "record-2"]})


@pytest.mark.asyncio
async def test_legacy_candidates_remain_compatible_and_empty_is_valid(monkeypatch):
    db = Database(records=[{"id": "record-1"}])
    wire(monkeypatch, db)
    assert await TaskSamplingService().sample({"scene": None, "record_ids": ["record-1", "record-1"]}) == [{"id": "record-1"}]
    db.records = []
    assert await TaskSamplingService().sample({}) == []


@pytest.mark.parametrize("scene", ["running", "final", "outpatient"])
def test_scene_route_refuses_before_candidate_read_or_write(monkeypatch, scene):
    db = Database(task={"id": "task-1", "scene": scene})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 409
    assert "场景抽样暂不可用" in response.json()["detail"]
    assert db.calls == [("qc_tasks", "select")]
    assert db.writes == []


@pytest.mark.parametrize("failure", [("qc_tasks", "select"), ("medical_records", "select")])
def test_route_query_failure_is_503_without_writes(monkeypatch, failure):
    db = Database(task={"id": "task-1"}, fail=failure)
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 503
    assert "internal database" not in response.text
    assert db.writes == []


def test_route_nonexistent_task_remains_404(monkeypatch):
    db = Database()
    response = wire(monkeypatch, db).post("/api/v1/tasks/missing/sample")
    assert response.status_code == 404
    assert db.writes == []


def test_route_missing_explicit_id_is_422_before_writes(monkeypatch):
    db = Database(task={"id": "task-1", "record_ids": ["missing"]})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 422
    assert db.writes == []


@pytest.mark.parametrize("failure", [("qc_task_records", "insert"), ("qc_tasks", "update")])
def test_route_persistence_failure_does_not_report_success(monkeypatch, failure):
    db = Database(task={"id": "task-1"}, records=[{"id": "record-1"}], fail=failure)
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 503
    assert "internal database" not in response.text
    assert len(db.save_calls) == 1
    assert db.writes == []


def test_route_successful_empty_candidates_is_distinct_from_failure(monkeypatch):
    db = Database(task={"id": "task-1"})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 200
    assert response.json()["data"]["sampled_count"] == 0
    assert len(db.save_calls) == 1
    assert db.save_calls[0][1] == []
    assert db.writes == []


@pytest.mark.parametrize("status", ["assigned", "in_progress", "completed", "cancelled", "unknown", None])
def test_route_rejects_non_draft_states_before_candidate_read(monkeypatch, status):
    db = Database(task={"id": "task-1", "status": status})
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 409
    assert db.calls == [("qc_tasks", "select")]
    assert db.save_calls == []


def test_route_sampling_retry_replays_persisted_result_without_candidates(monkeypatch):
    db = Database(task={"id": "task-1", "status": "sampling"}, fail=("medical_records", "select"))
    db.saved_result = {
        "task_id": "task-1",
        "sampled_count": 1,
        "records": [{"id": "saved-assignment", "record_id": "first-sampled-record"}],
    }
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == 200
    assert response.json()["data"] == db.saved_result
    assert db.calls == [("qc_tasks", "select")]
    assert db.save_calls == [(db.task, [])]


@pytest.mark.parametrize("kind,code", [("missing", 404), ("conflict", 409), ("driver", 503)])
def test_route_maps_transaction_failure_without_retry(monkeypatch, kind, code):
    from app.services.task_sampling_persistence import SamplingConflict, SamplingTaskNotFound

    db = Database(task={"id": "task-1"}, records=[{"id": "record-1"}])
    db.save_error = {
        "missing": SamplingTaskNotFound("missing"),
        "conflict": SamplingConflict("任务状态已变化"),
        "driver": ValueError("internal driver implementation detail"),
    }[kind]
    response = wire(monkeypatch, db).post("/api/v1/tasks/task-1/sample")
    assert response.status_code == code
    assert len(db.save_calls) == 1
    assert "internal driver" not in response.text
    assert db.writes == []
