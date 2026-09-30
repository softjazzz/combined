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
        # 与 PostgREST 一致：多次 .order() 依调用顺序组成主次排序键。
        self.orders: list[tuple[str, bool]] = []
        self.insert_payload: dict[str, Any] | None = None

    def select(self, *_args, **_kwargs):
        return self

    def single(self):
        return self

    def insert(self, payload: dict[str, Any]):
        self.insert_payload = dict(payload)
        return self

    def update(self, payload: dict[str, Any]):
        self.database.update_attempts.append(dict(payload))
        return self

    def eq(self, field: str, value: Any):
        self.filters.append(("eq", field, value))
        return self

    def is_(self, field: str, value: Any):
        self.filters.append(("is", field, value))
        return self

    def in_(self, field: str, values: list[Any]):
        self.filters.append(("in", field, values))
        return self

    def or_(self, *_args, **_kwargs):
        return self

    def order(self, field: str, *, desc: bool = False):
        self.orders.append((field, desc))
        return self

    def range(self, start: int, end: int):
        self.start = start
        self.end = end
        return self

    def execute(self) -> _Result:
        self.database.query_count += 1
        if self.table_name in self.database.fail_tables:
            raise RuntimeError("secret database host and credentials")
        if self.insert_payload is not None:
            self.database.inserted.append(dict(self.insert_payload))
            return _Result([dict(self.insert_payload)], 1)

        rows = [dict(row) for row in self.database.rows.get(self.table_name, [])]
        for operation, field, expected in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(field) == expected]
            elif operation == "is":
                rows = [row for row in rows if row.get(field) is expected]
            elif operation == "in":
                rows = [row for row in rows if row.get(field) in expected]
        for field, desc in reversed(self.orders):
            rows.sort(key=lambda row, field=field: str(row.get(field) or ""), reverse=desc)
        total = len(rows)
        if self.end is not None:
            rows = rows[self.start : self.end + 1]
        return _Result(rows, total)


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
        self.inserted: list[dict[str, Any]] = []
        self.update_attempts: list[dict[str, Any]] = []
        self.query_count = 0

    def table(self, table_name: str) -> _Query:
        return _Query(self, table_name)


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    database: _Database,
    *,
    user_id: str = "user-1",
) -> TestClient:
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "display_name": "质控员",
        "roles": ["admin"],
    }

    async def _execute(query: _Query) -> _Result:
        return query.execute()

    monkeypatch.setattr(tasks, "get_supabase", lambda: database)
    monkeypatch.setattr(tasks, "async_execute", _execute)
    monkeypatch.setattr(
        tasks,
        "_utc_now",
        lambda: datetime(2026, 9, 22, tzinfo=timezone.utc),
    )
    return TestClient(app)


def _task(
    task_id: str,
    *,
    scene: str | None,
    creator_id: str = "other-user",
    status: str = "assigned",
    created_at: str,
) -> dict[str, Any]:
    return {
        "id": task_id,
        "task_number": f"QC-{task_id}",
        "task_name": task_id,
        "creator_id": creator_id,
        "scene": scene,
        "status": status,
        "deadline": "2026-09-22T12:00:00Z",
        "created_at": created_at,
    }


@pytest.mark.parametrize(
    ("scene", "rule_set_key"),
    [
        ("running", "luxian_0609_qc_v1"),
        ("final", "sc_content_v1"),
    ],
)
def test_create_persists_explicit_scene(
    monkeypatch: pytest.MonkeyPatch,
    scene: str,
    rule_set_key: str,
):
    database = _Database()
    client = _make_client(monkeypatch, database)

    response = client.post(
        "/api/v1/tasks",
        json={"task_name": "场景任务", "scene": scene, "rule_set_key": rule_set_key},
    )

    assert response.status_code == 200, response.text
    assert database.inserted[0]["scene"] == scene
    assert database.inserted[0]["rule_set_key"] == rule_set_key


@pytest.mark.parametrize("payload", [{"task_name": "旧客户端"}, {"task_name": "空场景", "scene": None}])
def test_create_legacy_or_null_scene_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, Any],
):
    database = _Database()
    client = _make_client(monkeypatch, database)

    response = client.post("/api/v1/tasks", json=payload)

    assert response.status_code == 422
    assert database.query_count == 0
    assert database.inserted == []


def test_create_rejects_unknown_scene_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
):
    database = _Database()
    client = _make_client(monkeypatch, database)

    response = client.post(
        "/api/v1/tasks",
        json={"task_name": "错误场景", "scene": "discharged"},
    )

    assert response.status_code == 422
    assert database.query_count == 0
    assert database.inserted == []


def test_direct_call_query_default_does_not_apply_scene_filter():
    database = _Database()
    query = database.table("qc_tasks")

    result = tasks._apply_task_scene_scope(query, tasks.Query(None))

    assert result is query
    assert query.filters == []


