"""任务分析 HTTP 权限与脱敏错误合同。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import quality_reports as routes
from app.services import task_analysis_service as service

BASE = "/api/v1/quality-reports/tasks/task-1"


def _client(user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.mark.parametrize(
    "user,expected_manager",
    [
        ({"id": "creator", "roles": ["qc_staff"]}, False),
        ({"id": "admin-1", "roles": ["admin"]}, True),
        ({"id": "manager-1", "roles": ["qc_manager"]}, True),
    ],
)
def test_read_permission_and_object_context_are_passed_to_service(monkeypatch, user, expected_manager):
    captured = {}

    def analyze(**kwargs):
        captured.update(kwargs)
        return {"contract_version": "task-analysis-v1", "task": {"id": kwargs["task_id"]}}

    monkeypatch.setattr(service, "get_task_analysis", analyze)
    response = _client(user).get(BASE)
    assert response.status_code == 200
    assert captured == {"task_id": "task-1", "actor_id": user["id"], "is_manager": expected_manager}


def test_missing_identity_and_missing_read_permission_precede_service(monkeypatch):
    monkeypatch.setattr(
        service, "get_task_analysis", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不可调用服务")),
    )
    assert _client({"roles": ["admin"]}).get(BASE).status_code == 401
    assert _client({"id": "user-1", "roles": ["unknown"]}).get(BASE).status_code == 403


@pytest.mark.parametrize(
    "error,status",
    [
        (service.TaskAnalysisInvalid("任务标识无效"), 422),
        (service.TaskAnalysisNotFound("任务不存在"), 404),
        (service.TaskAnalysisForbidden("仅任务创建人或管理员可查看整任务分析"), 403),
    ],
)
def test_known_errors_keep_stable_http_semantics(monkeypatch, error, status):
    monkeypatch.setattr(service, "get_task_analysis", lambda **_kwargs: (_ for _ in ()).throw(error))
    response = _client({"id": "creator", "roles": ["qc_staff"]}).get(BASE)
    assert response.status_code == status


def test_unknown_error_is_sanitized(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_task_analysis",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("patient P001 private SQL")),
    )
    response = _client({"id": "creator", "roles": ["qc_staff"]}).get(BASE)
    assert response.status_code == 503
    assert response.json()["detail"] == "任务分析暂不可用，请稍后重试"
    assert "P001" not in response.text and "private SQL" not in response.text
