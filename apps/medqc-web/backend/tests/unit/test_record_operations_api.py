"""病历级操作记录 HTTP 合同：权限、参数 422、脱敏 503、路由挂载（SQLite 合成数据，不连真实库）。"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.routers import record_operations as routes
from tests.unit.test_case_operation_timeline_service import add_rectification, build_env
from app.database.models.qc import SysUser

PATH = "/api/v1/record-operations/case"
CASE = {"institute_id": "hospital-A", "patient_id": "P1", "visit_id": "V1"}


@pytest.fixture
def env(monkeypatch):
    engine, factory, tables = build_env(monkeypatch)
    yield engine
    engine.dispose()


def client(*, user_id="mgr-1", roles=("qc_manager",)):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {
        "id": user_id, "roles": list(roles),
    }
    return TestClient(app)


def test_case_timeline_response_shape(env):
    res = client().get(PATH, params=CASE)
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total"] == 6 and data["limit"] == 100 and len(data["items"]) == 6
    assert {k: data[k] for k in CASE} == CASE
    first = data["items"][0]
    assert first == {
        "id": "task_record:tr-1:completed", "type": "task_record_completed",
        "occurred_at": "2026-09-01T08:40:00", "actor_id": "qc-1", "actor_name": "合成质控员",
        "summary": {"task_id": "task-1", "task_record_id": "tr-1", "completed_run_number": 2},
    }
    assert {item["type"] for item in data["items"]} == {
        "qc_run_completed", "record_review", "manual_defect_created",
        "manual_defect_reviewed", "task_record_completed",
    }


def test_limit_query(env):
    data = client().get(PATH, params={**CASE, "limit": 3}).json()["data"]
    assert data["total"] == 6 and data["limit"] == 3 and len(data["items"]) == 3


def test_rectification_events_http_contract(monkeypatch):
    engine, factory, _ = build_env(monkeypatch)
    try:
        add_rectification(factory)
        data = client().get(PATH, params=CASE).json()["data"]
        assert data["total"] == 11
        urge = next(item for item in data["items"] if item["type"] == "rectification_urged")
        assert urge["summary"]["new_status"] == "pending"
        assert urge["summary"]["root_job_id"] == "old-job"
        assert urge["summary"]["envelope_id"] == "old-envelope"
    finally:
        engine.dispose()


@pytest.mark.parametrize("changes", [
    {"is_active": False}, {"institute_id": "hospital-B"}, {"roles_json": '["doctor"]'},
])
def test_stale_token_does_not_override_persistent_authorization(env, changes):
    with env.begin() as connection:
        connection.execute(sa.update(SysUser).where(SysUser.id == "mgr-1").values(**changes))
    assert client().get(PATH, params=CASE).status_code == 403


@pytest.mark.parametrize("user_id", [None, ""])
def test_missing_identity_rejected(env, user_id):
    assert client(user_id=user_id).get(PATH, params=CASE).status_code == 401


@pytest.mark.parametrize("roles", [("doctor",), ("qc_staff",), ()])
def test_without_review_permission_forbidden(env, roles):
    assert client(roles=roles).get(PATH, params=CASE).status_code == 403


@pytest.mark.parametrize("params", [
    {"patient_id": "P1", "visit_id": "V1"},
    {**CASE, "institute_id": ""},
    {**CASE, "patient_id": " P1"},
    {**CASE, "visit_id": "V1 "},
    {**CASE, "visit_id": "x" * 129},
    {**CASE, "limit": 0},
    {**CASE, "limit": 201},
    {**CASE, "limit": "abc"},
])
def test_invalid_params_422(env, params):
    assert client().get(PATH, params=params).status_code == 422


def test_any_source_failure_returns_masked_503(env):
    def fail(conn, cursor, statement, *args):
        if "qc_record_reviews" in statement:
            raise OperationalError("SELECT secret FROM qc_record_reviews", {}, Exception("boom"))

    sa.event.listen(env, "before_cursor_execute", fail)
    res = client().get(PATH, params=CASE)
    assert res.status_code == 503
    body = res.text
    assert "病例操作记录服务暂不可用" in body
    for leaked in ("secret", "qc_record_reviews", "boom", "SELECT", "P1"):
        assert leaked not in body


def test_route_mounted_on_production_app():
    from app.main import create_app

    def collect_paths(route_list):
        paths = set()
        for route in route_list:
            if path := getattr(route, "path", None):
                paths.add(path)
            if original_router := getattr(route, "original_router", None):
                paths.update(collect_paths(original_router.routes))
        return paths

    assert PATH in collect_paths(create_app().routes)
