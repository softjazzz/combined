from __future__ import annotations

import pytest

from app.core.security import get_current_user


class _FakeQuery:
    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def gte(self, *args, **kwargs):
        return self

    def lt(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self


class _FakeSupabase:
    def table(self, _name: str):
        return _FakeQuery()


class _Resp:
    def __init__(self, data):
        self.data = data
        self.count = len(data)


@pytest.fixture(autouse=True)
def _override_user(client):
    client.app.dependency_overrides[get_current_user] = lambda: {"id": "u-test-notif"}
    yield
    client.app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.api
def test_notifications_overview_aggregate_and_sort(client, monkeypatch):
    monkeypatch.setattr("app.routers.notifications._ensure_db", lambda: _FakeSupabase())

    rows = [
        {
            "id": "n1",
            "recipient_id": "u-test-notif",
            "type": "defect_urge",
            "severity": "warning",
            "department": "内科",
            "record_id": "R001",
            "title": "缺陷催办",
            "content": "请处理缺陷 A",
            "created_at": "2026-03-23T10:00:00Z",
            "is_read": False,
        },
        {
            "id": "n2",
            "recipient_id": "u-test-notif",
            "type": "defect_urge",
            "severity": "warning",
            "department": "内科",
            "record_id": "R001",
            "title": "缺陷催办",
            "content": "请处理缺陷 A-2",
            "created_at": "2026-03-23T11:00:00Z",
            "is_read": True,
        },
        {
            "id": "n3",
            "recipient_id": "u-test-notif",
            "type": "task_assign",
            "severity": "critical",
            "department": "外科",
            "record_id": "R002",
            "title": "任务分配",
            "content": "新任务",
            "created_at": "2026-03-23T09:00:00Z",
            "is_read": False,
        },
    ]

    async def _fake_async_execute(_query):
        return _Resp(rows)

    monkeypatch.setattr("app.routers.notifications.async_execute", _fake_async_execute)

    resp = client.get("/api/v1/notifications/overview?date=2026-03-23")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    items = body["data"]["items"]
    assert len(items) == 2

    defect_item = next(item for item in items if item["type"] == "defect_urge")
    assert defect_item["occurrence_count"] == 2
    assert defect_item["unread_count"] == 1
    assert set(defect_item["source_notification_ids"]) == {"n1", "n2"}
