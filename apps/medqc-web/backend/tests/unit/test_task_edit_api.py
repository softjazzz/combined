from __future__ import annotations

import json

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCTask, QCTaskQCRun, QCTaskRecord
from app.routers import task_edits as routes
from app.services import task_edit_service as service


@pytest.fixture
def http(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCTask.__table__.create(engine)
    QCTaskRecord.__table__.create(engine)
    QCTaskQCRun.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    with factory.begin() as session:
        session.execute(sa.insert(QCTask.__table__).values(
            id="task-1", task_number="TASK-1", task_name="原任务", task_type="one_time",
            scene="outpatient", rule_set_key="outpatient", rule_set_version="v1",
            department_filter=json.dumps([]), record_ids=json.dumps([]), record_refs=[],
            sampling_method="all", sampling_config=json.dumps({}), assign_method="by_ratio",
            assignee_config=json.dumps({}), status="draft", progress=0, total_records=0,
            completed_records=0, creator_id="owner", creator_name="创建人",
            configuration_version=1,
        ))
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {
        "id": "owner", "roles": ["admin"],
    }
    yield TestClient(app)
    engine.dispose()


def draft_body(version=1):
    return {
        "configuration_version": version,
        "task_name": "更新任务",
        "deadline": "2026-10-01",
        "date_range": None,
        "department_filter": [],
        "record_refs": [],
        "sampling_method": "all",
        "sampling_config": {},
        "assign_method": "by_ratio",
        "assignee_config": {},
    }


def test_get_put_patch_share_strict_response_contract(http, monkeypatch):
    audits = []
    monkeypatch.setattr(routes, "audit_event", lambda *_args, **kwargs: audits.append(kwargs))
    read = http.get("/api/v1/task-edits/task-1")
    assert read.status_code == 200
    assert read.json()["data"]["configuration_version"] == 1

    replaced = http.put("/api/v1/task-edits/task-1/draft-configuration", json=draft_body())
    assert replaced.status_code == 200
    assert replaced.json()["data"]["configuration_version"] == 2
    assert "changed_fields" not in replaced.json()["data"]

    patched = http.patch("/api/v1/task-edits/task-1/metadata", json={
        "configuration_version": 2, "deadline": None,
    })
    assert patched.status_code == 200
    assert patched.json()["data"]["deadline"] is None
    assert patched.json()["data"]["configuration_version"] == 3
    assert [item["details"]["previous_configuration_version"] for item in audits] == [1, 2]
    assert [item["details"]["configuration_version"] for item in audits] == [2, 3]
    assert all("record_refs" not in item["details"] for item in audits)


def test_api_rejects_frozen_and_legacy_fields_and_returns_conflict_code(http):
    frozen = draft_body()
    frozen["scene"] = "final"
    assert http.put("/api/v1/task-edits/task-1/draft-configuration", json=frozen).status_code == 422
    assert http.patch("/api/v1/task-edits/task-1/metadata", json={
        "configuration_version": 1, "record_ids": ["legacy"],
    }).status_code == 422

    assert http.put("/api/v1/task-edits/task-1/draft-configuration", json=draft_body()).status_code == 200
    stale = http.patch("/api/v1/task-edits/task-1/metadata", json={
        "configuration_version": 1, "task_name": "过期",
    })
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "version_conflict"


def test_api_desensitizes_unavailable_error(http, monkeypatch):
    def broken(*_args, **_kwargs):
        raise service.TaskEditUnavailable("SELECT patient secret")

    monkeypatch.setattr(service, "get_task_edit", broken)
    response = http.get("/api/v1/task-edits/task-1")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "task_edit_unavailable"
    assert "secret" not in response.text
