"""任务列表科室范围、医院日期和旧待办调用的聚焦合同。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks as routes
from app.services.task_list_summary_service import unknown_summary
from app.services.task_list_filter_service import (
    TaskDepartmentScopeInvalid,
    TaskListFilterInvalid,
    parse_task_list_filter,
    task_matches_department,
)


def test_hospital_calendar_dates_become_utc_half_open_window():
    task_filter = parse_task_list_filter(
        created_start="2026-09-02", created_end="2026-09-02",
    )

    assert task_filter.utc_start == datetime(2026, 9, 1, 16, tzinfo=timezone.utc)
    assert task_filter.utc_end_exclusive == datetime(2026, 9, 2, 16, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"created_start": "2026/09/02"},
        {"created_start": "2026-09-03", "created_end": "2026-09-02"},
        {"created_end": "9999-12-31"},
    ],
)
def test_invalid_or_unrepresentable_dates_are_rejected(kwargs):
    with pytest.raises(TaskListFilterInvalid):
        parse_task_list_filter(**kwargs)


def test_saved_department_scope_is_exact_and_empty_scope_means_all_departments():
    assert task_matches_department(None, "心内科") is True
    assert task_matches_department("[]", "心内科") is True
    assert task_matches_department('["心内科"]', "心内科") is True
    assert task_matches_department('["心内科一区"]', "心内科") is False
    assert task_matches_department("bad-json", None) is True
    with pytest.raises(TaskDepartmentScopeInvalid):
        task_matches_department("bad-json", "心内科")


def test_existing_todo_stats_reader_call_keeps_empty_filter_compatibility(monkeypatch):
    async def no_assignments(_sb, _current_user):
        return []

    monkeypatch.setattr(routes, "_received_task_ids", no_assignments)
    rows = asyncio.run(routes._received_todo_rows(
        object(),
        {"id": "qc-1"},
        None,
        columns="id,status,deadline",
    ))
    assert rows == []


class _TaskQuery:
    def __init__(self, rows):
        self.rows = list(rows)
        self.filters = []
        self.orders = []
        self.bounds = (0, len(rows) - 1)

    def select(self, _columns, count=None):
        assert count == "exact"
        return self

    def eq(self, field, value):
        self.filters.append(lambda row: row.get(field) == value)
        return self

    def is_(self, field, value):
        self.filters.append(lambda row: row.get(field) is value)
        return self

    def gte(self, field, value):
        self.filters.append(lambda row: str(row.get(field) or "") >= value)
        return self

    def lt(self, field, value):
        self.filters.append(lambda row: str(row.get(field) or "") < value)
        return self

    def or_ilike(self, fields, pattern):
        needle = pattern.strip("%").lower()
        self.filters.append(
            lambda row: any(needle in str(row.get(field) or "").lower() for field in fields)
        )
        return self

    def order(self, field, desc=False):
        self.orders.append((field, desc))
        return self

    def range(self, start, end):
        self.bounds = (start, end)
        return self

    def execute(self):
        rows = [row for row in self.rows if all(check(row) for check in self.filters)]
        for field, desc in reversed(self.orders):
            rows.sort(key=lambda row: str(row.get(field) or ""), reverse=desc)
        total = len(rows)
        start, end = self.bounds
        return SimpleNamespace(data=rows[start:end + 1], count=total)


class _TaskClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "qc_tasks"
        return _TaskQuery(self.rows)


class _BadCountQuery(_TaskQuery):
    def execute(self):
        response = super().execute()
        response.count = True
        return response


class _BadCountClient(_TaskClient):
    def table(self, name):
        assert name == "qc_tasks"
        return _BadCountQuery(self.rows)


def _api_client(monkeypatch, rows) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "manager", "roles": ["admin"],
    }
    monkeypatch.setattr(routes, "get_supabase", lambda: _TaskClient(rows))
    return TestClient(app)


def test_full_department_filter_happens_before_count_and_page(monkeypatch):
    rows = [
        {"id": "3", "created_at": "2026-09-03T00:00:00Z", "department_filter": '["外科"]'},
        {"id": "2", "created_at": "2026-09-02T00:00:00Z", "department_filter": "[]"},
        {"id": "1", "created_at": "2026-09-01T00:00:00Z", "department_filter": '["心内科"]'},
    ]
    monkeypatch.setattr(routes, "_TASK_FILTER_READ_PAGE_SIZE", 1)
    filtered = asyncio.run(routes._read_all_task_filter_rows(
        _TaskClient(rows),
        tab="all",
        current_user={"id": "manager", "roles": ["admin"]},
        scene=None,
        status=None,
        keyword=None,
        task_filter=parse_task_list_filter(department="心内科"),
    ))

    assert [row["id"] for row in filtered] == ["2", "1"]


def test_list_and_stats_http_endpoints_share_exact_filters_before_pagination(monkeypatch):
    rows = [
        {
            "id": "4", "task_name": "重点四", "task_number": "N4",
            "scene": "running", "status": "completed",
            "created_at": "2026-09-02T08:00:00Z", "department_filter": '["心内科"]',
        },
        {
            "id": "3", "task_name": "重点三", "task_number": "N3",
            "scene": "running", "status": "completed",
            "created_at": "2026-09-02T07:00:00Z", "department_filter": "[]",
        },
        {
            "id": "2", "task_name": "重点二", "task_number": "N2",
            "scene": "running", "status": "completed",
            "created_at": "2026-09-02T06:00:00Z", "department_filter": '["外科"]',
        },
        {
            "id": "1", "task_name": "重点一", "task_number": "N1",
            "scene": "running", "status": "completed",
            "created_at": "2026-08-31T08:00:00Z", "department_filter": '["心内科"]',
        },
    ]
    monkeypatch.setattr(routes, "_TASK_FILTER_READ_PAGE_SIZE", 1)
    client = _api_client(monkeypatch, rows)
    params = {
        "tab": "all", "scene": "running", "status": "completed",
        "keyword": "重点", "department": "心内科",
        "created_start": "2026-09-02", "created_end": "2026-09-02",
    }

    listed = client.get("/api/v1/tasks", params={**params, "page": 2, "page_size": 1})
    stats = client.get("/api/v1/tasks/stats", params=params)

    assert listed.status_code == 200
    data = listed.json()["data"]
    # 列表项另带“我创建/受领”汇总字段（无汇总来源时为未知 None），此处只比对筛选与分页。
    assert data["items"] == [{**rows[1], **unknown_summary()}]
    assert {k: v for k, v in data.items() if k != "items"} == {
        "total": 2, "page": 2, "page_size": 1, "total_pages": 2,
    }
    assert stats.status_code == 200
    assert stats.json()["data"] == {
        "total": 2,
        "by_status": {"completed": 2},
        "draft": 0,
        "in_progress": 0,
        "completed": 2,
        "cancelled": 0,
        "department_options": ["外科", "心内科"],
    }


def test_list_http_endpoint_rejects_unverifiable_exact_count(monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "manager", "roles": ["admin"],
    }
    monkeypatch.setattr(routes, "get_supabase", lambda: _BadCountClient([]))

    response = TestClient(app).get("/api/v1/tasks", params={"tab": "all"})

    assert response.status_code == 503
    assert response.json()["detail"] == "任务列表总数不可验证"
