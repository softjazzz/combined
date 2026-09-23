"""创建任务时显式选择已登记规则集，不连接业务数据库。"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks
from app.schemas.tasks import TaskResponse


class _Database:
    def __init__(self):
        self.inserted = []

    def table(self, name):
        assert name == "qc_tasks"
        return self

    def insert(self, payload):
        self.inserted.append(dict(payload))
        return self

    def execute(self):
        return SimpleNamespace(data=[self.inserted[-1]])


def _client(monkeypatch, database):
    app = FastAPI()
    app.include_router(tasks.router)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "creator-1", "display_name": "质控员", "roles": ["admin"]
    }
    monkeypatch.setattr(tasks, "get_supabase", lambda: database)

    async def execute(query):
        return query.execute()

    monkeypatch.setattr(tasks, "async_execute", execute)
    return TestClient(app)


@pytest.mark.parametrize(
    "payload",
    [
        {"task_name": "未选规则", "scene": "final"},
        {"task_name": "未选场景和规则"},
        {"task_name": "空规则", "scene": "final", "rule_set_key": "  "},
        {"task_name": "空规则值", "scene": "final", "rule_set_key": None},
        {"task_name": "未知规则", "scene": "running", "rule_set_key": "unknown_v1"},
        {"task_name": "缺场景", "rule_set_key": "sc_content_v1"},
        {"task_name": "空场景值", "scene": None, "rule_set_key": "sc_content_v1"},
        {"task_name": "门急诊误选终末", "scene": "outpatient", "rule_set_key": "sc_content_v1"},
        {"task_name": "运行误选终末", "scene": "running", "rule_set_key": "sc_content_v1"},
    ],
)
def test_invalid_rule_set_contract_is_422_before_database_access(monkeypatch, payload):
    database = _Database()
    response = _client(monkeypatch, database).post("/api/v1/tasks", json=payload)
    assert response.status_code == 422
    assert database.inserted == []


def test_explicit_rule_set_is_normalized_to_catalog_key(monkeypatch):
    database = _Database()
    response = _client(monkeypatch, database).post(
        "/api/v1/tasks",
        json={"task_name": "终末任务", "scene": "final", "rule_set_key": " SC_CONTENT_V1 "},
    )
    assert response.status_code == 200, response.text
    assert database.inserted[0]["rule_set_key"] == "sc_content_v1"
    assert response.json()["data"]["rule_set_key"] == "sc_content_v1"


def test_legacy_request_without_rule_set_is_rejected(monkeypatch):
    database = _Database()
    response = _client(monkeypatch, database).post(
        "/api/v1/tasks", json={"task_name": "旧任务"}
    )
    assert response.status_code == 422
    assert database.inserted == []


@pytest.mark.parametrize("rule_set_key", ["sc_content_v1", None])
def test_update_rejects_rule_set_change_before_database_access(monkeypatch, rule_set_key):
    database = _Database()
    response = _client(monkeypatch, database).put(
        "/api/v1/tasks/task-1", json={"rule_set_key": rule_set_key}
    )
    assert response.status_code == 422
    assert database.inserted == []


def test_schema_response_can_read_historical_missing_rule_set_key():
    response = TaskResponse.model_validate({
        "id": "legacy-1",
        "task_number": "QC-LEGACY-1",
        "task_name": "旧任务",
        "task_type": "one_time",
        "status": "draft",
        "creator_id": "creator-1",
        "created_at": "2026-09-22T00:00:00Z",
        "updated_at": "2026-09-22T00:00:00Z",
    })
    assert response.scene is None
    assert response.rule_set_key is None
