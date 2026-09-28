"""任务模板 HTTP 合同，不连接真实数据库。"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTaskTemplate
from app.routers import tasks as routes
from app.services import task_template_service as service

BASE = "/api/v1/tasks/templates"


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCTaskTemplate.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def client(user_id="u-1"):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {
        "id": user_id, "roles": ["admin"],
    }
    return TestClient(app)


def body(name="常用"):
    return {
        "name": name,
        "config": {
            "scene": "final",
            "rule_set_key": "sc_content_fast_v1",
            "date_range": None,
            "department_filter": [],
            "sampling_method": "all",
            "sampling_config": {},
            "assign_method": "by_ratio",
            "assignee_config": {},
        },
    }


def test_http_flow_and_other_owner_isolation(sessions):
    http = client()
    created = http.post(BASE, json=body())
    assert created.status_code == 200
    item = created.json()["data"]
    assert item["usable"] is True and item["version"] == 1
    assert client("u-2").get(BASE).json()["data"]["items"] == []
    assert client("u-2").put(
        f"{BASE}/{item['id']}", json={"version": 1, "name": "偷改"},
    ).status_code == 404

    updated = http.put(f"{BASE}/{item['id']}", json={"version": 1, "name": "改名"})
    assert updated.status_code == 200 and updated.json()["data"]["version"] == 2
    stale = http.delete(f"{BASE}/{item['id']}", params={"version": 1})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "version_conflict"
    assert http.delete(f"{BASE}/{item['id']}", params={"version": 2}).status_code == 200


def test_http_rejects_forbidden_fields_and_reports_conflict(sessions):
    invalid = body()
    invalid["config"]["task_name"] = "不得保存"
    assert client().post(BASE, json=invalid).status_code == 422
    assert client().post(BASE, json=body()).status_code == 200
    duplicate = client().post(BASE, json=body())
    assert duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "name_conflict"


def test_missing_identity_and_unavailable_are_desensitized(sessions, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {"roles": ["admin"]}
    assert TestClient(app).get(BASE).status_code == 401

    def broken(**_kwargs):
        raise service.TaskTemplateUnavailable("SELECT secret")

    monkeypatch.setattr(routes, "list_task_templates", broken)
    response = client().get(BASE)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "template_unavailable"
    assert "secret" not in response.text

