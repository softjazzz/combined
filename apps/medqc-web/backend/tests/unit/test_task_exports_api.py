"""全部任务导出 HTTP 权限、上限和脱敏错误合同。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import task_exports as routes
from app.services import task_export_service as service

BASE = "/api/v1/task-exports"


def _client(user: dict) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.mark.parametrize("role", ["admin", "qc_manager"])
def test_manager_export_passes_only_real_filters_and_returns_safe_csv(monkeypatch, role):
    captured = {}
    audits = []

    def export(**kwargs):
        captured.update(kwargs)
        return service.TaskExportResult(content=b"\xef\xbb\xbfa,b\r\n1,2\r\n", row_count=1)

    monkeypatch.setattr(service, "export_all_tasks", export)
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))
    response = _client({"id": "manager", "roles": [role]}).get(
        BASE, params={
            "scene": "running", "status": "completed", "keyword": "重点",
            "department": "心内科", "created_start": "2026-09-01",
            "created_end": "2026-09-28",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "scene": "running", "status": "completed", "keyword": "重点",
        "department": "心内科", "created_start": "2026-09-01",
        "created_end": "2026-09-28",
    }
    assert response.content.startswith(b"\xef\xbb\xbf")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''task-list.csv"
    assert audits[0]["details"] == {
        "scene": "running",
        "status": "completed",
        "keyword_applied": True,
        "department_applied": True,
        "created_start": "2026-09-01",
        "created_end": "2026-09-28",
        "total_rows": 1,
        "limit": 5_000,
    }


def test_permission_and_manager_role_checks_precede_service(monkeypatch):
    monkeypatch.setattr(
        service, "export_all_tasks",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("不可调用服务")),
    )
    assert _client({"id": "staff", "roles": ["qc_staff"]}).get(BASE).status_code == 403
    assert _client({"id": "unknown", "roles": ["unknown"]}).get(BASE).status_code == 403
    assert _client({"roles": ["admin"]}).get(BASE).status_code == 401


def test_too_large_response_is_explicit_and_does_not_audit_success(monkeypatch):
    audits = []
    monkeypatch.setattr(
        service,
        "export_all_tasks",
        lambda **_kwargs: (_ for _ in ()).throw(service.TaskExportTooLarge(5_001)),
    )
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))

    response = _client({"id": "admin", "roles": ["admin"]}).get(BASE)

    assert response.status_code == 413
    assert response.json()["detail"] == {
        "code": "task_export_too_large",
        "message": "匹配任务超过 5000 条，请缩小筛选范围",
        "matched_at_least": 5_001,
        "limit": 5_000,
    }
    assert "text/csv" not in response.headers["content-type"]
    assert audits == []


def test_unknown_errors_are_sanitized_and_not_audited(monkeypatch):
    audits = []
    monkeypatch.setattr(
        service,
        "export_all_tasks",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("patient P001 private SQL")),
    )
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))

    response = _client({"id": "admin", "roles": ["admin"]}).get(BASE)

    assert response.status_code == 503
    assert response.json()["detail"] == "任务导出暂不可用，请稍后重试"
    assert "P001" not in response.text and "private SQL" not in response.text
    assert audits == []


@pytest.mark.parametrize(
    "params",
    [
        {"scene": "emergency"},
        {"page": 2},
        {"page_size": 100},
        {"start_date": "2026-09-01"},
    ],
)
def test_unknown_or_inactive_filter_contract_is_rejected(params):
    response = _client({"id": "admin", "roles": ["admin"]}).get(BASE, params=params)
    assert response.status_code == 422