@pytest.mark.parametrize("scene", ["running", None])
def test_update_rejects_scene_key_even_when_null(
    monkeypatch: pytest.MonkeyPatch,
    scene: str | None,
):
    database = _Database()
    client = _make_client(monkeypatch, database)

    response = client.put("/api/v1/tasks/task-1", json={"scene": scene})

    assert response.status_code == 422
    assert database.query_count == 0
    assert database.update_attempts == []


@pytest.fixture
def scene_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [
        _task("run-new", scene="running", created_at="09"),
        _task("run-old", scene="running", status="in_progress", created_at="08"),
        _task("final", scene="final", created_at="07"),
        _task("outpatient", scene="outpatient", created_at="06"),
        _task("legacy", scene=None, created_at="05"),
        _task("other-user", scene="running", created_at="04"),
    ]
    records = [
        {"task_id": row["id"], "assignee_id": "user-1"}
        for row in rows
        if row["id"] != "other-user"
    ]
    records.extend(
        [
            {"task_id": "run-new", "assignee_id": "user-1"},
            {"task_id": "other-user", "assignee_id": "user-2"},
        ]
    )
    return rows, records


@pytest.mark.parametrize(
    ("scene", "expected_ids"),
    [
        ("running", ["run-new", "run-old"]),
        ("final", ["final"]),
        ("outpatient", ["outpatient"]),
        ("unclassified", ["legacy"]),
    ],
)
def test_scene_scope_is_user_isolated_deduplicated_and_consistent(
    monkeypatch: pytest.MonkeyPatch,
    scene_rows,
    scene: str,
    expected_ids: list[str],
):
    task_rows, record_rows = scene_rows
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database)
    params = {"tab": "received", "scene": scene}

    listed = client.get("/api/v1/tasks", params=params)
    stats = client.get("/api/v1/tasks/stats", params=params)
    todos = client.get("/api/v1/tasks/todo-stats", params={"scene": scene})

    assert listed.status_code == stats.status_code == todos.status_code == 200
    assert [row["id"] for row in listed.json()["data"]["items"]] == expected_ids
    assert listed.json()["data"]["total"] == stats.json()["data"]["total"]
    assert stats.json()["data"]["total"] == (
        todos.json()["data"]["assigned"] + todos.json()["data"]["in_progress"]
    )


def test_scene_filter_is_applied_before_pagination(
    monkeypatch: pytest.MonkeyPatch,
    scene_rows,
):
    task_rows, record_rows = scene_rows
    database = _Database(task_rows=task_rows, record_rows=record_rows)
    client = _make_client(monkeypatch, database)

    first = client.get(
        "/api/v1/tasks",
        params={"tab": "received", "scene": "running", "page": 1, "page_size": 1},
    )
    second = client.get(
        "/api/v1/tasks",
        params={"tab": "received", "scene": "running", "page": 2, "page_size": 1},
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["total"] == second.json()["data"]["total"] == 2
    assert [row["id"] for row in first.json()["data"]["items"]] == ["run-new"]
    assert [row["id"] for row in second.json()["data"]["items"]] == ["run-old"]


@pytest.mark.parametrize(
    "endpoint",
    ["/api/v1/tasks", "/api/v1/tasks/stats", "/api/v1/tasks/todo-stats"],
)
def test_read_endpoints_reject_unknown_scene(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
):
    database = _Database()
    client = _make_client(monkeypatch, database)

    response = client.get(endpoint, params={"scene": "discharged"})

    assert response.status_code == 422
    assert database.query_count == 0


@pytest.mark.parametrize(
    "endpoint",
    ["/api/v1/tasks", "/api/v1/tasks/stats", "/api/v1/tasks/todo-stats"],
)
def test_scene_query_failure_is_non_success_and_does_not_leak_details(
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
):
    database = _Database(
        task_rows=[_task("run", scene="running", created_at="01")],
        record_rows=[{"task_id": "run", "assignee_id": "user-1"}],
        fail_tables={"qc_tasks"},
    )
    client = _make_client(monkeypatch, database)
    params = {"scene": "running"}
    if endpoint != "/api/v1/tasks/todo-stats":
        params["tab"] = "received"

    response = client.get(endpoint, params=params)

    assert response.status_code == 500
    assert "secret database host" not in response.text


@pytest.mark.parametrize(
    ("method", "endpoint", "payload"),
    [
        ("post", "/api/v1/tasks", {"task_name": "场景任务", "scene": "running", "rule_set_key": "luxian_0609_qc_v1"}),
        ("get", "/api/v1/tasks/task-1", None),
    ],
)
def test_task_write_and_detail_failures_do_not_leak_database_details(
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None,
):
    database = _Database(fail_tables={"qc_tasks"})
    client = _make_client(monkeypatch, database)

    response = client.request(method, endpoint, json=payload)

    assert response.status_code == 500
    assert "secret database host" not in response.text
