"""任务运行 API 返回真实 job 身份，不调用旧演示执行。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks
from app.services.product_activation import require_product_activation
from app.services.task_qc_run_service import TaskQCRunConflict, TaskQCRunForbidden


def _client(monkeypatch, *, user=None):
    app = FastAPI()
    app.include_router(tasks.router)
    user = user or {"id": "user-1", "roles": ["admin"]}
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_product_activation] = lambda: user
    app.dependency_overrides[tasks.get_qc_service] = lambda: object()
    monkeypatch.setattr(tasks, "_sichuan_workspace_service", lambda: object())
    return TestClient(app)


def test_start_returns_exact_workspace_job_id(monkeypatch):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return {"task_id": kwargs["task_id"], "run_number": 2, "job_id": "job-2", "status": "queued"}

    monkeypatch.setattr(tasks, "create_task_qc_run", create)
    response = _client(monkeypatch).post("/api/v1/tasks/task-1/qc-runs")

    assert response.status_code == 200
    assert response.json()["data"]["job_id"] == "job-2"
    assert calls[0]["actor_id"] == "user-1"
    assert calls[0]["task_id"] == "task-1"
    assert calls[0]["run_scope"] == "all"
    assert callable(calls[0]["dispatch"])


def test_start_selected_records_validates_uuid_and_forwards_exact_ids(monkeypatch):
    record_id = "11111111-1111-4111-8111-111111111111"
    calls = []
    monkeypatch.setattr(tasks, "create_task_qc_run", lambda **kwargs: calls.append(kwargs) or {
        "task_id": "task-1", "run_number": 2, "job_id": "job-2", "run_scope": "all",
        "status": "queued", "task_record_ids": kwargs["task_record_ids"],
    })
    client = _client(monkeypatch)

    response = client.post("/api/v1/tasks/task-1/qc-runs", json={"task_record_ids": [record_id]})

    assert response.status_code == 200
    assert calls[0]["task_record_ids"] == [record_id]
    assert calls[0]["is_admin"] is True
    assert client.post(
        "/api/v1/tasks/task-1/qc-runs", json={"task_record_ids": ["not-a-uuid"]},
    ).status_code == 422


def test_non_admin_role_is_forwarded_without_elevation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        tasks,
        "create_task_qc_run",
        lambda **kwargs: calls.append(("create", kwargs))
        or {"task_id": "task-1", "run_number": 1, "job_id": "job-1", "status": "queued"},
    )
    monkeypatch.setattr(
        tasks,
        "list_task_qc_runs",
        lambda **kwargs: calls.append(("list", kwargs)) or [],
    )
    monkeypatch.setattr(
        tasks,
        "get_task_qc_run_record_result",
        lambda **kwargs: calls.append(("result", kwargs))
        or {"task_id": "task-1", "run_number": 1, "task_record_id": "record-1"},
    )
    client = _client(
        monkeypatch,
        user={"id": "staff-1", "roles": ["qc_staff"]},
    )

    assert client.post("/api/v1/tasks/task-1/qc-runs").status_code == 200
    assert client.get("/api/v1/tasks/task-1/qc-runs").status_code == 200
    assert client.get(
        "/api/v1/tasks/task-1/qc-runs/1/records/record-1",
    ).status_code == 200
    assert [item[1]["is_admin"] for item in calls] == [False, False, False]


def test_run_history_path_is_not_task_detail_and_is_creator_scoped(monkeypatch):
    calls = []

    def list_runs(**kwargs):
        calls.append(kwargs)
        return [{"task_id": "task-1", "run_number": 1, "job_id": "job-1"}]

    monkeypatch.setattr(tasks, "list_task_qc_runs", list_runs)
    response = _client(monkeypatch).get("/api/v1/tasks/task-1/qc-runs")

    assert response.status_code == 200
    assert response.json()["data"][0]["job_id"] == "job-1"
    assert calls[0]["task_id"] == "task-1"
    assert calls[0]["actor_id"] == "user-1"
    assert calls[0]["run_scope"] == "all"
    assert calls[0]["is_admin"] is True
    assert callable(calls[0]["workspace_factory"])


def test_assigned_scope_is_forwarded_and_invalid_scope_is_422(monkeypatch):
    creates = []
    lists = []
    monkeypatch.setattr(tasks, "create_task_qc_run", lambda **kwargs: creates.append(kwargs) or {
        "task_id": "task-1", "run_number": 1, "job_id": "job-1",
        "run_scope": "assigned", "status": "queued",
    })
    monkeypatch.setattr(tasks, "list_task_qc_runs", lambda **kwargs: lists.append(kwargs) or [])
    client = _client(monkeypatch)
    assert client.post("/api/v1/tasks/task-1/qc-runs?scope=assigned").json()["data"]["run_scope"] == "assigned"
    assert client.get("/api/v1/tasks/task-1/qc-runs?scope=assigned").status_code == 200
    assert creates[0]["run_scope"] == "assigned"
    assert lists[0]["task_id"] == "task-1"
    assert lists[0]["actor_id"] == "user-1"
    assert lists[0]["run_scope"] == "assigned"
    assert lists[0]["is_admin"] is True
    assert client.post("/api/v1/tasks/task-1/qc-runs?scope=other").status_code == 422
    assert client.get("/api/v1/tasks/task-1/qc-runs?scope=other").status_code == 422
    assert len(creates) == len(lists) == 1


def test_exact_record_result_route_forwards_identity_and_scope(monkeypatch):
    calls = []
    monkeypatch.setattr(tasks, "get_task_qc_run_record_result", lambda **kwargs: calls.append(kwargs) or {
        "task_id": "task-1", "run_number": 3, "task_record_id": "association-1",
        "job_id": "job-3", "job_status": "completed", "result_state": "available",
        "rule_set_key": "luxian_0609_qc_v1", "items": [{"rule_id": "LX0609-001"}],
    })
    response = _client(monkeypatch).get(
        "/api/v1/tasks/task-1/qc-runs/3/records/association-1?scope=assigned"
    )
    assert response.status_code == 200
    assert response.json()["data"]["items"] == [{"rule_id": "LX0609-001"}]
    assert calls[0]["actor_id"] == "user-1"
    assert calls[0]["run_scope"] == "assigned"
    assert calls[0]["task_record_id"] == "association-1"
    assert _client(monkeypatch).get(
        "/api/v1/tasks/task-1/qc-runs/3/records/association-1?scope=other"
    ).status_code == 422


def test_exact_record_result_route_rejects_conflict_and_forbidden(monkeypatch):
    def forbidden(**_):
        raise TaskQCRunForbidden("forbidden")

    monkeypatch.setattr(tasks, "get_task_qc_run_record_result", forbidden)
    path = "/api/v1/tasks/task-1/qc-runs/1/records/association-1"
    assert _client(monkeypatch).get(path).status_code == 403

    def conflict(**_):
        raise TaskQCRunConflict("incomplete")

    monkeypatch.setattr(tasks, "get_task_qc_run_record_result", conflict)
    assert _client(monkeypatch).get(path).status_code == 409
