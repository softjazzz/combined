"""旧任务重新质控的创建人边界，不启动应用生命周期。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks
from app.services import qc_service


class FakeDatabase:
    def __init__(self, task=None, records=None, fail=None):
        self.task = task
        self.records = records or []
        self.fail = fail
        self.calls = []
        self.writes = []

    def table(self, name):
        return FakeQuery(self, name)


class FakeQuery:
    def __init__(self, db, table):
        self.db = db
        self.table = table
        self.operation = "select"
        self.payload = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def single(self):
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def execute(self):
        key = (self.table, self.operation)
        self.db.calls.append(key)
        if key == self.db.fail:
            raise RuntimeError("private driver detail")
        if self.operation == "update":
            self.db.writes.append(self.payload)
            return SimpleNamespace(data=[])
        data = self.db.task if self.table == "qc_tasks" else self.db.records
        return SimpleNamespace(data=data)


def client_for(monkeypatch, db, user=None):
    async def execute(query):
        return query.execute()

    monkeypatch.setattr(tasks, "get_supabase", lambda: db)
    monkeypatch.setattr(tasks, "async_execute", execute)
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: (
        {"id": "qc-user", "roles": ["admin"]} if user is None else user
    )
    return TestClient(app)


@pytest.mark.parametrize("creator_id", ["other-user", None, ""])
def test_foreign_or_unowned_task_denied_before_record_read_and_qc(monkeypatch, creator_id):
    db = FakeDatabase(task={"id": "task-1", "creator_id": creator_id, "scene": None})
    evaluated = []
    monkeypatch.setattr(qc_service, "QCService", lambda: evaluated.append("created"))

    response = client_for(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")

    assert response.status_code == 403
    assert db.calls == [("qc_tasks", "select")]
    assert db.writes == []
    assert evaluated == []


def test_missing_actor_identity_denied_before_database_access(monkeypatch):
    db = FakeDatabase(task={"id": "task-1", "creator_id": "qc-user"})

    response = client_for(monkeypatch, db, user={"roles": ["admin"]}).post(
        "/api/v1/tasks/task-1/re-analyze"
    )

    assert response.status_code == 401
    assert db.calls == []


def test_nonexistent_task_is_404(monkeypatch):
    db = FakeDatabase()

    response = client_for(monkeypatch, db).post("/api/v1/tasks/missing/re-analyze")

    assert response.status_code == 404
    assert db.calls == [("qc_tasks", "select")]


def test_modern_task_still_refuses_legacy_entry_for_creator(monkeypatch):
    db = FakeDatabase(task={"id": "task-1", "creator_id": "qc-user", "scene": "running"})

    response = client_for(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")

    assert response.status_code == 409
    assert db.calls == [("qc_tasks", "select")]
    assert db.writes == []


def test_creator_can_run_legacy_task(monkeypatch):
    db = FakeDatabase(
        task={"id": "task-1", "creator_id": "qc-user", "scene": None},
        records=[{"record_id": "record-1"}],
    )
    evaluated = []

    class FakeQCService:
        async def evaluate(self, payload):
            evaluated.append(payload)

    monkeypatch.setattr(qc_service, "QCService", FakeQCService)

    response = client_for(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")

    assert response.status_code == 200
    assert evaluated == [{"record_id": "record-1"}]
    assert db.calls == [
        ("qc_tasks", "select"),
        ("qc_task_records", "select"),
        ("qc_tasks", "update"),
    ]
    assert len(db.writes) == 1
    assert response.json()["data"] == {
        "task_id": "task-1",
        "total": 1,
        "attempted": 1,
        "started": 1,
        "failed": 0,
        "not_attempted": 0,
        "partial": False,
        "results": [{"record_id": "record-1", "status": "started"}],
    }


def test_single_failed_analysis_is_redacted_and_does_not_update_task(monkeypatch):
    db = FakeDatabase(
        task={"id": "task-1", "creator_id": "qc-user", "scene": None},
        records=[{"record_id": "record-1"}],
    )

    class FailingQCService:
        async def evaluate(self, _payload):
            raise RuntimeError("private patient content and driver detail")

    monkeypatch.setattr(qc_service, "QCService", FailingQCService)

    response = client_for(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")

    assert response.status_code == 503
    assert "private patient content" not in response.text
    assert "本次尝试 1 条" in response.json()["detail"]
    assert db.calls == [("qc_tasks", "select"), ("qc_task_records", "select")]
    assert db.writes == []


def test_partial_analysis_reports_actual_counts_and_redacts_failure(monkeypatch):
    db = FakeDatabase(
        task={"id": "task-1", "creator_id": "qc-user", "scene": None},
        records=[{"record_id": f"record-{index}"} for index in range(3)],
    )

    class PartialQCService:
        async def evaluate(self, payload):
            if payload["record_id"] == "record-1":
                raise RuntimeError("private patient content")

    monkeypatch.setattr(qc_service, "QCService", PartialQCService)

    response = client_for(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")

    assert response.status_code == 200
    assert "部分完成" in response.json()["message"]
    assert "private patient content" not in response.text
    data = response.json()["data"]
    assert (
        data["total"], data["attempted"], data["started"], data["failed"], data["not_attempted"]
    ) == (3, 3, 2, 1, 0)
    assert data["partial"] is True
    assert data["results"] == [
        {"record_id": "record-0", "status": "started"},
        {"record_id": "record-1", "status": "failed", "error": "质控分析失败"},
        {"record_id": "record-2", "status": "started"},
    ]
    assert len(db.writes) == 1


def test_all_failed_analysis_does_not_claim_progress(monkeypatch):
    db = FakeDatabase(
        task={"id": "task-1", "creator_id": "qc-user", "scene": None},
        records=[{"record_id": "record-1"}, {"record_id": "record-2"}],
    )

    class FailingQCService:
        async def evaluate(self, _payload):
            raise RuntimeError("private patient content")

    monkeypatch.setattr(qc_service, "QCService", FailingQCService)

    response = client_for(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")

    assert response.status_code == 503
    assert "本次尝试 2 条" in response.json()["detail"]
    assert "private patient content" not in response.text
    assert db.writes == []


def test_legacy_batch_limit_distinguishes_total_from_attempted(monkeypatch):
    db = FakeDatabase(
        task={"id": "task-1", "creator_id": "qc-user", "scene": None},
        records=[{"record_id": f"record-{index}"} for index in range(51)],
    )
    evaluated = []

    class FakeQCService:
        async def evaluate(self, payload):
            evaluated.append(payload)

    monkeypatch.setattr(qc_service, "QCService", FakeQCService)

    response = client_for(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")

    assert response.status_code == 200
    assert len(evaluated) == 50
    data = response.json()["data"]
    assert (
        data["total"], data["attempted"], data["started"], data["failed"], data["not_attempted"]
    ) == (51, 50, 50, 0, 1)
    assert data["partial"] is True
    assert "未尝试 1 条" in response.json()["message"]
    assert len(data["results"]) == 50


@pytest.mark.parametrize("fail", [("qc_tasks", "select"), ("qc_task_records", "select")])
def test_query_failure_is_redacted_503_without_qc_or_writes(monkeypatch, fail):
    db = FakeDatabase(task={"id": "task-1", "creator_id": "qc-user"}, fail=fail)
    evaluated = []
    monkeypatch.setattr(qc_service, "QCService", lambda: evaluated.append("created"))

    response = client_for(monkeypatch, db).post("/api/v1/tasks/task-1/re-analyze")

    assert response.status_code == 503
    assert "private driver detail" not in response.text
    assert db.writes == []
    assert evaluated == []
