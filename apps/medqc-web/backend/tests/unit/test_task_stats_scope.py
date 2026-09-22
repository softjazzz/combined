from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks


@dataclass
class _Result:
    data: list[dict[str, Any]]
    count: int | None = None


class _Query:
    def __init__(self, database: "_Database", table_name: str):
        self.database = database
        self.table_name = table_name
        self.filters: list[tuple[str, str, Any]] = []
        self.start = 0
        self.end: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field: str, value: Any):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field: str, values: list[Any]):
        self.filters.append(("in", field, values))
        return self

    def or_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, start: int, end: int):
        self.start = start
        self.end = end
        return self

    def execute(self) -> _Result:
        self.database.query_count += 1
        self.database.query_count_by_table[self.table_name] = (
            self.database.query_count_by_table.get(self.table_name, 0) + 1
        )
        if self.table_name in self.database.fail_tables:
            raise RuntimeError(f"{self.table_name} unavailable")

        rows = [dict(row) for row in self.database.rows.get(self.table_name, [])]
        for operation, field, expected in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(field) == expected]
            elif operation == "in":
                rows = [row for row in rows if row.get(field) in expected]

        total = len(rows)
        if self.end is not None:
            rows = rows[self.start : self.end + 1]
        return _Result(data=rows, count=total)


class _Database:
    def __init__(
        self,
        *,
        task_rows: list[dict[str, Any]],
        record_rows: list[dict[str, Any]],
        fail_tables: set[str] | None = None,
    ):
        self.rows = {
            "qc_tasks": task_rows,
            "qc_task_records": record_rows,
        }
        self.fail_tables = fail_tables or set()
        self.query_count = 0
        self.query_count_by_table: dict[str, int] = {}

    def table(self, table_name: str) -> _Query:
        return _Query(self, table_name)


@pytest.fixture
def scoped_tasks() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task_rows = [
        {"id": "task-1", "creator_id": "user-1", "status": "assigned"},
        {"id": "task-2", "creator_id": "user-2", "status": "in_progress"},
        {"id": "task-3", "creator_id": "user-2", "status": "completed"},
        {"id": "task-4", "creator_id": "user-1", "status": "draft"},
    ]
    record_rows = [
        {"task_id": "task-1", "assignee_id": "user-1"},
        {"task_id": "task-1", "assignee_id": "user-1"},
        {"task_id": "task-2", "assignee_id": "user-1"},
        {"task_id": "task-3", "assignee_id": "user-2"},
    ]
    return task_rows, record_rows


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    database: _Database,
    current_user: dict[str, Any],
) -> TestClient:
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: current_user

    async def _execute(query: _Query) -> _Result:
        return query.execute()

    monkeypatch.setattr(tasks, "get_supabase", lambda: database)
    monkeypatch.setattr(tasks, "async_execute", _execute)
    return TestClient(app)


def _user(user_id: str | None) -> dict[str, Any]:
    user = {
        "email": "qc@example.com",
        "roles": ["admin"],
    }
    if user_id is not None:
        user["id"] = user_id
    return user


def test_received_stats_are_isolated_by_current_user_and_deduplicate_tasks(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)

    user_1 = _make_client(monkeypatch, database, _user("user-1"))
    response = user_1.get("/api/v1/tasks/stats", params={"tab": "received"})
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "total": 2,
        "by_status": {"assigned": 1, "in_progress": 1},
        "draft": 0,
        "in_progress": 1,
        "completed": 0,
        "cancelled": 0,
    }

    user_2 = _make_client(monkeypatch, database, _user("user-2"))
    response = user_2.get("/api/v1/tasks/stats", params={"tab": "received"})
    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["by_status"] == {"completed": 1}


def test_authenticated_id_wins_over_conflicting_legacy_user_id(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    current_user = _user("user-1")
    current_user["user_id"] = "user-2"
    client = _make_client(monkeypatch, database, current_user)

    response = client.get("/api/v1/tasks/stats", params={"tab": "received"})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 2
    assert response.json()["data"]["by_status"] == {
        "assigned": 1,
        "in_progress": 1,
    }


def test_legacy_user_id_remains_supported_when_authenticated_id_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    current_user = _user(None)
    current_user["user_id"] = "user-2"
    client = _make_client(monkeypatch, database, current_user)

    response = client.get("/api/v1/tasks/stats", params={"tab": "received"})

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["by_status"] == {"completed": 1}


def test_created_and_received_stats_match_their_list_totals(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-1"))

    for tab in ("created", "received"):
        stats_response = client.get("/api/v1/tasks/stats", params={"tab": tab})
        list_response = client.get("/api/v1/tasks", params={"tab": tab})
        assert stats_response.status_code == 200, stats_response.text
        assert list_response.status_code == 200, list_response.text
        assert stats_response.json()["data"]["total"] == list_response.json()["data"]["total"]


def test_stats_default_keeps_all_tasks_and_created_filters_by_creator(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-1"))

    all_response = client.get("/api/v1/tasks/stats")
    created_response = client.get("/api/v1/tasks/stats", params={"tab": "created"})

    assert all_response.status_code == 200, all_response.text
    assert all_response.json()["data"]["total"] == 4
    assert created_response.status_code == 200, created_response.text
    assert created_response.json()["data"]["total"] == 2
    assert created_response.json()["data"]["by_status"] == {"assigned": 1, "draft": 1}


@pytest.mark.parametrize(
    ("tab", "expected_query_count"),
    [("all", 1), ("created", 1), ("received", 2)],
)
def test_stats_query_count_is_constant_per_scope(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
    tab: str,
    expected_query_count: int,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-1"))

    response = client.get("/api/v1/tasks/stats", params={"tab": tab})

    assert response.status_code == 200, response.text
    assert database.query_count == expected_query_count


def test_received_with_no_assignments_returns_real_zero_without_task_query(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-without-tasks"))

    response = client.get("/api/v1/tasks/stats", params={"tab": "received"})

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "total": 0,
        "by_status": {},
        "draft": 0,
        "in_progress": 0,
        "completed": 0,
        "cancelled": 0,
    }
    assert database.query_count_by_table == {"qc_task_records": 1}


@pytest.mark.parametrize("tab", ["created", "received"])
@pytest.mark.parametrize("endpoint", ["/api/v1/tasks/stats", "/api/v1/tasks"])
def test_personal_task_scope_requires_current_user_id(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
    tab: str,
    endpoint: str,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user(None))

    response = client.get(endpoint, params={"tab": tab})

    assert response.status_code == 401
    assert database.query_count == 0


@pytest.mark.parametrize("failed_table", ["qc_task_records", "qc_tasks"])
def test_received_stats_database_failure_is_not_reported_as_success(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
    failed_table: str,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(
        task_rows=task_rows,
        record_rows=record_rows,
        fail_tables={failed_table},
    )
    client = _make_client(monkeypatch, database, _user("user-1"))

    response = client.get("/api/v1/tasks/stats", params={"tab": "received"})

    assert response.status_code == 500


def test_stats_reject_unknown_tab(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-1"))

    response = client.get("/api/v1/tasks/stats", params={"tab": "someone-else"})

    assert response.status_code == 422
    assert database.query_count == 0


def test_list_rejects_unknown_tab(
    monkeypatch: pytest.MonkeyPatch,
    scoped_tasks,
):
    task_rows, record_rows = scoped_tasks
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-1"))

    response = client.get("/api/v1/tasks", params={"tab": "someone-else"})

    assert response.status_code == 422
    assert database.query_count == 0
