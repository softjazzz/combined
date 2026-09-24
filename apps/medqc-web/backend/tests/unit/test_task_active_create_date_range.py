"""显式在院任务创建时的日期边界，不启动应用生命周期或访问真实数据库。"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import tasks
from app.services.case_scope_service import CaseScopeService
from app.services.task_sampling_service import validate_scoped_sampling_config


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
    monkeypatch.setattr(
        CaseScopeService,
        "resolve_hospitalization_scope",
        lambda *_args, **_kwargs: pytest.fail("创建任务不得查询在院候选源"),
    )
    return TestClient(app)


def _payload(date_range=None, *, scene="running", active=True):
    payload = {
        "task_name": "在院任务",
        "scene": scene,
        "rule_set_key": "luxian_0609_qc_v1" if scene == "running" else "sc_content_v1",
        "sampling_config": {"case_scope": "active"} if active else {},
    }
    if date_range is not None:
        payload["date_range"] = date_range
    return payload


@pytest.mark.parametrize("days_ago", [0, 180])
def test_active_running_create_accepts_boundary_start_without_source(monkeypatch, days_ago):
    database = _Database()
    today = datetime.now(timezone(timedelta(hours=8))).date()
    date_range = {"start": (today - timedelta(days=days_ago)).isoformat(), "end": today.isoformat()}
    response = _client(monkeypatch, database).post("/api/v1/tasks", json=_payload(date_range))
    assert response.status_code == 200, response.text
    assert database.inserted[0]["date_range"] == date_range


@pytest.mark.parametrize(
    "invalid_window",
    [
        lambda today: {"start": (today + timedelta(days=1)).isoformat()},
        lambda today: {"start": (today - timedelta(days=181)).isoformat()},
        lambda today: {"start": today.isoformat(), "end": (today - timedelta(days=1)).isoformat()},
        lambda today: {"start": "2026-2-1"},
        lambda today: {"start": "2026-02-30"},
        lambda today: {"end": "2026-02-30"},
    ],
)
def test_active_running_create_rejects_invalid_window_without_insert(monkeypatch, invalid_window):
    database = _Database()
    today = datetime.now(timezone(timedelta(hours=8))).date()
    response = _client(monkeypatch, database).post(
        "/api/v1/tasks", json=_payload(invalid_window(today))
    )
    assert response.status_code == 422
    assert database.inserted == []


def test_active_running_create_allows_missing_date_range(monkeypatch):
    database = _Database()
    response = _client(monkeypatch, database).post("/api/v1/tasks", json=_payload())
    assert response.status_code == 200, response.text
    assert database.inserted[0]["date_range"] is None


@pytest.mark.parametrize(
    ("scene", "active"),
    [("final", False), ("running", False)],
)
def test_other_scope_create_preserves_existing_date_behavior(monkeypatch, scene, active):
    database = _Database()
    response = _client(monkeypatch, database).post(
        "/api/v1/tasks", json=_payload({"start": "2026-2-1"}, scene=scene, active=active)
    )
    assert response.status_code == 200, response.text
    assert len(database.inserted) == 1


@pytest.mark.parametrize(
    ("method", "config"),
    [
        ("count", {"case_scope": "active", "total": 0}),
        ("count", {"case_scope": "active", "total": "2"}),
        ("count", {"case_scope": "active", "total": True}),
        ("count", {"case_scope": "active", "by_department": "false"}),
        ("percentage", {"case_scope": "active", "percentage": 0}),
        ("percentage", {"case_scope": "active", "percentage": 101}),
        ("percentage", {"case_scope": "active", "percentage": "10"}),
        ("percentage", {"case_scope": "active", "group_by": "doctor_name"}),
    ],
)
def test_active_running_create_rejects_unsampleable_config_before_insert(monkeypatch, method, config):
    database = _Database()
    payload = _payload()
    payload.update(sampling_method=method, sampling_config=config)
    response = _client(monkeypatch, database).post("/api/v1/tasks", json=payload)
    assert response.status_code == 422, response.text
    assert database.inserted == []


@pytest.mark.parametrize(
    ("method", "config"),
    [
        ("count", {"case_scope": "active", "total": 2, "by_department": True}),
        ("percentage", {"case_scope": "active", "percentage": 10, "group_by": "department"}),
    ],
)
def test_active_running_create_keeps_valid_sampling_config(monkeypatch, method, config):
    database = _Database()
    payload = _payload()
    payload.update(sampling_method=method, sampling_config=config)
    response = _client(monkeypatch, database).post("/api/v1/tasks", json=payload)
    assert response.status_code == 200, response.text
    assert database.inserted[0]["sampling_config"] == config


@pytest.mark.parametrize(
    ("method", "config"),
    [
        ("count", {"total": -1}),
        ("count", {"by_department": "true"}),
        ("percentage", {"percentage": 101}),
        ("percentage", {"group_by": "doctor_name"}),
    ],
)
def test_outpatient_sampling_config_uses_same_contract(method, config):
    with pytest.raises(ValueError):
        validate_scoped_sampling_config("outpatient", method, config)


@pytest.mark.parametrize(
    ("method", "config"),
    [
        ("count", {"total": 0}),
        ("percentage", {"percentage": 25, "group_by": "doctor_name"}),
    ],
)
def test_outpatient_create_rejects_invalid_sampling_before_insert(monkeypatch, method, config):
    database = _Database()
    monkeypatch.setattr(
        tasks,
        "get_sichuan_rule_set",
        lambda key: SimpleNamespace(key=key, scope="outpatient", version="synthetic-v1"),
    )
    payload = _payload(scene="outpatient")
    payload.update(rule_set_key="synthetic-outpatient", sampling_method=method, sampling_config=config)
    response = _client(monkeypatch, database).post("/api/v1/tasks", json=payload)
    assert response.status_code == 422, response.text
    assert database.inserted == []


def test_legacy_running_creation_does_not_apply_active_sampling_validation(monkeypatch):
    database = _Database()
    payload = _payload(active=False)
    payload.update(sampling_method="percentage", sampling_config={"group_by": "doctor_name"})
    response = _client(monkeypatch, database).post("/api/v1/tasks", json=payload)
    assert response.status_code == 200, response.text
    assert database.inserted[0]["sampling_config"] == {"group_by": "doctor_name"}
