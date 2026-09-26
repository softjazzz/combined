"""用户筛选模板 HTTP 合同：本人范围、状态码、409 code、脱敏 503（SQLite 合成数据，不连真实库）。"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models.qc import QCUserFilterTemplate
from app.routers import filter_templates as routes
from app.services import filter_template_service as service

BASE = "/api/v1/filter-templates"
INPATIENT = "v5_records_inpatient"


@pytest.fixture
def sessions(monkeypatch):
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    QCUserFilterTemplate.__table__.create(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", factory)
    yield factory
    engine.dispose()


def client(user_id="u-1"):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {"id": user_id, "roles": ["qc_doctor"]}
    return TestClient(app)


def _post(http, name="常用", **extra):
    body = {"page_key": INPATIENT, "name": name, "filters": {"dept": "内科"}, **extra}
    return http.post(BASE, json=body)


def test_create_list_update_delete_flow(sessions):
    http = client()
    created = _post(http, is_default=True, filters={"review_state": ["pending_review", "pending_recheck"]})
    assert created.status_code == 200
    item = created.json()["data"]
    assert item["filters"] == {"review_state": ["pending_review", "pending_recheck"]}
    assert item["is_default"] is True and item["version"] == 1 and "owner_id" not in item

    listed = http.get(BASE, params={"page_key": INPATIENT})
    assert listed.status_code == 200
    assert [entry["id"] for entry in listed.json()["data"]["items"]] == [item["id"]]
    assert listed.json()["data"]["max_per_page"] == 20

    updated = http.put(f"{BASE}/{item['id']}", json={"version": 1, "name": "改名", "is_default": False})
    assert updated.status_code == 200
    assert updated.json()["data"]["version"] == 2 and updated.json()["data"]["is_default"] is False

    stale = http.put(f"{BASE}/{item['id']}", json={"version": 1, "name": "再改"})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "version_conflict"

    stale_delete = http.delete(f"{BASE}/{item['id']}", params={"version": 1})
    assert stale_delete.status_code == 409 and stale_delete.json()["detail"]["code"] == "version_conflict"
    deleted = http.delete(f"{BASE}/{item['id']}", params={"version": 2})
    assert deleted.status_code == 200 and deleted.json()["data"] == {"id": item["id"], "deleted": True}


def test_name_conflict_and_limit_reached_are_409_with_code(sessions):
    http = client()
    assert _post(http).status_code == 200
    duplicate = _post(http)
    assert duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "name_conflict"
    for index in range(service.MAX_TEMPLATES_PER_PAGE - 1):
        assert _post(http, name=f"模板{index}").status_code == 200
    over = _post(http, name="超限")
    assert over.status_code == 409 and over.json()["detail"]["code"] == "limit_reached"


def test_other_users_template_is_404(sessions):
    item = _post(client("u-1")).json()["data"]
    other = client("u-2")
    assert other.put(f"{BASE}/{item['id']}", json={"version": 1, "name": "x"}).status_code == 404
    assert other.delete(f"{BASE}/{item['id']}", params={"version": 1}).status_code == 404
    assert other.get(BASE, params={"page_key": INPATIENT}).json()["data"]["items"] == []


@pytest.mark.parametrize("body", [
    {"page_key": "v5_records_outpatient", "name": "x", "filters": {}},
    {"page_key": INPATIENT, "name": "x", "filters": {"page": 1}},
    {"page_key": INPATIENT, "name": "x", "filters": {"review_state": ["rejected"]}},
    {"page_key": INPATIENT, "name": "x", "filters": {"start_date": "20260901"}},
    {"page_key": INPATIENT, "name": "  ", "filters": {}},
    {"page_key": INPATIENT, "name": "x", "filters": {}, "owner_id": "u-2"},
    {"page_key": INPATIENT, "name": "x", "filters": {}, "is_default": "yes"},
    {"page_key": INPATIENT, "name": "x"},
])
def test_create_rejects_invalid_body_with_422(sessions, body):
    assert client().post(BASE, json=body).status_code == 422


@pytest.mark.parametrize("body", [
    {"name": "x"},
    {"version": 0, "name": "x"},
    {"version": "1", "name": "x"},
    {"version": 1},
    {"version": 1, "page_key": INPATIENT},
    {"version": 1, "filters": {"unknown": 1}},
])
def test_update_rejects_invalid_body_with_422(sessions, body):
    item = _post(client()).json()["data"]
    assert client().put(f"{BASE}/{item['id']}", json=body).status_code == 422


def test_list_and_delete_parameter_validation(sessions):
    http = client()
    assert http.get(BASE).status_code == 422
    assert http.get(BASE, params={"page_key": "other"}).status_code == 422
    assert http.delete(f"{BASE}/abc").status_code == 422


def test_missing_identity_is_401(sessions):
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_current_user] = lambda: {"roles": ["qc_doctor"]}
    assert TestClient(app).get(BASE, params={"page_key": INPATIENT}).status_code == 401


def test_database_failure_is_desensitized_503(monkeypatch, caplog):
    def broken(**_kwargs):
        raise service.FilterTemplateUnavailable("SELECT secret FROM qc_user_filter_templates")

    monkeypatch.setattr(routes, "list_templates", broken)
    monkeypatch.setattr(routes, "create_template", broken)
    http = client()
    response = http.get(BASE, params={"page_key": INPATIENT})
    assert response.status_code == 503
    assert response.json()["detail"] == "筛选模板服务暂不可用，请稍后重试"
    created = http.post(BASE, json={"page_key": INPATIENT, "name": "x", "filters": {}})
    assert created.status_code == 503 and "secret" not in created.text
    assert "secret" not in caplog.text
