"""任务详情沿用列表个人范围，关联清单不得混入其他质控员。"""

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
        self.orders = []
        self.one = False

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filters.append((key, {value}))
        return self

    def in_(self, key, values):
        self.filters.append((key, set(values)))
        return self

    def order(self, key):
        self.orders.append(key)
        return self

    def single(self):
        self.one = True
        return self

    def execute(self):
        self.database.calls.append(self)
        if self.table in self.database.fail_tables:
            raise RuntimeError("private SQL connection failure")
        rows = [dict(row) for row in self.database.rows[self.table]]
        for key, values in self.filters:
            rows = [row for row in rows if row.get(key) in values]
        for key in reversed(self.orders):
            rows.sort(key=lambda row: (row.get(key) is None, row.get(key) or ""))
        if self.table == "qc_task_records" and self.database.reassign_after_scope_read:
            self.database.reassign_after_scope_read = False
            for row in self.database.rows["qc_task_records"]:
                if row.get("assignee_id") == "u-1":
                    row["assignee_id"] = "u-2"
        return SimpleNamespace(data=(rows[0] if rows else None) if self.one else rows)


class Database:
    def __init__(self):
        self.rows = {
            "qc_tasks": [
                {"id": "shared", "creator_id": "u-1", "task_name": "共享任务", "total_records": 3, "progress": 25},
                {"id": "other", "creator_id": "u-2", "task_name": "不可见任务", "total_records": 1},
                {"id": "empty", "creator_id": "u-1", "total_records": 0},
            ],
            "qc_task_records": [
                {"id": "b", "task_id": "shared", "record_id": "same-visit", "assignee_id": "u-1", "created_at": "2026-09-22", "score": None},
                {"id": "c", "task_id": "shared", "record_id": "other-visit", "assignee_id": "u-2", "created_at": "2026-09-22", "score": 90},
                {"id": "a", "task_id": "shared", "record_id": "same-visit", "assignee_id": "u-1", "created_at": "2026-09-22", "score": 0},
                {"id": "d", "task_id": "other", "record_id": "private-visit", "assignee_id": "u-2", "created_at": "2026-09-22"},
            ],
        }
        self.calls = []
        self.fail_tables = set()
        self.reassign_after_scope_read = False

    def table(self, name):
        return Query(self, name)


def client_for(monkeypatch, database, **identity):
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: {"roles": ["admin"], **identity}
    monkeypatch.setattr(tasks, "get_supabase", lambda: database)

    async def execute(query):
        return query.execute()

    monkeypatch.setattr(tasks, "async_execute", execute)
    return TestClient(app)


def test_received_records_are_isolated_without_reinterpreting_task_totals(monkeypatch):
    database = Database()
    client = client_for(monkeypatch, database, id="u-1", user_id="u-2")
    response = client.get("/api/v1/tasks/shared", params={"tab": "received"})
    assert response.status_code == 200
    detail = response.json()["data"]
    assert [row["id"] for row in detail["records"]] == ["a", "b"]
    assert [row["score"] for row in detail["records"]] == [0, None]
    assert detail["total_records"] == 3 and detail["progress"] == 25
    assert len(database.calls) == 3


def test_other_assignee_only_sees_their_record(monkeypatch):
    client = client_for(monkeypatch, Database(), user_id="u-2")
    response = client.get("/api/v1/tasks/shared?tab=received")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]["records"]] == ["c"]


@pytest.mark.parametrize("tab", [None, "all", "created"])
def test_all_and_creator_can_read_full_stable_assignment_list(monkeypatch, tab):
    client = client_for(monkeypatch, Database(), id="u-1")
    response = client.get("/api/v1/tasks/shared", params={} if tab is None else {"tab": tab})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]["records"]] == ["a", "b", "c"]


@pytest.mark.parametrize("tab", ["created", "received"])
def test_task_outside_personal_scope_returns_not_found_without_details(monkeypatch, tab):
    client = client_for(monkeypatch, Database(), id="u-1")
    response = client.get("/api/v1/tasks/other", params={"tab": tab})
    assert response.status_code == 404
    assert "不可见任务" not in response.text and "private-visit" not in response.text


def test_received_with_no_assignments_does_not_read_task_or_other_records(monkeypatch):
    database = Database()
    response = client_for(monkeypatch, database, id="nobody").get("/api/v1/tasks/shared?tab=received")
    assert response.status_code == 404
    assert len(database.calls) == 1
    assert database.calls[0].filters == [("assignee_id", {"nobody"})]


def test_received_assignment_revoked_during_read_does_not_return_task_metadata(monkeypatch):
    database = Database()
    database.reassign_after_scope_read = True
    response = client_for(monkeypatch, database, id="u-1").get("/api/v1/tasks/shared?tab=received")
    assert response.status_code == 404
    assert "共享任务" not in response.text and "same-visit" not in response.text


@pytest.mark.parametrize("tab", ["created", "received"])
def test_missing_personal_identity_rejected_before_data_queries(monkeypatch, tab):
    database = Database()
    response = client_for(monkeypatch, database).get("/api/v1/tasks/shared", params={"tab": tab})
    assert response.status_code == 401
    assert database.calls == []


@pytest.mark.parametrize("tab", ["", "everyone", "null"])
def test_invalid_tab_is_not_an_all_scope_fallback(monkeypatch, tab):
    database = Database()
    response = client_for(monkeypatch, database, id="u-1").get("/api/v1/tasks/shared", params={"tab": tab})
    assert response.status_code == 422
    assert database.calls == []


def test_genuine_empty_task_is_successfully_empty(monkeypatch):
    response = client_for(monkeypatch, Database(), id="u-1").get("/api/v1/tasks/empty?tab=created")
    assert response.status_code == 200
    assert response.json()["data"]["records"] == []


def test_missing_task_is_404(monkeypatch):
    response = client_for(monkeypatch, Database(), id="u-1").get("/api/v1/tasks/missing")
    assert response.status_code == 404


def test_unavailable_database_is_503(monkeypatch):
    response = client_for(monkeypatch, None, id="u-1").get("/api/v1/tasks/shared")
    assert response.status_code == 503


@pytest.mark.parametrize("table,tab", [("qc_tasks", "all"), ("qc_task_records", "all"), ("qc_task_records", "received")])
def test_query_failures_are_not_fake_empty_success(monkeypatch, table, tab):
    database = Database()
    database.fail_tables.add(table)
    response = client_for(monkeypatch, database, id="u-1").get("/api/v1/tasks/shared", params={"tab": tab})
    assert response.status_code == 500
    assert "private SQL" not in response.text
