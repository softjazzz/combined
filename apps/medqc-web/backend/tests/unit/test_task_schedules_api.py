"""定时任务管理 HTTP 权限、参数、CAS 与脱敏错误合同。"""

from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import task_schedules as routes
from app.services import task_schedule_job_service as job_service
from app.services import task_schedule_service as schedule_service


BASE = "/api/v1/task-schedules"


def _client(user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _create_payload() -> dict:
    return {
        "source_task_id": "task-source",
        "source_configuration_version": 3,
        "timing_config": {
            "kind": "once",
            "timezone": "Asia/Shanghai",
            "run_at": "2026-10-01T09:30:00+08:00",
        },
    }


def _schedule() -> dict:
    return {
        "id": "schedule-1",
        "source_task_id": "task-source",
        "owner_id": "manager-1",
        "name": "每日质控",
        "scene": "running",
        "rule_set_key": "running_medical_record",
        "rule_set_version": "v1",
        "task_config": {
            "date_range": None,
            "department_filter": [],
            "sampling_method": "all",
            "sampling_config": {},
            "assign_method": "by_ratio",
            "assignee_config": {"assignees": [{"user_id": "qc-1", "ratio": 100}]},
        },
        "timing_config": {
            "kind": "once",
            "timezone": "Asia/Shanghai",
            "run_at": "2026-10-01T09:30:00+08:00",
        },
        "state": "active",
        "next_fire_at": "2026-10-01T01:30:00Z",
        "last_fire_at": None,
        "version": 1,
        "created_at": "2026-09-28T12:00:00Z",
        "updated_at": "2026-09-28T12:00:00Z",
    }


def _run() -> dict:
    return {
        "id": "run-1",
        "schedule_id": "schedule-1",
        "trigger_type": "manual",
        "scheduled_fire_at": "2026-09-28T12:30:00Z",
        "idempotency_key": "request-1",
        "status": "queued",
        "generated_task_id": None,
        "async_job_id": "job-1",
        "attempt_count": 0,
        "heartbeat_at": None,
        "started_at": None,
        "finished_at": None,
        "error_code": None,
        "error_message": None,
        "created_at": "2026-09-28T12:30:00Z",
        "updated_at": "2026-09-28T12:30:00Z",
    }


@pytest.mark.parametrize("role", ["admin", "qc_manager"])
def test_create_copies_source_draft_and_audits_only_stable_identifiers(monkeypatch, role):
    captured = {}
    audits = []

    def create(**kwargs):
        captured.update(kwargs)
        return _schedule()

    monkeypatch.setattr(schedule_service, "create_task_schedule", create)
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))

    response = _client({"id": " manager-1 ", "roles": [role]}).post(
        BASE,
        json=_create_payload(),
        headers={"Idempotency-Key": "create-request-1"},
    )

    assert response.status_code == 201
    assert captured == {
        "actor_id": "manager-1",
        "is_manager": True,
        "request_id": "create-request-1",
        "source_task_id": "task-source",
        "source_configuration_version": 3,
        "timing_config": {
            "kind": "once",
            "timezone": "Asia/Shanghai",
            "run_at": "2026-10-01T09:30:00+08:00",
        },
    }
    assert response.json()["data"]["source_task_id"] == "task-source"
    assert audits[0]["details"] == {
        "schedule_id": "schedule-1",
        "source_task_id": "task-source",
        "version": 1,
    }
    assert "timing_config" not in audits[0]["details"]


