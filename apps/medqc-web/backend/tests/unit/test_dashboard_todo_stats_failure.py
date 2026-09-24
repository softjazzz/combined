import pytest
from fastapi import HTTPException
from starlette.requests import Request
from types import SimpleNamespace

from app.routers import dashboard_api


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/api/v1/dashboard/todo-stats", "headers": []})


class _Query:
    def __init__(self, table_name):
        self.table_name = table_name

    def select(self, *args, **kwargs):
        return self


class _Supabase:
    def table(self, table_name):
        return _Query(table_name)


@pytest.mark.asyncio
async def test_todo_stats_db_unavailable_fails_closed_without_memory_fallback(monkeypatch):
    async def unavailable(*args, **kwargs):
        return None

    async def unexpected_memory_read():
        raise AssertionError("unavailable DB must not read fallback records")

    monkeypatch.setattr(dashboard_api, "_get_db_stats_by_scene", unavailable)
    monkeypatch.setattr(dashboard_api, "_aggregate_from_memory", unexpected_memory_read)

    with pytest.raises(HTTPException) as error:
        await dashboard_api.get_todo_stats(_request(), scene="all", current_user={"user_id": "tester"})

    assert error.value.status_code == 503
    assert error.value.detail == "待办统计暂不可用，请稍后重试"


@pytest.mark.asyncio
async def test_todo_stats_real_zero_counts_are_not_treated_as_failure(monkeypatch):
    async def empty_stats(*args, **kwargs):
        return {
            "records": {"total": 0, "by_status": {}, "by_department": {}},
            "qc": {"total": 0, "avg_score": 0, "by_grade": {}},
            "appeals": {"by_status": {}},
            "remediation": {"total": 0, "by_status": {}},
        }

    monkeypatch.setattr(dashboard_api, "_get_db_stats_by_scene", empty_stats)

    result = await dashboard_api.get_todo_stats(_request(), scene="all", current_user={"user_id": "tester"})

    assert result["success"] is True
    assert result["data"]["record_stats"]["total"] == 0
    assert result["data"]["task_stats"] == {
        "countdown": None,
        "in_progress": None,
        "not_started": None,
    }
    assert result["data"]["defect_stats"] == {
        "clinical_appeals": None,
        "pending_review": None,
        "urged": None,
    }
    assert result["data"]["record_stats"]["pending_review"] is None
    assert result["data"]["record_stats"]["pending_recheck"] is None
    assert result["data"]["overview"]["pass_rate"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_table", ["qc_appeals", "qc_remediation_tasks"])
async def test_todo_stats_partial_source_failure_does_not_publish_false_zero(monkeypatch, failed_table):
    async def query(query):
        if query.table_name == failed_table:
            raise RuntimeError("private connection detail")
        return SimpleNamespace(data=[])

    monkeypatch.setattr(dashboard_api, "get_supabase", _Supabase)
    monkeypatch.setattr(dashboard_api, "async_execute", query)

    with pytest.raises(HTTPException) as error:
        await dashboard_api.get_todo_stats(_request(), scene="all", current_user={"user_id": "tester"})

    assert error.value.status_code == 503
    assert error.value.detail == "待办统计暂不可用，请稍后重试"
