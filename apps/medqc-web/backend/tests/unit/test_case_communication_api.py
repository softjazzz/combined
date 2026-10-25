from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.routers import case_communications as api
from app.services.defect_rectification_service import RectificationError


@pytest.fixture
def client(monkeypatch):
    service = Mock()
    monkeypatch.setattr(api, "service", service)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: {"id": "persistent-login"}
    return TestClient(app), service


def payload():
    return dict(
        institute_id="H",
        patient_id="P",
        visit_id="V",
        scene="running",
        root_job_id="J",
        envelope_id="E",
        rule_set_key="K",
        rule_set_version="1",
        recipient_id="doc",
        action="urge",
        content="催办说明",
        request_id="request",
    )


def test_actor_from_login_and_full_frozen_source_preserved(client):
    http, service = client
    service.create.return_value = {"id": "event"}
    body = payload()
    assert http.post("/api/v1/case-communications", json=body).status_code == 200
    service.create.assert_called_once_with(
        "persistent-login", dict(body, related_event_id=None)
    )


def test_candidates_only_accept_case_coordinates_and_expected_job(client):
    http, service = client
    body = {
        key: payload()[key]
        for key in ("institute_id", "patient_id", "visit_id", "root_job_id")
    }
    service.candidates.return_value = {
        "source": {**body, "scene": "running"},
        "doctors": [],
        "items": [],
    }
    response = http.post("/api/v1/case-communications/candidates", json=body)
    assert response.status_code == 200
    assert response.json()["data"]["source"]["scene"] == "running"
    service.candidates.assert_called_once_with("persistent-login", body)
    assert (
        http.post(
            "/api/v1/case-communications/candidates", json={**body, "scene": "final"}
        ).status_code
        == 422
    )


@pytest.mark.parametrize(
    "change",
    [
        dict(actor_id="forged"),
        dict(scene="outpatient_emergency"),
        dict(rule_set_version=""),
        dict(content="  "),
        dict(action="withdraw"),
        dict(related_event_id="other"),
    ],
)
def test_invalid_contract_never_reaches_service(client, change):
    http, service = client
    assert (
        http.post(
            "/api/v1/case-communications", json=dict(payload(), **change)
        ).status_code
        == 422
    )
    service.create.assert_not_called()


def test_inbox_route_is_exact_and_pagination_bounded(client):
    http, service = client
    service.inbox.return_value = {"items": [], "total": 0}
    assert http.get("/api/v1/case-communications/inbox").status_code == 200
    service.inbox.assert_called_once_with("persistent-login", 1, 20)
    service.detail.assert_not_called()
    assert (
        http.get("/api/v1/case-communications/inbox?page_size=101").status_code == 422
    )


@pytest.mark.parametrize("code", [403, 404, 409])
def test_expected_business_failures_preserve_http_status(client, code):
    http, service = client
    service.detail.side_effect = RectificationError("拒绝读取", code)
    assert http.get("/api/v1/case-communications/e1").status_code == code


def test_missing_table_or_unknown_write_failure_is_redacted(client):
    http, service = client
    service.create.side_effect = RuntimeError("postgresql://synthetic-secret")
    response = http.post("/api/v1/case-communications", json=payload())
    assert response.status_code == 503
    assert "synthetic-secret" not in response.text
    assert "勿重复提交" in response.text
