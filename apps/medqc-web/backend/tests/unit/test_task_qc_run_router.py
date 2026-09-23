"""任务运行 API 返回真实 job 身份，不调用旧演示执行。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks
from app.services.product_activation import require_product_activation


def _client(monkeypatch):
    app = FastAPI()
    app.include_router(tasks.router)
    user = {"id": "user-1", "roles": ["admin"]}
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
    assert callable(calls[0]["dispatch"])


def test_run_history_path_is_not_task_detail_and_is_creator_scoped(monkeypatch):
    calls = []

    def list_runs(**kwargs):
        calls.append(kwargs)
        return [{"task_id": "task-1", "run_number": 1, "job_id": "job-1"}]

    monkeypatch.setattr(tasks, "list_task_qc_runs", list_runs)
    response = _client(monkeypatch).get("/api/v1/tasks/task-1/qc-runs")

    assert response.status_code == 200
    assert response.json()["data"][0]["job_id"] == "job-1"
    assert calls == [{"task_id": "task-1", "actor_id": "user-1"}]
