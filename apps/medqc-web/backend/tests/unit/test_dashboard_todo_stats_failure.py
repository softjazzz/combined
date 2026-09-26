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
    _stub_review_counts(monkeypatch)

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
    # 真实 0 是有效计数，不当作失败；无审核权限时人工缺陷待办仍为 None（不可用）。
    assert result["data"]["record_stats"]["pending_review"] == 0
    assert result["data"]["record_stats"]["pending_recheck"] == 0
    assert result["data"]["overview"]["pass_rate"] == 0


def _stub_review_counts(monkeypatch, *, initial=0, recheck=0, manual=0, fail=False):
    from app.routers import record_reviews
    from app.services import manual_defect_review_service

    def record_counts(actor_id, scene=None):
        if fail:
            raise RuntimeError("SELECT secret FROM qc_record_reviews")
        return {"initial": initial, "recheck": recheck}

    monkeypatch.setattr(record_reviews, "count_my_record_review_todos", record_counts)
    monkeypatch.setattr(manual_defect_review_service, "count_pending_manual_defects", lambda: manual)


async def _empty_stats(*args, **kwargs):
    return {
        "records": {"total": 0, "by_status": {}, "by_department": {}},
        "qc": {"total": 0, "avg_score": 0, "by_grade": {}},
        "appeals": {"by_status": {}},
        "remediation": {"total": 0, "by_status": {}},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(("scene", "role", "expected_manual"), [
    ("all", "qc_manager", 7),
    ("all", "qc_staff", None),
    ("running", "qc_manager", None),
])
async def test_review_todo_counts_pass_through_with_scope(monkeypatch, scene, role, expected_manual):
    monkeypatch.setattr(dashboard_api, "_get_db_stats_by_scene", _empty_stats)
    _stub_review_counts(monkeypatch, initial=3, recheck=2, manual=7)

    result = await dashboard_api.get_todo_stats(
        _request(), scene=scene, current_user={"user_id": "tester", "roles": [role]}
    )

    assert result["data"]["record_stats"]["pending_review"] == 3
    assert result["data"]["record_stats"]["pending_recheck"] == 2
    assert result["data"]["defect_stats"]["pending_review"] == expected_manual


@pytest.mark.asyncio
async def test_review_todo_count_failure_is_redacted_503(monkeypatch):
    monkeypatch.setattr(dashboard_api, "_get_db_stats_by_scene", _empty_stats)
    _stub_review_counts(monkeypatch, fail=True)

    with pytest.raises(HTTPException) as error:
        await dashboard_api.get_todo_stats(_request(), scene="all", current_user={"user_id": "tester"})

    assert error.value.status_code == 503
    assert "SELECT" not in str(error.value.detail)


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
