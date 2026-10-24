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


def _stub_review_counts(monkeypatch, *, initial=0, recheck=0, manual=0):
    from app.routers import record_reviews
    from app.services import manual_defect_review_service

    calls = []

    def record_counts(actor_id, scene=None):
        calls.append((actor_id, scene))
        return {"initial": initial, "recheck": recheck}

    monkeypatch.setattr(record_reviews, "count_my_record_review_todos", record_counts)
    monkeypatch.setattr(
        manual_defect_review_service,
        "count_pending_manual_defects",
        lambda *, scene="all", actor_id: manual,
    )
    return calls


def _request():
    return Request({"type": "http", "method": "GET", "path": "/api/v1/dashboard/todo-stats", "headers": []})


@pytest.mark.asyncio
async def test_review_source_unavailable_preserves_null_and_manual_source(monkeypatch):
    from app.routers import record_reviews
    from app.services import manual_defect_review_service

    monkeypatch.setattr(record_reviews, "count_my_record_review_todos", lambda *_args: {
        "initial": None, "recheck": None, "unavailable_reason": "review_source_unavailable",
    })
    monkeypatch.setattr(manual_defect_review_service, "count_pending_manual_defects", lambda **_kwargs: 2)
    async def db_stats(**_kwargs):
        return {"records": {"total": 3}, "qc": {}}
    monkeypatch.setattr(dashboard_api, "_get_db_stats_by_scene", db_stats)
    result = await dashboard_api.get_todo_stats(
        _request(), scene="outpatient_emergency", current_user={"user_id": "tester", "roles": ["qc_manager"]},
    )
    assert result["data"]["record_stats"] == {
        "pending_review": None, "pending_recheck": None, "total": 3,
        "unavailable_reason": "review_source_unavailable",
    }
    assert result["data"]["defect_stats"]["pending_review"] == 2


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
    calls = _stub_review_counts(monkeypatch)

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
    # 病历审核待办只来自审核服务的本人计数；medical_records 的全局 pending_review 状态不能冒充。
    assert data["record_stats"]["pending_review"] == 0
    assert data["record_stats"]["pending_recheck"] == 0
    assert calls == [("tester", scene)]
    assert data["record_stats"]["total"] == (2 if scene == "all" else 0)
    assert data["overview"]["total_records"] == data["record_stats"]["total"]
    if scene == "all":
        assert data["overview"]["grade_a"] == 1
