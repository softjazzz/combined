from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
        self.order_field: str | None = None
        self.order_desc = False
        self.insert_payload: dict[str, Any] | None = None

    def select(self, *_args, **kwargs):
        if kwargs.get("count"):
            self.database.count_requests += 1
        return self

    def insert(self, payload: dict[str, Any]):
        self.insert_payload = dict(payload)
        return self

    def eq(self, field: str, value: Any):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field: str, values: list[Any]):
        self.filters.append(("in", field, values))
        return self

    def or_(self, expression: str):
        self.filters.append(("search", "", expression))
        return self

    def order(self, field: str, *, desc: bool = False):
        self.order_field = field
        self.order_desc = desc
        return self

    def range(self, start: int, end: int):
        self.start = start
        self.end = end
        return self

    def execute(self) -> _Result:
        self.database.adapter_calls += 1
        self.database.calls_by_table[self.table_name] = (
            self.database.calls_by_table.get(self.table_name, 0) + 1
        )
        if self.table_name in self.database.fail_tables:
            raise RuntimeError(f"{self.table_name} unavailable")

        if self.insert_payload is not None:
            self.database.inserted.append(dict(self.insert_payload))
            self.database.rows.setdefault(self.table_name, []).append(
                dict(self.insert_payload)
            )
            return _Result(data=[dict(self.insert_payload)], count=1)

        rows = [dict(row) for row in self.database.rows.get(self.table_name, [])]
        for operation, field, expected in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(field) == expected]
            elif operation == "in":
                rows = [row for row in rows if row.get(field) in expected]
            elif operation == "search":
                keyword = expected.split("%", 2)[1].lower()
                rows = [
                    row
                    for row in rows
                    if keyword in str(row.get("task_name", "")).lower()
                    or keyword in str(row.get("task_number", "")).lower()
                ]

        if self.order_field:
            rows.sort(
                key=lambda row: str(row.get(self.order_field) or ""),
                reverse=self.order_desc,
            )
        total = len(rows)
        if self.end is not None:
            rows = rows[self.start : self.end + 1]
        return _Result(data=rows, count=total)


class _Database:
    def __init__(
        self,
        *,
        task_rows: list[dict[str, Any]] | None = None,
        record_rows: list[dict[str, Any]] | None = None,
        fail_tables: set[str] | None = None,
    ):
        self.rows = {
            "qc_tasks": list(task_rows or []),
            "qc_task_records": list(record_rows or []),
        }
        self.fail_tables = fail_tables or set()
        self.adapter_calls = 0
        self.count_requests = 0
        self.calls_by_table: dict[str, int] = {}
        self.inserted: list[dict[str, Any]] = []

    def table(self, table_name: str) -> _Query:
        return _Query(self, table_name)


def _user(user_id: str | None, *, legacy_id: str | None = None) -> dict[str, Any]:
    user: dict[str, Any] = {
        "email": "qc@example.com",
        "display_name": "质控员",
        "roles": ["admin"],
    }
    if user_id is not None:
        user["id"] = user_id
    if legacy_id is not None:
        user["user_id"] = legacy_id
    return user


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    database: _Database,
    current_user: dict[str, Any],
    *,
    now: datetime | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: current_user

    async def _execute(query: _Query) -> _Result:
        return query.execute()

    monkeypatch.setattr(tasks, "get_supabase", lambda: database)
    monkeypatch.setattr(tasks, "async_execute", _execute)
    if now is not None:
        monkeypatch.setattr(tasks, "_utc_now", lambda: now)
    return TestClient(app)


def _task(
    task_id: str,
    status: str,
    deadline: str | None,
    *,
    created_at: str,
    creator_id: str = "creator",
) -> dict[str, Any]:
    return {
        "id": task_id,
        "task_number": f"QC-{task_id}",
        "task_name": f"任务 {task_id}",
        "creator_id": creator_id,
        "status": status,
        "deadline": deadline,
        "created_at": created_at,
    }


def test_list_summary_receives_only_authorized_page_and_preserves_approved_zero(monkeypatch):
    database = _Database(task_rows=[
        _task("own", "completed", None, created_at="2", creator_id="real-user"),
        _task("foreign", "completed", None, created_at="1", creator_id="other"),
    ])
    calls = []
    def read(**kwargs):
        calls.append(kwargs)
        return {"own": {**tasks.unknown_summary(), "approved_records": 0, "assigned_to_me": 2}}
    monkeypatch.setattr(tasks, "get_task_list_summaries", read)
    client = _make_client(monkeypatch, database, _user("real-user"))
    response = client.get("/api/v1/tasks?tab=created")
    assert response.status_code == 200
    assert calls == [{"task_ids": ["own"], "actor_id": "real-user", "tab": "created", "is_manager": True}]
    row = response.json()["data"]["items"][0]
    assert row["approved_records"] == 0
    assert row["assigned_to_me"] == 2


