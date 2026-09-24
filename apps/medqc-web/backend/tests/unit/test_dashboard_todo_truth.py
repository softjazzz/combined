from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.routers import dashboard_api


class _Query:
    def __init__(self, name):
        self.table_name = name

    def select(self, *args, **kwargs):
        return self


class _Supabase:
    def table(self, name):
        return _Query(name)


def _request():
    return Request({"type": "http", "method": "GET", "path": "/api/v1/dashboard/todo-stats", "headers": []})


@pytest.mark.asyncio
@pytest.mark.parametrize("scene", ["all", "outpatient_emergency"])
async def test_global_statuses_and_other_users_work_do_not_become_my_todos(monkeypatch, scene):
    rows = {
        "medical_records": [
            {"id": "r1", "status": "pending", "department": "内科", "record_type": "inpatient"},
            {"id": "r2", "status": "pending_review", "department": "内科", "record_type": "inpatient"},
        ],
        "qc_results": [{"id": "q1", "record_id": "r1", "grade": "A", "overall_score": 95}],
        "qc_appeals": [{"id": "a1", "record_id": "r1", "status": "pending", "user_id": "someone-else"}],
        "qc_remediation_tasks": [
            {"id": "t1", "record_id": "r1", "status": "submitted", "assignee_id": "someone-else"}
        ],
    }

    async def query(query):
        return SimpleNamespace(data=rows[query.table_name])

    monkeypatch.setattr(dashboard_api, "get_supabase", _Supabase)
    monkeypatch.setattr(dashboard_api, "async_execute", query)

    result = await dashboard_api.get_todo_stats(
        _request(), scene=scene, current_user={"user_id": "tester"}
    )
    data = result["data"]

    assert data["task_stats"] == {
        "countdown": None,
        "in_progress": None,
        "not_started": None,
    }
    assert data["defect_stats"] == {
        "clinical_appeals": None,
        "pending_review": None,
        "urged": None,
    }
    assert data["record_stats"]["pending_review"] is None
    assert data["record_stats"]["pending_recheck"] is None
    assert data["record_stats"]["total"] == (2 if scene == "all" else 0)
    assert data["overview"]["total_records"] == data["record_stats"]["total"]
    if scene == "all":
        assert data["overview"]["grade_a"] == 1
