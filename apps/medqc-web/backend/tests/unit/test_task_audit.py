from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.access_control import enforce_default_auth
from app.services.task_delete_service import TaskDeleteConflict


@pytest.fixture
def client(app):
    # 本文件只测路由合同，不启动会在真实数据库重建视图的 lifespan。
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()


def _admin_headers(client) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@medqc.com", "password": "admin888"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_assign_task_emits_audit_event(client, monkeypatch):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    headers = _admin_headers(client)
    audit_calls: list[dict] = []
    monkeypatch.setattr(
        "app.routers.tasks.assign_task_records",
        lambda **_kwargs: {
            "task_id": "task-1", "total_assigned": 2,
            "assignment_summary": {"QC One": 2},
            "assignment_details": [{"user_id": "qc-1", "user_name": "QC One", "count": 2}],
            "idempotent": False,
        },
    )
    monkeypatch.setattr(
        "app.routers.tasks.audit_event",
        lambda _request, **kwargs: audit_calls.append(kwargs),
    )

    resp = client.post(
        "/api/v1/tasks/task-1/assign",
        json={
            "assignees": [{"user_id": "qc-1", "user_name": "QC One"}],
            "method": "by_ratio",
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total_assigned"] == 2
    assert any(
        call.get("action") == "tasks.assignment.update"
        and call.get("details", {}).get("task_id") == "task-1"
        and call.get("details", {}).get("total_assigned") == 2
        for call in audit_calls
    )
    client.app.dependency_overrides.clear()


def test_assignee_options_empty_and_db_failure(client, monkeypatch):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    headers = _admin_headers(client)
    monkeypatch.setattr("app.routers.tasks.list_qc_assignee_options", lambda: [])
    response = client.get("/api/v1/tasks/assignee-options", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"] == []

    def _fail():
        raise RuntimeError("private database detail")

    monkeypatch.setattr("app.routers.tasks.list_qc_assignee_options", _fail)
    response = client.get("/api/v1/tasks/assignee-options", headers=headers)
    assert response.status_code == 503
    assert "private database detail" not in response.text
    client.app.dependency_overrides.clear()


def test_update_cannot_set_assigned_directly(client, monkeypatch):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    headers = _admin_headers(client)

    def _unexpected_db_call():
        raise AssertionError("validation must reject before database access")

    monkeypatch.setattr("app.routers.tasks.get_supabase", _unexpected_db_call)
    response = client.put(
        "/api/v1/tasks/task-1", json={"status": "assigned"}, headers=headers
    )
    assert response.status_code == 422
    client.app.dependency_overrides.clear()


def test_delete_task_emits_audit_event(client, monkeypatch):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    headers = _admin_headers(client)
    audit_calls: list[dict] = []

    deleted: list[str] = []
    # 草稿删除保护由 test_task_delete_guard 覆盖；此处只验证路由审计。
    monkeypatch.setattr(
        "app.routers.tasks.delete_empty_draft_task",
        lambda *, task_id, actor_id: deleted.append(task_id),
    )
    monkeypatch.setattr(
        "app.routers.tasks.audit_event",
        lambda _request, **kwargs: audit_calls.append(kwargs),
    )

    resp = client.delete("/api/v1/tasks/task-del-1", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert deleted == ["task-del-1"]
    assert any(
        call.get("action") == "tasks.lifecycle.delete"
        and call.get("details", {}).get("task_id") == "task-del-1"
        for call in audit_calls
    )
    client.app.dependency_overrides.clear()


def test_delete_task_conflict_does_not_emit_success_audit(client, monkeypatch):
    async def _noop_auth_gate():
        return None

    client.app.dependency_overrides[enforce_default_auth] = _noop_auth_gate
    headers = _admin_headers(client)
    audit_calls: list[dict] = []

    def _conflict(*, task_id, actor_id):
        raise TaskDeleteConflict("任务已有关联病历，不能删除")

    monkeypatch.setattr("app.routers.tasks.delete_empty_draft_task", _conflict)
    monkeypatch.setattr(
        "app.routers.tasks.audit_event",
        lambda _request, **kwargs: audit_calls.append(kwargs),
    )

    resp = client.delete("/api/v1/tasks/task-del-2", headers=headers)

    assert resp.status_code == 409, resp.text
    assert not any(call.get("action") == "tasks.lifecycle.delete" for call in audit_calls)
    client.app.dependency_overrides.clear()