def test_received_list_keeps_original_contract_without_new_summary(monkeypatch):
    database = _Database(
        task_rows=[{**_task("assigned", "in_progress", None, created_at="1"), "completed_records": 3}],
        record_rows=[{"task_id": "assigned", "assignee_id": "real-user"}],
    )
    def forbidden(**_kwargs):
        pytest.fail("受领列表不应读取创建/管理摘要")
    monkeypatch.setattr(tasks, "get_task_list_summaries", forbidden)
    client = _make_client(monkeypatch, database, _user("real-user"))
    response = client.get("/api/v1/tasks?tab=received")
    assert response.status_code == 200
    row = response.json()["data"]["items"][0]
    assert row["completed_records"] == 3
    assert "approved_records" not in row and "qc_assignees" not in row


def test_create_task_uses_authenticated_id_before_legacy_id(
    monkeypatch: pytest.MonkeyPatch,
):
    database = _Database()
    client = _make_client(
        monkeypatch,
        database,
        _user("real-user", legacy_id="legacy-user"),
    )

    response = client.post("/api/v1/tasks", json={
        "task_name": "季度抽查", "scene": "final", "rule_set_key": "sc_content_v1"
    })

    assert response.status_code == 200, response.text
    assert database.inserted[0]["creator_id"] == "real-user"


def test_create_task_supports_legacy_user_id_and_rejects_missing_identity(
    monkeypatch: pytest.MonkeyPatch,
):
    legacy_database = _Database()
    legacy_client = _make_client(
        monkeypatch,
        legacy_database,
        _user(None, legacy_id="legacy-user"),
    )
    response = legacy_client.post("/api/v1/tasks", json={
        "task_name": "历史入口", "scene": "final", "rule_set_key": "sc_content_v1"
    })
    assert response.status_code == 200, response.text
    assert legacy_database.inserted[0]["creator_id"] == "legacy-user"

    missing_database = _Database()
    missing_client = _make_client(monkeypatch, missing_database, _user(None))
    response = missing_client.post("/api/v1/tasks", json={
        "task_name": "无身份", "scene": "final", "rule_set_key": "sc_content_v1"
    })
    assert response.status_code == 401
    assert missing_database.inserted == []
    assert missing_database.adapter_calls == 0


@pytest.fixture
def todo_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [
        _task("due-utc", "assigned", "2026-09-22T01:00:00Z", created_at="12"),
        _task("due-edge", "in_progress", "2026-09-23T00:00:00+00:00", created_at="11"),
        _task("at-start", "assigned", "2026-09-22T00:00:00+00:00", created_at="10"),
        _task("after-window", "assigned", "2026-09-23T00:00:00.000001Z", created_at="09"),
        _task("naive-shanghai", "in_progress", "2026-09-22T09:00:00", created_at="08"),
        _task("date-only", "assigned", "2026-09-22", created_at="07"),
        _task("next-date", "assigned", "2026-09-23", created_at="065"),
        _task("overdue", "assigned", "2026-09-21T23:59:59Z", created_at="06"),
        _task("invalid", "assigned", "not-a-date", created_at="05"),
        _task("empty", "assigned", None, created_at="04"),
        _task("completed", "completed", "2026-09-22T02:00:00Z", created_at="03"),
        _task("cancelled", "cancelled", "2026-09-22T02:00:00Z", created_at="02"),
        _task("sampling", "sampling", "2026-09-22T02:00:00Z", created_at="01"),
        _task("other-user", "assigned", "2026-09-22T02:00:00Z", created_at="00"),
    ]
    records = [
        {"task_id": row["id"], "assignee_id": "user-1"}
        for row in rows
        if row["id"] != "other-user"
    ]
    records.extend(
        [
            {"task_id": "due-utc", "assignee_id": "user-1"},
            {"task_id": "other-user", "assignee_id": "user-2"},
        ]
    )
    return rows, records


def test_todo_stats_are_personal_deduplicated_and_use_fixed_deadline_contract(
    monkeypatch: pytest.MonkeyPatch,
    todo_rows,
):
    task_rows, record_rows = todo_rows
    as_of = datetime(2026, 9, 22, tzinfo=timezone.utc)
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-1"), now=as_of)

    response = client.get("/api/v1/tasks/todo-stats")

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "as_of": "2026-09-22T00:00:00+00:00",
        "assigned": 8,
        "in_progress": 2,
        "due_soon": 4,
    }
    assert database.adapter_calls == 2

    other_database = _Database(task_rows=task_rows, record_rows=record_rows)
    other_client = _make_client(
        monkeypatch,
        other_database,
        _user("user-2"),
        now=as_of,
    )
    response = other_client.get("/api/v1/tasks/todo-stats")
    assert response.status_code == 200, response.text
    assert response.json()["data"]["assigned"] == 1
    assert response.json()["data"]["due_soon"] == 1


