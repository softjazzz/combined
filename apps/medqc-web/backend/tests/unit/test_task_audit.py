from __future__ import annotations

from app.core.access_control import enforce_default_auth


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
    call_index = {"value": 0}

    async def _fake_async_execute(_query):
        idx = call_index["value"]
        call_index["value"] += 1
        if idx == 0:
            return _DummyResp(
                data=[
                    {"id": "tr-1", "task_id": "task-1", "status": "pending"},
                    {"id": "tr-2", "task_id": "task-1", "status": "pending"},
                ]
            )
        return _DummyResp(data=[{"ok": True}])

    monkeypatch.setattr("app.routers.tasks.get_supabase", lambda: _FakeSupabase())
    monkeypatch.setattr("app.routers.tasks.async_execute", _fake_async_execute)
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
