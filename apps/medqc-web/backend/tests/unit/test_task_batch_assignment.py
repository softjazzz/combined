"""全部任务批量分配：限量、逐项事务结果与权限守卫。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import tasks
from app.services.task_assignment_service import AssignmentConflict, AssignmentForbidden


def _payload(task_ids: list[str]) -> dict:
    return {
        "tasks": [
            {
                "task_id": task_id,
                "method": "by_original_reviewer" if task_id == "original" else "by_ratio",
                **({"fallback": "reject"} if task_id == "original" else {}),
            }
            for task_id in task_ids
        ],
        "assignees": [{"user_id": "qc-1", "user_name": "质控员甲"}],
    }


def _client(monkeypatch, assign):
    events: list[dict] = []
    monkeypatch.setattr(tasks, "assign_task_records", assign)
    monkeypatch.setattr(tasks, "audit_event", lambda _request, **kwargs: events.append(kwargs))
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[tasks.get_current_user] = lambda: {
        "id": "owner", "roles": ["qc_manager"], "display_name": "质控主管",
    }
    return TestClient(app), events


def test_batch_assignment_reports_each_independent_result_in_input_order(monkeypatch):
    calls: list[dict] = []

    def assign(**kwargs):
        calls.append(kwargs)
        if kwargs["task_id"] == "conflict":
            raise AssignmentConflict(
                "有病历无原质控员", code="original_reviewer_unmatched", unmatched_count=2,
            )
        if kwargs["task_id"] == "forbidden":
            raise AssignmentForbidden("仅任务创建人可分配")
        return {
            "task_id": kwargs["task_id"], "total_assigned": 3,
            "assignment_summary": {"质控员甲": 3}, "assignment_details": [],
            "idempotent": False,
        }

    client, events = _client(monkeypatch, assign)
    with client:
        response = client.post(
            "/api/v1/tasks/batch-assign",
            json=_payload(["ok", "original", "conflict", "forbidden"]),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["atomic"] is False
    assert (data["total"], data["success_count"], data["failed_count"]) == (4, 2, 2)
    assert [item["task_id"] for item in data["items"]] == [
        "ok", "original", "conflict", "forbidden",
    ]
    assert data["items"][2] == {
        "task_id": "conflict", "success": False, "status": 409,
        "message": "有病历无原质控员", "code": "original_reviewer_unmatched",
        "details": {"unmatched_count": 2},
    }
    assert data["items"][3]["status"] == 403
    assert calls[1]["task_id"] == "original"
    assert calls[1]["method"] == "by_original_reviewer"
    assert calls[1]["fallback"] == "reject"
    assert all(call["actor_id"] == "owner" for call in calls)
    assert events[-1]["outcome"] == "partial"
    assert events[-1]["details"] == {
        "task_ids": ["ok", "original", "conflict", "forbidden"],
        "assignees_count": 1, "success_count": 2, "failed_count": 2,
    }


def test_batch_assignment_rejects_duplicate_ids_before_any_write(monkeypatch):
    calls: list[dict] = []
    client, events = _client(monkeypatch, lambda **kwargs: calls.append(kwargs))

    with client:
        response = client.post(
            "/api/v1/tasks/batch-assign",
            json=_payload(["same", "same"]),
        )

    assert response.status_code == 422
    assert calls == []
    assert events == []


def test_batch_assignment_rejects_more_than_twenty_tasks(monkeypatch):
    calls: list[dict] = []
    client, _events = _client(monkeypatch, lambda **kwargs: calls.append(kwargs))

    with client:
        response = client.post(
            "/api/v1/tasks/batch-assign",
            json=_payload([f"task-{index}" for index in range(21)]),
        )

    assert response.status_code == 422
    assert calls == []


def test_batch_assignment_server_checks_every_task_owner_and_state(monkeypatch):
    calls: list[str] = []

    def assign(**kwargs):
        calls.append(kwargs["task_id"])
        if kwargs["task_id"] == "not-owner":
            raise AssignmentForbidden("仅任务创建人可分配")
        if kwargs["task_id"] == "not-sampling":
            raise AssignmentConflict("任务状态不允许分配")
        return {
            "task_id": kwargs["task_id"], "total_assigned": 1,
            "assignment_summary": {"质控员甲": 1}, "assignment_details": [],
            "idempotent": False,
        }

    client, _events = _client(monkeypatch, assign)
    with client:
        response = client.post(
            "/api/v1/tasks/batch-assign",
            json=_payload(["not-owner", "not-sampling", "ok"]),
        )

    data = response.json()["data"]
    assert calls == ["not-owner", "not-sampling", "ok"]
    assert [item["status"] for item in data["items"][:2]] == [403, 409]
    assert data["items"][2]["success"] is True


def test_batch_assignment_sanitizes_unexpected_error_without_traceback_log(monkeypatch):
    logs: list[tuple[tuple, dict]] = []

    def assign(**_kwargs):
        raise RuntimeError("sql params: patient-secret")

    monkeypatch.setattr(tasks.logger, "error", lambda *args, **kwargs: logs.append((args, kwargs)))
    client, _events = _client(monkeypatch, assign)
    with client:
        response = client.post("/api/v1/tasks/batch-assign", json=_payload(["failed-task"]))

    item = response.json()["data"]["items"][0]
    assert item == {
        "task_id": "failed-task",
        "success": False,
        "status": 503,
        "message": "任务分配暂不可用",
    }
    assert logs == [(
        ("批量任务分配单项失败 code=assignment_unavailable task_id=%s", "failed-task"),
        {},
    )]