def test_due_soon_list_filters_before_pagination_and_matches_stats(
    monkeypatch: pytest.MonkeyPatch,
    todo_rows,
):
    task_rows, record_rows = todo_rows
    as_of = datetime(2026, 9, 22, tzinfo=timezone.utc)
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-1"), now=as_of)
    params = {
        "tab": "received",
        "todo": "due_soon",
        "as_of": "2026-09-22T08:00:00+08:00",
        "page_size": 2,
    }

    first = client.get("/api/v1/tasks", params={**params, "page": 1})
    second = client.get("/api/v1/tasks", params={**params, "page": 2})
    stats = client.get("/api/v1/tasks/todo-stats")

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["total"] == stats.json()["data"]["due_soon"] == 4
    assert first.json()["data"]["total_pages"] == 2
    assert [row["id"] for row in first.json()["data"]["items"]] == [
        "due-utc",
        "due-edge",
    ]
    assert [row["id"] for row in second.json()["data"]["items"]] == [
        "naive-shanghai",
        "date-only",
    ]
    assert database.count_requests > 0


@pytest.mark.parametrize(
    ("todo", "expected_total"),
    [("assigned", 8), ("in_progress", 2)],
)
def test_status_todo_list_matches_received_status_counts(
    monkeypatch: pytest.MonkeyPatch,
    todo_rows,
    todo: str,
    expected_total: int,
):
    task_rows, record_rows = todo_rows
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database, _user("user-1"))

    response = client.get(
        "/api/v1/tasks",
        params={"tab": "received", "todo": todo, "page_size": 100},
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == expected_total


@pytest.mark.parametrize(
    "params",
    [
        {"tab": "received", "todo": "unknown"},
        {"tab": "all", "todo": "assigned"},
        {"tab": "created", "todo": "due_soon"},
        {"tab": "received", "todo": "due_soon", "as_of": "2026-09-22T00:00:00"},
        {"tab": "received", "todo": "due_soon", "as_of": "invalid"},
        {"tab": "received", "todo": "due_soon", "as_of": "9999-12-31T00:00:00Z"},
        {"tab": "received", "todo": "due_soon", "as_of": "0001-01-01T00:00:00+14:00"},
    ],
)
def test_todo_list_rejects_invalid_contract_without_database_calls(
    monkeypatch: pytest.MonkeyPatch,
    params: dict[str, str],
):
    database = _Database()
    client = _make_client(monkeypatch, database, _user("user-1"))

    response = client.get("/api/v1/tasks", params=params)

    assert response.status_code == 422
    assert database.adapter_calls == 0


@pytest.mark.parametrize(
    "deadline",
    ["0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-14:00"],
)
def test_unrepresentable_deadline_is_excluded_as_invalid_legacy_value(
    monkeypatch: pytest.MonkeyPatch,
    deadline: str,
):
    database = _Database(
        task_rows=[_task("extreme", "assigned", deadline, created_at="1")],
        record_rows=[{"task_id": "extreme", "assignee_id": "user-1"}],
    )
    client = _make_client(monkeypatch, database, _user("user-1"))

    response = client.get(
        "/api/v1/tasks",
        params={
            "tab": "received",
            "todo": "due_soon",
            "as_of": "2026-09-22T00:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["total"] == 0


def test_todo_empty_assignments_return_zero_and_missing_identity_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
):
    as_of = datetime(2026, 9, 22, tzinfo=timezone.utc)
    empty_database = _Database()
    empty_client = _make_client(
        monkeypatch,
        empty_database,
        _user("user-1"),
        now=as_of,
    )
    response = empty_client.get("/api/v1/tasks/todo-stats")
    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "as_of": "2026-09-22T00:00:00+00:00",
        "assigned": 0,
        "in_progress": 0,
        "due_soon": 0,
    }
    assert empty_database.adapter_calls == 1

    missing_database = _Database()
    missing_client = _make_client(monkeypatch, missing_database, _user(None))
    response = missing_client.get("/api/v1/tasks/todo-stats")
    assert response.status_code == 401
    assert missing_database.adapter_calls == 0


@pytest.mark.parametrize("failed_table", ["qc_task_records", "qc_tasks"])
def test_todo_database_failures_are_not_success(
    monkeypatch: pytest.MonkeyPatch,
    failed_table: str,
):
    database = _Database(
        task_rows=[
            _task(
                "task-1",
                "assigned",
                "2026-09-22T01:00:00Z",
                created_at="1",
            )
        ],
        record_rows=[{"task_id": "task-1", "assignee_id": "user-1"}],
        fail_tables={failed_table},
    )
    client = _make_client(monkeypatch, database, _user("user-1"))

    stats_response = client.get("/api/v1/tasks/todo-stats")
    list_response = client.get(
        "/api/v1/tasks",
        params={"tab": "received", "todo": "assigned"},
    )

    assert stats_response.status_code == 500
    assert stats_response.json()["detail"] == "获取任务待办统计失败，请稍后重试"
    assert failed_table not in stats_response.text
    assert list_response.status_code == 500
