from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks


@dataclass
class Result:
    data: list[dict[str, Any]]
    count: int | None


class Query:
    def __init__(self, db: "Database", table: str):
        self.db = db
        self.table = table
        self.filters: list[tuple[str, Any]] = []
        self.sort_field: str | None = None
        self.desc = False
        self.start = 0
        self.end: int | None = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self.filters.append((field, value))
        return self

    def in_(self, field, values):
        assert len(values) <= 200
        self.filters.append((field, set(values)))
        return self

    def is_(self, field, value):
        self.filters.append((field, value))
        return self

    def order(self, field, *, desc=False):
        self.sort_field = field
        self.desc = desc
        return self

    def range(self, start, end):
        self.start, self.end = start, end
        return self

    def execute(self):
        rows = [dict(row) for row in self.db.rows[self.table]]
        for field, value in self.filters:
            if isinstance(value, set):
                rows = [row for row in rows if row.get(field) in value]
            else:
                rows = [row for row in rows if row.get(field) == value]
        total = len(rows)
        if self.sort_field:
            rows.sort(key=lambda row: row[self.sort_field], reverse=self.desc)
        if self.end is not None:
            rows = rows[self.start:self.end + 1]
        return Result(rows[:self.db.response_cap], self.db.counts.get(self.table, total))


class Database:
    def __init__(self, assignments, task_rows, *, response_cap=1000, counts=None):
        self.rows = {"qc_task_records": assignments, "qc_tasks": task_rows}
        self.response_cap = response_cap
        self.counts = counts or {}

    def table(self, table):
        return Query(self, table)


def client_for(monkeypatch, db):
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "roles": ["admin"]}
    monkeypatch.setattr(tasks, "get_supabase", lambda: db)

    async def execute(query):
        return query.execute()

    monkeypatch.setattr(tasks, "async_execute", execute)
    return TestClient(app)


@pytest.mark.parametrize("count,response_cap", [(1001, 1000), (1501, 75)])
def test_todo_counts_and_pages_include_rows_beyond_response_cap(monkeypatch, count, response_cap):
    assignments = [
        {"id": f"r{i:05d}", "task_id": f"t{i:05d}", "assignee_id": "u1"}
        for i in range(count)
    ]
    assignments += [
        {"id": f"extra{i:05d}", "task_id": f"t{i:05d}", "assignee_id": "u1"}
        for i in range(25)
    ]
    task_rows = [
        {"id": f"t{i:05d}", "status": "assigned", "scene": "running",
         "deadline": None, "created_at": f"2026-09-01T{i % 24:02d}:00:00Z"}
        for i in range(count)
    ]
    client = client_for(monkeypatch, Database(assignments, task_rows, response_cap=response_cap))
    stats = client.get("/api/v1/tasks/todo-stats", params={"scene": "running"})
    assert stats.status_code == 200, stats.text
    assert stats.json()["data"]["assigned"] == count

    params = {"tab": "received", "todo": "assigned", "scene": "running", "page_size": 100}
    first = client.get("/api/v1/tasks", params={**params, "page": 1})
    last = client.get("/api/v1/tasks", params={**params, "page": (count + 99) // 100})
    empty = client.get("/api/v1/tasks", params={**params, "page": (count + 99) // 100 + 1})
    assert first.status_code == last.status_code == empty.status_code == 200
    assert first.json()["data"]["total"] == last.json()["data"]["total"] == count
    assert len(first.json()["data"]["items"]) == 100
    assert len(last.json()["data"]["items"]) == count % 100 or 100
    assert empty.json()["data"]["items"] == []
    expected = sorted(
        task_rows, key=lambda row: (row["created_at"], row["id"]), reverse=True
    )
    assert [row["id"] for row in first.json()["data"]["items"]] == [
        row["id"] for row in expected[:100]
    ]
    assert [row["id"] for row in last.json()["data"]["items"]] == [
        row["id"] for row in expected[((count - 1) // 100) * 100:]
    ]


def test_todo_scope_limit_fails_instead_of_reporting_partial_count(monkeypatch):
    monkeypatch.setattr(tasks, "_TODO_MAX_ASSIGNMENTS", 1000)
    assignments = [
        {"id": f"r{i:05d}", "task_id": "t", "assignee_id": "u1"}
        for i in range(1001)
    ]
    client = client_for(monkeypatch, Database(assignments, [
        {"id": "t", "status": "assigned", "scene": "running", "deadline": None}
    ]))
    stats = client.get("/api/v1/tasks/todo-stats")
    listing = client.get("/api/v1/tasks", params={"tab": "received", "todo": "assigned"})
    assert stats.status_code == listing.status_code == 503


@pytest.mark.parametrize(
    "table,count", [("qc_task_records", None), ("qc_task_records", 999),
                    ("qc_tasks", None), ("qc_tasks", 999)]
)
def test_todo_missing_or_inconsistent_count_fails_closed(monkeypatch, table, count):
    db = Database(
        [{"id": "r1", "task_id": "t1", "assignee_id": "u1"}],
        [{"id": "t1", "status": "assigned", "deadline": None}],
        counts={table: count},
    )
    client = client_for(monkeypatch, db)
    stats = client.get("/api/v1/tasks/todo-stats")
    listing = client.get("/api/v1/tasks", params={"tab": "received", "todo": "assigned"})
    assert stats.status_code == listing.status_code == 503
