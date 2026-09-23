from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.access_control import enforce_default_auth


@pytest.fixture
def client(app):
    # 本文件只测路由合同，不启动会在真实数据库重建视图的 lifespan。
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()


class _DummyResp:
    def __init__(self, data=None, count=None):
        self.data = data if data is not None else []
        self.count = count


class _FakeQuery:
    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def update(self, *_args, **_kwargs):
        return self

    def delete(self, *_args, **_kwargs):
        return self


class _FakeSupabase:
    def table(self, _name: str):
        return _FakeQuery()


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

    async def _fake_async_execute(_query):
        return _DummyResp(data=[{"ok": True}])

    monkeypatch.setattr("app.routers.tasks.get_supabase", lambda: _FakeSupabase())
    monkeypatch.setattr("app.routers.tasks.async_execute", _fake_async_execute)
    monkeypatch.setattr(
        "app.routers.tasks.audit_event",
        lambda _request, **kwargs: audit_calls.append(kwargs),
    )

    resp = client.delete("/api/v1/tasks/task-del-1", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert any(
        call.get("action") == "tasks.lifecycle.delete"
        and call.get("details", {}).get("task_id") == "task-del-1"
        for call in audit_calls
    )
    client.app.dependency_overrides.clear()
