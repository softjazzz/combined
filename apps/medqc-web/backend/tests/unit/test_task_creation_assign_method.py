"""任务创建只接受可执行的分配方式（比例/原质控员/科室），不触达真实数据库。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import tasks
from app.schemas.tasks import AssignMethod, TaskCreateRequest


class FakeTasksTable:
    def __init__(self, inserted):
        self.inserted = inserted

    def insert(self, row):
        self.inserted.append(row)
        return row


class FakeSupabase:
    def __init__(self, inserted):
        self.inserted = inserted

    def table(self, name):
        assert name == "qc_tasks"
        return FakeTasksTable(self.inserted)


@pytest.fixture
def client(monkeypatch):
    inserted = []
    fake_db = FakeSupabase(inserted)
    monkeypatch.setattr(tasks, "get_supabase", lambda: fake_db)
    monkeypatch.setattr(
        tasks, "get_sichuan_rule_set",
        lambda key: SimpleNamespace(key=key, version="test", scope="final"),
    )

    async def fake_execute(query):
        return SimpleNamespace(data=[query])

    monkeypatch.setattr(tasks, "async_execute", fake_execute)
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[tasks.get_current_user] = lambda: {
        "id": "qc-manager", "roles": ["qc_manager"], "display_name": "质控员",
    }
    with TestClient(app) as test_client:
        yield test_client, inserted


def payload(**overrides):
    return {
        "task_name": "测试任务", "scene": "final", "rule_set_key": "test-final",
        **overrides,
    }


def test_omitted_assign_method_defaults_to_ratio_in_schema_and_persistence(client):
    test_client, inserted = client
    model = TaskCreateRequest.model_validate(payload())
    assert model.assign_method is AssignMethod.BY_RATIO

    response = test_client.post("/api/v1/tasks", json=payload())
    assert response.status_code == 200
    assert len(inserted) == 1
    assert inserted[0]["assign_method"] == "by_ratio"
    assert response.json()["data"]["assign_method"] == "by_ratio"


def test_explicit_ratio_still_creates_task(client):
    test_client, inserted = client
    response = test_client.post(
        "/api/v1/tasks", json=payload(assign_method="by_ratio"),
    )
    assert response.status_code == 200
    assert len(inserted) == 1
    assert inserted[0]["assign_method"] == "by_ratio"


@pytest.mark.parametrize("assign_method", ["keep", "by_type"])
def test_unimplemented_methods_rejected_before_insert(client, assign_method):
    test_client, inserted = client
    response = test_client.post(
        "/api/v1/tasks", json=payload(assign_method=assign_method),
    )
    assert response.status_code == 422
    assert inserted == []


@pytest.mark.parametrize("assign_method", ["unrecognized", "", None, 42])
def test_malformed_method_rejected_before_insert(client, assign_method):
    test_client, inserted = client
    response = test_client.post(
        "/api/v1/tasks", json=payload(assign_method=assign_method),
    )
    assert response.status_code == 422
    assert inserted == []


@pytest.mark.parametrize("assign_method,config", [
    ("by_department", {}),
    ("by_original_reviewer", {"fallback": "by_ratio"}),
    ("by_original_reviewer", {"fallback": "reject"}),
])
def test_new_assign_methods_accepted(client, assign_method, config):
    test_client, inserted = client
    response = test_client.post(
        "/api/v1/tasks", json=payload(assign_method=assign_method, assignee_config=config),
    )
    assert response.status_code == 200
    assert len(inserted) == 1
    assert inserted[0]["assign_method"] == assign_method
    assert inserted[0]["assignee_config"] == config


@pytest.mark.parametrize("config", [None, {}, {"fallback": "keep"}, {"fallback": ""}])
def test_original_reviewer_requires_fallback(client, config):
    test_client, inserted = client
    body = payload(assign_method="by_original_reviewer")
    if config is not None:
        body["assignee_config"] = config
    response = test_client.post("/api/v1/tasks", json=body)
    assert response.status_code == 422
    assert "fallback" in response.text
    assert inserted == []


def test_record_type_method_unavailable_without_insert(client):
    test_client, inserted = client
    response = test_client.post("/api/v1/tasks", json=payload(assign_method="by_record_type"))
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "method_unavailable"
    assert detail["reason"]
    assert inserted == []