def test_create_rejects_extra_body_fields_before_service(monkeypatch):
    monkeypatch.setattr(
        schedule_service,
        "create_task_schedule",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不可调用服务")),
    )
    payload = _create_payload()
    payload["name"] = "客户端不得覆盖源草稿名称"

    response = _client({"id": "manager-1", "roles": ["admin"]}).post(
        BASE,
        json=payload,
        headers={"Idempotency-Key": "create-request-1"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("headers", [{}, {"Idempotency-Key": "contains space"}])
def test_create_requires_visible_ascii_idempotency_key_before_service(monkeypatch, headers):
    monkeypatch.setattr(
        schedule_service,
        "create_task_schedule",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不可调用服务")),
    )

    response = _client({"id": "manager-1", "roles": ["admin"]}).post(
        BASE,
        json=_create_payload(),
        headers=headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (
            schedule_service.TaskScheduleInvalid("源任务必须是未启动的单次草稿"),
            422,
            {"code": "schedule_invalid", "message": "源任务必须是未启动的单次草稿"},
        ),
        (
            schedule_service.TaskScheduleConflict("内部原始消息", code="request_conflict"),
            409,
            {"code": "request_conflict", "message": "请求编号已用于其他定时计划"},
        ),
    ],
)
def test_create_returns_actionable_controlled_errors(monkeypatch, error, status_code, detail):
    monkeypatch.setattr(
        schedule_service,
        "create_task_schedule",
        lambda **_kwargs: (_ for _ in ()).throw(error),
    )

    response = _client({"id": "manager-1", "roles": ["admin"]}).post(
        BASE,
        json=_create_payload(),
        headers={"Idempotency-Key": "create-request-1"},
    )

    assert response.status_code == status_code
    assert response.json()["detail"] == detail


def test_list_passes_only_frozen_pagination_and_state(monkeypatch):
    captured = {}

    def list_schedules(**kwargs):
        captured.update(kwargs)
        return {"items": [_schedule()], "total": 1, "page": 2, "page_size": 25}

    monkeypatch.setattr(schedule_service, "list_task_schedules", list_schedules)
    response = _client({"id": "manager-1", "roles": ["qc_manager"]}).get(
        BASE, params={"state": "paused", "page": 2, "page_size": 25},
    )

    assert response.status_code == 200
    assert captured == {
        "actor_id": "manager-1",
        "is_manager": True,
        "state": "paused",
        "page": 2,
        "page_size": 25,
    }
    assert response.json()["data"]["total"] == 1


@pytest.mark.parametrize(
    "path",
    [
        f"{BASE}?department=内科",
        f"{BASE}/schedule-1?include_private=true",
        f"{BASE}/schedule-1/runs?offset=10",
    ],
)
def test_read_routes_reject_uncontracted_query_fields(monkeypatch, path):
    monkeypatch.setattr(
        schedule_service,
        "list_task_schedules",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不可调用服务")),
    )
    monkeypatch.setattr(
        schedule_service,
        "get_task_schedule",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不可调用服务")),
    )
    monkeypatch.setattr(
        schedule_service,
        "list_task_schedule_runs",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不可调用服务")),
    )

    response = _client({"id": "manager-1", "roles": ["admin"]}).get(path)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "schedule_invalid"


def test_manager_role_and_stable_actor_are_checked_before_service(monkeypatch):
    monkeypatch.setattr(
        schedule_service,
        "list_task_schedules",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不可调用服务")),
    )

    assert _client({"id": "staff-1", "roles": ["qc_staff"]}).get(BASE).status_code == 403
    assert _client({"roles": ["admin"]}).get(BASE).status_code == 401


@pytest.mark.parametrize(
    ("action", "target_state"),
    [("pause", "paused"), ("resume", "active"), ("cancel", "cancelled")],
)
def test_state_actions_use_patch_and_cas_version(monkeypatch, action, target_state):
    captured = {}
    result = deepcopy(_schedule())
    result.update({"state": target_state, "version": 5})

    def change(schedule_id, **kwargs):
        captured.update({"schedule_id": schedule_id, **kwargs})
        return result

    monkeypatch.setattr(schedule_service, f"{action}_task_schedule", change)
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **_kwargs: None)
    client = _client({"id": "manager-1", "roles": ["admin"]})

    assert client.post(f"{BASE}/schedule-1/{action}", json={"version": 4}).status_code == 405
    response = client.patch(f"{BASE}/schedule-1/{action}", json={"version": 4})

    assert response.status_code == 200
    assert captured == {
        "schedule_id": "schedule-1",
        "actor_id": "manager-1",
        "is_manager": True,
        "expected_version": 4,
    }
    assert response.json()["data"]["state"] == target_state


def test_run_now_requires_visible_ascii_idempotency_key_and_passes_it_unchanged(monkeypatch):
    captured = {}

    def enqueue(**kwargs):
        captured.update(kwargs)
        return _run()

    monkeypatch.setattr(job_service, "enqueue_manual_schedule_run", enqueue)
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **_kwargs: None)
    client = _client({"id": "manager-1", "roles": ["qc_manager"]})

    assert client.post(f"{BASE}/schedule-1/run-now").status_code == 422
    assert client.post(
        f"{BASE}/schedule-1/run-now", headers={"Idempotency-Key": "contains space"},
    ).status_code == 422
    response = client.post(
        f"{BASE}/schedule-1/run-now", headers={"Idempotency-Key": "Request:ABC-123"},
    )

    assert response.status_code == 200
    assert captured == {
        "schedule_id": "schedule-1",
        "request_id": "Request:ABC-123",
        "actor_id": "manager-1",
        "is_manager": True,
    }


def test_retry_static_route_calls_job_service_without_request_payload(monkeypatch):
    captured = {}

    def retry(**kwargs):
        captured.update(kwargs)
        return _run()

    monkeypatch.setattr(job_service, "retry_schedule_run", retry)
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **_kwargs: None)
    response = _client({"id": "manager-1", "roles": ["admin"]}).post(
        f"{BASE}/runs/run-1/retry",
    )

    assert response.status_code == 200
    assert captured == {"run_id": "run-1", "actor_id": "manager-1", "is_manager": True}
    assert response.json()["data"]["id"] == "run-1"


def test_runs_list_passes_status_and_bounded_pagination(monkeypatch):
    captured = {}

    def list_runs(schedule_id, **kwargs):
        captured.update({"schedule_id": schedule_id, **kwargs})
        return {"items": [_run()], "total": 1, "page": 1, "page_size": 50}

    monkeypatch.setattr(schedule_service, "list_task_schedule_runs", list_runs)
    response = _client({"id": "manager-1", "roles": ["admin"]}).get(
        f"{BASE}/schedule-1/runs", params={"status": "failed", "page": 1, "page_size": 50},
    )

    assert response.status_code == 200
    assert captured == {
        "schedule_id": "schedule-1",
        "actor_id": "manager-1",
        "is_manager": True,
        "status": "failed",
        "page": 1,
        "page_size": 50,
    }


def test_unknown_service_errors_are_sanitized_and_not_success_audited(monkeypatch):
    audits = []
    monkeypatch.setattr(
        schedule_service,
        "get_task_schedule",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("patient P001 private SQL")),
    )
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))

    response = _client({"id": "manager-1", "roles": ["admin"]}).get(f"{BASE}/schedule-1")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "schedule_unavailable",
        "message": "定时计划暂不可用，请稍后重试",
    }
    assert "P001" not in response.text and "private SQL" not in response.text
    assert audits == []
