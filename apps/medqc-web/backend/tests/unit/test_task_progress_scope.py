"""整任务进度仅向创建人及管理角色开放。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks


class Query:
    def __init__(self, database, table):
        self.database = database
        self.table = table
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def single(self):
        return self

    def execute(self):
        self.database.calls.append(self.table)
        if self.table in self.database.fail_tables:
            raise RuntimeError("private database detail")
        rows = self.database.rows[self.table]
        for key, value in self.filters:
            rows = [row for row in rows if row.get(key) == value]
        return SimpleNamespace(data=dict(rows[0]) if rows else None)


class Database:
    def __init__(self, creator_id="creator"):
        self.rows = {
            "qc_tasks": [{"id": "task-1", "creator_id": creator_id}],
            "v_qc_task_progress": [{"task_id": "task-1", "completed": 2}],
        }
        self.calls = []
        self.fail_tables = set()

    def table(self, name):
        return Query(self, name)


def client_for(monkeypatch, database, user):
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(tasks, "get_supabase", lambda: database)

    async def execute(query):
        return query.execute()

    monkeypatch.setattr(tasks, "async_execute", execute)
    return TestClient(app)


def test_creator_can_read_whole_task_progress(monkeypatch):
    database = Database()
    client = client_for(monkeypatch, database, {"id": "creator", "roles": ["qc_staff"]})
    response = client.get("/api/v1/tasks/task-1/progress")
    assert response.status_code == 200
    assert response.json()["data"]["completed"] == 2
    assert database.calls == ["qc_tasks", "v_qc_task_progress"]


@pytest.mark.parametrize("role", ["admin", "qc_manager"])
def test_management_can_read_whole_task_progress(monkeypatch, role):
    database = Database()
    client = client_for(monkeypatch, database, {"id": "manager", "roles": [role]})
    response = client.get("/api/v1/tasks/task-1/progress")
    assert response.status_code == 200
    assert database.calls == ["qc_tasks", "v_qc_task_progress"]


@pytest.mark.parametrize("user", [
    {"id": "stranger", "roles": ["doctor"]},
    {"id": "assignee", "roles": ["qc_staff"]},
])
def test_non_creator_cannot_query_progress_view(monkeypatch, user):
    database = Database()
    client = client_for(monkeypatch, database, user)
    response = client.get("/api/v1/tasks/task-1/progress")
    assert response.status_code == 403
    assert database.calls == ["qc_tasks"]


def test_empty_creator_denies_non_admin(monkeypatch):
    database = Database(creator_id=None)
    client = client_for(monkeypatch, database, {"id": "assignee", "roles": ["qc_staff"]})
    response = client.get("/api/v1/tasks/task-1/progress")
    assert response.status_code == 403
    assert database.calls == ["qc_tasks"]


def test_missing_identity_does_not_query_database(monkeypatch):
    database = Database()
    client = client_for(monkeypatch, database, {"roles": ["admin"]})
    response = client.get("/api/v1/tasks/task-1/progress")
    assert response.status_code == 401
    assert database.calls == []


def test_missing_task_does_not_query_progress_view(monkeypatch):
    database = Database()
    client = client_for(monkeypatch, database, {"id": "creator", "roles": ["qc_staff"]})
    response = client.get("/api/v1/tasks/missing/progress")
    assert response.status_code == 404
    assert database.calls == ["qc_tasks"]


def test_missing_view_row_is_404(monkeypatch):
    database = Database()
    database.rows["v_qc_task_progress"] = []
    client = client_for(monkeypatch, database, {"id": "creator", "roles": ["qc_staff"]})
    response = client.get("/api/v1/tasks/task-1/progress")
    assert response.status_code == 404
    assert database.calls == ["qc_tasks", "v_qc_task_progress"]


@pytest.mark.parametrize("table", ["qc_tasks", "v_qc_task_progress"])
def test_source_failure_is_sanitized_503(monkeypatch, table):
    database = Database()
    database.fail_tables.add(table)
    client = client_for(monkeypatch, database, {"id": "creator", "roles": ["qc_staff"]})
    response = client.get("/api/v1/tasks/task-1/progress")
    assert response.status_code == 503
    assert "private database detail" not in response.text


def test_database_unavailable_is_503(monkeypatch):
    client = client_for(monkeypatch, None, {"id": "creator", "roles": ["qc_staff"]})
    response = client.get("/api/v1/tasks/task-1/progress")
    assert response.status_code == 503
