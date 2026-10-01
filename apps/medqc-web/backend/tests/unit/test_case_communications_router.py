"""HTTP 合同使用替身服务，不访问业务库。"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import case_communications as api
from app.services.defect_rectification_service import RectificationError


@pytest.fixture
def setup(monkeypatch):
    service = SimpleNamespace(**{name: Mock(return_value={"items": []}) for name in ("create", "candidates", "inbox", "read", "detail")})
    monkeypatch.setattr(api, "service", service)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_current_user] = lambda: {"id": "persisted-actor"}
    body = {"institute_id": "H", "patient_id": "P", "visit_id": "V", "scene": "final", "root_job_id": "J",
        "envelope_id": "E", "recipient_id": "D", "action": "opinion", "content": "合成质控意见", "request_id": "R"}
    return TestClient(app), service, body


def test_http_preserves_identity_and_pagination(setup):
    client, service, body = setup
    assert client.post("/api/v1/case-communications", json=body).status_code == 200
    service.create.assert_called_once_with("persisted-actor", {**body, "related_event_id": None})
    assert client.get("/api/v1/case-communications/inbox?page=2&page_size=100").status_code == 200
    service.inbox.assert_called_once_with("persisted-actor", 2, 100)
    assert client.post("/api/v1/case-communications/event/read").status_code == 200
    service.read.assert_called_once_with("persisted-actor", "event")
    assert client.get("/api/v1/case-communications/event").status_code == 200
    service.detail.assert_called_once_with("persisted-actor", "event")


@pytest.mark.parametrize("change", [{"scene": "coding"}, {"content": "x" * 2001}, {"content": "  "},
    {"rule_set_key": "untrusted"}, {"action": "withdraw"}, {"related_event_id": "original"}, {"patient_id": ""}])
def test_http_invalid_input_never_reaches_owner(setup, change):
    client, service, body = setup
    assert client.post("/api/v1/case-communications", json={**body, **change}).status_code == 422
    service.create.assert_not_called()


@pytest.mark.parametrize("query", ["page=0", "page_size=101", "page_size=0"])
def test_http_invalid_pagination(setup, query):
    client, service, _ = setup
    assert client.get(f"/api/v1/case-communications/inbox?{query}").status_code == 422
    service.inbox.assert_not_called()


@pytest.mark.parametrize("exception,status", [(RectificationError("越权", 403), 403),
    (RectificationError("幂等冲突", 409), 409), (RuntimeError("private database details"), 503)])
def test_http_failure_not_empty_success_or_exposed_internal_details(setup, exception, status):
    client, service, body = setup
    service.create.side_effect = exception
    response = client.post("/api/v1/case-communications", json=body)
    assert response.status_code == status
    assert "private database details" not in response.text
